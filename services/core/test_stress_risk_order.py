"""
DETERMINISTIC TEST: Stress → Risk Ordering

Direct test of risk_adjustment at different stress levels.
"""
import sys
sys.path.insert(0, '/app')

from uuid import uuid4

from autonomy.arbitration import (
    ActionArbitrator,
    ArbitrationConfig,
    ArbitrationContext,
    EmotionalSnapshot,
    ResourceSnapshot,
    SystemStateSnapshot,
    DecisionAction,
    RiskLevel
)
from autonomy.policy_engine import ActionType


def create_test_action(risk_level: RiskLevel) -> DecisionAction:
    return DecisionAction(
        id=uuid4(),
        action_type=ActionType.CREATE_GOAL,
        action_payload={},
        strategy_id=uuid4(),
        source_rule_name="test",
        reason="test",
        risk_level=risk_level,
        cost_estimate=50.0
    )


def create_context(stress: float, confidence: float = 0.5) -> ArbitrationContext:
    emotional = EmotionalSnapshot(
        valence=0.0,
        arousal=0.5,
        stress=stress,
        confidence=confidence,
        momentum=0.5
    )
    
    resource = ResourceSnapshot(
        budget_remaining=50,
        budget_limit=100,
        concurrent_goals=30,
        max_concurrent_goals=100,
        compute_available=0.5
    )
    
    system = SystemStateSnapshot(
        metrics={"active_goals": 30},
        trends={}
    )
    
    return ArbitrationContext(
        emotion=emotional,
        resources=resource,
        system_state=system,
        strategy_configs={},
        strategy_stats={},
        config=ArbitrationConfig()
    )


def main():
    print("="*70)
    print("DETERMINISTIC TEST: Risk Adjustment at Different Stress Levels")
    print("="*70)
    
    arbitrator = ActionArbitrator()
    
    risk_levels = [
        RiskLevel.MINIMAL,
        RiskLevel.LOW,
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL
    ]
    
    stress_scenarios = [
        ("NORMAL", 0.2, 0.6),
        ("CONSERVATIVE", 0.45, 0.5),
        ("DEFENSIVE", 0.7, 0.4),
        ("SURVIVAL", 0.9, 0.2)
    ]
    
    print("\nRisk adjustment (1.0 = no penalty, lower = worse):")
    print("-"*70)
    print(f"{'Stress Mode':<15} {'MIN':<8} {'LOW':<8} {'MED':<8} {'HIGH':<8} {'CRIT':<8}")
    print("-"*70)
    
    all_results = {}
    
    for mode_name, stress, confidence in stress_scenarios:
        context = create_context(stress, confidence)
        
        penalties = []
        for risk in risk_levels:
            action = create_test_action(risk)
            adjustment = arbitrator._risk_adjustment(context, action)
            penalties.append(adjustment)
        
        all_results[mode_name] = penalties
        
        print(f"{mode_name:<15}", end="")
        for p in penalties:
            print(f" {p:<7.3f}", end="")
        print()
    
    print("-"*70)
    
    # Analysis
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    crit_normal = all_results["NORMAL"][4]
    crit_survival = all_results["SURVIVAL"][4]
    low_normal = all_results["NORMAL"][1]
    low_survival = all_results["SURVIVAL"][1]
    
    ratio_normal = low_normal / crit_normal
    ratio_survival = low_survival / crit_survival
    
    print(f"\nDiscrimination (LOW/CRITICAL utility ratio):")
    print(f"  NORMAL:   {ratio_normal:.2f}x")
    print(f"  SURVIVAL: {ratio_survival:.2f}x")
    print(f"  Increase: {(ratio_survival/ratio_normal - 1) * 100:.0f}%")
    
    spread_normal = low_normal - crit_normal
    spread_survival = low_survival - crit_survival
    
    print(f"\nSpread (LOW utility - CRITICAL utility):")
    print(f"  NORMAL:   {spread_normal:.3f}")
    print(f"  SURVIVAL: {spread_survival:.3f}")
    
    # Tests
    print("\n" + "="*70)
    print("VALIDATION")
    print("="*70)
    
    tests = []
    
    # Test 1: CRITICAL gets penalized more in SURVIVAL
    test1 = crit_survival < crit_normal
    print(f"\n1. CRITICAL penalized more in SURVIVAL: {test1}")
    print(f"   {crit_normal:.3f} → {crit_survival:.3f}")
    tests.append(test1)
    
    # Test 2: Discrimination increases (at least 20%)
    discrimination_increase = (ratio_survival / ratio_normal) - 1
    test2 = discrimination_increase >= 0.20
    print(f"\n2. Discrimination increases ≥20%: {test2}")
    print(f"   {discrimination_increase*100:.0f}% increase")
    tests.append(test2)
    
    # Test 3: Spread increases
    test3 = spread_survival > spread_normal
    print(f"\n3. Spread increases with stress: {test3}")
    tests.append(test3)
    
    # Overall
    success = all(tests)
    
    print("\n" + "="*70)
    if success:
        print("✓ PASS: Risk penalty works correctly")
        print(f"  SURVIVAL mode: LOW is {ratio_survival:.1f}x better than CRITICAL")
        print(f"  (vs {ratio_normal:.1f}x in NORMAL)")
    else:
        print("✗ FAIL: Risk penalty too weak")
    print("="*70)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
