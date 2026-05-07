"""
DETERMINISTIC TEST: Adaptive Strategy Weighting

Question: Do strategies with better performance get higher priority?

Controlled test:
- Two strategies with same base priority
- One has good performance (90% success)
- One has poor performance (40% success)
- After min_samples activations, effective priorities should diverge
"""
import sys
sys.path.insert(0, '/app')

from uuid import uuid4
from datetime import datetime

from autonomy.arbitration import (
    ActionArbitrator,
    ArbitrationConfig,
    ArbitrationContext,
    StrategyConfig,
    StrategyRuntimeStats,
    EmotionalSnapshot,
    ResourceSnapshot,
    SystemStateSnapshot,
    RiskLevel
)
from autonomy.adaptive_weights import (
    AdaptiveWeightCalculator,
    AdaptiveWeightConfig,
    reset_adaptive_weight_calculator
)
from autonomy.policy_engine import ActionType


def create_strategy_stats(activation_count: int, success_rate: float) -> StrategyRuntimeStats:
    """Create stats with given success rate."""
    success_count = int(activation_count * success_rate)
    return StrategyRuntimeStats(
        strategy_id=uuid4(),
        activation_count=activation_count,
        success_count=success_count,
        failure_count=activation_count - success_count,
        cumulative_cost=activation_count * 50.0,
        last_activated_at=datetime.utcnow()
    )


def create_strategy_config(priority: float = 0.7) -> StrategyConfig:
    """Create config with given priority."""
    return StrategyConfig(
        strategy_id=uuid4(),
        name="Test Strategy",
        description="Test",
        priority=priority,
        default_risk_level=RiskLevel.MEDIUM,
        cost_estimate=50.0
    )


def test_adaptive_weighting_basic():
    """Test that performance affects priority."""
    
    reset_adaptive_weight_calculator()
    
    print("="*70)
    print("ADAPTIVE WEIGHTING TEST")
    print("="*70)
    
    config = AdaptiveWeightConfig(min_samples=5)
    calculator = AdaptiveWeightCalculator(config)
    
    # Same base priority
    base_priority = 0.7
    
    # Good performance: 90% success
    good_stats = create_strategy_stats(activation_count=20, success_rate=0.9)
    good_priority = calculator.calculate_effective_priority(base_priority, good_stats)
    
    # Poor performance: 40% success
    poor_stats = create_strategy_stats(activation_count=20, success_rate=0.4)
    poor_priority = calculator.calculate_effective_priority(base_priority, poor_stats)
    
    print(f"\nBase priority: {base_priority}")
    print(f"\nGood strategy (90% success, 20 activations):")
    print(f"  Effective priority: {good_priority:.4f}")
    print(f"  Adjustment: {(good_priority/base_priority - 1)*100:+.1f}%")
    
    print(f"\nPoor strategy (40% success, 20 activations):")
    print(f"  Effective priority: {poor_priority:.4f}")
    print(f"  Adjustment: {(poor_priority/base_priority - 1)*100:+.1f}%")
    
    print(f"\nSpread: {good_priority - poor_priority:.4f}")
    print(f"Ratio: {good_priority/poor_priority:.2f}x")
    
    # Validation
    print("\n" + "="*70)
    print("VALIDATION")
    print("="*70)
    
    # Test 1: Good strategy gets bonus
    test1 = good_priority > base_priority
    print(f"\n1. Good performance gets bonus: {test1}")
    tests = [test1]
    
    # Test 2: Poor strategy gets penalty
    test2 = poor_priority < base_priority
    print(f"2. Poor performance gets penalty: {test2}")
    tests.append(test2)
    
    # Test 3: Significant spread
    spread = good_priority - poor_priority
    test3 = spread > 0.05
    print(f"3. Significant spread (>0.05): {test3} (spread={spread:.3f})")
    tests.append(test3)
    
    success = all(tests)
    
    print("\n" + "="*70)
    if success:
        print("✓ PASS: Adaptive weighting works correctly")
        print(f"  Good strategy: {good_priority:.3f} (+{(good_priority/base_priority-1)*100:.0f}%)")
        print(f"  Poor strategy: {poor_priority:.3f} ({(poor_priority/base_priority-1)*100:.0f}%)")
    else:
        print("✗ FAIL: Adaptive weighting not working")
    print("="*70)
    
    return success


def test_low_confidence_neutral():
    """Test that low sample count stays near neutral."""
    
    reset_adaptive_weight_calculator()
    
    print("\n" + "="*70)
    print("HYSTERESIS TEST: Low Confidence = Neutral")
    print("="*70)
    
    config = AdaptiveWeightConfig(min_samples=5)
    calculator = AdaptiveWeightCalculator(config)
    
    base_priority = 0.7
    
    # Very few activations (low confidence)
    low_sample_stats = create_strategy_stats(activation_count=2, success_rate=1.0)
    low_sample_priority = calculator.calculate_effective_priority(base_priority, low_sample_stats)
    
    print(f"\nStrategy with only 2 activations (100% success):")
    print(f"  Base priority: {base_priority}")
    print(f"  Effective priority: {low_sample_priority:.4f}")
    print(f"  Adjustment: {(low_sample_priority/base_priority - 1)*100:+.1f}%")
    
    # Should be close to base (no adjustment due to low confidence)
    close_to_base = abs(low_sample_priority - base_priority) < 0.01
    
    print(f"\n  Close to base (hysteresis): {close_to_base}")
    
    return close_to_base


def test_performance_metrics():
    """Test performance metrics calculation."""
    
    print("\n" + "="*70)
    print("PERFORMANCE METRICS TEST")
    print("="*70)
    
    from autonomy.adaptive_weights import PerformanceCalculator
    
    calc = PerformanceCalculator()
    
    # Good stats
    good_stats = create_strategy_stats(activation_count=20, success_rate=0.9)
    good_metrics = calc.calculate(good_stats)
    
    print(f"\nGood strategy (90% success):")
    print(f"  success_rate: {good_metrics.success_rate:.2f}")
    print(f"  confidence: {good_metrics.confidence:.2f}")
    print(f"  effective_performance: {good_metrics.effective_performance:.2f}")
    
    # Poor stats
    poor_stats = create_strategy_stats(activation_count=20, success_rate=0.4)
    poor_metrics = calc.calculate(poor_stats)
    
    print(f"\nPoor strategy (40% success):")
    print(f"  success_rate: {poor_metrics.success_rate:.2f}")
    print(f"  confidence: {poor_metrics.confidence:.2f}")
    print(f"  effective_performance: {poor_metrics.effective_performance:.2f}")
    
    # Good should have higher effective performance
    return good_metrics.effective_performance > poor_metrics.effective_performance


if __name__ == "__main__":
    results = []
    
    results.append(test_adaptive_weighting_basic())
    results.append(test_low_confidence_neutral())
    results.append(test_performance_metrics())
    
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"Test 1 (Basic weighting): {'PASS' if results[0] else 'FAIL'}")
    print(f"Test 2 (Hysteresis): {'PASS' if results[1] else 'FAIL'}")
    print(f"Test 3 (Metrics): {'PASS' if results[2] else 'FAIL'}")
    
    success = all(results)
    print(f"\nOverall: {'✓ ALL PASS' if success else '✗ SOME FAILED'}")
    print("="*70)
    
    sys.exit(0 if success else 1)
