import asyncio
import random
import time
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from langchain_google_genai import ChatGoogleGenerativeAI
from google.generativeai import configure
from database import *
from persona import *
from voice import *

# ===================== الإعدادات =====================
TOKEN = "8852940754:AAFtWl51XMFC8OlrH_KXL7UAg6gmYiPcDg0"  # ضع توكن البوت
GOOGLE_API_KEY = "AIzaSyBSRSVmlJ3_B-Tz3alzJ8-sFq2VwMqN3ZU"  # ضع مفتاح Gemini
configure(api_key=GOOGLE_API_KEY)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
user_mode = {}
user_msg_count = {}

# ===================== قائمة المطورين =====================
DEVELOPER_ID = 7965377136
ADMIN_IDS = [7965377136, 6688256875, 8080689721]  # أضف معرفات المديرين هنا

# ===================== القوائم =====================
def main_menu():
    keyboard = [
        [types.KeyboardButton(text="📊 تقرير")],
        [types.KeyboardButton(text="🎤 تحدث معي")],
        [types.KeyboardButton(text="❓ مساعدة")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def build_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton("📊 تقرير", callback_data="report"),
        types.InlineKeyboardButton("🎤 تحدث معي", callback_data="voice")
    )
    markup.row(
        types.InlineKeyboardButton("📖 عن T11", callback_data="about"),
        types.InlineKeyboardButton("❓ مساعدة", callback_data="help")
    )
    return markup

# ===================== المعالجات =====================
@router.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    user_mode[user_id] = "assistant"
    user_msg_count[user_id] = 0
    
    # فيديو ترحيبي (رابط فيديو)
    try:
        video_file = FSInputFile("welcome.mp4")  # ضع فيديو الترحيب في نفس المجلد
        await bot.send_video(
            chat_id=message.chat.id,
            video=video_file,
            caption="مرحباً بك في بروتوكول T11.\nأنا الكيان.\nاختر خدمة من القائمة.",
            reply_markup=build_menu()
        )
    except:
        # إذا لم يوجد فيديو، أرسل نصاً
        await message.answer(
            "مرحباً بك في بروتوكول T11.\nأنا الكيان.\nاختر خدمة من القائمة.",
            reply_markup=build_menu()
        )
    
    save_message(user_id, "/start")

@router.message(F.text == "📊 تقرير")
@router.message(Command("report"))
async def report_command(message: Message):
    user_id = message.from_user.id
    if user_id != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ هذه الخاصية للمطور فقط.")
        return
    
    rep = get_report()
    reply = f"📊 تقرير 24 ساعة يا سيدي:\n"
    reply += f"🔨 حظر: {rep.get('ban', 0)}\n"
    reply += f"⚠️ مخالفات: {rep.get('warn', 0)}\n"
    reply += f"👥 مستخدمين نشطين: {len(set([r[0] for r in c.execute('SELECT user_id FROM memory').fetchall()]))}"
    
    await message.answer(reply)
    
    # إرسال الصوت
    audio_file = generate_T11_voice(reply)
    if audio_file:
        await bot.send_voice(message.chat.id, voice=FSInputFile(audio_file))
        os.remove(audio_file)

@router.message(F.text == "🎤 تحدث معي")
@router.message(Command("voice"))
async def voice_command(message: Message):
    user_id = message.from_user.id
    await message.answer("🎤 أرسل النص الذي تريد سماعه بصوت T11:")

@router.message(F.text == "❓ مساعدة")
@router.message(Command("help"))
async def help_command(message: Message):
    help_text = """
🤖 *بروتوكول T11 - المساعدة*

*الأوامر المتاحة:*
• /start - تفعيل البوت
• /report - عرض التقرير (للمطور)
• /voice - تحويل النص إلى صوت
• /say النص - يقول النص بصوت T11
• /send id النص - يرسل رسالة لمستخدم (للمطور)
• /ban id - حظر مستخدم (للمطور)
• /unban id - فك حظر مستخدم (للمطور)

*الأزرار:*
• 📊 تقرير - عرض الإحصائيات
• 🎤 تحدث معي - تحويل النص إلى صوت
• ❓ مساعدة - عرض هذه الرسالة

*نظام الاحترام:*
• كل تفاعل يزيد الاحترام +2
• الألفاظ غير اللائقة تخفض -30
• الطلبات السخيفة تخفض -15
• عند وصول الاحترام لـ 0 يتم الحظر
"""
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("ban"))
async def ban_command(message: Message):
    user_id = message.from_user.id
    if user_id != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ هذه الخاصية للمطور فقط.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ استخدم: /ban [معرف المستخدم]")
        return
    
    target = int(parts[1])
    ban_user(target)
    await message.answer(f"✅ تم حظر المستخدم {target}")
    add_report("ban")

@router.message(Command("unban"))
async def unban_command(message: Message):
    user_id = message.from_user.id
    if user_id != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ هذه الخاصية للمطور فقط.")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ استخدم: /unban [معرف المستخدم]")
        return
    
    target = int(parts[1])
    # حذف سجل الحظر
    c.execute("DELETE FROM memory WHERE user_id=? AND message='BANNED'", (target,))
    conn.commit()
    await message.answer(f"✅ تم فك حظر المستخدم {target}")

@router.message(Command("say"))
async def say_command(message: Message):
    user_id = message.from_user.id
    if user_id != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ هذه الخاصية للمطور فقط.")
        return
    
    text = message.text.replace("/say ", "")
    if not text:
        await message.answer("⚠️ أدخل النص: /say النص")
        return
    
    audio_file = generate_T11_voice(text)
    if audio_file:
        await bot.send_voice(message.chat.id, voice=FSInputFile(audio_file), caption=text)
        os.remove(audio_file)
    else:
        await message.answer("❌ فشل توليد الصوت")

@router.message(Command("send"))
async def send_command(message: Message):
    user_id = message.from_user.id
    if user_id != DEVELOPER_ID and user_id not in ADMIN_IDS:
        await message.answer("⛔ هذه الخاصية للمطور فقط.")
        return
    
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        await message.answer("⚠️ استخدم: /send [معرف المستخدم] [النص]")
        return
    
    target = int(parts[1])
    msg_text = parts[2]
    
    try:
        await bot.send_message(target, f"📨 [T11]: {msg_text}")
        await message.answer(f"✅ تم إرسال الرسالة إلى {target}")
    except Exception as e:
        await message.answer(f"❌ فشل الإرسال: {str(e)[:100]}")

# ===================== معالج النصوص العامة =====================
@router.message(F.text)
async def router_T11(message: Message):
    user_id = message.from_user.id
    text = message.text
    
    save_message(user_id, text)
    
    # تحديث عدد الرسائل
    user_msg_count[user_id] = user_msg_count.get(user_id, 0) + 1
    
    # التحقق من المطور
    if user_id == DEVELOPER_ID or user_id in ADMIN_IDS:
        await handle_T11_Dev(message)
        return
    
    # التحقق من المستخدمين العاديين
    if user_mode.get(user_id) == "assistant":
        await handle_T11_Public(message)
    else:
        await message.answer("اكتب /start للبدء", reply_markup=build_menu())

# ===================== معالج المطور =====================
async def handle_T11_Dev(message: Message):
    user_id = message.from_user.id
    text = message.text
    
    # أوامر خاصة
    if text.startswith("/"):
        return  # تم التعامل معها في الأوامر
    
    # دردشة فلسفية مع المطور
    history = "\n".join(get_history(user_id))
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            system_instruction=T11_DEV + f"\nسجل المحادثة: {history}",
            temperature=0.5
        )
        response = llm.invoke(text)
        await message.answer(response.content)
        
        # إرسال الصوت
        audio_file = generate_T11_voice(response.content[:500])
        if audio_file:
            await bot.send_voice(message.chat.id, voice=FSInputFile(audio_file))
            os.remove(audio_file)
    except Exception as e:
        await message.answer(f"❌ خطأ: {str(e)[:100]}")

# ===================== معالج المستخدمين العاديين =====================
async def handle_T11_Public(message: Message):
    user_id = message.from_user.id
    text = message.text
    
    # التحقق من الحظر
    if is_banned(user_id):
        await message.answer("⛔ تم تقييدك. عد بعد ساعة.")
        return
    
    # التحقق من الكلمات
    status = check_message(text, get_respect(user_id))
    if status == "ban":
        ban_user(user_id)
        await message.answer("⛔ تم تقييدك بسبب الإساءة المتكررة.")
        return
    if status == "warn":
        new_respect = update_respect(user_id, -30)
        await message.answer(f"⚠️ أسلوب مرفوض. تم خصم 30.\nالاحترام الحالي: {new_respect}")
        return
    if status == "dumb":
        new_respect = update_respect(user_id, -15)
        await message.answer(f"🤖 طلبك خارج نطاقي. تم خصم 15.\nالاحترام الحالي: {new_respect}")
        return
    
    # زيادة الاحترام
    update_respect(user_id, 2)
    
    # الحالة المزاجية
    mood = get_mood(last_seen(user_id), user_msg_count.get(user_id, 0))
    if mood:
        await message.answer(mood)
        return
    
    # الرد باستخدام Gemini
    history = "\n".join(get_history(user_id))
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            system_instruction=T11_PUBLIC + f"\nذاكرة المستخدم: {history}",
            temperature=0.9
        )
        response = llm.invoke(text)
        await message.answer(response.content)
    except Exception as e:
        await message.answer(f"❌ خطأ: {str(e)[:100]}")

# ===================== معالج الكول باك =====================
@router.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    
    if data == "report":
        if user_id != DEVELOPER_ID and user_id not in ADMIN_IDS:
            await callback.answer("⛔ هذه الخاصية للمطور فقط.")
            return
        rep = get_report()
        reply = f"📊 تقرير 24 ساعة:\nحظر: {rep.get('ban', 0)}\nمخالفات: {rep.get('warn', 0)}"
        await callback.message.answer(reply)
        audio_file = generate_T11_voice(reply)
        if audio_file:
            await bot.send_voice(callback.message.chat.id, voice=FSInputFile(audio_file))
            os.remove(audio_file)
        await callback.answer()
    
    elif data == "voice":
        await callback.message.answer("🎤 أرسل النص الذي تريد سماعه بصوت T11:")
        await callback.answer()
    
    elif data == "about":
        about_text = """
🤖 *عن T11*

T11 هو كيان آلي متطور، صُمم ليكون مساعداً ذكياً وغامضاً.
• تم تطويره بواسطة المطور T99
• يستخدم تقنيات الذكاء الاصطناعي المتقدمة
• يتميز بشخصية فريدة ونظام احترام
• يدعم الأوامر الصوتية والنصية

*الإصدار:* 2.0
*البروتوكول:* T11
"""
        await callback.message.answer(about_text, parse_mode="Markdown")
        await callback.answer()
    
    elif data == "help":
        help_text = """
🤖 *بروتوكول T11 - المساعدة*

*الأوامر المتاحة:*
• /start - تفعيل البوت
• /report - عرض التقرير (للمطور)
• /voice - تحويل النص إلى صوت
• /say النص - يقول النص بصوت T11

*نظام الاحترام:*
• كل تفاعل يزيد الاحترام +2
• الألفاظ غير اللائقة تخفض -30
• الطلبات السخيفة تخفض -15
"""
        await callback.message.answer(help_text, parse_mode="Markdown")
        await callback.answer()

# ===================== تشغيل البوت =====================
async def main():
    dp.include_router(router)
    print("🚀 T11 Online - جاهز للخدمة")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
