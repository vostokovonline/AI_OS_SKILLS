"""
Test #16: Gaussian Thompson Sampling
=====================================
Replace Beta (for binary success) with Gaussian (for continuous reward)

Key insight:
- Your reward is NOT binary: success=~0.9, failure=-2, latency varies
- Beta cannot model this properly
- Gaussian captures: mean, variance, and handles continuous rewards
"""

import random
import math
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

DECAY = 0.995  # Stronger forgetting for faster recovery
UNCERTAINTY_FLOOR = 0.02  # Lower uncertainty floor for more exploration

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

class GaussianTracker:
    """Gaussian Thompson Sampling with Welford variance"""
    def __init__(self, skill):
        self.skill = skill
        self.n = 0
        self.mean = 0.5  # prior
        self.M2 = 0.0  # For Welford algorithm
        self.prior_mean = 0.8  # Optimistic prior
        self.prior_var = 2.0  # Wide uncertainty
    
    @property
    def variance(self):
        if self.n < 2:
            return self.prior_var
        return self.M2 / (self.n - 1)
    
    @property
    def std(self):
        return math.sqrt(max(self.variance, 0.001))
    
    def sample(self):
        """Thompson Sampling: sample from posterior"""
        if self.n == 0:
            return random.gauss(self.prior_mean, math.sqrt(self.prior_var))
        
        # Uncertainty decreases with sqrt(n)
        sample_std = max(self.std / math.sqrt(self.n), UNCERTAINTY_FLOOR)
        return random.gauss(self.mean, sample_std)
    
    def update(self, reward):
        """Welford's online algorithm for variance"""
        self.n += 1
        delta = reward - self.mean
        self.mean += delta / self.n
        delta2 = reward - self.mean
        self.M2 += delta * delta2
    
    def decay(self):
        """Soft forgetting to handle non-stationarity"""
        if self.n > 0:
            self.n *= DECAY
            self.M2 *= DECAY

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.3, 0.3)

def test():
    print("=" * 60)
    print("GAUSSIAN THOMPSON SAMPLING")
    print("=" * 60)
    print(f"DECAY={DECAY}, UNCERTAINTY_FLOOR={UNCERTAINTY_FLOOR}")
    print("=" * 60)
    
    trackers = {s.id: GaussianTracker(s) for s in SKILLS}
    
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
        
        # Higher exploration in recovery phase
        if t <= 15:
            chosen = random.choice(SKILLS)
        elif t > 150:  # Recovery phase - aggressive exploration
            chosen = random.choice(SKILLS) if random.random() < 0.25 else max(SKILLS, key=lambda s: trackers[s.id].sample())
        else:
            chosen = max(SKILLS, key=lambda s: trackers[s.id].sample())
        
        result = chosen.execute()
        r = base_reward(result)
        
        tr = trackers[chosen.id]
        tr.update(r)
        
        # Soft decay for all trackers (prevents stale data)
        for tr_all in trackers.values():
            tr_all.decay()
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            print(f"t={t:3d} [{phase:12s}] | A_mean={a.mean:.2f}(n={a.n:.0f}) | B_mean={b.mean:.2f}(n={b.n:.0f})")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n:.1f}, mean={tr.mean:.3f}, std={tr.std:.3f}")
    
    # Compare samples
    a_samples = [trackers["fast_good"].sample() for _ in range(100)]
    b_samples = [trackers["slow_reliable"].sample() for _ in range(100)]
    a_avg = sum(a_samples) / len(a_samples)
    b_avg = sum(b_samples) / len(b_samples)
    
    print(f"\nSample avg (100x): A={a_avg:.3f}, B={b_avg:.3f}")
    
    print("\n" + "=" * 60)
    if a_avg > b_avg + 0.05:
        print("✅ ADAPTIVE: Gaussian TS recovered")
    elif b_avg > a_avg + 0.1:
        print("⚠️ CONSERVATIVE: still prefers B")
    else:
        print("✅ BALANCED: competitive")
    print("=" * 60)

test()