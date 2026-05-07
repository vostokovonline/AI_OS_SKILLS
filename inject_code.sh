#!/bin/bash
set -e

echo "🧠 INJECTING CODE INTO SERVICES..."

# ==========================================
# 1. CORE (The Brain)
# ==========================================
echo "📦 Core..."
cat << 'EOF' > services/core/requirements.txt
fastapi
uvicorn
sqlalchemy
asyncpg
httpx
pydantic
python-dotenv
langchain>=0.3.0
langchain-core>=0.3.0
langchain-community>=0.3.0
langgraph>=0.2.0
langgraph-checkpoint-postgres
psycopg[binary,pool]
langchain-openai
celery[redis]
psutil
apscheduler
gitpython
mcp
PyGithub
duckduckgo-search
EOF

cat << 'EOF' > services/core/Dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git curl gnupg build-essential libpq-dev nodejs npm \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat << 'EOF' > services/core/database.py
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from psycopg_pool import AsyncConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session: yield session

DB_URI = DATABASE_URL.replace("+asyncpg", "")
connection_pool = AsyncConnectionPool(conninfo=DB_URI, max_size=20, open=False, kwargs={"autocommit": True})
EOF

cat << 'EOF' > services/core/models.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import uuid
from database import Base

class ChatSession(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String)
    content = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Goal(Base):
    __tablename__ = "goals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("goals.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="active")
    progress = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    children = relationship("Goal", backref=backref('parent', remote_side=[id]))

class SystemPrompt(Base):
    __tablename__ = "system_prompts"
    key = Column(String, primary_key=True)
    content = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class UserFact(Base):
    __tablename__ = "user_facts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category = Column(String)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RunLog(Base):
    __tablename__ = "run_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String)
    agent_role = Column(String)
    tool_used = Column(String)
    input_summary = Column(Text)
    output_summary = Column(Text)
    status = Column(String)
    duration_ms = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ToolStats(Base):
    __tablename__ = "tool_stats"
    tool_name = Column(String, primary_key=True)
    calls_count = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    avg_duration_ms = Column(Float, default=0.0)
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class Thought(Base):
    __tablename__ = "thoughts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text)
    source = Column(String)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
EOF

cat << 'EOF' > services/core/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict
from datetime import datetime

class MessageCreate(BaseModel):
    session_id: Optional[str] = None
    content: str
    image_url: Optional[str] = None

class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: datetime
    class Config: from_attributes = True

class ResumeRequest(BaseModel):
    session_id: str
    action: str
    feedback: Optional[str] = None

class EventRequest(BaseModel):
    source: str
    payload: object

class QualityReview(BaseModel):
    score: int
    is_acceptable: bool
    feedback: str

class SupervisorDecision(BaseModel):
    next_node: Literal["RESEARCHER", "CODER", "DESIGNER", "PM", "INTELLIGENCE", "COACH", "INNOVATOR", "LIBRARIAN", "DEVOPS", "FINISH"]
    reasoning: str

class Step(BaseModel):
    id: int
    description: str
    assigned_role: Literal["CODER", "RESEARCHER", "DESIGNER", "PM", "SKILL"]
    skill_name: Optional[str] = None
    status: str = "pending"

class Plan(BaseModel):
    steps: List[Step]
    final_goal: str
    reasoning: str

class Budget(BaseModel):
    total_steps: int = 15
    steps_used: int = 0
    allow_human_interaction: bool = True

class MetaEvaluation(BaseModel):
    process_score: int
    waste_detected: bool
    better_path_suggestion: str
EOF

cat << 'EOF' > services/core/resource_manager.py
import psutil
class SystemMonitor:
    def __init__(self, cpu_limit=90, ram_min_mb=500):
        self.cpu_limit = cpu_limit
        self.ram_min_mb = ram_min_mb
    def check_health(self):
        cpu = psutil.cpu_percent(interval=0.5)
        if cpu > self.cpu_limit: return False
        mem = psutil.virtual_memory()
        if (mem.available / 1024 / 1024) < self.ram_min_mb: return False
        return True
EOF

cat << 'EOF' > services/core/skill_manager.py
import os, json, subprocess, httpx
SKILLS_DIR = "/app/skills"
REGISTRY_FILE = os.path.join(SKILLS_DIR, "registry.json")
MEMORY_URL = os.getenv("MEMORY_URL", "http://memory:8001")

if not os.path.exists(REGISTRY_FILE):
    with open(REGISTRY_FILE, "w") as f: json.dump({}, f)
if not os.path.exists(os.path.join(SKILLS_DIR, ".git")):
    try:
        subprocess.run(["git", "init"], cwd=SKILLS_DIR)
        subprocess.run(["git", "config", "user.email", "ai@os"], cwd=SKILLS_DIR)
        subprocess.run(["git", "config", "user.name", "AI"], cwd=SKILLS_DIR)
    except: pass

def load_registry():
    try:
        with open(REGISTRY_FILE, "r") as f: return json.load(f)
    except: return {}

def save_registry(data):
    with open(REGISTRY_FILE, "w") as f: json.dump(data, f, indent=2)

async def create_skill(name, code, description, example):
    safe_name = "".join(x for x in name if x.isalnum() or x == "_")
    filename = f"{safe_name}.py"
    filepath = os.path.join(SKILLS_DIR, filename)
    with open(filepath, "w") as f: f.write(code)
    registry = load_registry()
    registry[safe_name] = {"description": description, "example": example}
    save_registry(registry)
    try:
        subprocess.run(["git", "add", "."], cwd=SKILLS_DIR)
        subprocess.run(["git", "commit", "-m", f"Add {safe_name}"], cwd=SKILLS_DIR)
    except: pass
    async with httpx.AsyncClient() as client:
        try:
            text = f"Skill: {safe_name}\nDescription: {description}\nUsage: {example}"
            await client.post(f"{MEMORY_URL}/remember", json={"text": text, "metadata": {"source": "skill", "name": safe_name}})
        except: pass
    return f"Skill {safe_name} created."
EOF

cat << 'EOF' > services/core/telemetry.py
import time
from database import AsyncSessionLocal
from models import RunLog, ToolStats
from sqlalchemy import select

async def log_action(session_id, agent, tool, input_data, output_data, status, start_time):
    duration = (time.time() - start_time) * 1000
    try:
        async with AsyncSessionLocal() as db:
            log = RunLog(session_id=str(session_id), agent_role=agent, tool_used=tool, input_summary=str(input_data)[:500], output_summary=str(output_data)[:500], status=status, duration_ms=duration)
            db.add(log)
            res = await db.execute(select(ToolStats).where(ToolStats.tool_name == tool))
            stats = res.scalar_one_or_none()
            if not stats:
                stats = ToolStats(tool_name=tool, calls_count=0, errors_count=0, avg_duration_ms=0.0)
                db.add(stats)
            tot = (stats.avg_duration_ms * stats.calls_count) + duration
            stats.calls_count += 1
            stats.avg_duration_ms = tot / stats.calls_count
            if status != "success": 
                stats.errors_count += 1
                stats.last_error = str(output_data)[:200]
            await db.commit()
    except Exception as e: print(f"Telemetry Error: {e}")
EOF

cat << 'EOF' > services/core/mcp_manager.py
# Stubbed MCP Manager to prevent startup crashes
import os, asyncio
class MCPClientManager:
    def __init__(self): self.tools = []
    async def connect(self): print("🐙 MCP: Connecting (Mock)...")
    async def cleanup(self): pass
mcp_manager = MCPClientManager()
EOF

cat << 'EOF' > services/core/dna_manager.py
from database import AsyncSessionLocal
from models import SystemPrompt, UserFact
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

DEFAULTS = {
    "SUPERVISOR": "You are the Supervisor. Coordinate the team: PM, RESEARCHER, INTELLIGENCE, CODER, DESIGNER, COACH, INNOVATOR. Protocol: Huge task -> PM. Sub-task -> Worker.",
    "RESEARCHER": "Researcher. Use `browse_web`, `save_to_memory`. Be accurate.",
    "CODER": "Senior Python Engineer. Use `run_python_code`, `search_skills`. Check skills first.",
    "DESIGNER": "Designer. Use `generate_image`.",
    "PM": "Project Manager. Use `create_goal`, `get_goal_tree`. Plan & Track.",
    "INTELLIGENCE": "Intelligence Officer. Proactively learn for goals. Check docs.",
    "COACH": "Personal Optimization Coach. Track user state & social graph.",
    "INNOVATOR": "Innovator. Generate ideas from concepts.",
    "LIBRARIAN": "Librarian. Merge duplicates, prune logs.",
    "DEVOPS": "DevOps. Use `github_action`."
}

async def bootstrap_dna():
    async with AsyncSessionLocal() as db:
        for key, text in DEFAULTS.items():
            stmt = insert(SystemPrompt).values(key=key, content=text).on_conflict_do_nothing()
            await db.execute(stmt)
        await db.commit()

async def get_prompt(key: str):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(SystemPrompt).where(SystemPrompt.key == key))
        prompt = res.scalar_one_or_none()
        return prompt.content if prompt else DEFAULTS.get(key, "")

async def get_user_profile():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(UserFact))
        facts = res.scalars().all()
        return "\nUSER CONTEXT:\n" + "\n".join([f"- [{f.category}] {f.content}" for f in facts]) if facts else ""
EOF

cat << 'EOF' > services/core/emotions.py
from pydantic import BaseModel
from langchain_core.messages import SystemMessage
import os
from langchain_openai import ChatOpenAI

class EmotionalState(BaseModel):
    user_mood: str
    bot_mood: str
    color_hex: str

async def analyze_sentiment(messages):
    try:
        llm = ChatOpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key="stub", model="vision-model", temperature=0.5).with_structured_output(EmotionalState)
        res = await llm.ainvoke([SystemMessage(content="Analyze mood. JSON.")] + messages[-3:])
        return res
    except: return EmotionalState(user_mood="neutral", bot_mood="professional", color_hex="#00FFFF")
EOF

cat << 'EOF' > services/core/tools_memory.py
import httpx, os
from langchain_core.tools import tool
from database import AsyncSessionLocal
from models import Goal
from sqlalchemy import select

MEMORY_URL = os.getenv("MEMORY_URL", "http://memory:8001")

@tool
async def save_memory(text: str, category: str = "general"):
    """Saves episodic memory."""
    async with httpx.AsyncClient() as client:
        await client.post(f"{MEMORY_URL}/remember", json={"text": text, "type": "episodic", "metadata": {"category": category}})
    return "Saved."

@tool
async def learn_fact(subject: str, predicate: str, object_name: str):
    """Saves semantic fact to Graph."""
    async with httpx.AsyncClient() as client:
        await client.post(f"{MEMORY_URL}/add_fact", json={"subject": subject, "predicate": predicate, "object": object_name})
    return "Fact learned."

@tool
async def recall(query: str, type: str = "episodic"):
    """Searches memory (episodic or semantic)."""
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{MEMORY_URL}/search", json={"text": query, "type": type})
        matches = res.json().get("matches", [])
        graph_info = []
        if type == "semantic":
            entity = query.split()[-1] 
            g_res = await client.post(f"{MEMORY_URL}/search_graph", params={"entity": entity})
            graph_info = g_res.json().get("relations", [])
        out = f"MEMORY ({type}):\n" + "\n".join(matches)
        if graph_info: out += "\nGRAPH:\n" + "\n".join(graph_info)
        return out

@tool
async def analyze_goal_knowledge_needs():
    """Analyzes active goals for knowledge gaps."""
    async with AsyncSessionLocal() as db:
        stmt = select(Goal).where(Goal.status == "active")
        goals = (await db.execute(stmt)).scalars().all()
    if not goals: return "No active goals."
    txt = "\n".join([f"- {g.title}: {g.description}" for g in goals])
    return f"ACTIVE GOALS:\n{txt}\nINSTRUCTION: Find missing technical knowledge."

@tool
async def get_random_concepts_for_synthesis():
    """Retrieves random concepts from memory."""
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{MEMORY_URL}/concepts/random")
        return str(res.json().get("concepts", []))

@tool
async def register_idea(title: str, description: str):
    """Registers a new idea."""
    async with AsyncSessionLocal() as db:
        new_goal = Goal(title=f"💡 {title}", description=description, status="idea")
        db.add(new_goal)
        await db.commit()
    return f"Idea '{title}' registered."

@tool
async def log_my_state(energy: int, mood: str, focus: int, notes: str = ""):
    """Logs the user's current state."""
    async with httpx.AsyncClient() as client:
        await client.post(f"{MEMORY_URL}/user/state", json={"energy": energy, "mood": mood, "focus": focus, "notes": notes})
    return "State logged."

@tool
async def add_contact(name: str, relation: str, interests: str):
    """Adds a person to social graph."""
    async with httpx.AsyncClient() as client:
        await client.post(f"{MEMORY_URL}/user/social", params={"name": name, "relation": relation}, json=interests.split(","))
    return "Contact added."

@tool
async def get_social_insights():
    """Returns social analysis."""
    async with httpx.AsyncClient() as client:
        return str((await client.get(f"{MEMORY_URL}/user/analysis")).json())

@tool
async def merge_knowledge_concepts(keep_concept: str, remove_concept: str):
    """Merges duplicate concepts."""
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{MEMORY_URL}/graph/merge", json={"primary": keep_concept, "alias": remove_concept})
        return str(res.json())

@tool
async def inspect_knowledge_graph():
    """Returns a list of entities to check for duplicates."""
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{MEMORY_URL}/graph/inspect")
        return str(res.json())

@tool
async def prune_old_logs(days: int = 7):
    """Deletes system logs older than N days."""
    from sqlalchemy import text
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"DELETE FROM run_logs WHERE created_at < NOW() - INTERVAL '{days} days'"))
        await db.commit()
    return "Logs pruned."
EOF

cat << 'EOF' > services/core/tools_external.py
import os
from langchain_core.tools import tool
from github import Github
from duckduckgo_search import DDGS

@tool
def github_action(action: str, repo_name: str, path: str = "", content: str = "", branch: str = "main"):
    """Interact with GitHub."""
    token = os.getenv("GITHUB_TOKEN")
    if not token or token == "change_me": return "Error: GITHUB_TOKEN not set"
    try:
        g = Github(token)
        repo = g.get_user().get_repo(repo_name)
        if action == "read": return repo.get_contents(path, ref=branch).decoded_content.decode("utf-8")
        elif action == "create_file":
            try:
                repo.update_file(path, "Update", content, repo.get_contents(path).sha, branch=branch)
                return "Updated"
            except:
                repo.create_file(path, "Create", content, branch=branch)
                return "Created"
        elif action == "create_issue": return f"Issue: {repo.create_issue(title=path, body=content).html_url}"
        return "Unknown action"
    except Exception as e: return f"GitHub Error: {e}"

@tool
def fast_search(query: str):
    """Quick text search (DuckDuckGo)."""
    try:
        return str(DDGS().text(query, max_results=5))
    except Exception as e: return f"Search Error: {e}"
EOF

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

async def logged_exec(tool_name, func_coro, *args, **kwargs):
    start = time.time()
    status = "success"
    try:
        res = await func_coro
        if "ERROR" in str(res): status = "error"
        return res
    except Exception as e:
        status = "crash"
        raise e
    finally:
        sid = kwargs.get("session_id", "unknown")
        await log_action(sid, "UNKNOWN", tool_name, str(kwargs), "logs", status, start)

@tool
async def run_python_code(code: str, session_id: str = "default"):
    """Executes Python code."""
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
    """Visits a website."""
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
    """Chat with Web LLMs."""
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
    merge_knowledge_concepts, inspect_knowledge_graph, prune_old_logs,
    github_action, fast_search
]
EOF

cat << 'EOF' > services/core/agents/prompts.py
SUPERVISOR_PROMPT = """You are the Supervisor. Coordinate the team."""
RESEARCHER_PROMPT = "You are a Researcher. Use fast_search first, then browse_web."
CODER_PROMPT = "You are a Senior Python Engineer. Tools: run_python_code, search_skills. Check skills first."
DESIGNER_PROMPT = "You are a Designer. Use generate_image or analyze images."
PM_PROMPT = "You are the Project Manager. Use create_goal, get_goal_tree. Plan & Track."
INTELLIGENCE_PROMPT = "You are the Intelligence Officer. Check knowledge gaps (analyze_goal_knowledge_needs) and learn."
COACH_PROMPT = "You are the Coach. Track user state (log_my_state) and social circle."
INNOVATOR_PROMPT = "You are the Innovator. Combine concepts (get_random_concepts_for_synthesis) into ideas."
LIBRARIAN_PROMPT = "You are the Librarian. Reduce Entropy. Merge duplicates, prune logs."
DEVOPS_PROMPT = "You are the DevOps Engineer. Manage Code via github_action."
EVALUATOR_PROMPT = """QA Lead. Criteria: Safety, Completeness, Logic. OUTPUT JSON: {"score": 1-10, "is_acceptable": bool, "feedback": "Reason"}"""
TROUBLESHOOTER_PROMPT = "You are the System Repair Agent. Fix errors. If code failed, rewrite it."
PLANNER_PROMPT = "You are the Architect. Create a step-by-step plan. OUTPUT JSON."
EOF

cat << 'EOF' > services/core/agents/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, List, Optional, Dict

class QualityReview(BaseModel):
    score: int
    is_acceptable: bool
    feedback: str

class SupervisorDecision(BaseModel):
    next_node: Literal["RESEARCHER", "CODER", "DESIGNER", "PM", "INTELLIGENCE", "COACH", "INNOVATOR", "LIBRARIAN", "DEVOPS", "FINISH"]
    reasoning: str

class Step(BaseModel):
    id: int
    description: str
    assigned_role: Literal["CODER", "RESEARCHER", "DESIGNER", "PM", "SKILL"]
    skill_name: Optional[str] = None
    status: str = "pending"

class Plan(BaseModel):
    steps: List[Step]
    final_goal: str
    reasoning: str

class Budget(BaseModel):
    total_steps: int = 15
    steps_used: int = 0
    allow_human_interaction: bool = True

class MetaEvaluation(BaseModel):
    process_score: int
    waste_detected: bool
    better_path_suggestion: str
EOF

cat << 'EOF' > services/core/agent_graph.py
import os, operator
from typing import Annotated, List, TypedDict, Dict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from tools import AGENT_TOOLS
from mcp_manager import mcp_manager
from dna_manager import get_prompt, get_user_profile
from agents.schemas import Plan, Step, Budget, MetaEvaluation, QualityReview
from database import DB_URI
from agents.prompts import *

checkpointer = MemorySaver()

def get_model(role="DEFAULT"):
    # HYBRID ROUTING (Groq / Gemini)
    # Thinkers = Smart / Slow
    if role in ["PLANNER", "EVALUATOR", "META_EVAL", "SUPERVISOR", "LIBRARIAN", "TROUBLESHOOTER", "PM", "INTELLIGENCE"]:
        return ChatOpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key="stub", model="smart-model", temperature=0.1, request_timeout=120)
    # Actors = Fast / Tools
    return ChatOpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key="stub", model="speed-coder", temperature=0, request_timeout=90)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    plan: Plan
    current_step: int
    budget: Budget
    next_node: str
    retry_count: int
    last_error: str

async def planner_node(state):
    llm = get_model("PLANNER").with_structured_output(Plan)
    sys = await get_prompt("PLANNER") or PLANNER_PROMPT
    try:
        plan = await llm.ainvoke([SystemMessage(content=sys)] + state["messages"])
    except:
        return {"next_node": "ACTOR", "plan": None}

    budget = Budget(total_steps=len(plan.steps) * 3)
    return {
        "plan": plan, 
        "current_step": 0, 
        "budget": budget,
        "next_node": "EXECUTOR",
        "messages": [HumanMessage(content=f"🧠 PLAN GENERATED: {len(plan.steps)} steps.")]
    }

async def executor_node(state):
    plan = state.get("plan")
    if not plan: return {"next_node": "ACTOR"}

    idx = state.get("current_step", 0)
    budget = state.get("budget", Budget())
    
    # Check Budget
    if budget.steps_used >= budget.total_steps:
        return {"next_node": "META_EVAL", "messages": [HumanMessage(content="BUDGET EXHAUSTED.")]}
    
    # Check Finish
    if idx >= len(plan.steps):
        return {"next_node": "META_EVAL"}
        
    step = plan.steps[idx]
    
    if state.get("last_error"):
        return {"next_node": "TROUBLESHOOTER"}

    role_map = {
        "CODER": "Coder", "RESEARCHER": "Researcher", "DESIGNER": "Designer", 
        "PM": "PM", "LIBRARIAN": "Librarian", "DEVOPS": "DevOps", "SKILL": "TOOLS"
    }
    target = role_map.get(step.assigned_role, "Coder")
    
    budget.steps_used += 1
    return {"next_node": target, "budget": budget}

async def worker_wrapper(state, role):
    llm = get_model(role).bind_tools(AGENT_TOOLS + mcp_manager.tools)
    sys = await get_prompt(role) or f"You are {role}."
    
    plan = state.get("plan")
    ctx = ""
    if plan and state.get("current_step", 0) < len(plan.steps):
        ctx = f"\nFOCUS: {plan.steps[state.get('current_step', 0)].description}"
    
    res = await llm.ainvoke([SystemMessage(content=sys + ctx)] + state["messages"])
    
    if res.tool_calls:
        return {"messages": [res], "next_node": "TOOLS"}
    
    return {
        "messages": [res], 
        "current_step": state.get("current_step", 0) + 1,
        "next_node": "EXECUTOR"
    }

# Nodes
async def coder_node(state): return await worker_wrapper(state, "CODER")
async def researcher_node(state): return await worker_wrapper(state, "RESEARCHER")
async def designer_node(state): return await worker_wrapper(state, "DESIGNER")
async def pm_node(state): return await worker_wrapper(state, "PM")
async def actor_node(state): return await worker_wrapper(state, "ACTOR")
async def librarian_node(state): return await worker_wrapper(state, "LIBRARIAN")
async def devops_node(state): return await worker_wrapper(state, "DEVOPS")
async def intelligence_node(state): return await worker_wrapper(state, "INTELLIGENCE")
async def coach_node(state): return await worker_wrapper(state, "COACH")
async def innovator_node(state): return await worker_wrapper(state, "INNOVATOR")

async def troubleshooter_node(state):
    llm = get_model("TROUBLESHOOTER").bind_tools(AGENT_TOOLS)
    err = state.get("last_error")
    res = await llm.ainvoke([SystemMessage(content=TROUBLESHOOTER_PROMPT), HumanMessage(content=f"Fix error: {err}")])
    return {"messages": [res], "last_error": None, "next_node": "TOOLS" if res.tool_calls else "EXECUTOR"}

async def meta_evaluator_node(state):
    return {"next_node": END}

class DynamicToolNode(ToolNode):
    def __init__(self): super().__init__([])
    async def ainvoke(self, input, config=None, **kwargs):
        self.tools_by_name = {t.name: t for t in (AGENT_TOOLS + mcp_manager.tools)}
        return await super().ainvoke(input, config, **kwargs)

async def post_tool_node(state):
    last_msg = state["messages"][-1]
    content = last_msg.content
    
    # Detect failure
    if "ERROR" in content or "Traceback" in content:
        return {"next_node": "EXECUTOR", "last_error": content}
    
    # Success -> Next Step
    return {"next_node": "EXECUTOR", "last_error": None, "current_step": state.get("current_step", 0) + 1}

async def human_node(state): return {}

# GRAPH
wf = StateGraph(AgentState)
wf.add_node("Planner", planner_node)
wf.add_node("Executor", executor_node)
wf.add_node("MetaEval", meta_evaluator_node)
wf.add_node("Coder", coder_node)
wf.add_node("Researcher", researcher_node)
wf.add_node("Designer", designer_node)
wf.add_node("PM", pm_node)
wf.add_node("Intelligence", intelligence_node)
wf.add_node("Coach", coach_node)
wf.add_node("Innovator", innovator_node)
wf.add_node("Librarian", librarian_node)
wf.add_node("DevOps", devops_node)
wf.add_node("ACTOR", actor_node)
wf.add_node("Troubleshooter", troubleshooter_node)
wf.add_node("TOOLS", DynamicToolNode())
wf.add_node("PostTool", post_tool_node)
wf.add_node("HUMAN", human_node)

wf.set_entry_point("Planner")
def router(s):
    n = s.get("next_node", END)
    if n == "FINISH": return END
    return n

nodes = ["Planner", "Executor", "MetaEval", "Coder", "Researcher", "Designer", "PM", "Intelligence", "Coach", "Innovator", "Librarian", "DevOps", "ACTOR", "Troubleshooter", "PostTool", "HUMAN"]
for n in nodes: wf.add_conditional_edges(n, router)

wf.add_edge("TOOLS", "PostTool")
app_graph = wf.compile(checkpointer=checkpointer, interrupt_before=["HUMAN"])
EOF

cat << 'EOF' > services/core/tasks.py
import os, asyncio, httpx, traceback
from celery import Celery
from langchain_core.messages import HumanMessage
from resource_manager import SystemMonitor
from agent_graph import app_graph
import redis

monitor = SystemMonitor()
celery_app = Celery("ns", broker=os.getenv("CELERY_BROKER_URL"))
# Unified Queue
celery_app.conf.task_routes = {'tasks.*': {'queue': 'default'}}

async def notify(msg, sid=None):
    try: 
        if sid and "tg_" in sid: await httpx.post(f"{os.getenv('TELEGRAM_URL')}/ask_human", json={"chat_id": sid, "text": msg})
        else: await httpx.post(f"{os.getenv('TELEGRAM_URL')}/notify", json={"message": msg})
    except: pass

async def _exec(sid, input_msg=None):
    cfg = {"configurable": {"thread_id": sid}, "recursion_limit": 30}
    inputs = {"messages": [input_msg]} if input_msg else None
    
    try:
        print(f"⚙️ Executing Graph for {sid}")
        async for event in app_graph.astream(inputs, cfg, stream_mode="values"): final = event
        res = final['messages'][-1].content
        await notify(f"✅ DONE: {res[:2000]}")
        return res
    except Exception as e:
        print(f"🔥 Error: {e}")
        await notify(f"🔥 SYSTEM ERROR: {e}")
        return "ERROR"
    
    snap = await app_graph.aget_state(cfg)
    if snap.next and snap.next[0] == "HUMAN":
        await notify(f"🛑 PAUSED: {final['messages'][-1].content}", sid)
        return "PAUSED"

@celery_app.task(bind=True)
def run_chat_task(self, session_id, content, image_url=None):
    if not monitor.check_health(): return "BUSY"
    msg = HumanMessage(content=[{"type":"text","text":content},{"type":"image_url","image_url":image_url}]) if image_url else HumanMessage(content=content)
    return asyncio.run(_exec(session_id, msg))

@celery_app.task(bind=True)
def run_resume_task(self, session_id):
    return asyncio.run(_exec(session_id, None))

@celery_app.task(bind=True)
def run_cron_task(self, session_id, content):
    return asyncio.run(_exec(session_id, HumanMessage(content=content)))
EOF

cat << 'EOF' > services/core/scheduler.py
import uuid
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from tasks import run_cron_task
from resource_manager import SystemMonitor
from cognition.drive import generate_internal_drive

scheduler = AsyncIOScheduler()
monitor = SystemMonitor()

async def cognitive_heartbeat():
    thought = await generate_internal_drive()
    if "No active goals" not in thought:
        print(f"💓 Heartbeat: {thought}")
        run_cron_task.delay(f"internal_{uuid.uuid4()}", thought)

def start_scheduler():
    # Cognitive Loop every 10 mins
    scheduler.add_job(cognitive_heartbeat, 'interval', minutes=10)
    scheduler.start()
EOF

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

@app.on_event("startup")
async def startup():
    while True:
        try:
            await connection_pool.open()
            async with connection_pool.connection() as conn: await conn.execute("SELECT 1")
            break
        except: await asyncio.sleep(2)
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

# ------------------------------------------
# SERVICE: OPENCODE
# ------------------------------------------
echo "🐍 Building Opencode..."
cat << 'EOF' > services/opencode/requirements.txt
fastapi
uvicorn
jupyter_client
ipykernel
pandas
numpy
matplotlib
requests
scikit-learn
boto3
python-dotenv
EOF

cat << 'EOF' > services/opencode/Dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential libffi-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
RUN python -m ipykernel install --user --name=python3
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
EOF

cat << 'EOF' > services/opencode/preload.py
import os, boto3, uuid
try:
    s3 = boto3.client('s3', endpoint_url=os.getenv('MINIO_ENDPOINT'), aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'), aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'))
    s3.create_bucket(Bucket="workspace")
except: pass
def save_artifact(path):
    try:
        name = f"{uuid.uuid4().hex[:8]}_{path}"
        s3.upload_file(path, "workspace", name)
        return f"Saved: {name}"
    except Exception as e: return str(e)
EOF

cat << 'EOF' > services/opencode/main.py
import uuid
from fastapi import FastAPI
from pydantic import BaseModel
from jupyter_client import MultiKernelManager
from preload import save_artifact

app = FastAPI()
km = MultiKernelManager(default_kernel_name='python3')
sessions = {}

class Req(BaseModel):
    session_id: str
    code: str

@app.post("/run")
async def run(r: Req):
    if r.session_id not in sessions:
        sessions[r.session_id] = km.start_kernel()
        cl = km.get_kernel(sessions[r.session_id]).client()
        cl.start_channels()
        try:
            with open("preload.py", "r") as f: cl.execute(f.read())
        except: pass
    
    cl = km.get_kernel(sessions[r.session_id]).client()
    mid = cl.execute(r.code)
    outs = []
    MAX_CHARS = 100000
    while True:
        try:
            msg = cl.get_iopub_msg(timeout=10)
            if msg['parent_header'].get('msg_id') != mid: continue
            mt = msg['msg_type']
            if mt == 'stream': outs.append(msg['content']['text'])
            elif mt == 'execute_result': outs.append(str(msg['content']['data'].get('text/plain', '')))
            elif mt == 'error': return {"status":"error", "stderr": str(msg['content'])}
            elif mt == 'status' and msg['content']['execution_state'] == 'idle': break
            if len("".join(outs)) > MAX_CHARS: outs.append("\n[TRUNCATED]"); break
        except: break
    return {"status":"success", "stdout": "".join(outs)}
EOF

# ------------------------------------------
# SERVICE: WEBSURFER
# ------------------------------------------
echo "🌐 Building WebSurfer..."
cat << 'EOF' > services/websurfer/requirements.txt
fastapi
uvicorn
playwright
html2text
boto3
python-dotenv
beautifulsoup4
playwright-stealth
EOF

cat << 'EOF' > services/websurfer/Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
RUN playwright install chromium
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
EOF

cat << 'EOF' > services/websurfer/main.py
import os, boto3, uuid, html2text, asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

app = FastAPI()
s3 = boto3.client('s3', endpoint_url=os.getenv('MINIO_ENDPOINT'), aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'), aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'))
USER_DATA_DIR = "/app/browser_data"

class ChatReq(BaseModel):
    provider: str
    prompt: str

class VisitReq(BaseModel):
    url: str

@app.post("/chat_web")
async def chat_web(r: ChatReq):
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(user_data_dir=USER_DATA_DIR, headless=True, args=["--disable-blink-features=AutomationControlled"], viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        await stealth_async(page)
        res_text = "Error"
        try:
            if r.provider == "chatgpt":
                await page.goto("https://chatgpt.com", timeout=60000)
                if await page.query_selector("button[data-testid='login-button']"): return {"status": "error", "detail": "Not logged in."}
                box = await page.wait_for_selector("#prompt-textarea")
                await box.fill(r.prompt)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)
                await page.wait_for_timeout(10000)
                msgs = await page.query_selector_all(".markdown")
                if msgs: res_text = await msgs[-1].inner_text()
            await context.close()
            return {"status": "success", "content": res_text}
        except Exception as e:
            await context.close()
            return {"status": "error", "detail": str(e)}

@app.post("/visit")
async def visit(r: VisitReq):
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        try:
            await pg.goto(r.url, timeout=30000)
            txt = html2text.HTML2Text().handle(await pg.content())
            return {"status":"success", "title":await pg.title(), "content":txt[:5000]}
        except Exception as e: return {"status":"error", "detail":str(e)}
        finally: await b.close()
EOF

# ------------------------------------------
# SERVICE: MEMORY
# ------------------------------------------
echo "🧠 Building Memory..."
cat << 'EOF' > services/memory/requirements.txt
fastapi
uvicorn
pymilvus==2.3.2
torch --index-url https://download.pytorch.org/whl/cpu
sentence-transformers
neo4j
pydantic
python-dotenv
EOF

cat << 'EOF' > services/memory/Dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
EOF

cat << 'EOF' > services/memory/graph.py
import os
from neo4j import GraphDatabase
class KnowledgeGraph:
    def __init__(self):
        try: self.d = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))
        except: pass
    def add_fact(self, s, p, o):
        if hasattr(self, 'd'):
            with self.d.session() as ssn: ssn.run("MERGE (a:Entity {name:$s}) MERGE (b:Entity {name:$o}) MERGE (a)-[:REL {type:$p}]->(b)", s=s, p=p, o=o)
    def update_user_state(self, e, m, f, n):
        if hasattr(self, 'd'):
            with self.d.session() as ssn: ssn.run("MATCH (u:User) CREATE (u)-[:FELT]->(:State {e:$e,m:$m,f:$f,n:$n})", e=e, m=m, f=f, n=n)
    def add_social(self, n, r, i):
        if hasattr(self, 'd'):
            with self.d.session() as ssn: ssn.run("MATCH (u:User) MERGE (p:Person {name:$n}) MERGE (u)-[:KNOWS {rel:$r}]->(p)", n=n, r=r)
    def get_user_patterns(self): return []
    def search_related(self, e): return []
    def get_random_concepts(self, l): return []
    def merge_nodes(self, p, a): return "Merged"
    def get_potential_duplicates(self): return []
EOF

cat << 'EOF' > services/memory/main.py
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from graph import KnowledgeGraph
import os, time

app = FastAPI()
model = None
cols = {}
kg = None

@app.on_event("startup")
async def start():
    global model, kg
    model = SentenceTransformer('all-MiniLM-L6-v2')
    for i in range(10):
        try: connections.connect("default", host="milvus", port="19530"); break
        except: time.sleep(2)
    
    for n in ["episodic", "semantic"]:
        if not utility.has_collection(n):
            f = [FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True), FieldSchema("vector", DataType.FLOAT_VECTOR, dim=384), FieldSchema("content", DataType.VARCHAR, max_length=60000), FieldSchema("meta", DataType.VARCHAR, max_length=2000)]
            c = Collection(n, CollectionSchema(f))
            c.create_index("vector", {"metric_type":"L2", "index_type":"IVF_FLAT", "params":{"nlist":128}})
            c.load()
        cols[n] = Collection(n); cols[n].load()
    try: kg = KnowledgeGraph()
    except: pass

@app.post("/remember")
async def rem(item: dict):
    emb = model.encode(item['text']).tolist()
    c = cols.get(item.get('type', 'episodic'), cols['episodic'])
    c.insert([[emb], [item['text']], [str(item.get('metadata', {}))]])
    return "ok"

@app.post("/add_fact")
async def add_fact(r: dict):
    kg.add_fact(r['subject'], r['predicate'], r['object'])
    return "ok"

@app.post("/search")
async def search(q: dict):
    emb = model.encode(q['text']).tolist()
    c = cols.get(q.get('type', 'episodic'), cols['episodic'])
    res = c.search([emb], "vector", {"metric_type":"L2"}, limit=3, output_fields=["content"])
    return {"matches": [h.entity.get("content") for h in res[0]]}

@app.post("/user/state")
async def log_st(r: dict): kg.update_user_state(r['energy'], r['mood'], r['focus'], r['notes']); return "ok"
@app.post("/user/social")
async def add_soc(r: dict): kg.add_social(r['name'], r['relation'], r['interests']); return "ok"
@app.get("/user/analysis")
async def ana(): return {"patterns": kg.get_user_patterns()}
@app.post("/graph/merge")
async def merge(r: dict): return kg.merge_nodes(r['primary'], r['alias'])
@app.get("/graph/inspect")
async def inspect(): return {"nodes": kg.get_potential_duplicates()}
EOF

# ------------------------------------------
# SERVICE: GOVERNOR
# ------------------------------------------
echo "👮 Building Governor..."
cat << 'EOF' > services/governor/requirements.txt
docker
psutil
redis
httpx
python-dotenv
rich
EOF

cat << 'EOF' > services/governor/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["python", "main.py"]
EOF

cat << 'EOF' > services/governor/main.py
import time, os, docker, psutil, redis, httpx
from datetime import datetime

DOCKER_CLIENT = docker.from_env()
REDIS_CLIENT = redis.from_url(os.getenv("CELERY_BROKER_URL"))
TELEGRAM_URL = os.getenv("TELEGRAM_URL")
CPU_THRESHOLD = int(os.getenv("CPU_THRESHOLD", 90))
RAM_THRESHOLD = int(os.getenv("RAM_THRESHOLD", 90))

SERVICES = {
    "ns_core": f"{os.getenv('CORE_URL')}/docs",
    "ns_minio": "http://minio:9000/minio/health/live"
}

def log(msg, level="INFO"): print(f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {msg}")

def notify(msg):
    try: httpx.post(f"{TELEGRAM_URL}/notify", json={"message": f"🏥 **System Doctor:**\n{msg}"}, timeout=5)
    except: log("Failed to notify", "WARN")

def check_env_health():
    if "change_me" in os.getenv("GEMINI_KEY_1", ""): log("❌ Invalid GEMINI_KEY", "ERROR")

def heal_container(name):
    try:
        DOCKER_CLIENT.containers.get(name).restart()
        notify(f"Service **{name}** was unhealthy. Restarted.")
    except: log(f"Failed to heal {name}", "ERROR")

def manage_resources():
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    if mem > RAM_THRESHOLD: REDIS_CLIENT.set("STATUS_CRITICAL", "1", ex=60)
    else: REDIS_CLIENT.delete("STATUS_CRITICAL")
    if cpu > CPU_THRESHOLD: REDIS_CLIENT.set("STATUS_HEAVY_LOAD", "1", ex=30)
    else: REDIS_CLIENT.delete("STATUS_HEAVY_LOAD")

if __name__ == "__main__":
    log("System Doctor Started.")
    check_env_health()
    time.sleep(20)
    while True:
        manage_resources()
        for name, url in SERVICES.items():
            try:
                if httpx.get(url, timeout=5).status_code >= 500: heal_container(name)
            except: pass
        time.sleep(30)
EOF

# ------------------------------------------
# SERVICE: TELEGRAM
# ------------------------------------------
echo "📱 Building Telegram..."
cat << 'EOF' > services/telegram/requirements.txt
fastapi
uvicorn
aiogram==3.1.1
httpx
python-dotenv
openai
EOF

cat << 'EOF' > services/telegram/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
EOF

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
async def s(m: types.Message): 
    if m.from_user.id != OWNER: return
    await m.answer("System Online.")

@dp.message(F.voice)
async def v(m: types.Message):
    if m.from_user.id != OWNER: return
    f = await bot.get_file(m.voice.file_id)
    buf = io.BytesIO()
    await bot.download_file(f.file_path, buf)
    buf.name = "v.ogg"
    try:
        txt = await aclient.audio.transcriptions.create(model="whisper-1", file=buf)
        await m.reply(f"🗣️ {txt.text}")
        async with httpx.AsyncClient(timeout=120) as c:
            await c.post(f"{CORE}/chat", json={"session_id":f"tg_{m.from_user.id}", "content":txt.text})
    except Exception as e: await m.answer(str(e))

@dp.message(F.text)
async def h(m: types.Message):
    if m.from_user.id != OWNER: return
    async with httpx.AsyncClient(timeout=120) as c:
        sid = f"tg_{m.from_user.id}"
        await c.post(f"{CORE}/chat", json={"session_id": sid, "content": m.text})
        await m.answer("⏳ Accepted.")

@app.post("/ask_human")
async def ask(r: dict):
    tg_id = r['chat_id'].replace("tg_", "")
    kb = InlineKeyboardBuilder()
    kb.button(text="Retry", callback_data=f"res:retry:{r['chat_id']}")
    kb.button(text="Abort", callback_data=f"res:abort:{r['chat_id']}")
    await bot.send_message(int(tg_id), r['text'], reply_markup=kb.as_markup(), parse_mode="Markdown")
    return "ok"

@dp.callback_query(lambda c: c.data.startswith("res:"))
async def cb(c: types.CallbackQuery):
    act, sid = c.data.split(":")[1], c.data.split(":")[2]
    await c.message.edit_text(f"Selected: {act}")
    async with httpx.AsyncClient() as client:
        await client.post(f"{CORE}/resume", json={"session_id": sid, "action": act})

@app.post("/notify")
async def n(r: dict):
    try: await bot.send_message(OWNER, r['message'])
    except: pass
    return "ok"

@app.on_event("startup")
async def start(): asyncio.create_task(dp.start_polling(bot))
EOF

# ------------------------------------------
# SERVICE: DASHBOARD
# ------------------------------------------
echo "🖥 Building Dashboard..."
cat << 'EOF' > services/dashboard/requirements.txt
streamlit
pandas
neo4j
redis
boto3
plotly
streamlit-agraph
streamlit-ace
python-dotenv
sqlalchemy
psycopg2-binary
requests
EOF

cat << 'EOF' > services/dashboard/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
EOF

cat << 'EOF' > services/dashboard/app.py
import streamlit as st
import pandas as pd
import redis, boto3, os, requests
from sqlalchemy import create_engine, text
from streamlit_ace import st_ace

st.set_page_config(layout="wide", page_title="Technocratic OS", page_icon="🧠")

if 'auth' not in st.session_state: st.session_state.auth = False
def check_pw():
    if st.session_state.auth: return True
    if st.text_input("Password", type="password") == "admin":
        st.session_state.auth = True
        st.rerun()
    return False
if not check_pw(): st.stop()

# Safe Connections
try: 
    DB = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:5432/{os.getenv('POSTGRES_DB')}"
    pg = create_engine(DB)
except: pg = None
try: r = redis.from_url(os.getenv("CELERY_BROKER_URL"))
except: r = None
try: s3 = boto3.client('s3', endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT')}", aws_access_key_id=os.getenv('MINIO_ACCESS_KEY'), aws_secret_access_key=os.getenv('MINIO_SECRET_KEY'))
except: s3 = None

t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Analytics", "📜 Logs", "🎯 Strategy", "🧬 DNA", "🚦 Status", "📂 Files"])

with t1:
    st.header("Reliability")
    if st.button("Refresh Stats"): st.rerun()
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM tool_stats ORDER BY calls_count DESC", pg)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else: st.info("No stats yet.")
        except: st.warning("Stats DB not ready.")

with t2:
    st.header("Logs")
    if st.button("Refresh Logs"): st.rerun()
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM run_logs ORDER BY created_at DESC LIMIT 20", pg)
            if not df.empty:
                for i, row in df.iterrows():
                    with st.expander(f"{row['created_at']} - {row['agent_role']} ({row['status']})"):
                        st.code(row['output_summary'])
        except: st.warning("No logs yet")

with t3:
    st.header("Projects")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM goals", pg)
            if not df.empty:
                roots = df[df['parent_id'].isnull()]
                for i, root in roots.iterrows():
                    with st.expander(f"{root['title']} ({root['progress']*100:.0f}%)"):
                        st.write(root['description'])
                        if st.button("Execute", key=f"x_{root['id']}"):
                            requests.post("http://core:8000/chat", json={"session_id":"admin","content":f"Execute {root['title']}"})
        except: pass

with t4:
    st.header("DNA")
    if pg:
        try:
            df = pd.read_sql("SELECT * FROM system_prompts", pg)
            if not df.empty:
                role = st.selectbox("Role", df['key'])
                val = df[df['key']==role]['content'].values
                st.text_area("Prompt", val[0] if len(val)>0 else "", height=300)
        except: pass

with t5:
    if r:
        try:
            raw = r.get("SYSTEM_PAUSED")
            paused = raw.decode('utf-8')=="1" if raw else False
            st.metric("Paused", "YES" if paused else "NO")
            if st.button("Toggle Pause"):
                if paused: r.delete("SYSTEM_PAUSED")
                else: r.set("SYSTEM_PAUSED", "1")
        except: st.error("Redis Error")

with t6:
    if s3:
        try:
            b = s3.list_buckets().get('Buckets', [])
            if b:
                bn = st.selectbox("Bucket", [x['Name'] for x in b])
                o = s3.list_objects_v2(Bucket=bn).get('Contents', [])
                if o: st.dataframe(pd.DataFrame([{"Key":x['Key'], "Size":x['Size']} for x in o]))
        except: pass
EOF

# ------------------------------------------
# SERVICE: AVATAR
# ------------------------------------------
echo "🗣 Building Avatar..."
cat << 'EOF' > services/avatar/requirements.txt
fastapi
uvicorn
python-dotenv
edge-tts
httpx
jinja2
python-multipart
EOF

cat << 'EOF' > services/avatar/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"]
EOF

cat << 'EOF' > services/avatar/main.py
import os, httpx, edge_tts, base64
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()
CORE = os.getenv("CORE_URL")

@app.get("/")
async def get():
    return HTMLResponse("""
<!DOCTYPE html><html><body style="background:#000;color:#0f0;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column">
<div id="orb" style="width:200px;height:200px;border-radius:50%;background:radial-gradient(circle,#0ff,#000);box-shadow:0 0 50px #0ff"></div>
<button onclick="start()" style="margin-top:20px;padding:10px">Voice</button>
<script>
    let ws = new WebSocket("ws://"+location.host+"/ws");
    ws.onmessage = (e) => {
        let d = JSON.parse(e.data);
        if(d.type=="audio"){
            let a = new Audio("data:audio/mp3;base64,"+d.payload);
            a.play();
        }
    };
    function start() {
        let r = new webkitSpeechRecognition();
        r.onresult = (e) => ws.send(JSON.stringify({type:"text", payload:e.results[0][0].transcript}));
        r.start();
    }
</script></body></html>
""")

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        d = await websocket.receive_json()
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{CORE}/chat", json={"session_id":"voice", "content":d['payload']})
            txt = r.json().get("content", "Error")
            try:
                await c.post(f"{CORE}/analyze_mood", json={"history":[d['payload']]})
            except: pass
            comm = edge_tts.Communicate(txt, "en-US-ChristopherNeural")
            audio = b""
            async for chunk in comm.stream():
                if chunk["type"] == "audio": audio += chunk["data"]
            await websocket.send_json({"type":"audio", "payload": base64.b64encode(audio).decode('utf-8')})
EOF

# ------------------------------------------
# SERVICE: WEBHOOK
# ------------------------------------------
echo "🔌 Building Webhook..."
cat << 'EOF' > services/webhook/requirements.txt
fastapi
uvicorn
redis
httpx
python-dotenv
EOF

cat << 'EOF' > services/webhook/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8007"]
EOF

cat << 'EOF' > services/webhook/main.py
import os, httpx
from fastapi import FastAPI, Request, BackgroundTasks
app = FastAPI()
CORE = os.getenv("CORE_URL")
@app.post("/trigger/{source}")
async def trig(source: str, request: Request, bt: BackgroundTasks):
    try: body = await request.json()
    except: body = (await request.body()).decode()
    bt.add_task(fwd, source, body)
    return {"status": "accepted"}
async def fwd(src, data):
    async with httpx.AsyncClient() as c:
        try: await c.post(f"{CORE}/event", json={"source": src, "payload": data})
        except: pass
EOF

# ------------------------------------------
# SERVICE: WALLET
# ------------------------------------------
echo "💰 Building Wallet..."
mkdir -p services/wallet
cat << 'EOF' > services/wallet/requirements.txt
fastapi
uvicorn
pydantic
EOF
cat << 'EOF' > services/wallet/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
EOF
cat << 'EOF' > services/wallet/main.py
import os
from fastapi import FastAPI
from pydantic import BaseModel
app = FastAPI()
DATA_FILE = "/app/data/balance.txt"
os.makedirs("/app/data", exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f: f.write("100.00")
class Transaction(BaseModel):
    to_address: str
    amount: float
@app.get("/balance")
async def get_balance():
    with open(DATA_FILE, "r") as f: bal = float(f.read().strip())
    return {"balance": bal, "currency": "USDT", "address": "0xAI_WALLET_V1"}
@app.post("/send")
async def send(tx: Transaction):
    with open(DATA_FILE, "r") as f: bal = float(f.read().strip())
    if bal < tx.amount: return {"status": "failed", "reason": "Insufficient funds"}
    new_bal = bal - tx.amount
    with open(DATA_FILE, "w") as f: f.write(str(new_bal))
    return {"status": "success", "new_balance": new_bal, "tx": "0xFAKE_HASH"}
EOF

echo "✅ DONE! Technocratic AI OS v4.0 (PLATINUM) Installed."
echo "👉 1. Edit .env (Add GROQ_API_KEY, GEMINI_KEYS & Telegram Token)"
echo "👉 2. Run: docker-compose up --build -d"
echo "👉 3. Dashboard: http://localhost:8501 (pass: admin)"
