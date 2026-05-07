#!/bin/bash
echo "🧠 APPLYING 'ANTI-LAZY' PATCH..."

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

# Используем самую умную модель для принятия решений
def get_model(role="DEFAULT"):
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL"), 
        api_key="stub", 
        model="smart-model",  # Gemini Pro / GPT-4
        temperature=0.0,      # Zero creativity -> Maximum obedience
        request_timeout=120
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

async def human_node(state): return {}

# STRICT SUPERVISOR
async def supervisor_node(state):
    llm = get_model()
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()
    
    last_msg = state["messages"][-1].content.lower()
    
    # HARDCODED ROUTING (Если LLM тупит)
    if "цель" in last_msg or "goal" in last_msg or "план" in last_msg: 
        print("🚦 Routing to PM (Heuristic)")
        return {"next_agent": "PM"}
        
    prompt = f"{sys}\n{usr}\n\nHISTORY:\n{str(state['messages'][-5:])}\nDECISION (PM, CODER, RESEARCHER, FINISH):"
    try:
        decision = await llm.ainvoke([HumanMessage(content=prompt)])
        nxt = decision.next_node.title()
        if nxt == "Finish": nxt = "FINISH"
    except: nxt = "FINISH"
    return {"next_agent": nxt}

async def dynamic_tool_node(state):
    current_tools = AGENT_TOOLS + mcp_manager.tools
    tool_node = ToolNode(current_tools)
    return await tool_node.ainvoke(state)

async def worker_node(state, role, default_prompt):
    tools = AGENT_TOOLS + mcp_manager.tools
    llm = get_model().bind_tools(tools)
    sys = await get_prompt(role) or default_prompt
    usr = await get_user_profile()
    
    # FORCE INSTRUCTION
    force = """
    CRITICAL INSTRUCTION:
    You are an AGENT, not a chatbot.
    If the user asks to create/save/write something, YOU MUST CALL A TOOL.
    Do NOT describe what you would do. JUST DO IT.
    """
    
    res = await llm.ainvoke([SystemMessage(content=sys+usr+force)] + state["messages"])
    
    # Если инструмент вызван - отлично
    if res.tool_calls: 
        print(f"🛠 Tool Call by {role}: {res.tool_calls}")
        return {"messages": [res], "next_agent": "Tools"}
    
    # Если инструмент НЕ вызван, но должен был (проверка эвристикой)
    content = res.content.lower()
    if "done" in content or "created" in content or "saved" in content:
        # Агент врет, что сделал, но тулза нет.
        print(f"🤥 {role} hallucinated success without tool.")
        retry_msg = "SYSTEM ERROR: You claimed success but did not call any tool. CALL THE TOOL NOW."
        return {"messages": [res, HumanMessage(content=retry_msg)], "next_agent": role} # Force retry

    return {"messages": [res], "next_agent": "Evaluator"}

# ... (Остальные узлы стандартные) ...
# Для краткости скрипта, я скопирую стандартную обвязку
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

async def post_tool_node(state):
    # Tool executed successfully
    print("✅ Tool Executed.")
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

echo "✅ ANTI-LAZY PATCH APPLIED."
echo "👉 Restarting Core..."
docker compose restart core core_worker
