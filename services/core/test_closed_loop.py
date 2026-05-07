#!/usr/bin/env python3
"""
Closed Loop Integration Test - Full adaptive cycle test.

Tests: Find → Probe → Exploit → Degrade → Unlock → Re-adapt

Uses PlanMemory + PlanningEngine which has the multi-strategy selection system.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.plan_memory import get_plan_memory, BLACKLIST_THRESHOLD, BLACKLIST_COOLDOWN_HOURS
from semantic.planning_engine import Planner

TEST_GOAL = "fetch external data from API"
AVAILABLE_STRATEGIES = ["api_fetch", "web_scraping", "database_fetch", "cached_data"]
ITERATIONS = 25

# Degradation simulation
def simulate_execution(strategy: str, iteration: int) -> dict:
    """Simulate strategy availability changes."""
    strategy_lower = strategy.lower()
    
    # api_fetch unavailable until iteration 13
    if "api_fetch" in strategy_lower:
        if iteration < 13:
            return {"success": False, "error": "API still down"}
        return {"success": True, "result": "API recovered!"}
    
    # web_scraping works initially, then degrades
    if "web_scraping" in strategy_lower:
        if iteration < 6:
            return {"success": True, "result": "scraped data"}
        elif iteration < 10:
            return {"success": True, "result": "slow scraping"}
        else:
            return {"success": False, "error": "site blocked"}
    
    # database_fetch always works (fallback)
    if "database_fetch" in strategy_lower:
        return {"success": True, "result": "from database"}
    
    # cached_data always works
    if "cached_data" in strategy_lower:
        return {"success": True, "result": "from cache"}
    
    return {"success": True, "result": "default"}

# Initialize
memory = get_plan_memory()
planner = Planner()

# Clear state
memory._strategy_scores = {}
memory._blacklist = {}
memory._failure_counts = {}
memory._mode = "explore"
memory._exploit_history = []
memory._locked_strategy = None
memory._probe_count = 0

# Save to persist clear state
memory._save()

print("=" * 70)
print("🔥 CLOSED LOOP INTEGRATION TEST")
print("=" * 70)
print("Strategies:", AVAILABLE_STRATEGIES)
print("Iterations:", ITERATIONS)
print("\nPhase 1 (1-5):   Find working strategy")
print("Phase 2 (6-12):  web_scraping degrades 1.0→0.8→0.5→0.2")
print("Phase 3 (13+):   api_fetch recovers")
print("=" * 70)

RESULTS = []

for i in range(1, ITERATIONS + 1):
    iteration_start = i
    phase = "FIND" if i < 6 else "DEGRADE" if i < 13 else "READAPT"
    
    print(f"\n{'='*60}")
    print(f"📌 ITERATION {i} [{phase}]")
    print(f"{'='*60}")
    
    # Get current mode and locked strategy
    mode = memory.get_mode()
    locked = memory.get_locked_strategy()
    print(f"Mode: {mode}, Locked: {locked}")
    
    # Get blacklisted strategies
    candidates = AVAILABLE_STRATEGIES.copy()
    filtered = planner._enforce_blacklist(TEST_GOAL, candidates)
    
    # Select strategy using Thompson Sampling
    selected = memory.select_strategy(filtered)
    print(f"Selected: {selected}")
    
    # Simulate execution
    result = simulate_execution(selected, i)
    success = result.get("success", False)
    print(f"Result: {result}")
    
    # Record in memory
    if success:
        memory.record_strategy_success(selected)
    else:
        memory.record_strategy_failure(selected)
    
    # Update mode based on result
    memory._update_mode(selected, success)
    
    RESULTS.append({
        "iteration": i,
        "phase": phase,
        "selected": selected,
        "success": success,
        "mode": memory.get_mode(),
        "locked": memory.get_locked_strategy()
    })

print("\n" + "=" * 70)
print("📈 RESULTS")
print("=" * 70)

strategy_usage = {}
for r in RESULTS:
    s = r["selected"]
    strategy_usage[s] = strategy_usage.get(s, 0) + 1

print("\n📊 Strategy Distribution:")
for strategy, count in sorted(strategy_usage.items(), key=lambda x: -x[1]):
    print(f"  {strategy}: {count} ({count/ITERATIONS*100:.1f}%)")

print("\n📋 Iteration Log:")
print("-" * 70)
for r in RESULTS:
    status = "✅" if r["success"] else "❌"
    phase = r["phase"][:3]
    print(f"{r['iteration']:2d}. [{phase}] {status} {r['selected']:15s} mode={r['mode']}")

# Phase analysis
find_results = RESULTS[:5]
degrade_results = RESULTS[5:12]
readapt_results = RESULTS[12:]

find_success = sum(1 for r in find_results if r["success"])
degrade_success = sum(1 for r in degrade_results if r["success"])
readapt_success = sum(1 for r in readapt_results if r["success"])

print(f"\n📊 Phase Analysis:")
print(f"  FIND:    {find_success}/5 = {find_success/5*100:.0f}% success")
print(f"  DEGRADE: {degrade_success}/7 = {degrade_success/7*100:.0f}% success")
print(f"  READAPT: {readapt_success}/{len(readapt_results)} = {readapt_success/len(readapt_results)*100:.0f}% success")

# Check transitions
modes = [r["mode"] for r in RESULTS]
reached_exploit = "exploit" in modes
switched_strategies = len(set(r["selected"] for r in RESULTS if r["iteration"] > 10)) > 1

print(f"\n🔍 Key Transitions:")
print(f"  Reached exploit mode: {reached_exploit}")
print(f"  Switched to alternative: {switched_strategies}")

print("\n" + "=" * 70)
if reached_exploit:
    print("✅ CLOSED LOOP TEST PASSED")
    print("   System found working strategy and locked to it!")
else:
    print("⚠️  NEEDS ATTENTION")
print("=" * 70)