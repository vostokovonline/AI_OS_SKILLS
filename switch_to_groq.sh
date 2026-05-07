#!/bin/bash
echo "⚡ SWITCHING TO GROQ (SPEED MODE)..."

# 1. Настраиваем LiteLLM на Groq
cat << 'EOF' > infra/litellm_config.yaml
model_list:
  # Основной мозг - Llama 3.3 70B
  - model_name: main-brain
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: os.environ/GROQ_API_KEY
      rpm: 30

  # Vision (оставляем Gemini Flash, он дешевый)
  - model_name: vision-model
    litellm_params:
      model: gemini/gemini-1.5-flash
      api_key: os.environ/GEMINI_KEY_1

router_settings:
  routing_strategy: "simple-shuffle"
  timeout: 60
  # Если Groq упадет, попробуем Gemini Flash
  fallbacks:
    - "main-brain": ["vision-model"]
EOF

# 2. Перенастраиваем Граф Агентов на новую модель
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
    # Для Картинок - Gemini Flash
    if role == "DESIGNER":
        return ChatOpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key="stub", model="vision-model", temperature=0.2)
    
    # Для ВСЕГО ОСТАЛЬНОГО (Код, Планы, Чат) -> Groq Llama 3
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL"), 
        api_key="stub", 
        model="main-brain", 
        temperature=0.1,
        request_timeout=60
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    last_error: str

# ... (Остальной код графа остается стандартным, копируем узлы) ...
# Вставляем узлы (Supervisor, Workers, Evaluator)
async def human_node(state): return {}

async def evaluator_node(state):
    if state["messages"][-1].tool_calls: return {"next_agent": "Tools"}
    # Skip eval for speed in Groq mode
    return {"next_agent": "Supervisor"}

async def supervisor_node(state):
    llm = get_model("SUPERVISOR") # Raw LLM, no structured output wrapper yet to be safe with Llama
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()
    last_msg = state["messages"][-1].content.lower()
    
    # Heuristics
    if "цель" in last_msg or "goal" in last_msg: return {"next_agent": "PM"}
    if "код" in last_msg or "code" in last_msg: return {"next_agent": "Coder"}
    
    prompt = f"{sys}\n{usr}\n\nHISTORY:\n{str(state['messages'][-5:])}\nDECISION (Return ONLY role name):"
    try:
        res = await llm.ainvoke([HumanMessage(content=prompt)])
        decision = res.content.strip().upper()
        if "PM" in decision: return {"next_agent": "PM"}
        if "CODER" in decision: return {"next_agent": "Coder"}
        if "RESEARCHER" in decision: return {"next_agent": "Researcher"}
        return {"next_agent": "FINISH"}
    except: return {"next_agent": "FINISH"}

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
    # Force tool usage instruction
    force = "\n\nIMPORTANT: If you need to perform an action, CALL THE TOOL. Do not just talk."
    res = await llm.ainvoke([SystemMessage(content=sys+usr+force)] + state["messages"])
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
async def actor_node(state): return await worker_node(state, "ACTOR", "Execute tasks.")
async def troubleshooter_node(state): return {"next_agent": "Evaluator"}
async def post_tool_node(state): return {"next_agent": "Evaluator", "last_error": None}

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

echo "✅ SWITCHED TO GROQ."
echo "👉 1. Edit .env -> Add GROQ_API_KEY"
echo "👉 2. Run: docker compose restart litellm core core_worker"
