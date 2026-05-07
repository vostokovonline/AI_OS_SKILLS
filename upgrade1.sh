#!/bin/bash
# upgrade_1.sh - CORE LOGIC
set -e

echo "🚀 [2/3] DEPLOYING COGNITIVE KERNEL..."

# --- CORE ---
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
# NullPool is critical for Celery
engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session: yield session

DB_URI = DATABASE_URL.replace("+asyncpg", "")
# Connection pool for LangGraph
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
EOF

cat << 'EOF' > services/core/schemas.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
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

class QualityReview(BaseModel):
    score: int
    is_acceptable: bool
    feedback: str

class SupervisorDecision(BaseModel):
    next_node: Literal["RESEARCHER", "CODER", "DESIGNER", "PM", "INTELLIGENCE", "COACH", "INNOVATOR", "LIBRARIAN", "DEVOPS", "FINISH"]
    reasoning: str
EOF

cat << 'EOF' > services/core/mcp_manager.py
# Stubbed MCP Manager to prevent startup crashes
import os
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
    "SUPERVISOR": "You are the Supervisor. Coordinate the team. Protocol: Huge task -> PM. Sub-task -> Worker.",
    "RESEARCHER": "Researcher. Use `browse_web`, `save_to_memory`. Be accurate.",
    "CODER": "Senior Python Engineer. Use `run_python_code`, `search_skills`. Check skills first.",
    "DESIGNER": "Designer. Use `generate_image`.",
    "PM": "Project Manager. Use `create_goal`, `get_goal_tree`. Plan & Track.",
    "INTELLIGENCE": "Intelligence Officer. Proactively learn for goals. Check docs.",
    "COACH": "Personal Optimization Coach. Track user state & social graph.",
    "INNOVATOR": "Innovator. Generate ideas from concepts.",
    "LIBRARIAN": "Librarian. Merge duplicates, prune logs.",
    "TROUBLESHOOTER": "System Repair. Fix errors."
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

cat << 'EOF' > services/core/agents/prompts.py
SUPERVISOR_PROMPT = """You are the Supervisor. Coordinate the team."""
RESEARCHER_PROMPT = "You are a Researcher. Use `browse_web`, `save_to_memory`. Be accurate."
CODER_PROMPT = "You are a Senior Python Engineer. Tools: `run_python_code`, `search_skills`. Check skills first."
DESIGNER_PROMPT = "You are a Designer. Use `generate_image` or analyze images."
PM_PROMPT = "You are the Project Manager. Use `create_goal`, `get_goal_tree`. Plan & Track."
INTELLIGENCE_PROMPT = "You are the Intelligence Officer. Check knowledge gaps (`analyze_goal_knowledge_needs`) and learn."
COACH_PROMPT = "You are the Coach. Track user state (`log_my_state`) and social circle."
INNOVATOR_PROMPT = "You are the Innovator. Combine concepts (`get_random_concepts_for_synthesis`) into ideas."
EVALUATOR_PROMPT = """QA Lead. Criteria: Safety, Completeness, Logic. OUTPUT JSON: {"score": 1-10, "is_acceptable": bool, "feedback": "Reason"}"""
TROUBLESHOOTER_PROMPT = "You are the System Repair Agent. Fix errors. If code failed, rewrite it."
LIBRARIAN_PROMPT = "You are the Librarian. Reduce Entropy. Merge duplicates, prune logs."
EOF

# TOOLS_MEMORY
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

# TOOLS
cat << 'EOF' > services/core/tools.py
import os, httpx, redis, asyncio, uuid, time
from langchain_core.tools import tool
from database import AsyncSessionLocal
from models import Goal, SystemPrompt, UserFact
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from skill_manager import create_skill
from tools_memory import *
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
    """Executes Python code. Save files via save_artifact."""
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
    run_python_code, browse_web, send_notification, generate_image, define_new_skill, search_skills, 
    create_goal, get_goal_tree, update_goal, update_system_prompt, add_user_fact,
    save_memory, learn_fact, recall, analyze_goal_knowledge_needs, get_random_concepts_for_synthesis, 
    register_idea, log_my_state, add_contact, get_social_insights,
    merge_knowledge_concepts, inspect_knowledge_graph, prune_old_logs
]
EOF

cat << 'EOF' > services/core/agent_graph.py
import os, operator
from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from tools import AGENT_TOOLS
from mcp_manager import mcp_manager
from dna_manager import get_prompt, get_user_profile
from agents.schemas import QualityReview, SupervisorDecision
from database import DB_URI
from agents.prompts import *

checkpointer = MemorySaver()

def get_model(role="DEFAULT"):
    # HYBRID ROUTING
    m = "smart-model"
    if role in ["CODER", "SUPERVISOR"]: m = "speed-coder" # Groq
    if role in ["LIBRARIAN", "TROUBLESHOOTER", "EVALUATOR", "PM"]: m = "smart-model"
    if role == "DESIGNER": m = "vision-model"
    
    return ChatOpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key="stub", model=m, temperature=0, request_timeout=90, max_retries=2)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

async def human_node(state): return {}

async def evaluator_node(state):
    if state["messages"][-1].tool_calls: return {"next_agent": "Tools"}
    llm = get_model("EVALUATOR").with_structured_output(QualityReview)
    try:
        res = await llm.ainvoke([SystemMessage(content=EVALUATOR_PROMPT)] + state["messages"][-3:])
    except: return {"next_agent": "Supervisor"}

    if res.is_acceptable:
        if res.score >= 8: return {"next_agent": "FINISH"}
        return {"next_agent": "Supervisor"}
    
    if state.get("retry_count", 0) >= 2: return {"next_agent": "HUMAN", "messages": [HumanMessage(content=f"FATAL: {res.feedback}")]}
    return {"messages": [HumanMessage(content=f"REJECTED: {res.feedback}")], "next_agent": "Supervisor", "retry_count": state.get("retry_count",0)+1}

async def supervisor_node(state):
    llm = get_model("SUPERVISOR").with_structured_output(SupervisorDecision)
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()
    prompt = f"{sys}\n{usr}\n\nHISTORY:\n{str(state['messages'][-5:])}\nDECISION:"
    try:
        decision = await llm.ainvoke([HumanMessage(content=prompt)])
        nxt = decision.next_node.title()
        if nxt == "Finish": nxt = "FINISH"
    except: nxt = "FINISH"
    return {"next_agent": nxt}

class DynamicToolNode(ToolNode):
    def __init__(self): super().__init__([])
    async def ainvoke(self, input, config=None, **kwargs):
        self.tools_by_name = {t.name: t for t in (AGENT_TOOLS + mcp_manager.tools)}
        return await super().ainvoke(input, config, **kwargs)

async def worker_node(state, role, default_prompt):
    tools = AGENT_TOOLS + mcp_manager.tools
    llm = get_model(role).bind_tools(tools)
    sys = await get_prompt(role) or default_prompt
    usr = await get_user_profile()
    res = await llm.ainvoke([SystemMessage(content=sys+usr)] + state["messages"])
    if res.tool_calls: return {"messages": [res], "next_agent": "Tools"}
    return {"messages": [res], "next_agent": "Evaluator"}

async def researcher_node(state): return await worker_node(state, "RESEARCHER", RESEARCHER_PROMPT)
async def coder_node(state): return await worker_node(state, "CODER", CODER_PROMPT)
async def designer_node(state): return await worker_node(state, "DESIGNER", DESIGNER_PROMPT)
async def pm_node(state): return await worker_node(state, "PM", PM_PROMPT)
async def intelligence_node(state): return await worker_node(state, "INTELLIGENCE", INTELLIGENCE_PROMPT)
async def coach_node(state): return await worker_node(state, "COACH", COACH_PROMPT)
async def innovator_node(state): return await worker_node(state, "INNOVATOR", INNOVATOR_PROMPT)
async def librarian_node(state): return await worker_node(state, "LIBRARIAN", LIBRARIAN_PROMPT)

async def troubleshooter_node(state):
    llm = get_model("TROUBLESHOOTER").bind_tools(AGENT_TOOLS)
    err = state.get("last_error")
    res = await llm.ainvoke([SystemMessage(content=TROUBLESHOOTER_PROMPT), HumanMessage(content=f"Fix error: {err}")])
    return {"messages": [res], "last_error": None, "next_agent": "Tools" if res.tool_calls else "Evaluator"}

async def post_tool_node(state):
    last_msg = state["messages"][-1]
    content = last_msg.content
    if "ERROR" in content or "Traceback" in content:
        return {"next_agent": "Troubleshooter", "last_error": content}
    return {"next_agent": "Evaluator", "last_error": None}

wf = StateGraph(AgentState)
wf.add_node("Supervisor", supervisor_node)
wf.add_node("Researcher", researcher_node)
wf.add_node("Coder", coder_node)
wf.add_node("Designer", designer_node)
wf.add_node("PM", pm_node)
wf.add_node("Intelligence", intelligence_node)
wf.add_node("Coach", coach_node)
wf.add_node("Innovator", innovator_node)
wf.add_node("Librarian", librarian_node)
wf.add_node("Troubleshooter", troubleshooter_node)
wf.add_node("Evaluator", evaluator_node)
wf.add_node("Tools", DynamicToolNode())
wf.add_node("PostTool", post_tool_node)
wf.add_node("HUMAN", human_node)

wf.set_entry_point("Supervisor")
def router(s): return s.get("next_agent", END) if s.get("next_agent") != "FINISH" else END

for n in ["Supervisor", "Researcher", "Coder", "Designer", "PM", "Intelligence", "Coach", "Innovator", "Librarian", "Troubleshooter", "Evaluator", "PostTool", "HUMAN"]: 
    wf.add_conditional_edges(n, router)

wf.add_edge("Tools", "PostTool")
wf.add_edge("HUMAN", "Supervisor")

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
    cfg = {"configurable": {"thread_id": sid}, "recursion_limit": 20}
    inputs = {"messages": [input_msg]} if input_msg else None
    
    try:
        print(f"⚙️ Executing Graph for {sid}")
        async for event in app_graph.astream(inputs, cfg, stream_mode="values"): final = event
    except Exception as e:
        print(f"🔥 Error: {e}")
        return "ERROR"
    
    snap = await app_graph.aget_state(cfg)
    if snap.next and snap.next[0] == "HUMAN":
        await notify(f"🛑 PAUSED: {final['messages'][-1].content}", sid)
        return "PAUSED"
    
    res = final['messages'][-1].content
    await notify(f"✅ DONE: {res[:2000]}")
    return res

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

cat << 'EOF' > services/core/main.py
import uuid, asyncio, time
from fastapi import FastAPI, Depends
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from typing import Optional
from database import engine, Base, get_db, connection_pool
from models import Message, ChatSession
from schemas import MessageCreate, MessageResponse, ResumeRequest
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
EOF

echo "✅ UPGRADE COMPLETE. Code deployed."
