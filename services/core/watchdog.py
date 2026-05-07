"""
Anti-Deadlock Watchdog

Следит за зависшими goals и генерирует события для recovery.
Запускается периодически.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional


class Watchdog:
    """
    Watchdog для обнаружения stuck goals.
    
    Критерии stuck:
    - status != done
    - last_update > threshold минут  
    - нет активного execution
    """
    
    def __init__(self, threshold_minutes: int = 10):
        self.threshold_minutes = threshold_minutes
        self.last_check = None
    
    async def check_stuck_goals(self) -> List[dict]:
        """Найти зависшие цели"""
        from models import Goal
        from database import AsyncSessionLocal
        
        stuck_goals = []
        
        async with AsyncSessionLocal() as session:
            # Ищем не-done цели с old last_update
            threshold = datetime.now() - timedelta(minutes=self.threshold_minutes)
            
            from sqlalchemy import select, and_
            
            stmt = select(Goal).where(
                and_(
                    Goal._status != "done",
                    Goal.last_update < threshold
                )
            )
            
            result = await session.execute(stmt)
            goals = result.scalars().all()
            
            for goal in goals:
                stuck_goals.append({
                    "goal_id": str(goal.id),
                    "title": goal.title[:50],
                    "status": goal._status,
                    "progress": goal.progress,
                    "last_update": goal.last_update,
                    "is_atomic": goal.is_atomic,
                    "parent_id": goal.parent_id
                })
        
        self.last_check = datetime.now()
        return stuck_goals
    
    async def run_watchdog(self) -> dict:
        """Запустить проверку и эмитить события для stuck goals"""
        from event_bus import emit_goal_stuck
        
        stuck = await self.check_stuck_goals()
        
        stats = {
            "checked_at": datetime.now().isoformat(),
            "threshold_minutes": self.threshold_minutes,
            "stuck_count": len(stuck),
            "stuck_goals": []
        }
        
        for stuck_goal in stuck:
            goal_id = stuck_goal["goal_id"]
            stuck_minutes = self.threshold_minutes
            
            # Эмитим событие
            await emit_goal_stuck(goal_id, stuck_minutes)
            
            stats["stuck_goals"].append({
                "goal_id": goal_id,
                "title": stuck_goal["title"],
                "status": stuck_goal["status"],
                "progress": stuck_goal["progress"]
            })
        
        if stuck:
            print(f"[Watchdog] Found {len(stuck)} stuck goals")
        
        return stats
    
    async def start_periodic(self, interval_seconds: int = 120):
        """
        Запустить периодическую проверку.
        Вызывать при старте системы.
        """
        print(f"[Watchdog] Starting periodic check every {interval_seconds}s")
        
        while True:
            try:
                await self.run_watchdog()
            except Exception as e:
                print(f"[Watchdog] Error: {e}")
            
            await asyncio.sleep(interval_seconds)


# Глобальный инстанс
_watchdog: Optional[Watchdog] = None


def get_watchdog(threshold_minutes: int = 10) -> Watchdog:
    """Получить watchdog"""
    global _watchdog
    if _watchdog is None:
        _watchdog = Watchdog(threshold_minutes)
    return _watchdog


async def run_watchdog_check() -> dict:
    """Одиночный запуск watchdog"""
    dog = get_watchdog()
    return await dog.run_watchdog()


__all__ = [
    "Watchdog",
    "get_watchdog", 
    "run_watchdog_check",
]