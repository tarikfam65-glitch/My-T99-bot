FROM python:3.10-slim

WORKDIR /app

# تثبيت FFmpeg (ضروري لتحويل النص إلى صوت وتحميل الفيديو)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تشغيل البوت
CMD ["python", "bot.py"]
