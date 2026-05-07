import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Подключение к локалхосту (так как порты проброшены)
DB_URL = "postgresql+asyncpg://ns_admin:ns_secure_pass@localhost:5432/ns_core_db"

async def inject():
    try:
        print("⏳ Connecting to DB...")
        engine = create_async_engine(DB_URL)
        
        async with engine.begin() as conn:
            # 1. Создаем Главную Цель
            root_id = uuid.uuid4()
            print(f"📝 Injecting Root Goal: {root_id}")
            
            await conn.execute(text("""
                INSERT INTO goals (id, title, description, status, progress, created_at)
                VALUES (:id, 'Ручной Тест (Admin)', 'Проверка связи базы и дашборда', 'active', 0.5, NOW())
            """), {"id": root_id})
            
            # 2. Создаем Подзадачу
            await conn.execute(text("""
                INSERT INTO goals (id, parent_id, title, description, status, progress, created_at)
                VALUES (:id, :pid, 'Задача 1', 'Это создано скриптом напрямую', 'pending', 0.0, NOW())
            """), {"id": uuid.uuid4(), "pid": root_id})
            
        print("✅ SUCCESS! Goal injected. Check Dashboard now.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(inject())
