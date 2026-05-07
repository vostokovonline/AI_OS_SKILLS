#!/usr/bin/env python3
"""
Simple learning test - submit to Celery
"""
import asyncio
import sys
sys.path.insert(0, '/app')

async def test_learning():
    from database import AsyncSessionLocal
    from sqlalchemy import text
    
    # Get first pending goal
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT id, title FROM goals 
            WHERE status = 'active' AND is_atomic = true
            ORDER BY created_at DESC LIMIT 1
        """))
        row = result.fetchone()
        
    if not row:
        print("No active goals found")
        return
    
    goal_id = str(row[0])
    print(f"Submitting goal: {row[1]} ({goal_id})")
    
    # Submit to Celery
    from tasks import execute_goal_task
    task = execute_goal_task.delay(goal_id, None)
    print(f"Task submitted: {task.id}")
    
    # Wait for completion
    print("Waiting for execution...")
    await asyncio.sleep(45)
    
    # Check telemetry
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT skill_id, task_type, goal_id FROM skill_telemetry 
            WHERE goal_id = :goal_id
        """), {"goal_id": goal_id})
        row = result.fetchone()
        
    if row:
        print(f"✅ Telemetry: skill={row[0]}, task_type={row[1]}")
    else:
        print("❌ No telemetry recorded")

if __name__ == "__main__":
    asyncio.run(test_learning())