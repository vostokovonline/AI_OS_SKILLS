"""
Core API Handlers
DEPRECATED: Use /api/v1/goals instead
"""

import logging
from fastapi import HTTPException
from sqlalchemy import text
from typing import Optional, Dict, Any, List

from database import engine
from infrastructure.uow import get_uow
from logging_config import get_logger

logger = get_logger(__name__)

logger.warning("DEPRECATED API: /api/goals - use /api/v1/goals")


async def handle_api_status() -> Dict[str, Any]:
    """Get system status"""
    return {"status": "ok", "message": "Use /api/v1/goals"}


async def handle_api_goals(
    limit: int = 500,
    status: Optional[str] = None,
    offset: int = 0
) -> Dict[str, Any]:
    """Deprecated - use /api/v1/goals"""
    logger.warning("Deprecated /api/goals called - use /api/v1/goals")
    
    from database import AsyncSessionLocal
    
    try:
        async with AsyncSessionLocal() as db:
            count_query = "SELECT COUNT(*) as cnt FROM goals"
            if status:
                count_query += f" WHERE status = '{status}'"
            count_result = await db.execute(text(count_query))
            total = count_result.scalar() or 0
            
            query = "SELECT * FROM goals"
            if status:
                query += f" WHERE status = '{status}'"
            query += f" ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"

            result = await db.execute(text(query))
            rows = result.fetchall()
            
            goals = []
            if rows:
                columns = result.keys()
                for row in rows:
                    goals.append(dict(zip(columns, row)))
            
            return {"goals": goals, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Error fetching goals: {e}")
        return {"goals": [], "total": 0, "limit": limit, "offset": offset}


async def handle_api_agents() -> Dict[str, Any]:
    return {"agents": [], "total": 0, "active": 0}


async def handle_api_artifacts(limit: int = 50) -> Dict[str, Any]:
    from database import AsyncSessionLocal
    
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(f"SELECT * FROM artifacts ORDER BY created_at DESC LIMIT {limit}")
            )
            rows = result.fetchall()
            
            artifacts = []
            if rows:
                columns = result.keys()
                for row in rows:
                    artifacts.append(dict(zip(columns, row)))
            
            return {"artifacts": artifacts or [], "total": len(artifacts) if artifacts else 0}
    except Exception as e:
        logger.error(f"Error fetching artifacts: {e}")
        return {"artifacts": [], "total": 0}