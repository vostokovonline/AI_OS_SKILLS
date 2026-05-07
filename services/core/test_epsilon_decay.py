#!/usr/bin/env python3
"""Extended test showing epsilon-greedy + decay in action"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.decomposition_graph import get_decomposition_graph
from semantic.plan_memory import get_plan_memory

ITERATIONS = 30
GOAL_TYPE = "data_fetch"

# Scenario: api_fetch recovers at iteration 15
def simulate_execution(strategy: str, iteration: int) -> dict:
    s = str(strategy).lower()
    
    if "api_fetch" in s:
        if iteration < 15:
            return {"success": False, "error": "API down"}
        return {"success": True, "result": "API recovered", "latency": 0.1}
    
    if "cached_data" in s:
        return {"success": True, "result": "cached", "latency": 0.01}
    
    return {"success": True, "result": "OK"}

# Setup
graph = get_decomposition_graph()
memory = get_plan_memory()

# Reset
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
memory._exploit_history = []

# Create strategies
root = graph.get_or_create_root(GOAL_TYPE)
for s in ["api_fetch", "cached_data"]:
    graph.add_node(s, "strategy", parent_id=root.node_id)
graph._save()

print("=" * 70)
print("ε-GREEDY + DECAY TEST (30 iterations)")
print("Phase 1 (1-14): api_fetch down")
print("Phase 2 (15+):  api_fetch recovers")
print("=" * 70)

for i in range(1, ITERATIONS + 1):
    candidates = graph.get_candidates(GOAL_TYPE, {})
    selected = memory.select_strategy(candidates)
    
    result = simulate_execution(selected, i)
    success = result.get("success", False)
    
    if success:
        memory.record_strategy_success(selected)
    else:
        memory.record_strategy_failure(selected)
    memory._update_mode(selected, success)
    
    # Show every 5 iterations
    if i % 5 == 0:
        print(f"\n--- Iteration {i} ---")
        print(f"Selected: {selected}, Mode: {memory._mode}")
        
        # Show alpha/beta for all strategies
        for s, st in memory._strategy_scores.items():
            a = st.get("alpha", 1.0)
            b = st.get("beta", 1.0)
            print(f"  {s}: α={a:.2f}, β={b:.2f}")

print("\n" + "=" * 70)
print("FINAL DEBUG DUMP")
print("=" * 70)

print("\n📊 Strategy Stats:")
for s, st in memory._strategy_scores.items():
    a = st.get("alpha", 1.0)
    b = st.get("beta", 1.0)
    tr = st.get("total_reward", 0.0)
    rc = st.get("reward_count", 0)
    avg = tr / rc if rc > 0 else 0
    print(f"  {s}: α={a:.2f}, β={b:.2f}, avg_reward={avg:.2f}, count={rc}")

print(f"\nMode: {memory._mode}, Locked: {memory._locked_strategy}")
print("=" * 70)