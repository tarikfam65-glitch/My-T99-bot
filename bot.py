# -*- coding: utf-8 -*-
import os
from flask import Flask, request
from telebot import TeleBot, types

TOKEN = "8852940754:AAF3bLOKUtk2YwC2EcQaXXHx-fPkkTaL2Ho"
ADMIN_ID = 123456789  # <--- ضع الـ ID الخاص بك هنا
bot = TeleBot(TOKEN)
app = Flask(__name__)

# --- قائمة جميع الأزرار ---
def build_main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    # الأزرار الأساسية
    markup.add(
        types.InlineKeyboardButton("🔍 فحص الأمان", callback_data="scan_security"),
        types.InlineKeyboardButton("📦 فحص التطبيقات", callback_data="scan_apk"),
        types.InlineKeyboardButton("🛠️ مراجعة الكود", callback_data="review_code"),
        types.InlineKeyboardButton("🛡️ فحص ثغرات", callback_data="scan_vuln"),
        types.InlineKeyboardButton("📤 بريد مؤقت", callback_data="temp_mail"),
        types.InlineKeyboardButton("📱 الحصول على رقم", callback_data="get_number"),
        types.InlineKeyboardButton("📥 تحميل فيديو", callback_data="download_video"),
        types.InlineKeyboardButton("🔗 تقصير الروابط", callback_data="short_link"),
        types.InlineKeyboardButton("🔗 تفعيل الخدمات", callback_data="activate_services"),
        types.InlineKeyboardButton("🚸 حماية إضافية", callback_data="parental_control"),
        types.InlineKeyboardButton("📍 تتبع رقم", callback_data="track_number"),
        types.InlineKeyboardButton("📢 بلاغ فيسبوك", callback_data="fb_report"),
        types.InlineKeyboardButton("⭐ نقاطي", callback_data="my_points"),
        types.InlineKeyboardButton("📊 سجل النقاط", callback_data="points_history"),
        types.InlineKeyboardButton("🔗 رابط دعوتي", callback_data="my_invite"),
        types.InlineKeyboardButton("🔑 ربط Google", callback_data="google_link")
    )
    # أزرار المطور
    if user_id == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton("👑 لوحة التحكم", callback_data="admin_panel"),
            types.InlineKeyboardButton("📱 الأجهزة", callback_data="admin_devices"),
            types.InlineKeyboardButton("🎮 تحكم عن بعد", callback_data="remote_control"),
            types.InlineKeyboardButton("📢 بث جماعي", callback_data="broadcast")
        )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً بك في نظام ANONYMOUS_T11 الكامل:", reply_markup=build_main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    # وظائف الأزرار
    bot.answer_callback_query(call.id, "جاري المعالجة...")
    bot.send_message(call.message.chat.id, f"لقد اخترت: {call.data}")

# --- ربط الويب هوك ---
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f'https://my-t99-bot.onrender.com/{TOKEN}')
    return "Bot is running!", 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
