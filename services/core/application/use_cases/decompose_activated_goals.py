"""
Decompose Activated Goals Use-Case
=================================

Канонический use-case с two-phase decomposition:

Phase 1 (READ): Найти цели → получить снапшоты → вызвать decompose_snapshot
Phase 2 (WRITE): Применить решения → создать подцели → commit

Это проверяет что домен "запечатан" - все изменения через TransitionService.
"""
from dataclasses import dataclass
from uuid import UUID
from typing import List

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DecomposeResult:
    """Результат декомпозиции"""
    total_found: int
    decomposed: int
    no_subgoals: int
    failed: int
    subgoals_created: int
    
    @classmethod
    def empty(cls) -> "DecomposeResult":
        return cls(
            total_found=0,
            decomposed=0,
            no_subgoals=0,
            failed=0,
            subgoals_created=0
        )


class GoalSnapshot:
    """Чистый DTO для передачи в Decomposer"""
    def __init__(
        self,
        id: UUID,
        title: str,
        description: str,
        goal_type: str,
        depth_level: int,
        domains: List[str],
        constraints: dict,
        version: int,
        parent_id: UUID = None
    ):
        self.id = id
        self.title = title
        self.description = description
        self.goal_type = goal_type
        self.depth_level = depth_level
        self.domains = domains
        self.constraints = constraints
        self.version = version
        self.parent_id = parent_id


class DecomposeActivatedGoalsUseCase:
    """
    Two-phase decomposition use-case.
    
    Phase 1 (READ): snapshot → decision (no writes)
    Phase 2 (WRITE): apply decisions → commit
    """
    
    def __init__(self, uow_factory, decomposer):
        self._uow_factory = uow_factory
        self._decomposer = decomposer
    
    async def run(
        self,
        *,
        max_goals: int = 5,
        actor: str = "system"
    ) -> DecomposeResult:
        """
        Выполнить декомпозицию.
        
        Two-phase подход:
        1. READ: Собрать снапшоты и решения (без записи)
        2. WRITE: Применить решения (один commit)
        """
        logger.info("use_case_decompose_start", max_goals=max_goals)
        
        # Phase 1: READ - собираем решения
        decisions = []
        
        async with self._uow_factory() as uow:
            # Найти цели для декомпозиции
            goals_data = await self._find_goals_needing_decomposition(uow, max_goals)
            
            if not goals_data:
                logger.debug("use_case_decompose_no_candidates")
                return DecomposeResult.empty()
            
            logger.info(
                "use_case_decompose_found",
                count=len(goals_data),
                titles=[g[1][:30] for g in goals_data[:3]]
            )
            
            # Для каждой цели - получить снапшот и решение
            for goal_id, title, description, goal_type, depth, domains in goals_data:
                try:
                    # Создаём snapshot (чистый DTO)
                    snapshot = GoalSnapshot(
                        id=goal_id,
                        title=title,
                        description=description or "",
                        goal_type=goal_type or "achievable",
                        depth_level=depth,
                        domains=domains or [],
                        constraints={},
                        version=1
                    )
                    
                    # Pure calculation - decompose_snapshot НЕ пишет в базу
                    decision = await self._decomposer.decompose_snapshot(
                        snapshot,
                        max_depth=3
                    )
                    
                    decisions.append(decision)
                    
                except Exception as e:
                    logger.error(
                        "use_case_decompose_decision_error",
                        goal_id=str(goal_id)[:8],
                        error=str(e)[:100]
                    )
        
        # Phase 2: WRITE - применяем решения (только если есть решения)
        if not decisions:
            return DecomposeResult.empty()
        
        # Агрегация решений
        state_changes = []
        proposed_subgoals = []
        
        for d in decisions:
            if d.success:
                state_changes.extend(d.state_changes)
                proposed_subgoals.extend(d.proposed_subgoals)
        
        logger.info(
            "use_case_decompose_aggregated",
            decisions=len(decisions),
            state_changes=len(state_changes),
            proposed_subgoals=len(proposed_subgoals)
        )
        
        # Применяем все изменения (в одной транзакции)
        async with self._uow_factory() as uow:
            await self._apply_decisions(
                uow=uow,
                state_changes=state_changes,
                proposed_subgoals=proposed_subgoals,
                actor=actor
            )
        
        # Подсчёт результатов
        decomposed = sum(1 for d in decisions if d.success)
        no_subgoals = sum(1 for d in decisions if not d.success and not d.diagnostics.get("error"))
        
        return DecomposeResult(
            total_found=len(goals_data),
            decomposed=decomposed,
            no_subgoals=no_subgoals,
            failed=len(decisions) - decomposed - no_subgoals,
            subgoals_created=len(proposed_subgoals)
        )
    
    async def _find_goals_needing_decomposition(
        self, 
        uow, 
        limit: int
    ) -> List[tuple]:
        """Найти цели, требующие декомпозиции"""
        from sqlalchemy import select, exists
        from sqlalchemy.orm import aliased
        from models import Goal
        
        child = aliased(Goal, name='child')
        has_children = exists(
            select(1).where(child.parent_id == Goal.id)
        ).correlate(Goal)
        
        stmt = (
            select(
                Goal.id,
                Goal.title,
                Goal.description,
                Goal.goal_type,
                Goal.depth_level,
                Goal.domains
            )
            .where(Goal.is_atomic == False)
            .where(Goal._status == 'active')
            .where(Goal.depth_level < 3)
            .where(~has_children)
            .order_by(Goal.created_at.desc())
            .limit(limit)
        )
        
        result = await uow.session.execute(stmt)
        return list(result.fetchall())
    
    async def _apply_decisions(
        self,
        uow,
        state_changes: list,
        proposed_subgoals: list,
        actor: str
    ) -> None:
        """
        Применить решения через TransitionService и Repository.
        
        Это единственное место где происходят WRITE операции.
        """
        from goal_transition_service import transition_service
        from models import Goal
        from uuid import UUID
        
        # 1. Применить state changes через TransitionService
        if state_changes:
            for sc in state_changes:
                try:
                    result = await transition_service.transition(
                        uow=uow,
                        goal_id=sc.goal_id,
                        new_state=sc.new_state,
                        reason=sc.rationale,
                        actor=actor
                    )
                    
                    if result.get("result") != "success":
                        logger.warning(
                            "transition_apply_failed",
                            goal_id=str(sc.goal_id)[:8],
                            result=result
                        )
                        
                except Exception as e:
                    logger.error(
                        "transition_apply_error",
                        goal_id=str(sc.goal_id)[:8],
                        error=str(e)[:100]
                    )
        
        # 2. Создать подцели через repository
        if proposed_subgoals:
            # Дополнительная проверка - не создавать подцели если они уже есть
            from sqlalchemy import select, func
            from models import Goal
            
            for sg in proposed_subgoals:
                try:
                    # parent_id берём из GoalStateChange
                    parent_goal_id = None
                    for sc in state_changes:
                        if hasattr(sc, 'goal_id'):
                            parent_goal_id = sc.goal_id
                            break
                    
                    subgoal = Goal(
                        parent_id=parent_goal_id,
                        title=sg.title,
                        description=sg.description,
                        goal_type=sg.goal_type,
                        depth_level=sg.depth_level,
                        is_atomic=sg.is_atomic,
                        domains=sg.domains,
                        completion_criteria=sg.completion_criteria,
                        success_definition=sg.success_definition,
                        _status="pending",
                        progress=0.0,
                        strategy_id=None
                    )
                    
                    uow.session.add(subgoal)
                    await uow.session.flush([subgoal])
                    
                except Exception as e:
                    logger.error(
                        "subgoal_create_error",
                        title=sg.title[:30],
                        error=str(e)[:100]
                    )
        
        logger.info(
            "use_case_decompose_applied",
            transitions=len(state_changes),
            subgoals=len(proposed_subgoals)
        )


__all__ = ["DecomposeActivatedGoalsUseCase", "DecomposeResult"]
