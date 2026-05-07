#!/usr/bin/env python3
"""Goal-aware reward test - verify different goals = different behaviors"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.decomposition_graph import get_decomposition_graph
from semantic.plan_memory import get_plan_memory

ITERATIONS = 20

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
memory._iteration_count = 0
memory._last_seen = {}

GOAL = "data_fetch"
root = graph.get_or_create_root(GOAL)
for s in ["api_fetch", "cached_data"]:
    graph.add_node(s, "strategy", parent_id=root.node_id)
graph._save()

# Simulate with different characteristics
def simulate(strategy: str) -> dict:
    s = str(strategy).lower()
    
    if "api_fetch" in s:
        # Fresh but expensive and slow
        return {"success": True, "result": "OK", "freshness": 1.0, "latency": 0.3, "cost": 0.8}
    
    if "cached_data" in s:
        # Fast and cheap but stale
        return {"success": True, "result": "cached", "freshness": 0.2, "latency": 0.01, "cost": 0.1}
    
    return {"success": True, "result": "OK"}

print("=" * 60)
print("GOAL-AWARE REWARD TEST")
print("api_fetch:  freshness=1.0, latency=0.3, cost=0.8")
print("cached_data: freshness=0.2, latency=0.01, cost=0.1")
print("=" * 60)

# Test each goal
for goal_name, _ in memory.GOAL_PROFILES.items():
    if goal_name == "default":
        continue
    
    # Reset for each goal
    memory._strategy_scores = {}
    memory._iteration_count = 0
    
    print(f"\n--- Goal: {goal_name} ---")
    
    # Get goal weights
    weights = memory.GOAL_PROFILES[goal_name]
    print(f"Weights: {weights}")
    
    # Run iterations
    for i in range(1, ITERATIONS + 1):
        candidates = ["api_fetch", "cached_data"]
        
        # Simple TS selection
        if random.random() < 0.1:
            selected = random.choice(candidates)
        else:
            scores = {}
            for s in candidates:
                ts = memory._get_thompson_sample_for_context(s, {})
                scores[s] = ts
            selected = max(scores, key=scores.get)
        
        # Simulate and compute goal-aware reward
        result = simulate(selected)
        reward_dict = memory.compute_reward(result, {}, goal_name)
        
        # Record
        memory.record_strategy_reward(selected, reward_dict["total"], {})
    
    # Show results
    print(f"Final stats after {ITERATIONS} iterations:")
    for s in ["api_fetch", "cached_data"]:
        key = (s, "default")
        if key in memory._strategy_scores:
            st = memory._strategy_scores[key]
            a = st.get("alpha", 1.0)
            b = st.get("beta", 1.0)
            avg = st.get("total_reward", 0) / max(1, st.get("reward_count", 1))
            print(f"  {s}: α={a:.1f}, β={b:.1f}, avg_reward={avg:.2f}")

print("\n" + "=" * 60)
print("REWARD COMPONENT BREAKDOWN BY GOAL")
print("=" * 60)

# Show what each goal emphasizes
for goal_name, weights in memory.GOAL_PROFILES.items():
    print(f"\n{goal_name}:")
    
    # Compute reward for each strategy with this goal
    for s in ["api_fetch", "cached_data"]:
        result = simulate(s)
        reward_dict = memory.compute_reward(result, {}, goal_name)
        
        comps = reward_dict["components"]
        print(f"  {s}: total={reward_dict['total']:.2f} "
              f"(success={comps['success']:.1f}, "
              f"freshness={comps['freshness']:.1f}, "
              f"latency={comps['latency']:.1f}, "
              f"cost={comps['cost']:.1f})")

print("\n" + "=" * 60)
print("EXPECTED BEHAVIOR:")
print("  realtime_data → prefers api_fetch (freshness matters)")
print("  cheap_batch   → prefers cached_data (cost matters)")
print("  fast_response→ prefers cached_data (latency matters)")
print("=" * 60)