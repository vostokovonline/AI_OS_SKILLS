#!/usr/bin/env python3
"""
DEGRADATION TEST - Full adaptive cycle
Tests: find → lock → degrade → unlock → re-adapt
"""
import sys
import os
import json
import time
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.plan_memory import get_plan_memory, BLACKLIST_THRESHOLD, BLACKLIST_COOLDOWN_HOURS
from semantic.planning_engine import Planner
from semantic.execution_policy import get_execution_policy_manager

memory = get_plan_memory()
planner = Planner()
policy_manager = get_execution_policy_manager()

TEST_GOAL = "fetch external data from API"
ITERATIONS = 30

RESULTS = []
AVAILABLE_STRATEGIES = ["api_fetch", "web_scraping", "database_fetch", "cached_data", "bulk_write"]

def simulate_execution(strategy: str, iteration: int) -> dict:
    """
    Degradation scenario:
    - Phase 1 (1-5): find working strategy
    - Phase 2 (6-12): web_scraping degrades
    - Phase 3 (13+): api_fetch becomes available
    """
    if strategy == "api_fetch":
        if iteration < 13:
            return {"success": False, "error": "still down", "category": "rate_limit"}
        else:
            return {"success": True, "result": "api recovered!"}
    
    elif strategy == "web_scraping":
        if iteration < 6:
            return {"success": True, "result": "scraped data"}
        elif iteration < 10:
            return {"success": random.random() < 0.8, "result": "scraped data", "error": "slow", "category": "timeout"}
        elif iteration < 14:
            return {"success": random.random() < 0.5, "result": "scraped data", "error": "failing", "category": "timeout"}
        else:
            return {"success": random.random() < 0.2, "result": "scraped data", "error": "broken", "category": "fatal"}
    
    return {"success": True, "result": "default"}

print("=" * 80)
print("🔥 DEGRADATION TEST - Full Adaptive Cycle")
print("=" * 80)
print(f"Iterations: {ITERATIONS}")
print("Phase 1 (1-5):   Find working strategy")
print("Phase 2 (6-12):  web_scraping degrades 1.0 → 0.8 → 0.5 → 0.2")
print("Phase 3 (13+):   api_fetch recovers")
print("=" * 80)

memory.plans = []
memory._save()

blacklist_path = memory._storage_path.replace(".json", "_blacklist.json")
try:
    os.remove(blacklist_path)
except:
    pass

memory._blacklist = {}
memory._failure_counts = {}
memory._mode = "explore"
memory._exploit_history = []

for i in range(1, ITERATIONS + 1):
    iteration_start = time.time()
    
    phase = "FIND" if i < 6 else "DEGRADE" if i < 13 else "READAPT"
    
    print(f"\n{'='*60}")
    print(f"📌 ITERATION {i} [{phase}]")
    print(f"{'='*60}")
    
    mode = memory.get_mode()
    locked = memory.get_locked_strategy()
    print(f"Mode: {mode}, Locked: {locked}")
    
    candidates = AVAILABLE_STRATEGIES.copy()
    filtered = planner._enforce_blacklist(TEST_GOAL, candidates)
    
    selected = memory.select_strategy(filtered)
    print(f"Selected: {selected}")
    
    result = simulate_execution(selected, i)
    print(f"Result: {result}")
    
    memory.record_strategy_success(selected) if result.get("success") else memory.record_strategy_failure(selected)
    memory._update_mode(selected, result.get("success", False))
    
    RESULTS.append({
        "iteration": i,
        "phase": phase,
        "selected": selected,
        "success": result.get("success", False),
        "mode": memory.get_mode(),
        "locked": memory.get_locked_strategy()
    })

print("\n" + "=" * 80)
print("📈 DEGRADATION TEST RESULTS")
print("=" * 80)

strategy_usage = {}
for r in RESULTS:
    s = r["selected"]
    strategy_usage[s] = strategy_usage.get(s, 0) + 1

print("\n📊 Strategy Distribution:")
for strategy, count in sorted(strategy_usage.items(), key=lambda x: -x[1]):
    print(f"  {strategy}: {count} ({count/ITERATIONS*100:.1f}%)")

print("\n📋 Iteration Log:")
print("-" * 80)
for r in RESULTS:
    status = "✅" if r["success"] else "❌"
    phase = r["phase"][:3]
    print(f"{r['iteration']:2d}. [{phase}] {status} {r['selected']:15s} mode={r['mode']}")

print("\n📊 Phase Analysis:")
phase_stats = {}
for r in RESULTS:
    p = r["phase"]
    if p not in phase_stats:
        phase_stats[p] = {"total": 0, "success": 0}
    phase_stats[p]["total"] += 1
    if r["success"]:
        phase_stats[p]["success"] += 1

for phase in ["FIND", "DEGRADE", "READAPT"]:
    if phase in phase_stats:
        s = phase_stats[phase]
        rate = s["success"] / s["total"] * 100 if s["total"] > 0 else 0
        print(f"  {phase}: {s['success']}/{s['total']} = {rate:.0f}% success")

print("\n" + "=" * 80)
find_locked = any(r["mode"] == "exploit" and r["iteration"] <= 5 for r in RESULTS)
degrade_unlocked = any(r["phase"] == "DEGRADE" and r["mode"] == "explore" for r in RESULTS)
readapt_new = any(r["phase"] == "READAPT" and r["selected"] == "api_fetch" for r in RESULTS)

print("✅ FIND PHASE:", "Locked to web_scraping" if find_locked else "NOT LOCKED")
print("✅ DEGRADE PHASE:", "Returned to explore" if degrade_unlocked else "STUCK IN EXPLOIT")
print("✅ READAPT PHASE:", "Found api_fetch" if readapt_new else "DID NOT RE-ADAPT")
print("=" * 80)

with open("degradation_test_results.json", "w") as f:
    json.dump({
        "iterations": RESULTS,
        "phase_stats": phase_stats,
        "strategy_distribution": strategy_usage,
        "find_locked": find_locked,
        "degrade_unlocked": degrade_unlocked,
        "readapt_new": readapt_new
    }, f, indent=2)

print(f"\n💾 Results saved to degradation_test_results.json")
