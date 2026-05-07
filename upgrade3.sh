#!/bin/bash
# upgrade_3_telegram.sh - COMMUNICATION INTERFACE
set -e

echo "📱 DEPLOYING TELEGRAM INTERFACE..."

# 1. REQUIREMENTS
cat << 'EOF' > services/telegram/requirements.txt
fastapi
uvicorn
aiogram==3.1.1
httpx
python-dotenv
openai
EOF

# 2. DOCKERFILE
cat << 'EOF' > services/telegram/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
EOF

# 3. LOGIC (BOT + GATEWAY)
cat << 'EOF' > services/telegram/main.py
import os, httpx, asyncio, io
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI

# Config
TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", 0))
CORE_URL = os.getenv("CORE_URL", "http://core:8000")

# Whisper Client (Optional, falls back if no key)
openai_key = os.getenv("OPENAI_API_KEY", "sk-stub")
aclient = AsyncOpenAI(api_key=openai_key)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# --- HANDLERS ---

@dp.message(Command("start"))
async def start_cmd(m: types.Message):
    if m.from_user.id != OWNER_ID: return
    await m.answer("🤖 **Technocratic OS Online.**\nReady for commands.")

@dp.message(F.voice)
async def handle_voice(m: types.Message):
    """Принимает голосовое, транскрибирует (Whisper) и отправляет в Core."""
    if m.from_user.id != OWNER_ID: return
    
    await bot.send_chat_action(m.chat.id, "typing")
    try:
        # 1. Скачиваем файл
        file_info = await bot.get_file(m.voice.file_id)
        voice_io = io.BytesIO()
        await bot.download_file(file_info.file_path, voice_io)
        voice_io.name = "voice.ogg"
        
        # 2. Транскрибация
        if "sk-" not in openai_key:
            await m.reply("⚠️ Voice disabled (OPENAI_API_KEY missing).")
            return

        transcription = await aclient.audio.transcriptions.create(
            model="whisper-1", 
            file=voice_io
        )
        text = transcription.text
        await m.reply(f"🗣️ *{text}*", parse_mode="Markdown")
        
        # 3. Отправка в Core
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(
                f"{CORE_URL}/chat", 
                json={"session_id": f"tg_{m.from_user.id}", "content": text}
            )
            
    except Exception as e:
        await m.answer(f"Voice Error: {e}")

@dp.message(F.text)
async def handle_text(m: types.Message):
    """Обычный текст."""
    if m.from_user.id != OWNER_ID: return
    
    # Показываем, что думаем
    await bot.send_chat_action(m.chat.id, "typing")
    
    async with httpx.AsyncClient(timeout=120) as client:
        try:
            sid = f"tg_{m.from_user.id}"
            await client.post(
                f"{CORE_URL}/chat", 
                json={"session_id": sid, "content": m.text}
            )
            # Мы не ждем ответа здесь, ответ придет асинхронно через notify
            await m.answer("⏳ Accepted.")
        except Exception as e:
            await m.answer(f"Core Connection Error: {e}")

# --- INTERNAL API (Для Core) ---

@app.post("/notify")
async def notify(r: dict):
    """Простое уведомление от системы."""
    try:
        await bot.send_message(OWNER_ID, r['message'], parse_mode="Markdown")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.post("/ask_human")
async def ask_human(r: dict):
    """Запрос с кнопками (Human-in-the-Loop)."""
    try:
        # r['chat_id'] это session_id (tg_12345)
        tg_id = r['chat_id'].replace("tg_", "")
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Retry", callback_data=f"res:retry:{r['chat_id']}")
        builder.button(text="🛑 Abort", callback_data=f"res:abort:{r['chat_id']}")
        # Можно добавить кнопку "Совет", но для MVP хватит двух
        
        await bot.send_message(
            int(tg_id), 
            r['text'], 
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@dp.callback_query(lambda c: c.data.startswith("res:"))
async def handle_callback(c: types.CallbackQuery):
    """Обработка нажатия кнопок."""
    action, session_id = c.data.split(":")[1], c.data.split(":")[2]
    
    await c.message.edit_text(f"✅ Selected: **{action.upper()}**")
    
    # Шлем решение обратно в Core
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{CORE_URL}/resume",
            json={"session_id": session_id, "action": action}
        )

# --- STARTUP ---

@app.on_event("startup")
async def on_startup():
    # Запускаем поллинг Телеграма в фоне
    asyncio.create_task(dp.start_polling(bot))
EOF

echo "✅ TELEGRAM INTERFACE INSTALLED."
echo "👉 Now run: docker compose up -d --build telegram"
