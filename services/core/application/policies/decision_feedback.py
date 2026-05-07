"""
Decision Feedback - Regret Analysis
==================================

Анализ качества решений политики.

Принцип:
- Сравниваем что ВЫБРАЛИ vs что ОТКЛОНИЛИ
- Regret = полезность отклонённого - полезность выбранного
"""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class RegretAnalysis:
    """
    Результат анализа regret.
    
    Показывает ценность потерянных решений.
    """
    cycle_id: str
    policy_name: str
    
    # Выбранные
    selected_count: int
    selected_avg_utility: float
    selected_total_utility: float
    
    # Отклонённые
    rejected_count: int
    rejected_avg_utility: float
    rejected_total_utility: float
    
    # Regret метрики
    potential_utility_lost: float  # Сколько полезности потеряли
    regret_ratio: float            # regret / selected_utility
    
    # Metadata
    budget_limit: Optional[int]
    timestamp: datetime


class DecisionFeedback:
    """
    Анализ качества решений на основе Trace.
    
    Использование:
        feedback = DecisionFeedback()
        analysis = feedback.analyze(trace, execution_result)
    """
    
    def analyze(
        self,
        trace_records: List,  # ArbitrationRecord list
        budget_limit: Optional[int] = None
    ) -> RegretAnalysis:
        """
        Анализировать regret на основе trace.
        
        Args:
            trace_records: Список ArbitrationRecord
            budget_limit: Лимит который был при выборе
            
        Returns:
            RegretAnalysis с метриками
        """
        if not trace_records:
            return self._empty_analysis()
        
        selected = [r for r in trace_records if r.selected]
        rejected = [r for r in trace_records if not r.selected]
        
        selected_utility = [r.utility for r in selected]
        rejected_utility = [r.utility for r in rejected]
        
        selected_total = sum(selected_utility)
        rejected_total = sum(rejected_utility)
        
        # Regret = полезность лучшего отклонённого - полезность худшего выбранного
        # Упрощённо: potential_utility_lost = max(rejected) - min(selected)
        potential_lost = 0
        if rejected and selected:
            best_rejected = max(rejected_utility)
            worst_selected = min(selected_utility)
            potential_lost = max(0, best_rejected - worst_selected)
        
        regret_ratio = 0
        if selected_total > 0:
            regret_ratio = potential_lost / selected_total
        
        cycle_id = trace_records[0].cycle_id if trace_records else "unknown"
        
        return RegretAnalysis(
            cycle_id=str(cycle_id),
            policy_name=trace_records[0].policy_name if trace_records else "unknown",
            
            selected_count=len(selected),
            selected_avg_utility=sum(selected_utility) / len(selected_utility) if selected_utility else 0,
            selected_total_utility=selected_total,
            
            rejected_count=len(rejected),
            rejected_avg_utility=sum(rejected_utility) / len(rejected_utility) if rejected_utility else 0,
            rejected_total_utility=rejected_total,
            
            potential_utility_lost=potential_lost,
            regret_ratio=regret_ratio,
            
            budget_limit=budget_limit,
            timestamp=datetime.utcnow()
        )
    
    def _empty_analysis(self) -> RegretAnalysis:
        return RegretAnalysis(
            cycle_id="empty",
            policy_name="unknown",
            selected_count=0,
            selected_avg_utility=0,
            selected_total_utility=0,
            rejected_count=0,
            rejected_avg_utility=0,
            rejected_total_utility=0,
            potential_utility_lost=0,
            regret_ratio=0,
            budget_limit=None,
            timestamp=datetime.utcnow()
        )
    
    def should_improve_policy(self, analysis: RegretAnalysis) -> bool:
        """
        Нужно ли улучшать политику?
        
        Правило: если regret_ratio > 0.3 - есть куда расти.
        """
        return analysis.regret_ratio > 0.3


# Usage Example:
#
# # After execution
# feedback = DecisionFeedback()
# analysis = feedback.analyze(trace.get_records(), budget=10)
#
# print(f"Regret ratio: {analysis.regret_ratio:.2%}")
# print(f"Potential utility lost: {analysis.potential_utility_lost:.2f}")
#
# if feedback.should_improve_policy(analysis):
#     print("Policy should be improved!")
