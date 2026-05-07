#!/bin/bash
echo "🧠 FIXING MISSING COGNITION MODULE..."

# 1. Создаем папку (если нет)
mkdir -p services/core/cognition

# 2. Создаем пустой __init__.py (чтобы Python видел это как пакет)
touch services/core/cognition/__init__.py

# 3. Создаем drive.py (Логика внутреннего драйва)
cat << 'EOF' > services/core/cognition/drive.py
import uuid
from sqlalchemy import select
from database import AsyncSessionLocal
from models import Goal, Thought

async def generate_internal_drive():
    """
    Cognitive Loop: Generates thoughts based on goals without user input.
    """
    async with AsyncSessionLocal() as db:
        # 1. Check Active Goals
        try:
            stmt = select(Goal).where(Goal.status == "active")
            result = await db.execute(stmt)
            goals = result.scalars().all()
        except Exception as e:
            return f"Drive Error: {e}"
        
        if not goals:
            return "No active goals to drive."
            
        # 2. Pick a goal to focus on (Simplified: Pick first)
        focus_goal = goals[0]
        
        # 3. Generate a 'Curiosity' or 'Action' thought
        thought_content = f"INTERNAL DRIVE: I need to advance goal '{focus_goal.title}'. What is the next logical step?"
        
        # 4. Inject into Stream
        thought = Thought(content=thought_content, source="drive_engine", status="pending")
        db.add(thought)
        await db.commit()
        
        return f"Generated thought for {focus_goal.title}"
EOF

echo "✅ Module restored. Rebuilding core..."
docker compose build core core_worker
docker compose up -d core core_worker

echo "⏳ Waiting for startup..."
sleep 5
docker logs --tail 20 ns_core
