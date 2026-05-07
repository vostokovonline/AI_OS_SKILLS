"""
Admin API Endpoints for Execution Recovery

Provides manual recovery capabilities for stuck executions.

Author: Claude (Control Center v3.1)
Date: 2026-03-03
BUG-002 fix
"""

from fastapi import APIRouter, HTTPException, Header, Query
from sqlalchemy import text
from typing import Optional, List
from database import AsyncSessionLocal
from logging_config import get_logger
import uuid

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# Authentication helpers
# ============================================================================

async def verify_admin_permission(admin_user: str) -> bool:
    """
    Verify admin permissions.

    TODO: Implement proper authentication/authorization.

    For now, just check that header is present and not empty.
    """
    if not admin_user or admin_user.strip() == "":
        return False
    return True


# ============================================================================
# Execution Recovery Endpoints
# ============================================================================

@router.post("/executions/{trace_id}/force-corrupted")
async def force_corrupted(
    trace_id: str,
    reason: str = Query(..., description="Reason for manual intervention"),
    x_admin_user: str = Header(..., alias="X-Admin-User", description="Admin username")
):
    """
    Manually mark execution as CORRUPTED (admin only).

    Use this endpoint to manually recover stuck executions when automatic
    recovery is not working or for immediate intervention.

    Args:
        trace_id: Execution trace ID
        reason: Reason for manual intervention
        x_admin_user: Admin username (required header)

    Returns:
        Dict with status and trace_id
    """
    # Verify admin permissions
    if not await verify_admin_permission(x_admin_user):
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Provide X-Admin-User header."
        )

    try:
        from execution.orchestrator import execution_orchestrator
        from execution.goal_execution_integration import goal_execution_integration
        from datetime import datetime

        async with AsyncSessionLocal() as session:
            # Log audit event
            logger.warning(
                "manual_intervention",
                trace_id=trace_id,
                admin=x_admin_user,
                reason=reason,
                action="force_corrupted"
            )

            # Parse trace_id
            try:
                trace_uuid = uuid.UUID(trace_id)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid trace_id format: {trace_id}"
                )

            # Get current state
            state_query = text("""
                SELECT state, goal_id
                FROM executions
                WHERE trace_id = :trace_id
            """)
            result = await session.execute(state_query, {"trace_id": str(trace_uuid)})
            current = result.fetchone()

            if not current:
                raise HTTPException(
                    status_code=404,
                    detail=f"Execution not found: {trace_id}"
                )

            current_state = current[0]
            goal_id = str(current[1])

            # Transition to CORRUPTED (allow from any state)
            await execution_orchestrator.transition(
                session,
                trace_id=trace_uuid,
                to_state="CORRUPTED",
                expected_state=None,  # Override state machine
                failure_category="SYSTEM_ERROR",  # Valid category
                executed_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )

            # Record error outcome
            await goal_execution_integration._store_error(
                session,
                trace_id=trace_uuid,
                error_message=f"Manual intervention by {x_admin_user}: {reason}",
                failure_category="SYSTEM_ERROR"
            )

            await session.commit()

            logger.info(
                "execution_force_corrupted",
                trace_id=trace_id,
                goal_id=goal_id,
                previous_state=current_state,
                admin=x_admin_user
            )

            return {
                "status": "corrupted",
                "trace_id": trace_id,
                "goal_id": goal_id,
                "previous_state": current_state,
                "new_state": "CORRUPTED",
                "failure_category": "SYSTEM_ERROR",
                "admin": x_admin_user,
                "reason": reason
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "force_corrupted_failed",
            trace_id=trace_id,
            admin=x_admin_user,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to force corrupt execution: {str(e)}"
        )


@router.post("/executions/{trace_id}/retry")
async def retry_execution(
    trace_id: str,
    x_admin_user: str = Header(..., alias="X-Admin-User", description="Admin username")
):
    """
    Retry failed/corrupted execution (admin only).

    Creates a new execution with attempt + 1.

    Args:
        trace_id: Original execution trace ID
        x_admin_user: Admin username (required header)

    Returns:
        Dict with original and new trace IDs
    """
    # Verify admin permissions
    if not await verify_admin_permission(x_admin_user):
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Provide X-Admin-User header."
        )

    try:
        from execution.orchestrator import execution_orchestrator

        async with AsyncSessionLocal() as session:
            # Get original execution
            query = text("""
                SELECT trace_id, goal_id, attempt, state
                FROM executions
                WHERE trace_id = :trace_id
            """)
            result = await session.execute(query, {"trace_id": trace_id})
            execution = result.fetchone()

            if not execution:
                raise HTTPException(
                    status_code=404,
                    detail=f"Execution not found: {trace_id}"
                )

            original_trace_id = execution[0]
            goal_id = execution[1]
            attempt = execution[2]
            state = execution[3]

            # Only allow retry from terminal states
            if state not in ["CORRUPTED", "FAILED", "COMPLETE", "TIMEOUT"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot retry from state: {state}. Must be terminal state."
                )

            # Create new execution with incremented attempt
            new_trace_id = await execution_orchestrator.create_execution(
                session,
                goal_id=goal_id,
                attempt=attempt + 1,
                is_retry=True
            )

            await session.commit()

            logger.info(
                "execution_retried",
                original_trace_id=str(original_trace_id),
                new_trace_id=str(new_trace_id),
                goal_id=str(goal_id),
                attempt=attempt + 1,
                admin=x_admin_user
            )

            return {
                "status": "retried",
                "original_trace_id": str(original_trace_id),
                "new_trace_id": str(new_trace_id),
                "goal_id": str(goal_id),
                "attempt": attempt + 1,
                "admin": x_admin_user
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "retry_execution_failed",
            trace_id=trace_id,
            admin=x_admin_user,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry execution: {str(e)}"
        )


@router.get("/executions/stuck")
async def list_stuck_executions(
    timeout_minutes: int = Query(5, ge=1, le=60, description="Timeout in minutes"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    x_admin_user: str = Header(..., alias="X-Admin-User", description="Admin username")
):
    """
    List all stuck executions (admin only).

    Stuck execution definition:
    - state = 'EXECUTING'
    - started_at < NOW() - timeout_minutes
    - executed_at = NULL

    Args:
        timeout_minutes: Custom timeout (default: 5)
        limit: Max results (default: 100)
        x_admin_user: Admin username (required header)

    Returns:
        Dict with count and list of stuck executions
    """
    # Verify admin permissions
    if not await verify_admin_permission(x_admin_user):
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Provide X-Admin-User header."
        )

    try:
        from execution.recovery_scheduler import execution_recovery_scheduler

        stuck_executions = await execution_recovery_scheduler.list_stuck_executions(
            timeout_minutes=timeout_minutes,
            limit=limit
        )

        logger.info(
            "stuck_executions_listed",
            admin=x_admin_user,
            timeout_minutes=timeout_minutes,
            count=len(stuck_executions)
        )

        return {
            "stuck_count": len(stuck_executions),
            "timeout_minutes": timeout_minutes,
            "stuck_executions": stuck_executions
        }

    except Exception as e:
        logger.error(
            "list_stuck_executions_failed",
            admin=x_admin_user,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list stuck executions: {str(e)}"
        )


@router.get("/executions/metrics")
async def get_execution_metrics(
    x_admin_user: str = Header(..., alias="X-Admin-User", description="Admin username")
):
    """
    Get execution metrics for monitoring (admin only).

    Returns:
        Dict with various execution metrics
    """
    # Verify admin permissions
    if not await verify_admin_permission(x_admin_user):
        raise HTTPException(
            status_code=403,
            detail="Admin access required. Provide X-Admin-User header."
        )

    try:
        from execution.recovery_scheduler import execution_recovery_scheduler

        async with AsyncSessionLocal() as session:
            # Get overall stats
            stats_query = text("""
                SELECT
                    state,
                    COUNT(*) as count
                FROM executions
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY state
                ORDER BY count DESC
            """)
            result = await session.execute(stats_query)
            by_state = {row[0]: row[1] for row in result}

            # Get stuck count
            stuck_count = await execution_recovery_scheduler.get_stuck_executions_count(
                timeout_minutes=5
            )

            logger.info(
                "execution_metrics_requested",
                admin=x_admin_user,
                by_state=by_state,
                stuck_count=stuck_count
            )

            return {
                "last_24_hours": {
                    "by_state": by_state,
                    "total": sum(by_state.values())
                },
                "stuck_executions": {
                    "count_5min": stuck_count,
                    "timeout_minutes": 5
                },
                "recovery_status": {
                    "scheduler_enabled": True,
                    "timeout_seconds": 300,
                    "check_interval_seconds": 60
                }
            }

    except Exception as e:
        logger.error(
            "get_execution_metrics_failed",
            admin=x_admin_user,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/health/recovery")
async def get_recovery_health():
    """
    Health check endpoint for recovery system (no auth required).

    Returns:
        Dict with recovery system health status
    """
    try:
        from execution.recovery_scheduler import execution_recovery_scheduler

        stuck_count = await execution_recovery_scheduler.get_stuck_executions_count(
            timeout_minutes=5
        )

        # Determine health status
        if stuck_count == 0:
            status = "healthy"
        elif stuck_count < 5:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "stuck_executions_5min": stuck_count,
            "recovery_scheduler": {
                "enabled": True,
                "timeout_seconds": 300,
                "check_interval_seconds": 60
            }
        }

    except Exception as e:
        logger.error("recovery_health_check_failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "recovery_scheduler": {
                "enabled": False
            }
        }
