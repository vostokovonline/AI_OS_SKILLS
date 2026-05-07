"""
Retry Scheduler for Timed-Out Executions

Separate from cleanup watchdog (Cleanup ≠ Retry).

Responsibilities:
- Create retry executions for TIMEOUT state
- Respect circuit breaker
- Respect backpressure
- Enforce max_attempts limit
- Deduplicate by parent_trace_id
- Apply exponential backoff with jitter

Runs every 1 minute via scheduler.

Author: Claude (Control Center v3.1)
Date: 2026-03-03
"""

import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger
import uuid

logger = get_logger(__name__)

MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY_SECONDS = 10  # 10, 20, 40, 80...
JITTER_PERCENT = 0.20  # ±20% jitter to prevent retry storm
BATCH_SIZE = 10  # Max retries per run


async def retry_timed_out_executions(session) -> int:
    """
    Create retry executions for timed-out executions.

    Separate from cleanup - only creates retries if safe:
    - Circuit breaker is closed
    - Concurrency limit not reached
    - Max attempts not exceeded
    - Not already retried (deduplication by parent_trace_id)

    Returns: Number of retry executions created
    """
    # Import here to avoid circular dependency
    from execution.orchestrator import retry_circuit_breaker, check_backpressure

    # 1. Check circuit breaker FIRST
    can_retry = await retry_circuit_breaker.can_retry(session)
    if not can_retry:
        logger.debug("retry_blocked", reason="circuit_breaker_open")
        return 0

    # 2. Check backpressure
    has_capacity = await check_backpressure(session)
    if not has_capacity:
        logger.debug("retry_blocked", reason="backpressure_active")
        return 0

    # 3. Find candidates ready for retry
    query = text("""
        SELECT
            trace_id, goal_id, attempt, parent_trace_id,
            EXTRACT(EPOCH FROM (NOW() - retry_after)) / 60 as minutes_since_retry_after
        FROM executions
        WHERE
            state = 'TIMEOUT'
            AND retry_after IS NOT NULL
            AND retry_after < NOW()
            AND attempt < :max_attempts
        ORDER BY created_at ASC
        LIMIT :batch_size
    """)

    result = await session.execute(query, {
        "max_attempts": MAX_RETRY_ATTEMPTS,
        "batch_size": BATCH_SIZE
    })
    candidates = result.fetchall()

    if not candidates:
        return 0

    retries_created = 0
    skipped = 0

    for candidate in candidates:
        try:
            # 4. Deduplication check
            dup_check = text("""
                SELECT COUNT(*) as count
                FROM executions
                WHERE
                    parent_trace_id = :parent_trace_id
                    AND state IN ('INIT', 'EXECUTING')
            """)

            dup_result = await session.execute(dup_check, {
                "parent_trace_id": str(candidate.trace_id)
            })
            dup_count = dup_result.scalar()

            if dup_count > 0:
                skipped += 1
                logger.debug(
                    "retry_skipped_duplicate",
                    original_trace_id=str(candidate.trace_id),
                    existing_retries=dup_count
                )
                continue

            # 5. Create retry execution (with unique constraint protection)
            new_trace_id = uuid.uuid4()
            new_attempt = candidate.attempt + 1

            try:
                insert_query = text("""
                    INSERT INTO executions (
                        trace_id, goal_id, state, attempt, parent_trace_id,
                        schema_version, policy_version,
                        created_at, execution_timeout_at
                    ) VALUES (
                        :trace_id, :goal_id, 'INIT', :attempt, :parent_trace_id,
                        1, 1,
                        NOW(), NOW() + INTERVAL '5 minutes'
                    )
                """)

                await session.execute(insert_query, {
                    "trace_id": str(new_trace_id),
                    "goal_id": str(candidate.goal_id),
                    "attempt": new_attempt,
                    "parent_trace_id": str(candidate.trace_id)
                })

            except Exception as e:
                # Unique constraint violation - another scheduler created retry first
                error_msg = str(e).lower()
                if 'uniq_active_retry' in error_msg or 'duplicate key' in error_msg or 'unique constraint' in error_msg:
                    skipped += 1
                    logger.debug(
                        "retry_skipped_duplicate_concurrent",
                        original_trace_id=str(candidate.trace_id),
                        error="another_scheduler_created_retry"
                    )
                    continue
                else:
                    # Some other error - rethrow
                    raise

            # 6. Calculate exponential backoff with jitter
            # 10 * 2^attempt: 10, 20, 40, 80...
            base_delay = BASE_RETRY_DELAY_SECONDS * (2 ** candidate.attempt)

            # Apply ±20% jitter to prevent retry storm
            jitter_factor = random.uniform(1.0 - JITTER_PERCENT, 1.0 + JITTER_PERCENT)
            final_delay = base_delay * jitter_factor

            # Update original execution with retry_after
            # NOTE: Postgres syntax for parameterized INTERVAL: (:param * INTERVAL '1 second')
            update_query = text("""
                UPDATE executions
                SET retry_after = NOW() + (:delay * INTERVAL '1 second')
                WHERE trace_id = :trace_id
            """)

            await session.execute(update_query, {
                "delay": final_delay,
                "trace_id": str(candidate.trace_id)
            })

            retries_created += 1

            logger.info(
                "execution_retried",
                original_trace_id=str(candidate.trace_id),
                new_trace_id=str(new_trace_id),
                attempt=new_attempt,
                delay_seconds=round(final_delay, 2),
                jitter_factor=round(jitter_factor, 3)
            )

        except Exception as e:
            logger.error(
                "retry_failed",
                trace_id=str(candidate.trace_id),
                error=str(e)
            )

    if retries_created > 0:
        logger.info(
            "retry_batch_completed",
            created=retries_created,
            skipped=skipped,
            total_candidates=len(candidates)
        )

    return retries_created


# Singleton for scheduler integration
retry_scheduler = retry_timed_out_executions
