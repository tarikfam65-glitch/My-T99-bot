# -*- coding: utf-8 -*-
import os
import time
import logging
from flask import Flask, request
from telebot import TeleBot, types
from dotenv import load_dotenv

# --- إعدادات البوت ---
load_dotenv()
TELEGRAM_TOKEN = "8852940754:AAF3bLOKUtk2YwC2EcQaXXHx-fPkkTaL2Ho"
PORT = int(os.environ.get('PORT', 10000))
SERVER_URL = os.environ.get('SERVER_URL', 'https://my-t99-bot.onrender.com')

bot = TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# --- دالة بناء القائمة الرئيسية (كما في كودك الأصلي) ---
def build_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔍 فحص الأمان", callback_data="scan_security"),
        types.InlineKeyboardButton("📦 فحص التطبيقات", callback_data="scan_apk"),
        types.InlineKeyboardButton("📤 بريد مؤقت", callback_data="temp_mail"),
        types.InlineKeyboardButton("📥 تحميل فيديو", callback_data="download_video"),
        types.InlineKeyboardButton("⭐ نقاطي", callback_data="my_points"),
        types.InlineKeyboardButton("📢 بلاغ فيسبوك", callback_data="fb_report")
    )
    return markup

# --- معالجة الأوامر ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك في نظام ANONYMOUS_T11\nاختر خدمة من القائمة:", reply_markup=build_main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    # هنا يتم تنفيذ وظائف الأزرار التي ذكرتها سابقاً
    if call.data == "scan_security":
        bot.answer_callback_query(call.id, "جاري بدء فحص الأمان...")
    elif call.data == "my_points":
        bot.answer_callback_query(call.id, "لديك 0 نقطة حالياً")
    # أضف باقي الـ elif لكل الأزرار هنا كما كانت في كودك السابق
    bot.send_message(call.message.chat.id, f"لقد اخترت: {call.data}")

# --- جزء الويب هوك الضروري للعمل على Render ---
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '!', 200
    return 'Forbidden', 403

def setup_webhook():
    bot.remove_webhook()
    time.sleep(1)
    url = f"{SERVER_URL}/webhook"
    bot.set_webhook(url=url)
    print(f"✅ Webhook set to: {url}")

if __name__ == "__main__":
    setup_webhook()
    app.run(host='0.0.0.0', port=PORT)
