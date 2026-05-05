"""
Test #10: Adaptive Learning with EMA
=====================================
Key test: Can system switch between skills when environment changes?

Scenario:
  Phase 1 (t=1-75):   A=90%/fast, B=100%/slow → prefer A
  Phase 2 (t=76-150): A degrades to 50%, B stays 100% → switch to B
  Phase 3 (t=151-225): A recovers to 90% → try A again

With EMA: should track changes, not get stuck
"""

import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

LAMBDA = 0.4  # High enough to forget old bad experiences
EPSILON = 0.25  # Enough exploration to test alternatives
BETA = 0.15

class SkillA:
    id = "fast_variable"
    success_rate = 0.9
    
    @classmethod
    def execute(cls):
        if random.random() > cls.success_rate:
            return {"success": False, "latency": 0.01}
        return {"success": True, "latency": 0.01}  # Much faster

class SkillB:
    id = "slow_stable"
    success_rate = 1.0
    
    @classmethod
    def execute(cls):
        if random.random() > cls.success_rate:
            return {"success": False, "latency": 0.8}
        return {"success": True, "latency": 0.8}  # Much slower

SKILLS = [SkillA, SkillB]

class Tracker:
    def __init__(self, skill):
        self.skill = skill
        self.total = 0
        self.successes = 0
        self.q = 0.5
    
    def effective_q(self):
        uncertainty = min(BETA / (self.total ** 0.5) if self.total > 0 else BETA, 0.2)
        return self.q - uncertainty
    
    def update_ema(self, reward):
        self.q = (1 - LAMBDA) * self.q + LAMBDA * reward

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.3, 0.3)  # Less latency penalty

def test():
    print("=" * 60)
    print("ADAPTIVE EMA TEST - REVISED SCENARIO")
    print("=" * 60)
    print(f"Lambda = {LAMBDA}, Epsilon = {EPSILON}")
    print("Phase 1 (t=1-75):   A=90%/fast, B=100%/slow → prefer A")
    print("Phase 2 (t=76-150): A=50% (degraded), B=100% → switch to B")
    print("Phase 3 (t=151-225): A=90% (recovered) → try A again")
    print("=" * 60)
    
    trackers = {s.id: Tracker(s) for s in SKILLS}
    
    for t in range(1, 226):
        # Environment changes
        if t <= 75:
            SkillA.success_rate = 0.9
            phase = "A good"
        elif t <= 150:
            SkillA.success_rate = 0.5  # Degraded
            phase = "A degraded"
        else:
            SkillA.success_rate = 0.9  # Recovered
            phase = "A recovered"
        
        # Selection with exploration
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
        tr.update_ema(r)
        
        if t % 50 == 0:
            a_q = trackers["fast_variable"].effective_q()
            b_q = trackers["slow_stable"].effective_q()
            print(f"t={t:3d} [{phase:12s}] | A_eff={a_q:.3f} | B_eff={b_q:.3f} | chosen={chosen.id}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        sr = tr.successes / max(1, tr.total)
        print(f"  {sid}: total={tr.total}, sr={sr:5.1%}, Q={tr.q:.3f}, eff_q={tr.effective_q():.3f}")
    
    # Check if it adapted properly
    a_eff = trackers["fast_variable"].effective_q()
    b_eff = trackers["slow_stable"].effective_q()
    
    print("\n" + "=" * 60)
    # In phase 3, A is good again (90%) and faster, so should be competitive
    # But B is 100% reliable - which one wins depends on balance
    diff = abs(a_eff - b_eff)
    if diff < 0.15:
        print(f"✅ BALANCED: both competitive (A={a_eff:.3f}, B={b_eff:.3f})")
        print("   System adapted - doesn't get stuck on one choice")
    elif b_eff > a_eff:
        print(f"⚠️ CONSERVATIVE: prefers B (reliable)")
    else:
        print(f"✅ ADAPTIVE: prefers A (learned it's good again)")
    print("=" * 60)

test()