"""
Test #14: Trend-Based Q Update (Production-Level)
==================================================
Instead of decay/random - use explicit change detection

Key insight:
- Not "Q = value" but "Q responds to trend"
- If skill improves → give recovery credit
- If skill degrades → penalize immediately
- No random exploration needed when system is change-aware
"""

import random
import math
from collections import deque
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

LAMBDA = 0.4  # Base learning rate
TREND_ALPHA = 0.6  # Stronger trend response
C = 2.0  # More exploration
RECENT_WINDOW = 8

class SkillA:
    id = "fast_good"
    success_rate = 0.95
    
    @classmethod
    def execute(cls):
        if random.random() > cls.success_rate:
            return {"success": False, "latency": 0.02}
        return {"success": True, "latency": 0.02}

class SkillB:
    id = "slow_reliable"
    success_rate = 1.0
    
    @classmethod
    def execute(cls):
        if random.random() > cls.success_rate:
            return {"success": False, "latency": 0.5}
        return {"success": True, "latency": 0.5}

SKILLS = [SkillA, SkillB]

class Tracker:
    def __init__(self, skill):
        self.skill = skill
        self.n = 0
        self.q = 0.5
        self.baseline = 0.5
        self.recent_rewards = deque(maxlen=RECENT_WINDOW)
        self.last_trend = 0
    
    @property
    def recent_avg(self):
        return sum(self.recent_rewards) / len(self.recent_rewards) if self.recent_rewards else 0.5
    
    @property
    def trend(self):
        """Positive = improving, negative = degrading"""
        if len(self.recent_rewards) < 3:
            return 0
        return self.recent_avg - self.baseline
    
    def score(self, total_steps):
        if self.n == 0:
            return float('inf')
        
        # Modest UCB
        exploration = C * math.sqrt(math.log(total_steps + 1) / self.n)
        
        # Strong trend bonus/penalty
        trend_bonus = TREND_ALPHA * self.trend * 10  # Scale trend to be significant
        
        return self.q + exploration + trend_bonus
    
    def update(self, reward):
        self.n += 1
        self.recent_rewards.append(reward)
        
        # Trend-based update (key difference from EMA!)
        self.last_trend = self.trend
        
        if len(self.recent_rewards) >= 3:
            # Update baseline faster to track changes
            self.baseline = 0.85 * self.baseline + 0.15 * self.recent_avg
            
            # Q responds to TREND, not just absolute value
            trend = self.trend
            self.q = self.q + LAMBDA * (reward - self.q) + TREND_ALPHA * trend
        else:
            # Initial learning - standard EMA
            self.q = (1 - LAMBDA) * self.q + LAMBDA * reward

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.15, 0.25)

def test():
    print("=" * 60)
    print("TREND-BASED Q UPDATE TEST")
    print("=" * 60)
    print(f"Lambda={LAMBDA}, Trend_alpha={TREND_ALPHA}, C={C}")
    print("Key: Q responds to TREND, not absolute value")
    print("=" * 60)
    
    trackers = {s.id: Tracker(s) for s in SKILLS}
    total_steps = 0
    
    for t in range(1, 226):
        total_steps += 1
        
        if t <= 75:
            SkillA.success_rate = 0.95
            phase = "A good"
        elif t <= 150:
            SkillA.success_rate = 0.55
            phase = "A degraded"
        else:
            SkillA.success_rate = 0.95
            phase = "A recovered"
        
        # Small exploration floor to track all skills (not just one)
        if random.random() < 0.05 or total_steps < 20:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: trackers[s.id].score(total_steps))
        
        result = chosen.execute()
        r = base_reward(result)
        
        tr = trackers[chosen.id]
        tr.update(r)
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            print(f"t={t:3d} [{phase:12s}] | A_q={a.q:.2f}(t={a.trend:+.2f}) | B_q={b.q:.2f}(t={b.trend:+.2f})")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, Q={tr.q:.3f}, trend={tr.trend:+.3f}")
    
    a_q = trackers["fast_good"].q
    b_q = trackers["slow_reliable"].q
    
    print(f"\nFinal: A={a_q:.3f}, B={b_q:.3f}")
    
    print("\n" + "=" * 60)
    if a_q > b_q + 0.05:
        print("✅ ADAPTIVE: trend-based update works")
    elif b_q > a_q + 0.1:
        print("⚠️ CONSERVATIVE: still prefers stable")
    else:
        print("✅ BALANCED: competitive")
    print("=" * 60)

test()