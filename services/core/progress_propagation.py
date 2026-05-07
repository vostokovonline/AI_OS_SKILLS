"""
Event-Driven Progress Propagation

ЕДИНСТВЕННЫЙ механизм обновления прогресса родителя.
Вызывается СТРОГО при событии completion дочерней цели.

Никакого polling! Никакого scheduler!
Только событие → обновление.
"""

from typing import Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ProgressEvent:
    """Событие изменения прогресса"""
    child_goal_id: str
    parent_goal_id: str
    old_progress: float
    new_progress: float
    timestamp: datetime


class ProgressPropagation:
    """
    Event-driven propagation прогресса.
    
    Вызывается при каждом completion дочерней цели.
    Обновляет всю цепочку предков.
    """
    
    def __init__(self):
        self.event_log = []
    
    async def propagate(self, session, child_goal) -> Optional[ProgressEvent]:
        """
        Обновить прогресс родителя при completion дочерней цели.
        Вызывается ИЗВНЕ при transition goal → done.
        """
        if not child_goal.parent_id:
            return None
        
        from models import Goal as GoalModel
        from sqlalchemy import select, func
        
        # Цепочка предков
        current_parent_id = child_goal.parent_id
        chain_updated = []
        
        while current_parent_id:
            # Получаем родителя
            parent = await session.get(GoalModel, current_parent_id)
            if not parent:
                break
            
            old_progress = parent.progress
            
            if parent.is_atomic:
                # Atomic просто done
                parent._internal_set_status("done")
                parent.progress = 1.0
                
                chain_updated.append({
                    "id": str(parent.id),
                    "old": 0.0,
                    "new": 1.0
                })
                
                await session.commit()
                
                if parent.parent_id:
                    current_parent_id = parent.parent_id
                else:
                    break
                continue
            
            # Non-atomic: считаем прогресс
            total_stmt = select(func.count(GoalModel.id)).where(
                GoalModel.parent_id == parent.id
            )
            total_result = await session.execute(total_stmt)
            total_children = total_result.scalar() or 0
            
            if total_children == 0:
                break
            
            done_stmt = select(func.count(GoalModel.id)).where(
                GoalModel.parent_id == parent.id,
                GoalModel._status == "done"
            )
            done_result = await session.execute(done_stmt)
            done_children = done_result.scalar() or 0
            
            new_progress = done_children / total_children
            parent.progress = new_progress
            
            chain_updated.append({
                "id": str(parent.id),
                "old": old_progress,
                "new": new_progress
            })
            
            # Auto-complete если все done
            if done_children >= total_children and new_progress >= 1.0:
                parent._internal_set_status("done")
                parent.completed_at = datetime.now()
            
            await session.commit()
            
            # Следующий предок
            if parent.parent_id:
                current_parent_id = parent.parent_id
            else:
                break
        
        # Логируем событие
        if chain_updated:
            event = ProgressEvent(
                child_goal_id=str(child_goal.id),
                parent_goal_id=chain_updated[0]["id"] if chain_updated else "",
                old_progress=0.0,
                new_progress=chain_updated[-1]["new"] if chain_updated else 0.0,
                timestamp=datetime.now()
            )
            self.event_log.append(event)
        
        return event


# Глобальный инстанс
_propagation = None


def get_propagation() -> ProgressPropagation:
    global _propagation
    if _propagation is None:
        _propagation = ProgressPropagation()
    return _propagation


# Простой API для вызова
async def on_goal_completed(session, goal):
    """
    Вызывать при transition goal → done.
    
    Пример использования:
        await on_goal_completed(session, goal)
    """
    propagation = get_propagation()
    return await propagation.propagate(session, goal)