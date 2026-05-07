#!/usr/bin/env python3
"""
Test the full ExecutionOrchestrator closed loop.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.execution_orchestrator import get_orchestrator

# Simple mock executor
def mock_executor(step: str, context: dict) -> dict:
    """Mock executor that simulates execution."""
    # Simple success for testing
    return {"success": True, "step": step}

# Get orchestrator
orchestrator = get_orchestrator(executor=mock_executor)

print("=" * 60)
print("🧪 ORCHESTRATOR TEST")
print("=" * 60)

# Test 1: Basic run
print("\n📌 Test 1: Basic goal execution")
result = orchestrator.run_goal(
    goal="fetch data from API",
    context={"goal_type": "data_fetch"}
)

print(f"Success: {result.success}")
print(f"Plan before: {result.plan_before_adaptation}")
print(f"Plan after: {result.plan_after_adaptation}")
print(f"Chosen path: {result.chosen_path}")
print(f"TS scores: {result.ts_scores}")
print(f"Adaptation applied: {result.adaptation_applied}")

# Test 2: Run multiple iterations
print("\n📌 Test 2: Multiple iterations")
for i in range(5):
    r = orchestrator.run_goal(
        goal=f"fetch data iteration {i}",
        context={"goal_type": "data_fetch", "iteration": i}
    )
    print(f"  Iteration {i+1}: success={r.success}, path={r.chosen_path[:2] if r.chosen_path else 'none'}")

# Test 3: Check telemetry
print("\n📌 Test 3: Telemetry")
telemetry = orchestrator.get_telemetry()
print(f"Events captured: {len(telemetry)}")
for t in telemetry[:3]:
    print(f"  - {t['phase']}: {list(t['details'].keys())}")

# Export telemetry
orchestrator.export_telemetry_json("/tmp/orchestrator_test.json")
print("\n📁 Telemetry exported to /tmp/orchestrator_test.json")

print("\n" + "=" * 60)
print("✅ ORCHESTRATOR TEST COMPLETE")
print("=" * 60)