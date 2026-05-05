"""
Test #13: Universal Q-Decay + Min Exploration
==============================================
Root problem: Q "sticks" when skill is not selected
Solution: 
  1. Decay ALL Q-values each step (not just selected)
  2. Minimum exploration guarantee (5% random)
  3. Drift as exploration boost, not force
"""

import random
import math
from collections import deque
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

LAMBDA = 0.5
C = 2.0
DECAY = 0.92  # Even stronger decay
MIN_EXPLORE = 0.20  # Higher random exploration
DRIFT_BOOST = 2.0  # Multiply exploration on drift
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
    
    @property
    def recent_avg(self):
        return sum(self.recent_rewards) / len(self.recent_rewards) if self.recent_rewards else 0.5
    
    def detect_drift(self):
        if len(self.recent_rewards) < 5:
            return False
        return (self.baseline - self.recent_avg) > 0.3
    
    def score(self, total_steps):
        if self.n == 0:
            return float('inf')
        
        exploration = C * math.sqrt(math.log(total_steps + 1) / self.n)
        
        # Boost exploration if drifted
        if self.detect_drift():
            exploration *= DRIFT_BOOST
        
        return self.q + exploration
    
    def decay_q(self):
        """Key: decay ALL Q values, not just selected"""
        self.q *= DECAY
    
    def update(self, reward):
        self.n += 1
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
    print("UNIVERSAL DECAY + MIN EXPLORE TEST")
    print("=" * 60)
    print(f"Lambda={LAMBDA}, C={C}, DECAY={DECAY}, MIN_EXPLORE={MIN_EXPLORE}")
    print(f"Key fix: ALL Q values decay each step")
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
        
        # Step 1: Minimum exploration (probabilistic floor)
        if random.random() < MIN_EXPLORE:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: trackers[s.id].score(total_steps))
        
        result = chosen.execute()
        r = base_reward(result)
        
        # Step 2: Update selected skill
        tr = trackers[chosen.id]
        tr.update(r)
        
        # Step 3: DECAY ALL Q values (key fix!)
        for sid, tr_all in trackers.items():
            tr_all.decay_q()
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            a_d = " DRIFT!" if a.detect_drift() else ""
            print(f"t={t:3d} [{phase:12s}] | A_Q={a.q:.2f}{a_d} | B_Q={b.q:.2f} | chosen={chosen.id}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, Q={tr.q:.3f}, recent={tr.recent_avg:.3f}")
    
    a_q = trackers["fast_good"].q
    b_q = trackers["slow_reliable"].q
    
    print(f"\nFinal: A={a_q:.3f}, B={b_q:.3f}")
    
    print("\n" + "=" * 60)
    if a_q > b_q + 0.05:
        print("✅ ADAPTIVE: prefers fast_good (recovered)")
    elif b_q > a_q + 0.1:
        print("⚠️ CONSERVATIVE: prefers slow_reliable")
    else:
        print("✅ BALANCED: competitive")
    print("=" * 60)

test()