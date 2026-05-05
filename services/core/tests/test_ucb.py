"""
Test #11: UCB (Upper Confidence Bound) Selection
=================================================
Replace epsilon-greedy with UCB for deterministic, adaptive exploration

UCB formula: score = Q + c * sqrt(ln(total_time) / n_i)

Benefits:
- Automatic exploration based on uncertainty
- No random exploration needed
- Better recovery after degradation
- Lower variance than epsilon-greedy
"""

import random
import math
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

LAMBDA = 0.4  # EMA for Q-update
C = 3.0  # Higher exploration constant
BETA = 0.15  # Uncertainty penalty

class SkillA:
    id = "fast_variable"
    success_rate = 0.9
    
    @classmethod
    def execute(cls):
        if random.random() > cls.success_rate:
            return {"success": False, "latency": 0.01}
        return {"success": True, "latency": 0.01}

class SkillB:
    id = "slow_stable"
    success_rate = 1.0
    
    @classmethod
    def execute(cls):
        if random.random() > cls.success_rate:
            return {"success": False, "latency": 0.8}
        return {"success": True, "latency": 0.8}

SKILLS = [SkillA, SkillB]

class Tracker:
    def __init__(self, skill):
        self.skill = skill
        self.n = 0
        self.successes = 0
        self.q = 0.5
    
    def ucb_score(self, total_steps):
        if self.n == 0:
            return float('inf')  # Explore unvisited
        # UCB formula
        exploration = C * math.sqrt(math.log(total_steps) / self.n)
        return self.q + exploration
    
    def update_ema(self, reward):
        self.q = (1 - LAMBDA) * self.q + LAMBDA * reward

def base_reward(result):
    if not result["success"]:
        return -2.0
    # Less latency penalty - success matters more
    return 1.0 - min(result["latency"] * 0.1, 0.2)

def test():
    print("=" * 60)
    print("UCB SELECTION TEST")
    print("=" * 60)
    print(f"Lambda = {LAMBDA}, C = {C} (UCB exploration)")
    print("Phase 1 (t=1-75):   A=90%/fast → prefer A")
    print("Phase 2 (t=76-150): A=50% (degraded) → switch to B")
    print("Phase 3 (t=151-225): A=90% (recovered) → try A again")
    print("=" * 60)
    
    trackers = {s.id: Tracker(s) for s in SKILLS}
    total_steps = 0
    
    for t in range(1, 226):
        total_steps += 1
        
        if t <= 75:
            SkillA.success_rate = 0.9
            phase = "A good"
        elif t <= 150:
            SkillA.success_rate = 0.5
            phase = "A degraded"
        else:
            SkillA.success_rate = 0.9
            phase = "A recovered"
        
        # UCB selection - deterministic!
        chosen = max(SKILLS, key=lambda s: trackers[s.id].ucb_score(total_steps))
        
        result = chosen.execute()
        r = base_reward(result)
        
        tr = trackers[chosen.id]
        tr.n += 1
        if result["success"]:
            tr.successes += 1
        tr.update_ema(r)
        
        if t % 50 == 0:
            a_ucb = trackers["fast_variable"].ucb_score(total_steps)
            b_ucb = trackers["slow_stable"].ucb_score(total_steps)
            print(f"t={t:3d} [{phase:12s}] | A_UCB={a_ucb:.3f} | B_UCB={b_ucb:.3f} | chosen={chosen.id}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        sr = tr.successes / max(1, tr.n)
        print(f"  {sid}: n={tr.n}, sr={sr:5.1%}, Q={tr.q:.3f}, UCB={tr.ucb_score(total_steps):.3f}")
    
    a_ucb = trackers["fast_variable"].ucb_score(total_steps)
    b_ucb = trackers["slow_stable"].ucb_score(total_steps)
    
    print("\n" + "=" * 60)
    diff = abs(a_ucb - b_ucb)
    if a_ucb > b_ucb and diff > 0.1:
        print(f"✅ ADAPTIVE: prefers fast_variable (recovered)")
    elif b_ucb > a_ucb + 0.15:
        print(f"⚠️ CONSERVATIVE: prefers slow_stable")
    else:
        print(f"✅ BALANCED: both competitive")
    print("=" * 60)

test()