#!/bin/bash
echo "🧠 FIXING GRAPH ATTRIBUTE ERROR..."

cat << 'EOF' > services/core/agent_graph.py
import os, operator
from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
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
    m = "smart-model"
    if role in ["CODER", "SUPERVISOR", "DEVOPS"]: m = "speed-coder"
    if role in ["LIBRARIAN", "TROUBLESHOOTER", "EVALUATOR"]: m = "smart-model"
    if role == "DESIGNER": m = "vision-model"
    return ChatOpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key="stub", model=m, temperature=0, request_timeout=90, max_retries=2)

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

async def human_node(state): return {}

async def evaluator_node(state):
    last_msg = state["messages"][-1]
    
    # --- FIX START: Safe check for tool_calls ---
    # Проверяем, есть ли атрибут tool_calls (он есть только у AIMessage)
    if getattr(last_msg, "tool_calls", None): 
        return {"next_agent": "Tools"}
    # --- FIX END ---

    llm = get_model("EVALUATOR").with_structured_output(QualityReview)
    try:
        # Оцениваем последние сообщения (контекст + результат тулза)
        res = await llm.ainvoke([SystemMessage(content=EVALUATOR_PROMPT)] + state["messages"][-3:])
    except: return {"next_agent": "Supervisor"}

    if res.is_acceptable:
        if res.score >= 8: return {"next_agent": "FINISH"}
        return {"next_agent": "Supervisor"}
    
    if state.get("retry_count", 0) >= 2: 
        return {"next_agent": "HUMAN", "messages": [HumanMessage(content=f"FATAL: {res.feedback}")]}
    
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

# Function-based ToolNode
async def dynamic_tool_node(state):
    current_tools = AGENT_TOOLS + mcp_manager.tools
    tool_node = ToolNode(current_tools)
    return await tool_node.ainvoke(state)

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
async def devops_node(state): return await worker_node(state, "DEVOPS", DEVOPS_PROMPT)
async def actor_node(state): return await worker_node(state, "ACTOR", "You are an Actor. Execute tasks.")

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
wf.add_node("DevOps", devops_node)
wf.add_node("ACTOR", actor_node)
wf.add_node("Troubleshooter", troubleshooter_node)
wf.add_node("Evaluator", evaluator_node)
wf.add_node("Tools", dynamic_tool_node)
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

echo "✅ Graph Logic Patched."
echo "🚀 Restarting Core..."
docker compose build core core_worker
docker compose up -d core core_worker
