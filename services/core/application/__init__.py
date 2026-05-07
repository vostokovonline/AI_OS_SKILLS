"""
Application Layer - Business Use Case Orchestration

This layer contains orchestrators that coordinate domain operations
into complete use cases. All application services:
- Accept UnitOfWork from caller (never create own transactions)
- Never commit (caller owns transaction boundary)
- Use domain services for business logic
- Use repositories for data access
- Work on snapshots, not ORM objects (for bulk operations)
- Dispatch to queue, never HTTP (for execution)
"""

from .bulk_transition_engine import (
    BulkTransitionEngine,
    StateTransitionPlanner,
    bulk_transition_engine
)

from .bulk.types import (
    GoalSnapshot,
    Transition,
    BulkTransitionPlan
)

from .goal_dispatcher import (
    GoalDispatcher,
    configure_dispatcher,
    get_dispatcher,
    goal_dispatcher
)

__all__ = [
    "BulkTransitionEngine",
    "StateTransitionPlanner",
    "bulk_transition_engine",
    # Bulk types (snapshot-based)
    "GoalSnapshot",
    "Transition",
    "BulkTransitionPlan",
    # Dispatcher (queue-based execution)
    "GoalDispatcher",
    "configure_dispatcher",
    "get_dispatcher",
    "goal_dispatcher",
]
