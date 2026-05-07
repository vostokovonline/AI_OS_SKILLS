#!/usr/bin/env python3
"""Pure TS selection test - NO lock/mode logic"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.decomposition_graph import get_decomposition_graph
from semantic.plan_memory import get_plan_memory

ITERATIONS = 25
GOAL_TYPE = "data_fetch"

# Simulate: api_fetch works after iteration 15
def simulate(strategy: str, iteration: int) -> dict:
    s = str(strategy).lower()
    
    if "api_fetch" in s:
        if iteration < 15:
            return {"success": False, "error": "API down", "latency": 0.1}
        return {"success": True, "result": "OK", "latency": 0.1}
    
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

# Reset memory - clear ALL state
memory._strategy_scores = {}
memory._iteration_count = 0
memory._last_seen = {}

# Create strategies
root = graph.get_or_create_root(GOAL_TYPE)
for s in ["api_fetch", "cached_data"]:
    graph.add_node(s, "strategy", parent_id=root.node_id)
graph._save()

print("=" * 60)
print("PURE TS SELECTION (NO LOCK/MODE)")
print("Phase 1 (1-14): api_fetch down")
print("Phase 2 (15+):  api_fetch recovers")
print("=" * 60)

RESULTS = []

for i in range(1, ITERATIONS + 1):
    candidates = graph.get_candidates(GOAL_TYPE, {})
    
    # Pure TS selection with manual epsilon
    if random.random() < 0.25:
        selected = random.choice(candidates)
        print(f"[ε-GREEDY] Exploring: {selected}")
    else:
        # Manual TS scoring
        scores = {}
        for s in candidates:
            ts = memory._get_thompson_sample(s)
            scores[s] = ts
        selected = max(scores, key=scores.get)
    
    result = simulate(selected, i)
    success = result.get("success", False)
    
    # Update via soft reward
    reward = 1.0 if success else 0.0
    memory.record_strategy_reward(selected, reward)
    
    RESULTS.append({
        "iteration": i,
        "selected": selected,
        "success": success,
        "reward": reward
    })
    
    # Show every 5 iterations
    if i % 5 == 0:
        print(f"\n--- Iteration {i} ---")
        print(f"Selected: {selected}, Success: {success}")
        print("Alpha/Beta:")
        for s, st in memory._strategy_scores.items():
            a = st.get("alpha", 1.0)
            b = st.get("beta", 1.0)
            print(f"  {s}: α={a:.2f}, β={b:.2f}")

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

# Distribution
from collections import Counter
dist = Counter(r["selected"] for r in RESULTS)
print("\nStrategy distribution:")
for s, c in sorted(dist.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c} ({c/ITERATIONS*100:.0f}%)")

# Early vs Late
early = [r for r in RESULTS[:12]]
late = [r for r in RESULTS[12:]]

early_dist = Counter(r["selected"] for r in early)
late_dist = Counter(r["selected"] for r in late)

print(f"\nEarly (1-12): {dict(early_dist)}")
print(f"Late (13-25): {dict(late_dist)}")

print("\n" + "=" * 60)
print("FINAL STATE")
print("=" * 60)
for s, st in memory._strategy_scores.items():
    a = st.get("alpha", 1.0)
    b = st.get("beta", 1.0)
    tr = st.get("total_reward", 0.0)
    rc = st.get("reward_count", 0)
    avg = tr / rc if rc > 0 else 0
    print(f"  {s}: α={a:.2f}, β={b:.2f}, avg={avg:.2f}, count={rc}")
print("=" * 60)