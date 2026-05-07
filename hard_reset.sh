#!/bin/bash
echo "☢️ PERFORMING HARD RESET OF COGNITIVE SERVICES..."

# 1. Добавляем "Print-Debug" в граф, чтобы видеть мысли в консоли
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
from agents.schemas import SupervisorDecision
from agents.prompts import *

checkpointer = MemorySaver()

# FORCE SMART MODEL
def get_model(role="DEFAULT"):
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL"), 
        api_key="stub", 
        model="smart-model", 
        temperature=0.0, 
        request_timeout=120
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

async def supervisor_node(state):
    llm = get_model("SUPERVISOR").with_structured_output(SupervisorDecision)
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()
    
    last_msg = state["messages"][-1].content.lower()
    print(f"🤖 SUPERVISOR SEEKS: {last_msg}") # DEBUG LOG

    # HARD HEURISTICS
    if "цель" in last_msg or "goal" in last_msg: 
        print("🚀 FORCE ROUTING -> PM")
        return {"next_agent": "PM"}
    
    prompt = f"{sys}\n{usr}\nDECISION:"
    try:
        decision = await llm.ainvoke([HumanMessage(content=prompt)] + state["messages"][-5:])
        nxt = decision.next_node.title()
        if nxt == "Finish": nxt = "FINISH"
    except Exception as e:
        print(f"❌ SUPERVISOR ERROR: {e}")
        nxt = "FINISH"
    return {"next_agent": nxt}

async def worker_node(state, role, default_prompt):
    print(f"👷 WORKER {role} STARTED...") # DEBUG LOG
    tools = AGENT_TOOLS + mcp_manager.tools
    llm = get_model(role).bind_tools(tools)
    sys = await get_prompt(role) or default_prompt
    usr = await get_user_profile()
    
    # AGGRESSIVE PROMPT INJECTION
    force = "\n\nSYSTEM INSTRUCTION: You MUST use a tool. Do NOT reply with text only. If you need to create a goal, call `create_goal`."
    
    # Выводим, что мы отправляем модели (для отладки)
    # print(f"📤 SENDING TO LLM: {state['messages'][-1].content}")

    res = await llm.ainvoke([SystemMessage(content=sys+usr+force)] + state["messages"])
    
    print(f"📥 LLM RESPONSE: {res}") # DEBUG LOG: SEE WHAT LLM SAYS

    if res.tool_calls: 
        print(f"🛠️ TOOL CALLING: {res.tool_calls}")
        return {"messages": [res], "next_agent": "Tools"}
    
    print("⚠️ WARNING: LLM did not call a tool.")
    return {"messages": [res], "next_agent": "Evaluator"}

# Node Wrappers
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
async def evaluator_node(state): return {"next_agent": "Supervisor"} # Skip eval for speed
async def human_node(state): return {}

class DynamicToolNode(ToolNode):
    def __init__(self): super().__init__([])
    async def ainvoke(self, input, config=None, **kwargs):
        self.tools_by_name = {t.name: t for t in (AGENT_TOOLS + mcp_manager.tools)}
        return await super().ainvoke(input, config, **kwargs)

async def post_tool_node(state):
    print("✅ TOOL FINISHED.")
    return {"next_agent": "Evaluator", "last_error": None}

# Graph Assembly
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
def router(s):
    n = s.get("next_agent", END)
    if n == "FINISH": return END
    return n

for n in ["Supervisor", "Researcher", "Coder", "Designer", "PM", "Intelligence", "Coach", "Innovator", "Librarian", "DevOps", "ACTOR", "Troubleshooter", "Evaluator", "PostTool", "HUMAN"]: 
    wf.add_conditional_edges(n, router)
wf.add_edge("Tools", "PostTool")
wf.add_edge("HUMAN", "Supervisor")

app_graph = wf.compile(checkpointer=checkpointer, interrupt_before=["HUMAN"])
EOF

# 2. ОСТАНОВКА И УДАЛЕНИЕ (ЧИСТКА)
echo "🧹 Stopping Core Containers..."
docker stop ns_core ns_core_worker
docker rm ns_core ns_core_worker

# 3. ПЕРЕСБОРКА БЕЗ КЭША (ГАРАНТИЯ ОБНОВЛЕНИЯ)
echo "🔨 Rebuilding Core from scratch..."
docker compose build --no-cache core core_worker

# 4. ЗАПУСК
echo "🚀 Starting fresh containers..."
docker compose up -d core core_worker

echo "✅ DONE. Now run: 'docker logs -f ns_core_worker' and send a message!"
