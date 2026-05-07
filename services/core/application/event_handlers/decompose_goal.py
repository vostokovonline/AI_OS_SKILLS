"""
DecomposeGoalHandler - Обработчик события GoalActivated
====================================================

Реагирует на активацию цели и запускает декомпозицию.
Это заменяет HTTP вызов /decompose.
"""
from logging_config import get_logger

logger = get_logger(__name__)


class DecomposeGoalHandler:
    """
    Обработчик события GoalActivated.
    
    При получении события - запускает декомпозицию цели.
    """
    
    def __init__(self, uow_factory, decomposer):
        self._uow_factory = uow_factory
        self._decomposer = decomposer
    
    async def __call__(self, event):
        """
        Обработать событие активации цели.
        
        Args:
            event: GoalActivated event
        """
        from application.events.goal_events import GoalActivated
        
        if not isinstance(event, GoalActivated):
            return
        
        goal_id = event.goal_id
        logger.info("decompose_handler_start", goal_id=str(goal_id)[:8])
        
        try:
            # Вызываем decomposer напрямую (без HTTP)
            subgoals = await self._decomposer.decompose_goal(
                goal_id=str(goal_id),
                max_depth=3
            )
            
            subgoals_count = len(subgoals) if subgoals else 0
            
            logger.info(
                "decompose_handler_complete",
                goal_id=str(goal_id)[:8],
                subgoals=subgoals_count
            )
            
            return {"subgoals_created": subgoals_count}
            
        except Exception as e:
            logger.error(
                "decompose_handler_error",
                goal_id=str(goal_id)[:8],
                error=str(e)[:100]
            )
            # Не поднимаем исключение - логируем и продолжаем
            # Event bus должен быть отказоустойчивым
            return None
