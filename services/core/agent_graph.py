from logging_config import get_logger
logger = get_logger(__name__)

import os, operator, json, re
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

# --- INTELLIGENT MODEL ROTATOR WITH LOAD BALANCING ---
def get_model(role="DEFAULT"):
    """
    Возвращает LangChain модель с умной ротацией.

    НОВАЯ СИСТЕМА (v2.0):
    - Ротация через 7 моделей (круговой)
    - Предпочтение облачных моделей (не нагружают ПК)
    - Локальная модель используется редко
    - Cold start avoidance (предотвращает задержки)
    - Load balancing (распределяет нагрузку)

    Доступные модели:
    1. minimax-m2:cloud (облачная, быстрая)
    2. glm-4.6:cloud (облачная)
    3. gpt-oss:120b-cloud (облачная, большая)
    4. qwen3-coder:480b-cloud (облачная, код)
    5. qwen3-vl:235b-cloud (облачная, визуальная)
    6. qwen2.5-coder:latest (ЛОКАЛЬНАЯ, 4.7GB)
    7. deepseek-v3.1:671b-cloud (облачная, рассуждения)
    """
    # Try to use intelligent rotator
    try:
        from model_rotator import model_rotator

        # Select model based on rotation strategy
        model_name = model_rotator.select_model(role)

        logger.debug(
            "model_selected_by_rotator",
            role=role,
            model=model_name
        )

    except Exception as e:
        # Fallback to simple mapping if rotator fails
        logger.warning("model_rotator_failed", error=str(e), fallback="simple_mapping")

        MODEL_MAPPING = {
            "SUPERVISOR": "local-coder",
            "CODER": "local-coder",
            "PM": "local-coder",
            "RESEARCHER": "local-coder",
            "INTELLIGENCE": "deepseek-reasoner",
            "DEFAULT": "local-coder"
        }

        model_name = MODEL_MAPPING.get(role, os.getenv("LLM_MODEL", "local-coder"))

    # Temperature по роли
    if role == "SUPERVISOR":
        temp = 0.1  # Более детерминированный для роутинга
    elif role == "INTELLIGENCE":
        temp = 0.3  # Более креативный для анализа
    else:
        temp = 0.2  # Стандартный

    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY", "sk-1234"),
        model=model_name,
        temperature=temp,
        request_timeout=120  # 2 минуты (все модели быстрые)
    )

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    next_agent: str
    retry_count: int
    loop_count: int
    last_error: str

# --- ROBUST JSON PARSER ---
def extract_next_agent(llm_output: str) -> str:
    """
    Вытаскивает имя агента из ответа DeepSeek, игнорируя 'мысли' и markdown.
    """
    text = llm_output.strip()
    
    # 1. Попытка найти JSON блок 
    json_match = re.search(r"", text, re.DOTALL)
    if not json_match:
        # 2. Попытка найти просто JSON объект {...}
        json_match = re.search(r"(\{.*\})", text, re.DOTALL)
    
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return data.get("next_node", "FINISH")
        except json.JSONDecodeError as e:
            logger.debug("json_decode_error", error=str(e))
        except Exception as e:
            logger.warning("unexpected_error_parsing_json", error=str(e))
            
    # 3. Эвристический поиск, если JSON сломан (DeepSeek иногда пишет просто: "Decision: Researcher")
    if "Researcher" in text: return "Researcher"
    if "Coder" in text: return "Coder"
    if "PM" in text: return "PM"
    if "Finish" in text or "FINISH" in text: return "FINISH"
    
    return "PM" # Fallback по умолчанию

async def supervisor_node(state):
    # Предохранитель от бесконечного цикла
    msg_count = len(state["messages"])
    if msg_count > 25:
        logger.info(f"🛑 SAFETY BREAK: {msg_count} messages. Force FINISH.")
        return {"next_agent": "FINISH"}

    # Проверяем, не зациклились ли мы (повторяющиеся сообщения)
    if msg_count >= 10:
        last_5 = [m.content if isinstance(m.content, str) else str(m.content)[:100]
                  for m in state["messages"][-5:]]
        if len(set(last_5)) < 3:  # Если последние 5 сообщений почти одинаковые
            logger.info(f"🛑 LOOP DETECTED: Messages repeating. Force FINISH.")
            return {"next_agent": "FINISH"}

    # Используем обычный invoke (без structured output), чтобы получить "мысли" модели
    llm = get_model("SUPERVISOR")
    sys = await get_prompt("SUPERVISOR")
    usr = await get_user_profile()

    # 🧠 EMOTIONAL LAYER INTEGRATION
    # Collect emotional context for decision-making
    try:
        from emotional_helpers import collect_emotional_signals, format_emotional_context
        from emotional_layer import emotional_layer

        # Get user message
        last_content = state["messages"][-1].content
        if isinstance(last_content, str):
            user_message = last_content
        else:
            user_message = str(last_content)

        # Default user_id (TODO: get from session/auth)
        user_id = "00000000-0000-0000-0000-000000000001"

        # Collect signals
        signals = await collect_emotional_signals(user_id, user_message)

        # Get emotional context
        emotional_context = await emotional_layer.get_influence_context(user_id, signals)

        # Format as hints for LLM
        emotional_hints = format_emotional_context(emotional_context)

        if emotional_hints:
            logger.info(f"💭 EMOTIONAL CONTEXT: {emotional_context}")

    except Exception as e:
        # If emotional layer fails, continue without it (graceful degradation)
        logger.info(f"⚠️  Emotional layer error (continuing without): {e}")
        emotional_hints = ""

    logger.info(f"🧠 DEEPSEEK THINKING ON: {last_content[:60]}...")

    # Strict JSON Instruction
    instruction = (
        "\n\nCOMMAND:"
        "\nAnalyze the conversation. Who should act next?"
        "\nOptions: [Researcher, Coder, PM, Designer, Intelligence, Finish]"
        "\n"
        "\nRULES:"
        "\n1. If searching/news/web -> 'Researcher'"
        "\n2. If coding/files/analysis -> 'Coder'"
        "\n3. If goals/plans -> 'PM'"
        "\n4. If done -> 'Finish'"
        "\n"
        "\nOUTPUT FORMAT:"
        "\nYou MUST respond with a JSON object inside a code block, like this:"
        "\n"
        "\nDo not write anything else outside the JSON."
    )

    # Add emotional hints if present
    if emotional_hints:
        instruction += (
            "\n\n"
            "\nBEHAVIORAL ADJUSTMENT:"
            "\n" + emotional_hints
        )

    prompt = f"{sys}\n{usr}\n{instruction}"
    
    try:
        # Запрашиваем raw text
        response = await llm.ainvoke([HumanMessage(content=prompt)] + state["messages"][-15:])
        raw_content = response.content
        
        # Парсим вручную
        nxt = extract_next_agent(raw_content)
        
        # Валидация
        valid_agents = ["Researcher", "Coder", "Designer", "PM", "Intelligence", "Coach", "Innovator", "Librarian", "DevOps", "Actor", "Troubleshooter"]
        if nxt != "FINISH" and nxt not in valid_agents:
             nxt = "PM" # Если галлюцинирует, зовем менеджера
             
    except Exception as e:
        logger.info(f"❌ SUPERVISOR ERROR: {e}")
        nxt = "PM" 
        
    logger.info(f"🧠 DEEPSEEK DECIDED: {nxt}")
    return {"next_agent": nxt}

async def worker_node(state, role, default_prompt):
    logger.info(f"👷 WORKER {role} (Groq) STARTED...") 
    tools = AGENT_TOOLS + mcp_manager.tools
    llm = get_model(role).bind_tools(tools)
    sys = await get_prompt(role) or default_prompt
    usr = await get_user_profile()

    force = "\n\nSYSTEM INSTRUCTION: You represent the 'Hands' of the system. Use tools immediately. If task requires file creation, use write_file tool."

    res = await llm.ainvoke([SystemMessage(content=sys+usr+force)] + state["messages"])

    if res.tool_calls:
        logger.info(f"🛠️ TOOL CALLING: {res.tool_calls}")
        return {"messages": [res], "next_agent": "Tools"}

    logger.info(f"✅ WORKER {role} FINISHED.")
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
async def evaluator_node(state): return {"next_agent": "Supervisor"} 

async def dynamic_tool_node(state):
    current_tools = AGENT_TOOLS + mcp_manager.tools
    runnable = ToolNode(current_tools)
    return await runnable.ainvoke(state)

async def post_tool_node(state):
    logger.info("✅ TOOL EXECUTION DONE.")
    return {"next_agent": "Evaluator"}

async def human_node(state): return {}

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
wf.add_node("Tools", dynamic_tool_node)
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



# ==============================
# Supervisor v2 — Goal-driven, no recursion
# ==============================

async def supervisor_v2(state):
    goals = state.get("goals", [])

    if not goals:
        state.setdefault("messages", []).append(
            "Supervisor: no goals defined."
        )
        return state

    active = next((g for g in goals if g.get("status") == "active"), None)

    if not active:
        pending = next((g for g in goals if g.get("status") == "pending"), None)
        if not pending:
            state.setdefault("messages", []).append(
                "Supervisor: all goals completed."
            )
            return state
        pending["status"] = "active"
        active = pending

    if active.get("type") == "bounded":
        action = f"[GOAL DONE] {active.get('title')}"
        active["status"] = "done"
    else:
        action = f"[SYSTEM GOAL STEP] {active.get('title')}"

    state.setdefault("messages", []).append(action)
    return state
