#!/bin/bash
echo "🧠 FIXING BRAIN ROUTING (ADDING HEURISTICS)..."

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
    # Используем smart-model (Gemini) для надежности
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL"), 
        api_key="stub", 
        model="smart-model", 
        temperature=0, 
        request_timeout=60
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

async def human_node(state): return {}

async def evaluator_node(state):
    if state["messages"][-1].tool_calls: return {"next_agent": "Tools"}
    # Skip eval for now to speed up debugging
    return {"next_agent": "Supervisor"}

async def supervisor_node(state):
    llm = get_model("SUPERVISOR") # Raw LLM, no structured output wrapper yet
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()
    
    last_msg = state["messages"][-1].content.lower()
    print(f"🤖 SUPERVISOR INPUT: {last_msg}")

    # --- 1. HEURISTIC ROUTING (Hardcoded Rules) ---
    # Это спасательный круг, если LLM тупит
    if "цель" in last_msg or "goal" in last_msg or "проект" in last_msg:
        print("🚀 HEURISTIC MATCH: -> PM")
        return {"next_agent": "PM"}
    if "код" in last_msg or "code" in last_msg or "скрипт" in last_msg:
        print("🚀 HEURISTIC MATCH: -> Coder")
        return {"next_agent": "Coder"}
    if "найди" in last_msg or "search" in last_msg:
        print("🚀 HEURISTIC MATCH: -> Researcher")
        return {"next_agent": "Researcher"}

    # --- 2. LLM ROUTING (Fallback) ---
    prompt = f"{sys}\n{usr}\n\nHISTORY:\n{str(state['messages'][-5:])}\nDECISION (Return ONLY the role name: PM, CODER, RESEARCHER, FINISH):"
    
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        decision = res.content.strip().upper()
        print(f"🤔 LLM DECISION: {decision}")
        
        if "PM" in decision: return {"next_agent": "PM"}
        if "CODER" in decision: return {"next_agent": "Coder"}
        if "RESEARCHER" in decision: return {"next_agent": "Researcher"}
        if "DESIGNER" in decision: return {"next_agent": "Designer"}
        
        return {"next_agent": "FINISH"}
    except Exception as e:
        print(f"❌ Supervisor Crash: {e}")
        return {"next_agent": "FINISH"}

class DynamicToolNode(ToolNode):
    def __init__(self): super().__init__([])
    async def ainvoke(self, input, config=None, **kwargs):
        self.tools_by_name = {t.name: t for t in (AGENT_TOOLS + mcp_manager.tools)}
        return await super().ainvoke(input, config, **kwargs)

async def worker_node(state, role, default_prompt):
    print(f"👷 WORKER STARTED: {role}")
    tools = AGENT_TOOLS + mcp_manager.tools
    llm = get_model(role).bind_tools(tools)
    sys = await get_prompt(role) or default_prompt
    usr = await get_user_profile()
    
    # FORCE TOOL USAGE
    force = "\n\nCRITICAL: If the user asked to CREATE/SAVE something, call the tool immediately. Do not ask for details."
    
    res = await llm.ainvoke([SystemMessage(content=sys+usr+force)] + state["messages"])
    
    if res.tool_calls: 
        print(f"🛠️ TOOL CALL DETECTED: {res.tool_calls}")
        return {"messages": [res], "next_agent": "Tools"}
    
    print(f"🗣️ WORKER TEXT RESPONSE: {res.content[:50]}...")
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
async def actor_node(state): return await worker_node(state, "ACTOR", "You are an Actor. Execute tasks.")
async def troubleshooter_node(state): return {"next_agent": "Evaluator"} # Stub

async def post_tool_node(state):
    print("✅ TOOL EXECUTED. Returning to Evaluator.")
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

nodes = ["Supervisor", "Researcher", "Coder", "Designer", "PM", "Intelligence", "Coach", "Innovator", "Librarian", "DevOps", "ACTOR", "Troubleshooter", "Evaluator", "PostTool", "HUMAN"]
for n in nodes: wf.add_conditional_edges(n, router)

wf.add_edge("Tools", "PostTool")
wf.add_edge("HUMAN", "Supervisor")

app_graph = wf.compile(checkpointer=checkpointer, interrupt_before=["HUMAN"])
EOF

echo "🚀 REBUILDING CORE..."
docker compose build core core_worker
docker compose up -d core core_worker

echo "👀 Watching logs..."
docker logs -f ns_core_worker
