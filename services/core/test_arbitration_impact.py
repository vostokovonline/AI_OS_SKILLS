"""
Arbitration Impact Test - Direct Risk Penalty Validation

Simplified test: Check that stress affects risk penalty directly.
"""
import sys
sys.path.insert(0, '/app')

from uuid import uuid4
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
from autonomy.emotional_adapter import StressMode
from datetime import datetime


def create_test_context(stress: float) -> ArbitrationContext:
    """Create minimal context for testing."""
    
    emotional = EmotionalSnapshot(
        valence=0.0,
        arousal=0.5,
        stress=stress,
        confidence=0.5,
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


def test_risk_adjustment():
    """Test that risk adjustment increases with stress."""
    
    arbitrator = ActionArbitrator()
    
    print("="*60)
    print("RISK ADJUSTMENT TEST")
    print("="*60)
    
    stress_levels = [
        ("NORMAL", 0.2),
        ("CONSERVATIVE", 0.45),
        ("DEFENSIVE", 0.7),
        ("SURVIVAL", 0.9)
    ]
    
    risk_levels = [
        ("LOW", RiskLevel.LOW, 1),
        ("MEDIUM", RiskLevel.MEDIUM, 2),
        ("HIGH", RiskLevel.HIGH, 3),
        ("CRITICAL", RiskLevel.CRITICAL, 4)
    ]
    
    print("\nRisk adjustments by stress level:")
    print("-"*60)
    print(f"{'Stress':<12} {'LOW':<10} {'MEDIUM':<10} {'HIGH':<10} {'CRITICAL':<10}")
    print("-"*60)
    
    results = {}
    
    for stress_name, stress_value in stress_levels:
        context = create_test_context(stress_value)
        adjustments = []
        
        for risk_name, risk_level, _ in risk_levels:
            adj = arbitrator._risk_adjustment(risk_level, context)
            adjustments.append(adj)
        
        results[stress_name] = adjustments
        print(f"{stress_name:<12} {adjustments[0]:<10.3f} {adjustments[1]:<10.3f} {adjustments[2]:<10.3f} {adjustments[3]:<10.3f}")
    
    print("-"*60)
    
    # Validation
    print("\n" + "="*60)
    print("VALIDATION:")
    print("="*60)
    
    # Check 1: Adjustment decreases with risk (higher risk = lower adjustment)
    # Or increases penalty depending on implementation
    normal_adj = results["NORMAL"]
    print(f"\n  NORMAL stress risk adjustments:")
    print(f"    LOW={normal_adj[0]:.3f}, MEDIUM={normal_adj[1]:.3f}, HIGH={normal_adj[2]:.3f}, CRITICAL={normal_adj[3]:.3f}")
    
    # Check 2: SURVIVAL stress affects CRITICAL differently
    survival_critical = results["SURVIVAL"][3]
    normal_critical = results["NORMAL"][3]
    stress_affects_risk = survival_critical != normal_critical
    print(f"\n  Stress affects CRITICAL risk adjustment: {stress_affects_risk}")
    print(f"    NORMAL={normal_critical:.3f} vs SURVIVAL={survival_critical:.3f}")
    
    # Check 3: Higher stress = more penalty (lower adjustment)
    critical_adj = [results[s][3] for s in ["NORMAL", "CONSERVATIVE", "DEFENSIVE", "SURVIVAL"]]
    stress_increases_penalty = critical_adj[3] < critical_adj[0]
    print(f"\n  Higher stress = more penalty on CRITICAL: {stress_increases_penalty}")
    print(f"    NORMAL={critical_adj[0]:.3f} → SURVIVAL={critical_adj[3]:.3f}")
    
    success = stress_affects_risk and stress_increases_penalty
    
    print("\n" + "="*60)
    if success:
        print("✓ PASS: Risk adjustment responds to stress")
    else:
        print("✗ FAIL: Risk adjustment not affected by stress")
    print("="*60)
    
    return success


if __name__ == "__main__":
    success = test_risk_adjustment()
    sys.exit(0 if success else 1)
