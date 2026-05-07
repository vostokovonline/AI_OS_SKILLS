#!/usr/bin/env python3
"""Debug dump - check internal state after soft updates"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from semantic.plan_memory import get_plan_memory

memory = get_plan_memory()

print("=" * 60)
print("DEBUG DUMP - Internal State")
print("=" * 60)

# Print all strategy stats
print("\n📊 Strategy Stats (alpha, beta, total_reward, reward_count):")
for strategy, stats in memory._strategy_scores.items():
    alpha = stats.get("alpha", 1.0)
    beta = stats.get("beta", 1.0)
    total_reward = stats.get("total_reward", 0.0)
    reward_count = stats.get("reward_count", 0)
    avg = total_reward / reward_count if reward_count > 0 else 0.0
    
    print(f"  {strategy:20s}: alpha={alpha:.2f}, beta={beta:.2f}, "
          f"total={total_reward:.2f}, count={reward_count}, avg={avg:.2f}")

print(f"\n🔧 Mode: {memory._mode}")
print(f"🔒 Locked: {memory._locked_strategy}")
print(f"🔍 Probe candidate: {memory._probe_candidate}")
print(f"📈 Iteration: {memory._iteration_count}")

# Test TS sampling
print("\n🎲 Thompson Sampling samples (5 each):")
for strategy in ["api_fetch", "web_scraping", "database_fetch", "cached_data"]:
    samples = [memory._get_thompson_sample(strategy) for _ in range(5)]
    print(f"  {strategy:20s}: {samples}")

print("\n" + "=" * 60)