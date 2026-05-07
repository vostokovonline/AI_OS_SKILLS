#!/usr/bin/env python3
"""Context-aware TS test - different stats for different contexts"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.decomposition_graph import get_decomposition_graph
from semantic.plan_memory import get_plan_memory

ITERATIONS = 30
GOAL_TYPE = "data_fetch"

# Context changes at iteration 15
def simulate(strategy: str, iteration: int) -> dict:
    s = str(strategy).lower()
    
    # Context: offline (1-14), online (15+)
    is_online = iteration >= 15
    
    if "api_fetch" in s:
        if not is_online:
            return {"success": False, "error": "offline", "latency": 0.1}
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
print("CONTEXT-AWARE TS SELECTION")
print("Phase 1 (1-14): offline - api_fetch fails")
print("Phase 2 (15+):  online  - api_fetch works")
print("=" * 60)

RESULTS = []

for i in range(1, ITERATIONS + 1):
    candidates = graph.get_candidates(GOAL_TYPE, {})
    
    # Context: offline until 14, online from 15
    context = {"network": "online" if i >= 15 else "offline"}
    
    # Manual TS with context
    if random.random() < 0.15:
        selected = random.choice(candidates)
        print(f"[ε-GREEDY] {selected}")
    else:
        scores = {}
        for s in candidates:
            ts = memory._get_thompson_sample_for_context(s, context)
            scores[s] = ts
        selected = max(scores, key=scores.get)
    
    result = simulate(selected, i)
    success = result.get("success", False)
    
    # Update with context
    reward = 1.0 if success else 0.0
    memory.record_strategy_reward(selected, reward, context)
    
    RESULTS.append({
        "iteration": i,
        "selected": selected,
        "success": success,
        "context": context["network"]
    })
    
    if i % 5 == 0:
        print(f"\n--- Iteration {i} ({context['network']}) ---")
        print(f"Selected: {selected}, Success: {success}")
        print("Stats by context:")
        for ctx in ["offline", "online"]:
            for s in ["api_fetch", "cached_data"]:
                key = (s, ctx)
                if key in memory._strategy_scores:
                    st = memory._strategy_scores[key]
                    a = st.get("alpha", 1.0)
                    b = st.get("beta", 1.0)
                    print(f"  ({s}, {ctx}): α={a:.2f}, β={b:.2f}")

print("\n" + "=" * 60)
print("RESULTS BY CONTEXT")
print("=" * 60)

from collections import Counter

offline_results = [r for r in RESULTS if r["context"] == "offline"]
online_results = [r for r in RESULTS if r["context"] == "online"]

print(f"\nOFFLINE (1-14):")
off_dist = Counter(r["selected"] for r in offline_results)
for s, c in sorted(off_dist.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c} ({c/len(offline_results)*100:.0f}%)")

print(f"\nONLINE (15-30):")
on_dist = Counter(r["selected"] for r in online_results)
for s, c in sorted(on_dist.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c} ({c/len(online_results)*100:.0f}%)")

print("\n" + "=" * 60)
print("FINAL STATS BY CONTEXT")
print("=" * 60)

for ctx in ["offline", "online"]:
    print(f"\n{ctx.upper()}:")
    for s in ["api_fetch", "cached_data"]:
        key = (s, ctx)
        if key in memory._strategy_scores:
            st = memory._strategy_scores[key]
            a = st.get("alpha", 1.0)
            b = st.get("beta", 1.0)
            tr = st.get("total_reward", 0.0)
            rc = st.get("reward_count", 0)
            avg = tr / rc if rc > 0 else 0
            print(f"  {s}: α={a:.2f}, β={b:.2f}, avg={avg:.2f}, count={rc}")
        else:
            print(f"  {s}: no data")

print("=" * 60)