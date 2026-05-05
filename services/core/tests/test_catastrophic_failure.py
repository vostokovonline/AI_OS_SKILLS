"""
Test #4: Catastrophic Failure
=============================
Test: Can system learn to AVOID rare catastrophic events?

Scenario:
  SkillA: 100% success, slow (reward = 0.75)
  SkillB: 95% success, fast (reward ≈ 0.97) BUT...
          5% → catastrophic failure (reward = -10)

Expected:
  If reward works correctly → system should AVOID SkillB despite high success rate
"""

import asyncio
import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

ALPHA = 0.1
EPSILON = 0.1

class SkillA:
    """100% success, reliable but slow"""
    id = "slow_reliable"
    @staticmethod
    def execute():
        return {"success": True, "latency": 0.5}

class SkillB:
    """95% success, fast, but 5% catastrophic failure"""
    id = "fast_risky"
    @staticmethod
    def execute():
        if random.random() < 0.05:
            return {"success": False, "latency": 0.01, "catastrophic": True}
        return {"success": True, "latency": 0.01, "catastrophic": False}

SKILLS = [SkillA, SkillB]

def reward(result):
    """Hierarchical reward with catastrophic penalty"""
    if result.get("catastrophic"):
        return -10.0  # catastrophic failure
    if not result["success"]:
        return -2.0   # regular failure
    return 1.0 - min(result["latency"] * 0.5, 0.3)

async def test():
    from sqlalchemy import text
    from database import AsyncSessionLocal
    
    print("=" * 60)
    print("CATASTROPHIC FAILURE TEST")
    print("=" * 60)
    print("SkillA (slow_reliable): 100% success → reward ≈ 0.75")
    print("SkillB (fast_risky): 95% success, 5% catastrophic → expected ≈ 0.465")
    print("Expected: system should AVOID fast_risky despite high success")
    print("=" * 60)
    
    async with AsyncSessionLocal() as session:
        for s in SKILLS:
            await session.execute(text("""
                INSERT INTO skill_stats VALUES (:id, :name, 0, 0, 0, 0, 0, 0, 0, NOW(), NOW(), NOW(), 'test4', 0.5)
                ON CONFLICT (skill_id, task_type) DO UPDATE SET q_value=0.5
            """), {"id": s.id, "name": s.id})
        await session.commit()
    
    selections = {"slow_reliable": 0, "fast_risky": 0}
    catastrophic_count = 0
    
    for t in range(1, 51):
        async with AsyncSessionLocal() as session:
            q = {r[0]:r[1] for r in (await session.execute(text(
                "SELECT skill_id, q_value FROM skill_stats WHERE task_type='test4'"
            ))).fetchall()}
        
        if random.random() < EPSILON:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: q.get(s.id, 0.5))
        
        result = chosen.execute()
        if result.get("catastrophic"):
            catastrophic_count += 1
        
        r = reward(result)
        
        q_old = q.get(chosen.id, 0.5)
        q_new = q_old + ALPHA * (r - q_old)
        
        async with AsyncSessionLocal() as session:
            await session.execute(text("UPDATE skill_stats SET q_value=:q WHERE skill_id=:id AND task_type='test4'"),
                {"q": q_new, "id": chosen.id})
            await session.commit()
        
        selections[chosen.id] += 1
        
        if t <= 10 or t % 10 == 0:
            marker = " 💥" if result.get("catastrophic") else ""
            print(f"t={t:2d} | {chosen.id:12s} | r={r:6.2f} | Q(reliable)={q.get('slow_reliable',0.5):.3f} | Q(risky)={q.get('fast_risky',0.5):.3f}{marker}")
    
    print("\n" + "=" * 60)
    print("FINAL:")
    async with AsyncSessionLocal() as session:
        for r in (await session.execute(text("SELECT skill_id, q_value FROM skill_stats WHERE task_type='test4'"))).fetchall():
            print(f"  {r[0]}: {r[1]:.3f}")
    
    print(f"\nSelections: slow_reliable={selections['slow_reliable']}, fast_risky={selections['fast_risky']}")
    print(f"Catastrophic events: {catastrophic_count}")
    
    reliable_q = q.get('slow_reliable', 0.5)
    risky_q = q.get('fast_risky', 0.5)
    
    print("\n" + "=" * 60)
    if reliable_q > risky_q + 0.1:
        print("✅ SYSTEM LEARNS TO AVOID CATASTROPHIC RISKS")
    elif risky_q > reliable_q + 0.1:
        print("❌ BROKEN: system prefers risky skill despite catastrophic potential")
    else:
        print("≈ TOO CLOSE")
    print("=" * 60)

asyncio.run(test())