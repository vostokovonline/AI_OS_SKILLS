#!/usr/bin/env python3
"""
DRIFT TEST - Does the system recover from permanent blacklist?
Tests whether the system can re-discover a strategy after it starts working again.
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
    Drift scenario:
    - iterations 1-2: api_fetch fails (rate_limit)
    - iterations 3-10: api_fetch still fails (continues to fail)
    - iterations 11+: api_fetch STARTS WORKING (world changed!)
    """
    if strategy == "api_fetch":
        if iteration <= 10:
            return {
                "success": False,
                "error": "rate_limit: 429 Too Many Requests",
                "category": "rate_limit"
            }
        else:
            return {"success": True, "result": "API recovered - working again!"}
    elif strategy in ["cached_data", "database_fetch"]:
        return {"success": True, "result": f"data from {strategy}"}
    elif strategy == "web_scraping":
        return {"success": True, "result": "scraped data"}
    
    return {"success": True, "result": "default"}

print("=" * 80)
print("🔥 DRIFT TEST - Recovery from Permanent Blacklist")
print("=" * 80)
print(f"Goal: {TEST_GOAL}")
print(f"Iterations: {ITERATIONS}")
print(f"Blacklist cooldown: {BLACKLIST_COOLDOWN_HOURS}h")
print(f"Scenario: api_fail until iter 10, then recovers at iter 11+")
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

for i in range(1, ITERATIONS + 1):
    iteration_start = time.time()
    
    print(f"\n{'='*60}")
    print(f"📌 ITERATION {i}")
    print(f"{'='*60}")
    
    blacklisted = memory.get_blacklisted_strategies(TEST_GOAL)
    
    blacklist_status = {}
    for key, ts in blacklisted.items():
        if ":" in key:
            strategy = key.split(":", 1)[1]
            remaining = max(0, ts - time.time())
            blacklist_status[strategy] = f"{remaining/3600:.1f}h remaining"
        else:
            blacklist_status[key] = "unknown"
    
    print(f"🔍 Blacklist status: {blacklist_status if blacklist_status else 'none'}")
    
    candidates = AVAILABLE_STRATEGIES.copy()
    filtered = planner._enforce_blacklist(TEST_GOAL, candidates)
    
    print(f"📋 Candidates: {candidates}")
    print(f"🔎 Filtered: {filtered}")
    
    if filtered:
        selected = filtered[0]
    else:
        selected = "cached_data"
    
    print(f"✅ Selected: {selected}")
    
    result = simulate_execution(selected, i)
    print(f"📊 Result: {result}")
    
    stats = memory.get_strategy_stats(selected)
    score = memory.get_strategy_score(selected)
    print(f"📈 Strategy stats: {stats}, score: {score:.3f}")
    
    iteration_result = {
        "iteration": i,
        "selected": selected,
        "success": result.get("success", False),
        "blacklist_status": blacklist_status,
        "strategy_score": score,
        "strategy_stats": stats.copy(),
        "was_filtered": selected not in candidates,
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
        
        memory.record_strategy_failure(selected)
        memory._update_mode(selected, False)
        
        was_blacklisted = memory.record_failure(TEST_GOAL, selected, category)
        
        if was_blacklisted:
            print(f"🚫 STRATEGY BLACKLISTED!")
    else:
        memory.store(
            goal=TEST_GOAL,
            tasks=[{"id": f"t{i}", "description": selected}],
            success=True
        )
        
        memory.record_strategy_success(selected)
        memory._update_mode(selected, True)
        
        new_score = memory.get_strategy_score(selected)
        print(f"✅ SUCCESS - score updated: {score:.3f} → {new_score:.3f}")
        
        key = f"{TEST_GOAL}:{selected}"
        if key in memory._blacklist:
            del memory._blacklist[key]
            if key in memory._failure_counts:
                del memory._failure_counts[key]
            print(f"🟢 REMOVED FROM BLACKLIST: {selected}")

print("\n" + "=" * 80)
print("📈 DRIFT TEST RESULTS")
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

api_recovery_iteration = None
first_api_after_blacklist = None

for r in RESULTS:
    status = "✅" if r["success"] else "❌"
    bl = r.get("blacklist_status", {})
    bl_str = f" [BL: {bl}]" if bl else ""
    
    print(f"{r['iteration']:2d}. {status} {r['selected']:20s} {bl_str}")
    
    if r['iteration'] >= 11 and r['selected'] == 'api_fetch':
        if first_api_after_blacklist is None:
            first_api_after_blacklist = r['iteration']

print("\n" + "=" * 80)

if first_api_after_blacklist:
    print(f"🎉 RECOVERY DETECTED!")
    print(f"   System returned to api_fetch at iteration {first_api_after_blacklist}")
    print(f"   Latency: {first_api_after_blacklist - 10} iterations after recovery")
else:
    print(f"❌ PERMANENT FORGETTING!")
    print(f"   System NEVER returned to api_fetch after it started working")
    print(f"   This is the bug we need to fix with TTL + exploration")

print("=" * 80)

with open("drift_test_results.json", "w") as f:
    json.dump({
        "test_goal": TEST_GOAL,
        "iterations": ITERATIONS,
        "scenario": "api_fail_until_10_then_recover",
        "strategy_distribution": strategy_usage,
        "first_api_after_blacklist": first_api_after_blacklist,
        "iterations_log": RESULTS
    }, f, indent=2)

print(f"\n💾 Results saved to drift_test_results.json")
