"""
Test #12b: Drift-Aware - Balanced Scenario
============================================
Scenario where both skills are genuinely competitive:
- A: 95% / fast = expected 0.9+
- B: 100% / slow = expected 0.8

This is a more realistic production scenario.
Drift detection should help A recover when it degrades.
"""

import random
import math
from collections import deque
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

LAMBDA = 0.6  # Very fast adaptation
C = 1.5
DRIFT_THRESHOLD = 0.25
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
        self.recent_rewards = deque(maxlen=RECENT_WINDOW)
        self.baseline = 0.5
        self.total_reward = 0
    
    @property
    def recent_avg(self):
        return sum(self.recent_rewards) / len(self.recent_rewards) if self.recent_rewards else 0.5
    
    @property
    def avg_reward(self):
        return self.total_reward / self.n if self.n > 0 else 0.5
    
    def detect_drift(self):
        if len(self.recent_rewards) < 5:
            return False
        return (self.baseline - self.recent_avg) > DRIFT_THRESHOLD
    
    def score(self, total_steps):
        if self.n == 0:
            return float('inf')
        
        # If drifted, penalize (don't explore - it's bad!)
        if self.detect_drift():
            return self.q - 2.0  # Heavy penalty for degraded skill
        
        exploration = C * math.sqrt(math.log(total_steps + 1) / self.n)
        return self.q + exploration
    
    def update(self, reward):
        self.n += 1
        self.total_reward += reward
        self.recent_rewards.append(reward)
        self.q = (1 - LAMBDA) * self.q + LAMBDA * reward
        
        if self.n % 15 == 0:
            self.baseline = 0.85 * self.baseline + 0.15 * self.recent_avg

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.15, 0.25)

def test():
    print("=" * 60)
    print("DRIFT-AWARE: BALANCED SCENARIO")
    print("=" * 60)
    print(f"A: 95%/fast (expected ~0.9), B: 100%/slow (expected ~0.8)")
    print(f"More realistic - neither is clearly better")
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
        
        chosen = max(SKILLS, key=lambda s: trackers[s.id].score(total_steps))
        
        result = chosen.execute()
        r = base_reward(result)
        
        tr = trackers[chosen.id]
        tr.update(r)
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            a_d = " DRIFT!" if a.detect_drift() else ""
            print(f"t={t:3d} [{phase:12s}] | A_Q={a.q:.2f}{a_d} | B_Q={b.q:.2f} | chosen={chosen.id}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, avg_r={tr.avg_reward:.3f}, recent={tr.recent_avg:.3f}, drift={tr.detect_drift()}")
    
    a_q = trackers["fast_good"].q
    b_q = trackers["slow_reliable"].q
    
    print(f"\nFinal Q: A={a_q:.3f}, B={b_q:.3f}")
    
    print("\n" + "=" * 60)
    if a_q > b_q + 0.05:
        print("✅ ADAPTIVE: prefers fast_good (recovered)")
    elif b_q > a_q + 0.1:
        print("⚠️ CONSERVATIVE: prefers slow_reliable")
    else:
        print("✅ BALANCED: competitive")
    print("=" * 60)

test()