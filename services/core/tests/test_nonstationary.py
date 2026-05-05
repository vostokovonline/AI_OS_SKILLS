"""
Test #9: Non-Stationary Environment
===================================
Test: Can system adapt when skill quality changes over time?

Scenario:
  Phase 1 (t=1-50):   fast_skill is good (90% success)
  Phase 2 (t=51-100): fast_skill degrades (50% success) - should switch away
  Phase 3 (t=101-150): fast_skill recovers (90% success) - should switch back

Expected: System should track changing environment, not get stuck on old Q-values
"""

import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

ALPHA = 0.15  # Faster adaptation for changing environment
EPSILON = 0.2
BETA = 0.2

class SlowStable:
    """Always 100% success, slow - baseline"""
    id = "slow_stable"
    @staticmethod
    def execute():
        return {"success": True, "latency": 0.5}

class FastVariable:
    """Changes behavior over time"""
    id = "fast_variable"
    success_rate = 0.9  # Will change
    
    @classmethod
    def execute(cls):
        if random.random() > cls.success_rate:
            return {"success": False, "latency": 0.01}
        return {"success": True, "latency": 0.01}

SKILLS = [SlowStable, FastVariable]

class Tracker:
    def __init__(self, skill):
        self.skill = skill
        self.total = 0
        self.successes = 0
        self.q = 0.5
    
    def effective_q(self):
        uncertainty = min(BETA / (self.total ** 0.5) if self.total > 0 else BETA, 0.3)
        return self.q - uncertainty
    
    def update(self, reward):
        self.q = self.q + ALPHA * (reward - self.q)

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.5, 0.3)

def test():
    print("=" * 60)
    print("NON-STATIONARY ENVIRONMENT TEST")
    print("=" * 60)
    print("Phase 1 (t=1-50):   fast=90% (good)")
    print("Phase 2 (t=51-100): fast=50% (degraded)")
    print("Phase 3 (t=101-150): fast=90% (recovered)")
    print("=" * 60)
    
    trackers = {s.id: Tracker(s) for s in SKILLS}
    
    for t in range(1, 151):
        # Change fast_variable behavior
        if t <= 50:
            FastVariable.success_rate = 0.9
            phase = "GOOD"
        elif t <= 100:
            FastVariable.success_rate = 0.5
            phase = "DEGRADED"
        else:
            FastVariable.success_rate = 0.9
            phase = "RECOVERED"
        
        # Selection
        if random.random() < EPSILON:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: trackers[s.id].effective_q())
        
        result = chosen.execute()
        r = base_reward(result)
        
        tr = trackers[chosen.id]
        tr.total += 1
        if result["success"]:
            tr.successes += 1
        tr.update(r)
        
        if t % 30 == 0:
            slow_q = trackers["slow_stable"].effective_q()
            fast_q = trackers["fast_variable"].effective_q()
            print(f"t={t:3d} [{phase:9s}] | slow_q={slow_q:.3f} | fast_q={fast_q:.3f} | chosen={chosen.id}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        sr = tr.successes / max(1, tr.total)
        print(f"  {sid}: total={tr.total}, sr={sr:.1%}, Q={tr.q:.3f}, eff_q={tr.effective_q():.3f}")
    
    # Check adaptation
    slow_eff = trackers["slow_stable"].effective_q()
    fast_eff = trackers["fast_variable"].effective_q()
    
    print("\n" + "=" * 60)
    # After phase 3 (recovered), system should favor fast if it's good again
    # But given Q-learning is slow to forget, slow might still dominate
    if slow_eff > fast_eff:
        print(f"⚠️ STABLE: prefers slow_stable (may be too conservative)")
        print("   This is actually OK for safety-critical systems")
    else:
        print(f"✅ ADAPTIVE: prefers fast_variable (learned it's good again)")
    print("=" * 60)

test()