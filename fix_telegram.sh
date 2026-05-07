#!/bin/bash
echo "📱 FIXING TELEGRAM BOT CRASH..."

# 1. Обновляем зависимости (фиксируем httpx чтобы не было конфликтов)
cat << 'EOF' > services/telegram/requirements.txt
fastapi
uvicorn
aiogram==3.1.1
httpx==0.27.0
python-dotenv
openai>=1.0.0
EOF

# 2. Обновляем код бота (Безопасная инициализация)
cat << 'EOF' > services/telegram/main.py
import os, httpx, asyncio, io
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI

TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER = int(os.getenv("TELEGRAM_OWNER_ID"))
CORE = os.getenv("CORE_URL")

# Safe OpenAI Init
api_key = os.getenv("OPENAI_API_KEY", "sk-stub")
if api_key == "sk-stub":
    aclient = None
else:
    aclient = AsyncOpenAI(api_key=api_key)

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

@dp.message(Command("start"))
async def s(m: types.Message): 
    if m.from_user.id != OWNER: return
    await m.answer("System Online.")

@dp.message(F.voice)
async def v(m: types.Message):
    if m.from_user.id != OWNER: return
    if not aclient:
        await m.answer("Voice disabled (No OpenAI Key)")
        return

    await bot.send_chat_action(m.chat.id, "typing")
    f = await bot.get_file(m.voice.file_id)
    buf = io.BytesIO()
    await bot.download_file(f.file_path, buf)
    buf.name = "v.ogg"
    
    try:
        txt = await aclient.audio.transcriptions.create(model="whisper-1", file=buf)
        await m.reply(f"🗣️ {txt.text}")
        async with httpx.AsyncClient(timeout=120) as c:
            await c.post(f"{CORE}/chat", json={"session_id":f"tg_{m.from_user.id}", "content":txt.text})
    except Exception as e: await m.answer(f"Error: {e}")

@dp.message(F.text)
async def h(m: types.Message):
    if m.from_user.id != OWNER: return
    # Show typing status
    await bot.send_chat_action(m.chat.id, "typing")
    
    async with httpx.AsyncClient(timeout=120) as c:
        sid = f"tg_{m.from_user.id}"
        try:
            await c.post(f"{CORE}/chat", json={"session_id": sid, "content": m.text})
            await m.answer("⏳ Accepted.")
        except Exception as e:
            await m.answer(f"Core Error: {e}")

@app.post("/ask_human")
async def ask(r: dict):
    tg_id = r['chat_id'].replace("tg_", "")
    kb = InlineKeyboardBuilder()
    kb.button(text="Retry", callback_data=f"res:retry:{r['chat_id']}")
    kb.button(text="Abort", callback_data=f"res:abort:{r['chat_id']}")
    await bot.send_message(int(tg_id), r['text'], reply_markup=kb.as_markup())
    return "ok"

@dp.callback_query(lambda c: c.data.startswith("res:"))
async def cb(c: types.CallbackQuery):
    act, sid = c.data.split(":")[1], c.data.split(":")[2]
    await c.message.edit_text(f"Selected: {act}")
    async with httpx.AsyncClient() as client:
        await client.post(f"{CORE}/resume", json={"session_id": sid, "action": act})

@app.post("/notify")
async def n(r: dict):
    await bot.send_message(OWNER, r['message'])
    return "ok"

@app.on_event("startup")
async def start(): asyncio.create_task(dp.start_polling(bot))
EOF

echo "🚀 Rebuilding Telegram..."
docker compose build telegram
docker compose up -d telegram

echo "✅ DONE. Check logs: docker logs -f ns_telegram"
