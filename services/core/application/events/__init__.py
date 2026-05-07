"""
Domain Events Module

Immutable facts about what happened in the system.
Used for decoupling causality (reactions) from execution.
"""
from .execution_events import (
    GoalExecutionFinished,
    BatchExecutionCompleted
)
from .bus import EventBus, get_event_bus

__all__ = [
    "GoalExecutionFinished",
    "BatchExecutionCompleted",
    "EventBus",
    "get_event_bus",
]
