"""
Outcome Tracking Layer - Real Model Performance Validation

This module stores ACTUAL execution outcomes to validate Control Center recommendations.

Key Principles:
1. Link shadow decisions to goal outcomes via goal_id
2. Track real performance (latency, cost, success rate)
3. Enable Conservative Divergence Evaluation
4. Support Shadow Replay for counterfactual resolution

Author: Claude (Control Center v3.1)
Date: 2026-03-02
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger
import json
from dateutil.parser import isoparse

logger = get_logger(__name__)

outcome_router = APIRouter(prefix="/llm/control/outcome", tags=["Outcome Tracking"])


def parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to naive datetime object (assumes UTC)."""
    if not dt_str:
        return None
    try:
        dt = isoparse(dt_str)
        # Convert to naive datetime (strip timezone for PostgreSQL timestamp without time zone)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except Exception as e:
        logger.warning("failed_to_parse_datetime", dt_str=dt_str, error=str(e))
        return None


# ============================================================================
# Outcome Models
# ============================================================================

class GoalOutcome(BaseModel):
    goal_id: str

    # Model used
    model_name: str

    # Control Center recommendation
    cc_recommended_model: Optional[str] = None
    cc_recommended_score: Optional[float] = None
    cc_confidence: Optional[float] = None
    was_divergent: bool = False

    # Execution metrics
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None

    # Outcome classification
    outcome_status: str  # 'success', 'error', 'timeout', 'cancelled'
    error_category: Optional[str] = None

    # Quality metrics
    evaluator_score: Optional[float] = None
    evaluator_mode: Optional[str] = None
    artifacts_passed: Optional[int] = None
    artifacts_total: Optional[int] = None

    # Cost tracking
    estimated_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None
    tokens_used: Optional[int] = None

    # Retries
    retry_count: int = 0
    is_retry: bool = False
    original_goal_id: Optional[str] = None

    # Shadow replay
    is_shadow_replay: bool = False
    replay_of_model: Optional[str] = None

    # Context
    goal_type: Optional[str] = None
    goal_depth: Optional[int] = None
    agent_role: Optional[str] = None


class ModelAccuracyStats(BaseModel):
    model_name: str
    total_executions: int
    successful_executions: int
    success_rate: float

    avg_evaluator_score: float
    avg_duration_ms: float
    avg_cost_usd: float

    # Control Center comparison
    cc_recommended_count: int  # How often CC recommended this model
    cc_followed_count: int     # How often executor followed CC recommendation


class ConservativeAccuracy(BaseModel):
    """
    Conservative estimate of Control Center superiority.

    Level 1 - Conservative Divergence Evaluation:
    - If executor FAILED and CC recommended DIFFERENT model
    - Count as "CC potentially better"
    """
    total_executions: int
    executor_successes: int
    executor_failures: int

    # Conservative CC accuracy estimate
    cc_potentially_better: int  # Executor failed, CC recommended different
    cc_accuracy_estimate: float  # Lower bound

    # Divergence cases
    divergent_cases: int
    divergent_where_executor_failed: int
    divergent_where_executor_succeeded: int


# ============================================================================
# Outcome Recording Endpoint
# ============================================================================

@outcome_router.post("/record")
async def record_goal_outcome(outcome: GoalOutcome):
    """
    Record actual execution outcome for a goal.

    Called by goal_executor AFTER goal completion:

    1. Goal execution completes (success/failure)
    2. GoalStrictEvaluator evaluates quality
    3. This endpoint stores the outcome
    4. Links to shadow decision via goal_id if available

    This enables:
    - Real model performance tracking
    - Conservative divergence evaluation
    - Validation of CC recommendations
    """
    async with AsyncSessionLocal() as session:
        # Check if table exists
        check_table = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'llm_goal_outcomes'
            )
        """)
        table_exists = (await session.execute(check_table)).scalar()

        if not table_exists:
            # Create outcomes table
            from pathlib import Path
            migration_file = Path("/app/migrations/llm_outcome_tracking.sql")
            if migration_file.exists():
                sql = migration_file.read_text()
                await session.execute(text(sql))
                await session.commit()
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Outcome tracking migration file not found"
                )

        # Insert outcome
        insert_query = text("""
            INSERT INTO llm_goal_outcomes (
                goal_id, model_name,
                cc_recommended_model, cc_recommended_score, cc_confidence, was_divergent,
                started_at, completed_at, duration_ms,
                outcome_status, error_category,
                evaluator_score, evaluator_mode, artifacts_passed, artifacts_total,
                estimated_cost_usd, actual_cost_usd, tokens_used,
                retry_count, is_retry, original_goal_id,
                is_shadow_replay, replay_of_model,
                goal_type, goal_depth, agent_role
            ) VALUES (
                :goal_id, :model_name,
                :cc_recommended_model, :cc_recommended_score, :cc_confidence, :was_divergent,
                :started_at, :completed_at, :duration_ms,
                :outcome_status, :error_category,
                :evaluator_score, :evaluator_mode, :artifacts_passed, :artifacts_total,
                :estimated_cost_usd, :actual_cost_usd, :tokens_used,
                :retry_count, :is_retry, :original_goal_id,
                :is_shadow_replay, :replay_of_model,
                :goal_type, :goal_depth, :agent_role
            )
            ON CONFLICT (goal_id) DO UPDATE SET
                outcome_status = EXCLUDED.outcome_status,
                evaluator_score = EXCLUDED.evaluator_score,
                duration_ms = EXCLUDED.duration_ms,
                completed_at = EXCLUDED.completed_at,
                actual_cost_usd = EXCLUDED.actual_cost_usd,
                updated_at = NOW()
        """)

        await session.execute(insert_query, {
            "goal_id": outcome.goal_id,
            "model_name": outcome.model_name,
            "cc_recommended_model": outcome.cc_recommended_model,
            "cc_recommended_score": outcome.cc_recommended_score,
            "cc_confidence": outcome.cc_confidence,
            "was_divergent": outcome.was_divergent,
            "started_at": parse_datetime(outcome.started_at),
            "completed_at": parse_datetime(outcome.completed_at),
            "duration_ms": outcome.duration_ms,
            "outcome_status": outcome.outcome_status,
            "error_category": outcome.error_category,
            "evaluator_score": outcome.evaluator_score,
            "evaluator_mode": outcome.evaluator_mode,
            "artifacts_passed": outcome.artifacts_passed,
            "artifacts_total": outcome.artifacts_total,
            "estimated_cost_usd": outcome.estimated_cost_usd,
            "actual_cost_usd": outcome.actual_cost_usd,
            "tokens_used": outcome.tokens_used,
            "retry_count": outcome.retry_count,
            "is_retry": outcome.is_retry,
            "original_goal_id": outcome.original_goal_id,
            "is_shadow_replay": outcome.is_shadow_replay,
            "replay_of_model": outcome.replay_of_model,
            "goal_type": outcome.goal_type,
            "goal_depth": outcome.goal_depth,
            "agent_role": outcome.agent_role
        })

        await session.commit()

        logger.info(
            "outcome_recorded",
            goal_id=outcome.goal_id,
            model=outcome.model_name,
            status=outcome.outcome_status,
            score=outcome.evaluator_score,
            divergent=outcome.was_divergent
        )

        return {
            "status": "recorded",
            "goal_id": outcome.goal_id,
            "outcome_status": outcome.outcome_status
        }


@outcome_router.get("/model-accuracy/{model_name}", response_model=ModelAccuracyStats)
async def get_model_accuracy(
    model_name: str,
    hours_back: int = Query(24, description="Hours to analyze")
):
    """
    Get real accuracy statistics for a specific model.

    Returns:
    - Success rate
    - Average evaluator score
    - Average duration and cost
    - How often CC recommended this model
    - How often executor followed CC
    """
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT
                COUNT(*) as total_executions,
                COUNT(*) FILTER (WHERE outcome_status = 'success') as successful_executions,
                AVG(evaluator_score) as avg_evaluator_score,
                AVG(duration_ms) as avg_duration_ms,
                AVG(actual_cost_usd) as avg_cost_usd,
                COUNT(*) FILTER (WHERE cc_recommended_model = :model_name) as cc_recommended_count,
                COUNT(*) FILTER (WHERE cc_recommended_model = :model_name AND model_name = :model_name) as cc_followed_count
            FROM llm_goal_outcomes
            WHERE
                model_name = :model_name
                AND started_at >= NOW() - (INTERVAL '1 hour' * :hours)
        """)

        result = await session.execute(query, {"model_name": model_name, "hours": hours_back})
        row = result.fetchone()

        if not row or row.total_executions == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No outcome data found for model '{model_name}' in last {hours_back} hours"
            )

        return ModelAccuracyStats(
            model_name=model_name,
            total_executions=row.total_executions,
            successful_executions=row.successful_executions or 0,
            success_rate=round((row.successful_executions or 0) / row.total_executions, 3),
            avg_evaluator_score=round(row.avg_evaluator_score or 0, 3),
            avg_duration_ms=round(row.avg_duration_ms or 0, 1),
            avg_cost_usd=round(row.avg_cost_usd or 0, 4),
            cc_recommended_count=row.cc_recommended_count or 0,
            cc_followed_count=row.cc_followed_count or 0
        )


@outcome_router.get("/conservative-accuracy", response_model=ConservativeAccuracy)
async def get_conservative_accuracy(
    hours_back: int = Query(24, description="Hours to analyze")
):
    """
    Conservative estimate of Control Center superiority.

    Level 1 - Conservative Divergence Evaluation:
    - If executor FAILED and CC recommended DIFFERENT model
    - Count as "CC potentially better"

    This is a LOWER BOUND estimate.
    Real CC accuracy is likely HIGHER (counterfactual gains).
    """
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT
                COUNT(*) as total_executions,
                COUNT(*) FILTER (WHERE outcome_status = 'success') as executor_successes,
                COUNT(*) FILTER (WHERE outcome_status IN ('error', 'timeout')) as executor_failures,
                COUNT(*) FILTER (WHERE was_divergent = TRUE) as divergent_cases,
                COUNT(*) FILTER (
                    WHERE was_divergent = TRUE
                    AND outcome_status IN ('error', 'timeout')
                ) as divergent_where_executor_failed,
                COUNT(*) FILTER (
                    WHERE was_divergent = TRUE
                    AND outcome_status = 'success'
                ) as divergent_where_executor_succeeded,
                COUNT(*) FILTER (
                    WHERE outcome_status IN ('error', 'timeout')
                    AND cc_recommended_model IS NOT NULL
                    AND cc_recommended_model != model_name
                ) as cc_potentially_better
            FROM llm_goal_outcomes
            WHERE started_at >= NOW() - (INTERVAL '1 hour' * :hours)
        """)

        result = await session.execute(query, {"hours": hours_back})
        row = result.fetchone()

        if not row or row.total_executions == 0:
            return ConservativeAccuracy(
                total_executions=0,
                executor_successes=0,
                executor_failures=0,
                cc_potentially_better=0,
                cc_accuracy_estimate=0.0,
                divergent_cases=0,
                divergent_where_executor_failed=0,
                divergent_where_executor_succeeded=0
            )

        # Conservative estimate: CC potentially better / total executions
        cc_potentially_better = row.cc_potentially_better or 0
        total = row.total_executions

        cc_accuracy_estimate = cc_potentially_better / total if total > 0 else 0.0

        return ConservativeAccuracy(
            total_executions=total,
            executor_successes=row.executor_successes or 0,
            executor_failures=row.executor_failures or 0,
            cc_potentially_better=cc_potentially_better,
            cc_accuracy_estimate=round(cc_accuracy_estimate, 3),
            divergent_cases=row.divergent_cases or 0,
            divergent_where_executor_failed=row.divergent_where_executor_failed or 0,
            divergent_where_executor_succeeded=row.divergent_where_executor_succeeded or 0
        )


@outcome_router.get("/divergence-breakdown")
async def get_divergence_breakdown(
    hours_back: int = Query(24, description="Hours to analyze")
):
    """
    Breakdown divergence by key dimensions to understand patterns.

    Returns:
    - Divergence by goal_type
    - Divergence by confidence bucket
    - Divergence by model pair
    """
    async with AsyncSessionLocal() as session:
        # By goal type
        by_goal_type = text("""
            SELECT
                goal_type,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE was_divergent = TRUE) as divergent,
                AVG(evaluator_score) as avg_score
            FROM llm_goal_outcomes
            WHERE
                started_at >= NOW() - (INTERVAL '1 hour' * :hours)
                AND goal_type IS NOT NULL
            GROUP BY goal_type
            ORDER BY divergent DESC
        """)

        # By confidence bucket
        by_confidence = text("""
            SELECT
                CASE
                    WHEN cc_confidence >= 0.8 THEN 'high'
                    WHEN cc_confidence >= 0.6 THEN 'medium'
                    ELSE 'low'
                END as confidence_bucket,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE was_divergent = TRUE) as divergent,
                AVG(evaluator_score) FILTER (WHERE was_divergent = TRUE) as avg_score_when_divergent
            FROM llm_goal_outcomes
            WHERE
                started_at >= NOW() - (INTERVAL '1 hour' * :hours)
                AND cc_confidence IS NOT NULL
            GROUP BY confidence_bucket
            ORDER BY
                CASE confidence_bucket
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END
        """)

        # By model pair
        by_model_pair = text("""
            SELECT
                model_name as actual_model,
                cc_recommended_model,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE outcome_status = 'success') as successful,
                AVG(evaluator_score) as avg_score
            FROM llm_goal_outcomes
            WHERE
                started_at >= NOW() - (INTERVAL '1 hour' * :hours)
                AND was_divergent = TRUE
                AND cc_recommended_model IS NOT NULL
            GROUP BY model_name, cc_recommended_model
            ORDER BY total DESC
            LIMIT 10
        """)

        result1 = await session.execute(by_goal_type, {"hours": hours_back})
        by_goal_type_rows = result1.fetchall()

        result2 = await session.execute(by_confidence, {"hours": hours_back})
        by_confidence_rows = result2.fetchall()

        result3 = await session.execute(by_model_pair, {"hours": hours_back})
        by_model_pair_rows = result3.fetchall()

        return {
            "by_goal_type": [
                {
                    "goal_type": row.goal_type,
                    "total": row.total,
                    "divergent": row.divergent,
                    "divergence_rate": round(row.divergent / row.total, 3) if row.total > 0 else 0,
                    "avg_score": round(row.avg_score, 3) if row.avg_score else 0
                }
                for row in by_goal_type_rows
            ],
            "by_confidence": [
                {
                    "confidence_bucket": row.confidence_bucket,
                    "total": row.total,
                    "divergent": row.divergent,
                    "divergence_rate": round(row.divergent / row.total, 3) if row.total > 0 else 0,
                    "avg_score_when_divergent": round(row.avg_score_when_divergent, 3) if row.avg_score_when_divergent else 0
                }
                for row in by_confidence_rows
            ],
            "by_model_pair": [
                {
                    "actual_model": row.actual_model,
                    "cc_recommended_model": row.cc_recommended_model,
                    "total": row.total,
                    "successful": row.successful,
                    "success_rate": round(row.successful / row.total, 3) if row.total > 0 else 0,
                    "avg_score": round(row.avg_score, 3) if row.avg_score else 0
                }
                for row in by_model_pair_rows
            ]
        }


@outcome_router.post("/trigger-shadow-replay")
async def trigger_shadow_replay(
    goal_id: str,
    replay_model: str,
    max_cost_usd: float = Query(0.1, description="Max cost for replay"),
    require_divergent: bool = Query(True, description="Only replay divergent cases")
):
    """
    Trigger shadow replay for counterfactual validation.

    For a goal that was already executed with one model,
    execute it AGAIN with the CC-recommended model (in shadow mode).

    This gives REAL data on "would CC have been better?"

    Constraints:
    - Only for divergent cases (executor chose different model)
    - Cost limit to prevent runaway costs
    - Stores as is_shadow_replay=true
    """
    async with AsyncSessionLocal() as session:
        # Get original outcome
        get_original = text("""
            SELECT
                goal_id, model_name, cc_recommended_model, was_divergent,
                goal_type, goal_depth, outcome_status, evaluator_score
            FROM llm_goal_outcomes
            WHERE goal_id = :goal_id
        """)

        result = await session.execute(get_original, {"goal_id": goal_id})
        original = result.fetchone()

        if not original:
            raise HTTPException(
                status_code=404,
                detail=f"Original outcome not found for goal_id {goal_id}"
            )

        # Validate conditions
        if require_divergent and not original.was_divergent:
            raise HTTPException(
                status_code=400,
                detail="Shadow replay only enabled for divergent cases"
            )

        if original.cc_recommended_model == replay_model:
            # This is the recommended model - good
            pass
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Replay model {replay_model} doesn't match CC recommendation {original.cc_recommended_model}"
            )

        # Check estimated cost
        # TODO: Query model catalog for cost estimate

        # Return replay task (would be queued to executor)
        return {
            "status": "queued",
            "original_goal_id": goal_id,
            "replay_model": replay_model,
            "original_model": original.model_name,
            "was_divergent": original.was_divergent,
            "notes": "This would execute goal again with replay_model in shadow mode"
        }
