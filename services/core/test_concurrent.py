import asyncio
import sys
sys.path.insert(0, '/app')

from database import AsyncSessionLocal
from models import Goal
from infrastructure.uow import create_uow_provider
from goal_executor_v2 import goal_executor_v2
import uuid
from datetime import datetime

async def test():
    goal_ids = []
    async with AsyncSessionLocal() as session:
        for i in range(10):
            goal = Goal(
                id=uuid.uuid4(),
                title=f'Concurrent {i}',
                description='Test',
                goal_type='achievable',
                is_atomic=True,
                domains=['testing'],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(goal)
            goal_ids.append(goal.id)
        await session.commit()

    get_uow = create_uow_provider()
    
    async def exec_one(gid):
        async with get_uow() as uow:
            return await goal_executor_v2.execute_goal_with_uow(uow, str(gid))
    
    results = await asyncio.gather(*[exec_one(gid) for gid in goal_ids])
    successful = [r for r in results if r.get('status') == 'success']
    print(f'✅ {len(successful)}/10 successful')
    return len(successful) == 10

asyncio.run(test())
