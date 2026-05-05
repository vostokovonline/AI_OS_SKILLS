"""
Test #6: Risk-Aware Reward
==========================
Problem from Test #4: System can't learn from rare catastrophic events
Solution: Incorporate failure_rate into reward directly (not from observations)

New reward formula:
  reward = expected_reward - risk_penalty
  where risk_penalty = max(0, (1 - success_rate)) * K

Scenario (same as Test #4):
  SkillA: 100% success, slow → reward ≈ 0.75
  SkillB: 95% known failure rate, fast
         → expected ≈ 0.97 - 0.15 = 0.82 (or lower depending on K)

Key difference: System penalizes risky skills BEFORE they cause damage
"""

import asyncio
import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

ALPHA = 0.1
EPSILON = 0.1

# Configurable risk penalty factor
RISK_PENALTY_K = 0.5  # How much to penalize per 1% of failure rate

class SkillA:
    id = "slow_reliable"
    success_rate = 1.0
    @staticmethod
    def execute():
        return {"success": True, "latency": 0.5}

class SkillB:
    id = "fast_risky"
    success_rate = 0.95  # Known failure rate (from metadata, not observation)
    @staticmethod
    def execute():
        return {"success": random.random() < 0.95, "latency": 0.01}

SKILLS = [SkillA, SkillB]

def compute_risk_penalty(skill):
    """Penalize based on known failure rate (not observed)"""
    failure_rate = 1.0 - skill.success_rate
    return max(0, failure_rate * RISK_PENALTY_K * 10)  # Scale for visibility

def reward(result, skill):
    """Risk-aware reward: success-based + risk penalty"""
    if not result["success"]:
        base = -2.0
    else:
        base = 1.0 - min(result["latency"] * 0.5, 0.3)
    
    # Add risk penalty based on KNOWN failure rate (not observation)
    risk_penalty = compute_risk_penalty(skill)
    
    return base - risk_penalty

async def test():
    from sqlalchemy import text
    from database import AsyncSessionLocal
    
    print("=" * 60)
    print("RISK-AWARE REWARD TEST")
    print("=" * 60)
    print(f"Risk penalty K = {RISK_PENALTY_K}")
    print("SkillA (slow_reliable): 100% success → base=0.75, risk=0 → total=0.75")
    print("SkillB (fast_risky): 95% success → base≈0.97, risk=0.25 → total≈0.72")
    print("Expected: system should prefer slow_reliable due to risk awareness")
    print("=" * 60)
    
    async with AsyncSessionLocal() as session:
        for s in SKILLS:
            await session.execute(text("""
                INSERT INTO skill_stats VALUES (:id, :name, 0, 0, 0, 0, 0, 0, 0, NOW(), NOW(), NOW(), 'test6', 0.5)
                ON CONFLICT (skill_id, task_type) DO UPDATE SET q_value=0.5
            """), {"id": s.id, "name": s.id})
        await session.commit()
    
    selections = {"slow_reliable": 0, "fast_risky": 0}
    
    for t in range(1, 51):
        async with AsyncSessionLocal() as session:
            q = {r[0]:r[1] for r in (await session.execute(text(
                "SELECT skill_id, q_value FROM skill_stats WHERE task_type='test6'"
            ))).fetchall()}
        
        if random.random() < EPSILON:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: q.get(s.id, 0.5))
        
        result = chosen.execute()
        r = reward(result, chosen)
        
        q_old = q.get(chosen.id, 0.5)
        q_new = q_old + ALPHA * (r - q_old)
        
        async with AsyncSessionLocal() as session:
            await session.execute(text("UPDATE skill_stats SET q_value=:q WHERE skill_id=:id AND task_type='test6'"),
                {"q": q_new, "id": chosen.id})
            await session.commit()
        
        selections[chosen.id] += 1
        
        risk_a = compute_risk_penalty(SkillA)
        risk_b = compute_risk_penalty(SkillB)
        
        if t <= 10 or t % 10 == 0:
            print(f"t={t:2d} | {chosen.id:12s} | r={r:5.2f} | Q(slow)={q.get('slow_reliable',0.5):.3f} | Q(risky)={q.get('fast_risky',0.5):.3f}")
    
    print("\n" + "=" * 60)
    print("RISK PENALTIES:")
    print(f"  slow_reliable: {compute_risk_penalty(SkillA):.2f} (failure_rate=0%)")
    print(f"  fast_risky:    {compute_risk_penalty(SkillB):.2f} (failure_rate=5%)")
    print("\nFINAL Q-VALUES:")
    async with AsyncSessionLocal() as session:
        for r in (await session.execute(text("SELECT skill_id, q_value FROM skill_stats WHERE task_type='test6'"))).fetchall():
            print(f"  {r[0]}: {r[1]:.3f}")
    
    print(f"\nSelections: slow_reliable={selections['slow_reliable']}, fast_risky={selections['fast_risky']}")
    
    reliable_q = q.get('slow_reliable', 0.5)
    risky_q = q.get('fast_risky', 0.5)
    
    print("\n" + "=" * 60)
    if reliable_q > risky_q + 0.1:
        print("✅ RISK-AWARE: system avoids risky skill based on known failure_rate")
    elif risky_q > reliable_q + 0.1:
        print("❌ BROKEN: system prefers risky despite risk awareness")
    else:
        print("≈ CLOSE")
    print("=" * 60)

asyncio.run(test())