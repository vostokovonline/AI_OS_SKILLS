#!/bin/bash
echo "🚑 APPLYING EMERGENCY FIXES FOR v4.0..."

# 1. FIX MEMORY SERVICE (Torch Installation)
# Проблема: pip внутри Docker иногда не может прочитать --index-url из файла
echo "🧠 Fixing Memory Service..."
cat << 'EOF' > services/memory/requirements.txt
fastapi
uvicorn
pymilvus==2.3.2
sentence-transformers
neo4j
pydantic
python-dotenv
EOF

cat << 'EOF' > services/memory/Dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
# Install CPU Torch explicitly first
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
# Run a check
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
EOF

# 2. FIX CORE TOOLS (Missing Docstrings)
echo "🛠 Fixing Core Tools Docstrings..."
cat << 'EOF' > services/core/tools.py
import os, httpx, redis, asyncio, uuid, time
from langchain_core.tools import tool
from database import AsyncSessionLocal
from models import Goal, SystemPrompt, UserFact
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from skill_manager import create_skill
from tools_memory import *
from tools_external import github_action, fast_search
from telemetry import log_action

redis_client = redis.from_url(os.getenv("CELERY_BROKER_URL"))
LIMITS = {"compute": 3, "browser": 2}
OPENCODE_URL = os.getenv("OPENCODE_URL")
WEBSURFER_URL = os.getenv("WEBSURFER_URL")
TELEGRAM_URL = os.getenv("TELEGRAM_URL")

async def acquire_lock(rtype, timeout=60):
    if redis_client.get("STATUS_CRITICAL"): return False, "Low RAM"
    if rtype == "compute" and redis_client.get("STATUS_HEAVY_LOAD"): return False, "High CPU"
    key = f"semaphore:{rtype}"
    limit = LIMITS.get(rtype, 1)
    start = asyncio.get_event_loop().time()
    while True:
        if redis_client.incr(key) <= limit:
            redis_client.expire(key, 300)
            return True, ""
        redis_client.decr(key)
        if asyncio.get_event_loop().time() - start > timeout: return False, "Timeout"
        await asyncio.sleep(1)

async def release_lock(rtype):
    redis_client.decr(f"semaphore:{rtype}")

@tool
async def run_python_code(code: str, session_id: str = "default"):
    """
    Executes Python code in a persistent Jupyter environment.
    Use this for calculations, data analysis, or file manipulation.
    """
    allowed, msg = await acquire_lock("compute")
    if not allowed: return f"System Busy: {msg}"
    start = time.time()
    status = "success"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(f"{OPENCODE_URL}/run", json={"session_id": session_id, "code": code}, timeout=60)
            data = res.json()
            out = f"STDOUT:\n{data.get('stdout')}" if data["status"] == "success" else f"ERROR:\n{data.get('stderr')}"
            if data["status"] != "success": status = "error"
            return out
    except Exception as e: 
        status = "crash"
        return str(e)
    finally:
        await release_lock("compute")
        await log_action(session_id, "CODER", "run_python", code, "", status, start)

@tool
async def browse_web(url: str):
    """Visits a website and extracts content."""
    allowed, msg = await acquire_lock("browser")
    if not allowed: return f"System Busy: {msg}"
    start = time.time()
    status = "success"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(f"{WEBSURFER_URL}/visit", json={"url": url}, timeout=60)
            data = res.json()
            out = f"Title: {data['title']}\nContent:\n{data['content'][:4000]}" if data["status"] == "success" else f"Error: {data.get('detail')}"
            if data["status"] != "success": status = "error"
            return out
    except Exception as e:
        status = "crash"
        return str(e)
    finally:
        await release_lock("browser")
        await log_action("unknown", "RESEARCHER", "browse_web", url, "", status, start)

@tool
async def ask_web_llm(provider: str, prompt: str):
    """Chat with Web LLMs (ChatGPT). Provider: 'chatgpt'."""
    allowed, msg = await acquire_lock("browser")
    if not allowed: return f"System Busy: {msg}"
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(f"{WEBSURFER_URL}/chat_web", json={"provider": provider, "prompt": prompt})
            d = res.json()
            if d["status"]=="success": return f"WEB-LLM RESPONSE:\n{d['content']}"
            return f"WEB ERROR: {d.get('detail')}"
    except Exception as e: return str(e)
    finally: await release_lock("browser")

@tool
async def send_notification(message: str):
    """Sends a notification to Telegram."""
    async with httpx.AsyncClient() as client:
        try: await client.post(f"{TELEGRAM_URL}/notify", json={"message": message})
        except: pass
    return "Sent."

@tool
async def generate_image(prompt: str):
    """Generates an image via AI."""
    safe = prompt.replace(" ", "%20")
    return f"Image: https://image.pollinations.ai/prompt/{safe}"

@tool
async def define_new_skill(name: str, python_code: str, description: str, usage_example: str):
    """Creates a new tool."""
    return await create_skill(name, python_code, description, usage_example)

@tool
async def search_skills(query: str):
    """Searches existing skills."""
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{os.getenv('MEMORY_URL')}/search", json={"text": query, "top_k": 3})
        found = [m['text'] for m in res.json().get('matches', []) if "Skill:" in m['text']]
        return "Found:\n" + "\n".join(found) if found else "No skills found."

@tool
async def create_goal(title: str, description: str = "", parent_id: str = None):
    """Creates a new goal."""
    async with AsyncSessionLocal() as db:
        pid = uuid.UUID(parent_id) if parent_id else None
        g = Goal(title=title, description=description, parent_id=pid)
        db.add(g)
        await db.commit()
        return f"Goal {g.title} created (ID: {g.id})"

@tool
async def get_goal_tree(root_id: str = None):
    """Gets the goal hierarchy."""
    async with AsyncSessionLocal() as db:
        stmt = select(Goal).where(Goal.parent_id == None).where(Goal.status != "completed")
        goals = (await db.execute(stmt)).scalars().all()
        if not goals: return "No active goals."
        out = "STRATEGY TREE:\n"
        for g in goals: out += f"- {g.title} ({g.status}, ID: {g.id})\n"
        return out

@tool
async def update_goal(goal_id: str, status: str, progress: float):
    """Updates goal status."""
    async with AsyncSessionLocal() as db:
        stmt = select(Goal).where(Goal.id == uuid.UUID(goal_id))
        g = (await db.execute(stmt)).scalar_one_or_none()
        if g:
            g.status = status
            g.progress = progress
            await db.commit()
            return "Updated."
        return "Not found."

@tool
async def update_system_prompt(agent_role: str, new_prompt: str):
    """Updates system DNA."""
    async with AsyncSessionLocal() as db:
        stmt = insert(SystemPrompt).values(key=agent_role.upper(), content=new_prompt).on_conflict_do_update(index_elements=['key'], set_=dict(content=new_prompt))
        await db.execute(stmt)
        await db.commit()
    return f"DNA Updated for {agent_role}."

@tool
async def add_user_fact(category: str, content: str):
    """Saves user fact."""
    async with AsyncSessionLocal() as db:
        db.add(UserFact(category=category, content=content))
        await db.commit()
    return "User Profile Updated."

AGENT_TOOLS = [
    run_python_code, browse_web, ask_web_llm, send_notification, generate_image, define_new_skill, search_skills, 
    create_goal, get_goal_tree, update_goal, update_system_prompt, add_user_fact,
    save_memory, learn_fact, recall, analyze_goal_knowledge_needs, get_random_concepts_for_synthesis, 
    register_idea, log_my_state, add_contact, get_social_insights,
    github_action, fast_search
]
EOF

# 3. DISABLE MCP & FIX MAIN (Stabilize)
echo "🛡 Stabilizing Core..."
cat << 'EOF' > services/core/main.py
import uuid, asyncio, time
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
        except Exception as e:
            print(f"⚠️ DB Wait: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup():
    await wait_for_db()
    async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
    await bootstrap_dna()
    # await mcp_manager.connect() # DISABLED FOR STABILITY
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
    return Message(session_id=sid, role="system", content="⏳ Processing...", created_at=uuid.uuid1().time)

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

echo "🚀 REBUILDING CRASHED SERVICES..."
# Сначала пересобираем, потом поднимаем
docker compose build core core_worker memory telegram websurfer avatar
docker compose up -d

echo "✅ FIX COMPLETE. Waiting for stabilization..."
sleep 10
bash test.sh
