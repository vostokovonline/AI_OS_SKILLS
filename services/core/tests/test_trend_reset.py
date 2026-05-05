"""
Test #14b: Smart Re-evaluation
==============================
Key insight: After skill recovers, old negative rewards poison the trend

Solution: 
- If skill hasn't been used for N steps, reset its recent window
- Force re-evaluation of "abandoned" skills
"""

import random
import math
from collections import deque
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

LAMBDA = 0.4
TREND_ALPHA = 0.5
C = 2.0
RECENT_WINDOW = 8
RE_EVAL_THRESHOLD = 15  # More aggressive re-evaluation

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
        self.baseline = 0.5
        self.recent_rewards = deque(maxlen=RECENT_WINDOW)
        self.last_used = 0
    
    @property
    def recent_avg(self):
        return sum(self.recent_rewards) / len(self.recent_rewards) if self.recent_rewards else 0.5
    
    @property
    def trend(self):
        if len(self.recent_rewards) < 3:
            return 0
        return self.recent_avg - self.baseline
    
    @property
    def needs_re_eval(self):
        return (self.last_used > 0 and (tracker_env.current_step - self.last_used) > RE_EVAL_THRESHOLD)
    
    def score(self, total_steps):
        if self.n == 0:
            return float('inf')
        
        # If abandoned, force re-evaluation
        if self.needs_re_eval:
            return 5.0  # High score to ensure selection
        
        exploration = C * math.sqrt(math.log(total_steps + 1) / self.n)
        trend_bonus = TREND_ALPHA * self.trend * 8
        
        return self.q + exploration + trend_bonus
    
    def update(self, reward, current_step):
        self.n += 1
        self.last_used = current_step
        self.recent_rewards.append(reward)
        
        if len(self.recent_rewards) >= 3:
            # Reset baseline on re-evaluation to capture new state
            if self.n == 1 or self.needs_re_eval:
                self.baseline = self.recent_avg
            else:
                self.baseline = 0.8 * self.baseline + 0.2 * self.recent_avg
            
            trend = self.trend
            self.q = self.q + LAMBDA * (reward - self.q) + TREND_ALPHA * trend
        else:
            self.q = (1 - LAMBDA) * self.q + LAMBDA * reward

# Global tracker for current step
class Env:
    current_step = 0

tracker_env = Env()

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.15, 0.25)

def test():
    print("=" * 60)
    print("SMART RE-EVALUATION TEST")
    print("=" * 60)
    print(f"Re-eval threshold: {RE_EVAL_THRESHOLD} steps")
    print("=" * 60)
    
    trackers = {s.id: Tracker(s) for s in SKILLS}
    total_steps = 0
    
    for t in range(1, 226):
        tracker_env.current_step = t
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
        
        # Higher exploration in recovery phase
        explore_rate = 0.05 if t < 15 else (0.15 if t > 150 else 0.05)
        
        if random.random() < explore_rate:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: trackers[s.id].score(total_steps))
        
        result = chosen.execute()
        r = base_reward(result)
        
        tr = trackers[chosen.id]
        tr.update(r, t)
        
        if t % 50 == 0:
            a = trackers["fast_good"]
            b = trackers["slow_reliable"]
            a_re = " RE-EVAL" if a.needs_re_eval else ""
            print(f"t={t:3d} [{phase:12s}] | A_q={a.q:.2f}{a_re} | B_q={b.q:.2f}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    for sid, tr in trackers.items():
        print(f"  {sid}: n={tr.n}, Q={tr.q:.3f}, trend={tr.trend:+.3f}")
    
    a_q = trackers["fast_good"].q
    b_q = trackers["slow_reliable"].q
    
    print(f"\nFinal: A={a_q:.3f}, B={b_q:.3f}")
    
    print("\n" + "=" * 60)
    if a_q > b_q + 0.05:
        print("✅ ADAPTIVE: system recovered")
    elif b_q > a_q + 0.1:
        print("⚠️ CONSERVATIVE: still prefers B")
    else:
        print("✅ BALANCED: competitive")
    print("=" * 60)

test()