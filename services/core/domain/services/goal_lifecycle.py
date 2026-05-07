"""
Domain Services - Goal Lifecycle Machine
=========================================
Формальная state machine для управления жизненным циклом целей.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Set


class GoalLifecycleState(Enum):
    """
    Полный набор состояний жизненного цикла цели.
    Каждое состояние имеет строго определённые переходы.
    """
    CREATED = "created"           # Цель только создана
    READY = "ready"               # Готова к планированию
    PLANNING = "planning"         # Декомпозиция/планирование
    EXECUTING = "executing"        # Выполнение
    EVALUATING = "evaluating"     # Оценка результатов
    COMPLETED = "completed"        # Успешно завершена
    FAILED = "failed"              # Неудача
    BLOCKED = "blocked"            # Заблокирована (зависимость)
    ONGOING = "ongoing"           # Непрерывная (continuous)
    FROZEN = "frozen"              # Заморожена
    RETRY = "retry"               # Повторная попытка


class TransitionReason(Enum):
    """Причины переходов - для аудита"""
    INITIAL_CREATION = "initial_creation"
    USER_REQUEST = "user_request"
    SYSTEM_READY = "system_ready"
    DECOMPOSITION_STARTED = "decomposition_started"
    DECOMPOSITION_COMPLETE = "decomposition_complete"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETE = "execution_complete"
    ALL_CHILDREN_DONE = "all_children_done"
    DEPENDENCY_NOT_MET = "dependency_not_met"
    DEPENDENCY_MET = "dependency_met"
    EVALUATION_PASSED = "evaluation_passed"
    EVALUATION_FAILED = "evaluation_failed"
    NO_PASSED_ARTIFACTS = "no_passed_artifacts"
    MANUAL_COMPLETION = "manual_completion"
    SYSTEM_ERROR = "system_error"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    FREEZE_REQUESTED = "freeze_requested"
    UNFREEZE_REQUESTED = "unfreeze_requested"


@dataclass
class Transition:
    """Описание перехода"""
    from_state: GoalLifecycleState
    to_state: GoalLifecycleState
    reason: TransitionReason
    allowed_goals_types: Set[str]  # Для каких типов целей применимо
    
    # Optional guards
    guard: Optional[Callable] = None


class GoalLifecycleMachine:
    """
    Формальная state machine для целей.
    
    Инварианты:
    - Из терминальных состояний (COMPLETED, FAILED, FROZEN) нет переходов
    - BLOCKED → READY только при выполнении зависимостей
    - Continuous goals не переходят в COMPLETED (используют ONGOING)
    """
    
    # Терминальные состояния
    TERMINAL_STATES = {
        GoalLifecycleState.COMPLETED,
        GoalLifecycleState.FAILED,
        GoalLifecycleState.FROZEN,
    }
    
    # Полный граф переходов
    TRANSITIONS: List[Transition] = [
        # Создание
        Transition(GoalLifecycleState.CREATED, GoalLifecycleState.READY, TransitionReason.SYSTEM_READY, {"*"}),
        
        # Планирование
        Transition(GoalLifecycleState.READY, GoalLifecycleState.PLANNING, TransitionReason.DECOMPOSITION_STARTED, {"*"}),
        Transition(GoalLifecycleState.PLANNING, GoalLifecycleState.EXECUTING, TransitionReason.DECOMPOSITION_COMPLETE, {"*"}),
        
        # Выполнение
        Transition(GoalLifecycleState.EXECUTING, GoalLifecycleState.EVALUATING, TransitionReason.EXECUTION_COMPLETE, {"*"}),
        
        # Оценка
        Transition(GoalLifecycleState.EVALUATING, GoalLifecycleState.COMPLETED, TransitionReason.EVALUATION_PASSED, {"achievable", "exploratory", "meta"}),
        Transition(GoalLifecycleState.EVALUATING, GoalLifecycleState.RETRY, TransitionReason.EVALUATION_FAILED, {"*"}),
        Transition(GoalLifecycleState.EVALUATING, GoalLifecycleState.ONGOING, TransitionReason.EVALUATION_PASSED, {"continuous"}),
        
        # Retry loop
        Transition(GoalLifecycleState.RETRY, GoalLifecycleState.EXECUTING, TransitionReason.SYSTEM_READY, {"*"}),
        Transition(GoalLifecycleState.RETRY, GoalLifecycleState.FAILED, TransitionReason.MAX_RETRIES_EXCEEDED, {"*"}),
        
        # Блокировка
        Transition(GoalLifecycleState.CREATED, GoalLifecycleState.BLOCKED, TransitionReason.DEPENDENCY_NOT_MET, {"*"}),
        Transition(GoalLifecycleState.READY, GoalLifecycleState.BLOCKED, TransitionReason.DEPENDENCY_NOT_MET, {"*"}),
        Transition(GoalLifecycleState.EXECUTING, GoalLifecycleState.BLOCKED, TransitionReason.DEPENDENCY_NOT_MET, {"*"}),
        
        # Разблокировка
        Transition(GoalLifecycleState.BLOCKED, GoalLifecycleState.READY, TransitionReason.DEPENDENCY_MET, {"*"}),
        
        # Freeze
        Transition(GoalLifecycleState.CREATED, GoalLifecycleState.FROZEN, TransitionReason.FREEZE_REQUESTED, {"*"}),
        Transition(GoalLifecycleState.READY, GoalLifecycleState.FROZEN, TransitionReason.FREEZE_REQUESTED, {"*"}),
        Transition(GoalLifecycleState.BLOCKED, GoalLifecycleState.FROZEN, TransitionReason.FREEZE_REQUESTED, {"*"}),
        
        # Unfreeze
        Transition(GoalLifecycleState.FROZEN, GoalLifecycleState.READY, TransitionReason.UNFREEZE_REQUESTED, {"*"}),
        
        # Manual completion (edge case)
        Transition(GoalLifecycleState.EXECUTING, GoalLifecycleState.COMPLETED, TransitionReason.MANUAL_COMPLETION, {"achievable"}),
    ]
    
    def __init__(self):
        self._build_transition_map()
    
    def _build_transition_map(self) -> None:
        """Построить словарь допустимых переходов"""
        self._allowed_transitions: Dict[GoalLifecycleState, Dict[GoalLifecycleState, Set[TransitionReason]]]] = {}  # type: ignore
        
        for t in self.TRANSITIONS:
            if t.from_state not in self._allowed_transitions:
                self._allowed_transitions[t.from_state] = {}
            
            if t.to_state not in self._allowed_transitions[t.from_state]:
                self._allowed_transitions[t.from_state][t.to_state] = set()
            
            self._allowed_transitions[t.from_state][t.to_state].add(t.reason)
    
    def get_allowed_transitions(self, current_state: GoalLifecycleState, goal_type: str = "*") -> Dict[GoalLifecycleState, Set[TransitionReason]]:
        """
        Получить все допустимые переходы из текущего состояния.
        
        Returns:
            Dict[to_state -> Set[reasons]]
        """
        if current_state in self.TERMINAL_STATES:
            return {}  # No transitions from terminal states
        
        allowed = self._allowed_transitions.get(current_state, {})
        
        # Filter by goal_type
        result = {}
        for to_state, reasons in allowed.items():
            filtered_reasons = {
                r for r in reasons
                if r in [t.reason for t in self.TRANSITIONS 
                        if t.from_state == current_state and t.to_state == to_state
                        and ("*" in t.allowed_goals_types or goal_type in t.allowed_goals_types)]
            }
            if filtered_reasons:
                result[to_state] = filtered_reasons
        
        return result
    
    def can_transition(self, from_state: GoalLifecycleState, to_state: GoalLifecycleState, 
                       goal_type: str = "*", reason: Optional[TransitionReason] = None) -> bool:
        """
        Проверить возможен ли переход.
        
        Args:
            from_state: Текущее состояние
            to_state: Желаемое состояние
            goal_type: Тип цели
            reason: Причина перехода (если указана - проверяется точнее)
        """
        if from_state in self.TERMINAL_STATES:
            return False
        
        allowed = self._allowed_transitions.get(from_state, {})
        
        if to_state not in allowed:
            return False
        
        if reason:
            return reason in allowed[to_state]
        
        return True
    
    def validate_transition(self, from_state: GoalLifecycleState, to_state: GoalLifecycleState,
                           goal_type: str, reason: TransitionReason) -> Optional[str]:
        """
        Валидировать переход. Возвращает ошибку если невалиден.
        """
        # Terminal state check
        if from_state in self.TERMINAL_STATES:
            return f"Cannot transition from terminal state '{from_state.value}'"
        
        # Goal type specific rules
        if goal_type == "continuous" and to_state == GoalLifecycleState.COMPLETED:
            return "Continuous goals cannot transition to COMPLETED. Use ONGOING."
        
        if goal_type == "directional" and to_state == GoalLifecycleState.COMPLETED:
            return "Directional goals cannot transition to COMPLETED. Use FROZEN or keep as ONGOING."
        
        # Check if transition exists
        if not self.can_transition(from_state, to_state, goal_type, reason):
            allowed = self.get_allowed_transitions(from_state, goal_type)
            allowed_str = ", ".join([f"{s.value} ({rs})" for s, rs in allowed.items()])
            return f"Invalid transition: {from_state.value} → {to_state.value}. Allowed: {allowed_str or 'none'}"
        
        return None  # Valid
    
    def get_next_states(self, current_state: GoalLifecycleState, goal_type: str = "*") -> List[GoalLifecycleState]:
        """Получить все возможные следующие состояния"""
        allowed = self.get_allowed_transitions(current_state, goal_type)
        return list(allowed.keys())


# Глобальный экземпляр
goal_lifecycle_machine = GoalLifecycleMachine()
