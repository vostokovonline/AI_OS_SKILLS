#!/bin/bash
echo "📱 FIXING TELEGRAM ERROR HANDLING..."

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
aclient = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-stub"))

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

@dp.message(Command("start"))
async def s(m: types.Message): await m.answer("System Online.")

@dp.message(F.text)
async def h(m: types.Message):
    if m.from_user.id != OWNER: return
    async with httpx.AsyncClient(timeout=120) as c:
        sid = f"tg_{m.from_user.id}"
        await c.post(f"{CORE}/chat", json={"session_id": sid, "content": m.text})
        await m.answer("⏳ Accepted.")

@app.post("/ask_human")
async def ask(r: dict):
    # FIX: Robust ID parsing
    raw_id = str(r.get('chat_id', ''))
    if "tg_" in raw_id:
        tg_id = int(raw_id.replace("tg_", ""))
    else:
        # Fallback to owner if ID is weird
        tg_id = OWNER
        
    kb = InlineKeyboardBuilder()
    kb.button(text="Retry", callback_data=f"res:retry:{raw_id}")
    kb.button(text="Abort", callback_data=f"res:abort:{raw_id}")
    
    try:
        await bot.send_message(tg_id, r['text'], reply_markup=kb.as_markup(), parse_mode="Markdown")
    except Exception as e:
        print(f"Telegram Send Error: {e}")
        # Retry without markdown
        await bot.send_message(tg_id, r['text'], reply_markup=kb.as_markup())
    return "ok"

@dp.callback_query(lambda c: c.data.startswith("res:"))
async def cb(c: types.CallbackQuery):
    act, sid = c.data.split(":")[1], c.data.split(":")[2]
    await c.message.edit_text(f"Selected: {act}")
    async with httpx.AsyncClient() as client:
        await client.post(f"{CORE}/resume", json={"session_id": sid, "action": act})

@app.post("/notify")
async def n(r: dict):
    try:
        await bot.send_message(OWNER, r['message'])
    except Exception as e:
        print(f"Notify Error: {e}")
    return "ok"

@app.on_event("startup")
async def start(): asyncio.create_task(dp.start_polling(bot))
EOF

echo "✅ Telegram patched. Restarting..."
docker compose restart telegram
