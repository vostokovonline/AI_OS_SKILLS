"""
STABILITY MONITOR LAYER

Monitors long-term stability of the autonomous loop:
- Entropy trends (diversity over time)
- Dominance detection (single strategy taking over)
- Drift detection (behavioral changes)
- EMA oscillation (instability indicators)

Critical for validating Stage 3 hardening before Stage 4.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import deque
import math
import json

from logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class StabilityMetrics:
    """Metrics for a single observation window."""
    cycle: int
    timestamp: str
    
    # Entropy (diversity measure)
    entropy: float
    
    # Dominance (max single-strategy share)
    dominant_strategy: str
    dominant_share: float
    
    # Distribution (strategy → selection count)
    distribution: Dict[str, int]
    total_selections: int
    
    # Drift indicators
    entropy_change: float  # Change from previous window
    distribution_stability: float  # How similar to previous (0-1)
    
    # Warnings
    warnings: List[str] = field(default_factory=list)
    
    def is_healthy(self) -> bool:
        """Check if system is in healthy state."""
        return len(self.warnings) == 0


@dataclass
class StabilityConfig:
    """Configuration for stability monitoring."""
    # Entropy thresholds
    entropy_min: float = 0.5  # Below this = too deterministic
    entropy_warning: float = 0.7  # Below this = warning
    
    # Dominance thresholds
    dominance_max: float = 0.7  # Max share for single strategy
    dominance_warning: float = 0.5  # Warning at this share
    
    # Drift thresholds
    entropy_change_max: float = 0.3  # Max change per window
    distribution_stability_min: float = 0.7  # Min similarity to previous
    
    # Window sizes
    observation_window: int = 100  # Cycles per observation
    history_size: int = 50  # Number of observations to keep


class StabilityMonitor:
    """
    Monitors stability of autonomous loop over time.
    
    Key responsibilities:
    1. Track entropy over time (diversity)
    2. Detect dominance (one strategy taking over)
    3. Detect drift (behavioral changes)
    4. Generate warnings when thresholds violated
    
    Usage:
        monitor = StabilityMonitor()
        
        for cycle in range(3000):
            # ... arbitration happens ...
            monitor.record_selection(cycle, strategy_id)
            
            if cycle % 100 == 0:
                metrics = monitor.observe()
                print(f"Entropy: {metrics.entropy:.3f}")
                if not metrics.is_healthy():
                    print(f"WARNING: {metrics.warnings}")
    """
    
    def __init__(self, config: Optional[StabilityConfig] = None):
        self.config = config or StabilityConfig()
        
        # Selection history
        self._selections: deque = deque(
            maxlen=self.config.observation_window * 10
        )
        
        # Metrics history
        self._metrics_history: deque = deque(
            maxlen=self.config.history_size
        )
        
        # Current window tracking
        self._current_cycle: int = 0
        self._last_observation_cycle: int = 0
    
    def record_selection(self, cycle: int, strategy_id: str):
        """Record a strategy selection."""
        self._current_cycle = cycle
        self._selections.append({
            "cycle": cycle,
            "strategy": strategy_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def observe(self) -> StabilityMetrics:
        """
        Observe current stability state.
        
        Analyzes selections in current window and generates metrics.
        """
        # Get selections in observation window
        recent_selections = list(self._selections)[-self.config.observation_window:]
        
        if not recent_selections:
            return StabilityMetrics(
                cycle=self._current_cycle,
                timestamp=datetime.utcnow().isoformat(),
                entropy=0.0,
                dominant_strategy="none",
                dominant_share=0.0,
                distribution={},
                total_selections=0,
                entropy_change=0.0,
                distribution_stability=1.0,
                warnings=["No selections recorded"]
            )
        
        # Calculate distribution
        distribution: Dict[str, int] = {}
        for sel in recent_selections:
            sid = sel["strategy"][:8]  # Use short ID
            distribution[sid] = distribution.get(sid, 0) + 1
        
        total = len(recent_selections)
        
        # Calculate entropy
        entropy = self._calculate_entropy(distribution, total)
        
        # Find dominant strategy
        dominant_strategy, dominant_share = self._find_dominant(distribution, total)
        
        # Calculate drift indicators
        entropy_change = 0.0
        distribution_stability = 1.0
        
        if self._metrics_history:
            prev = self._metrics_history[-1]
            entropy_change = abs(entropy - prev.entropy)
            distribution_stability = self._calculate_distribution_similarity(
                distribution, prev.distribution
            )
        
        # Generate warnings
        warnings = self._generate_warnings(
            entropy=entropy,
            dominant_share=dominant_share,
            entropy_change=entropy_change,
            distribution_stability=distribution_stability
        )
        
        # Create metrics
        metrics = StabilityMetrics(
            cycle=self._current_cycle,
            timestamp=datetime.utcnow().isoformat(),
            entropy=round(entropy, 4),
            dominant_strategy=dominant_strategy,
            dominant_share=round(dominant_share, 4),
            distribution=distribution,
            total_selections=total,
            entropy_change=round(entropy_change, 4),
            distribution_stability=round(distribution_stability, 4),
            warnings=warnings
        )
        
        # Record in history
        self._metrics_history.append(metrics)
        self._last_observation_cycle = self._current_cycle
        
        # Log if unhealthy
        if not metrics.is_healthy():
            logger.warning(
                "stability_warning",
                cycle=self._current_cycle,
                entropy=metrics.entropy,
                dominant_share=metrics.dominant_share,
                warnings=metrics.warnings
            )
        
        return metrics
    
    def _calculate_entropy(self, distribution: Dict[str, int], total: int) -> float:
        """Calculate Shannon entropy of distribution."""
        if total == 0:
            return 0.0
        
        entropy = 0.0
        for count in distribution.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        return entropy
    
    def _find_dominant(self, distribution: Dict[str, int], total: int) -> Tuple[str, float]:
        """Find the most dominant strategy."""
        if not distribution:
            return "none", 0.0
        
        max_strategy = max(distribution, key=distribution.get)
        max_count = distribution[max_strategy]
        share = max_count / total if total > 0 else 0.0
        
        return max_strategy, share
    
    def _calculate_distribution_similarity(
        self, 
        dist1: Dict[str, int], 
        dist2: Dict[str, int]
    ) -> float:
        """
        Calculate similarity between two distributions.
        
        Uses Jaccard-like similarity on normalized distributions.
        """
        if not dist1 or not dist2:
            return 1.0 if not dist1 and not dist2 else 0.0
        
        # Normalize
        total1 = sum(dist1.values())
        total2 = sum(dist2.values())
        
        if total1 == 0 or total2 == 0:
            return 0.0
        
        norm1 = {k: v / total1 for k, v in dist1.items()}
        norm2 = {k: v / total2 for k, v in dist2.items()}
        
        # Calculate overlap (sum of min for each key)
        all_keys = set(norm1.keys()) | set(norm2.keys())
        overlap = sum(min(norm1.get(k, 0), norm2.get(k, 0)) for k in all_keys)
        
        return overlap
    
    def _generate_warnings(
        self,
        entropy: float,
        dominant_share: float,
        entropy_change: float,
        distribution_stability: float
    ) -> List[str]:
        """Generate warnings based on thresholds."""
        warnings = []
        
        # Entropy warnings
        if entropy < self.config.entropy_min:
            warnings.append(f"CRITICAL: Entropy {entropy:.3f} below minimum {self.config.entropy_min}")
        elif entropy < self.config.entropy_warning:
            warnings.append(f"WARNING: Entropy {entropy:.3f} below warning threshold {self.config.entropy_warning}")
        
        # Dominance warnings
        if dominant_share > self.config.dominance_max:
            warnings.append(f"CRITICAL: Dominant strategy has {dominant_share:.1%} share (max {self.config.dominance_max:.1%})")
        elif dominant_share > self.config.dominance_warning:
            warnings.append(f"WARNING: Dominant strategy has {dominant_share:.1%} share")
        
        # Drift warnings
        if entropy_change > self.config.entropy_change_max:
            warnings.append(f"WARNING: Entropy changed by {entropy_change:.3f} (max {self.config.entropy_change_max})")
        
        if distribution_stability < self.config.distribution_stability_min:
            warnings.append(f"WARNING: Distribution stability {distribution_stability:.3f} below {self.config.distribution_stability_min}")
        
        return warnings
    
    def get_summary(self) -> Dict:
        """Get summary statistics from history."""
        if not self._metrics_history:
            return {"observations": 0}
        
        history = list(self._metrics_history)
        
        # Calculate averages
        avg_entropy = sum(m.entropy for m in history) / len(history)
        avg_dominant_share = sum(m.dominant_share for m in history) / len(history)
        
        # Count warnings
        total_warnings = sum(len(m.warnings) for m in history)
        unhealthy_count = sum(1 for m in history if not m.is_healthy())
        
        # Entropy trend
        if len(history) >= 2:
            first_half = history[:len(history)//2]
            second_half = history[len(history)//2:]
            first_avg = sum(m.entropy for m in first_half) / len(first_half)
            second_avg = sum(m.entropy for m in second_half) / len(second_half)
            entropy_trend = "increasing" if second_avg > first_avg else "decreasing"
        else:
            entropy_trend = "unknown"
        
        return {
            "observations": len(history),
            "total_selections": self._selections.__len__() if self._selections else 0,
            "avg_entropy": round(avg_entropy, 4),
            "avg_dominant_share": round(avg_dominant_share, 4),
            "total_warnings": total_warnings,
            "unhealthy_observations": unhealthy_count,
            "health_rate": round(1 - unhealthy_count / len(history), 4) if history else 1.0,
            "entropy_trend": entropy_trend,
            "last_cycle": history[-1].cycle if history else 0
        }
    
    def export_history(self, filepath: str):
        """Export metrics history to JSON for analysis."""
        history = [
            {
                "cycle": m.cycle,
                "entropy": m.entropy,
                "dominant_strategy": m.dominant_strategy,
                "dominant_share": m.dominant_share,
                "entropy_change": m.entropy_change,
                "distribution_stability": m.distribution_stability,
                "warnings": m.warnings,
                "is_healthy": m.is_healthy()
            }
            for m in self._metrics_history
        ]
        
        with open(filepath, 'w') as f:
            json.dump(history, f, indent=2)
        
        logger.info("stability_history_exported", filepath=filepath, observations=len(history))
    
    def reset(self):
        """Reset all tracking."""
        self._selections.clear()
        self._metrics_history.clear()
        self._current_cycle = 0
        self._last_observation_cycle = 0


# Singleton
_stability_monitor: Optional[StabilityMonitor] = None


def get_stability_monitor(config: Optional[StabilityConfig] = None) -> StabilityMonitor:
    """Get or create global stability monitor."""
    global _stability_monitor
    if _stability_monitor is None:
        _stability_monitor = StabilityMonitor(config)
    return _stability_monitor


def reset_stability_monitor():
    """Reset global monitor."""
    global _stability_monitor
    if _stability_monitor:
        _stability_monitor.reset()
