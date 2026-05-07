"""
Decision Policies - Arbitration Layer
==================================

Политики принятия решений для bulk execution.

Принцип: Policy решает ЧТО применять, BulkEngine знает только КАК.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from application.policies.arbitration_trace import ArbitrationTrace
    from application.bulk_engine import BulkExecutionIntent


@dataclass(frozen=True)
class ScoredIntent:
    """
    Intent с оценкой для принятия решения.
    
    Политика использует эти поля для ranking/selection.
    """
    intent: "BulkExecutionIntent"
    utility: float      # Оценка полезности (0-1)
    cost: float         # Оценка стоимости (0-1)
    risk: float        # Оценка риска (0-1)


class DecisionPolicy(ABC):
    """
    Абстрактная политика принятия решений.
    
    Принцип: Policy.select() решает, BulkEngine.apply() только применяет.
    """
    
    @abstractmethod
    async def select(
        self,
        scored: List[ScoredIntent],
        budget: Optional[int] = None
    ) -> List[ScoredIntent]:
        """
        Выбрать подмножество intents для применения.
        
        Args:
            scored: Список scored intents
            budget: Максимум intents (None = без лимита)
            
        Returns:
            Выбранные intents для применения
        """
        pass


class PassThroughPolicy(DecisionPolicy):
    """
    Пропускает все intents без изменений.
    
    Используется для:
    - Тестирования bulk без политики
    - Baseline для сравнения
    - Начальной валидации архитектуры
    """
    
    async def select(
        self,
        scored: List[ScoredIntent],
        budget: Optional[int] = None,
        trace: "ArbitrationTrace" = None
    ) -> List[ScoredIntent]:
        """
        Пропускает всё без изменений.
        
        trace - optional, если передан - записывает решения.
        """
        # Записываем если trace передан
        if trace:
            for s in scored:
                trace.record(
                    intent_id=s.intent.goal_id,
                    utility=s.utility,
                    cost=s.cost,
                    risk=s.risk,
                    selected=True
                )
        
        if budget is None:
            return scored
        return scored[:budget]


class GreedyUtilityPolicy(DecisionPolicy):
    """
    Greedy политика - выбирает по убыванию utility.
    
    ВАЖНО: Не использует ratio (utility/cost)!
    Это убивает batch semantics.
    
    Правильная модель:
    1. Сортируем по utility DESC
    2. Берём первые budget
    """
    
    async def select(
        self,
        scored: List[ScoredIntent],
        budget: Optional[int] = None,
        trace: "ArbitrationTrace" = None
    ) -> List[ScoredIntent]:
        """
        Выбрать top-k по utility.
        
        Args:
            scored: Отсортированные по убыванию utility
            budget: Максимум для выбора
            trace: Optional trace для записи решений
        """
        # Сортируем по utility DESC (детерминированно)
        sorted_intents = sorted(
            scored, 
            key=lambda s: s.utility, 
            reverse=True
        )
        
        # Записываем решения в trace если передан
        if trace:
            for i, s in enumerate(sorted_intents):
                is_selected = (budget is None) or (i < budget)
                reason = None if is_selected else f"budget_limit:{budget}"
                
                trace.record(
                    intent_id=s.intent.goal_id,
                    utility=s.utility,
                    cost=s.cost,
                    risk=s.risk,
                    selected=is_selected,
                    rejection_reason=reason
                )
        
        # Берём первые budget
        if budget is not None:
            return sorted_intents[:budget]
        
        return sorted_intents


class UtilityCostAwarePolicy(DecisionPolicy):
    """
    Политика учитывающая и utility, и cost.
    
    Но НЕ через ratio! Использует пороги.
    
    Правило:
    - utility >= min_utility
    - cost <= max_cost
    - Сортировка по utility - cost
    """
    
    def __init__(
        self,
        min_utility: float = 0.3,
        max_cost: float = 0.7
    ):
        self.min_utility = min_utility
        self.max_cost = max_cost
    
    async def select(
        self,
        scored: List[ScoredIntent],
        budget: Optional[int] = None,
        trace: "ArbitrationTrace" = None
    ) -> List[ScoredIntent]:
        """
        Фильтруем по порогам, сортируем по utility - cost.
        """
        # Фильтр
        filtered = []
        for s in scored:
            passes = s.utility >= self.min_utility and s.cost <= self.max_cost
            
            if trace:
                trace.record(
                    intent_id=s.intent.goal_id,
                    utility=s.utility,
                    cost=s.cost,
                    risk=s.risk,
                    selected=passes,
                    rejection_reason=None if passes else "threshold_failed"
                )
            
            if passes:
                filtered.append(s)
        
        # Сортировка
        sorted_intents = sorted(
            filtered,
            key=lambda s: s.utility - s.cost,
            reverse=True
        )
        
        if budget is not None:
            return sorted_intents[:budget]
        
        return sorted_intents
        
        if budget is not None:
            return sorted_intents[:budget]
        
        return sorted_intents


# NOTE: Global state removed!
# Policy should be passed explicitly through UseCase.
# This makes decisions observable and testable.
# 
# Usage:
#   use_case = MyUseCase(policy=PassThroughPolicy())
#   use_case = MyUseCase(policy=GreedyUtilityPolicy())
