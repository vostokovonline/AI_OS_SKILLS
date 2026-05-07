"""
Safe Auto-Tuning Loop
====================

Безопасный auto-tuning с защитами от рисков.

Safeguards:
1. Gradual changes - шаг не более +2 за цикл
2. Smoothing - анализ по 5+ циклам
3. Minimum threshold - только при avg_regret > 0.3 И тренд > 0
4. Rollback capability - можем откатить
5. Hybrid mode - suggestion vs auto
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable
from datetime import datetime
from enum import Enum

from application.policies.decision_feedback import DecisionFeedback, RegretAnalysis
from application.policies.regret_tuner import RegretDrivenTuner, PolicyRecommendation


class TuningMode(Enum):
    """Режим работы tuner"""
    OFF = "off"                    # Выключен
    SUGGEST = "suggest"           # Только предлагает
    AUTO = "auto"                  # Автоматически применяет


@dataclass
class TuningEvent:
    """
    Запись изменения параметров.
    """
    cycle_id: str
    policy_name: str
    old_params: dict
    new_params: dict
    reason: str
    expected_improvement: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TuningState:
    """
    Состояние tuner для одной политики.
    """
    policy_name: str
    current_params: dict
    param_history: List[TuningEvent] = field(default_factory=list)
    enabled: bool = True
    mode: TuningMode = TuningMode.SUGGEST
    
    # Safeguards
    min_regret_threshold: float = 0.3
    min_cycles_for_analysis: int = 5
    max_step_size: int = 2  # Макс изменение за цикл
    
    # Rollback
    last_rollback: Optional[datetime] = None


class SafeAutoTuner:
    """
    Safe auto-tuning с safeguards.
    
    Usage:
        tuner = SafeAutoTuner()
        
        # Регистрируем политику
        tuner.register_policy(
            "GreedyUtilityPolicy",
            {"budget": 10},
            mode=TuningMode.SUGGEST  # Сначала только предлагаем
        )
        
        # После каждого цикла
        action = tuner.process_cycle(
            policy_name="GreedyUtilityPolicy",
            regret_history=[0.1, 0.15, 0.2, 0.25, 0.35],
            current_regret=0.35
        )
        
        # action: {"type": "suggest"|"apply"|"none", "params": {...}, "reason": "..."}
    """
    
    def __init__(self):
        self._policies: dict[str, TuningState] = {}
        self._feedback = DecisionFeedback()
        self._tuner = RegretDrivenTuner(
            regret_threshold=0.3,
            improvement_threshold=0.1
        )
        
        # Callbacks для alerting/rollback
        self._on_change: Optional[Callable] = None
        self._on_suggestion: Optional[Callable] = None
    
    def register_policy(
        self,
        policy_name: str,
        initial_params: dict,
        mode: TuningMode = TuningMode.SUGGEST,
        min_regret_threshold: float = 0.3
    ) -> None:
        """Зарегистрировать политику для tuning"""
        self._policies[policy_name] = TuningState(
            policy_name=policy_name,
            current_params=initial_params.copy(),
            mode=mode,
            min_regret_threshold=min_regret_threshold
        )
    
    def set_mode(self, policy_name: str, mode: TuningMode) -> bool:
        """Изменить режим для политики"""
        if policy_name in self._policies:
            self._policies[policy_name].mode = mode
            return True
        return False
    
    def set_callbacks(
        self,
        on_change: Optional[Callable] = None,
        on_suggestion: Optional[Callable] = None
    ) -> None:
        """Установить callbacks для alerting"""
        self._on_change = on_change
        self._on_suggestion = on_suggestion
    
    def process_cycle(
        self,
        policy_name: str,
        regret_history: List[float],
        current_regret: float
    ) -> dict:
        """
        Обработать результаты цикла.
        
        Returns:
            {"type": "suggest"|"apply"|"none", "params": {...}, "reason": "..."}
        """
        if policy_name not in self._policies:
            return {"type": "none", "reason": "policy_not_registered"}
        
        state = self._policies[policy_name]
        
        if not state.enabled:
            return {"type": "none", "reason": "tuning_disabled"}
        
        # Safeguard 1: Недостаточно данных
        if len(regret_history) < state.min_cycles_for_analysis:
            return {
                "type": "none",
                "reason": f"need_{state.min_cycles_for_analysis}_cycles",
                "current_regret": current_regret
            }
        
        # Safeguard 2: Проверяем порог и тренд
        avg_regret = sum(regret_history) / len(regret_history)
        
        # Safeguard 3: Тренд (только если последний > предыдущих)
        trend = 0
        if len(regret_history) >= 3:
            recent = regret_history[-3:]
            trend = recent[-1] - sum(recent[:-1]) / len(recent[:-1])
        
        # Не применяем если avg <= threshold или тренд не положительный
        should_tune = (
            avg_regret > state.min_regret_threshold and 
            trend > 0
        )
        
        if not should_tune:
            return {
                "type": "none",
                "reason": "regret_acceptable",
                "avg_regret": avg_regret,
                "trend": trend
            }
        
        # Получаем рекомендацию
        recommendation = self._tuner.analyze_and_suggest(
            policy_name=policy_name,
            regret_history=regret_history,
            current_params=state.current_params
        )
        
        if not recommendation or recommendation.expected_improvement <= 0:
            return {"type": "none", "reason": "no_improvement_suggested"}
        
        # Safeguard 4: Gradual changes - ограничиваем шаг
        new_params = self._apply_step_limit(
            state.current_params,
            recommendation.recommended_params,
            state.max_step_size
        )
        
        # Проверяем, что есть реальное изменение
        if new_params == state.current_params:
            return {"type": "none", "reason": "no_effective_change"}
        
        # Decision: apply или suggest
        if state.mode == TuningMode.SUGGEST:
            # Только предлагаем
            if self._on_suggestion:
                self._on_suggestion(policy_name, new_params, recommendation.reason)
            
            return {
                "type": "suggest",
                "params": new_params,
                "reason": recommendation.reason,
                "expected_improvement": recommendation.expected_improvement,
                "current": state.current_params
            }
        
        elif state.mode == TuningMode.AUTO:
            # Применяем постепенно
            old_params = state.current_params.copy()
            state.current_params = new_params
            
            # Записываем в историю
            event = TuningEvent(
                cycle_id=regret_history[-1],  # Use last as cycle_id
                policy_name=policy_name,
                old_params=old_params,
                new_params=new_params,
                reason=recommendation.reason,
                expected_improvement=recommendation.expected_improvement
            )
            state.param_history.append(event)
            
            # Callback
            if self._on_change:
                self._on_change(policy_name, old_params, new_params)
            
            return {
                "type": "apply",
                "params": new_params,
                "reason": recommendation.reason,
                "old": old_params
            }
        
        return {"type": "none", "reason": "mode_off"}
    
    def _apply_step_limit(
        self,
        current: dict,
        recommended: dict,
        max_step: int
    ) -> dict:
        """Ограничить изменения постепенными шагами"""
        result = current.copy()
        
        for key, new_value in recommended.items():
            if key not in current:
                continue
            
            old_value = current[key]
            
            # Числовые значения - ограничиваем шаг
            if isinstance(new_value, (int, float)) and isinstance(old_value, (int, float)):
                diff = new_value - old_value
                
                # Ограничиваем abs(diff) <= max_step
                if abs(diff) > max_step:
                    new_value = old_value + (max_step if diff > 0 else -max_step)
            
            result[key] = new_value
        
        return result
    
    def rollback(self, policy_name: str, steps: int = 1) -> Optional[dict]:
        """
        Откатить параметры назад.
        
        Returns:
            Новые параметры или None если нечего откатывать
        """
        if policy_name not in self._policies:
            return None
        
        state = self._policies[policy_name]
        
        if len(state.param_history) < steps:
            return None
        
        # Находим нужный момент
        target_event = state.param_history[-steps]
        state.current_params = target_event.old_params.copy()
        
        state.last_rollback = datetime.utcnow()
        
        return state.current_params
    
    def get_state(self, policy_name: str) -> Optional[dict]:
        """Получить состояние политики"""
        if policy_name not in self._policies:
            return None
        
        state = self._policies[policy_name]
        
        return {
            "policy_name": state.policy_name,
            "current_params": state.current_params,
            "mode": state.mode.value,
            "enabled": state.enabled,
            "tuning_events_count": len(state.param_history),
            "last_rollback": state.last_rollback.isoformat() if state.last_rollback else None
        }
    
    def get_all_states(self) -> dict:
        """Получить состояние всех политик"""
        return {
            name: self.get_state(name)
            for name in self._policies
        }


# Global instance
_safe_tuner: Optional[SafeAutoTuner] = None


def get_safe_tuner() -> SafeAutoTuner:
    global _safe_tuner
    if _safe_tuner is None:
        _safe_tuner = SafeAutoTuner()
    return _safe_tuner


# Usage:
#
# tuner = get_safe_tuner()
#
# # Register policy in SUGGEST mode first
# tuner.register_policy(
#     "GreedyUtilityPolicy",
#     {"budget": 10},
#     mode=TuningMode.SUGGEST
# )
#
# # After each cycle
# action = tuner.process_cycle(
#     policy_name="GreedyUtilityPolicy",
#     regret_history=[0.1, 0.15, 0.2, 0.25, 0.35, 0.4],
#     current_regret=0.4
# )
#
# if action["type"] == "suggest":
#     print(f"Consider: {action['params']} - {action['reason']}")
#     # Человек подтверждает
#     tuner.set_mode("GreedyUtilityPolicy", TuningMode.AUTO)
#
# elif action["type"] == "apply":
#     print(f"Applied: {action['params']}")
#
# # Rollback if needed
# tuner.rollback("GreedyUtilityPolicy")
