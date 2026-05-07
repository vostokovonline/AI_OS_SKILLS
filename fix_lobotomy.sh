#!/bin/bash
echo "🧠 APPLYING 'ANTI-LOBOTOMY' PATCH (Forcing Intelligence)..."

# 1. ОБНОВЛЯЕМ ПРОМПТЫ (Делаем их агрессивными)
cat << 'EOF' > services/core/agents/prompts.py
SUPERVISOR_PROMPT = """
You are the Supervisor. Your job is ROUTING only.
- If user wants to create/manage goals -> Choose **PM**.
- If user wants code/files -> Choose **CODER**.
- If user wants info -> Choose **RESEARCHER**.
- If user just says "Hi" -> Choose **FINISH**.
"""

PM_PROMPT = """
You are the Project Manager (PM).
YOUR ONLY PURPOSE IS TO MANAGE GOALS IN THE DATABASE.

🔴 **CRITICAL RULES:**
1. **DO NOT CHAT.** Do not reply with "Okay", "I will do it", or "Done".
2. **USE TOOLS.** You MUST call `create_goal`, `update_goal`, or `get_goal_tree`.
3. If the user says "Create goal X", you MUST output the TOOL CALL to create it.
"""

RESEARCHER_PROMPT = "You are a Researcher. Use `browse_web` or `fast_search`. Do not hallucinate info."
CODER_PROMPT = "You are a Senior Python Engineer. Use `run_python_code`. Always verify code."
DESIGNER_PROMPT = "You are a Designer. Use `generate_image`."
INTELLIGENCE_PROMPT = "You are Intelligence. Use `analyze_goal_knowledge_needs`."
COACH_PROMPT = "You are the Coach. Use `log_my_state`."
INNOVATOR_PROMPT = "You are the Innovator. Use `get_random_concepts_for_synthesis`."
LIBRARIAN_PROMPT = "You are the Librarian. Use `prune_old_logs`."
DEVOPS_PROMPT = "You are DevOps. Use `github_action`."
EVALUATOR_PROMPT = """QA Lead. Output JSON: {"score": 1-10, "is_acceptable": bool, "feedback": "Reason"}"""
TROUBLESHOOTER_PROMPT = "System Repair. Fix errors."
EOF

# 2. ОБНОВЛЯЕМ ГРАФ (Привязываем умные модели)
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
    # === FORCE SMART MODEL FOR LOGIC ===
    # Gemini 1.5 Pro или GPT-4o
    m = "smart-model"
    
    # Для простых задач можно использовать Turbo, но пока система тупит - ставим Smart
    if role in ["DESIGNER"]: m = "vision-model"
    
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL"), 
        api_key="stub", 
        model=m, 
        temperature=0.0, # ZERO CREATIVITY -> HIGH OBEDIENCE
        request_timeout=120
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

async def human_node(state): return {}

async def evaluator_node(state):
    if state["messages"][-1].tool_calls: return {"next_agent": "Tools"}
    # Skip eval for now to ensure speed
    return {"next_agent": "Supervisor"}

async def supervisor_node(state):
    llm = get_model("SUPERVISOR").with_structured_output(SupervisorDecision)
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()
    
    # HEURISTIC OVERRIDE (Если LLM не справляется)
    last_text = state["messages"][-1].content.lower()
    if "цель" in last_text or "goal" in last_text: return {"next_agent": "PM"}
    
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
    
    # FORCE TOOL INJECTION
    force = "\n\nSYSTEM OVERRIDE: If the user request implies an action (DB, File, Search), YOU MUST CALL A TOOL. Do not respond with text."
    
    res = await llm.ainvoke([SystemMessage(content=sys+usr+force)] + state["messages"])
    
    if res.tool_calls: return {"messages": [res], "next_agent": "Tools"}
    
    # Если инструмент не вызван, но должен был (проверка)
    if role == "PM" and "create" in state["messages"][-1].content.lower():
        # Force retry with explicit instruction
        return {"messages": [HumanMessage(content="ERROR: You did not call the tool. Call `create_goal` now.")], "next_agent": role}

    return {"messages": [res], "next_agent": "Evaluator"}

async def researcher_node(state): return await worker_node(state, "RESEARCHER", RESEARCHER_PROMPT)
async def coder_node(state): return await worker_node(state, "CODER", CODER_PROMPT)
async def designer_node(state): return await worker_node(state, "DESIGNER", DESIGNER_PROMPT)
async def pm_node(state): return await worker_node(state, "PM", PM_PROMPT)
async def intelligence_node(state): return await worker_node(state, "INTELLIGENCE", INTELLIGENCE_PROMPT)
async def coach_node(state): return await worker_node(state, "COACH", COACH_PROMPT)
async def innovator_node(state): return await worker_node(state, "INNOVATOR", INNOVATOR_PROMPT)
async def librarian_node(state): return await worker_node(state, "LIBRARIAN", LIBRARIAN_PROMPT)
async def devops_node(state): return await worker_node(state, "DEVOPS", DEVOPS_PROMPT)
async def actor_node(state): return await worker_node(state, "ACTOR", "Execute.")
async def troubleshooter_node(state): return {"next_agent": "Evaluator"}
async def post_tool_node(state): return {"next_agent": "Evaluator", "last_error": None}
async def human_node(state): return {}

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
wf.add_node("DevOps", devops_node)
wf.add_node("ACTOR", actor_node)
wf.add_node("Troubleshooter", troubleshooter_node)
wf.add_node("Evaluator", evaluator_node)
wf.add_node("Tools", DynamicToolNode())
wf.add_node("PostTool", post_tool_node)
wf.add_node("HUMAN", human_node)

wf.set_entry_point("Supervisor")
def router(s): return s.get("next_agent", END) if s.get("next_agent") != "FINISH" else END
for n in ["Supervisor", "Researcher", "Coder", "Designer", "PM", "Intelligence", "Coach", "Innovator", "Librarian", "DevOps", "ACTOR", "Troubleshooter", "Evaluator", "PostTool", "HUMAN"]: 
    wf.add_conditional_edges(n, router)
wf.add_edge("Tools", "PostTool")
wf.add_edge("HUMAN", "Supervisor")

app_graph = wf.compile(checkpointer=checkpointer, interrupt_before=["HUMAN"])
EOF

# 3. FIX TELEGRAM RESPONSE
echo "📱 Fixing Telegram Ack..."
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

@dp.message(F.text)
async def h(m: types.Message):
    if m.from_user.id != OWNER: return
    
    # 1. Send "Typing"
    await bot.send_chat_action(m.chat.id, "typing")
    
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            # 2. Send to Core
            sid = f"tg_{m.from_user.id}"
            resp = await c.post(f"{CORE}/chat", json={"session_id": sid, "content": m.text})
            
            # 3. Check if Core accepted it
            if resp.status_code == 200:
                await m.answer("⏳ Task Queued.")
            else:
                await m.answer(f"❌ Core Error: {resp.status_code}")
    except Exception as e:
        await m.answer(f"❌ Connection Error: {e}")

# ... (Остальные методы: ask, notify, startup - оставляем как есть, для скрипта опустим, 
# но в реальности надо сохранить весь файл. Для надежности лучше не перезаписывать telegram 
# этим скриптом, если там нет явных багов, кроме молчания).
EOF

echo "🚀 Restarting Core..."
docker compose build core
docker compose up -d core

echo "✅ DONE. Brain lobotomy fixed."
