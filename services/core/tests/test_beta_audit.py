"""
Test #17b: Beta TS + Audit Layer (Production-Ready)
====================================================
Using Beta for fast policy (more stable), Audit layer for re-evaluation

Beta captures: success rate (what matters most)
Audit: guarantees re-evaluation of abandoned skills
"""

import random
import math
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

AUDIT_THRESHOLD = 15  # Force re-evaluation if not used for 15 steps

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

class BetaTS:
    """Beta Thompson Sampling with audit tracking"""
    def __init__(self, skill):
        self.skill = skill
        self.alpha = 1.0
        self.beta = 1.0
        self.last_used = 0
        self.total_latency = 0
        self.n = 0
    
    def sample(self):
        if self.n == 0:
            return random.betavariate(1, 1) - 0.2  # optimistic, penalize latency
        
        success_sample = random.betavariate(self.alpha, self.beta)
        avg_latency = self.total_latency / self.n if self.n > 0 else 0.5
        latency_penalty = min(avg_latency * 0.3, 0.3)
        
        return success_sample - latency_penalty
    
    def update(self, success, latency, current_step):
        self.n += 1
        self.last_used = current_step
        self.total_latency += latency
        
        if success:
            self.alpha += 1
        else:
            self.beta += 1
    
    def needs_audit(self, current_step):
        return (current_step - self.last_used) > AUDIT_THRESHOLD

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.3, 0.3)

def select_with_audit(trackers, current_step):
    # Layer 1: Audit
    for skill in SKILLS:
        if trackers[skill.id].needs_audit(current_step):
            return skill
    
    # Layer 2: Beta TS
    return max(SKILLS, key=lambda s: trackers[s.id].sample())

def test():
    print("=" * 60)
    print("BETA TS + AUDIT LAYER")
    print("=" * 60)
    print(f"Audit threshold: {AUDIT_THRESHOLD}")
    print("=" * 60)
    
    trackers = {s.id: BetaTS(s) for s in SKILLS}
    
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
        
        chosen = select_with_audit(trackers, t)
        
        result = chosen.execute()
        trackers[chosen.id].update(result["success"], result["latency"], t)
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            a_audit = " [AUDIT]" if a.needs_audit(t) else ""
            b_audit = " [AUDIT]" if b.needs_audit(t) else ""
            print(f"t={t:3d} [{phase:12s}] | A_s={a.sample():.2f}(n={a.n}){a_audit} | B_s={b.sample():.2f}(n={b.n}){b_audit}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, alpha={tr.alpha:.0f}, beta={tr.beta:.0f}")
    
    a_samples = [trackers["fast_good"].sample() for _ in range(100)]
    b_samples = [trackers["slow_reliable"].sample() for _ in range(100)]
    a_avg = sum(a_samples) / len(a_samples)
    b_avg = sum(b_samples) / len(b_samples)
    
    print(f"\nSample avg: A={a_avg:.3f}, B={b_avg:.3f}")
    print(f"Selections: A={trackers['fast_good'].n}, B={trackers['slow_reliable'].n}")
    
    print("\n" + "=" * 60)
    if a_avg > b_avg + 0.05:
        print("✅ ADAPTIVE: recovered")
    elif b_avg > a_avg + 0.1:
        print("⚠️ CONSERVATIVE")
    else:
        print("✅ BALANCED: competitive")
    print("=" * 60)

test()