#!/usr/bin/env python3
"""
Behavioral Adaptation Test - 20 iterations
Tests whether the system actually adapts: fails → blacklist → switches strategy

Run: python test_adaptation_loop.py
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.plan_memory import get_plan_memory, BLACKLIST_THRESHOLD
from semantic.planning_engine import Planner
from semantic.execution_policy import get_execution_policy_manager

memory = get_plan_memory()
planner = Planner()
policy_manager = get_execution_policy_manager()

TEST_GOAL = "fetch external data from API"

ITERATIONS = 20
RESULTS = []

AVAILABLE_STRATEGIES = ["api_fetch", "web_scraping", "database_fetch", "cached_data", "bulk_write"]

def simulate_execution(strategy: str, iteration: int) -> dict:
    """
    Simulate execution - first 2 iterations fail with rate_limit,
    then should succeed with fallback strategy.
    """
    if strategy == "api_fetch":
        if iteration <= 2:
            return {
                "success": False,
                "error": "rate_limit: 429 Too Many Requests",
                "category": "rate_limit"
            }
        else:
            return {"success": True, "result": "data from API"}
    elif strategy in ["cached_data", "database_fetch"]:
        return {"success": True, "result": f"data from {strategy}"}
    elif strategy == "web_scraping":
        return {"success": True, "result": "scraped data"}
    
    return {"success": True, "result": "default"}

print("=" * 80)
print("🔬 BEHAVIORAL ADAPTATION TEST")
print("=" * 80)
print(f"Goal: {TEST_GOAL}")
print(f"Iterations: {ITERATIONS}")
print(f"Blacklist threshold: {BLACKLIST_THRESHOLD} failures")
print(f"Available strategies: {AVAILABLE_STRATEGIES}")
print("=" * 80)

memory.plans = []
memory._save()

blacklist_path = memory._storage_path.replace(".json", "_blacklist.json")
try:
    os.remove(blacklist_path)
except:
    pass

for i in range(1, ITERATIONS + 1):
    iteration_start = time.time()
    
    print(f"\n{'='*60}")
    print(f"📌 ITERATION {i}")
    print(f"{'='*60}")
    
    blacklisted = memory.get_blacklisted_strategies(TEST_GOAL)
    print(f"🔍 Blacklisted strategies: {list(blacklisted.keys()) if blacklisted else 'none'}")
    
    candidates = AVAILABLE_STRATEGIES.copy()
    filtered = planner._enforce_blacklist(TEST_GOAL, candidates)
    
    print(f"📋 Strategy candidates: {candidates}")
    print(f"🔎 After blacklist filtering: {filtered}")
    
    if filtered:
        selected = filtered[0]
    else:
        selected = "cached_data"
    
    print(f"✅ Selected strategy: {selected}")
    
    result = simulate_execution(selected, i)
    
    print(f"📊 Execution result: {result}")
    
    iteration_result = {
        "iteration": i,
        "blacklisted": list(blacklisted.keys()),
        "candidates": candidates,
        "filtered": filtered,
        "selected": selected,
        "success": result.get("success", False),
        "error": result.get("error"),
        "category": result.get("category"),
        "duration_ms": int((time.time() - iteration_start) * 1000)
    }
    RESULTS.append(iteration_result)
    
    if not result.get("success"):
        category = result.get("category", "unknown")
        
        memory.store(
            goal=TEST_GOAL,
            tasks=[{"id": f"t{i}", "description": selected}],
            success=False,
            failed_task_ids=[f"t{i}"],
            failure_errors={f"t{i}": result.get("error", "unknown")}
        )
        
        was_blacklisted = memory.record_failure(TEST_GOAL, selected, category)
        
        policy_manager.record_failure(selected, category)
        
        print(f"⚠️ FAILURE recorded - category: {category}")
        
        if was_blacklisted:
            print(f"🚫 STRATEGY BLACKLISTED!")
        
        updated_blacklist = memory.get_blacklisted_strategies(TEST_GOAL)
        
        print(f"⚠️ FAILURE recorded - category: {category}")
        
        updated_blacklist = memory.get_blacklisted_strategies(TEST_GOAL)
        if updated_blacklist:
            print(f"🚫 BLACKLIST UPDATED: {list(updated_blacklist.keys())}")
    else:
        memory.store(
            goal=TEST_GOAL,
            tasks=[{"id": f"t{i}", "description": selected}],
            success=True
        )
        print(f"✅ SUCCESS")

print("\n" + "=" * 80)
print("📈 FINAL RESULTS")
print("=" * 80)

blacklist_final = memory.get_blacklisted_strategies(TEST_GOAL)
print(f"\nFinal blacklist: {list(blacklist_final.keys()) if blacklist_final else 'none'}")

success_count = sum(1 for r in RESULTS if r["success"])
fail_count = sum(1 for r in RESULTS if not r["success"])
print(f"\nTotal: {ITERATIONS} iterations")
print(f"  ✅ Success: {success_count}")
print(f"  ❌ Failed: {fail_count}")

print("\n📊 Strategy Distribution:")
strategy_usage = {}
for r in RESULTS:
    s = r["selected"]
    strategy_usage[s] = strategy_usage.get(s, 0) + 1

for strategy, count in sorted(strategy_usage.items(), key=lambda x: -x[1]):
    print(f"  {strategy}: {count} ({count/ITERATIONS*100:.1f}%)")

print("\n📋 Iteration Log:")
print("-" * 80)
for r in RESULTS:
    status = "✅" if r["success"] else "❌"
    blackmarked = f" [BLACKLIST: {r['blacklisted']}]" if r["blacklisted"] else ""
    print(f"{r['iteration']:2d}. {status} {r['selected']:20s} {blackmarked}")

print("\n" + "=" * 80)

if success_count > fail_count and blacklist_final:
    print("🎉 ADAPTATION DETECTED!")
    print("   System learned from failures and switched strategies.")
elif not blacklist_final:
    print("⚠️ NO ADAPTATION - No blacklist formed")
    print("   Failures were not recorded or threshold not reached.")
else:
    print("❌ ADAPTATION FAILED")
    print("   System failed to switch strategies after failures.")

print("=" * 80)

with open("adaptation_test_results.json", "w") as f:
    json.dump({
        "test_goal": TEST_GOAL,
        "iterations": ITERATIONS,
        "blacklist_threshold": BLACKLIST_THRESHOLD,
        "final_blacklist": list(blacklist_final.keys()) if blacklist_final else [],
        "success_count": success_count,
        "fail_count": fail_count,
        "strategy_distribution": strategy_usage,
        "iterations_log": RESULTS
    }, f, indent=2)

print(f"\n💾 Results saved to adaptation_test_results.json")
