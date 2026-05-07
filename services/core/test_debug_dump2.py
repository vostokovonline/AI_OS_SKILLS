#!/usr/bin/env python3
"""Debug dump - check internal state during test"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.decomposition_graph import get_decomposition_graph
from semantic.plan_memory import get_plan_memory
import random

random.seed(42)

ITERATIONS = 15
GOAL_TYPE = "data_fetch"

# Simple simulation
def simulate_execution(strategy: str, iteration: int) -> dict:
    if "api_fetch" in strategy:
        if iteration < 10:
            return {"success": False, "error": "API down"}
        return {"success": True, "result": "API recovered"}
    if "cached_data" in strategy:
        return {"success": True, "result": "from cache"}
    return {"success": True, "result": "OK"}

# Initialize
graph = get_decomposition_graph()
memory = get_plan_memory()

# Clear state
graph_path = "/app/decomposition_graph.json"
if os.path.exists(graph_path):
    os.remove(graph_path)
graph.nodes = {}
graph.roots = {}
graph._save()

memory._strategy_scores = {}
memory._mode = "explore"
memory._locked_strategy = None
memory._probe_candidate = None
memory._iteration_count = 0

# Create strategies
root = graph.get_or_create_root(GOAL_TYPE)
for s in ["api_fetch", "cached_data"]:
    graph.add_node(s, "strategy", parent_id=root.node_id)
graph._save()

print("=" * 60)
print("RUNNING 15 ITERATIONS WITH DEBUG DUMP")
print("=" * 60)

for i in range(1, ITERATIONS + 1):
    print(f"\n--- ITERATION {i} ---")
    
    candidates = graph.get_candidates(GOAL_TYPE, {})
    selected = memory.select_strategy(candidates)
    
    result = simulate_execution(selected, i)
    success = result.get("success", False)
    
    print(f"Selected: {selected}, Success: {success}")
    
    if success:
        memory.record_strategy_success(selected)
    else:
        memory.record_strategy_failure(selected)
    
    memory._update_mode(selected, success)
    
    # Debug every 5 iterations
    if i % 5 == 0:
        print(f"\n📊 After iteration {i}:")
        for s, st in memory._strategy_scores.items():
            a = st.get("alpha", 1.0)
            b = st.get("beta", 1.0)
            tr = st.get("total_reward", 0.0)
            rc = st.get("reward_count", 0)
            avg = tr / rc if rc > 0 else 0
            print(f"  {s}: alpha={a:.2f}, beta={b:.2f}, avg={avg:.2f}")
        print(f"Mode: {memory._mode}, Locked: {memory._locked_strategy}")

print("\n" + "=" * 60)
print("FINAL STATE")
print("=" * 60)
print(f"\n📊 Final Strategy Stats:")
for s, st in memory._strategy_scores.items():
    a = st.get("alpha", 1.0)
    b = st.get("beta", 1.0)
    tr = st.get("total_reward", 0.0)
    rc = st.get("reward_count", 0)
    avg = tr / rc if rc > 0 else 0
    print(f"  {s}: alpha={a:.2f}, beta={b:.2f}, total_reward={tr:.2f}, count={rc}, avg={avg:.2f}")

print(f"\n🎲 Final TS samples (10 each):")
for s in ["api_fetch", "cached_data"]:
    samples = [memory._get_thompson_sample(s) for _ in range(10)]
    print(f"  {s}: {samples}")

print(f"\nMode: {memory._mode}, Locked: {memory._locked_strategy}")
print("=" * 60)