#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, '/app')

async def direct_test():
    from database import AsyncSessionLocal
    from goal_executor_v2 import GoalExecutorV2
    from infrastructure.uow import UnitOfWork
    from models import Goal
    from sqlalchemy import text
    
    # Create fresh goal
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            INSERT INTO goals (id, title, description, goal_type, status, is_atomic, created_at)
            VALUES (gen_random_uuid(), 'Direct write test', 'Write a simple test file', 'achievable', 'active', true, now())
            RETURNING id
        """))
        goal_id = result.fetchone()[0]
        print(f"Created goal: {goal_id}")
    
    # Execute directly
    executor = GoalExecutorV2()
    
    async with UnitOfWork() as uow:
        goal = await uow.session.get(Goal, goal_id)
        print(f"Got goal: {goal.title}")
        
        # Force pipeline mode by skipping planner
        result = await executor._execute_pipeline(
            uow=uow,
            goal=goal,
            skills=["core.write_file"],
            goal_snapshot={"id": str(goal.id), "title": goal.title, "description": goal.description},
            trace={}
        )
        print(f"Result: {result.get('status')}")
    
    # Check telemetry
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT skill_id, task_type FROM skill_telemetry 
            WHERE goal_id = :goal_id
        """), {"goal_id": str(goal_id)})
        row = result.fetchone()
        
    if row:
        print(f"✅ Telemetry: skill={row[0]}, task_type={row[1]}")
    else:
        print("❌ No telemetry")

asyncio.run(direct_test())