"""
Decision Trace Layer - Explainable Model Selection

This module provides detailed traceability for model selection decisions.
Every recommendation includes full breakdown of WHY a model was chosen.

Key Principles:
1. Complete transparency - show all candidates, not just winner
2. Constraint tracking - explain WHY models were filtered
3. Scoring breakdown - show HOW winner was selected
4. Decision audit - immutable record for later analysis

Author: Claude (Control Center v2)
Date: 2026-03-01
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)

decision_router = APIRouter(prefix="/llm/control/decision", tags=["Decision Trace"])

# ============================================================================
# Goal-Type Specific Weights (Adaptive Economic Router) - v1.0
# ============================================================================
#
# SCORING FORMULA:
#   adjusted_score = combined_score * sample_confidence
#   combined_score = success_score * w_success + cost_score * w_cost + latency_score * w_latency
#
# NORMALIZATION (min-max to [0,1], higher is better):
#   cost_score = (max_cost - cost) / (max_cost - min_cost)
#   latency_score = (max_latency - latency) / (max_latency - min_latency)
#   success_score = success_rate (already in [0,1])
#
# CONFIDENCE PENALTY:
#   MIN_SAMPLE = 10: confidence = 0.1 (severe penalty)
#   TARGET_SAMPLE = 50: confidence = 1.0 (full confidence)
#   Linear interpolation between
#
# GUARDRAILS:
#   - Weights must sum to 1.0 (validated at startup)
#   - Unknown goal_types fallback to "default"
#   - MIN_SAMPLE threshold prevents decisions on insufficient data

# Frozen list of supported goal types (v1.0)
SUPPORTED_GOAL_TYPES = frozenset([
    "precise_reasoning",
    "cheap_generation",
    "creative_writing",
    "long_context"
])

GOAL_TYPE_WEIGHTS = {
    # precise_reasoning: Quality is paramount, willing to pay more
    "precise_reasoning": {
        "success": 0.6,
        "latency": 0.2,
        "cost": 0.2
    },
    # cheap_generation: Optimize for throughput and cost
    "cheap_generation": {
        "success": 0.2,
        "latency": 0.5,
        "cost": 0.3
    },
    # creative_writing: Quality matters most
    "creative_writing": {
        "success": 0.7,
        "latency": 0.15,
        "cost": 0.15
    },
    # long_context: Balance quality and context handling
    "long_context": {
        "success": 0.5,
        "latency": 0.25,
        "cost": 0.25
    },
    # Default for unknown goal_types
    "default": {
        "success": 0.5,
        "latency": 0.2,
        "cost": 0.3
    }
}

# ============================================================================
# Guardrail: Validate weights at startup
# ============================================================================

def _validate_weights():
    """Validate that all weight sets sum to 1.0"""
    for goal_type, weights in GOAL_TYPE_WEIGHTS.items():
        total = weights["success"] + weights["latency"] + weights["cost"]
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Weights for {goal_type} sum to {total}, not 1.0")
    logger.info("goal_type_weights_validated", goal_types=list(GOAL_TYPE_WEIGHTS.keys()))

_validate_weights()  # Run at module load

def get_weights_for_goal_type(goal_type: str) -> dict:
    """Get scoring weights for a specific goal type."""
    return GOAL_TYPE_WEIGHTS.get(goal_type, GOAL_TYPE_WEIGHTS["default"])


# ============================================================================
# Trace Models
# ============================================================================

class ModelCandidate(BaseModel):
    model_name: str
    eligible: bool  # Passed all constraints?

    # Raw metrics
    total_calls: int
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_cost_usd: float
    cost_per_successful_goal: float
    roi_score: float

    # Scoring
    cost_score: float  # 0-1, higher is better (cheaper)
    latency_score: float  # 0-1, higher is better (faster)
    success_score: float  # 0-1, higher is better
    combined_score: float  # Weighted combination (all normalized)
    sample_confidence: float  # 0-1, confidence based on sample size
    adjusted_score: float  # combined_score * sample_confidence

    # Constraint checks
    constraint_results: Dict[str, Dict[str, Any]]  # {"max_latency": {"passed": false, "value": 8000, "limit": 2000}}

    # Explanation
    rejection_reason: Optional[str] = None
    selection_reason: Optional[str] = None


class DecisionTrace(BaseModel):
    goal_type: str
    timestamp: str

    # Constraints applied
    constraints: Dict[str, Any]  # {"max_latency_ms": 2000, "max_cost_per_goal": 0.05}

    # All candidates evaluated
    candidates: List[ModelCandidate]

    # Winner
    selected_model: str
    winner_confidence: float  # 0-1

    # Decision reasoning
    decision_summary: str
    decision_breakdown: List[str]  # Step-by-step explanation

    # Metadata
    total_candidates: int
    eligible_candidates: int
    data_freshness_hours: float
    data_freshness_warning: Optional[str] = None  # Warning if data is stale


# ============================================================================
# Decision Trace Endpoint
# ============================================================================

@decision_router.get("/trace", response_model=DecisionTrace)
async def get_decision_trace(
    goal_type: str = Query(..., description="Goal type"),
    max_latency_ms: Optional[int] = Query(None, description="Max acceptable latency"),
    max_cost_per_goal: Optional[float] = Query(None, description="Max cost per goal"),
    min_success_rate: Optional[float] = Query(0.5, description="Min success rate")
):
    """
    Get detailed trace of model selection decision.

    This returns COMPLETE breakdown:
    - All models considered
    - Why each was filtered or selected
    - Scoring details
    - Final decision explanation

    Use this to:
    - Validate decision logic
    - Debug unexpected recommendations
    - Audit model selection over time
    """
    async with AsyncSessionLocal() as session:
        # Get model metrics filtered by goal_type (task-specific routing)
        # First try exact goal_type match, fallback to achievable if not enough data
        query = text("""
            SELECT
                model_name,
                goal_type,
                SUM(total_calls) as total_calls,
                SUM(success_calls) as success_calls,
                SUM(error_calls) as error_calls,
                SUM(avg_latency * total_calls) / NULLIF(SUM(total_calls), 0) as avg_latency,
                SUM(p95_estimate * total_calls) / NULLIF(SUM(total_calls), 0) as p95_latency,
                SUM(p99_estimate * total_calls) / NULLIF(SUM(total_calls), 0) as p99_latency,
                SUM(total_cost) as total_cost
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - INTERVAL '72 hours'
              AND goal_type = :goal_type
            GROUP BY model_name, goal_type
            HAVING SUM(total_calls) > 10
        """)

        result = await session.execute(query, {"goal_type": goal_type})
        rows = result.fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Insufficient data for decision trace. Need at least 10 calls per model."
            )

        # Build candidates with constraint checking
        candidates = []
        breakdown = []

        for r in rows:
            total_calls = r.total_calls or 0
            success_calls = r.success_calls or 0
            total_cost = r.total_cost or 0
            avg_latency = r.avg_latency or 0
            p95_latency = r.p95_latency or 0
            p99_latency = r.p99_latency or 0

            success_rate = success_calls / total_calls if total_calls > 0 else 0
            cost_per_goal = total_cost / success_calls if success_calls > 0 else 0
            roi_score = success_calls / total_cost if total_cost > 0 else 0

            # Check constraints
            constraint_results = {}
            eligible = True
            rejection_reasons = []

            # Min success rate constraint
            if min_success_rate:
                passed = success_rate >= min_success_rate
                constraint_results["min_success_rate"] = {
                    "passed": passed,
                    "value": round(success_rate, 3),
                    "limit": min_success_rate
                }
                if not passed:
                    eligible = False
                    rejection_reasons.append(f"Success rate {success_rate:.1%} below minimum {min_success_rate:.1%}")

            # Max latency constraint
            if max_latency_ms:
                passed = avg_latency <= max_latency_ms
                constraint_results["max_latency_ms"] = {
                    "passed": passed,
                    "value": round(avg_latency, 1),
                    "limit": max_latency_ms
                }
                if not passed:
                    eligible = False
                    rejection_reasons.append(f"Latency {avg_latency:.0f}ms exceeds limit {max_latency_ms}ms")

            # Max cost constraint
            if max_cost_per_goal:
                passed = cost_per_goal <= max_cost_per_goal
                constraint_results["max_cost_per_goal"] = {
                    "passed": passed,
                    "value": round(cost_per_goal, 4),
                    "limit": max_cost_per_goal
                }
                if not passed:
                    eligible = False
                    rejection_reasons.append(f"Cost ${cost_per_goal:.4f} exceeds limit ${max_cost_per_goal:.4f}")

            # Calculate scores (only for eligible models)
            weights = get_weights_for_goal_type(goal_type)  # Get weights early for logging
            if eligible and total_calls > 0:
                # Min-max normalization for all metrics to [0, 1] range

                # Cost: lower is better, so invert
                costs = [r_.total_cost for r_ in rows]
                min_cost = min(costs)
                max_cost = max(costs)
                cost_range = max_cost - min_cost if max_cost > min_cost else 1
                cost_score = (max_cost - total_cost) / cost_range  # 0-1, higher is better

                # Latency: lower is better, so invert
                latencies = [r_.avg_latency or 0 for r_ in rows]
                min_latency = min(latencies)
                max_latency = max(latencies)
                latency_range = max_latency - min_latency if max_latency > min_latency else 1
                latency_score = (max_latency - avg_latency) / latency_range  # 0-1, higher is better

                # Success rate: already 0-1
                success_score = success_rate

                # Get goal-type specific weights (Adaptive Economic Router)
                weights = get_weights_for_goal_type(goal_type)

                # Combined score: weighted sum using goal-type specific weights
                combined_score = (
                    success_score * weights["success"] +
                    cost_score * weights["cost"] +
                    latency_score * weights["latency"]
                )

                # Sample confidence: penalize low sample sizes
                # MIN_SAMPLE = 10 (below this, severe penalty)
                # TARGET_SAMPLE = 50 (full confidence)
                # Formula: (calls - MIN) / (TARGET - MIN), capped at [0.1, 1.0]
                MIN_SAMPLE = 10
                TARGET_SAMPLE = 50
                if total_calls <= MIN_SAMPLE:
                    sample_confidence = 0.1  # Minimum confidence for very low samples
                elif total_calls >= TARGET_SAMPLE:
                    sample_confidence = 1.0  # Full confidence for sufficient data
                else:
                    # Linear interpolation between MIN and TARGET
                    sample_confidence = 0.1 + (total_calls - MIN_SAMPLE) / (TARGET_SAMPLE - MIN_SAMPLE) * 0.9

                # Adjusted score: base score * confidence
                adjusted_score = combined_score * sample_confidence
            else:
                cost_score = 0
                latency_score = 0
                combined_score = 0
                sample_confidence = 0.0
                adjusted_score = 0.0

            candidate = ModelCandidate(
                model_name=r.model_name,
                eligible=eligible,
                total_calls=total_calls,
                success_rate=round(success_rate, 3),
                avg_latency_ms=round(avg_latency, 1),
                p95_latency_ms=round(p95_latency, 1),
                total_cost_usd=round(total_cost, 4),
                cost_per_successful_goal=round(cost_per_goal, 4),
                roi_score=round(roi_score, 2),
                cost_score=round(cost_score, 3),
                latency_score=round(latency_score, 3),
                success_score=round(success_score if eligible else 0, 3),
                combined_score=round(combined_score, 3),
                sample_confidence=round(sample_confidence, 3),
                adjusted_score=round(adjusted_score, 3),
                constraint_results=constraint_results,
                rejection_reason="; ".join(rejection_reasons) if rejection_reasons else None,
                selection_reason=f"Score {adjusted_score:.3f} (base:{combined_score:.2f}×conf:{sample_confidence:.2f}, weights:S={weights['success']:.1f}/L={weights['latency']:.1f}/C={weights['cost']:.1f})" if eligible else None
            )

            candidates.append(candidate)

        # Sort by adjusted score (eligible first, then by adjusted_score)
        candidates.sort(key=lambda c: (-c.eligible, -c.adjusted_score))

        # Find winner (first eligible model)
        eligible_candidates = [c for c in candidates if c.eligible]

        if not eligible_candidates:
            raise HTTPException(
                status_code=404,
                detail=f"No models pass constraints. Consider relaxing constraints."
            )

        winner = eligible_candidates[0]

        # Calculate winner confidence (based on score gap to second place)
        if len(eligible_candidates) > 1:
            second_place = eligible_candidates[1]
            score_gap = winner.combined_score - second_place.combined_score
            # Larger gap = higher confidence (0.5 to 1.0)
            confidence = min(0.5 + score_gap * 2, 1.0)
        else:
            # Only one eligible candidate
            confidence = 0.7

        # Build decision breakdown
        breakdown = [
            f"Evaluating {len(candidates)} models for goal_type='{goal_type}'",
        ]

        # Add constraints to breakdown
        applied_constraints = []
        if max_latency_ms:
            applied_constraints.append(f"max_latency_ms={max_latency_ms}")
        if max_cost_per_goal:
            applied_constraints.append(f"max_cost_per_goal=${max_cost_per_goal:.4f}")
        if min_success_rate:
            applied_constraints.append(f"min_success_rate={min_success_rate:.1%}")

        if applied_constraints:
            breakdown.append(f"Applied constraints: {', '.join(applied_constraints)}")

        # Add filtering results
        filtered_count = len(candidates) - len(eligible_candidates)
        if filtered_count > 0:
            breakdown.append(f"{filtered_count} model(s) filtered out by constraints")

            # Add specific reasons
            for c in candidates:
                if not c.eligible:
                    breakdown.append(f"  - {c.model_name}: {c.rejection_reason}")

        # Add scoring for eligible models
        breakdown.append(f"Scoring {len(eligible_candidates)} eligible model(s):")
        for i, c in enumerate(eligible_candidates[:3], 1):  # Top 3
            breakdown.append(
                f"  {i}. {c.model_name}: score={c.combined_score:.3f} "
                f"(success={c.success_score:.3f}, cost={c.cost_score:.3f}, "
                f"latency={c.latency_score:.3f})"
            )

        # Add final decision
        decision_summary = (
            f"Selected {winner.model_name} with combined score {winner.combined_score:.3f}. "
            f"Confidence: {confidence:.1%}. "
        )

        if winner.selection_reason:
            decision_summary += winner.selection_reason

        # Data freshness check
        freshness_query = text("""
            SELECT EXTRACT(EPOCH FROM (NOW() - MAX(bucket))) / 3600.0 as hours_ago
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - INTERVAL '72 hours'
        """)
        freshness_result = await session.execute(freshness_query)
        freshness_hours = (freshness_result.fetchone().hours_ago or 0)

        # Freshness warning if data is older than threshold
        FRESHNESS_WARNING_HOURS = 24
        freshness_warning = None
        if freshness_hours > FRESHNESS_WARNING_HOURS:
            freshness_warning = f"Data is {freshness_hours:.1f}h old. Consider collecting fresh metrics."

        return DecisionTrace(
            goal_type=goal_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            constraints={
                "max_latency_ms": max_latency_ms,
                "max_cost_per_goal": max_cost_per_goal,
                "min_success_rate": min_success_rate
            },
            candidates=candidates,
            selected_model=winner.model_name,
            winner_confidence=round(confidence, 2),
            decision_summary=decision_summary,
            decision_breakdown=breakdown,
            total_candidates=len(candidates),
            eligible_candidates=len(eligible_candidates),
            data_freshness_hours=round(freshness_hours, 2),
            data_freshness_warning=freshness_warning
        )


@decision_router.get("/test-scenarios")
async def get_test_scenarios():
    """
    Get predefined test scenarios for validating decision logic.

    Each scenario represents a real-world use case with expected outcomes.
    Use this for systematic validation of Control Center behavior.
    """
    scenarios = [
        {
            "name": "Baseline - No Constraints",
            "description": "All models eligible, should rank by ROI",
            "params": {
                "goal_type": "achievable",
                "min_success_rate": 0.0,
                "max_latency_ms": None,
                "max_cost_per_goal": None
            },
            "expected_outcome": "local-coder should win (cheapest with reasonable success)",
            "validation_checks": [
                "local-coder ranked highest",
                "gpt-4 ranked middle",
                "claude-3-opus ranked lowest (expensive)"
            ]
        },
        {
            "name": "Latency-Sensitive Task",
            "description": "Real-time response required (<2s)",
            "params": {
                "goal_type": "achievable",
                "min_success_rate": 0.0,
                "max_latency_ms": 2000,
                "max_cost_per_goal": None
            },
            "expected_outcome": "local-coder filtered out, gpt-4 should win",
            "validation_checks": [
                "local-coder rejected (8000ms > 2000ms)",
                "gpt-4 selected (1500ms < 2000ms)",
                "claude-3-opus eligible but lower score"
            ]
        },
        {
            "name": "Budget-Constrained Task",
            "description": "Low budget, need cheap model",
            "params": {
                "goal_type": "achievable",
                "min_success_rate": 0.0,
                "max_latency_ms": None,
                "max_cost_per_goal": 0.02
            },
            "expected_outcome": "Only local-coder eligible",
            "validation_checks": [
                "gpt-4 rejected ($0.03 > $0.02)",
                "claude-3-opus rejected ($0.045 > $0.02)",
                "local-coder selected ($0.001 < $0.02)"
            ]
        },
        {
            "name": "High-Quality Requirement",
            "description": "Critical task, need high success rate",
            "params": {
                "goal_type": "achievable",
                "min_success_rate": 0.90,
                "max_latency_ms": None,
                "max_cost_per_goal": None
            },
            "expected_outcome": "local-coder filtered out (75% < 90%), gpt-4 should win",
            "validation_checks": [
                "local-coder rejected (75% < 90%)",
                "gpt-4 selected (92% > 90%)",
                "claude-3-opus eligible (88% < 90%)"
            ]
        },
        {
            "name": "Strict Constraints (No Winner)",
            "description": "Impossible constraints, should fail gracefully",
            "params": {
                "goal_type": "achievable",
                "min_success_rate": 0.95,
                "max_latency_ms": 1000,
                "max_cost_per_goal": 0.01
            },
            "expected_outcome": "No models pass all constraints",
            "validation_checks": [
                "All models rejected",
                "404 error returned",
                "Clear explanation of constraint violations"
            ]
        }
    ]

    return {
        "total_scenarios": len(scenarios),
        "scenarios": scenarios,
        "usage": "Run each scenario via GET /llm/control/decision/trace with the specified params"
    }


# ============================================================================
# Integration: Update main router
# ============================================================================

# Add to main.py:
# from application.api.decision_trace_endpoints import router as decision_trace_router
# app.include_router(decision_trace_router)
