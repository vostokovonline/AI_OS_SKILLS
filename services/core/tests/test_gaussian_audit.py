"""
Test #17: Gaussian TS + Audit Layer (Production-Ready)
======================================================
Proper Bayesian Gaussian with Normal-Inverse-Gamma prior
+ Audit layer for guaranteed re-evaluation of abandoned skills

Key insight:
- Gaussian TS alone cannot solve non-stationary bandit
- Need 2-layer: fast policy + slow audit
- Audit forces re-evaluation, preventing sample starvation
"""

import random
import math
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

AUDIT_THRESHOLD = 20  # Force re-evaluation if not used for 20 steps

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

class GaussianTS:
    """Proper Bayesian Gaussian with Normal-Inverse-Gamma prior"""
    def __init__(self, skill):
        self.skill = skill
        self.last_used = 0
        self.n = 0
        
        # Normal-Inverse-Gamma prior (conjugate for Gaussian)
        self.mu = 0.5      # prior mean
        self.lambda_ = 1.0 # precision of mean
        self.alpha = 1.0   # shape of variance
        self.beta = 1.0    # scale of variance
    
    def sample(self):
        """Thompson Sampling from posterior"""
        if self.n == 0:
            # Sample from prior
            sigma2 = 1.0 / random.gammavariate(self.alpha, 1.0 / self.beta)
            return random.gauss(self.mu, math.sqrt(sigma2 / self.lambda_))
        
        # Sample from posterior
        sigma2 = 1.0 / random.gammavariate(self.alpha, 1.0 / self.beta)
        return random.gauss(self.mu, math.sqrt(sigma2 / self.lambda_))
    
    def update(self, reward, current_step):
        """Bayesian update for Gaussian with unknown variance"""
        self.n += 1
        self.last_used = current_step
        
        # Update sufficient statistics
        self.lambda_ += 1
        delta = reward - self.mu
        self.mu += delta / self.lambda_
        
        # Update variance parameters
        self.alpha += 0.5
        self.beta += 0.5 * delta * delta * (self.lambda_ - 1) / self.lambda_
    
    def needs_audit(self, current_step):
        """Check if skill needs forced re-evaluation"""
        return (current_step - self.last_used) > AUDIT_THRESHOLD

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.3, 0.3)

def select_with_audit(trackers, current_step):
    """
    Two-layer selection:
    1. Audit layer: forced re-evaluation of abandoned skills
    2. Fast policy: Thompson Sampling
    """
    # Layer 1: Check for abandoned skills
    for skill in SKILLS:
        if trackers[skill.id].needs_audit(current_step):
            return skill  # Forced audit
    
    # Layer 2: Thompson Sampling
    return max(SKILLS, key=lambda s: trackers[s.id].sample())

def test():
    print("=" * 60)
    print("GAUSSIAN TS + AUDIT LAYER")
    print("=" * 60)
    print(f"Audit threshold: {AUDIT_THRESHOLD} steps")
    print("Layer 1: Forced re-evaluation of abandoned skills")
    print("Layer 2: Thompson Sampling")
    print("=" * 60)
    
    trackers = {s.id: GaussianTS(s) for s in SKILLS}
    
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
        
        # Two-layer selection
        chosen = select_with_audit(trackers, t)
        
        result = chosen.execute()
        r = base_reward(result)
        
        trackers[chosen.id].update(r, t)
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            a_audit = " [AUDIT]" if a.needs_audit(t) else ""
            b_audit = " [AUDIT]" if b.needs_audit(t) else ""
            print(f"t={t:3d} [{phase:12s}] | A_mu={a.mu:.2f}(n={a.n}){a_audit} | B_mu={b.mu:.2f}(n={b.n}){b_audit}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, mu={tr.mu:.3f}, alpha={tr.alpha:.1f}, beta={tr.beta:.1f}")
    
    # Compare samples
    a_samples = [trackers["fast_good"].sample() for _ in range(100)]
    b_samples = [trackers["slow_reliable"].sample() for _ in range(100)]
    a_avg = sum(a_samples) / len(a_samples)
    b_avg = sum(b_samples) / len(b_samples)
    
    print(f"\nSample avg: A={a_avg:.3f}, B={b_avg:.3f}")
    
    # Check if audit helped
    a_n = trackers["fast_good"].n
    b_n = trackers["slow_reliable"].n
    print(f"Selection distribution: A={a_n}, B={b_n}")
    
    print("\n" + "=" * 60)
    if a_avg > b_avg + 0.05:
        print("✅ ADAPTIVE: recovered after degradation")
    elif b_avg > a_avg + 0.1:
        print("⚠️ CONSERVATIVE: still prefers B")
    else:
        print("✅ BALANCED: both competitive")
    print("=" * 60)

test()