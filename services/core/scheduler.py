import uuid
import asyncio
from uuid import UUID
# Use BackgroundScheduler instead of AsyncIOScheduler for thread-safe operation
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from tasks import run_cron_task
from resource_manager import SystemMonitor
from cognition.drive import generate_internal_drive

# Centralized logging
from logging_config import get_logger

logger = get_logger(__name__)

# BackgroundScheduler works without event loop - perfect for threading
scheduler = BackgroundScheduler()
monitor = SystemMonitor()


# ============================================================================
# USE CASES LAYER - Подключаем use-cases вместо старой логики
# ============================================================================

def _setup_event_handlers():
    """Регистрируем обработчики событий при старте"""
    from application.events.bus import get_event_bus
    from application.events.goal_events import GoalActivated
    from application.event_handlers.decompose_goal import DecomposeGoalHandler
    from infrastructure.uow import get_uow
    from goal_decomposer import GoalDecomposer

    event_bus = get_event_bus()
    uow_factory = get_uow
    decomposer = GoalDecomposer()

    handler = DecomposeGoalHandler(uow_factory, decomposer)
    event_bus.subscribe(GoalActivated, handler)

    import logging
    logging.getLogger("event_bus").info("Event handlers registered: GoalActivated → DecomposeGoalHandler")


def _setup_execution_event_handlers():
    """Регистрируем обработчики событий выполнения"""
    from application.events.bus import get_event_bus
    from application.events.execution_events import (
        GoalExecutionFinished,
        BatchExecutionCompleted
    )
    from logging_config import get_logger

    logger = get_logger(__name__)
    event_bus = get_event_bus()

    # Handler: Log each execution event
    def log_execution_event(event: GoalExecutionFinished):
        logger.info(
            "goal_execution_finished",
            goal_id=str(event.goal_id)[:8],
            status=event.status,
            confidence=event.confidence,
            attempts=event.attempts,
            artifacts=event.artifacts_registered
        )

    # Handler: Log batch completion
    def log_batch_event(event: BatchExecutionCompleted):
        logger.info(
            "batch_execution_completed",
            total=event.total_goals,
            completed=event.completed,
            failed=event.failed,
            duration_ms=event.execution_time_ms
        )

    # Handler: Unblock dependent goals when goal completes
    async def unblock_dependents(event: GoalExecutionFinished):
        """When a goal finishes, check if dependent goals can be unblocked (BATCH)."""
        # Only unblock if goal actually completed successfully
        if event.status != "done":
            return

        from infrastructure.uow import get_uow
        from goal_dependencies import get_dependency_resolver

        try:
            async with get_uow() as uow:
                resolver = get_dependency_resolver(uow.session)

                # BATCH UNBLOCK: Single SQL UPDATE for all dependent goals
                # Performance: 1000 dependents → 1 UPDATE instead of 1000 UPDATEs
                result = await resolver.unblock_dependent_goals_batch(event.goal_id)

                if result["unblocked"] > 0:
                    logger.info(
                        "goals_unblocked_batch",
                        total_found=result["total_found"],
                        unblocked=result["unblocked"],
                        unblocked_goal_ids=[str(gid)[:8] for gid in result["goal_ids"]],
                        triggered_by=str(event.goal_id)[:8]
                    )
        except Exception as e:
            logger.error(
                "dependency_resolution_failed",
                goal_id=str(event.goal_id)[:8],
                error=str(e)[:200]
            )

    # Subscribe handlers
    event_bus.subscribe(GoalExecutionFinished, log_execution_event)
    event_bus.subscribe(GoalExecutionFinished, unblock_dependents)
    event_bus.subscribe(BatchExecutionCompleted, log_batch_event)

    logger.info("execution_event_handlers_registered")


def _create_use_cases():
    """
    Создаём use-cases с зависимостями.

    Это единственное место, где собираются зависимости.

    v3.0: Теперь включает Arbitration layer.
    """
    from infrastructure.uow import create_uow_provider, get_uow
    from application.bulk_transition_engine import bulk_transition_engine
    from application.use_cases import (
        ResumePendingGoalsUseCase,
        ExecuteReadyGoalsUseCase,
        DecomposeActivatedGoalsUseCase
    )
    from application.events.bus import get_event_bus
    from goal_executor_v2 import goal_executor_v2
    from goal_decomposer import GoalDecomposer

    # Arbitration components (v3.0)
    from application.arbitration import (
        BatchArbitrator,
        GreedyUtilityPolicy,
        ConfidenceUtilityEstimator,
        ConstantCostEstimator,
        ConfidenceRiskEstimator,
        FixedBudgetAllocator,
        InMemoryArbitrationLog,
    )

    uow_factory = get_uow
    event_bus = get_event_bus()

    # Create arbitration components
    arbitrator = BatchArbitrator(
        utility_estimator=ConfidenceUtilityEstimator(),
        cost_estimator=ConstantCostEstimator(cost=1.0),
        risk_estimator=ConfidenceRiskEstimator(),
        policy=GreedyUtilityPolicy(),
        arbitration_log=InMemoryArbitrationLog(max_size=100),
    )

    capital_allocator = FixedBudgetAllocator(budget=30.0)  # ← FIX C: Increased from 10.0 to 30.0 for higher throughput

    resume_use_case = ResumePendingGoalsUseCase(
        uow_factory=uow_factory,
        bulk_engine=bulk_transition_engine,
    )

    execute_use_case = ExecuteReadyGoalsUseCase(
        uow_factory=uow_factory,
        executor=goal_executor_v2,
        bulk_engine=bulk_transition_engine,
        arbitrator=arbitrator,  # ✅ v3.0: Arbitration layer
        capital_allocator=capital_allocator,  # ✅ v3.0: Budget management
        event_bus=event_bus,
    )

    decomposer_instance = GoalDecomposer()
    decompose_use_case = DecomposeActivatedGoalsUseCase(
        uow_factory=uow_factory,
        decomposer=decomposer_instance,
    )

    return {
        "resume": resume_use_case,
        "execute": execute_use_case,
        "decompose": decompose_use_case,
        "arbitrator": arbitrator,  # For API access
        "capital_allocator": capital_allocator,  # For API access
    }


# Кэш use-cases (создаём один раз при старте)
_use_cases = None


def _get_use_cases():
    global _use_cases
    if _use_cases is None:
        _use_cases = _create_use_cases()
    return _use_cases


# ============================================================================
# SCHEDULER FUNCTIONS - Теперь только триггерят use-cases
# ============================================================================

async def cognitive_heartbeat():
    thought = await generate_internal_drive()
    if "No active goals" not in thought:
        logger.info("cognitive_heartbeat", thought=thought)
        run_cron_task.delay(f"internal_{uuid.uuid4()}", thought)


async def execute_atomic_goals():
    """
    Выполняет готовые атомарные цели.

    CRITICAL: This function MUST NOT raise exceptions to APScheduler.
    Unhandled exceptions will cause scheduler shutdown and container restart.
    
    Теперь использует Cognitive Arbiter для умного выбора целей.
    """
    from time import time

    try:
        start_time = time()

        # Используем Cognitive Arbiter для умного выбора
        use_cases = _get_use_cases()
        
        # Сначала получим scored goals через arbiter
        arbiter_result = await use_cases["execute"].run(
            actor="scheduler.atomic_executor",
            limit=20
        )

        duration = time() - start_time

        logger.info(
            f"atomic_execution_summary: found={arbiter_result.total_found}, completed={arbiter_result.completed}, failed={arbiter_result.failed}, duration_seconds={duration:.2f}"
        )

    except asyncio.CancelledError:
        # Task was cancelled (e.g., during shutdown)
        # Log but DON'T re-raise - this prevents scheduler crash
        logger.warning(
            "atomic_executor_cancelled: reason=Task cancelled during execution, phase=cleanup"
        )
        # IMPORTANT: Don't re-raise CancelledError!
        # APScheduler will handle this gracefully

    except Exception as e:
        # Catch ALL other exceptions to prevent scheduler shutdown
        logger.exception(
            f"atomic_executor_crash: error_type={type(e).__name__}, error={str(e)[:200]}, phase=exception_handling"
        )
        # Don't re-raise - scheduler continues running


async def run_progress_monitor():
    """
    Progress Monitor - проверяет застрявшие цели.
    
    Запускается каждые 2 минуты.
    """
    from progress_monitor import ProgressMonitorService
    from database import AsyncSessionLocal
    
    service = ProgressMonitorService(AsyncSessionLocal)
    stuck_goals = await service.run_monitoring_cycle()
    
    if stuck_goals:
        logger.info("progress_monitor_stuck_goals", count=len(stuck_goals))


async def run_self_improver():
    """
    Self-Improving Capability System
    
    Автоматически:
    1. Detects capability gaps
    2. Generates new skills
    3. Registers them in system
    
    Запускается каждый час.
    """
    from self_improving_capability import AutoSkillRegistrar
    from database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        registrar = AutoSkillRegistrar(session)
        result = await registrar.auto_improve()
        
        if result['skills_created'] > 0:
            logger.info("self_improvement_complete", result=result)


async def auto_resume_pending_goals():
    """
    Активирует pending цели без детей.
    
    Теперь это просто вызов use-case.
    """
    use_cases = _get_use_cases()
    result = await use_cases["resume"].run(
        actor="scheduler.auto_resume"
    )
    
    logger.info(
        f"resume_summary: found={result.total_found}, activated={result.activated}, skipped={result.skipped}, failed={result.failed}"
    )


async def decompose_non_atomic_goals():
    """
    Декомпозирует активные не-атомарные цели.

    Теперь это просто вызов use-case.
    """
    use_cases = _get_use_cases()
    result = await use_cases["decompose"].run(
        actor="scheduler.decomposer",
        max_goals=5
    )

    logger.info(
        f"decompose_summary: found={result.total_found}, decomposed={result.decomposed}, no_subgoals={result.no_subgoals}, failed={result.failed}"
    )


async def decompose_pending_goals():
    """
    Декомпозирует застрявшие pending не-атомарные цели.

    Это补齐ает пробел: новые цели создаются как 'pending',
    но основной decompose job обрабатывает только 'active'.
    Этот job находит pending цели старше 5 минут и декомпозирует их.

    Runs every 5 minutes.
    """
    try:
        from auto_decomposer import auto_decomposer
        report = await auto_decomposer.scan_and_decompose_stuck_goals()

        logger.info(
            f"pending_decompose_summary: scanned={report['scanned']}, decomposed={report['decomposed']}, skipped={report['skipped']}, failed={report['failed']}"
        )
    except Exception as e:
        logger.error(
            f"pending_decompose_error: error={str(e)[:200]}"
        )


async def run_nightly_invariants_check():
    """
    Проверка всех инвариантов state-machine.
    """
    from invariants_checker import run_invariants_check

    logger.info("nightly_invariants_check_started")

    try:
        result = await run_invariants_check()

        if result["overall_status"] == "PASS":
            logger.info("all_invariants_pass",
                       passed=result['summary']['passed'],
                       total=result['summary']['total_checks'])
        elif result["overall_status"] == "VIOLATION":
            logger.warning("invariants_violation_detected",
                          violations=result['summary']['violations'])

            for check in result['invariant_checks']:
                if check['status'] == 'VIOLATION':
                    logger.error("invariant_violation",
                                invariant=check['invariant'],
                                message=check['message'])
        else:
            logger.error("invariants_check_error", errors=result['summary']['errors'])

    except Exception as e:
        logger.error("invariants_check_exception", error=str(e))


async def cleanup_memory_patterns():
    """
    Очистка старых паттернов с low confidence.
    """
    from semantic_memory import semantic_memory

    logger.info("memory_cleanup_started")

    try:
        deleted = await semantic_memory.cleanup_old_patterns(days=30)
        
        logger.info("memory_cleanup_completed", deleted_count=deleted)
        return {"deleted": deleted}
        
    except Exception as e:
        logger.error("memory_cleanup_error", error=str(e))
        return {"error": str(e)}


async def decay_memory_signals():
    """
    Decay всех MemorySignal.
    """
    from memory_signal import memory_registry, persistent_memory_registry

    logger.info("memory_signal_decay_started")

    try:
        memory_registry.decay_all()
        local_count = len(memory_registry.get_active())
        
        redis_summary = persistent_memory_registry.summary()
        
        logger.info("memory_signal_decay_completed",
                   local_signals=local_count,
                   redis_signals=redis_summary.get("total_signals", 0))
        
        return {"local": local_count, "redis": redis_summary.get("total_signals", 0)}
        
    except Exception as e:
        logger.error("memory_signal_decay_error", error=str(e))
        return {"error": str(e)}


def start_scheduler():
    """
    Регистрация всех jobs.

    Примечание: Имена функций НЕ изменились для обратной совместимости.
    """
    # IMPORTANT: Remove any existing jobs before adding new ones
    if scheduler.running:
        scheduler.shutdown(wait=False)
    
    # Clear all jobs from previous runs
    scheduler.remove_all_jobs()
    
    # Регистрируем event handlers
    _setup_event_handlers()
    _setup_execution_event_handlers()  # Register dependency resolution handlers

    # CRITICAL SETTINGS for all jobs to prevent misfire after container restart
    JOB_CONFIG = {
        'misfire_grace_time': 120,  # Allow 2min delay before skipping
        'coalesce': True,           # Merge missed runs into single execution
    }

    # Cognitive Loop every 10 mins
    scheduler.add_job(
        cognitive_heartbeat,
        'interval',
        minutes=10,
        id='cognitive_heartbeat',
        **JOB_CONFIG
    )

    # Atomic Goals Executor every 90 seconds
    # ← FIX B2: Increased from 30s to 90s to prevent job overlap
    # Batch of 20 goals takes ~2.5 min (20 × 8 sec/goal)
    # 90 sec interval ensures previous batch completes before next run
    scheduler.add_job(
        execute_atomic_goals,
        'interval',
        seconds=90,  # ← Balanced: allows 20-goal batch to complete
        id='atomic_executor',
        max_instances=1,  # Prevent overlapping executions
        **JOB_CONFIG
    )

    # Pending Goals Auto-Resume every 5 mins
    scheduler.add_job(
        auto_resume_pending_goals,
        'interval',
        minutes=5,
        id='auto_resume',
        **JOB_CONFIG
    )

    # Decomposition Scheduler every 10 mins (active goals)
    scheduler.add_job(
        decompose_non_atomic_goals,
        'interval',
        minutes=10,
        id='decompose_executor',
        **JOB_CONFIG
    )

    # Pending Goals Decomposition every 5 mins (catches newly created pending goals)
    scheduler.add_job(
        decompose_pending_goals,
        'interval',
        minutes=5,
        id='decompose_pending',
        **JOB_CONFIG
    )

    # Progress Monitor every 2 minutes
    scheduler.add_job(
        run_progress_monitor,
        'interval',
        minutes=2,
        id='progress_monitor',
        **JOB_CONFIG
    )

    # Self-Improving Capability System every hour
    scheduler.add_job(
        run_self_improver,
        'interval',
        minutes=60,
        id='self_improver',
        **JOB_CONFIG
    )

    # Execution Recovery Scheduler every 1 minute (BUG-001 fix)
    from execution.recovery_scheduler import recover_stuck_executions
    scheduler.add_job(
        recover_stuck_executions,
        'interval',
        minutes=1,
        id='execution_recovery',
        **JOB_CONFIG
    )

    # Invariants check nightly (every 24h at 3 AM)
    scheduler.add_job(
        run_nightly_invariants_check,
        'cron',
        hour=3,
        minute=0,
        id='invariants_check',
        **JOB_CONFIG
    )

    # Memory: Pattern cleanup nightly (every 24h at 4 AM)
    scheduler.add_job(
        cleanup_memory_patterns,
        'cron',
        hour=4,
        minute=0,
        id='memory_cleanup',
        **JOB_CONFIG
    )

    # Memory: Signal decay hourly
    scheduler.add_job(
        decay_memory_signals,
        'interval',
        hours=1,
        id='memory_decay',
        **JOB_CONFIG
    )

    # Skill Evolution: Controlled evolution every 6 hours
    async def run_skill_evolution():
        from controlled_evolution import run_controlled_evolution_cycle
        await run_controlled_evolution_cycle()

    scheduler.add_job(
        run_skill_evolution,
        'interval',
        hours=6,
        id='skill_evolution',
        **JOB_CONFIG
    )

    # Pipeline Evolution: Self-improving pipelines every 10 minutes
    async def run_pipeline_evolution():
        from capability import evolution_worker
        await evolution_worker.run_evolution_cycle()

    scheduler.add_job(
        run_pipeline_evolution,
        'interval',
        minutes=10,
        id='pipeline_evolution',
        **JOB_CONFIG
    )

    # 🔧 FIX: Self-healing watchdog — finds stuck non-atomic goals and triggers decomposition
    async def stuck_goals_watchdog():
        """
        Finds goals stuck in pending/active with 0 progress and auto-decomposes them.
        This is the safety net for goals that somehow avoided auto-decomposition at creation.
        """
        from sqlalchemy import select, and_
        from models import Goal as GoalModel
        from database import AsyncSessionLocal
        from datetime import datetime, timedelta, timezone
        from tasks import decompose_goal_task

        logger.info("watchdog_starting", reason="checking for stuck goals")

        async with AsyncSessionLocal() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            stmt = select(GoalModel).where(
                and_(
                    GoalModel._status.in_(["pending", "active"]),
                    GoalModel.progress == 0,
                    GoalModel.is_atomic == False,
                    GoalModel.created_at < cutoff,
                )
            ).limit(20)
            result = await db.execute(stmt)
            stuck = result.scalars().all()

            decomposed = 0
            for goal in stuck:
                # Check if already has children — skip those
                children_stmt = select(GoalModel).where(GoalModel.parent_id == goal.id).limit(1)
                children_result = await db.execute(children_stmt)
                has_children = children_result.scalar_one_or_none() is not None

                if has_children:
                    continue  # Already decomposed, just stuck for other reasons

                # Trigger decomposition
                decompose_goal_task.delay(str(goal.id))
                decomposed += 1
                age_hours = (datetime.now(timezone.utc) - goal.created_at).total_seconds() / 3600
                logger.info(
                    "watchdog_decomposed",
                    goal_id=str(goal.id),
                    goal_title=goal.title,
                    status=goal._status,
                    age_hours=round(age_hours, 1)
                )

            if decomposed > 0:
                logger.info("watchdog_complete", decomposed=decomposed, total_stuck=len(stuck))

    scheduler.add_job(
        stuck_goals_watchdog,
        'interval',
        minutes=5,
        id='stuck_goals_watchdog',
        **JOB_CONFIG
    )

    scheduler.start()
    logger.info("scheduler_started",
               cognitive_heartbeat="every 10 min",
               atomic_executor="every 30 seconds",  # ← FIX B: Updated
               auto_resume="every 5 min",
               decomposition="every 10 min",
               execution_recovery="every 1 min",
               invariants_check="daily at 3:00 AM",
               memory_cleanup="daily at 4:00 AM",
               memory_decay="hourly",
               skill_evolution="every 6 hours",
               pipeline_evolution="every 10 min")
