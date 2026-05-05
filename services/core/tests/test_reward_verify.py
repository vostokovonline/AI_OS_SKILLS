"""
Test #2: Reward Function Verification
=====================================
Skill A: 100% success, SLOW (0.5s) → reward = 1.0 - 0.5 = 0.5
Skill B: 80% success, FAST (0.01s) → reward ≈ 0.8 - 0.01 = 0.79

Question: Which will system choose?
If B wins → system optimizes for speed, not quality
"""

import asyncio
import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

ALPHA = 0.1
EPSILON = 0.1

class SkillA:
    id = "slow_good"
    @staticmethod
    def execute():
        return {"success": True, "latency": 0.5}  # 100%, but slow

class SkillB:
    id = "fast_ok"
    @staticmethod
    def execute():
        return {"success": random.random() < 0.8, "latency": 0.01}  # 80%, fast

SKILLS = [SkillA, SkillB]

def reward(success, latency):
    return max(0, (1.0 if success else 0.0) - latency)

async def test():
    from sqlalchemy import text
    from database import AsyncSessionLocal
    
    print("=" * 60)
    print("REWARD FUNCTION TEST")
    print("=" * 60)
    print("SlowGood: 100% success, 500ms → reward ≈ 0.5")
    print("FastOk: 80% success, 10ms → reward ≈ 0.79")
    print("=" * 60)
    
    # Reset
    async with AsyncSessionLocal() as session:
        for s in SKILLS:
            await session.execute(text("""
                INSERT INTO skill_stats VALUES (:id, :name, 0, 0, 0, 0, 0, 0, 0, NOW(), NOW(), NOW(), 'test2', 0.5)
                ON CONFLICT (skill_id, task_type) DO UPDATE SET q_value=0.5
            """), {"id": s.id, "name": s.id})
        await session.commit()
    
    for t in range(1, 31):
        async with AsyncSessionLocal() as session:
            q = {r[0]:r[1] for r in (await session.execute(text(
                "SELECT skill_id, q_value FROM skill_stats WHERE task_type='test2'"
            ))).fetchall()}
        
        chosen = random.choice(SKILLS) if random.random() < EPSILON else max(SKILLS, key=lambda s: q.get(s.id, 0.5))
        result = chosen.execute()
        r = reward(result["success"], result["latency"])
        
        q_old = q.get(chosen.id, 0.5)
        q_new = q_old + ALPHA * (r - q_old)
        
        async with AsyncSessionLocal() as session:
            await session.execute(text("UPDATE skill_stats SET q_value=:q WHERE skill_id=:id AND task_type='test2'"),
                {"q": q_new, "id": chosen.id})
            await session.commit()
        
        print(f"t={t:2d} | {chosen.id:10s} | r={r:.2f} | Q(slow)={q.get('slow_good',0.5):.3f} | Q(fast)={q.get('fast_ok',0.5):.3f}")
    
    print("\nFINAL:")
    async with AsyncSessionLocal() as session:
        for r in (await session.execute(text("SELECT skill_id, q_value FROM skill_stats WHERE task_type='test2'"))).fetchall():
            print(f"  {r[0]}: {r[1]:.3f}")
    
    print("\n" + "=" * 60)
    slow_q = q.get('slow_good', 0.5)
    fast_q = q.get('fast_ok', 0.5)
    if fast_q > slow_q + 0.1:
        print("⚠️ SYSTEM OPTIMIZES FOR SPEED (reward=0.79 > 0.5)")
    elif slow_q > fast_q + 0.1:
        print("✅ SYSTEM PREFERS RELIABILITY")
    else:
        print("≈ CLOSE")

asyncio.run(test())