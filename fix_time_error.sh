#!/bin/bash
echo "⏰ FIXING DATETIME VALIDATION ERROR..."

# Переписываем main.py с правильным datetime
cat << 'EOF' > services/core/main.py
import uuid, asyncio, time
from datetime import datetime
from fastapi import FastAPI, Depends
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from database import engine, Base, get_db, connection_pool
from models import Message, ChatSession
from schemas import MessageCreate, MessageResponse, ResumeRequest, EventRequest
from tasks import run_chat_task, run_resume_task, run_cron_task
from scheduler import start_scheduler
from agent_graph import app_graph
from dna_manager import bootstrap_dna
from emotions import analyze_sentiment
from sqlalchemy import select

app = FastAPI()

async def wait_for_db():
    print("⏳ Connecting to Database...")
    while True:
        try:
            await connection_pool.open()
            async with connection_pool.connection() as conn: await conn.execute("SELECT 1")
            print("✅ Database Connected!")
            break
        except: await asyncio.sleep(2)

@app.on_event("startup")
async def startup():
    await wait_for_db()
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await bootstrap_dna()
    start_scheduler()
    print("🚀 SYSTEM ONLINE")

@app.on_event("shutdown")
async def shutdown(): await connection_pool.close()

@app.post("/chat", response_model=MessageResponse)
async def chat(req: MessageCreate, db=Depends(get_db)):
    sid = req.session_id or str(uuid.uuid4())
    res = await db.execute(select(ChatSession).where(ChatSession.id == sid))
    if not res.scalar_one_or_none():
        db.add(ChatSession(id=sid))
        await db.commit()
    db.add(Message(session_id=sid, role="user", content=req.content))
    await db.commit()
    run_chat_task.delay(sid, req.content, req.image_url)
    
    # FIX: Use datetime.utcnow() instead of uuid time
    return Message(session_id=sid, role="system", content="⏳ Processing...", created_at=datetime.utcnow())

@app.post("/resume")
async def resume(req: ResumeRequest):
    run_resume_task.delay(req.session_id)
    return {"status": "resumed"}

@app.post("/analyze_mood")
async def analyze_mood(req: dict):
    msgs = [HumanMessage(content=m) for m in req.get('history', [])]
    return await analyze_sentiment(msgs)

@app.post("/event")
async def handle_event(evt: EventRequest):
    sid = f"event_{evt.source}_{uuid.uuid4().hex[:6]}"
    run_cron_task.delay(sid, f"EVENT: {evt.source}\nDATA: {evt.payload}")
    return {"status": "processing"}
EOF

echo "🚀 Restarting Core..."
docker compose build core
docker compose up -d core

echo "✅ DONE. Core API should be stable now."
