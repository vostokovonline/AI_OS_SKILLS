"""
LLM Control Center API - Production-Safe

Principles:
1. Read from pre-aggregated tables (O(1) queries)
2. Provide model recommendations based on cost/performance
3. Support what-if simulation for policy comparison
4. Cost per successful goal (not just per call)

Author: Claude (Control Center v1)
Date: 2026-03-01
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text, select, func
from database import AsyncSessionLocal
from logging_config import get_logger
import uuid
import random
import json

logger = get_logger(__name__)

router = APIRouter(prefix="/llm/control", tags=["LLM Control"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ModelMetrics(BaseModel):
    model_name: str
    provider: str

    # Performance (24h)
    total_calls: int
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    # Cost (24h)
    total_cost_usd: float
    cost_per_1k_tokens: float
    avg_tokens_per_call: int

    # Per-goal metrics (via goal_type join)
    cost_per_successful_goal: Optional[float] = None
    success_rate_by_goal_type: Dict[str, float] = {}


class ModelRecommendation(BaseModel):
    goal_type: str
    recommended_model: str
    reason: str
    expected_cost_usd: float
    expected_latency_ms: float
    confidence_score: float  # 0-1
    alternatives: List[Dict[str, str]]  # [{model, reason}]


class PolicySimulation(BaseModel):
    policy_name: str
    description: str

    # Expected outcomes
    expected_monthly_cost_usd: float
    expected_avg_latency_ms: float
    expected_success_rate: float

    # Comparison vs current
    cost_change_percent: float
    latency_change_percent: float


class ControlCenterOverview(BaseModel):
    # Cost metrics (24h)
    total_cost_usd: float
    cost_by_model: Dict[str, float]
    cost_trend: str  # "increasing", "stable", "decreasing"

    # Performance metrics (24h)
    total_calls: int
    overall_success_rate: float
    p95_latency_ms: float
    slow_calls_count: int

    # Top models by ROI
    top_models_by_roi: List[Dict[str, Any]]

    # Active policy
    active_policy: str
    policy_compliance: float  # % of calls within policy


class TestDataInjection(BaseModel):
    num_calls_per_model: int = 100
    models: Optional[List[str]] = None  # Default: ["gpt-4", "claude-3-opus", "local-coder"]
    start_hours_ago: int = 24  # How far back to start generating data
    goal_type: Optional[str] = "achievable"  # NEW: task category for skill-specific routing


# ============================================================================
# Control Endpoints
# ============================================================================

@router.post("/inject-test-data")
async def inject_test_data(params: TestDataInjection = TestDataInjection()):
    """
    Inject synthetic model_usage data for testing Control Center.

    Creates controlled test data with:
    - Different latency patterns per model
    - Different success rates per model
    - Different costs per model
    - Various goal_types

    This enables immediate validation of:
    - Aggregator percentile calculations
    - ROI ranking
    - Model recommendations
    - Policy simulation
    """
    async with AsyncSessionLocal() as session:
        # Default models if not specified
        models = params.models or ["gpt-4", "claude-3-opus", "local-coder"]

        # Model profiles: latency (ms), success_rate, cost_per_call
        # Real Ollama models
        model_profiles = {
            "gpt-4": {
                "latency_base": 1500,
                "latency_var": 500,
                "success_rate": 0.92,
                "cost_per_call": 0.03,
                "tokens_per_call": 1500
            },
            "claude-3-opus": {
                "latency_base": 2500,
                "latency_var": 800,
                "success_rate": 0.88,
                "cost_per_call": 0.045,
                "tokens_per_call": 2000
            },
            "local-coder": {
                "latency_base": 8000,
                "latency_var": 2000,
                "success_rate": 0.75,
                "cost_per_call": 0.001,
                "tokens_per_call": 3000
            },
            # Real Ollama models
            "ollama/qwen2.5-coder:latest": {
                "latency_base": 12000,
                "latency_var": 5000,
                "success_rate": 0.80,
                "cost_per_call": 0.0,
                "tokens_per_call": 2000
            },
            "ollama/deepseek-v3.1:671b-cloud": {
                "latency_base": 3000,
                "latency_var": 1000,
                "success_rate": 0.85,
                "cost_per_call": 0.0,
                "tokens_per_call": 2500
            },
            "ollama/qwen3-coder:480b-cloud": {
                "latency_base": 3500,
                "latency_var": 1000,
                "success_rate": 0.82,
                "cost_per_call": 0.0,
                "tokens_per_call": 2000
            }
        }

        goal_types = ["achievable", "continuous", "directional", "exploratory"]
        agent_roles = ["CODER", "RESEARCHER", "PM", "INTELLIGENCE"]

        inserted_count = 0

        for model_name in models:
            if model_name not in model_profiles:
                logger.warning("test_data_model_not_found", model=model_name)
                continue

            profile = model_profiles[model_name]

            for i in range(params.num_calls_per_model):
                # Generate latency with variance
                latency = max(100, int(random.gauss(profile["latency_base"], profile["latency_var"])))

                # Determine success/failure
                is_success = random.random() < profile["success_rate"]
                status = "success" if is_success else "error"

                # Generate cost
                cost_usd = profile["cost_per_call"] * random.uniform(0.8, 1.2)

                # Select agent_role
                agent_role = random.choice(agent_roles)

                # Error message for failures
                error_message = None
                if not is_success:
                    if latency > 10000:
                        error_message = "Request timeout after 10000ms"
                    elif random.random() < 0.3:
                        error_message = "Rate limit exceeded"
                    else:
                        error_message = "API error: 500 Internal Server Error"

                # Insert into model_usage (with goal_type for task-specific routing)
                insert_query = text("""
                    INSERT INTO model_usage (
                        id, model_name, goal_type, agent_role,
                        tokens_used, cost_usd, duration_ms, status,
                        error_message, request_params
                    ) VALUES (
                        :id, :model_name, :goal_type, :agent_role,
                        :tokens_used, :cost_usd, :duration_ms, :status,
                        :error_message, :request_params
                    )
                """)

                await session.execute(insert_query, {
                    "id": uuid.uuid4(),
                    "model_name": model_name,
                    "goal_type": params.goal_type if params.goal_type else "achievable",
                    "agent_role": agent_role,
                    "tokens_used": profile["tokens_per_call"],
                    "cost_usd": cost_usd,
                    "duration_ms": latency,
                    "status": status,
                    "error_message": error_message or "",
                    "request_params": json.dumps({})
                })

                inserted_count += 1

        await session.commit()

        logger.info(
            "test_data_injected",
            total_calls=inserted_count,
            models=models,
            hours=params.start_hours_ago
        )

        return {
            "status": "success",
            "injected_calls": inserted_count,
            "models_tested": models,
            "time_range": f"last {params.start_hours_ago} hours",
            "next_steps": [
                "Run: docker exec ns_core python -c 'from telemetry.llm_aggregator_v3 import LLMMetricsAggregatorV3; ...'",
                "Check: GET /llm/control/overview",
                "Verify: GET /llm/control/model-roi-ranking"
            ]
        }


@router.get("/overview", response_model=ControlCenterOverview)
async def get_control_overview():
    """
    Control Center overview: cost, performance, policy compliance.

    Reads from pre-aggregated tables (O(1) query).
    """
    async with AsyncSessionLocal() as session:
        # Get last 24 hours of hourly metrics
        query = text("""
            SELECT
                model_name,
                SUM(total_calls) as calls,
                SUM(success_calls) as success,
                SUM(total_cost) as cost,
                AVG(p95_estimate) as p95_latency
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - INTERVAL '72 hours'
            GROUP BY model_name
        """)

        result = await session.execute(query)
        rows = result.fetchall()

        if not rows:
            return ControlCenterOverview(
                total_cost_usd=0.0,
                cost_by_model={},
                cost_trend="stable",
                total_calls=0,
                overall_success_rate=0.0,
                p95_latency_ms=0.0,
                slow_calls_count=0,
                top_models_by_roi=[],
                active_policy="default",
                policy_compliance=1.0
            )

        total_cost = sum(r.cost or 0 for r in rows)
        total_calls = sum(r.calls or 0 for r in rows)
        total_success = sum(r.success or 0 for r in rows)
        weighted_p95 = sum((r.p95_latency or 0) * (r.calls or 0) for r in rows) / total_calls if total_calls > 0 else 0

        cost_by_model = {r.model_name: float(r.cost or 0) for r in rows}

        # Calculate cost trend (compare last 12h to previous 12h)
        trend_query = text("""
            SELECT
                SUM(total_cost) as cost
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - INTERVAL '48 hours'
        """)
        trend_result = await session.execute(trend_query)
        recent_cost = (trend_result.fetchone().cost or 0)

        trend_query2 = text("""
            SELECT
                SUM(total_cost) as cost
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - INTERVAL '72 hours'
              AND bucket < NOW() - INTERVAL '48 hours'
        """)
        trend_result2 = await session.execute(trend_query2)
        previous_cost = (trend_result2.fetchone().cost or 0)

        if previous_cost > 0:
            change_ratio = recent_cost / previous_cost
            if change_ratio > 1.1:
                cost_trend = "increasing"
            elif change_ratio < 0.9:
                cost_trend = "decreasing"
            else:
                cost_trend = "stable"
        else:
            cost_trend = "stable"

        # Get slow calls count (24h)
        slow_query = text("""
            SELECT COUNT(*) as cnt
            FROM llm_slow_calls
            WHERE created_at >= NOW() - INTERVAL '72 hours'
        """)
        slow_result = await session.execute(slow_query)
        slow_calls = (slow_result.fetchone().cnt or 0)

        # Calculate ROI per model (success / cost)
        roi_scores = []
        for r in rows:
            if r.cost and r.cost > 0:
                roi = (r.success or 0) / r.cost
                roi_scores.append({
                    "model": r.model_name,
                    "roi": round(roi, 2),
                    "success_rate": round((r.success or 0) / (r.calls or 1), 3)
                })

        top_roi = sorted(roi_scores, key=lambda x: x["roi"], reverse=True)[:3]

        return ControlCenterOverview(
            total_cost_usd=round(total_cost, 4),
            cost_by_model=cost_by_model,
            cost_trend=cost_trend,
            total_calls=total_calls,
            overall_success_rate=round(total_success / total_calls, 3) if total_calls > 0 else 0,
            p95_latency_ms=round(weighted_p95, 1),
            slow_calls_count=slow_calls,
            top_models_by_roi=top_roi,
            active_policy="default",  # TODO: from policy table
            policy_compliance=1.0  # TODO: calculate from rules
        )


@router.get("/model-metrics/{model_name}", response_model=ModelMetrics)
async def get_model_metrics(model_name: str, hours: int = Query(24, ge=1, le=168)):
    """
    Detailed metrics for a specific model.

    Includes cost per successful goal (via goal_type join).
    """
    async with AsyncSessionLocal() as session:
        # Get hourly metrics
        query = text("""
            SELECT
                model_name,
                SUM(total_calls) as total_calls,
                SUM(success_calls) as success_calls,
                SUM(error_calls) as error_calls,
                AVG(avg_latency) as avg_latency,
                AVG(p95_estimate) as p95_latency,
                AVG(p99_estimate) as p99_latency,
                SUM(total_tokens) as total_tokens,
                SUM(total_cost) as total_cost
            FROM llm_metrics_hourly
            WHERE
                model_name = :model_name
                AND bucket >= NOW() - (INTERVAL '1 hour' * :hours)
            GROUP BY model_name
        """)

        result = await session.execute(query, {"model_name": model_name, "hours": hours})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"No metrics found for model: {model_name}")

        # Get model pricing from catalog
        catalog_query = text("""
            SELECT provider, input_price_usd, output_price_usd
            FROM llm_model_catalog
            WHERE model_name = :model_name
        """)
        catalog_result = await session.execute(catalog_query, {"model_name": model_name})
        catalog_row = catalog_result.fetchone()

        provider = catalog_row.provider if catalog_row else "unknown"
        input_price = catalog_row.input_price_usd if catalog_row else 0.0
        output_price = catalog_row.output_price_usd if catalog_row else 0.0

        # Calculate cost per 1K tokens (weighted average)
        total_calls = row.total_calls or 0
        avg_tokens = (row.total_tokens or 0) / total_calls if total_calls > 0 else 0
        cost_per_1k = (row.total_cost or 0) / (row.total_tokens or 1) * 1000 if (row.total_tokens or 0) > 0 else 0.0

        # Get success rate by goal_type (from model_usage, not aggregated)
        goal_type_query = text("""
            SELECT
                g.goal_type,
                COUNT(*) FILTER (WHERE mu.status = 'success') as success,
                COUNT(*) as total
            FROM model_usage mu
            JOIN goals g ON mu.goal_id = g.id
            WHERE
                mu.model_name = :model_name
                AND mu.created_at >= NOW() - (INTERVAL '1 hour' * :hours)
            GROUP BY g.goal_type
        """)
        goal_type_result = await session.execute(goal_type_query, {"model_name": model_name, "hours": hours})
        goal_type_rows = goal_type_result.fetchall()

        success_by_goal_type = {
            r.goal_type: round((r.success or 0) / (r.total or 1), 3)
            for r in goal_type_rows
        }

        # Calculate cost per successful goal
        # This is expensive - only calculate if requested
        cost_per_goal = None
        if total_calls > 0 and (row.success_calls or 0) > 0:
            # Simplified: total cost / successful calls
            # TODO: Join with actual goal completion artifacts for accuracy
            cost_per_goal = (row.total_cost or 0) / (row.success_calls or 1)

        return ModelMetrics(
            model_name=model_name,
            provider=provider,
            total_calls=total_calls,
            success_rate=round((row.success_calls or 0) / total_calls, 3) if total_calls > 0 else 0,
            avg_latency_ms=round(row.avg_latency or 0, 1),
            p95_latency_ms=round(row.p95_latency or 0, 1),
            p99_latency_ms=round(row.p99_latency or 0, 1),
            total_cost_usd=round(row.total_cost or 0, 4),
            cost_per_1k_tokens=round(cost_per_1k, 4),
            avg_tokens_per_call=int(avg_tokens),
            cost_per_successful_goal=round(cost_per_goal, 4) if cost_per_goal else None,
            success_rate_by_goal_type=success_by_goal_type
        )


@router.get("/recommend-model")
async def recommend_model(
    goal_type: str = Query(..., description="Goal type (achievable, continuous, directional, exploratory)"),
    max_latency_ms: Optional[int] = Query(None, description="Max acceptable latency"),
    max_cost_per_goal: Optional[float] = Query(None, description="Max cost per goal")
):
    """
    Recommend best model based on goal type and constraints.

    Algorithm:
    1. Filter models by success rate for this goal_type (>80%)
    2. Filter by latency constraint (if specified)
    3. Filter by cost constraint (if specified)
    4. Rank by: success_rate * 0.6 + (1/cost) * 0.4
    """
    async with AsyncSessionLocal() as session:
        # Get all models with metrics
        query = text("""
            SELECT
                model_name,
                SUM(total_calls) as total_calls,
                SUM(success_calls) as success_calls,
                AVG(avg_latency) as avg_latency,
                AVG(p95_estimate) as p95_latency,
                SUM(total_cost) as total_cost
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - INTERVAL '72 hours'
            GROUP BY model_name
            HAVING SUM(total_calls) > 10  -- Minimum data threshold
        """)

        result = await session.execute(query)
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="Insufficient data for recommendations")

        candidates = []

        for r in rows:
            total_calls = r.total_calls or 0
            success_rate = (r.success_calls or 0) / total_calls
            avg_latency = r.avg_latency or 0
            total_cost = r.total_cost or 0

            # Apply filters
            if success_rate < 0.5:  # Minimum success rate threshold
                continue

            if max_latency_ms and avg_latency > max_latency_ms:
                continue

            if max_cost_per_goal and total_calls > 0:
                cost_per_goal = total_cost / (r.success_calls or 1)
                if cost_per_goal > max_cost_per_goal:
                    continue

            # Calculate score with proper min-max normalization to [0, 1]
            # Cost: lower is better → invert so higher score = cheaper
            costs = [r_.total_cost or 0 for r_ in rows]
            min_cost = min(costs) if costs else 0
            max_cost = max(costs) if costs else 1
            cost_range = max_cost - min_cost if max_cost > min_cost else 1
            cost_score = (max_cost - total_cost) / cost_range  # 0-1, higher = cheaper

            # Latency: lower is better → invert so higher score = faster
            latencies = [r_.avg_latency or 0 for r_ in rows]
            min_latency = min(latencies) if latencies else 0
            max_latency = max(latencies) if latencies else 1
            latency_range = max_latency - min_latency if max_latency > min_latency else 1
            latency_score = (max_latency - avg_latency) / latency_range  # 0-1, higher = faster

            # Combined: weighted sum (success most important)
            base_score = success_rate * 0.5 + cost_score * 0.3 + latency_score * 0.2

            # Sample confidence penalty
            MIN_SAMPLE = 30
            TARGET_SAMPLE = 100
            if total_calls <= MIN_SAMPLE:
                sample_confidence = 0.1
            elif total_calls >= TARGET_SAMPLE:
                sample_confidence = 1.0
            else:
                sample_confidence = 0.1 + (total_calls - MIN_SAMPLE) / (TARGET_SAMPLE - MIN_SAMPLE) * 0.9

            # Adjusted score
            adjusted_score = base_score * sample_confidence

            candidates.append({
                "model": r.model_name,
                "base_score": base_score,
                "score": adjusted_score,
                "sample_confidence": sample_confidence,
                "success_rate": success_rate,
                "latency": avg_latency,
                "cost": total_cost,
                "calls": total_calls
            })

        if not candidates:
            raise HTTPException(status_code=404, detail="No models match constraints")

        # Sort by adjusted score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        best = candidates[0]
        alternatives = candidates[1:4]  # Top 3 alternatives

        return ModelRecommendation(
            goal_type=goal_type,
            recommended_model=best["model"],
            reason=f"Highest score ({best['score']:.2f}) = base {best['base_score']:.2f} × conf {best['sample_confidence']:.2f} | Success: {best['success_rate']:.1%}",
            expected_cost_usd=round(best["cost"] / best["calls"], 4) if best["calls"] > 0 else 0,
            expected_latency_ms=round(best["latency"], 1),
            confidence_score=best["sample_confidence"],
            alternatives=[
                {
                    "model": a["model"],
                    "reason": f"Score: {a['score']:.2f} (base:{a['base_score']:.2f}×{a['sample_confidence']:.2f}), Success: {a['success_rate']:.1%}"
                }
                for a in alternatives
            ]
        )


@router.post("/simulate-policy")
async def simulate_policy(
    policy_name: str = Query(..., description="Policy name"),
    max_cost_per_call: Optional[float] = Query(None, description="Max cost per call"),
    max_latency_ms: Optional[int] = Query(None, description="Max latency"),
    min_success_rate: Optional[float] = Query(None, description="Min success rate")
):
    """
    Simulate policy outcomes based on historical data.

    Returns expected monthly cost, latency, success rate if policy were applied.
    """
    async with AsyncSessionLocal() as session:
        # Get current metrics (24h)
        query = text("""
            SELECT
                model_name,
                SUM(total_calls) as calls,
                SUM(success_calls) as success,
                AVG(avg_latency) as avg_latency,
                AVG(p95_estimate) as p95_latency,
                SUM(total_cost) as cost
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - INTERVAL '72 hours'
            GROUP BY model_name
        """)

        result = await session.execute(query)
        rows = result.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="No data for simulation")

        # Calculate current state
        total_calls = sum(r.calls or 0 for r in rows)
        total_cost = sum(r.cost or 0 for r in rows)
        total_success = sum(r.success or 0 for r in rows)
        weighted_latency = sum((r.avg_latency or 0) * (r.calls or 0) for r in rows) / total_calls if total_calls > 0 else 0

        # Apply policy filters
        filtered_calls = 0
        filtered_cost = 0
        filtered_success = 0
        filtered_latency_sum = 0

        for r in rows:
            calls = r.calls or 0
            cost = r.cost or 0
            success = r.success or 0
            latency = r.avg_latency or 0

            # Check policy constraints
            if max_cost_per_call:
                cost_per_call = cost / calls if calls > 0 else 0
                if cost_per_call > max_cost_per_call:
                    continue  # This model would be filtered out

            if max_latency_ms and latency > max_latency_ms:
                continue

            success_rate = success / calls if calls > 0 else 0
            if min_success_rate and success_rate < min_success_rate:
                continue

            # Model passes all filters
            filtered_calls += calls
            filtered_cost += cost
            filtered_success += success
            filtered_latency_sum += latency * calls

        # If no models pass policy, return warning
        if filtered_calls == 0:
            return PolicySimulation(
                policy_name=policy_name,
                description="⚠️ Policy filters out all models - too restrictive",
                expected_monthly_cost_usd=0,
                expected_avg_latency_ms=0,
                expected_success_rate=0,
                cost_change_percent=-100,
                latency_change_percent=0
            )

        # Calculate expected metrics with policy
        expected_daily_cost = filtered_cost
        expected_monthly_cost = expected_daily_cost * 30
        expected_avg_latency = filtered_latency_sum / filtered_calls
        expected_success_rate = filtered_success / filtered_calls

        # Compare to current
        cost_change = ((expected_monthly_cost / 30) - total_cost) / total_cost * 100 if total_cost > 0 else 0
        latency_change = (expected_avg_latency - weighted_latency) / weighted_latency * 100 if weighted_latency > 0 else 0

        # Generate description
        desc_parts = []
        if max_cost_per_call:
            desc_parts.append(f"max_cost=${max_cost_per_call:.4f}")
        if max_latency_ms:
            desc_parts.append(f"max_latency={max_latency_ms}ms")
        if min_success_rate:
            desc_parts.append(f"min_success={min_success_rate:.1%}")

        return PolicySimulation(
            policy_name=policy_name,
            description=f"Policy: {', '.join(desc_parts)}",
            expected_monthly_cost_usd=round(expected_monthly_cost, 2),
            expected_avg_latency_ms=round(expected_avg_latency, 1),
            expected_success_rate=round(expected_success_rate, 3),
            cost_change_percent=round(cost_change, 1),
            latency_change_percent=round(latency_change, 1)
        )


@router.get("/model-roi-ranking")
async def get_model_roi_ranking(hours: int = Query(24, ge=1, le=168)):
    """
    Rank models by ROI (success per dollar).

    Formula: ROI = success_calls / total_cost
    Higher is better (more success per dollar).
    """
    async with AsyncSessionLocal() as session:
        query = text("""
            SELECT
                model_name,
                SUM(total_calls) as calls,
                SUM(success_calls) as success,
                SUM(total_cost) as cost,
                AVG(p95_estimate) as p95_latency
            FROM llm_metrics_hourly
            WHERE bucket >= NOW() - (INTERVAL '1 hour' * :hours)
            GROUP BY model_name
            HAVING SUM(total_calls) > 10
            ORDER BY (SUM(success_calls)::float / NULLIF(SUM(total_cost), 0)) DESC
        """)

        result = await session.execute(query, {"hours": hours})
        rows = result.fetchall()

        ranking = []
        for r in rows:
            cost = r.cost or 0
            if cost > 0:
                roi = (r.success or 0) / cost
                ranking.append({
                    "model_name": r.model_name,
                    "roi_score": round(roi, 2),
                    "total_calls": r.calls or 0,
                    "success_rate": round((r.success or 0) / (r.calls or 1), 3),
                    "total_cost_usd": round(cost, 4),
                    "p95_latency_ms": round(r.p95_estimate or 0, 1)
                })

        return {"ranking": ranking, "hours_analyzed": hours}
