"""
Goal Completion Service

Автоматически завершает goals после создания PASSED artifacts.

Это ключевой компонент который исправляет pipeline:
skill → artifact → verification → goal transition
"""
from uuid import UUID
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


class GoalCompletionService:
    """
    Оценивает completion goals на основе artifacts.
    
    Правило: 
    - atomic goal + PASSED artifact = done
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def evaluate_goal_completion(self, goal_id: UUID) -> dict:
        """
        Оценивает готовность goal к завершению.
        
        Returns:
            dict с result (completed/skipped/failed)
        """
        # Get goal
        result = await self.session.execute(text("""
            SELECT id, title, status, progress, is_atomic
            FROM goals
            WHERE id = :goal_id
        """), {'goal_id': goal_id})
        
        goal = result.fetchone()
        if not goal:
            return {'result': 'goal_not_found'}
        
        goal_id, title, status, progress, is_atomic = goal
        
        # Skip if already done
        if status == 'done':
            return {'result': 'already_done', 'goal_id': str(goal_id)}
        
        # Skip if not atomic
        if not is_atomic:
            return {'result': 'not_atomic', 'goal_id': str(goal_id)}
        
        # Check for PASSED artifacts
        artifacts_result = await self.session.execute(text("""
            SELECT COUNT(*) 
            FROM artifacts 
            WHERE goal_id = :goal_id 
            AND verification_status = 'passed'
        """), {'goal_id': goal_id})
        
        passed_count = artifacts_result.scalar() or 0
        
        if passed_count > 0:
            # Complete the goal
            await self._transition_to_done(goal_id, passed_count)
            return {
                'result': 'completed',
                'goal_id': str(goal_id),
                'title': title,
                'artifacts_passed': passed_count
            }
        
        # Check for failed artifacts
        failed_result = await self.session.execute(text("""
            SELECT COUNT(*) 
            FROM artifacts 
            WHERE goal_id = :goal_id 
            AND verification_status = 'failed'
        """), {'goal_id': goal_id})
        
        failed_count = failed_result.scalar() or 0
        
        if failed_count > 0:
            return {
                'result': 'failed',
                'goal_id': str(goal_id),
                'artifacts_failed': failed_count
            }
        
        # No artifacts
        return {'result': 'no_artifacts', 'goal_id': str(goal_id)}
    
    async def _transition_to_done(self, goal_id: UUID, artifact_count: int):
        """Переводит goal в done"""
        # Get goal details for notification
        goal_result = await self.session.execute(text("""
            SELECT title, created_at FROM goals WHERE id = :goal_id
        """), {'goal_id': goal_id})
        goal_row = goal_result.fetchone()
        goal_title = goal_row[0] if goal_row else "Unknown"
        created_at = goal_row[1] if goal_row else None
        
        # Calculate duration
        duration_seconds = 0
        if created_at:
            duration_seconds = (datetime.utcnow() - created_at).total_seconds()
        
        await self.session.execute(text("""
            UPDATE goals
            SET status = 'done',
                progress = 1.0,
                updated_at = NOW(),
                completed_at = NOW()
            WHERE id = :goal_id
        """), {'goal_id': goal_id})
        
        await self.session.commit()
        
        # Send Telegram notification
        try:
            from telegram_notifier import send_goal_completed_notification
            await send_goal_completed_notification(
                goal_id=str(goal_id),
                goal_title=goal_title,
                status="done",
                artifacts_count=artifact_count,
                duration_seconds=duration_seconds
            )
        except Exception as e:
            logger.warning("telegram_notification_failed", error=str(e))
        
        logger.info(
            "goal_completed_via_artifacts",
            goal_id=str(goal_id),
            artifacts_passed=artifact_count
        )
    
    async def scan_and_complete_all(self) -> dict:
        """
        Сканирует все goals и завершает те что готовы.
        
        Returns:
            dict с количеством завершённых goals
        """
        # Find atomic goals with passed artifacts but not done
        result = await self.session.execute(text("""
            SELECT DISTINCT g.id
            FROM goals g
            JOIN artifacts a ON a.goal_id = g.id
            WHERE g.status != 'done'
            AND g.is_atomic = true
            AND a.verification_status = 'passed'
        """))
        
        goal_ids = [row[0] for row in result.fetchall()]
        
        completed = 0
        for goal_id in goal_ids:
            result = await self.evaluate_goal_completion(goal_id)
            if result['result'] == 'completed':
                completed += 1
        
        logger.info(
            "goal_completion_scan_complete",
            goals_scanned=len(goal_ids),
            completed=completed
        )
        
        return {
            'scanned': len(goal_ids),
            'completed': completed
        }


class ArtifactEventHandler:
    """
    Обрабатывает события от artifact verification.
    
    Подключается к pipeline:
    artifact_verified → trigger goal completion
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.completion_service = GoalCompletionService(session)
    
    async def on_artifact_verified(self, artifact_id: UUID, goal_id: UUID, status: str):
        """
        Обрабатывает событие верификации artifact.
        
        Если artifact PASSED → проверяем goal на completion
        """
        if status == 'passed':
            result = await self.completion_service.evaluate_goal_completion(goal_id)
            
            logger.info(
                "artifact_verification_event",
                artifact_id=str(artifact_id),
                goal_id=str(goal_id),
                verification_status=status,
                goal_completion_result=result['result']
            )
            
            return result
        
        return {'result': 'ignored'}
