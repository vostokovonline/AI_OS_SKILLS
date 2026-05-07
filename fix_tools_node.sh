#!/bin/bash
echo "🧠 FIXING DYNAMIC TOOL NODE ERROR..."

# Мы полностью переписываем agent_graph.py с правильной логикой вызова инструментов
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
    # HYBRID ROUTING (Groq / Gemini)
    m = "smart-model"
    if role in ["CODER", "SUPERVISOR", "DEVOPS"]: m = "speed-coder" # Groq Llama 3
    if role in ["LIBRARIAN", "TROUBLESHOOTER", "EVALUATOR"]: m = "smart-model" # Gemini Pro
    if role == "DESIGNER": m = "vision-model"
    
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL"), 
        api_key="stub", 
        model=m, 
        temperature=0, 
        request_timeout=90, 
        max_retries=2
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

# --- NODES ---

async def planner_node(state):
    llm = get_model("PLANNER").with_structured_output(Plan)
    sys = await get_prompt("PLANNER") or "Architect. Create plan."
    try:
        plan = await llm.ainvoke([SystemMessage(content=sys)] + state["messages"])
    except:
        # Fallback if Plan parsing fails
        return {"next_node": "ACTOR"} 

    # Simplified planning logic for stability
    return {
        "messages": [HumanMessage(content=f"🧠 PLAN GENERATED.")],
        "next_node": "EXECUTOR"
    }

# SUPERVISOR NODE
async def supervisor_node(state):
    llm = get_model("SUPERVISOR").with_structured_output(SupervisorDecision)
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()
    prompt = f"{sys}\n{usr}\n\nHISTORY:\n{str(state['messages'][-5:])}\nDECISION:"
    
    try:
        decision = await llm.ainvoke([HumanMessage(content=prompt)])
        nxt = decision.next_node.title()
        if nxt == "Finish": nxt = "FINISH"
    except Exception as e:
        print(f"Supervisor Error: {e}")
        nxt = "FINISH"
    return {"next_agent": nxt}

# GENERIC WORKER WRAPPER
async def worker_node(state, role, default_prompt):
    # Объединяем статические инструменты и динамические (MCP)
    all_tools = AGENT_TOOLS + mcp_manager.tools
    llm = get_model(role).bind_tools(all_tools)
    
    sys = await get_prompt(role) or default_prompt
    usr = await get_user_profile()
    
    try:
        res = await llm.ainvoke([SystemMessage(content=sys+usr)] + state["messages"])
    except Exception as e:
        return {"messages": [HumanMessage(content=f"Error in {role}: {e}")], "next_agent": "Evaluator"}

    if res.tool_calls: 
        return {"messages": [res], "next_agent": "Tools"}
    
    return {"messages": [res], "next_agent": "Evaluator"}

# WORKER NODES
async def researcher_node(state): return await worker_node(state, "RESEARCHER", RESEARCHER_PROMPT)
async def coder_node(state): return await worker_node(state, "CODER", CODER_PROMPT)
async def designer_node(state): return await worker_node(state, "DESIGNER", DESIGNER_PROMPT)
async def pm_node(state): return await worker_node(state, "PM", PM_PROMPT)
async def intelligence_node(state): return await worker_node(state, "INTELLIGENCE", INTELLIGENCE_PROMPT)
async def coach_node(state): return await worker_node(state, "COACH", COACH_PROMPT)
async def innovator_node(state): return await worker_node(state, "INNOVATOR", INNOVATOR_PROMPT)
async def librarian_node(state): return await
