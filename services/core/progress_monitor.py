"""
Progress Monitor - отслеживает прогресс выполнения целей

Таблица: goal_progress_tracking
Поля:
- goal_id: UUID
- last_progress: float (0.0-1.0)
- last_update: timestamp
- retry_count: int
- execution_time_ms: int
- stuck_detected: bool

Запускается каждые 1-2 минуты.
"""
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GoalMetrics:
    goal_id: UUID
    last_progress: float
    last_update: datetime
    retry_count: int
    execution_time_ms: int
    stuck_detected: bool = False


class ProgressMonitor:
    """Мониторит прогресс выполнения целей и_detects stuck goals"""
    
    STUCK_THRESHOLD_MINUTES = 10
    STUCK_PROGRESS_DELTA = 0.01
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def ensure_table(self):
        """Создаёт таблицу если не существует"""
        await self.session.execute(text("""
            CREATE TABLE IF NOT EXISTS goal_progress_tracking (
                goal_id UUID PRIMARY KEY,
                last_progress FLOAT DEFAULT 0.0,
                last_update TIMESTAMP DEFAULT NOW(),
                retry_count INTEGER DEFAULT 0,
                execution_time_ms INTEGER DEFAULT 0,
                stuck_detected BOOLEAN DEFAULT FALSE
            )
        """))
        await self.session.commit()
    
    async def record_progress(self, goal_id: UUID, progress: float, execution_time_ms: int = 0):
        """Записывает прогресс цели"""
        await self.session.execute(text("""
            INSERT INTO goal_progress_tracking (goal_id, last_progress, last_update, execution_time_ms)
            VALUES (:goal_id, :progress, NOW(), :exec_time)
            ON CONFLICT (goal_id) DO UPDATE SET
                last_progress = :progress,
                last_update = NOW(),
                execution_time_ms = :exec_time,
                stuck_detected = FALSE
        """), {"goal_id": goal_id, "progress": progress, "exec_time": execution_time_ms})
        await self.session.commit()
    
    async def increment_retry(self, goal_id: UUID):
        """Увеличивает счётчик retry"""
        await self.session.execute(text("""
            UPDATE goal_progress_tracking 
            SET retry_count = retry_count + 1,
                last_update = NOW()
            WHERE goal_id = :goal_id
        """), {"goal_id": goal_id})
        await self.session.commit()
    
    async def detect_stuck_goals(self) -> list[UUID]:
        """Находит застрявшие цели"""
        threshold = datetime.utcnow() - timedelta(minutes=self.STUCK_THRESHOLD_MINUTES)
        
        result = await self.session.execute(text("""
            SELECT goal_id, last_progress, last_update 
            FROM goal_progress_tracking
            WHERE last_update < :threshold
            AND stuck_detected = FALSE
        """), {"threshold": threshold})
        
        rows = result.fetchall()
        stuck_ids = []
        
        for row in rows:
            goal_id, last_progress, last_update = row
            
            if last_progress < 0.1:
                await self.session.execute(text("""
                    UPDATE goal_progress_tracking 
                    SET stuck_detected = TRUE 
                    WHERE goal_id = :goal_id
                """), {"goal_id": goal_id})
                stuck_ids.append(goal_id)
                logger.warning(
                    "goal_stuck_detected",
                    goal_id=str(goal_id),
                    last_progress=last_progress,
                    minutes_stuck=(datetime.utcnow() - last_update).total_seconds() / 60
                )
        
        if stuck_ids:
            await self.session.commit()
        
        return stuck_ids
    
    async def get_active_goal_metrics(self) -> list[GoalMetrics]:
        """Получает метрики активных целей"""
        result = await self.session.execute(text("""
            SELECT gem.goal_id, gem.last_progress, gem.last_update, 
                   gem.retry_count, gem.execution_time_ms, gem.stuck_detected,
                   g.status, g.progress
            FROM goal_progress_tracking gem
            JOIN goals g ON g.id = gem.goal_id
            WHERE g.status IN ('active', 'pending')
            ORDER BY gem.last_update ASC
            LIMIT 100
        """))
        
        metrics = []
        for row in result.fetchall():
            metrics.append(GoalMetrics(
                goal_id=row[0],
                last_progress=row[1],
                last_update=row[2],
                retry_count=row[3],
                execution_time_ms=row[4],
                stuck_detected=row[5]
            ))
        return metrics


class ProgressMonitorService:
    """Сервис мониторинга - запускается по расписанию"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
    
    async def run_monitoring_cycle(self):
        """Запускает один цикл мониторинга"""
        async with self.session_factory() as session:
            monitor = ProgressMonitor(session)
            
            # Ensure table exists first
            await monitor.ensure_table()
            
            # Then detect stuck goals
            stuck_goals = await monitor.detect_stuck_goals()
            
            if stuck_goals:
                logger.info(
                    "progress_monitoring_cycle",
                    stuck_goals_count=len(stuck_goals),
                    stuck_goal_ids=[str(g) for g in stuck_goals]
                )
                
                # Trigger re-planning for stuck goals
                await self.trigger_replanning(stuck_goals)
                
                return stuck_goals
            
            return []
    
    async def trigger_replanning(self, stuck_goal_ids: list[UUID]):
        """Запускает re-planning для застрявших целей"""
        from replanning_engine import RePlanner
        from uuid import UUID
        
        for goal_id in stuck_goal_ids:
            try:
                replanner = RePlanner()
                result = await replanner.replan_goal(goal_id)
                logger.info(
                    "replanning_triggered",
                    goal_id=str(goal_id),
                    result=result
                )
            except Exception as e:
                logger.error(
                    "replanning_failed",
                    goal_id=str(goal_id),
                    error=str(e)
                )
