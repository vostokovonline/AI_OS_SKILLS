"""
Event-Driven Pipeline v1

Заменяет polling scheduler на event-driven architecture.

BEFORE: polling every N seconds
AFTER:  real-time event handling

Benefits:
- No polling overhead
- Faster response (ms vs seconds)
- Declarative handlers
- Easy to trace/debug
"""
from typing import Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio


class PipelineEventType(str, Enum):
    """Pipeline events"""
    GOAL_CREATED = "goal.created"
    GOAL_ACTIVATED = "goal.activated"
    GOAL_PENDING = "goal.pending"
    GOAL_COMPLETED = "goal.completed"
    GOAL_FAILED = "goal.failed"
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_STUCK = "execution.stuck"


@dataclass
class PipelineEvent:
    """Pipeline event"""
    event_type: PipelineEventType
    goal_id: str | None = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "pipeline"


class PipelineHandler:
    """Base handler for pipeline events"""
    
    async def handle(self, event: PipelineEvent) -> bool:
        """Handle event. Return True if handled successfully."""
        raise NotImplementedError


class EventDrivenPipeline:
    """
    Event-Driven Pipeline replaces polling scheduler.
    
    Usage:
        pipeline = EventDrivenPipeline()
        
        # Register handlers
        pipeline.on(PipelineEventType.GOAL_PENDING, ResumeHandler())
        pipeline.on(PipelineEventType.GOAL_ACTIVATED, ExecuteHandler())
        pipeline.on(PipelineEventType.EXECUTION_STUCK, RecoveryHandler())
        
        # Emit events (from anywhere in system)
        await pipeline.emit(PipelineEvent(
            event_type=PipelineEventType.GOAL_CREATED,
            goal_id="..."
        ))
    """
    
    def __init__(self):
        self._handlers: Dict[PipelineEventType, List[PipelineHandler]] = {}
        self._event_history: List[PipelineEvent] = []
        self._max_history = 1000
        
    def on(self, event_type: PipelineEventType, handler: PipelineHandler):
        """Register handler for event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        
    async def emit(self, event: PipelineEvent):
        """Emit event - triggers all registered handlers"""
        self._event_history.append(event)
        
        # Trim history
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        handlers = self._handlers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                # Don't crash pipeline on handler error
                pass
                
    def get_history(self, event_type: PipelineEventType | None = None, limit: int = 100) -> List[PipelineEvent]:
        """Get event history"""
        if event_type:
            return [e for e in self._event_history if e.event_type == event_type][-limit:]
        return self._event_history[-limit:]


# Global pipeline instance
_pipeline: EventDrivenPipeline | None = None


def get_pipeline() -> EventDrivenPipeline:
    """Get global pipeline instance"""
    global _pipeline
    if _pipeline is None:
        _pipeline = EventDrivenPipeline()
        _setup_default_handlers(_pipeline)
    return _pipeline


def _setup_default_handlers(pipeline: EventDrivenPipeline):
    """Setup default handlers"""
    from application.use_cases.resume_pending_goals import ResumePendingGoalsUseCase
    from application.use_cases.execute_ready_goals import ExecuteReadyGoalsUseCase
    from infrastructure.uow import create_uow_provider
    from goal_executor_v2 import goal_executor_v2
    from application.bulk_engine import BulkTransitionEngine
    
    get_uow = create_uow_provider()
    bulk_engine = BulkTransitionEngine()
    
    # Resume handler - activates pending goals when dependencies satisfied
    class ResumeOnPendingHandler(PipelineHandler):
        async def handle(self, event: PipelineEvent) -> bool:
            use_case = ResumePendingGoalsUseCase(get_uow, bulk_engine)
            result = await use_case.run(actor="event_pipeline")
            return result.activated > 0
    
    # Execute handler - executes activated goals immediately
    class ExecuteOnActivatedHandler(PipelineHandler):
        async def handle(self, event: PipelineEvent) -> bool:
            use_case = ExecuteReadyGoalsUseCase(
                get_uow, goal_executor_v2, bulk_engine,
                arbitrator=None, capital_allocator=None, event_bus=None
            )
            result = await use_case.run(limit=5, actor="event_pipeline")
            return result.completed > 0
    
    pipeline.on(PipelineEventType.GOAL_PENDING, ResumeOnPendingHandler())
    pipeline.on(PipelineEventType.GOAL_ACTIVATED, ExecuteOnActivatedHandler())


__all__ = [
    "EventDrivenPipeline",
    "PipelineEvent",
    "PipelineEventType",
    "PipelineHandler",
    "get_pipeline",
]