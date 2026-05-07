"""
Arbitration API Endpoints - Dashboard integration.

Provides real-time access to decision-making metrics and history.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from application.arbitration import ArbitrationResult, InMemoryArbitrationLog
from application.arbitration.capital_allocator import CapitalAllocator, FixedBudgetAllocator


router = APIRouter(prefix="/arbitration", tags=["arbitration"])

# Global instances (injected by main.py)
_arbitration_log: InMemoryArbitrationLog | None = None
_capital_allocator: CapitalAllocator | None = None


def set_arbitration_log(log: InMemoryArbitrationLog) -> None:
    """Inject arbitration log (called from main.py)."""
    global _arbitration_log
    _arbitration_log = log


def set_capital_allocator(allocator: CapitalAllocator) -> None:
    """Inject capital allocator (called from main.py)."""
    global _capital_allocator
    _capital_allocator = allocator


@router.get("/latest")
async def get_latest_arbitration() -> dict:
    """
    Get most recent arbitration decision.

    Returns:
        Latest arbitration result with selected/rejected intents
    """
    if _arbitration_log is None:
        return {"error": "Arbitration not initialized"}

    result = _arbitration_log.get_latest()
    if result is None:
        raise HTTPException(status_code=404, detail="No arbitration decisions yet")

    return result.to_dict()


@router.get("/history")
async def get_arbitration_history(limit: int = 10) -> List[dict]:
    """
    Get recent arbitration history.

    Args:
        limit: Number of recent decisions to return

    Returns:
        List of arbitration results (newest first)
    """
    if _arbitration_log is None:
        return []

    history = _arbitration_log.get_recent(limit)
    return [r.to_dict() for r in reversed(history)]


@router.get("/metrics")
async def get_arbitration_metrics() -> dict:
    """
    Get aggregated arbitration metrics.

    Computes statistics over recent decisions:
        - Average selection rate
        - Total intents processed
        - Current budget
        - Average utility per selected intent
    """
    if _arbitration_log is None:
        return {
            "error": "Arbitration not initialized",
            "selection_rate_24h": 0.0,
            "total_processed": 0,
            "current_budget": 0.0,
        }

    history = _arbitration_log.get_recent(100)  # Last 100 decisions

    if not history:
        return {
            "selection_rate_24h": 0.0,
            "total_processed": 0,
            "current_budget": await _capital_allocator.current_budget() if _capital_allocator else 0.0,
            "avg_utility": 0.0,
            "avg_cost": 0.0,
        }

    # Compute metrics
    total_intents = sum(r.total_count for r in history)
    total_selected = sum(len(r.selected) for r in history)
    total_utility = sum(r.total_utility for r in history)
    total_cost = sum(r.total_cost for r in history)

    selection_rate = total_selected / total_intents if total_intents > 0 else 0.0
    avg_utility = total_utility / total_selected if total_selected > 0 else 0.0
    avg_cost = total_cost / total_selected if total_selected > 0 else 0.0

    current_budget = await _capital_allocator.current_budget() if _capital_allocator else 0.0

    return {
        "selection_rate_24h": selection_rate,
        "total_processed_24h": total_intents,
        "total_selected_24h": total_selected,
        "total_rejected_24h": total_intents - total_selected,
        "avg_utility_per_selected": avg_utility,
        "avg_cost_per_selected": avg_cost,
        "current_budget": current_budget,
        "recent_decisions_count": len(history),
    }


@router.get("/budget")
async def get_current_budget() -> dict:
    """
    Get current available budget.

    Returns:
        Current budget for execution cycle
    """
    if _capital_allocator is None:
        return {"error": "Capital allocator not initialized", "budget": 0.0}

    budget = await _capital_allocator.current_budget()
    return {
        "budget": budget,
        "currency": "execution_units",
        "allocator_type": type(_capital_allocator).__name__,
    }
