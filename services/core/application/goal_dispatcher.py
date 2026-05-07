"""
GoalDispatcher - Thin adapter for task execution queue

CRITICAL: Scheduler should NOT know about HTTP, API, or network.
All execution goes through queue dispatcher.

Architectural role:
    Scheduler → Dispatcher → Celery/Queue
    (orchestration)  (dispatch)    (execution)
"""
from uuid import UUID
from celery import Celery


class GoalDispatcher:
    """
    Thin adapter for dispatching goals to execution queue.

    Scheduler calls this → Dispatcher sends to Celery → Workers execute
    No HTTP. No API. No FastAPI layer.
    """

    def __init__(self, celery_app: Celery):
        self._celery = celery_app

    def dispatch_decomposition(self, goal_id: UUID) -> str:
        """
        Dispatch goal to decomposition queue.

        Args:
            goal_id: Goal ID to decompose

        Returns:
            Celery task ID
        """
        return self._celery.send_task(
            "tasks.decompose_goal",
            args=[str(goal_id)]
        )

    def dispatch_execution(self, goal_id: UUID) -> str:
        """
        Dispatch goal to execution queue.

        Args:
            goal_id: Goal ID to execute

        Returns:
            Celery task ID
        """
        return self._celery.send_task(
            "tasks.execute_goal",
            args=[str(goal_id)]
        )

    def dispatch_bulk_decomposition(self, goal_ids: list[UUID]) -> list[str]:
        """
        Dispatch multiple goals to decomposition queue.

        Args:
            goal_ids: List of goal IDs to decompose

        Returns:
            List of Celery task IDs
        """
        task_ids = []
        for goal_id in goal_ids:
            task_id = self.dispatch_decomposition(goal_id)
            task_ids.append(task_id)

        return task_ids


# Singleton instance (configured at startup)
goal_dispatcher: GoalDispatcher | None = None


def configure_dispatcher(celery_app: Celery) -> GoalDispatcher:
    """
    Configure dispatcher singleton.

    Called at application startup.

    Usage in main.py:
        from application.goal_dispatcher import configure_dispatcher
        from tasks import celery_app

        goal_dispatcher = configure_dispatcher(celery_app)
    """
    global goal_dispatcher
    goal_dispatcher = GoalDispatcher(celery_app)
    return goal_dispatcher


def get_dispatcher() -> GoalDispatcher:
    """
    Get dispatcher singleton.

    Raises:
        RuntimeError: If dispatcher not configured
    """
    if goal_dispatcher is None:
        raise RuntimeError(
            "GoalDispatcher not configured. "
            "Call configure_dispatcher() at startup."
        )
    return goal_dispatcher
