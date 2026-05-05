"""
Bandit Convergence Test - Isolated Experiment
=============================================
Tests whether Q-learning converges on 2 competing skills.

Skill A: 100% success, slow (0.2s)
Skill B: 70% success, fast (0.05s)

Expected: Q(A) should grow, selection shifts to A
"""

import asyncio
import random
import sys
import os

# Setup path
os.chdir('/app')
sys.path.insert(0, '/app')

# Q-learning parameters  
ALPHA = 0.1  # Learning rate
EPSILON = 0.1  # 10% exploration


# Fake Skills with controlled behavior
class SkillA:
    id = "skill_a"
    name = "SkillA"
    
    @staticmethod
    def execute():
        return {"success": True, "latency": 0.2}  # 100% success, 200ms


class SkillB:
    id = "skill_b" 
    name = "SkillB"
    
    @staticmethod
    def execute():
        return {"success": random.random() < 0.7, "latency": 0.05}  # 70% success, 50ms


SKILLS = [SkillA, SkillB]


def calculate_reward(success: bool, latency: float) -> float:
    """Simple reward: success - latency_penalty"""
    task_completion = 1.0 if success else 0.0
    latency_penalty = min(latency / 1.0, 0.5)
    return max(0, task_completion - latency_penalty)


async def run_bandit_experiment(steps: int = 50):
    from sqlalchemy import text
    from database import AsyncSessionLocal
    
    print("=" * 60)
    print("BANDIT CONVERGENCE TEST")
    print("=" * 60)
    print(f"Steps: {steps}, Alpha: {ALPHA}, Epsilon: {EPSILON}")
    print("SkillA: 100% success, 200ms | SkillB: 70% success, 50ms")
    print("=" * 60)
    
    # Initialize Q-values
    async with AsyncSessionLocal() as session:
        for skill in SKILLS:
            await session.execute(text("""
                INSERT INTO skill_stats (skill_id, skill_name, q_value, task_type, total_executions)
                VALUES (:id, :name, 0.5, 'bandit_test', 0)
                ON CONFLICT (skill_id, task_type) DO UPDATE SET q_value = 0.5
            """), {"id": skill.id, "name": skill.name})
        await session.commit()
    
    results = []
    
    for t in range(1, steps + 1):
        # Read Q-values
        async with AsyncSessionLocal() as session:
            q_result = await session.execute(text("""
                SELECT skill_id, q_value FROM skill_stats WHERE task_type = 'bandit_test'
            """))
            q_values = {row[0]: row[1] for row in q_result.fetchall()}
        
        # Epsilon-greedy selection
        if random.random() < EPSILON:
            chosen_skill = random.choice(SKILLS)
            mode = "explore"
        else:
            chosen_skill = max(SKILLS, key=lambda s: q_values.get(s.id, 0.5))
            mode = "exploit"
        
        # Execute
        result = chosen_skill.execute()
        reward = calculate_reward(result["success"], result["latency"])
        
        # Q-learning update
        current_q = q_values.get(chosen_skill.id, 0.5)
        new_q = current_q + ALPHA * (reward - current_q)
        new_q = max(0, min(1, new_q))
        
        # Write Q
        async with AsyncSessionLocal() as session:
            await session.execute(text("""
                UPDATE skill_stats SET q_value = :new_q 
                WHERE skill_id = :skill_id AND task_type = 'bandit_test'
            """), {"new_q": new_q, "skill_id": chosen_skill.id})
            await session.commit()
        
        # Log
        q_a = q_values.get("skill_a", 0.5)
        q_b = q_values.get("skill_b", 0.5)
        
        print(f"t={t:2d} | {chosen_skill.id} | {mode:6s} | r={reward:.2f} | "
              f"Q(A)={q_a:.3f}→{new_q:.3f} | Q(B)={q_b:.3f}")
        
        results.append({"t": t, "chosen": chosen_skill.id, "reward": reward, 
                       "q_a": q_a, "q_b": q_b, "new_q": new_q})
    
    # Final stats
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    async with AsyncSessionLocal() as session:
        final_q = await session.execute(text("""
            SELECT skill_id, q_value FROM skill_stats WHERE task_type = 'bandit_test'
        """))
        for row in final_q.fetchall():
            print(f"  {row[0]}: Q = {row[1]:.3f}")
    
    chosen_a = sum(1 for r in results if r["chosen"] == "skill_a")
    chosen_b = sum(1 for r in results if r["chosen"] == "skill_b")
    
    print(f"\nSelection: A={chosen_a} ({chosen_a*100//steps}%), B={chosen_b} ({chosen_b*100//steps}%)")
    
    final_q_a = results[-1]["q_a"]
    final_q_b = results[-1]["q_b"]
    
    if final_q_a > final_q_b + 0.1:
        print("\n✅ CONVERGENCE: Q(A) > Q(B)")
    elif abs(final_q_a - final_q_b) < 0.1:
        print("\n⚠️ NO CONVERGENCE")
    else:
        print("\n❌ REVERSE")


if __name__ == "__main__":
    asyncio.run(run_bandit_experiment(50))