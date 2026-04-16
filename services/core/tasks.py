import os
import asyncio
import httpx
from celery import Celery
from langchain_core.messages import HumanMessage
from resource_manager import SystemMonitor
from agent_graph import app_graph
import redis

# Import goal executor tasks to register them with Celery
from goal_executor import execute_goal_task, execute_complex_goal_task
# Import shared celery app
from celery_config import celery_app

# NEW: Centralized logging and error handling
from logging_config import get_logger
from error_handler import ErrorHandler

logger = get_logger(__name__)
monitor = SystemMonitor()

async def notify(msg, sid=None):
    """Send notification via Telegram with error handling"""
    try:
        if sid and "tg_" in sid:
            await httpx.post(
                f"{os.getenv('TELEGRAM_URL')}/ask_human",
                json={"chat_id": sid, "text": msg}
            )
        else:
            await httpx.post(
                f"{os.getenv('TELEGRAM_URL')}/notify",
                json={"message": msg}
            )
    except httpx.HTTPError as e:
        logger.error(
            "notification_failed",
            error=str(e),
            session_id=sid
        )
    except Exception as e:
        # Log but don't crash - notifications are non-critical
        logger.warning(
            "notification_error",
            error_type=type(e).__name__,
            error_message=str(e)
        )

async def _exec(sid, input_msg=None):
    """Execute agent graph with proper logging and error handling"""
    cfg = {"configurable": {"thread_id": sid}, "recursion_limit": 50}
    inputs = {"messages": [input_msg]} if input_msg else None

    logger.info("graph_execution_started", session_id=sid)

    try:
        async for event in app_graph.astream(inputs, cfg, stream_mode="values"):
            final = event

        res = final['messages'][-1].content
        logger.info("graph_execution_completed", session_id=sid, result_length=len(res))

        await notify(f"✅ DONE: {res[:2000]}")
        return res

    except Exception as e:
        logger.error(
            "graph_execution_failed",
            session_id=sid,
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True
        )
        await notify(f"🔥 SYSTEM ERROR: {e}")
        raise

    # Check if human input needed
    try:
        snap = await app_graph.aget_state(cfg)
        if snap.next and snap.next[0] == "HUMAN":
            logger.info("graph_paused_for_human", session_id=sid)
            await notify(f"🛑 PAUSED: {final['messages'][-1].content}", sid)
            return "PAUSED"
    except Exception as e:
        logger.warning("failed_to_check_human_pause", error=str(e))


# NEW: Proper async task execution without asyncio.run()
def _run_async(coro):
    """
    Run async coroutine in existing event loop.
    Replaces asyncio.run() which creates new loop each time.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, we can't use run_until_complete
            # This shouldn't happen in Celery worker, but handle gracefully
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop exists, create one (shouldn't happen in production)
        return asyncio.run(coro)


@celery_app.task(bind=True)
def run_chat_task(self, session_id, content, image_url=None):
    """Celery task for chat execution with proper error handling"""
    if not monitor.check_health():
        logger.warning("system_busy", session_id=session_id)
        return "BUSY"

    msg = (
        HumanMessage(content=[
            {"type": "text", "text": content},
            {"type": "image_url", "image_url": image_url}
        ])
        if image_url
        else HumanMessage(content=content)
    )

    return _run_async(_exec(session_id, msg))


@celery_app.task(bind=True)
def run_resume_task(self, session_id):
    """Celery task for resuming paused execution"""
    logger.info("resume_task_started", session_id=session_id)
    return _run_async(_exec(session_id, None))


@celery_app.task(bind=True)
def run_cron_task(self, session_id, content):
    """Celery task for scheduled/cron execution"""
    logger.info("cron_task_started", session_id=session_id)
    return _run_async(_exec(session_id, HumanMessage(content=content)))


@celery_app.task(bind=True)
def decompose_goal_task(self, goal_id):
    """
    🔧 FIX: Celery task for auto-decomposition of non-atomic goals.
    Called by:
    1. goal_executor.create_goal_with_uow (auto-decompose on creation)
    2. scheduler.stuck_goals_watchdog (self-healing)
    3. Manual trigger from dashboard
    """
    from goal_decomposer import goal_decomposer

    logger.info("decompose_task_started", goal_id=goal_id)
    try:
        result = _run_async(goal_decomposer.decompose_goal(goal_id))
        logger.info("decompose_task_completed", goal_id=goal_id, children=len(result) if result else 0)
        return {"goal_id": goal_id, "children_created": len(result) if result else 0}
    except Exception as e:
        logger.error("decompose_task_failed", goal_id=goal_id, error=str(e))
        return {"goal_id": goal_id, "error": str(e)}
