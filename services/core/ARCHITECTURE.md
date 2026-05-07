# Goal System Architecture v2.0

## Executive Summary

Clean, linear execution flow with clear separation of concerns. No cycles. No ambiguity.

## Core Principle

> **Only Orchestrator has the right to change goal state.**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                            │
│                   (api/endpoints/goals.py)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Single entry point
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator (V1)                         │
│                   (goal_executor.py)                         │
│                                                              │
│  Responsibilities:                                           │
│  • Entry point for ALL goal execution                       │
│  • Decides: atomic vs complex                               │
│  • Manages goal state via transition_goal()                 │
│  • Complex goals: decomposition + agent graph               │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ Delegation (one-way)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  Atomic Engine (V2)                          │
│                 (goal_executor_v2.py)                        │
│                                                              │
│  Responsibilities:                                           │
│  • Execute ONLY atomic goals                                │
│  • Skills + Artifacts + Verification                        │
│  • NO state management (Orchestrator decides)               │
│  • Raises ValueError if non-atomic                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ Result + Artifacts
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              GoalTransitionService                           │
│         (goal_transition_service.py)                         │
│                                                              │
│  Responsibilities:                                           │
│  • SINGLE point for state changes                           │
│  • Validates invariants                                     │
│  • Logs all transitions                                     │
│  • Only component with _status write access                 │
└─────────────────────────────────────────────────────────────┘
```

## Execution Flow

### 1. Goal Creation
```python
API.create_goal() 
  → goal_executor.create_goal()
    → Creates goal with status="pending"
    → Returns goal_id
```

### 2. Goal Execution
```python
API.execute_goal()
  → goal_executor.execute_goal()  # Orchestrator
    ├── IF atomic:
    │   └── goal_executor_v2.execute_goal()  # Atomic Engine
    │       → Execute skill
    │       → Return result + artifacts
    │
    ├── IF complex:
    │   └── Decomposition
    │   └── Agent graph execution
    │   └── Coordinate children
    │
    └── transition_goal()  # State change
```

### 3. State Transitions
```python
# ONLY via GoalTransitionService
result = await transition_goal(
    goal_id=goal_id,
    to_state="done",  # or "active", "blocked", etc.
    reason="All children completed",
    actor="goal_executor"
)

# Direct assignment is FORBIDDEN:
goal.status = "done"  # ❌ RuntimeError!
```

## Component Contracts

### Orchestrator (V1)

```python
class GoalExecutor:
    """
    Single entry point for goal execution.
    
    Responsibilities:
    - Route atomic goals to V2
    - Execute complex goals via agent graph
    - Manage state transitions
    - Coordinate subgoals
    """
    
    async def execute_goal(self, goal_id: str, session_id: str) -> dict:
        """
        Main entry point.
        
        Flow:
        1. Load goal
        2. Check contract
        3. IF atomic → delegate to V2
        4. IF complex → execute via agent graph
        5. Update state via transition_goal()
        6. Return result
        """
        pass
```

### Atomic Engine (V2)

```python
class GoalExecutorV2:
    """
    Dumb atomic goal executor.
    
    Responsibilities:
    - Execute skills for atomic goals ONLY
    - Return artifacts
    - NO state decisions
    
    Raises:
        ValueError: If goal is not atomic
    """
    
    async def execute_goal(self, goal_id: str, session_id: str) -> dict:
        """
        Execute atomic goal.
        
        Raises:
            ValueError: If not goal.is_atomic
        """
        if not goal.is_atomic:
            raise ValueError("V2 only handles atomic goals")
        
        # Execute skill
        # Return result
        pass
```

### State Manager

```python
# GoalTransitionService is the ONLY way
async def transition_goal(
    goal_id: str,
    to_state: str,
    reason: str,
    actor: str = "system"
) -> dict:
    """
    Single gate for all state changes.
    
    Validates:
    - Invariants (continuous can't be "done")
    - Transitions (valid state machine)
    - Audits all changes
    """
    pass
```

## State Machine

```
                    ┌──────────┐
         ┌─────────│  pending │◄────────┐
         │         └────┬─────┘         │
         │              │               │
         │              ▼               │
    ┌────┴────┐    ┌──────────┐   ┌────┴────┐
    │ blocked │◄───│  active  │──►│  done   │
    └────┬────┘    └────┬─────┘   └─────────┘
         │              │
         │              ▼
         │         ┌──────────┐
         └────────►│incomplete│
                   └──────────┘
```

**Rules:**
- `continuous` goals can never be "done" → use "ongoing"
- `directional` goals can never be "done" → use "active"
- Only `achievable` goals can reach "done"

## Migration Path

### Current State
- ✅ Dead code removed (enhanced_goal_executor.py)
- ✅ Cycle broken (V2 → V1 delegation removed)
- ✅ API simplified (only V1 entry point)
- ⚠️ Status violations remain (to be fixed)

### Next Steps
1. Fix 7 violations in goal_executor.py
2. Fix 6 violations in goal_executor_v2.py
3. Fix evaluators
4. Add comprehensive tests

## Testing

```python
# Test atomic flow
async def test_atomic_goal():
    goal_id = await create_goal(
        title="Write file",
        is_atomic=True
    )
    
    result = await execute_goal(goal_id)
    
    assert result["status"] == "success"
    assert len(result["artifacts"]) > 0

# Test complex flow  
async def test_complex_goal():
    goal_id = await create_goal(
        title="Build project",
        is_atomic=False
    )
    
    result = await execute_goal(goal_id)
    
    # Should decompose and execute children
    subgoals = await get_subgoals(goal_id)
    assert len(subgoals) > 0

# Test state protection
async def test_direct_assignment_blocked():
    goal = await get_goal(goal_id)
    
    with pytest.raises(RuntimeError):
        goal.status = "done"  # Should fail
```

## Anti-Patterns (Forbidden)

### ❌ Direct State Assignment
```python
goal.status = "done"  # FORBIDDEN
goal._status = "done"  # FORBIDDEN (outside transition service)
```

### ❌ Multiple State Managers
```python
# Don't do this:
executor1.change_state()
evaluator.change_state()
aggregator.change_state()

# Do this:
transition_goal(goal_id, state, reason, actor)
```

### ❌ Cyclic Dependencies
```python
# V1 → V2 → V1  # FORBIDDEN
# V1 → V2 only (one-way)
```

### ❌ Smart Components
```python
# V2 should be DUMB:
if goal.is_atomic:  # ✅ Only this check
    execute()
else:
    raise ValueError()  # ✅ Fail fast

# Don't add logic:
if goal.is_atomic:
    execute()
elif some_condition:  # ❌ NO!
    delegate()
```

## Success Metrics

- ✅ 1 entry point (Orchestrator)
- ✅ 0 cyclic dependencies
- ✅ 1 state manager (transition service)
- ✅ All violations fixed
- ✅ Test coverage > 80%

## Version History

- **v1.0**: Chaos (3 executors, cycles, violations)
- **v2.0**: Clean architecture (this document)

---

**Author:** AI-OS Core Team  
**Date:** 2026-02-12  
**Status:** Architecture Defined / Implementation In Progress
