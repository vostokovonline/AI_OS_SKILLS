"""
FINAL CLEAN: Windowed Gaussian TS (Production-Core)
====================================================
No shrinkage. No bonus. No audit. Pure principled approach.

Key fixes:
- Sample directly from N(mean, std) - no sqrt(n) shrinkage
- Window limits history, std stays alive for exploration
"""

import random
import math
from collections import deque
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

WINDOW_SIZE = 50  # Model parameter - environment timescale

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

class WindowedGaussian:
    def __init__(self, skill):
        self.skill = skill
        self.history = deque(maxlen=WINDOW_SIZE)
    
    @property
    def n(self):
        return len(self.history)
    
    @property
    def mean(self):
        if self.n == 0:
            return 0.5
        return sum(self.history) / self.n
    
    @property
    def variance(self):
        if self.n < 2:
            return 1.0
        m = self.mean
        return sum((x - m) ** 2 for x in self.history) / self.n
    
    @property
    def std(self):
        # Key: don't shrink std by sqrt(n) - exploration stays alive
        return max(math.sqrt(self.variance), 0.1)
    
    def sample(self):
        """Thompson Sampling: direct sample, no shrinkage"""
        if self.n == 0:
            return random.gauss(0.5, 1.0)
        return random.gauss(self.mean, self.std)
    
    def update(self, reward):
        self.history.append(reward)

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.3, 0.3)

def test():
    print("=" * 60)
    print("CLEAN GAUSSIAN TS (No shrinkage)")
    print("=" * 60)
    print(f"Window: {WINDOW_SIZE}, Sample ~ N(mean, std)")
    print("=" * 60)
    
    trackers = {s.id: WindowedGaussian(s) for s in SKILLS}
    
    for t in range(1, 226):
        if t <= 75:
            SkillA.success_rate = 0.95
            phase = "A good"
        elif t <= 150:
            SkillA.success_rate = 0.55
            phase = "A degraded"
        else:
            SkillA.success_rate = 0.95
            phase = "A recovered"
        
        # Pure Thompson Sampling
        chosen = max(SKILLS, key=lambda s: trackers[s.id].sample())
        
        result = chosen.execute()
        r = base_reward(result)
        
        trackers[chosen.id].update(r)
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            print(f"t={t:3d} [{phase:12s}] | A={a.mean:.2f}(s={a.std:.2f}) | B={b.mean:.2f}(s={b.std:.2f})")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, mean={tr.mean:.3f}, std={tr.std:.3f}")
    
    # Compare
    a_samples = [trackers["fast_good"].sample() for _ in range(100)]
    b_samples = [trackers["slow_reliable"].sample() for _ in range(100)]
    a_avg = sum(a_samples) / len(a_samples)
    b_avg = sum(b_samples) / len(b_samples)
    
    print(f"\nSample avg: A={a_avg:.3f}, B={b_avg:.3f}")
    print(f"Selections: A={trackers['fast_good'].n}, B={trackers['slow_reliable'].n}")
    
    a_n = trackers["fast_good"].n
    b_n = trackers["slow_reliable"].n
    min_sel = min(a_n, b_n)
    
    print("\n" + "=" * 60)
    if min_sel < 20:
        print("❌ LOCK-IN")
    elif a_avg > b_avg + 0.1:
        print("✅ ADAPTIVE: recovered")
    elif b_avg > a_avg + 0.1:
        print("⚠️ CONSERVATIVE (but healthy)")
    else:
        print("✅ BALANCED: no lock-in")
    print(f"Min selections: {min_sel}")
    print("=" * 60)

test()