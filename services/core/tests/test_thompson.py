"""
Test #15: Thompson Sampling
============================
Instead of storing Q, store distribution over reward

Key insight: 
- Skill not used recently → wider distribution → higher chance to sample
- No explicit exploration needed - it emerges from uncertainty
- "Dead arm" problem solved naturally

Uses Beta distribution (conjugate prior for Bernoulli)
"""

import random
import math
from collections import deque
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

# Beta distribution parameters
# alpha = successes + 1, beta = failures + 1
# Wide distribution when few samples

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

class BetaTracker:
    """Thompson Sampling with Beta distribution"""
    def __init__(self, skill):
        self.skill = skill
        self.alpha = 1.0  # prior
        self.beta = 1.0   # prior
        self.successes = 0
        self.failures = 0
        self.total_latency = 0
        self.n = 0
    
    def sample_expected_reward(self):
        """Sample from Beta distribution, combine with latency penalty"""
        if self.n == 0:
            return 1.0  # unexplored - optimistic
        
        # Sample from Beta
        success_sample = random.betavariate(self.alpha, self.beta)
        
        # Expected latency penalty (not sampled - use average)
        avg_latency = self.total_latency / self.n if self.n > 0 else 0.5
        latency_penalty = min(avg_latency * 0.3, 0.3)
        
        return success_sample - latency_penalty
    
    @property
    def uncertainty(self):
        """High when few samples"""
        if self.n == 0:
            return 1.0
        return 1.0 - (self.alpha / (self.alpha + self.beta))  # variance proxy
    
    def update(self, success, latency):
        self.n += 1
        self.total_latency += latency
        
        if success:
            self.successes += 1
            self.alpha += 1
        else:
            self.failures += 1
            self.beta += 1
    
    @property
    def estimated_mean(self):
        return self.alpha / (self.alpha + self.beta)

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.3, 0.3)

def test():
    print("=" * 60)
    print("THOMPSON SAMPLING TEST")
    print("=" * 60)
    print("No explicit exploration - emerges from uncertainty")
    print("=" * 60)
    
    trackers = {s.id: BetaTracker(s) for s in SKILLS}
    
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
        
        # Thompson Sampling: sample from each distribution and pick max
        chosen = max(SKILLS, key=lambda s: trackers[s.id].sample_expected_reward())
        
        result = chosen.execute()
        
        tr = trackers[chosen.id]
        tr.update(result["success"], result["latency"])
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            print(f"t={t:3d} [{phase:12s}] | A_sample={a.sample_expected_reward():.2f}(n={a.n}) | B_sample={b.sample_expected_reward():.2f}(n={b.n})")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, mean={tr.estimated_mean:.3f}, alpha={tr.alpha:.1f}, beta={tr.beta:.1f}")
    
    a_sample = trackers["fast_good"].sample_expected_reward()
    b_sample = trackers["slow_reliable"].sample_expected_reward()
    
    # Run multiple samples to get stable result
    a_scores = [trackers["fast_good"].sample_expected_reward() for _ in range(100)]
    b_scores = [trackers["slow_reliable"].sample_expected_reward() for _ in range(100)]
    a_avg = sum(a_scores) / len(a_scores)
    b_avg = sum(b_scores) / len(b_scores)
    
    print(f"\nSample avg (100x): A={a_avg:.3f}, B={b_avg:.3f}")
    
    print("\n" + "=" * 60)
    if a_avg > b_avg + 0.05:
        print("✅ ADAPTIVE: Thompson Sampling recovered")
    elif b_avg > a_avg + 0.1:
        print("⚠️ CONSERVATIVE: still prefers B")
    else:
        print("✅ BALANCED: competitive")
    print("=" * 60)

test()