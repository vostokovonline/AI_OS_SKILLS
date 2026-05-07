#!/usr/bin/env python3
"""
A/B Test Runner - Retry Effectiveness

CRITICAL RULE:
  delta < 5%  → DELETE retry
  delta >= 8% → KEEP retry (freeze)
  5-8%        → KEEP simple
"""
import asyncio
import sys
sys.path.insert(0, '/app')

import random
import uuid
from datetime import datetime

SEED = int(datetime.now().timestamp())
random.seed(SEED)

BATCH_SIZE = 20
NUM_BATCHES = 15  # 300 total goals

results = {
    "A": {"total": 0, "completed": 0, "blocked": 0, "confidence_sum": 0.0},
    "B": {"total": 0, "completed": 0, "blocked": 0, "confidence_sum": 0.0}
}
assignments = []


async def run_ab_test():
    from database import AsyncSessionLocal
    from sqlalchemy import text
    from goal_executor_v2 import GoalExecutorV2
    
    print(f"\n{'='*60}")
    print("A/B TEST: RETRY EFFECTIVENESS")
    print(f"{'='*60}")
    print(f"SEED: {SEED}")
    print(f"Total: {BATCH_SIZE * NUM_BATCHES} goals")
    print(f"Rule: delta < 5% → DELETE, delta >= 8% → KEEP")
    print(f"{'='*60}\n")
    
    executor = GoalExecutorV2()
    
    goal_num = 0
    for batch in range(NUM_BATCHES):
        print(f"\n--- Batch {batch+1}/{NUM_BATCHES} ---")
        
        for i in range(BATCH_SIZE):
            goal_num += 1
            goal_id = str(uuid.uuid4())
            
            # Random A/B assignment
            is_b = random.random() >= 0.5
            group = "B" if is_b else "A"
            max_attempts = 2 if is_b else 1
            
            assignments.append({
                "goal_id": goal_id,
                "group": group,
                "max_attempts": max_attempts
            })
            
            # Create goal in DB
            async with AsyncSessionLocal() as session:
                await session.execute(text(f'''
                    INSERT INTO goals (
                        id, title, description, goal_type, is_atomic,
                        status, progress, created_at, depth_level
                    )
                    VALUES (
                        '{goal_id}', 
                        'AB Test {goal_num}', 
                        'Retry effectiveness validation', 
                        'achievable', 
                        true, 
                        'active', 
                        0.0, 
                        NOW(), 
                        3
                    )
                '''))
                await session.commit()
            
            # Execute with group-specific retry limit
            try:
                result = await executor.execute_goal(
                    goal_id,
                    max_attempts_override=max_attempts
                )
                
                status = result.get("status", "unknown")
                confidence = result.get("final_confidence", 0.0)
                
                results[group]["total"] += 1
                if status == "completed":
                    results[group]["completed"] += 1
                    results[group]["confidence_sum"] += confidence
                elif status in ("blocked", "failed"):
                    results[group]["blocked"] += 1
                
                print(f"  {goal_num:3d}. {goal_id[:8]} → {group}({max_attempts}) → {status[:10]:10s} conf={confidence:.2f}")
                
            except Exception as e:
                results[group]["total"] += 1
                results[group]["blocked"] += 1
                print(f"  {goal_num:3d}. {goal_id[:8]} → {group}({max_attempts}) → ERROR: {str(e)[:30]}")
            
            await asyncio.sleep(1)
        
        print(f"  Batch complete. Sleeping 10s...")
        await asyncio.sleep(10)
    
    # Final summary
    print(f"\n{'='*60}")
    print("A/B TEST RESULTS")
    print(f"{'='*60}")
    
    for group in ["A", "B"]:
        r = results[group]
        rate = r["completed"] / r["total"] * 100 if r["total"] > 0 else 0
        avg_conf = r["confidence_sum"] / r["completed"] if r["completed"] > 0 else 0
        print(f"\nGroup {group}:")
        print(f"  Total:      {r['total']}")
        print(f"  Completed:  {r['completed']}")
        print(f"  Blocked:    {r['blocked']}")
        print(f"  Rate:       {rate:.1f}%")
        print(f"  Avg Conf:   {avg_conf:.2f}")
    
    rate_a = results["A"]["completed"] / results["A"]["total"] if results["A"]["total"] > 0 else 0
    rate_b = results["B"]["completed"] / results["B"]["total"] if results["B"]["total"] > 0 else 0
    delta = (rate_b - rate_a) * 100
    
    print(f"\n{'='*60}")
    print(f"DELTA: {delta:+.1f}%")
    print(f"  Group A (no retry):  {rate_a*100:.1f}%")
    print(f"  Group B (retry):     {rate_b*100:.1f}%")
    
    if delta >= 8:
        print("\n✅ DECISION: KEEP retry - freeze implementation")
    elif delta >= 5:
        print("\n📊 DECISION: KEEP retry - NO enhancements")
    else:
        print("\n❌ DECISION: DELETE retry layer")
    
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_ab_test())
