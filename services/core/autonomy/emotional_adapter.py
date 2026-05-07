"""
Emotional Adapter for Arbitration Layer - PRODUCTION VERSION

Converts from system's EmotionalLayer to Arbitration's EmotionalSnapshot.

Day 4: Production-grade stress model with:
- Non-linear aggregation (complementary probability)
- Stress memory (exponential inertia)
- Asymmetric decay
- Hysteresis (different enter/exit thresholds)
- Behavioral modes

Architecture:
    Signals → Normalization → Nonlinear Aggregation
           → Memory Layer
           → Decay Controller  
           → Mode Switch (Hysteresis)
           → Arbitration Modifier
"""
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

from autonomy.arbitration import EmotionalSnapshot


class StressMode(str, Enum):
    """Behavioral modes based on stress level"""
    NORMAL = "normal"          # 0.0 - 0.4
    CONSERVATIVE = "conservative"  # 0.4 - 0.7
    DEFENSIVE = "defensive"    # 0.7 - 0.85
    SURVIVAL = "survival"      # 0.85+


@dataclass
class StressState:
    """
    Production-grade stress state with memory and hysteresis.
    
    Key properties:
    - Non-linear aggregation prevents "averaging down"
    - Memory prevents rapid oscillation
    - Decay slower than growth (realistic recovery)
    - Hysteresis prevents mode thrashing
    """
    # Current stress level (0.0 - 1.0)
    value: float = 0.3
    
    # Behavioral mode
    mode: StressMode = StressMode.NORMAL
    
    # Timestamp of last update
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    # Configuration (can be tuned per deployment)
    inertia_alpha: float = 0.85  # Memory weight (0.7-0.9)
    growth_rate: float = 0.15    # Speed of stress increase
    recovery_rate: float = 0.05  # Speed of stress decrease (slower!)
    
    # Hysteresis thresholds (calibrated for scaled non-linear model)
    conservative_threshold: float = 0.35
    defensive_threshold: float = 0.55
    survival_threshold: float = 0.80
    
    # Exit thresholds (lower than entry - prevents oscillation)
    conservative_exit: float = 0.25
    defensive_exit: float = 0.40
    survival_exit: float = 0.60
    
    # Factor weights (must sum to 1.0)
    weight_overload: float = 0.30
    weight_deadline: float = 0.25
    weight_failure: float = 0.20
    weight_budget: float = 0.15
    weight_uncertainty: float = 0.10
    
    # Scaling factor to allow reaching survival threshold
    # With weights summing to 1.0, max stress = 0.68
    # Scaling by 1.5 allows reaching 0.85+
    stress_scale: float = 1.5
    
    def __post_init__(self):
        """Validate weights"""
        total = (self.weight_overload + self.weight_deadline + 
                 self.weight_failure + self.weight_budget + self.weight_uncertainty)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Factor weights must sum to 1.0, got {total}")
        self.value = max(0.0, min(1.0, self.value))
    
    def update(self, signals: dict) -> float:
        """
        Update stress from signals using production model.
        
        Steps:
        1. Extract and normalize factors
        2. Non-linear aggregation
        3. Apply memory (inertia)
        4. Asymmetric decay
        5. Update mode with hysteresis
        
        Returns:
            New stress value (0.0 - 1.0)
        """
        # Step 1: Extract factors
        factors = self._extract_factors(signals)
        
        # Step 2: Non-linear aggregation
        # stress_instant = 1 - ∏(1 - w_i * factor_i)
        # This prevents "averaging down" - one strong factor dominates
        stress_instant = self._nonlinear_aggregate(factors)
        
        # Step 3: Apply memory (exponential inertia)
        # stress(t) = α * stress(t-1) + (1-α) * stress_instant
        stress_with_memory = self._apply_memory(stress_instant)
        
        # Step 4: Asymmetric decay
        # Recovery is slower than growth
        stress_final = self._apply_decay(stress_with_memory, stress_instant)
        
        # Update value
        self.value = max(0.0, min(1.0, stress_final))
        
        # Step 5: Update mode with hysteresis
        self.mode = self._determine_mode(self.value)
        
        # Update timestamp
        self.last_updated = datetime.utcnow()
        
        return self.value
    
    def _extract_factors(self, signals: dict) -> Dict[str, float]:
        """Extract and normalize stress factors from signals."""
        factors = {}
        
        # Overload: active_goals / max_goals
        active_goals = signals.get("active_goals", 0)
        max_goals = signals.get("max_goals", 100)
        if max_goals > 0:
            factors["overload"] = min(1.0, active_goals / max_goals)
        else:
            factors["overload"] = 0.0
        
        # Deadline: exponential pressure as deadline approaches
        deadline_hours = signals.get("deadline_hours")
        if deadline_hours is not None and deadline_hours > 0:
            if deadline_hours < 24:
                # 24h = 0.5, 4h = 0.8, 1h = 0.95
                factors["deadline"] = 1.0 - (deadline_hours / 24) * 0.5
            else:
                factors["deadline"] = 0.0
        else:
            factors["deadline"] = 0.0
        
        # Failure rate: recent_failures / recent_total
        recent_failures = signals.get("recent_failures", 0)
        recent_total = signals.get("recent_total", 0)
        if recent_total > 0:
            factors["failure"] = min(1.0, recent_failures / recent_total)
        else:
            factors["failure"] = 0.0
        
        # Budget: inverse of remaining ratio
        budget_remaining = signals.get("budget_remaining", 100)
        budget_limit = signals.get("budget_limit", 100)
        if budget_limit > 0:
            factors["budget"] = max(0.0, 1.0 - (budget_remaining / budget_limit))
        else:
            factors["budget"] = 0.0
        
        # Uncertainty: from signals or default
        factors["uncertainty"] = signals.get("uncertainty", 0.0)
        
        return factors
    
    def _nonlinear_aggregate(self, factors: Dict[str, float]) -> float:
        """
        Non-linear aggregation using complementary probability.
        
        stress = 1 - ∏(1 - w_i * factor_i)
        
        Then scaled to allow reaching higher thresholds.
        
        Properties:
        - One strong factor → high stress
        - Multiple medium factors → cumulative growth
        - No factors → zero stress
        - Can't "average down" like with mean
        """
        # Map factor names to weights
        weights = {
            "overload": self.weight_overload,
            "deadline": self.weight_deadline,
            "failure": self.weight_failure,
            "budget": self.weight_budget,
            "uncertainty": self.weight_uncertainty
        }
        
        # Calculate product of (1 - w_i * factor_i)
        product = 1.0
        for name, value in factors.items():
            weight = weights.get(name, 0.1)
            contribution = 1.0 - (weight * value)
            product *= contribution
        
        # Complement gives stress
        stress_instant = 1.0 - product
        
        # Scale to allow reaching survival threshold
        stress_instant = min(1.0, stress_instant * self.stress_scale)
        
        return stress_instant
    
    def _apply_memory(self, stress_instant: float) -> float:
        """
        Apply exponential inertia (memory).
        
        stress(t) = α * stress(t-1) + (1-α) * stress_instant
        
        High α = system "remembers" overload, less impulsive
        """
        return (self.inertia_alpha * self.value + 
                (1 - self.inertia_alpha) * stress_instant)
    
    def _apply_decay(self, stress_with_memory: float, stress_instant: float) -> float:
        """
        Asymmetric decay - recovery is slower than growth.
        
        If stress is increasing: use full growth rate
        If stress is decreasing: use slower recovery rate
        """
        if stress_instant > self.value:
            # Stress increasing - fast response
            return stress_with_memory
        else:
            # Stress decreasing - slow recovery
            # Only allow small decreases per step
            decay_amount = min(
                self.recovery_rate,
                self.value - stress_with_memory
            )
            return max(stress_with_memory, self.value - decay_amount)
    
    def _determine_mode(self, stress: float) -> StressMode:
        """
        Determine behavioral mode with hysteresis.
        
        Hysteresis: exit threshold < entry threshold
        This prevents oscillation at boundary.
        """
        current_mode = self.mode
        
        # Survival mode (0.85+)
        if stress >= self.survival_threshold:
            return StressMode.SURVIVAL
        elif current_mode == StressMode.SURVIVAL and stress < self.survival_exit:
            return StressMode.DEFENSIVE
        
        # Defensive mode (0.70 - 0.85)
        if stress >= self.defensive_threshold:
            return StressMode.DEFENSIVE
        elif current_mode == StressMode.DEFENSIVE and stress < self.defensive_exit:
            return StressMode.CONSERVATIVE
        
        # Conservative mode (0.40 - 0.70)
        if stress >= self.conservative_threshold:
            return StressMode.CONSERVATIVE
        elif current_mode == StressMode.CONSERVATIVE and stress < self.conservative_exit:
            return StressMode.NORMAL
        
        # Normal mode (0.0 - 0.40)
        return StressMode.NORMAL
    
    def get_mode_params(self) -> dict:
        """
        Get arbitration parameters based on current mode.
        
        Returns modifiers for:
        - risk_weight: how much risk affects decisions
        - exploration: willingness to try new strategies
        - batch_size: how many tasks to run in parallel
        - planning_depth: how far ahead to plan
        """
        if self.mode == StressMode.NORMAL:
            return {
                "risk_weight": 1.0,
                "exploration": 1.0,
                "batch_size": 5,
                "planning_depth": 3,
                "parallelism": 1.0
            }
        elif self.mode == StressMode.CONSERVATIVE:
            return {
                "risk_weight": 1.5,
                "exploration": 0.7,
                "batch_size": 3,
                "planning_depth": 2,
                "parallelism": 0.7
            }
        elif self.mode == StressMode.DEFENSIVE:
            return {
                "risk_weight": 2.5,
                "exploration": 0.3,
                "batch_size": 2,
                "planning_depth": 1,
                "parallelism": 0.4
            }
        else:  # SURVIVAL
            return {
                "risk_weight": 5.0,
                "exploration": 0.1,  # Never zero - agent must find new solutions
                "batch_size": 1,
                "planning_depth": 1,
                "parallelism": 0.1
            }


# Global stress state (singleton pattern)
_stress_state: Optional[StressState] = None


def get_stress_state() -> StressState:
    """Get or create global stress state."""
    global _stress_state
    if _stress_state is None:
        _stress_state = StressState()
    return _stress_state


def reset_stress_state() -> None:
    """Reset stress state (for testing)."""
    global _stress_state
    _stress_state = None


def calculate_stress_from_signals(signals: dict) -> float:
    """
    Calculate stress level from signals using production model.
    
    This is the main entry point for stress calculation.
    Updates global stress state and returns current value.
    
    Args:
        signals: Dict with:
            - active_goals: int
            - max_goals: int
            - deadline_hours: float or None
            - recent_failures: int
            - recent_total: int
            - budget_remaining: float
            - budget_limit: float
            - uncertainty: float (0..1)
    
    Returns:
        Stress level 0..1
    """
    state = get_stress_state()
    return state.update(signals)


def emotional_state_to_snapshot(
    state: dict,
    default_momentum: float = 0.5
) -> EmotionalSnapshot:
    """
    Convert emotional_layer state dict to EmotionalSnapshot.
    
    Args:
        state: Dict from EmotionalLayer with keys:
            - arousal: 0..1
            - valence: -1..1
            - focus: 0..1
            - confidence: 0..1
        default_momentum: Default momentum value (0..1)
    
    Returns:
        EmotionalSnapshot for arbitration
    """
    arousal = state.get("arousal", 0.5)
    valence = state.get("valence", 0.0)
    focus = state.get("focus", 0.5)
    confidence = state.get("confidence", 0.5)
    
    # Map focus to stress (inverse)
    stress = 1.0 - focus
    
    # Clamp all values
    stress = max(0.0, min(1.0, stress))
    arousal = max(0.0, min(1.0, arousal))
    valence = max(-1.0, min(1.0, valence))
    confidence = max(0.0, min(1.0, confidence))
    momentum = max(0.0, min(1.0, default_momentum))
    
    return EmotionalSnapshot(
        valence=valence,
        arousal=arousal,
        stress=stress,
        confidence=confidence,
        momentum=momentum
    )


def calculate_momentum_from_history(
    recent_outcomes: list,
    window: int = 10
) -> float:
    """
    Calculate momentum from recent goal outcomes.
    
    Momentum = weighted success rate with recency bias.
    
    Args:
        recent_outcomes: List of booleans (True = success, False = failure)
        window: Number of recent outcomes to consider
    
    Returns:
        Momentum 0..1
    """
    if not recent_outcomes:
        return 0.5
    
    outcomes = recent_outcomes[-window:]
    
    # Weighted average with recency bias
    total_weight = 0
    weighted_sum = 0
    
    for i, outcome in enumerate(outcomes):
        weight = i + 1
        value = 1.0 if outcome else 0.0
        weighted_sum += value * weight
        total_weight += weight
    
    if total_weight == 0:
        return 0.5
    
    return weighted_sum / total_weight
