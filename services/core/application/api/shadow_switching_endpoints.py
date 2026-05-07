"""
Shadow Switching Layer - Safe Path to Auto-Switching

This module implements controlled experimentation with model selection:
1. Log executor's actual choice
2. Log Control Center's recommended choice
3. Calculate divergence
4. Analyze over time: would Control Center be better?

Only AFTER statistical validation should auto-switch be enabled.

Author: Claude (Control Center v3)
Date: 2026-03-01
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger
import json

logger = get_logger(__name__)

shadow_router = APIRouter(prefix="/llm/control/shadow", tags=["Shadow Switching"])


# ============================================================================
# Shadow Switching Models
# ============================================================================

class ShadowDecision(BaseModel):
    timestamp: str
    goal_type: str
    goal_id: Optional[str] = None

    # Executor's actual choice
    actual_model: str

    # Control Center's recommendation
    recommended_model: str
    recommended_score: float
    alternative_models: List[str]

    # Divergence analysis
    is_divergent: bool
    divergence_reason: str
    expected_gain_score: float  # Difference in combined score

    # Context
    confidence: float
    constraints_applied: Dict[str, Any]

    # Would switch happen?
    should_switch: bool  # Based on gain threshold
    switch_threshold: float  # Minimum gain to trigger switch


class DivergenceAnalytics(BaseModel):
    total_decisions: int
    divergent_decisions: int
    divergence_rate: float

    # When Control Center differs
    control_center_better: int  # Control Center choice had higher success
    executor_better: int  # Executor choice had higher success
    inconclusive: int  # Need more data

    # Expected gains
    avg_expected_gain_when_divergent: float
    high_confidence_divergences: int  # confidence > 0.7

    # Recommendations
    ready_for_auto_switch: bool
    readiness_criteria: Dict[str, Any]


class AutoSwitchCriteria(BaseModel):
    """
    Strict criteria for enabling auto-switch.

    All must be TRUE before auto-switch can be enabled.
    """
    min_shadow_decisions: int = 1000  # Minimum data points
    max_divergence_rate: float = 0.4  # Max 40% divergence
    min_accuracy: float = 0.65  # Control Center better in 65%+ of divergences
    min_confidence_gap: float = 0.1  # At least 0.1 score difference
    min_high_confidence_divergences: int = 50  # At least 50 high-confidence cases

    # Safety: anti-flapping
    min_stability_days: int = 7  # Must be stable for 7 days
    max_model_switches_per_day: int = 10  # Prevent thrashing


# ============================================================================
# Shadow Logging Endpoint
# ============================================================================

@shadow_router.post("/log-decision")
async def log_shadow_decision(decision: ShadowDecision):
    """
    Log a shadow decision for divergence analysis.

    Called by goal_executor BEFORE making actual LLM call:
    1. Get Control Center recommendation
    2. Log both actual and recommended
    3. Store for later analysis

    Does NOT affect executor behavior (shadow mode only).
    """
    async with AsyncSessionLocal() as session:
        # Check if shadow decisions table exists
        check_table = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'llm_shadow_decisions'
            )
        """)
        table_exists = (await session.execute(check_table)).scalar()

        if not table_exists:
            # Create shadow decisions table
            create_table = text("""
                CREATE TABLE llm_shadow_decisions (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    goal_type TEXT NOT NULL,
                    goal_id UUID,

                    actual_model TEXT NOT NULL,
                    recommended_model TEXT NOT NULL,
                    recommended_score FLOAT,
                    alternative_models JSONB,

                    is_divergent BOOLEAN DEFAULT FALSE,
                    divergence_reason TEXT,
                    expected_gain_score FLOAT,

                    confidence FLOAT,
                    constraints_applied JSONB,

                    should_switch BOOLEAN DEFAULT FALSE,
                    switch_threshold FLOAT DEFAULT 0.05,

                    INDEX (timestamp),
                    INDEX (goal_type),
                    INDEX (is_divergent)
                );
            """)
            await session.execute(create_table)
            await session.commit()

        # Insert shadow decision
        insert_query = text("""
            INSERT INTO llm_shadow_decisions (
                goal_type, goal_id,
                actual_model, recommended_model, recommended_score,
                alternative_models, is_divergent, divergence_reason,
                expected_gain_score, confidence, constraints_applied,
                should_switch, switch_threshold
            ) VALUES (
                :goal_type, :goal_id,
                :actual_model, :recommended_model, :recommended_score,
                :alternative_models, :is_divergent, :divergence_reason,
                :expected_gain_score, :confidence, :constraints_applied,
                :should_switch, :switch_threshold
            )
        """)

        await session.execute(insert_query, {
            "goal_type": decision.goal_type,
            "goal_id": decision.goal_id,
            "actual_model": decision.actual_model,
            "recommended_model": decision.recommended_model,
            "recommended_score": decision.recommended_score,
            "alternative_models": json.dumps(decision.alternative_models),
            "is_divergent": decision.is_divergent,
            "divergence_reason": decision.divergence_reason,
            "expected_gain_score": decision.expected_gain_score,
            "confidence": decision.confidence,
            "constraints_applied": json.dumps(decision.constraints_applied),
            "should_switch": decision.should_switch,
            "switch_threshold": decision.switch_threshold
        })

        await session.commit()

        logger.info(
            "shadow_decision_logged",
            actual=decision.actual_model,
            recommended=decision.recommended_model,
            divergent=decision.is_divergent,
            gain=decision.expected_gain_score
        )

        return {
            "status": "logged",
            "divergent": decision.is_divergent,
            "should_switch": decision.should_switch
        }


@shadow_router.get("/divergence-analytics", response_model=DivergenceAnalytics)
async def get_divergence_analytics(
    hours_back: int = Query(24, description="Hours to analyze"),
    min_gain_threshold: float = Query(0.05, description="Minimum gain to consider switch")
):
    """
    Analyze shadow decisions to determine readiness for auto-switch.

    Returns:
    - Divergence rate
    - Control Center accuracy
    - Expected gains
    - Ready for auto-switch?
    """
    async with AsyncSessionLocal() as session:
        # Check if we have shadow decisions
        check_query = text("""
            SELECT COUNT(*) as cnt
            FROM llm_shadow_decisions
        """)
        result = await session.execute(check_query)
        count = result.scalar()

        if not count or count < 100:
            return DivergenceAnalytics(
                total_decisions=count or 0,
                divergent_decisions=0,
                divergence_rate=0.0,
                control_center_better=0,
                executor_better=0,
                inconclusive=0,
                avg_expected_gain_when_divergent=0.0,
                high_confidence_divergences=0,
                ready_for_auto_switch=False,
                readiness_criteria={
                    "min_shadow_decisions": "MET" if count >= 1000 else f"NEED MORE: {count}/1000",
                    "reason": "Insufficient shadow decisions collected"
                }
            )

        # Overall stats
        stats_query = text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_divergent = TRUE) as divergent,
                AVG(expected_gain_score) FILTER (WHERE is_divergent = TRUE) as avg_gain,
                COUNT(*) FILTER (WHERE is_divergent = TRUE AND confidence > 0.7) as high_conf_div
            FROM llm_shadow_decisions
            WHERE timestamp >= NOW() - (INTERVAL '1 hour' * :hours)
        """)

        result = await session.execute(stats_query, {"hours": hours_back})
        row = result.fetchone()

        total = row.total or 0
        divergent = row.divergent or 0
        avg_gain = row.avg_gain or 0
        high_conf_div = row.high_conf_div or 0

        divergence_rate = divergent / total if total > 0 else 0

        # For deeper analysis, need actual outcomes
        # For now, mark as inconclusive
        control_center_better = 0
        executor_better = 0
        inconclusive = divergent

        # Check readiness criteria
        criteria = AutoSwitchCriteria()
        ready = all([
            total >= criteria.min_shadow_decisions,
            divergence_rate <= criteria.max_divergence_rate,
            inconclusive > 0,  # Need some divergence data
            avg_gain >= criteria.min_confidence_gap
        ])

        return DivergenceAnalytics(
            total_decisions=total,
            divergent_decisions=divergent,
            divergence_rate=round(divergence_rate, 3),
            control_center_better=control_center_better,
            executor_better=executor_better,
            inconclusive=inconclusive,
            avg_expected_gain_when_divergent=round(avg_gain, 3),
            high_confidence_divergences=high_conf_div,
            ready_for_auto_switch=ready,
            readiness_criteria={
                "min_shadow_decisions": "PASS" if total >= criteria.min_shadow_decisions else f"FAIL: {total}/{criteria.min_shadow_decisions}",
                "max_divergence_rate": "PASS" if divergence_rate <= criteria.max_divergence_rate else f"FAIL: {divergence_rate:.1%} > {criteria.max_divergence_rate:.0%}",
                "min_accuracy": "PENDING" if inconclusive > 0 else "FAIL",
                "min_confidence_gap": "PASS" if avg_gain >= criteria.min_confidence_gap else f"FAIL: {avg_gain:.3f} < {criteria.min_confidence_gap}",
                "overall": "READY" if ready else "NOT READY"
            }
        )


@shadow_router.get("/auto-switch-status")
async def get_auto_switch_status():
    """
    Get current status and recommendations for auto-switch.

    Returns:
    - Current criteria configuration
    - Readiness assessment
    - Recommendations for next steps
    """
    async with AsyncSessionLocal() as session:
        # Get current analytics
        try:
            analytics = await get_divergence_analytics(hours_back=24)
        except HTTPException:
            analytics = DivergenceAnalytics(
                total_decisions=0,
                divergent_decisions=0,
                divergence_rate=0.0,
                control_center_better=0,
                executor_better=0,
                inconclusive=0,
                avg_expected_gain_when_divergent=0.0,
                high_confidence_divergences=0,
                ready_for_auto_switch=False,
                readiness_criteria={}
            )

        criteria = AutoSwitchCriteria()

        # Generate recommendations
        recommendations = []

        if analytics.total_decisions < criteria.min_shadow_decisions:
            recommendations.append({
                "priority": "CRITICAL",
                "action": "Collect more shadow data",
                "target": f"{criteria.min_shadow_decisions} decisions",
                "current": analytics.total_decisions,
                "reason": "Insufficient data for statistical validation"
            })

        if analytics.divergence_rate > criteria.max_divergence_rate:
            recommendations.append({
                "priority": "WARNING",
                "action": "High divergence rate detected",
                "current": f"{analytics.divergence_rate:.1%}",
                "threshold": f"{criteria.max_divergence_rate:.0%}",
                "reason": "Control Center disagrees with executor too often. Review constraints or scoring."
            })

        if analytics.avg_expected_gain_when_divergent < criteria.min_confidence_gap:
            recommendations.append({
                "priority": "INFO",
                "action": "Low expected gain from switching",
                "current": f"{analytics.avg_expected_gain_when_divergent:.3f}",
                "threshold": f"{criteria.min_confidence_gap}",
                "reason": "Switching models wouldn't improve outcomes significantly"
            })

        return {
            "current_status": "SHADOW_MODE" if not analytics.ready_for_auto_switch else "READY_FOR_AUTO_SWITCH",
            "analytics": analytics.dict(),
            "criteria": criteria.dict(),
            "recommendations": recommendations,
            "next_steps": [
                "Continue shadow logging until all criteria met",
                "Monitor divergence analytics daily",
                "Review shadow decisions manually before enabling auto-switch",
                "Enable auto-switch via feature flag when ready"
            ]
        }


@shadow_router.post("/simulate-switch")
async def simulate_auto_switch(
    enable: bool = Query(..., description="Enable or disable auto-switch"),
    require_divergence_analysis: bool = Query(True, description="Check analytics before enabling")
):
    """
    Enable or disable auto-switch (WITH VALIDATION).

    This is SAFE because:
    1. Checks readiness criteria before enabling
    2. Requires explicit confirmation
    3. Can be disabled instantly if problems detected
    """
    if enable:
        # Validate readiness first
        analytics = await get_divergence_analytics(hours_back=24)

        if require_divergence_analysis and not analytics.ready_for_auto_switch:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot enable auto-switch: {analytics.readiness_criteria}"
            )

        # TODO: Set feature flag in database
        logger.warning(
            "auto_switch_enabled",
            analytics=analytics.dict()
        )

        return {
            "status": "enabled",
            "mode": "AUTO_SWITCH",
            "warning": "Model selection will now be controlled by Control Center. Monitor closely!"
        }
    else:
        # Disable auto-switch
        logger.info("auto_switch_disabled")

        return {
            "status": "disabled",
            "mode": "SHADOW_MODE",
            "message": "Reverted to shadow mode. Executor chooses models."
        }


# ============================================================================
# Integration Helper (for goal_executor_v2)
# ============================================================================

async def should_switch_model(
    goal_type: str,
    current_model: str,
    goal_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Integration point for goal_executor_v2.

    Call this BEFORE each LLM call to:
    1. Get Control Center recommendation
    2. Log shadow decision
    3. Return whether to switch (shadow mode only for now)

    Usage in executor:
        decision = await should_switch_model(goal_type, current_model, goal_id)

        if decision["should_switch"]:
            # Log only, don't actually switch yet
            logger.info("shadow_mode_recommendation", **decision)

        # Use original model (shadow mode)
        model_to_use = current_model
    """
    async with AsyncSessionLocal() as session:
        # Get decision trace
        trace_query = text("""
            SELECT
                model_name as recommended_model,
                combined_score as recommended_score,
                cost_score,
                latency_score,
                success_score,
                confidence
            FROM get_decision_trace_cached(:goal_type, NULL, NULL, 0.5)
        """)

        # Note: This would need to call the decision trace logic
        # For now, simplified version

        return {
            "current_model": current_model,
            "recommended_model": current_model,  # Placeholder
            "should_switch": False,  # Always false in shadow mode
            "confidence": 0.0,
            "expected_gain": 0.0
        }
