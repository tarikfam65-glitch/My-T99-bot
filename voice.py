import os
import asyncio
import edge_tts

VOICE_CODE = "ar-SA-HamedNeural"  # صوت رجالي سعودي عميق
# بدائل: ar-EG-OmarNeural (مصري), ar-SA-HamedNeural (سعودي)

def generate_T11_voice(text):
    """توليد صوت T11 الغامض باستخدام edge-tts"""
    try:
        os.makedirs('temp', exist_ok=True)
        filename = f"t11_voice_{int(time.time())}.mp3"
        filepath = os.path.join('temp', filename)
        
        async def generate():
            communicate = edge_tts.Communicate(text, VOICE_CODE)
            await communicate.save(filepath)
        
        asyncio.run(generate())
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath
        return None
    except Exception as e:
        print(f"Voice error: {e}")
        return None
