"""
Test #8: Multi-Skill Environment
================================
Test: Can system handle 5+ skills without getting stuck in local optimum?

Skills:
  1. perfect_slow:    100% success, slow (0.5s)        - baseline
  2. good_balanced:   90% success, medium (0.2s)      - good
  3. fast_median:     80% success, fast (0.05s)        - risky
  4. fast_unstable:   70% success, very fast (0.01s)   - risky
  5. risky_catastrophic: 95% success, fast (0.02s)    - rare catastrophic
  6. trash_fast:     50% success, fastest (0.005s)   - clearly bad

Expected: System should find good balance, not get stuck on fast but bad skills
"""

import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

ALPHA = 0.1
EPSILON = 0.15
BETA = 0.25

class Skill:
    def __init__(self, id, success_rate, latency):
        self.id = id
        self.success_rate = success_rate
        self.latency = latency
    
    def execute(self):
        if random.random() > self.success_rate:
            return {"success": False, "latency": self.latency, "catastrophic": False}
        return {"success": True, "latency": self.latency}

SKILLS = [
    Skill("perfect_slow",      1.00, 0.50),
    Skill("good_balanced",     0.90, 0.20),
    Skill("fast_median",       0.80, 0.05),
    Skill("fast_unstable",     0.70, 0.01),
    Skill("risky_catastrophic", 0.95, 0.02),  # rare failures
    Skill("trash_fast",        0.50, 0.005),
]

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
    print("MULTI-SKILL ENVIRONMENT TEST (6 skills)")
    print("=" * 60)
    for s in SKILLS:
        expected = s.success_rate * (1.0 - min(s.latency * 0.5, 0.3))
        print(f"  {s.id:20s}: sr={s.success_rate:.0%}, latency={s.latency:.3f}s, expected_r={expected:.2f}")
    print("=" * 60)
    
    trackers = {s.id: Tracker(s) for s in SKILLS}
    
    for t in range(1, 201):
        # Epsilon-greedy selection
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
        
        if t <= 10 or t % 50 == 0:
            print(f"t={t:3d} | {chosen.id:20s} | r={r:5.2f} | eff_q={tr.effective_q():.3f}")
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS (sorted by effective_q):")
    sorted_skills = sorted(trackers.items(), key=lambda x: x[1].effective_q(), reverse=True)
    for sid, tr in sorted_skills:
        sr = tr.successes / max(1, tr.total)
        print(f"  {sid:20s}: total={tr.total:3d}, sr={sr:5.1%}, Q={tr.q:.3f}, eff_q={tr.effective_q():.3f}")
    
    # Check: did system pick a reasonable skill?
    best_skill = sorted_skills[0][0]
    print("\n" + "=" * 60)
    if best_skill in ["perfect_slow", "good_balanced"]:
        print(f"✅ EXCELLENT: chose {best_skill} (best expected)")
    elif best_skill == "fast_median":
        print(f"⚠️ OK: chose fast_median (reasonable)")
    elif best_skill in ["fast_unstable", "risky_catastrophic"]:
        print(f"❌ BROKEN: chose {best_skill} (too risky)")
    else:
        print(f"❌ BAD: chose {best_skill} (trash skill)")
    print("=" * 60)

test()