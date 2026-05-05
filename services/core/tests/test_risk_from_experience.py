"""
Test #7: Learning Risk From Experience (In-Memory)
===================================================
Problem: Test #6 used "magic" success_rate = 0.95 (oracle)
Solution: Learn risk from observations + uncertainty penalty

Key formula:
  success_rate = successes / total_executions
  uncertainty = BETA / sqrt(total_executions)
  reward = base_reward - uncertainty

No oracle - system learns failure_rate from its own observations.
"""

import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

ALPHA = 0.1
EPSILON = 0.3  # More exploration to trigger catastrophic events
BETA = 0.2  # Lower uncertainty penalty so learning matters more

class SkillA:
    """100% success, reliable but slow"""
    id = "slow_reliable"
    @staticmethod
    def execute():
        return {"success": True, "latency": 0.5}

class SkillB:
    """95% success, fast, 5% catastrophic failure"""
    id = "fast_risky"
    @staticmethod
    def execute():
        if random.random() < 0.05:
            return {"success": False, "latency": 0.01, "catastrophic": True}
        return {"success": True, "latency": 0.01}

SKILLS = [SkillA, SkillB]

class SkillTracker:
    def __init__(self, skill):
        self.skill = skill
        self.total = 0
        self.successes = 0
        self.q = 0.5
    
    def success_rate(self):
        return self.successes / max(1, self.total)
    
    def uncertainty(self):
        return BETA / (self.total ** 0.5) if self.total > 0 else BETA
    
    def effective_q(self):
        """Q with uncertainty penalty - penalizes low-experience choices"""
        return self.q - self.uncertainty()
    
    def update(self, reward):
        self.q = self.q + ALPHA * (reward - self.q)

def base_reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.5, 0.3)

def test():
    print("=" * 60)
    print("LEARNING RISK FROM EXPERIENCE (IN-MEMORY)")
    print("=" * 60)
    print("No oracle - system learns failure_rate from observations")
    print(f"Formula: effective_q = Q - {BETA}/sqrt(total)")
    print("=" * 60)
    
    trackers = {s.id: SkillTracker(s) for s in SKILLS}
    selections = {"slow_reliable": 0, "fast_risky": 0}
    catastrophic_count = 0
    
    for t in range(1, 101):
        # Epsilon-greedy with uncertainty-penalized Q
        if random.random() < EPSILON:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: trackers[s.id].effective_q())
        
        result = chosen.execute()
        if result.get("catastrophic"):
            catastrophic_count += 1
        
        r = base_reward(result)
        tracker = trackers[chosen.id]
        tracker.total += 1
        if result["success"]:
            tracker.successes += 1
        tracker.update(r)
        
        selections[chosen.id] += 1
        
        if t <= 10 or t % 20 == 0:
            eff_q = tracker.effective_q()
            print(f"t={t:3d} | {chosen.id:12s} | r={r:5.2f} | eff_q={eff_q:.3f} | total={tracker.total} | sr={tracker.success_rate():.2%}")
    
    print("\n" + "=" * 60)
    print("FINAL STATS:")
    for sid, tr in trackers.items():
        print(f"  {sid}: total={tr.total}, sr={tr.success_rate():.2%}, Q={tr.q:.3f}, effective_q={tr.effective_q():.3f}")
    
    print(f"\nSelections: slow_reliable={selections['slow_reliable']}, fast_risky={selections['fast_risky']}")
    print(f"Catastrophic events: {catastrophic_count}")
    
    reliable_eff = trackers["slow_reliable"].effective_q()
    risky_eff = trackers["fast_risky"].effective_q()
    
    print("\n" + "=" * 60)
    if reliable_eff > risky_eff + 0.05:
        print("✅ SYSTEM LEARNED RISK FROM EXPERIENCE - avoids risky skill")
    elif risky_eff > reliable_eff + 0.05:
        print("❌ BROKEN: still prefers risky skill")
    else:
        print("≈ CLOSE - may need more iterations")
    print("=" * 60)

test()