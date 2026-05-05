"""
Test #11b: UCB + Forced Re-check
=================================
Add forced exploration for skills that haven't been used recently
This ensures recovery after degradation
"""

import random
import math
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

LAMBDA = 0.6  # Higher = faster adaptation, more volatile
C = 3.0
BETA = 0.05
FORCE_AFTER_N = 15  # More frequent forced exploration

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
        self.last_used = 0
    
    def ucb_score(self, total_steps):
        if self.n == 0:
            return float('inf')
        exploration = C * math.sqrt(math.log(total_steps) / self.n)
        return self.q + exploration
    
    def update_ema(self, reward, current_step):
        self.q = (1 - LAMBDA) * self.q + LAMBDA * reward
        self.last_used = current_step
    
    def should_force(self, current_step, total_steps):
        # Force re-check if not used for FORCE_AFTER_N steps
        return (current_step - self.last_used) >= FORCE_AFTER_N

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.1, 0.2)

def test():
    print("=" * 60)
    print("UCB + FORCED RE-CHECK TEST")
    print("=" * 60)
    print(f"Lambda = {LAMBDA}, C = {C}, Force after {FORCE_AFTER_N} steps")
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
        
        # UCB selection with forced exploration
        candidates = []
        for s in SKILLS:
            tr = trackers[s.id]
            if tr.should_force(t, total_steps):
                # Force this skill - give it very high score
                score = float('inf')
            else:
                score = tr.ucb_score(total_steps)
            candidates.append((s, score))
        
        chosen = max(candidates, key=lambda x: x[1])[0]
        
        result = chosen.execute()
        r = base_reward(result)
        
        tr = trackers[chosen.id]
        tr.n += 1
        if result["success"]:
            tr.successes += 1
        tr.update_ema(r, t)
        
        if t % 50 == 0:
            a_ucb = trackers["fast_variable"].ucb_score(total_steps)
            b_ucb = trackers["slow_stable"].ucb_score(total_steps)
            a_forced = trackers["fast_variable"].should_force(t, total_steps)
            b_forced = trackers["slow_stable"].should_force(t, total_steps)
            marker = " [FORCE!]" if a_forced or b_forced else ""
            print(f"t={t:3d} [{phase:12s}] | A={a_ucb:.3f}(f={a_forced}) | B={b_ucb:.3f}(f={b_forced}) | {chosen.id}{marker}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        sr = tr.successes / max(1, tr.n)
        print(f"  {sid}: n={tr.n}, sr={sr:5.1%}, Q={tr.q:.3f}, last_used={tr.last_used}")
    
    a_ucb = trackers["fast_variable"].ucb_score(total_steps)
    b_ucb = trackers["slow_stable"].ucb_score(total_steps)
    
    print("\n" + "=" * 60)
    if a_ucb > b_ucb + 0.1:
        print(f"✅ ADAPTIVE: prefers fast_variable")
    elif b_ucb > a_ucb + 0.2:
        print(f"⚠️ CONSERVATIVE: prefers slow_stable")
    else:
        print(f"✅ BALANCED: both competitive")
    print("=" * 60)

test()