"""
Trace Collector - Подписывается на events и сохраняет в Trace Store

Это мост между Event Bus и Trace Store.
"""
from typing import Any


class TraceCollector:
    """
    Подписывается на все execution events и сохраняет в Trace Store.
    """
    
    def __init__(self, trace_store):
        self.trace_store = trace_store
        
    async def handle_goal_started(self, event) -> None:
        """Handle GoalExecutionStarted event"""
        await self.trace_store.append_event(
            goal_id=str(event.goal_id),
            event_type="GoalExecutionStarted",
            data={
                "goal_title": getattr(event, "goal_title", "unknown"),
                "goal_type": getattr(event, "goal_type", ""),
                "is_atomic": getattr(event, "is_atomic", True)
            }
        )
    
    async def handle_skill_selected(self, event) -> None:
        """Handle SkillSelected event"""
        await self.trace_store.append_event(
            goal_id=str(event.goal_id),
            event_type="SkillSelected",
            data={
                "skill_id": getattr(event, "skill_id", ""),
                "skill_name": getattr(event, "skill_name", ""),
                "score": getattr(event, "score", 0.0),
                "attempt": getattr(event, "attempt", 1)
            }
        )
    
    async def handle_artifact_produced(self, event) -> None:
        """Handle ArtifactProduced event"""
        await self.trace_store.append_event(
            goal_id=str(event.goal_id),
            event_type="ArtifactProduced",
            data={
                "skill_id": getattr(event, "skill_id", ""),
                "artifact_type": getattr(event, "artifact_type", ""),
                "content_kind": getattr(event, "content_kind", ""),
                "verification_status": getattr(event, "verification_status", "")
            }
        )
    
    async def handle_goal_evaluated(self, event) -> None:
        """Handle GoalEvaluated event"""
        await self.trace_store.append_event(
            goal_id=str(event.goal_id),
            event_type="GoalEvaluated",
            data={
                "outcome": getattr(event, "outcome", ""),
                "confidence": getattr(event, "confidence", 0.0),
                "passed": getattr(event, "passed", False),
                "artifacts_count": getattr(event, "artifacts_count", 0)
            }
        )
    
    async def handle_goal_transitioned(self, event) -> None:
        """Handle GoalTransitioned event"""
        await self.trace_store.append_event(
            goal_id=str(event.goal_id),
            event_type="GoalTransitioned",
            data={
                "from_state": getattr(event, "from_state", ""),
                "to_state": getattr(event, "to_state", ""),
                "reason": getattr(event, "reason", ""),
                "actor": getattr(event, "actor", "")
            }
        )
    
    async def handle_goal_execution_finished(self, event) -> None:
        """Handle GoalExecutionFinished event - update trace status"""
        await self.trace_store.update_trace_status(
            goal_id=str(event.goal_id),
            status=event.status,
            confidence=event.confidence
        )
    
    async def handle_any_event(self, event) -> None:
        """Generic handler - dispatch to specific handler"""
        event_name = type(event).__name__
        
        handlers = {
            "GoalExecutionStarted": self.handle_goal_started,
            "SkillSelected": self.handle_skill_selected,
            "ArtifactProduced": self.handle_artifact_produced,
            "GoalEvaluated": self.handle_goal_evaluated,
            "GoalTransitioned": self.handle_goal_transitioned,
            "GoalExecutionFinished": self.handle_goal_execution_finished,
        }
        
        handler = handlers.get(event_name)
        if handler:
            try:
                import asyncio
                import inspect
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                print(f"TraceCollector error handling {event_name}: {e}")


# Global collector
_trace_collector = None


def get_trace_collector(trace_store=None) -> TraceCollector:
    """Get or create trace collector"""
    global _trace_collector
    if _trace_collector is None:
        if trace_store is None:
            from trace_store import get_trace_store
            trace_store = get_trace_store()
        _trace_collector = TraceCollector(trace_store)
    return _trace_collector
