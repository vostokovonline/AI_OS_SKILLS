"""
Test #5: Noisy Latency
=====================
Test: Can system remain stable with variable latency?

Scenario:
  SkillA: 100% success, latency = 0.5 ± 0.2 (stable)
  SkillB: 80% success, latency = random(0.01, 1.0) (noisy)

Expected:
  System should remain stable, not "jitter" between preferences
"""

import asyncio
import random
import sys, os
os.chdir('/app')
sys.path.insert(0, '/app')

ALPHA = 0.1
EPSILON = 0.1

class SkillA:
    """100% success, stable latency"""
    id = "stable_good"
    @staticmethod
    def execute():
        return {"success": True, "latency": 0.5 + random.uniform(-0.2, 0.2)}

class SkillB:
    """80% success, random latency (high variance)"""
    id = "noisy_ok"
    @staticmethod
    def execute():
        return {"success": random.random() < 0.8, "latency": random.uniform(0.01, 1.0)}

SKILLS = [SkillA, SkillB]

def reward(result):
    if not result["success"]:
        return -2.0
    return 1.0 - min(result["latency"] * 0.5, 0.3)

async def test():
    from sqlalchemy import text
    from database import AsyncSessionLocal
    
    print("=" * 60)
    print("NOISY LATENCY TEST")
    print("=" * 60)
    print("SkillA (stable_good): 100% success, latency = 0.5 ± 0.2")
    print("SkillB (noisy_ok):    80% success, latency = random(0.01-1.0)")
    print("Expected: system should prefer stable skill despite noise")
    print("=" * 60)
    
    async with AsyncSessionLocal() as session:
        for s in SKILLS:
            await session.execute(text("""
                INSERT INTO skill_stats VALUES (:id, :name, 0, 0, 0, 0, 0, 0, 0, NOW(), NOW(), NOW(), 'test5', 0.5)
                ON CONFLICT (skill_id, task_type) DO UPDATE SET q_value=0.5
            """), {"id": s.id, "name": s.id})
        await session.commit()
    
    selections = {"stable_good": 0, "noisy_ok": 0}
    q_history = []
    
    for t in range(1, 101):
        async with AsyncSessionLocal() as session:
            q = {r[0]:r[1] for r in (await session.execute(text(
                "SELECT skill_id, q_value FROM skill_stats WHERE task_type='test5'"
            ))).fetchall()}
        
        if random.random() < EPSILON:
            chosen = random.choice(SKILLS)
        else:
            chosen = max(SKILLS, key=lambda s: q.get(s.id, 0.5))
        
        result = chosen.execute()
        r = reward(result)
        
        q_old = q.get(chosen.id, 0.5)
        q_new = q_old + ALPHA * (r - q_old)
        
        async with AsyncSessionLocal() as session:
            await session.execute(text("UPDATE skill_stats SET q_value=:q WHERE skill_id=:id AND task_type='test5'"),
                {"q": q_new, "id": chosen.id})
            await session.commit()
        
        selections[chosen.id] += 1
        
        if t <= 10 or t % 20 == 0:
            print(f"t={t:3d} | {chosen.id:12s} | r={r:5.2f} | Q(stable)={q.get('stable_good',0.5):.3f} | Q(noisy)={q.get('noisy_ok',0.5):.3f}")
        
        if t % 10 == 0:
            q_history.append((t, q.get('stable_good', 0.5), q.get('noisy_ok', 0.5)))
    
    print("\n" + "=" * 60)
    print("FINAL:")
    async with AsyncSessionLocal() as session:
        for r in (await session.execute(text("SELECT skill_id, q_value FROM skill_stats WHERE task_type='test5'"))).fetchall():
            print(f"  {r[0]}: {r[1]:.3f}")
    
    print(f"\nSelections: stable_good={selections['stable_good']}, noisy_ok={selections['noisy_ok']}")
    
    # Check stability: variance in Q-values over time
    stable_variance = sum((h[1] - q_history[0][1])**2 for h in q_history) / len(q_history)
    noisy_variance = sum((h[2] - q_history[0][2])**2 for h in q_history) / len(q_history)
    
    print(f"\nQ-value variance: stable={stable_variance:.4f}, noisy={noisy_variance:.4f}")
    
    stable_q = q.get('stable_good', 0.5)
    noisy_q = q.get('noisy_ok', 0.5)
    
    print("\n" + "=" * 60)
    if stable_q > noisy_q + 0.1:
        print("✅ SYSTEM PREFERS STABLE PERFORMANCE")
    elif noisy_q > stable_q + 0.1:
        print("❌ BROKEN: system prefers noisy skill")
    else:
        print("≈ CLOSE - system is unstable")
    
    if stable_variance < 0.05:
        print("✅ Q-VALUES STABLE (low variance)")
    else:
        print(f"⚠️ Q-VALUES JITTER (variance={stable_variance:.4f})")
    print("=" * 60)

asyncio.run(test())