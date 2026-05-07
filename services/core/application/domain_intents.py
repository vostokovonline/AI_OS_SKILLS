"""
Goal Snapshot - Pure DTO для Decomposer
=====================================

Decomposer работает ТОЛЬКО со снапшотами, не с Entity.
Это делает его чистой функцией - детерминируемой и тестируемой.
"""
from dataclasses import dataclass
from uuid import UUID
from typing import Optional


@dataclass(frozen=True)
class GoalSnapshot:
    """
    Чистый DTO - состояние цели на момент передачи в Decomposer.
    
    Никаких ORM-связей, только примитивные типы.
    """
    id: UUID
    title: str
    description: str
    goal_type: str
    depth_level: int
    domains: list[str]
    constraints: dict
    version: int
    parent_id: Optional[UUID] = None


@dataclass(frozen=True)
class GoalStateChange:
    """
    Намерение изменить состояние.
    
    Decomposer предлагает, TransitionService решает.
    """
    goal_id: UUID
    new_state: str  # "active", "completed", "failed", etc.
    rationale: str


@dataclass(frozen=True)
class ProposedSubgoal:
    """
    Предложенная подцель.
    
    Decomposer предлагает, UseCase решает создавать или нет.
    """
    title: str
    description: str
    goal_type: str
    depth_level: int
    domains: list[str]
    is_atomic: bool
    completion_criteria: Optional[dict] = None
    success_definition: Optional[dict] = None


@dataclass(frozen=True)
class DecompositionDecision:
    """
    Результат работы Decomposer - "намерения", а не мутации.
    
    Это чистый return value - decomposer не знает про базу.
    """
    parent_snapshot: GoalSnapshot
    state_changes: list[GoalStateChange]
    proposed_subgoals: list[ProposedSubgoal]
    diagnostics: dict
    
    @property
    def success(self) -> bool:
        return len(self.proposed_subgoals) > 0


# Aliases для обратной совместимости
IntentGoalStateChange = GoalStateChange
IntentProposedSubgoal = ProposedSubgoal
IntentDecompositionResult = DecompositionDecision
