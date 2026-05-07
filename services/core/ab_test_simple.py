#!/usr/bin/env python3
"""
A/B Test: Retry Effectiveness

CRITICAL RULE:
  delta < 5%  → DELETE retry
  delta >= 8% → KEEP retry (freeze implementation)
  5-8%        → KEEP simple, NO enhancements

Groups:
  A: max_attempts = 1
  B: max_attempts = 2
"""
import asyncio
import sys
sys.path.insert(0, '/app')

import random
import uuid
from datetime import datetime

SEED = int(datetime.now().timestamp())
random.seed(SEED)

TOTAL_GOALS = 300
BATCH_SIZE = 10
BATCH_DELAY = 30

results = {
    "A": {"total": 0, "completed": 0, "blocked": 0, "confidence_sum": 0.0},
    "B": {"total": 0, "completed": 0, "blocked": 0, "confidence_sum": 0.0}
}
assignments = []


async def create_goal(goal_num: int):
    """Create test goal with A/B assignment."""
    from database import AsyncSessionLocal
    from sqlalchemy import text
    
    goal_id = str(uuid.uuid4())
    
    # Random assignment
    is_b = random.random() >= 0.5
    group = "B" if is_b else "A"
    max_attempts = 2 if is_b else 1
    
    assignments.append({
        "goal_id": goal_id,
        "group": group,
        "max_attempts": max_attempts
    })
    
    async with AsyncSessionLocal() as session:
        await session.execute(text(f'''
            INSERT INTO goals (
                id, title, description, goal_type, is_atomic,
                status, progress, created_at, depth_level
            )
            VALUES (
                '{goal_id}',
                'AB Test {goal_num}',
                'Retry effectiveness test',
                'achievable',
                true,
                'active',
                0.0,
                NOW(),
                3
            )
        '''))
        await session.commit()
    
    return goal_id, group, max_attempts


async def execute_with_retry_limit(goal_id: str, max_attempts: int):
    """Execute goal with specific retry limit."""
    from goal_executor_v2 import GoalExecutorV2
    
    # Temporarily override MAX_ATTEMPTS
    import goal_executor_v2
    original = getattr(goal_executor_v2, 'MAX_ATTEMPTS', 2)
    goal_executor_v2.MAX_ATTEMPTS = max_attempts
    
    try:
        executor = GoalExecutorV2()
        result = await executor.execute_goal(goal_id)
        return result
    finally:
        goal_executor_v2.MAX_ATTEMPTS = original


async def run_batch(batch_num: int):
    """Run one batch of goals."""
    print(f"\n{'='*50}")
    print(f"BATCH {batch_num}")
    print(f"{'='*50}")
    
    for i in range(BATCH_SIZE):
        goal_num = (batch_num - 1) * BATCH_SIZE + i
        goal_id, group, max_attempts = await create_goal(goal_num)
        
        print(f"  {goal_num+1}. {goal_id[:8]} → Group {group} (max={max_attempts})")
        
        try:
            result = await execute_with_retry_limit(goal_id, max_attempts)
            
            status = result.get("status", "unknown")
            confidence = result.get("final_confidence", 0.0)
            
            results[group]["total"] += 1
            if status == "completed":
                results[group]["completed"] += 1
                results[group]["confidence_sum"] += confidence
            elif status in ("blocked", "failed"):
                results[group]["blocked"] += 1
            
            print(f"     → {status} (conf={confidence:.2f})")
            
        except Exception as e:
            results[group]["total"] += 1
            results[group]["blocked"] += 1
            print(f"     → ERROR: {str(e)[:50]}")
        
        await asyncio.sleep(2)
    
    print(f"\nBatch {batch_num} done. Sleeping {BATCH_DELAY}s...")
    await asyncio.sleep(BATCH_DELAY)


def compute_delta():
    """Compute completion rate delta."""
    rate_a = results["A"]["completed"] / results["A"]["total"] if results["A"]["total"] > 0 else 0
    rate_b = results["B"]["completed"] / results["B"]["total"] if results["B"]["total"] > 0 else 0
    
    return rate_b - rate_a, rate_a, rate_b


def print_summary():
    """Print final results."""
    delta, rate_a, rate_b = compute_delta()
    
    print(f"\n{'='*60}")
    print("A/B TEST RESULTS")
    print(f"{'='*60}")
    print(f"Seed: {SEED}")
    print(f"Total goals: {len(assignments)}")
    print()
    
    for group in ["A", "B"]:
        r = results[group]
        avg_conf = r["confidence_sum"] / r["completed"] if r["completed"] > 0 else 0
        print(f"Group {group}:")
        print(f"  Total:      {r['total']}")
        print(f"  Completed:  {r['completed']}")
        print(f"  Blocked:    {r['blocked']}")
        print(f"  Rate:       {r['completed']/r['total']*100:.1f}%" if r['total'] > 0 else "  Rate:       N/A")
        print(f"  Avg Conf:   {avg_conf:.2f}")
        print()
    
    print(f"DELTA: {delta*100:.2f}%")
    print(f"  Group A (no retry):  {rate_a*100:.1f}%")
    print(f"  Group B (retry):     {rate_b*100:.1f}%")
    print()
    
    if delta >= 0.08:
        print("✅ DECISION: KEEP retry - freeze implementation")
    elif delta >= 0.05:
        print("📊 DECISION: KEEP retry - NO enhancements")
    else:
        print("❌ DECISION: DELETE retry layer")
    
    print(f"{'='*60}\n")


async def main():
    print(f"\n{'='*60}")
    print("A/B TEST: RETRY EFFECTIVENESS")
    print(f"{'='*60}")
    print(f"Seed: {SEED}")
    print(f"Total: {TOTAL_GOALS} goals")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Decision rule: delta < 5% → DELETE, delta >= 8% → KEEP")
    print(f"{'='*60}\n")
    
    batches = TOTAL_GOALS // BATCH_SIZE
    
    for batch_num in range(1, batches + 1):
        await run_batch(batch_num)
    
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
