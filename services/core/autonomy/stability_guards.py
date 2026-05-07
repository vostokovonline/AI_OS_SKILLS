"""
STABILITY GUARDS - Stage 3 Hardening
====================================

Architecture: RESILIENCE-FIRST by default.
Strategic flexibility > short-term optimization.

Engineering principles:
1. Anti-monopoly: penalize frequency, not success
2. Failure shock: EMA smoothing, not instant changes
3. Observability: full visibility for control
4. Profile-based: immutable profiles, manual mode switching

Critical: Structural ceiling ALWAYS (0.75-0.85).
No full monopoly allowed - this is a FEATURE, not a bug.

Author: AI-OS Team
Date: 2026-02-21
Version: 2.0.0
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID
from collections import deque
from enum import Enum
import math
import json
from logging_config import get_logger

logger = get_logger(__name__)


# ============================================================
# ARBITRATION PROFILES (Immutable)
# ============================================================

class ArbitrationMode(Enum):
    """Arbitration operating mode."""
    RESILIENCE = "resilience"
    PERFORMANCE = "performance"


@dataclass(frozen=True)
class ArbitrationProfile:
    """
    Immutable arbitration profile.
    
    Architecture principle:
    - NO mutable state in profiles
    - Profiles are infrastructure, not data
    - Switching modes = switching profiles, not mutating
    """
    name: str
    structural_ceiling: float
    min_strategy_breadth: int
    enable_momentum: bool
    stress_threshold: float


# Pre-defined profiles
ARBITRATION_PROFILE_RESILIENCE = ArbitrationProfile(
    name="resilience",
    structural_ceiling=0.75,
    min_strategy_breadth=3,
    enable_momentum=True,
    stress_threshold=0.6
)

ARBITRATION_PROFILE_PERFORMANCE = ArbitrationProfile(
    name="performance", 
    structural_ceiling=0.85,
    min_strategy_breadth=2,
    enable_momentum=True,
    stress_threshold=0.75
)


# ============================================================
# ANTI-MONOPOLY GUARD
# ============================================================

@dataclass
class AntiMonopolyConfig:
    """Configuration for anti-monopoly enforcement."""
    structural_ceiling: float = 0.75
    penalty_frequency_weight: float = 0.15
    min_breadth: int = 3
    observation_window: int = 50


class AntiMonopolyGuard:
    """
    Prevents strategy monopoly through frequency-based penalties.
    
    Architecture: Penalizes frequency, not success.
    - High-frequency strategies get diminishing returns
    - Low-frequency strategies get bonus
    - Structural ceiling enforced (no >75% share)
    
    This is RESILIENCE-FIRST by design.
    """
    
    def __init__(self, config: Optional[AntiMonopolyConfig] = None):
        self.config = config or AntiMonopolyConfig()
        self._selection_counts: Dict[str, int] = {}
        self._total_selections: int = 0
        self._selection_history: deque = deque(maxlen=self.config.observation_window)
    
    def apply(self, strategy_id: str, base_priority: float) -> float:
        """Apply anti-monopoly penalty to strategy priority."""
        self._selection_counts[strategy_id] = self._selection_counts.get(strategy_id, 0) + 1
        self._total_selections += 1
        self._selection_history.append(strategy_id)
        
        if self._total_selections == 0:
            return base_priority
        
        current_share = self._selection_counts[strategy_id] / self._total_selections
        
        if current_share > self.config.structural_ceiling:
            logger.warning(
                "anti_monopoly_ceiling_hit",
                strategy_id=strategy_id[:8],
                current_share=round(current_share, 3),
                ceiling=self.config.structural_ceiling
            )
            return base_priority * 0.5
        
        penalty = self.config.penalty_frequency_weight * current_share
        adjusted = base_priority * (1 - penalty)
        
        return adjusted
    
    def get_share(self, strategy_id: str) -> float:
        """Get current selection share for strategy."""
        if self._total_selections == 0:
            return 0.0
        return self._selection_counts.get(strategy_id, 0) / self._total_selections
    
    def get_stats(self) -> Dict:
        """Get guard statistics."""
        return {
            "total_selections": self._total_selections,
            "unique_strategies": len(self._selection_counts),
            "shares": {
                k: round(v / max(self._total_selections, 1), 3) 
                for k, v in self._selection_counts.items()
            }
        }


# ============================================================
# FAILURE SHOCK ABSORBER
# ============================================================

@dataclass
class ShockAbsorberConfig:
    """Configuration for failure shock absorption."""
    beta: float = 0.2
    initial_ema: float = 0.5
    shock_threshold: int = 4
    protection_factor: float = 0.6
    recovery_rate: float = 0.2


class FailureShockAbsorber:
    """
    Protects strategies from noise using EMA smoothing.
    """
    
    def __init__(self, config: Optional[ShockAbsorberConfig] = None):
        self.config = config or ShockAbsorberConfig()
        self._ema_success: Dict[str, float] = {}
        self._consecutive_failures: Dict[str, int] = {}
    
    def record_outcome(self, strategy_id: str, success: bool):
        """Record outcome and update EMA."""
        current_ema = self._ema_success.get(strategy_id, self.config.initial_ema)
        
        outcome_value = 1.0 if success else 0.0
        new_ema = (1 - self.config.beta) * current_ema + self.config.beta * outcome_value
        
        self._ema_success[strategy_id] = new_ema
        
        if success:
            self._consecutive_failures[strategy_id] = 0
        else:
            self._consecutive_failures[strategy_id] = \
                self._consecutive_failures.get(strategy_id, 0) + 1
        
        logger.debug(
            "ema_updated",
            strategy_id=strategy_id[:8],
            success=success,
            ema_before=round(current_ema, 3),
            ema_after=round(new_ema, 3),
            consecutive_failures=self._consecutive_failures.get(strategy_id, 0)
        )
    
    def get_ema_success(self, strategy_id: str) -> float:
        """Get EMA-smoothed success rate."""
        return self._ema_success.get(strategy_id, self.config.initial_ema)
    
    def apply_shock_protection(self, strategy_id: str, base_priority: float) -> float:
        """Apply shock protection to strategy priority."""
        consecutive = self._consecutive_failures.get(strategy_id, 0)
        
        if consecutive >= self.config.shock_threshold:
            protection = self.config.protection_factor
            protected = base_priority * protection
            
            logger.warning(
                "shock_protection_applied",
                strategy_id=strategy_id[:8],
                consecutive_failures=consecutive,
                original_priority=round(base_priority, 3),
                protected_priority=round(protected, 3)
            )
            return protected
        
        return base_priority
    
    def get_stats(self, strategy_id: str) -> Dict:
        """Get stats for strategy."""
        return {
            "ema_success": round(self.get_ema_success(strategy_id), 3),
            "consecutive_failures": self._consecutive_failures.get(strategy_id, 0)
        }


# ============================================================
# OBSERVABILITY TRACKER
# ============================================================

@dataclass
class CycleObservation:
    """Single cycle observation for tracking."""
    cycle_id: int
    timestamp: str
    strategy_id: str
    strategy_name: str
    base_priority: float
    ema_success: float
    confidence: float
    performance_bonus: float
    adaptive_priority: float
    diminishing_factor: float
    shock_protection: float
    emotion_factor: float
    risk_factor: float
    final_utility: float
    selected: bool


class ObservabilityTracker:
    """
    Tracks arbitration cycles for observability and statistics.
    """
    
    def __init__(self):
        self._cycle_counter: int = 0
        self._observations: List[CycleObservation] = []
    
    def start_cycle(self) -> int:
        """Start a new cycle, return cycle ID."""
        self._cycle_counter += 1
        return self._cycle_counter
    
    def record(self, observation: CycleObservation):
        """Record a cycle observation."""
        self._observations.append(observation)
        
        logger.debug(
            "cycle_observed",
            cycle_id=observation.cycle_id,
            strategy_id=observation.strategy_id[:8],
            selected=observation.selected
        )
    
    def get_selection_distribution(self) -> Dict[str, int]:
        """Get selection count per strategy."""
        distribution: Dict[str, int] = {}
        for obs in self._observations:
            if obs.selected:
                distribution[obs.strategy_id] = distribution.get(obs.strategy_id, 0) + 1
        return distribution
    
    def get_selection_share(self) -> Dict[str, float]:
        """Get selection share per strategy."""
        dist = self.get_selection_distribution()
        total = sum(dist.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in dist.items()}
    
    def get_entropy(self) -> float:
        """Calculate selection entropy (diversity measure)."""
        shares = self.get_selection_share()
        if not shares:
            return 0.0
        
        entropy = 0.0
        for share in shares.values():
            if share > 0:
                entropy -= share * math.log2(share)
        
        return entropy
    
    def get_average_utility(self) -> float:
        """Get average final utility across all observations."""
        if not self._observations:
            return 0.0
        return sum(o.final_utility for o in self._observations) / len(self._observations)
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics."""
        return {
            "total_cycles": self._cycle_counter,
            "total_observations": len(self._observations),
            "selection_distribution": self.get_selection_distribution(),
            "selection_share": {k: round(v, 3) for k, v in self.get_selection_share().items()},
            "entropy": round(self.get_entropy(), 3),
            "average_utility": round(self.get_average_utility(), 3)
        }


# ============================================================
# FACTORY FUNCTIONS (Singleton Pattern)
# ============================================================

_anti_monopoly_guard_instance: Optional[AntiMonopolyGuard] = None
_failure_shock_absorber_instance: Optional[FailureShockAbsorber] = None
_observability_tracker_instance: Optional[ObservabilityTracker] = None


def get_anti_monopoly_guard() -> AntiMonopolyGuard:
    """Get or create AntiMonopolyGuard singleton instance."""
    global _anti_monopoly_guard_instance
    if _anti_monopoly_guard_instance is None:
        _anti_monopoly_guard_instance = AntiMonopolyGuard()
    return _anti_monopoly_guard_instance


def get_failure_shock_absorber() -> FailureShockAbsorber:
    """Get or create FailureShockAbsorber singleton instance."""
    global _failure_shock_absorber_instance
    if _failure_shock_absorber_instance is None:
        _failure_shock_absorber_instance = FailureShockAbsorber()
    return _failure_shock_absorber_instance


def get_observability_tracker() -> ObservabilityTracker:
    """Get or create ObservabilityTracker singleton instance."""
    global _observability_tracker_instance
    if _observability_tracker_instance is None:
        _observability_tracker_instance = ObservabilityTracker()
    return _observability_tracker_instance


def reset_all_guards():
    """Reset all guard instances."""
    global _anti_monopoly_guard_instance, _failure_shock_absorber_instance, _observability_tracker_instance
    _anti_monopoly_guard_instance = None
    _failure_shock_absorber_instance = None
    _observability_tracker_instance = None
    logger.info("all_guards_reset")
