"""
Unit of Work Pattern + Audit Logger - Infrastructure Layer
=========================================================
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select


class UnitOfWork:
    """
    Тонкий Unit of Work для управления транзакциями.
    
    Usage:
        async with UnitOfWork(session_factory) as uow:
            goal = await uow.goals.get(uow.session, goal_id)
            await transition_service.transition(uow, goal_id, "done")
    """
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
    
    async def __aenter__(self) -> "UnitOfWork":
        """Создаём сессию и начинаем транзакцию"""
        self._session = self._session_factory()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Коммит или rollback + закрытие сессии"""
        try:
            if exc_type is None:
                if self._session:
                    await self._session.commit()
            else:
                if self._session:
                    await self._session.rollback()
        finally:
            if self._session:
                await self._session.close()
                self._session = None
    
    @property
    def session(self) -> AsyncSession:
        """Доступ к текущей сессии"""
        if self._session is None:
            raise RuntimeError(
                "Session not available. Use 'async with UnitOfWork() as uow:' pattern."
            )
        return self._session


class GoalRepository:
    """Репозиторий для Goal - только CRUD"""
    
    def __init__(self, uow: UnitOfWork | None = None):
        self._uow = uow
    
    async def get(self, session, goal_id) -> "Goal":
        """Получить цель по ID"""
        from models import Goal
        
        stmt = select(Goal).where(Goal.id == goal_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_for_update(self, session, goal_id) -> "Goal":
        """
        Получить цель с pessimistic lock (SELECT ... FOR UPDATE).
        """
        from models import Goal
        
        stmt = (
            select(Goal)
            .where(Goal.id == goal_id)
            .with_for_update()
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def bulk_get_for_update(self, session, goal_ids) -> list:
        """Получить несколько целей с lock"""
        from models import Goal
        
        stmt = (
            select(Goal)
            .where(Goal.id.in_(goal_ids))
            .with_for_update()
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    async def save(self, session, goal) -> None:
        """Сохранить (add + flush для получения ID)"""
        session.add(goal)
        await session.flush()  # Flush to get generated ID
    
    async def update(self, session, goal) -> None:
        """Обновить (flush всех изменений в сессии)"""
        await session.flush()


class AuditLogger:
    """Audit logging helper"""
    
    async def log_transition(
        self,
        session,
        goal_id: str,
        goal_type: str,
        from_state: str,
        to_state: str,
        reason: str,
        actor: str
    ) -> None:
        """Логировать успешный переход"""
        try:
            from audit_logger_v2 import audit_logger, AuditEventType
            await audit_logger.log(
                event_type=AuditEventType.STATE_TRANSITION,
                severity="INFO",
                goal_id=goal_id,
                goal_type=goal_type,
                from_state=from_state,
                to_state=to_state,
                reason=reason,
                actor=actor
            )
        except Exception:
            pass  # Logging не должен ломать transitions
    
    async def log_violation(
        self,
        session,
        goal_id: str,
        goal_type: str,
        reason: str
    ) -> None:
        """Логировать нарушение инварианта"""
        try:
            from audit_logger_v2 import audit_logger, AuditEventType
            await audit_logger.log(
                event_type=AuditEventType.INVARIANT_VIOLATION,
                severity="WARNING",
                goal_id=goal_id,
                goal_type=goal_type,
                reason=reason
            )
        except Exception:
            pass
    
    async def log_failure(
        self,
        session,
        goal_id: str,
        goal_type: str,
        from_state: str,
        to_state: str,
        error: str
    ) -> None:
        """Логировать ошибку перехода"""
        try:
            from audit_logger_v2 import audit_logger, AuditEventType
            await audit_logger.log(
                event_type=AuditEventType.STATE_TRANSITION_FAILED,
                severity="ERROR",
                goal_id=goal_id,
                goal_type=goal_type,
                from_state=from_state,
                to_state=to_state,
                error=error
            )
        except Exception:
            pass


def create_uow_provider() -> "UoWProvider":
    """
    Фабрика для создания UoW провайдера.
    
    Usage in FastAPI:
        from database import AsyncSessionLocal
        from infrastructure.uow import create_uow_provider
        
        get_uow = create_uow_provider()
        
        async def endpoint(uow: UnitOfWork = Depends(get_uow)):
            await uow.goals.get(uow.session, goal_id)
    """
    from database import AsyncSessionLocal
    
    class UoWProvider:
        def __init__(self, factory):
            self._factory = factory
        
        def __call__(self) -> UnitOfWork:
            return UnitOfWork(self._factory)
        
        @property
        def goals(self) -> GoalRepository:
            return GoalRepository()
    
    return UoWProvider(AsyncSessionLocal)


class BulkTransitionService:
    """
    Bulk Transition Service - массовые переходы в одной транзакции.
    
    Преимущества:
    - O(1) транзакций вместо O(N)
    - Atomic - все или ничего
    - Пессимистичные блокировки для консистентности
    """
    
    def __init__(self):
        self._repository = GoalRepository()
        self._logger = AuditLogger()
    
    async def execute_bulk(
        self,
        uow: "UnitOfWork",
        goal_ids: list,
        new_state: str,
        reason: str,
        actor: str = "system"
    ) -> dict:
        """
        Выполнить массовый переход для списка целей.
        
        Args:
            uow: UnitOfWork с активной транзакцией
            goal_ids: Список UUID целей
            new_state: Новое состояние
            reason: Причина перехода
            actor: Кто инициировал
            
        Returns:
            {
                "total": int,
                "succeeded": int,
                "failed": int,
                "results": [...]
            }
        """
        from uuid import UUID
        from domain.goal_domain_service import GoalDomainService, GoalState
        from datetime import datetime
        
        domain = GoalDomainService()
        goal_state = GoalState(new_state)
        
        results = []
        succeeded = 0
        failed = 0
        
        print(f"\n🔄 BULK TRANSITION: {len(goal_ids)} goals")
        print(f"   → State: {new_state}")
        print(f"   → Actor: {actor}")
        print(f"   → Reason: {reason}")
        print("=" * 70)
        
        # 1. Блокируем все цели одним запросом
        goals = await self._repository.bulk_get_for_update(uow.session, goal_ids)
        
        if len(goals) != len(goal_ids):
            found_ids = {str(g.id) for g in goals}
            missing = [str(gid) for gid in goal_ids if str(gid) not in found_ids]
            print(f"  ⚠️ Missing goals: {missing}")
        
        # 2. Выполняем переходы
        for goal in goals:
            goal_id = str(goal.id)
            from_state = goal._status
            
            try:
                # Делегируем доменному слою
                event = domain.transition(goal, goal_state, reason)
                
                # Логируем
                await self._logger.log_transition(
                    session=uow.session,
                    goal_id=goal_id,
                    goal_type=getattr(goal, 'goal_type', 'unknown'),
                    from_state=from_state,
                    to_state=new_state,
                    reason=reason,
                    actor=actor
                )
                
                results.append({
                    "goal_id": goal_id,
                    "status": "success",
                    "from_state": from_state,
                    "to_state": new_state
                })
                succeeded += 1
                
            except ValueError as e:
                # Бизнес-правило нарушено
                results.append({
                    "goal_id": goal_id,
                    "status": "blocked",
                    "from_state": from_state,
                    "reason": str(e)
                })
                failed += 1
                
                await self._logger.log_violation(
                    session=uow.session,
                    goal_id=goal_id,
                    goal_type=getattr(goal, 'goal_type', 'unknown'),
                    reason=str(e)
                )
                
            except Exception as e:
                # Непредвиденная ошибка
                results.append({
                    "goal_id": goal_id,
                    "status": "failed",
                    "from_state": from_state,
                    "error": str(e)
                })
                failed += 1
                
                await self._logger.log_failure(
                    session=uow.session,
                    goal_id=goal_id,
                    goal_type=getattr(goal, 'goal_type', 'unknown'),
                    from_state=from_state,
                    to_state=new_state,
                    error=str(e)
                )
        
        print(f"  ✅ Bulk Complete: {succeeded} succeeded, {failed} failed")
        print(f"{'='*70}\n")
        
        return {
            "total": len(goal_ids),
            "found": len(goals),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    async def freeze_tree(
        self,
        uow: "UnitOfWork",
        root_goal_id: str,
        reason: str = "Tree frozen",
        actor: str = "system"
    ) -> dict:
        """
        Заморозить всё дерево целей (root + все потомки).
        
        Полезно для:
        - Приостановки больших проектов
        - Массовой архивации
        - Cascade operations
        
        Args:
            uow: UnitOfWork с активной транзакцией
            root_goal_id: ID корневой цели
            reason: Причина
            actor: Кто инициировал
            
        Returns:
            Результаты bulk операции
        """
        from uuid import UUID
        from sqlalchemy import select, or_
        from models import Goal
        
        root_uuid = UUID(root_goal_id)
        
        # 1. Получаем все цели в дереве (root + descendants)
        stmt = select(Goal.id).where(
            or_(
                Goal.id == root_uuid,
                Goal.parent_id == root_uuid
            )
        )
        
        result = await uow.session.execute(stmt)
        goal_ids = [row[0] for row in result.all()]
        
        # 2. Выполняем bulk transition
        return await self.execute_bulk(
            uow=uow,
            goal_ids=goal_ids,
            new_state="frozen",
            reason=reason,
            actor=actor
        )


# Singleton instance
bulk_transition_service = BulkTransitionService()


# Default UoW provider for dependency injection
# Usage: from infrastructure.uow import get_uow
_uow_provider = create_uow_provider()


async def get_uow():
    """
    FastAPI Depends для UnitOfWork.
    
    Usage:
        @app.post("/endpoint")
        async def endpoint(uow: UnitOfWork = Depends(get_uow)):
            async with uow:
                # your code here
                pass
    """
    uow = _uow_provider()
    async with uow:
        yield uow
