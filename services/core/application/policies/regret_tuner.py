"""
Regret-Driven Policy Tuner
=========================

Автоматическая настройка политик на основе regret analysis.

Принцип:
- Собираем historical regret
- Если avg regret > threshold → предлагаем улучшение
- Пока только эвристика, не ML
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta


@dataclass
class PolicyRecommendation:
    """
    Рекомендация по улучшению политики.
    """
    policy_name: str
    current_params: dict
    recommended_params: dict
    reason: str
    expected_improvement: float
    confidence: float  # 0-1 насколько уверены
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RegretDrivenTuner:
    """
    Тюнер политик на основе исторического regret.
    
    Пока минимальный - эвристический.
    
    Usage:
        tuner = RegretDrivenTuner()
        
        # После нескольких циклов
        recommendation = tuner.analyze_and_suggest(
            policy_name="GreedyUtilityPolicy",
            regret_history=[0.1, 0.15, 0.25, 0.35]
        )
        
        if recommendation:
            print(f"Improve: {recommendation.reason}")
    """
    
    def __init__(
        self,
        regret_threshold: float = 0.25,
        improvement_threshold: float = 0.1
    ):
        """
        Args:
            regret_threshold: Когда avg regret > этого → предлагаем улучшение
            improvement_threshold: Минимальное ожидаемое улучшение
        """
        self.regret_threshold = regret_threshold
        self.improvement_threshold = improvement_threshold
    
    def analyze_and_suggest(
        self,
        policy_name: str,
        regret_history: List[float],
        current_params: Optional[dict] = None
    ) -> Optional[PolicyRecommendation]:
        """
        Проанализировать историю и предложить улучшение.
        
        Args:
            policy_name: Имя политики
            regret_history: Список regret_ratio за последние N циклов
            current_params: Текущие параметры политики
            
        Returns:
            PolicyRecommendation или None если улучшение не нужно
        """
        if len(regret_history) < 3:
            return None  # Недостаточно данных
        
        avg_regret = sum(regret_history) / len(regret_history)
        
        # Если avg regret в пределах нормы - не предлагаем
        if avg_regret <= self.regret_threshold:
            return None
        
        # Анализируем тренд
        recent = regret_history[-3:]
        trend = recent[-1] - sum(recent[:-1]) / len(recent[:-1])
        
        # Строим рекомендацию на основе политики
        if policy_name == "GreedyUtilityPolicy":
            return self._suggest_greedy_improvement(
                current_params or {},
                avg_regret,
                trend
            )
        
        elif policy_name == "UtilityCostAwarePolicy":
            return self._suggest_cost_aware_improvement(
                current_params or {},
                avg_regret,
                trend
            )
        
        return None
    
    def _suggest_greedy_improvement(
        self,
        current_params: dict,
        avg_regret: float,
        trend: float
    ) -> PolicyRecommendation:
        """
        GreedyPolicy: если regret растёт → возможно слишком жёсткий budget.
        
        Рекомендация: увеличить budget или смягчить cutoff.
        """
        current_budget = current_params.get("budget", 10)
        
        # Если тренд растёт и high regret → предлагаем увеличить budget
        if trend > 0 and avg_regret > 0.3:
            new_budget = min(current_budget + 5, 50)  # Max 50
            
            return PolicyRecommendation(
                policy_name="GreedyUtilityPolicy",
                current_params=current_params,
                recommended_params={**current_params, "budget": new_budget},
                reason=f"High regret ({avg_regret:.1%}) with rising trend. Consider larger budget.",
                expected_improvement=0.15,
                confidence=0.7
            )
        
        return PolicyRecommendation(
            policy_name="GreedyUtilityPolicy",
            current_params=current_params,
            recommended_params=current_params,
            reason="Regret is moderate, no significant action needed",
            expected_improvement=0.0,
            confidence=0.5
        )
    
    def _suggest_cost_aware_improvement(
        self,
        current_params: dict,
        avg_regret: float,
        trend: float
    ) -> PolicyRecommendation:
        """
        UtilityCostAwarePolicy: если regret высокий → возможно too strict thresholds.
        """
        current_min_utility = current_params.get("min_utility", 0.3)
        current_max_cost = current_params.get("max_cost", 0.7)
        
        # Смягчаем пороги
        new_min_utility = max(current_min_utility - 0.1, 0.1)
        new_max_cost = min(current_max_cost + 0.1, 1.0)
        
        return PolicyRecommendation(
            policy_name="UtilityCostAwarePolicy",
            current_params=current_params,
            recommended_params={
                "min_utility": new_min_utility,
                "max_cost": new_max_cost
            },
            reason=f"High regret ({avg_regret:.1%}). Consider relaxing thresholds.",
            expected_improvement=0.2,
            confidence=0.6
        )
    
    def get_statistics(
        self,
        regret_history: List[float]
    ) -> dict:
        """
        Получить статистику по истории regret.
        """
        if not regret_history:
            return {"count": 0}
        
        return {
            "count": len(regret_history),
            "avg": sum(regret_history) / len(regret_history),
            "min": min(regret_history),
            "max": max(regret_history),
            "recent_3_avg": sum(regret_history[-3:]) / min(3, len(regret_history)),
            "trend": regret_history[-1] - regret_history[0] if len(regret_history) > 1 else 0
        }


# Global tuner instance
_tuner: Optional[RegretDrivenTuner] = None


def get_tuner() -> RegretDrivenTuner:
    global _tuner
    if _tuner is None:
        _tuner = RegretDrivenTuner()
    return _tuner


# Usage:
#
# tuner = get_tuner()
#
# # After several cycles
# history = [0.1, 0.12, 0.15, 0.25, 0.35]  # regret_history
#
# recommendation = tuner.analyze_and_suggest(
#     policy_name="GreedyUtilityPolicy",
#     regret_history=history,
#     current_params={"budget": 10}
# )
#
# if recommendation:
#     print(f"Recommend: {recommendation.recommended_params}")
#     print(f"Reason: {recommendation.reason}")
#     print(f"Expected improvement: {recommendation.expected_improvement:.1%}")
