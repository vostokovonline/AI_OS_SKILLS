"""
ADAPTIVE STRATEGY WEIGHTING - Stage 3

Adjusts strategy priorities based on observed performance.

Key principles:
1. Better performing strategies get higher effective priority
2. Minimum samples required before adjustment (hysteresis)
3. Gradual adjustment (no sudden jumps)
4. Uses EMA from stability_guards (not instant success_rate)

Architecture:
    RuntimeStats → FailureShockAbsorber (EMA) → PerformanceCalculator → AdaptiveWeight
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from autonomy.arbitration import StrategyRuntimeStats
from autonomy.stability_guards import get_failure_shock_absorber
from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """
    Calculated performance metrics for a strategy.
    
    All values 0.0 to 1.0.
    """
    success_rate: float          # Historical success rate
    confidence: float            # How confident we are (based on sample size)
    recent_trend: float          # -0.5 to +0.5 (getting worse/better)
    effective_performance: float # Combined metric for weighting
    
    # Raw data for debugging
    activation_count: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class AdaptiveWeightConfig:
    """
    Configuration for adaptive weighting.
    
    Tunable parameters for production.
    """
    # Minimum activations before performance affects weight
    min_samples: int = 5
    
    # Maximum performance bonus (e.g., 0.3 = up to 30% boost)
    max_performance_bonus: float = 0.3
    
    # Maximum performance penalty (e.g., 0.2 = up to 20% reduction)
    max_performance_penalty: float = 0.2
    
    # Neutral point (success rate at which no adjustment)
    neutral_success_rate: float = 0.7
    
    # Recency window for trend calculation (recent N activations)
    recency_window: int = 10
    
    # Trend weight (how much recent trend affects performance)
    trend_weight: float = 0.3
    
    # Smoothing factor for gradual changes
    smoothing_alpha: float = 0.7


class PerformanceCalculator:
    """
    Calculates performance metrics from runtime stats.
    
    Stateless - just calculations.
    """
    
    def __init__(self, config: Optional[AdaptiveWeightConfig] = None):
        self.config = config or AdaptiveWeightConfig()
    
    def calculate(self, stats: StrategyRuntimeStats) -> PerformanceMetrics:
        """
        Calculate performance metrics from runtime stats.
        
        Uses EMA-smoothed success rate from FailureShockAbsorber if available,
        otherwise falls back to raw success_rate from stats.
        """
        activation_count = stats.activation_count
        success_count = stats.success_count
        failure_count = stats.failure_count
        
        # Raw success rate
        raw_success_rate = success_count / activation_count if activation_count > 0 else 0.5
        
        # Confidence (based on sample size)
        confidence = min(1.0, activation_count / self.config.min_samples)
        
        # Get EMA-smoothed success rate from shock absorber
        strategy_id = str(stats.strategy_id)
        shock_absorber = get_failure_shock_absorber()
        
        # Check if shock absorber has data for this strategy
        has_ema_data = strategy_id in shock_absorber._ema_success
        
        if has_ema_data:
            # Use EMA (smoothed)
            ema_success = shock_absorber.get_ema_success(strategy_id)
            protection_factor = shock_absorber.get_protection_factor(strategy_id)
            base_performance = ema_success
            
            # Apply shock protection
            if protection_factor < 1.0:
                base_performance = (
                    base_performance * protection_factor +
                    self.config.neutral_success_rate * (1 - protection_factor)
                )
        else:
            # Fall back to raw success rate
            base_performance = raw_success_rate
        
        # Effective performance
        if confidence < 1.0:
            # Not enough samples - use neutral performance
            effective_performance = self.config.neutral_success_rate
        else:
            effective_performance = base_performance
        
        # Clamp
        effective_performance = max(0.0, min(1.0, effective_performance))
        
        return PerformanceMetrics(
            success_rate=raw_success_rate,
            confidence=confidence,
            recent_trend=0.0,  # EMA handles smoothing
            effective_performance=effective_performance,
            activation_count=activation_count,
            success_count=success_count,
            failure_count=failure_count
        )
    
    def _calculate_trend(self, stats: StrategyRuntimeStats) -> float:
        """
        Calculate recent trend (-0.5 to +0.5).
        
        Positive = getting better
        Negative = getting worse
        """
        # Check if we have recent activations
        if len(stats.recent_activations) < 2:
            return 0.0
        
        # Split recent activations into first half and second half
        mid = len(stats.recent_activations) // 2
        
        # For now, use a simple heuristic based on activation count
        # (In production, you'd track success/failure per activation)
        
        # If we have enough data, estimate trend from overall success rate
        if stats.activation_count >= self.config.recency_window:
            # Assume recent performance is similar to overall
            # (This is a simplification - in production, track separately)
            overall_rate = stats.success_count / stats.activation_count
            
            # Trend relative to neutral
            trend = (overall_rate - self.config.neutral_success_rate) * 0.5
            return max(-0.5, min(0.5, trend))
        
        return 0.0


class AdaptiveWeightCalculator:
    """
    Calculates adaptive weights for strategies.
    
    Combines base priority with performance adjustment.
    """
    
    def __init__(self, config: Optional[AdaptiveWeightConfig] = None):
        self.config = config or AdaptiveWeightConfig()
        self.performance_calc = PerformanceCalculator(self.config)
        
        # Cache for smoothing (strategy_id -> last_weight)
        self._weight_cache: dict = {}
    
    def calculate_effective_priority(
        self,
        base_priority: float,
        stats: StrategyRuntimeStats
    ) -> float:
        """
        Calculate effective priority with performance adjustment.
        
        Args:
            base_priority: Strategy's configured priority (0.0-1.0)
            stats: Runtime statistics for this strategy
        
        Returns:
            Effective priority (can be higher or lower than base)
        """
        # Calculate performance
        perf = self.performance_calc.calculate(stats)
        
        # If low confidence, use base priority
        if perf.confidence < 1.0:
            logger.debug(
                "adaptive_weight_low_confidence",
                activations=perf.activation_count,
                required=self.config.min_samples
            )
            return base_priority
        
        # Calculate adjustment
        # Above neutral = bonus, below neutral = penalty
        performance_delta = perf.effective_performance - self.config.neutral_success_rate
        
        if performance_delta > 0:
            # Good performance - apply bonus
            adjustment = performance_delta * self.config.max_performance_bonus
            adjustment = min(adjustment, self.config.max_performance_bonus)
        else:
            # Poor performance - apply penalty
            adjustment = performance_delta * self.config.max_performance_penalty
            adjustment = max(adjustment, -self.config.max_performance_penalty)
        
        # Calculate effective priority
        effective = base_priority * (1.0 + adjustment)
        
        # Apply smoothing (gradual changes)
        strategy_id = str(stats.strategy_id)
        if strategy_id in self._weight_cache:
            last_weight = self._weight_cache[strategy_id]
            effective = (
                self.config.smoothing_alpha * last_weight +
                (1 - self.config.smoothing_alpha) * effective
            )
        
        # Cache for next time
        self._weight_cache[strategy_id] = effective
        
        # Clamp
        effective = max(0.0, min(2.0, effective))
        
        if adjustment != 0:
            logger.debug(
                "adaptive_weight_adjusted",
                strategy_id=strategy_id,
                base=base_priority,
                effective=effective,
                adjustment_pct=adjustment * 100
            )
        
        return effective
    
    def get_performance_metrics(self, stats: StrategyRuntimeStats) -> PerformanceMetrics:
        """Get detailed performance metrics for a strategy."""
        return self.performance_calc.calculate(stats)
    
    def reset_cache(self):
        """Reset weight cache (for testing)."""
        self._weight_cache.clear()


# Singleton for global use
_adaptive_weight_calculator: Optional[AdaptiveWeightCalculator] = None


def get_adaptive_weight_calculator(
    config: Optional[AdaptiveWeightConfig] = None
) -> AdaptiveWeightCalculator:
    """Get or create global adaptive weight calculator."""
    global _adaptive_weight_calculator
    if _adaptive_weight_calculator is None:
        _adaptive_weight_calculator = AdaptiveWeightCalculator(config)
    return _adaptive_weight_calculator


def reset_adaptive_weight_calculator():
    """Reset global calculator (for testing)."""
    global _adaptive_weight_calculator
    _adaptive_weight_calculator = None
