#!/usr/bin/env python3
"""
Closed Loop Integration Test - Full adaptive cycle with Candidates → TS → Selection

Tests: Find → Probe → Exploit → Degrade → Unlock → Re-adapt

Key change: Graph now returns candidates, PlanMemory selects via TS
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.decomposition_graph import get_decomposition_graph
from semantic.plan_memory import get_plan_memory

ITERATIONS = 25
GOAL_TYPE = "data_fetch"

# Degradation simulation
def simulate_execution(strategy: str, iteration: int) -> dict:
    """Simulate strategy availability changes."""
    strategy_lower = str(strategy).lower()
    
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
    
    # database_fetch fails first 3 times (to force exploration)
    if "database_fetch" in strategy_lower:
        if iteration <= 3:
            return {"success": False, "error": "DB connection failed"}
        return {"success": True, "result": "from database"}
    
    # cached_data always works
    if "cached_data" in strategy_lower:
        return {"success": True, "result": "from cache"}
    
    return {"success": True, "result": "default"}

# Initialize
graph = get_decomposition_graph()
memory = get_plan_memory()

# Clear state - reset graph completely
import os
graph_path = "/app/decomposition_graph.json"
if os.path.exists(graph_path):
    os.remove(graph_path)
    
graph.nodes = {}
graph.roots = {}
graph._save()

# Reset memory
memory._strategy_scores = {}
memory._blacklist = {}
memory._failure_counts = {}
memory._mode = "explore"
memory._exploit_history = []
memory._locked_strategy = None
memory._probe_candidate = None
memory._probe_successes = 0
memory._probe_attempts = 0
memory._iteration_count = 0
memory._total_experience_cache = 0
memory._last_seen = {}

print("Memory reset complete")
print(f"Mode: {memory._mode}")

# Pre-populate graph with strategies as children
root = graph.get_or_create_root(GOAL_TYPE)
print(f"Root created: {root.node_id}")

for strategy in ["api_fetch", "web_scraping", "database_fetch", "cached_data"]:
    graph.add_node(strategy, "strategy", parent_id=root.node_id)
    print(f"Added strategy: {strategy}")

graph._save()

print("=" * 70)
print("🔥 CLOSED LOOP WITH CANDIDATES → TS → SELECTION")
print("=" * 70)
print(f"Goal Type: {GOAL_TYPE}")
print(f"Iterations: {ITERATIONS}")
print("\nPhase 1 (1-5):   Find working strategy")
print("Phase 2 (6-12):  web_scraping degrades")
print("Phase 3 (13+):   api_fetch recovers")
print("=" * 70)

RESULTS = []

for i in range(1, ITERATIONS + 1):
    phase = "FIND" if i < 6 else "DEGRADE" if i < 13 else "READAPT"
    
    print(f"\n{'='*60}")
    print(f"📌 ITERATION {i} [{phase}]")
    print(f"{'='*60}")
    
    # Get current mode
    mode = memory.get_mode()
    locked = memory.get_locked_strategy()
    print(f"Mode: {mode}, Locked: {locked}")
    
    # Step 1: Get candidates from graph
    candidates = graph.get_candidates(GOAL_TYPE, {})
    print(f"Candidates: {candidates}")
    
    # Step 2: Select using TS
    if candidates:
        selected = memory.select_strategy(candidates)
    else:
        selected = "default_strategy"
    
    print(f"Selected (TS): {selected}")
    
    # Step 3: Expand plan with selected
    plan, path_nodes = graph.expand_plan(GOAL_TYPE, {}, selected=selected)
    print(f"Plan: {plan}")
    
    # Step 4: Simulate execution
    result = simulate_execution(selected, i)
    success = result.get("success", False)
    print(f"Result: {result}")
    
    # Step 5: Learn - update memory
    if success:
        memory.record_strategy_success(selected)
    else:
        memory.record_strategy_failure(selected)
    
    memory._update_mode(selected, success)
    
    # Update graph with result
    if path_nodes:
        graph.update_path(path_nodes, success, {})
    
    RESULTS.append({
        "iteration": i,
        "phase": phase,
        "candidates": candidates,
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
strategies_used = [r["selected"] for r in RESULTS]
unique_strategies = set(strategies_used)
switched = len(unique_strategies) > 1

print(f"\n🔍 Key Observations:")
print(f"  Unique strategies used: {len(unique_strategies)}")
print(f"  Strategies: {unique_strategies}")

# Check if TS actually made different selections
early_strategies = set(r["selected"] for r in RESULTS[:5])
late_strategies = set(r["selected"] for r in RESULTS[12:])
changed = early_strategies != late_strategies and len(late_strategies) > 0

print(f"  Changed strategy from early to late: {changed}")

print("\n" + "=" * 70)
if switched:
    print("✅ CANDIDATE → TS → SELECTION WORKING!")
    print("   System is exploring and selecting among alternatives")
else:
    print("⚠️  System stuck on single strategy")
print("=" * 70)