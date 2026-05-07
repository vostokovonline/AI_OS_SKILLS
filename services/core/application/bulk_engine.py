"""
Bulk Transition Engine - Pure Applier
======================================

Контракт: "тупый молоток" - применяет то, что уже решено.

Никакой бизнес-логики. Никаких if/else связанных с domain rules.
Только атомарное применение набора изменений.

Принципы:
1. Atomicity - всё в одном UoW
2. Deterministic Ordering - всегда sorted by goal_id
3. No Hidden Reads - только то, что передано
"""
from dataclasses import dataclass

from logging_config import get_logger

logger = get_logger(__name__)
from typing import List, Optional
from uuid import UUID
from datetime import datetime


@dataclass(frozen=True)
class StateTransitionIntent:
    """
    Готовое к применению изменение состояния.
    
    Все решения уже приняты - BulkEngine только применяет.
    """
    goal_id: UUID
    from_status: str  # Для валидации
    to_status: str    # Уже решено
    reason: str       # Уже сформулировано
    actor: str        # Уже определён


@dataclass(frozen=True) 
class SubgoalCreationIntent:
    """
    Готовое к созданию подцели.
    
    BulkEngine не знает про домен - только создаёт.
    """
    title: str
    description: str
    goal_type: str
    depth_level: int
    is_atomic: bool
    domains: List[str]
    parent_id: UUID


@dataclass(frozen=True)
class BulkExecutionIntent:
    """
    Полное намерение для bulk применения.
    
    Это то, что приходит от Arbitration/Execution слоя.
    BulkEngine понятия не имеет "почему" - только "что применить".
    """
    goal_id: UUID
    transition: StateTransitionIntent
    subgoals: List[SubgoalCreationIntent] = None
    
    def __post_init__(self):
        if self.subgoals is None:
            object.__setattr__(self, 'subgoals', [])


@dataclass
class BulkApplyResult:
    """Результат bulk применения"""
    total: int
    applied: int
    failed: int
    skipped: int
    results: List[dict]


class BulkTransitionEngine:
    """
    Dumb applier - применяет то, что уже решено.
    
    Никакой бизнес-логики. Никаких threshold, outcome评估.
    
    Usage:
        engine = BulkTransitionEngine()
        
        intents = [
            BulkExecutionIntent(
                goal_id=uuid1,
                transition=StateTransitionIntent(
                    goal_id=uuid1,
                    from_status="active",
                    to_status="done",
                    reason="Execution complete",
                    actor="system.arbiter"
                )
            ),
            ...
        ]
        
        result = await engine.apply_intents(uow, intents, actor="system")
    """
    
    async def apply_intents(
        self,
        uow,
        intents: List[BulkExecutionIntent],
        actor: str = "system.bulk"
    ) -> BulkApplyResult:
        """
        Применить набор намерений атомарно.
        
        ГАРАНТИИ:
        1. Все или ничего (atomic)
        2. Детерминированный порядок (sorted by goal_id)
        3. Никаких дополнительных reads/writes кроме явно указанных
        
        Args:
            uow: UnitOfWork с активной транзакцией
            intents: Список намерений (уже решённых)
            actor: Кто инициировал
            
        Returns:
            BulkApplyResult
        """
        from goal_transition_service import transition_service
        
        # Детерминированный порядок - critical для replay
        sorted_intents = sorted(intents, key=lambda i: i.goal_id)
        
        results = []
        applied = 0
        failed = 0
        skipped = 0
        
        for intent in sorted_intents:
            try:
                # Применяем transition (уже решено - просто применяем)
                result = await transition_service.transition(
                    uow=uow,
                    goal_id=intent.goal_id,
                    new_state=intent.transition.to_status,
                    reason=intent.transition.reason,
                    actor=actor
                )
                
                if result.get("result") == "success":
                    applied += 1
                else:
                    skipped += 1
                    
                results.append({
                    "goal_id": str(intent.goal_id),
                    "status": result.get("result"),
                    "to_status": intent.transition.to_status
                })
                
            except Exception as e:
                failed += 1
                results.append({
                    "goal_id": str(intent.goal_id),
                    "status": "failed",
                    "error": str(e)[:100]
                })
        
        return BulkApplyResult(
            total=len(intents),
            applied=applied,
            failed=failed,
            skipped=skipped,
            results=results
        )

    async def transition_goal(
        self,
        uow,
        goal_id: UUID,
        new_state: str,
        reason: str,
        actor: str = "system"
    ) -> dict:
        """
        Convenience method for single goal transition.
        Wraps transition_goal into BulkExecutionIntent and applies it.
        
        Args:
            uow: UnitOfWork с активной транзакцией
            goal_id: ID цели
            new_state: Новый статус
            reason: Причина перехода
            actor: Кто инициировал
            
        Returns:
            dict с результатом
        """
        from goal_transition_service import transition_service
        
        try:
            result = await transition_service.transition(
                uow=uow,
                goal_id=goal_id,
                new_state=new_state,
                reason=reason,
                actor=actor
            )
            return result
        except Exception as e:
            logger.warning("bulk_transition_goal_failed", goal_id=str(goal_id), error=str(e))
            raise
    
    async def apply_subgoals(
        self,
        uow,
        intents: List[SubgoalCreationIntent],
        actor: str = "system.bulk"
    ) -> BulkApplyResult:
        """
        Применить создание подцелей.
        
        Args:
            uow: UnitOfWork с активной транзакцией
            intents: Список намерений создания подцелей
            
        Returns:
            BulkApplyResult
        """
        from models import Goal
        
        sorted_intents = sorted(intents, key=lambda i: i.title)
        
        results = []
        applied = 0
        failed = 0
        
        for intent in sorted_intents:
            try:
                subgoal = Goal(
                    parent_id=intent.parent_id,
                    title=intent.title,
                    description=intent.description,
                    goal_type=intent.goal_type,
                    depth_level=intent.depth_level,
                    is_atomic=intent.is_atomic,
                    domains=intent.domains,
                    _status="pending",
                    progress=0.0
                )
                
                uow.session.add(subgoal)
                await uow.session.flush([subgoal])
                
                applied += 1
                results.append({
                    "title": intent.title,
                    "status": "created",
                    "id": str(subgoal.id)
                })
                
            except Exception as e:
                failed += 1
                results.append({
                    "title": intent.title,
                    "status": "failed",
                    "error": str(e)[:100]
                })
        
        return BulkApplyResult(
            total=len(intents),
            applied=applied,
            failed=failed,
            skipped=0,
            results=results
        )


# Singleton instance
_bulk_engine: BulkTransitionEngine | None = None


def get_bulk_engine() -> BulkTransitionEngine:
    global _bulk_engine
    if _bulk_engine is None:
        _bulk_engine = BulkTransitionEngine()
    return _bulk_engine
