"""
Stress Permanence Test - Anti-Stuck Validation

Critical test: Does the system recover from chronic stress?

Scenario:
1. 200 ticks of moderate load (stress builds up)
2. 200 ticks of calm (stress should recover)

Expected: Stress MUST return to NORMAL mode.

If it doesn't → chronic stress loop → production failure.
"""
import sys
sys.path.insert(0, '/app')

from autonomy.emotional_adapter import StressState, StressMode

def test_chronic_stress_recovery():
    """System must recover from prolonged moderate stress."""
    
    state = StressState(inertia_alpha=0.85)
    
    # Phase 1: 200 ticks of moderate load
    print("Phase 1: 200 ticks of MODERATE load")
    moderate_signals = {
        "active_goals": 60,
        "max_goals": 100,
        "deadline_hours": 8.0,
        "recent_failures": 3,
        "recent_total": 10
    }
    
    for i in range(200):
        state.update(moderate_signals)
        if i % 50 == 0:
            print(f"  Tick {i}: stress={state.value:.3f}, mode={state.mode.value}")
    
    peak_stress = state.value
    peak_mode = state.mode
    print(f"\nPeak stress: {peak_stress:.3f}, mode: {peak_mode.value}")
    
    # Phase 2: 200 ticks of calm
    print("\nPhase 2: 200 ticks of CALM")
    calm_signals = {
        "active_goals": 10,
        "max_goals": 100,
        "recent_failures": 0,
        "recent_total": 10,
        "budget_remaining": 90,
        "budget_limit": 100
    }
    
    for i in range(200):
        state.update(calm_signals)
        if i % 50 == 0:
            print(f"  Tick {i}: stress={state.value:.3f}, mode={state.mode.value}")
    
    final_stress = state.value
    final_mode = state.mode
    print(f"\nFinal stress: {final_stress:.3f}, mode: {final_mode.value}")
    
    # VALIDATION
    print("\n" + "="*50)
    print("VALIDATION:")
    
    # Check 1: Stress decreased
    stress_decreased = final_stress < peak_stress
    print(f"  Stress decreased: {stress_decreased} ({peak_stress:.3f} → {final_stress:.3f})")
    
    # Check 2: Returned to NORMAL mode
    returned_to_normal = final_mode == StressMode.NORMAL
    print(f"  Returned to NORMAL: {returned_to_normal} (mode={final_mode.value})")
    
    # Check 3: Final stress is reasonably low
    stress_low = final_stress < 0.35
    print(f"  Final stress low (< 0.35): {stress_low} (stress={final_stress:.3f})")
    
    # Overall
    success = stress_decreased and returned_to_normal and stress_low
    
    print("\n" + "="*50)
    if success:
        print("✓ PASS: System recovers from chronic stress")
    else:
        print("✗ FAIL: System stuck in chronic stress")
        print("  → Recovery too slow or α too high")
    print("="*50)
    
    return success

if __name__ == "__main__":
    success = test_chronic_stress_recovery()
    sys.exit(0 if success else 1)
