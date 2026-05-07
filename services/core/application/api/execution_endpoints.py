"""
Execution Orchestrator API Endpoints v1

HTTP API for submitting and monitoring goal executions through the orchestrator.

Author: Claude (Control Center v3.1)
Date: 2026-03-03
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger
import uuid

logger = get_logger(__name__)

execution_router = APIRouter(prefix="/execution", tags=["Execution Orchestrator"])

# Import orchestrator at runtime to avoid circular imports
from execution.orchestrator import (
    execution_orchestrator,
    retry_circuit_breaker,
    InvalidTransitionError,
    StateMismatchError,
    ConcurrentTransitionError,
    BackpressureRejectedException
)

# ============================================================================
# Request/Response Models
# ============================================================================

class SubmitExecutionRequest(BaseModel):
    """Submit a new goal for execution."""
    goal_id: str

    # Shadow decision metadata
    shadow_model: Optional[str] = None
    actual_model: Optional[str] = None
    is_divergent: bool = False
    shadow_confidence: Optional[float] = None


class ExecutionStatus(BaseModel):
    """Current execution status."""
    trace_id: str
    goal_id: str
    state: str

    # Shadow decision metadata
    shadow_model: Optional[str] = None
    actual_model: Optional[str] = None
    is_divergent: bool = False
    shadow_confidence: Optional[float] = None

    # Timing
    created_at: str
    started_at: Optional[str] = None
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Execution tracking
    attempt: int
    parent_trace_id: Optional[str] = None

    # Failure info
    failure_category: Optional[str] = None

    # Backpressure
    rejected_due_to_backpressure: bool = False


class QueueDepthMetrics(BaseModel):
    """Current execution queue metrics."""
    executing_count: int
    max_concurrent: int
    backpressure_active: bool
    utilization_percent: float


class HealthStatus(BaseModel):
    """Orchestrator health status."""
    status: str  # "healthy", "degraded", "down"
    queue_depth: QueueDepthMetrics
    circuit_breaker_open: bool
    stuck_executions: List[Dict[str, Any]]


class StuckExecutionInfo(BaseModel):
    """Information about stuck execution."""
    trace_id: str
    goal_id: str
    state: str
    started_at: str
    minutes_running: float


# ============================================================================
# Endpoints
# ============================================================================

@execution_router.post("/submit", response_model=ExecutionStatus)
async def submit_execution(request: SubmitExecutionRequest):
    """
    Submit a new goal for execution.

    Flow:
    1. Check backpressure (can we accept new execution?)
    2. Create execution record (INIT state)
    3. Enqueue to worker (side-effect, happens after state persists)
    4. Return trace_id for tracking

    If backpressure is active, returns 503 Service Unavailable.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Check backpressure first
            can_accept = await execution_orchestrator.can_start_execution(session)

            if not can_accept:
                logger.warning("execution_rejected_backpressure", goal_id=request.goal_id)
                raise HTTPException(
                    status_code=503,
                    detail="System at capacity (backpressure active). Retry later."
                )

            # Parse goal_id
            try:
                goal_uuid = uuid.UUID(request.goal_id)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid goal_id format: {request.goal_id}"
                )

            # Create execution (INIT state)
            trace_id = await execution_orchestrator.create_execution(
                session,
                goal_id=goal_uuid,
                shadow_model=request.shadow_model,
                actual_model=request.actual_model,
                is_divergent=request.is_divergent,
                shadow_confidence=request.shadow_confidence
            )

            await session.commit()

            # Fetch and return execution status
            status_query = text("""
                SELECT
                    trace_id, goal_id, state,
                    shadow_model, actual_model, is_divergent, shadow_confidence,
                    created_at, started_at, executed_at, completed_at,
                    attempt, parent_trace_id, failure_category,
                    rejected_due_to_backpressure
                FROM executions
                WHERE trace_id = :trace_id
            """)

            result = await session.execute(status_query, {"trace_id": str(trace_id)})
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=500,
                    detail="Execution created but not found (data race?)"
                )

            logger.info(
                "execution_submitted",
                trace_id=str(trace_id),
                goal_id=request.goal_id,
                shadow_model=request.shadow_model,
                actual_model=request.actual_model
            )

            return ExecutionStatus(
                trace_id=str(row.trace_id),
                goal_id=str(row.goal_id),
                state=row.state,
                shadow_model=row.shadow_model,
                actual_model=row.actual_model,
                is_divergent=row.is_divergent,
                shadow_confidence=row.shadow_confidence,
                created_at=row.created_at.isoformat(),
                started_at=row.started_at.isoformat() if row.started_at else None,
                executed_at=row.executed_at.isoformat() if row.executed_at else None,
                completed_at=row.completed_at.isoformat() if row.completed_at else None,
                attempt=row.attempt,
                parent_trace_id=str(row.parent_trace_id) if row.parent_trace_id else None,
                failure_category=row.failure_category,
                rejected_due_to_backpressure=row.rejected_due_to_backpressure or False
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("submit_execution_failed", goal_id=request.goal_id, error=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Failed to submit execution: {str(e)}"
            )


# IMPORTANT: Specific routes must come BEFORE parameterized routes
# FastAPI matches routes in order, so /health must be before /{trace_id}

@execution_router.get("/health", response_model=HealthStatus)
async def get_health():
    """
    Get orchestrator health status.

    Returns:
    - Overall health status
    - Queue depth metrics
    - Circuit breaker state
    - List of stuck executions (if any)
    """
    async with AsyncSessionLocal() as session:
        # Get queue depth
        queue_query = text("""
            SELECT COUNT(*) as executing_count
            FROM executions
            WHERE state = 'EXECUTING'
        """)
        queue_result = await session.execute(queue_query)
        queue_row = queue_result.fetchone()
        executing_count = queue_row.executing_count or 0

        max_concurrent = 50
        utilization = (executing_count / max_concurrent) * 100 if max_concurrent > 0 else 0

        # Check circuit breaker
        circuit_open = retry_circuit_breaker.circuit_open

        # Check for stuck executions
        stuck = await execution_orchestrator.check_timeout(session, timeout_minutes=30)

        # Determine overall health
        if circuit_open:
            status = "degraded"
        elif utilization > 90:
            status = "degraded"
        elif len(stuck) > 5:
            status = "degraded"
        else:
            status = "healthy"

        return HealthStatus(
            status=status,
            queue_depth=QueueDepthMetrics(
                executing_count=executing_count,
                max_concurrent=max_concurrent,
                backpressure_active=executing_count >= max_concurrent,
                utilization_percent=round(utilization, 1)
            ),
            circuit_breaker_open=circuit_open,
            stuck_executions=stuck
        )


@execution_router.get("/queue-depth", response_model=QueueDepthMetrics)
async def get_queue_depth():
    """
    Get current execution queue metrics.

    Returns:
    - Number of executions in EXECUTING state
    - Maximum concurrent capacity
    - Whether backpressure is active
    - Utilization percentage
    """
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT COUNT(*) as executing_count
            FROM executions
            WHERE state = 'EXECUTING'
        """)

        result = await session.execute(query)
        row = result.fetchone()

        executing_count = row.executing_count or 0
        max_concurrent = 50  # From MAX_CONCURRENT_EXECUTING in orchestrator.py

        return QueueDepthMetrics(
            executing_count=executing_count,
            max_concurrent=max_concurrent,
            backpressure_active=executing_count >= max_concurrent,
            utilization_percent=round((executing_count / max_concurrent) * 100, 1) if max_concurrent > 0 else 0.0
        )


@execution_router.post("/cleanup-expired")
async def cleanup_expired_executions():
    """
    Manually trigger cleanup of expired EXECUTING executions.

    Transitions EXECUTING → TIMEOUT based on execution_timeout_at invariant.
    This is typically called by watchdog scheduler every 30 seconds.

    Returns:
    - Number of executions cleaned
    - List of trace_ids cleaned
    """
    async with AsyncSessionLocal() as session:
        try:
            from execution.orchestrator import execution_orchestrator

            cleaned_count = await execution_orchestrator.cleanup_expired_executions(session)
            await session.commit()

            logger.info(
                "manual_cleanup_triggered",
                cleaned=cleaned_count
            )

            return {
                "status": "success",
                "cleaned": cleaned_count,
                "message": f"Cleaned {cleaned_count} expired executions"
            }

        except Exception as e:
            logger.error("cleanup_failed", error=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Cleanup failed: {str(e)}"
            )


@execution_router.post("/timeout-check", response_model=List[StuckExecutionInfo])
async def check_stuck_executions(
    timeout_minutes: int = Query(30, description="Minutes before considering execution stuck")
):
    """
    Check for executions stuck in EXECUTING state.

    This is typically called by a scheduled job (e.g., every 5 minutes).
    Returns list of executions that have exceeded the timeout.
    """
    async with AsyncSessionLocal() as session:
        stuck = await execution_orchestrator.check_timeout(session, timeout_minutes)

        logger.info(
            "timeout_check_completed",
            timeout_minutes=timeout_minutes,
            stuck_count=len(stuck)
        )

        return [
            StuckExecutionInfo(
                trace_id=s["trace_id"],
                goal_id=s["goal_id"],
                state=s["state"],
                started_at=s["started_at"],
                minutes_running=round(s["minutes_running"], 1)
            )
            for s in stuck
        ]


# Now the parameterized routes (must come after specific routes)

@execution_router.get("/{trace_id}", response_model=ExecutionStatus)
async def get_execution_status(trace_id: str):
    """
    Get current execution status by trace_id.

    Returns full execution record including:
    - Current state
    - Timing information
    - Shadow decision metadata
    - Failure category (if failed)
    """
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT
                trace_id, goal_id, state,
                shadow_model, actual_model, is_divergent, shadow_confidence,
                created_at, started_at, executed_at, completed_at,
                attempt, parent_trace_id, failure_category,
                rejected_due_to_backpressure
            FROM executions
            WHERE trace_id = :trace_id
        """)

        result = await session.execute(query, {"trace_id": trace_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Execution not found: {trace_id}"
            )

        return ExecutionStatus(
            trace_id=str(row.trace_id),
            goal_id=str(row.goal_id),
            state=row.state,
            shadow_model=row.shadow_model,
            actual_model=row.actual_model,
            is_divergent=row.is_divergent,
            shadow_confidence=row.shadow_confidence,
            created_at=row.created_at.isoformat(),
            started_at=row.started_at.isoformat() if row.started_at else None,
            executed_at=row.executed_at.isoformat() if row.executed_at else None,
            completed_at=row.completed_at.isoformat() if row.completed_at else None,
            attempt=row.attempt,
            parent_trace_id=str(row.parent_trace_id) if row.parent_trace_id else None,
            failure_category=row.failure_category,
            rejected_due_to_backpressure=row.rejected_due_to_backpressure or False
        )


@execution_router.get("/by-goal/{goal_id}", response_model=ExecutionStatus)
async def get_execution_by_goal(goal_id: str):
    """
    Get execution status by goal_id.

    Since goal_id is UNIQUE in executions table, this returns the single execution.
    """
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT
                trace_id, goal_id, state,
                shadow_model, actual_model, is_divergent, shadow_confidence,
                created_at, started_at, executed_at, completed_at,
                attempt, parent_trace_id, failure_category,
                rejected_due_to_backpressure
            FROM executions
            WHERE goal_id = :goal_id
        """)

        result = await session.execute(query, {"goal_id": goal_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Execution not found for goal_id: {goal_id}"
            )

        return ExecutionStatus(
            trace_id=str(row.trace_id),
            goal_id=str(row.goal_id),
            state=row.state,
            shadow_model=row.shadow_model,
            actual_model=row.actual_model,
            is_divergent=row.is_divergent,
            shadow_confidence=row.shadow_confidence,
            created_at=row.created_at.isoformat(),
            started_at=row.started_at.isoformat() if row.started_at else None,
            executed_at=row.executed_at.isoformat() if row.executed_at else None,
            completed_at=row.completed_at.isoformat() if row.completed_at else None,
            attempt=row.attempt,
            parent_trace_id=str(row.parent_trace_id) if row.parent_trace_id else None,
            failure_category=row.failure_category,
            rejected_due_to_backpressure=row.rejected_due_to_backpressure or False
        )


@execution_router.post("/transition/{trace_id}")
async def manual_transition(
    trace_id: str,
    to_state: str,
    expected_state: Optional[str] = None
):
    """
    Manually trigger state transition (ADMIN ONLY).

    This is primarily for recovery and testing.
    Most transitions should be automatic via orchestrator.
    """
    async with AsyncSessionLocal() as session:
        try:
            trace_uuid = uuid.UUID(trace_id)

            rows_updated = await execution_orchestrator.transition(
                session,
                trace_uuid,
                to_state,
                expected_state=expected_state
            )

            await session.commit()

            if rows_updated == 0:
                return {
                    "status": "idempotent",
                    "message": "Already in target state",
                    "trace_id": trace_id,
                    "to_state": to_state
                }

            return {
                "status": "success",
                "trace_id": trace_id,
                "from_state": expected_state or "unknown",
                "to_state": to_state,
                "rows_updated": rows_updated
            }

        except InvalidTransitionError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition: {str(e)}"
            )
        except StateMismatchError as e:
            raise HTTPException(
                status_code=409,
                detail=f"State mismatch: {str(e)}"
            )
        except ConcurrentTransitionError as e:
            raise HTTPException(
                status_code=409,
                detail=f"Concurrent modification: {str(e)}"
            )
        except Exception as e:
            logger.error("manual_transition_failed", trace_id=trace_id, error=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Transition failed: {str(e)}"
            )
