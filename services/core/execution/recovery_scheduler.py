"""
Execution Recovery Scheduler

Background task that detects and recovers stuck executions.

Author: Claude (Control Center v3.1)
Date: 2026-03-03
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


class ExecutionRecoveryScheduler:
    """
    Detects and recovers stuck executions.

    Stuck execution definition:
    - state = 'EXECUTING'
    - started_at < NOW() - timeout_seconds
    - executed_at = NULL
    """

    def __init__(
        self,
        timeout_seconds: int = 300,  # 5 minutes default
        check_interval_seconds: int = 60  # 1 minute
    ):
        self.timeout_seconds = timeout_seconds
        self.check_interval_seconds = check_interval_seconds

    async def recover_stuck_executions(self) -> Dict[str, Any]:
        """
        Main recovery function - called by scheduler every minute.

        Returns:
            Dict with recovery statistics
        """
        try:
            async with AsyncSessionLocal() as session:
                # Find stuck executions
                stuck_executions = await self._find_stuck_executions(session)

                if not stuck_executions:
                    return {
                        "recovered": 0,
                        "failed": 0,
                        "details": "No stuck executions found"
                    }

                logger.warning(
                    "stuck_executions_detected",
                    count=len(stuck_executions),
                    timeout_seconds=self.timeout_seconds
                )

                recovered = 0
                failed = 0

                for execution in stuck_executions:
                    try:
                        await self._recover_single_execution(session, execution)
                        recovered += 1
                    except Exception as e:
                        logger.error(
                            "recovery_failed",
                            trace_id=str(execution['trace_id']),
                            error=str(e)
                        )
                        failed += 1

                await session.commit()

                logger.info(
                    "recovery_completed",
                    recovered=recovered,
                    failed=failed,
                    total=len(stuck_executions)
                )

                return {
                    "recovered": recovered,
                    "failed": failed,
                    "total": len(stuck_executions)
                }

        except Exception as e:
            logger.error("recovery_scheduler_error", error=str(e))
            return {
                "recovered": 0,
                "failed": 0,
                "error": str(e)
            }

    async def _find_stuck_executions(self, session) -> List[Dict[str, Any]]:
        """Find all stuck executions in database."""
        # Use multiplication instead of INTERVAL parameter binding
        query = text("""
            SELECT
                trace_id,
                goal_id,
                started_at,
                EXTRACT(EPOCH FROM (NOW() - started_at)) as stuck_duration_seconds
            FROM executions
            WHERE state = 'EXECUTING'
              AND started_at < NOW() - (INTERVAL '1 second' * :timeout)
              AND executed_at IS NULL
            ORDER BY started_at ASC
        """)

        result = await session.execute(query, {"timeout": self.timeout_seconds})

        executions = []
        for row in result:
            executions.append({
                "trace_id": row.trace_id,
                "goal_id": row.goal_id,
                "started_at": row.started_at,
                "stuck_duration_seconds": int(row.stuck_duration_seconds)
            })

        return executions

    async def _recover_single_execution(self, session, execution: Dict[str, Any]) -> None:
        """
        Recover a single stuck execution.

        Strategy:
        1. Transition EXECUTING → CORRUPTED
        2. Record error in execution_results
        3. Log recovery event
        """
        from execution.orchestrator import execution_orchestrator
        from execution.goal_execution_integration import goal_execution_integration
        import uuid

        trace_id = execution['trace_id']
        goal_id = execution['goal_id']
        stuck_duration = execution['stuck_duration_seconds']

        logger.warning(
            "recovering_stuck_execution",
            trace_id=str(trace_id),
            goal_id=str(goal_id),
            stuck_duration_seconds=stuck_duration
        )

        # Step 1: Transition to CORRUPTED
        await execution_orchestrator.transition(
            session,
            trace_id=trace_id,
            to_state="CORRUPTED",
            expected_state="EXECUTING",
            failure_category="TIMEOUT",
            executed_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )

        # Step 2: Record error outcome
        await goal_execution_integration._store_error(
            session,
            trace_id=trace_id,
            error_message=(
                f"Execution stuck for {stuck_duration}s "
                f"(timeout: {self.timeout_seconds}s)"
            ),
            failure_category="TIMEOUT"
        )

        logger.info(
            "execution_recovered",
            trace_id=str(trace_id),
            goal_id=str(goal_id),
            new_state="CORRUPTED"
        )

    async def get_stuck_executions_count(self, timeout_minutes: int = 5) -> int:
        """
        Get count of stuck executions for monitoring.

        Args:
            timeout_minutes: Custom timeout for query (default: 5)

        Returns:
            Number of stuck executions
        """
        async with AsyncSessionLocal() as session:
            # Use multiplication instead of INTERVAL parameter binding
            query = text("""
                SELECT COUNT(*) as count
                FROM executions
                WHERE state = 'EXECUTING'
                  AND started_at < NOW() - (INTERVAL '1 minute' * :timeout_minutes)
                  AND executed_at IS NULL
            """)

            result = await session.execute(query, {"timeout_minutes": timeout_minutes})
            return result.scalar() or 0

    async def list_stuck_executions(
        self,
        timeout_minutes: int = 5,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List all stuck executions (for admin API).

        Args:
            timeout_minutes: Custom timeout (default: 5)
            limit: Max results (default: 100)

        Returns:
            List of stuck execution details
        """
        async with AsyncSessionLocal() as session:
            # Use multiplication instead of INTERVAL parameter binding
            query = text("""
                SELECT
                    trace_id,
                    goal_id,
                    started_at,
                    created_at,
                    attempt,
                    EXTRACT(EPOCH FROM (NOW() - started_at))/60 as stuck_minutes
                FROM executions
                WHERE state = 'EXECUTING'
                  AND started_at < NOW() - (INTERVAL '1 minute' * :timeout_minutes)
                  AND executed_at IS NULL
                ORDER BY started_at ASC
                LIMIT :limit
            """)

            result = await session.execute(query, {
                "timeout_minutes": timeout_minutes,
                "limit": limit
            })

            executions = []
            for row in result:
                executions.append({
                    "trace_id": str(row.trace_id),
                    "goal_id": str(row.goal_id),
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "attempt": row.attempt,
                    "stuck_minutes": round(float(row.stuck_minutes), 2) if row.stuck_minutes else 0
                })

            return executions


# Global instance (configured in production)
execution_recovery_scheduler = ExecutionRecoveryScheduler(
    timeout_seconds=300,  # 5 minutes
    check_interval_seconds=60  # 1 minute
)


# Scheduler function (called by APScheduler)
async def recover_stuck_executions():
    """
    Scheduled job function.

    Add to scheduler.py:
        scheduler.add_job(
            recover_stuck_executions,
            'interval',
            minutes=1,
            id='execution_recovery'
        )
    """
    result = await execution_recovery_scheduler.recover_stuck_executions()

    if result.get("recovered", 0) > 0:
        logger.info(
            "execution_recovery_job_completed",
            **result
        )
