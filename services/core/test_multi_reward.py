#!/usr/bin/env python3
"""Multi-metric reward test - TS should prefer better quality"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.decomposition_graph import get_decomposition_graph
from semantic.plan_memory import get_plan_memory

ITERATIONS = 40
GOAL_TYPE = "data_fetch"

# Simulate with multi-metric results
def simulate(strategy: str, iteration: int) -> dict:
    s = str(strategy).lower()
    is_online = iteration >= 15
    
    if "api_fetch" in s:
        if not is_online:
            return {"success": False, "error": "offline", "freshness": 1.0, "latency": 0.1, "cost": 0.3}
        # api_fetch: good freshness, higher cost
        return {"success": True, "result": "OK", "freshness": 1.0, "latency": 0.1, "cost": 0.3}
    
    if "cached_data" in s:
        # cached_data: low freshness, fast, cheap
        return {"success": True, "result": "cached", "freshness": 0.2, "latency": 0.01, "cost": 0.0}
    
    return {"success": True, "result": "OK", "freshness": 0.5, "latency": 0.2, "cost": 0.2}

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

root = graph.get_or_create_root(GOAL_TYPE)
for s in ["api_fetch", "cached_data"]:
    graph.add_node(s, "strategy", parent_id=root.node_id)
graph._save()

print("=" * 60)
print("MULTI-METRIC REWARD TEST")
print("cached_data: fast+cheap but stale (freshness=0.2)")
print("api_fetch:   fresh but slower+costly (freshness=1.0)")
print("=" * 60)

RESULTS = []

for i in range(1, ITERATIONS + 1):
    candidates = graph.get_candidates(GOAL_TYPE, {})
    context = {"network": "online" if i >= 15 else "offline"}
    
    # Selection
    if random.random() < 0.1:
        selected = random.choice(candidates)
    else:
        scores = {}
        for s in candidates:
            ts = memory._get_thompson_sample_for_context(s, context)
            scores[s] = ts
        selected = max(scores, key=scores.get)
    
    # Execution with multi-metric result
    result = simulate(selected, i)
    
    # Compute multi-metric reward
    reward = memory.compute_reward(result, context)
    
    # Record
    memory.record_strategy_reward(selected, reward, context)
    
    RESULTS.append({
        "iteration": i,
        "selected": selected,
        "context": context["network"],
        "reward": reward,
        "success": result.get("success", False),
        "freshness": result.get("freshness", 0)
    })
    
    if i % 10 == 0:
        print(f"\n--- Iteration {i} ({context['network']}) ---")
        print(f"Selected: {selected}, Reward: {reward:.2f}")
        print("Stats:")
        for ctx in ["offline", "online"]:
            for s in ["api_fetch", "cached_data"]:
                key = (s, ctx)
                if key in memory._strategy_scores:
                    st = memory._strategy_scores[key]
                    a = st.get("alpha", 1.0)
                    b = st.get("beta", 1.0)
                    avg = st.get("total_reward", 0) / max(1, st.get("reward_count", 1))
                    print(f"  ({s}, {ctx}): α={a:.1f}, β={b:.1f}, avg_r={avg:.2f}")

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)

from collections import Counter

online_results = [r for r in RESULTS if r["context"] == "online"]
print(f"\nONLINE (15-40): {len(online_results)} iterations")
dist = Counter(r["selected"] for r in online_results)
for s, c in sorted(dist.items(), key=lambda x: -x[1]):
    pct = c / len(online_results) * 100
    print(f"  {s}: {c} ({pct:.0f}%)")

avg_reward_api = sum(r["reward"] for r in online_results if r["selected"] == "api_fetch") / max(1, sum(1 for r in online_results if r["selected"] == "api_fetch"))
avg_reward_cache = sum(r["reward"] for r in online_results if r["selected"] == "cached_data") / max(1, sum(1 for r in online_results if r["selected"] == "cached_data"))

print(f"\nAvg reward in ONLINE:")
print(f"  api_fetch:   {avg_reward_api:.2f}")
print(f"  cached_data: {avg_reward_cache:.2f}")

print("\n" + "=" * 60)
print("FINAL STATE")
print("=" * 60)
for ctx in ["offline", "online"]:
    print(f"\n{ctx.upper()}:")
    for s in ["api_fetch", "cached_data"]:
        key = (s, ctx)
        if key in memory._strategy_scores:
            st = memory._strategy_scores[key]
            a = st.get("alpha", 1.0)
            b = st.get("beta", 1.0)
            tr = st.get("total_reward", 0)
            rc = st.get("reward_count", 0)
            avg = tr / rc if rc > 0 else 0
            print(f"  {s}: α={a:.1f}, β={b:.1f}, avg={avg:.2f}, n={rc}")

print("=" * 60)