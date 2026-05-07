"""
Execution Orchestrator v1 - Minimal Safe Contract

4-state machine: INIT → EXECUTING → EXECUTED → COMPLETE

Principles:
1. Single-source of truth for state (executions table)
2. Worker writes to execution_results (does NOT touch state)
3. Orchestrator owns state transitions (single-writer)
4. Terminal states are immutable (DB trigger enforced)

Author: Claude (Control Center v3.1)
Date: 2026-03-02
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger
import asyncio
import random
import uuid

logger = get_logger(__name__)

# ============================================================================
# Feature Flags
# ============================================================================

CONTROL_CENTER_ENABLED = os.getenv("CONTROL_CENTER_ENABLED", "false").lower() == "true"

DEFAULT_MODEL = "gpt-4"

# ============================================================================
# Allowed Transitions (State Machine Guard)
# ============================================================================

ALLOWED_TRANSITIONS = {
    'INIT': ['EXECUTING', 'CORRUPTED'],
    'EXECUTING': ['EXECUTED', 'TIMEOUT', 'CORRUPTED'],
    'EXECUTED': ['COMPLETE', 'CORRUPTED'],
    'COMPLETE': [],  # Terminal
    'CORRUPTED': [],  # Terminal
    'TIMEOUT': ['INIT', 'CORRUPTED']  # Can retry via scheduler or mark corrupted
}

# ============================================================================
# Circuit Breaker Configuration
# ============================================================================

class RetryCircuitBreaker:
    """
    Circuit breaker to prevent retry storm.

    Opens if retry rate exceeds threshold (with min sample size).
    """

    def __init__(
        self,
        threshold: float = 0.15,  # 15% retry rate triggers breaker
        min_sample_size: int = 50,  # Minimum executions before checking
        cooldown_seconds: int = 300  # Stay open for 5 minutes
    ):
        self.threshold = threshold
        self.min_sample_size = min_sample_size
        self.cooldown_seconds = cooldown_seconds
        self.circuit_open = False
        self.opened_at = None

    async def can_retry(self, session) -> bool:
        """Check if retries are allowed (circuit breaker check)."""

        # If circuit is open, check if cooldown expired
        if self.circuit_open:
            if datetime.now(timezone.utc) >= self.opened_at + timedelta(seconds=self.cooldown_seconds):
                # Cooldown expired - close circuit
                logger.info("retry_circuit_closed_after_cooldown")
                self.circuit_open = False
                self.opened_at = None
            else:
                # Still in cooldown
                logger.warning("retry_circuit_open", cooldown_remaining=self.cooldown_seconds - (datetime.now(timezone.utc) - self.opened_at).total_seconds())
                return False

        # Check retry rate (only if we have enough samples)
        query = text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE attempt > 1) as retries
            FROM executions
            WHERE created_at > NOW() - INTERVAL '5 minutes'
        """)

        result = await session.execute(query)
        row = result.fetchone()

        total = row.total or 0
        retries = row.retries or 0

        if total < self.min_sample_size:
            # Not enough data yet
            return True

        retry_rate = retries / total if total > 0 else 0

        if retry_rate > self.threshold:
            self.circuit_open = True
            self.opened_at = datetime.now(timezone.utc)
            logger.critical(
                "retry_circuit_opened",
                retry_rate=retry_rate,
                threshold=self.threshold,
                total=total
            )
            return False

        return True

    async def record_retry(self):
        """Record that a retry happened (for metrics)."""
        logger.warning("execution_retry_recorded")
        # Metrics would be recorded here

# Global circuit breaker instance
retry_circuit_breaker = RetryCircuitBreaker()

# ============================================================================
# Backpressure Configuration
# ============================================================================

MAX_CONCURRENT_EXECUTING = 50  # Max executions in EXECUTING state

async def check_backpressure(session) -> bool:
    """
    Check if system can accept new execution.

    Returns True if can accept, False if backpressure active.
    """
    query = text("""
        SELECT COUNT(*) as executing_count
        FROM executions
        WHERE state = 'EXECUTING'
    """)

    result = await session.execute(query)
    row = result.fetchone()

    executing_count = row.executing_count or 0

    if executing_count >= MAX_CONCURRENT_EXECUTING:
        logger.warning(
            "backpressure_active",
            executing=executing_count,
            max_allowed=MAX_CONCURRENT_EXECUTING
        )
        # TODO: Emit metric
        return False

    return True

# ============================================================================
# Execution Orchestrator
# ============================================================================

class ExecutionOrchestrator:
    """
    Minimal Safe Orchestrator - Single-node state machine owner.

    Responsibilities:
    - Own state machine (4-state: INIT → EXECUTING → EXECUTED → COMPLETE)
    - Enforce transition guards
    - Publish events (observability only)
    - Check backpressure
    - Record metrics

    NOT responsible for:
    - Complex recovery (manual fix for now)
    - Replay (future feature)
    """

    ALLOWED_TRANSITIONS = ALLOWED_TRANSITIONS

    def __init__(self):
        self.running = True

    async def create_execution(
        self,
        session,
        goal_id: uuid.UUID,
        shadow_model: Optional[str] = None,
        actual_model: Optional[str] = None,
        is_divergent: bool = False,
        shadow_confidence: Optional[float] = None,
        attempt: int = 1
    ) -> uuid.UUID:
        """
        Create new execution (INIT state).

        For first execution (attempt=1): Idempotent - returns existing trace_id if goal already has attempt=1.
        For retries (attempt>1): Always creates new execution.

        Args:
            goal_id: Goal to execute
            shadow_model: Shadow model decision
            actual_model: Actual model to use
            is_divergent: Whether shadow decision was divergent
            shadow_confidence: Shadow model confidence
            attempt: Attempt number (1 for first execution, 2+ for retries)

        Returns: trace_id
        """
        trace_id = uuid.uuid4()

        # For first execution, check if already exists (idempotency)
        if attempt == 1:
            # Check if goal already has an attempt=1 execution
            check_query = text("""
                SELECT trace_id, state FROM executions
                WHERE goal_id = :goal_id AND attempt = 1
                LIMIT 1
            """)
            result = await session.execute(check_query, {"goal_id": str(goal_id)})
            existing = result.fetchone()

            if existing:
                logger.info("first_execution_already_exists", goal_id=str(goal_id), trace_id=str(existing.trace_id), state=existing.state)
                return existing.trace_id

        # Create new execution
        insert_query = text("""
            INSERT INTO executions (
                trace_id, goal_id, state, attempt, schema_version, policy_version,
                shadow_model, actual_model, is_divergent, shadow_confidence,
                created_at
            ) VALUES (
                :trace_id, :goal_id, 'INIT', :attempt, 1, 1,
                :shadow_model, :actual_model, :is_divergent, :shadow_confidence,
                NOW()
            )
            RETURNING trace_id, state, created_at
        """)

        result = await session.execute(insert_query, {
            "trace_id": trace_id,
            "goal_id": str(goal_id),
            "attempt": attempt,
            "shadow_model": shadow_model,
            "actual_model": actual_model,
            "is_divergent": is_divergent,
            "shadow_confidence": shadow_confidence
        })

        row = result.fetchone()

        logger.info(
            "execution_created",
            trace_id=str(trace_id),
            goal_id=str(goal_id),
            attempt=attempt,
            shadow_model=shadow_model,
            actual_model=actual_model,
            is_divergent=is_divergent
        )

        return trace_id

    async def transition(
        self,
        session,
        trace_id: uuid.UUID,
        to_state: str,
        expected_state: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Atomic guarded state transition.

        Args:
            trace_id: Execution trace ID
            to_state: Target state
            expected_state: Optional expected current state (for guard)
            **kwargs: Additional fields to update

        Returns:
            Number of rows updated (0 = race condition or idempotent)

        Raises:
            InvalidTransitionError: If transition not allowed
            StateMismatchError: If expected_state doesn't match
        """
        # Get current state
        current_query = text("""
            SELECT state, policy_version FROM executions WHERE trace_id = :trace_id
        """)
        result = await session.execute(current_query, {"trace_id": str(trace_id)})
        current_row = result.fetchone()

        if current_row is None:
            raise ValueError(f"Execution not found: {trace_id}")

        current_state = current_row.state

        # Validate transition is allowed
        if to_state not in self.ALLOWED_TRANSITIONS.get(current_state, []):
            logger.error(
                "invalid_transition_attempted",
                trace_id=str(trace_id),
                from_state=current_state,
                to_state=to_state,
                allowed=self.ALLOWED_TRANSITIONS.get(current_state, [])
            )
            raise InvalidTransitionError(
                f"Invalid transition {current_state} → {to_state}. "
                f"Allowed: {self.ALLOWED_TRANSITIONS.get(current_state, [])}"
            )

        # Check expected state if specified
        if expected_state and current_state != expected_state:
            logger.warning(
                "state_mismatch",
                trace_id=str(trace_id),
                expected=expected_state,
                actual=current_state
            )
            raise StateMismatchError(
                f"Expected state {expected_state}, got {current_state}"
            )

        # Build SET clause dynamically
        set_clauses = []
        params = {
            "trace_id": str(trace_id),
            "to_state": to_state,
            "current_state": current_state
        }

        for key, value in kwargs.items():
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

        set_clause = ", ".join(set_clauses) if set_clauses else ""

        # Perform guarded UPDATE (concurrency-safe)
        update_query = text(f"""
            UPDATE executions
            SET
                state = :to_state,
                updated_at = NOW()
                {', ' + set_clause if set_clause else ''}
            WHERE
                trace_id = :trace_id
                AND state = :current_state
            RETURNING trace_id, state, updated_at
        """)

        time_before = datetime.now(timezone.utc)

        result = await session.execute(update_query, params)

        time_after = datetime.now(timezone.utc)
        latency_ms = (time_after - time_before).total_seconds() * 1000

        rowcount = result.rowcount

        if rowcount == 0:
            # Race condition - check if already in target state
            if current_state == to_state:
                logger.info(
                    "transition_idempotent",
                    trace_id=str(trace_id),
                    state=to_state
                )
                return 0
            else:
                logger.error(
                    "concurrent_transition_detected",
                    trace_id=str(trace_id),
                    expected=current_state,
                    to_state=to_state
                )
                raise ConcurrentTransitionError(
                    f"Concurrent transition detected for trace_id={trace_id}"
                )

        logger.info(
            "execution_transition",
            trace_id=str(trace_id),
            from_state=current_state,
            to_state=to_state,
            latency_ms=f"{latency_ms:.2f}",
            attempt=kwargs.get('attempt', 1),
            policy_version=current_row.policy_version
        )

        # TODO: Emit metric (transition_latency_ms)

        return rowcount

    async def check_timeout(
        self,
        session,
        timeout_minutes: int = 30
    ) -> List[Dict]:
        """
        Find executions stuck in EXECUTING state.

        Returns: List of stuck executions
        """
        query = text("""
            SELECT
                trace_id, goal_id, state, started_at,
                EXTRACT(EPOCH FROM (NOW() - started_at)) / 60 as minutes_running
            FROM executions
            WHERE
                state = 'EXECUTING'
                AND started_at < NOW() - (INTERVAL '1 minute' * :timeout_minutes)
            ORDER BY started_at ASC
        """)

        result = await session.execute(query, {"timeout_minutes": timeout_minutes})
        rows = result.fetchall()

        stuck = [
            {
                "trace_id": str(row.trace_id),
                "goal_id": str(row.goal_id),
                "state": row.state,
                "started_at": row.started_at.isoformat(),
                "minutes_running": float(row.minutes_running)
            }
            for row in rows
        ]

        if stuck:
            logger.warning(
                "stuck_executions_found",
                count=len(stuck),
                timeout_minutes=timeout_minutes
            )

        return stuck

    async def can_start_execution(self, session) -> bool:
        """
        Check if system can accept new execution (backpressure).

        Returns: True if can accept, False if backpressure active
        """
        return await check_backpressure(session)

    async def cleanup_expired_executions(self, session) -> int:
        """
        Atomic, idempotent cleanup of expired EXECUTING executions.

        Transitions EXECUTING → TIMEOUT based on execution_timeout_at invariant.
        Sets retry_after for retry scheduler (separate responsibility).
        Does NOT create retry executions directly.

        This is safe to run multiple times concurrently (guarded UPDATE).

        Returns: Number of executions cleaned
        """
        import random

        update_query = text("""
            UPDATE executions
            SET
                state = 'TIMEOUT',
                failure_category = 'WORKER_TIMEOUT',
                updated_at = NOW(),
                executed_at = NOW(),
                retry_after = NOW() + INTERVAL '10 seconds'
            WHERE
                state = 'EXECUTING'
                AND execution_timeout_at < NOW()
            RETURNING trace_id, goal_id, attempt
        """)

        result = await session.execute(update_query)
        cleaned = result.fetchall()

        if cleaned:
            logger.critical(
                "executions_timed_out",
                count=len(cleaned),
                trace_ids=[str(row.trace_id) for row in cleaned],
                attempts=[row.attempt for row in cleaned]
            )

        return len(cleaned)


# ============================================================================
# Exceptions
# ============================================================================

class InvalidTransitionError(Exception):
    """Transition not allowed by state machine."""
    pass

class StateMismatchError(Exception):
    """Expected state doesn't match actual state."""
    pass

class ConcurrentTransitionError(Exception):
    """Concurrent transition detected (race condition)."""
    pass

class BackpressureRejectedException(Exception):
    """Execution rejected due to backpressure."""
    pass


# ============================================================================
# Singleton instance
# ============================================================================

execution_orchestrator = ExecutionOrchestrator()
