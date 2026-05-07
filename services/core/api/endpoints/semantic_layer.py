"""
Semantic Layer API - v7.2 Adaptive Router & Policy Learning

Endpoints for monitoring and controlling:
- Thompson Sampling Router (cheap/smart/loop strategies)
- Policy Learning (Q-table, context-aware routing)
- Context Signatures & Confidence Tracking
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/semantic", tags=["semantic-layer"])


# ============================================================================
# TS ROUTER STATUS
# ============================================================================

@router.get("/router/status")
async def get_router_status():
    """
    Get Thompson Sampling Router status and configuration.
    
    Returns current strategy, exploration rate, and router health metrics.
    """
    try:
        # Try to import the actual router
        from semantic.multi_llm_router import get_router
        ts_router = get_router()
        
        return {
            "status": "online",
            "version": "v7.2",
            "current_strategy": "thompson_sampling",
            "policy_bias_enabled": ts_router.policy_bias_enabled if hasattr(ts_router, 'policy_bias_enabled') else True,
            "confidence_threshold": getattr(ts_router, 'confidence_threshold', 0.3),
            "decay_factor": getattr(ts_router, 'decay_factor', 0.995),
            "context_signatures": len(ts_router.context_history) if hasattr(ts_router, 'context_history') else 0,
            "exploration_rate": getattr(ts_router, 'exploration_rate', 0.1),
            "arms": ["cheap", "smart", "loop"],
            "total_decisions": getattr(ts_router, 'total_decisions', 0),
        }
    except ImportError:
        # Router not available, return defaults
        return {
            "status": "offline",
            "version": "v7.2",
            "current_strategy": "thompson_sampling",
            "policy_bias_enabled": True,
            "confidence_threshold": 0.3,
            "decay_factor": 0.995,
            "context_signatures": 0,
            "exploration_rate": 0.1,
            "arms": ["cheap", "smart", "loop"],
            "total_decisions": 0,
        }
    except Exception as e:
        return {
            "status": "error",
            "version": "v7.2",
            "error": str(e),
            "current_strategy": "thompson_sampling",
            "policy_bias_enabled": True,
            "confidence_threshold": 0.3,
            "decay_factor": 0.995,
            "context_signatures": 0,
            "exploration_rate": 0.1,
            "arms": ["cheap", "smart", "loop"],
            "total_decisions": 0,
        }


@router.get("/router/stats")
async def get_router_stats():
    """
    Get Thompson Sampling Router statistics.
    
    Returns arm statistics, success rates, and selection counts.
    """
    try:
        from semantic.multi_llm_router import get_router
        ts_router = get_router()
        
        # Get arm statistics
        arm_stats = {}
        if hasattr(ts_router, 'arms'):
            for arm_name, arm in ts_router.arms.items():
                arm_stats[arm_name] = {
                    "alpha": getattr(arm, 'alpha', 1),
                    "beta": getattr(arm, 'beta', 1),
                    "success_rate": getattr(arm, 'success_rate', 0.5),
                    "selections": getattr(arm, 'selections', 0),
                }
        
        return {
            "total_decisions": getattr(ts_router, 'total_decisions', 0),
            "arms": arm_stats,
            "context_signatures": len(ts_router.context_history) if hasattr(ts_router, 'context_history') else 0,
        }
    except Exception as e:
        return {
            "error": str(e),
            "total_decisions": 0,
            "arms": {},
            "context_signatures": 0,
        }


# ============================================================================
# POLICY LEARNING STATUS
# ============================================================================

@router.get("/policy/status")
async def get_policy_status():
    """
    Get Policy Learning status (Q-table).
    
    Returns Q-table size, confidence metrics, and learning progress.
    """
    try:
        from semantic.multi_llm_router import get_router
        ts_router = get_router()
        
        # Get policy table
        if hasattr(ts_router, 'policy_table'):
            policy_table = ts_router.policy_table
            q_table_size = len(policy_table.q_table) if hasattr(policy_table, 'q_table') else 0
            total_visits = sum(
                entry.visits if hasattr(entry, 'visits') else 0
                for entry in policy_table.q_table.values()
            ) if hasattr(policy_table, 'q_table') else 0
            
            return {
                "status": "online",
                "q_table_size": q_table_size,
                "total_entries": q_table_size,
                "total_visits": total_visits,
                "bias_weight": getattr(policy_table, 'POLICY_BIAS_WEIGHT', 0.3),
                "confidence_threshold": getattr(policy_table, 'CONFIDENCE_THRESHOLD', 0.3),
                "decay_factor": getattr(policy_table, 'decay_factor', 0.995),
            }
        else:
            return {
                "status": "offline",
                "q_table_size": 0,
                "total_entries": 0,
                "total_visits": 0,
                "bias_weight": 0.3,
                "confidence_threshold": 0.3,
                "decay_factor": 0.995,
            }
    except ImportError:
        return {
            "status": "offline",
            "q_table_size": 0,
            "total_entries": 0,
            "total_visits": 0,
            "bias_weight": 0.3,
            "confidence_threshold": 0.3,
            "decay_factor": 0.995,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "q_table_size": 0,
            "total_entries": 0,
            "total_visits": 0,
            "bias_weight": 0.3,
            "confidence_threshold": 0.3,
            "decay_factor": 0.995,
        }


@router.get("/policy/q-table")
async def get_q_table(context_prefix: Optional[str] = None):
    """
    Get Q-table entries (optionally filtered by context prefix).
    
    Returns learned policy entries with confidence and Q-values.
    """
    try:
        from semantic.multi_llm_router import get_router
        ts_router = get_router()
        
        if hasattr(ts_router, 'policy_table') and hasattr(ts_router.policy_table, 'q_table'):
            q_table = ts_router.policy_table.q_table
            
            # Filter by context prefix if provided
            if context_prefix:
                q_table = {
                    k: v for k, v in q_table.items()
                    if k.startswith(context_prefix)
                }
            
            # Serialize entries
            entries = []
            for context_key, entry in list(q_table.items())[:100]:  # Limit to 100
                entries.append({
                    "context_key": context_key,
                    "q_value": entry.q_value if hasattr(entry, 'q_value') else 0,
                    "visits": entry.visits if hasattr(entry, 'visits') else 0,
                    "confidence": entry.confidence if hasattr(entry, 'confidence') else 0,
                })
            
            return {
                "entries": entries,
                "total": len(entries),
            }
        else:
            return {
                "entries": [],
                "total": 0,
            }
    except Exception as e:
        return {
            "error": str(e),
            "entries": [],
            "total": 0,
        }


# ============================================================================
# CONTEXT SIGNATURES
# ============================================================================

@router.get("/context/signatures")
async def get_context_signatures():
    """
    Get all context signatures seen by the router.
    
    Returns unique context keys used for policy learning.
    """
    try:
        from semantic.multi_llm_router import get_router
        ts_router = get_router()
        
        if hasattr(ts_router, 'context_history'):
            signatures = list(ts_router.context_history.keys()) if isinstance(ts_router.context_history, dict) else []
            return {
                "signatures": signatures[:100],  # Limit to 100
                "total": len(signatures),
            }
        else:
            return {
                "signatures": [],
                "total": 0,
            }
    except Exception as e:
        return {
            "error": str(e),
            "signatures": [],
            "total": 0,
        }


# ============================================================================
# CONTROL OPERATIONS
# ============================================================================

class RouterControlRequest(BaseModel):
    action: str  # "reset", "pause", "resume", "adjust_exploration"
    params: dict = {}


@router.post("/router/control")
async def control_router(req: RouterControlRequest):
    """
    Control operations for the TS Router.
    
    Actions:
    - reset: Reset router state
    - pause: Pause learning
    - resume: Resume learning
    - adjust_exploration: Adjust exploration rate
    """
    try:
        from semantic.multi_llm_router import get_router
        ts_router = get_router()
        
        if req.action == "reset":
            # Reset router state
            if hasattr(ts_router, 'reset'):
                ts_router.reset()
            return {"status": "success", "message": "Router reset complete"}
        
        elif req.action == "adjust_exploration":
            new_rate = req.params.get("exploration_rate", 0.1)
            if hasattr(ts_router, 'exploration_rate'):
                ts_router.exploration_rate = new_rate
            return {"status": "success", "message": f"Exploration rate set to {new_rate}"}
        
        else:
            return {"status": "error", "message": f"Unknown action: {req.action}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class PolicyControlRequest(BaseModel):
    action: str  # "reset", "adjust_weight", "decay"
    params: dict = {}


@router.post("/policy/control")
async def control_policy(req: PolicyControlRequest):
    """
    Control operations for Policy Learning.

    Actions:
    - reset: Clear Q-table
    - adjust_weight: Change policy bias weight
    - decay: Apply decay to Q-values
    """
    try:
        from semantic.multi_llm_router import get_router
        ts_router = get_router()

        if hasattr(ts_router, 'policy_table'):
            policy_table = ts_router.policy_table

            if req.action == "reset":
                if hasattr(policy_table, 'reset'):
                    policy_table.reset()
                return {"status": "success", "message": "Policy reset complete"}

            elif req.action == "adjust_weight":
                new_weight = req.params.get("weight", 0.3)
                if hasattr(policy_table, 'POLICY_BIAS_WEIGHT'):
                    policy_table.POLICY_BIAS_WEIGHT = new_weight
                return {"status": "success", "message": f"Bias weight set to {new_weight}"}

            elif req.action == "decay":
                if hasattr(policy_table, 'decay'):
                    policy_table.decay()
                return {"status": "success", "message": "Decay applied"}

        return {"status": "error", "message": "Policy table not available"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================================
# PLAN MEMORY (Hierarchical MAB)
# ============================================================================

@router.get("/plan-memory/status")
async def get_plan_memory_status():
    """
    Get Plan Memory status - Hierarchical Multi-Armed Bandit.

    Returns current mode, locked strategy, strategy scores, and evolution state.
    """
    try:
        from semantic.plan_memory import PlanMemory, get_plan_memory
        pm = get_plan_memory()

        strategies = pm.get_all_strategies() if hasattr(pm, 'get_all_strategies') else []
        mode = pm.get_mode() if hasattr(pm, 'get_mode') else 'unknown'
        locked = pm.get_locked_strategy() if hasattr(pm, 'get_locked_strategy') else None

        return {
            "status": "online",
            "mode": mode,
            "locked_strategy": locked,
            "total_strategies": len(strategies),
            "artifact_cache_size": len(pm.artifact_cache) if hasattr(pm, 'artifact_cache') else 0,
            "evolution_count": pm.evolution_count if hasattr(pm, 'evolution_count') else 0,
            "total_selections": pm.total_selections if hasattr(pm, 'total_selections') else 0,
        }
    except Exception as e:
        return {
            "status": "offline",
            "mode": "unknown",
            "locked_strategy": None,
            "total_strategies": 0,
            "artifact_cache_size": 0,
            "evolution_count": 0,
            "total_selections": 0,
            "error": str(e),
        }


@router.get("/plan-memory/strategies")
async def get_plan_memory_strategies(limit: int = 50):
    """
    Get strategy scores from Plan Memory.

    Returns strategy names with alpha/beta, success rates, and selection counts.
    """
    try:
        from semantic.plan_memory import get_plan_memory
        pm = get_plan_memory()

        strategies = []
        if hasattr(pm, 'abstract_strategies'):
            for name, arm in list(pm.abstract_strategies.items())[:limit]:
                strategies.append({
                    "name": name,
                    "alpha": getattr(arm, 'alpha', 1),
                    "beta": getattr(arm, 'beta', 1),
                    "success_rate": getattr(arm, 'success_rate', 0.5),
                    "selections": getattr(arm, 'selections', 0),
                    "level": "abstract",
                })

        if hasattr(pm, 'concrete_strategies'):
            for name, arm in list(pm.concrete_strategies.items())[:limit]:
                strategies.append({
                    "name": name,
                    "alpha": getattr(arm, 'alpha', 1),
                    "beta": getattr(arm, 'beta', 1),
                    "success_rate": getattr(arm, 'success_rate', 0.5),
                    "selections": getattr(arm, 'selections', 0),
                    "level": "concrete",
                })

        return {
            "strategies": strategies,
            "total": len(strategies),
        }
    except Exception as e:
        return {
            "strategies": [],
            "total": 0,
            "error": str(e),
        }


# ============================================================================
# CAPABILITY SELECTOR (UCB1)
# ============================================================================

@router.get("/capability/selector/stats")
async def get_capability_selector_stats():
    """
    Get Capability Selector stats - UCB1-based skill selection.

    Returns capability-to-skill mappings, UCB1 scores, exploration bonuses.
    """
    try:
        from capability.selector import CapabilitySelector, get_selector
        selector = get_selector()

        stats = selector.get_stats() if hasattr(selector, 'get_stats') else {}

        return {
            "status": "online",
            "capabilities": stats.get("capabilities", {}),
            "total_selections": stats.get("total_selections", 0),
            "exploration_bonus_active": stats.get("exploration_bonus_active", True),
            "ucb_exploration_constant": getattr(selector, 'UCB_EXPLORATION_CONSTANT', 1.0),
        }
    except Exception as e:
        return {
            "status": "offline",
            "capabilities": {},
            "total_selections": 0,
            "exploration_bonus_active": False,
            "ucb_exploration_constant": 1.0,
            "error": str(e),
        }


# ============================================================================
# EXECUTION ORCHESTRATOR
# ============================================================================

@router.get("/orchestrator/status")
async def get_orchestrator_status():
    """
    Get Execution Orchestrator status.

    Returns current state, phase status, and telemetry events.
    """
    try:
        from semantic.execution_orchestrator import get_orchestrator
        orch = get_orchestrator()

        return {
            "status": "online",
            "current_phase": orch.current_phase if hasattr(orch, 'current_phase') else 'idle',
            "total_executions": orch.total_executions if hasattr(orch, 'total_executions') else 0,
            "successful_executions": orch.successful_executions if hasattr(orch, 'successful_executions') else 0,
            "failed_executions": orch.failed_executions if hasattr(orch, 'failed_executions') else 0,
        }
    except Exception as e:
        return {
            "status": "offline",
            "current_phase": 'idle',
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "error": str(e),
        }


@router.get("/orchestrator/telemetry")
async def get_orchestrator_telemetry(limit: int = 50):
    """
    Get Execution Orchestrator telemetry events.

    Returns recent telemetry events from the orchestrator.
    """
    try:
        from semantic.execution_orchestrator import get_orchestrator
        orch = get_orchestrator()

        events = []
        if hasattr(orch, 'telemetry_events'):
            events = list(orch.telemetry_events)[-limit:]

        return {
            "events": events,
            "total": len(events),
        }
    except Exception as e:
        return {
            "events": [],
            "total": 0,
            "error": str(e),
        }
