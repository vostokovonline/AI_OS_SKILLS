"""
Execution V3 Metrics Endpoint

Provides monitoring metrics for Phase 2A rollout.

Author: AI-OS Architecture v3.1
Date: 2026-03-03
Status: Phase 2A - 10% Rollout
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from sqlalchemy import text
from database import AsyncSessionLocal
from execution_v3 import get_baseline_observer, SuspicionChecks

router = APIRouter(prefix="/execution-v3", tags=["execution-v3"])


@router.get("/metrics")
async def get_execution_metrics():
    """
    Get Phase 2A execution metrics.

    Returns:
        - total_executions: Total goals executed
        - v3_executions: Goals executed with V3
        - legacy_executions: Goals executed with legacy
        - escalation_rate: Percentage of escalated goals
        - blocked_fallback_rate: Percentage of blocked fallbacks
        - success_rate: Percentage of successful executions
        - p50_metrics: Median values for key metrics
        - p95_metrics: 95th percentile values
    """
    async with AsyncSessionLocal() as session:
        # Only count recent executions (last 24 hours) to avoid test data pollution
        result = await session.execute(
            text("""
                SELECT COUNT(*)
                FROM goals
                WHERE execution_engine IS NOT NULL
                  AND created_at > NOW() - INTERVAL '24 hours'
            """)
        )
        total_executions = result.scalar() or 0

        # V3 vs Legacy split (last 24 hours only)
        result = await session.execute(
            text("""
                SELECT
                    execution_engine,
                    COUNT(*) as count
                FROM goals
                WHERE execution_engine IS NOT NULL
                  AND created_at > NOW() - INTERVAL '24 hours'
                GROUP BY execution_engine
            """)
        )
        rows = result.fetchall()
        v3_executions = next((r[1] for r in rows if r[0] == 'v3'), 0)
        legacy_executions = next((r[1] for r in rows if r[0] == 'legacy'), 0)

        # Escalation rate (last 24 hours only)
        result = await session.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'incomplete') as failed,
                    COUNT(*) as total
                FROM goals
                WHERE execution_engine = 'v3'
                  AND created_at > NOW() - INTERVAL '24 hours'
            """)
        )
        row = result.fetchone()
        failed, v3_total = row
        escalation_rate = (failed / v3_total * 100) if v3_total > 0 else 0

        # Success rate (last 24 hours only)
        result = await session.execute(
            text("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'done') as success,
                    COUNT(*) as total
                FROM goals
                WHERE execution_engine = 'v3'
                  AND created_at > NOW() - INTERVAL '24 hours'
            """)
        )
        row = result.fetchone()
        success, v3_total = row
        success_rate = (success / v3_total * 100) if v3_total > 0 else 0

        # Blocked fallback rate (estimated)
        # This would need to be tracked in execution metadata
        blocked_fallback_rate = 0  # Placeholder

        metrics = {
            "total_executions": total_executions,
            "v3_executions": v3_executions,
            "legacy_executions": legacy_executions,
            "v3_percentage": (v3_executions / total_executions * 100) if total_executions > 0 else 0,
            "escalation_rate": round(escalation_rate, 2),
            "blocked_fallback_rate": round(blocked_fallback_rate, 2),
            "success_rate": round(success_rate, 2),
        }

        # Baseline summary
        observer = get_baseline_observer()
        baseline = observer.get_summary()
        metrics["baseline"] = baseline

        # Suspicion checks
        warnings = SuspicionChecks.check_system_health(metrics)
        metrics["warnings"] = warnings

        return metrics


@router.get("/baseline")
async def get_baseline():
    """Get baseline observation data."""
    observer = get_baseline_observer()
    return observer.get_summary()


@router.get("/health")
async def health_check():
    """
    Health check for Execution V3.

    Returns:
        - status: "healthy" | "observation" | "degraded"
        - baseline_ready: Whether 48h observation period is complete
        - feature_flags: Current feature flag values
    """
    from execution_v3 import (
        ENABLE_EXECUTION_V3,
        EXECUTION_V3_PERCENTAGE,
        BASELINE_OBSERVATION_HOURS,
    )

    observer = get_baseline_observer()
    baseline = observer.get_summary()
    baseline_ready = baseline.get("status") == "baseline_ready"

    status = "observation"
    if baseline_ready:
        status = "healthy" if ENABLE_EXECUTION_V3 else "ready_to_enable"

    return {
        "status": status,
        "baseline_ready": baseline_ready,
        "feature_flags": {
            "ENABLE_EXECUTION_V3": ENABLE_EXECUTION_V3,
            "EXECUTION_V3_PERCENTAGE": EXECUTION_V3_PERCENTAGE,
            "BASELINE_OBSERVATION_HOURS": BASELINE_OBSERVATION_HOURS,
        },
        "baseline_hours_elapsed": baseline.get("hours_elapsed", 0),
    }
