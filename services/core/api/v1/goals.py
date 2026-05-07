"""
Goals Read API v1 - Canonical endpoint with cursor pagination

Replaces:
- /goals/list (main.py)
- /goals/list (api/endpoints)
- /api/goals (dashboard compatibility)

Contract: services/core/api/contracts/goals_read_api.py
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, Any, List
from datetime import datetime
from database import AsyncSessionLocal
from sqlalchemy import text, and_

router = APIRouter(prefix="/api/v1", tags=["Goals v1"])


@router.get("/goals")
async def get_goals_v1(
    cursor: Optional[str] = Query(None, description="Pagination cursor (created_at_id format)"),
    limit: int = Query(50, ge=1, le=100, description="Max items per request (max 100)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    goal_type: Optional[str] = Query(None, description="Filter by goal type"),
    is_atomic: Optional[bool] = Query(None, description="Filter by atomic flag"),
    include_archived: bool = Query(False, description="Include archived goals (default: NO)"),
    created_after: Optional[datetime] = Query(None, description="Created after this date"),
    created_before: Optional[datetime] = Query(None, description="Created before this date"),
    order_by: str = Query("created_at", description="Sort by: created_at, updated_at, title"),
    order_dir: str = Query("desc", description="Sort direction: asc, desc")
) -> Dict[str, Any]:
    """
    Canonical goals read endpoint with cursor pagination.
    
    Default behavior:
    - Excludes archived goals (use include_archived=true to include)
    - Returns pending, active, done goals by default
    - Max 100 items per request to prevent UI overload
    """
    
    # Validate order parameters
    valid_order_by = ["created_at", "updated_at", "title"]
    if order_by not in valid_order_by:
        order_by = "created_at"
    
    valid_order_dir = ["asc", "desc"]
    if order_dir not in valid_order_dir:
        order_dir = "desc"
    
    # Build WHERE clause
    conditions = []
    params = {}
    
    # IMPORTANT: Exclude archived by default
    if not include_archived:
        conditions.append("status != 'archived'")
    
    if status:
        conditions.append("status = :status")
        params["status"] = status
    
    if goal_type:
        conditions.append("goal_type = :goal_type")
        params["goal_type"] = goal_type
    
    if is_atomic is not None:
        conditions.append("is_atomic = :is_atomic")
        params["is_atomic"] = is_atomic
    
    if created_after:
        conditions.append("created_at > :created_after")
        params["created_after"] = created_after.isoformat()
    
    if created_before:
        conditions.append("created_at < :created_before")
        params["created_before"] = created_before.isoformat()
    
    # Handle cursor (format: "created_at_id")
    cursor_condition = ""
    if cursor:
        try:
            cursor_ts, cursor_id = cursor.rsplit("_", 1)
            cursor_condition = f"AND (created_at < :cursor_ts OR (created_at = :cursor_ts AND id < :cursor_id))"
            params["cursor_ts"] = cursor_ts
            params["cursor_id"] = cursor_id
        except ValueError:
            pass  # Invalid cursor format, ignore
    
    # Build ORDER BY (use id as tiebreaker for consistency)
    order_sql = f"{order_by} {order_dir}, id {order_dir}"
    
    # Build LIMIT (add 1 to check if there are more)
    fetch_limit = limit + 1
    
    async with AsyncSessionLocal() as db:
        # Get total count (without cursor)
        count_query = "SELECT COUNT(*) as cnt FROM goals"
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions)
        
        try:
            count_result = await db.execute(text(count_query), params)
            total_count = count_result.scalar() or 0
        except Exception:
            total_count = 0
        
        # Get goals
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        if cursor_condition:
            where_clause += cursor_condition
        
        query = f"""
            SELECT id, parent_id, title, description, status, progress, 
                   goal_type, depth_level, is_atomic, created_at, updated_at
            FROM goals
            WHERE {where_clause}
            ORDER BY {order_sql}
            LIMIT :limit
        """
        params["limit"] = fetch_limit
        
        result = await db.execute(text(query), params)
        rows = result.fetchall()
        
        # Check if there are more
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]  # Remove the extra row
        
        # Convert to dict
        goals = []
        for row in rows:
            goals.append({
                "id": str(row[0]),
                "parent_id": str(row[1]) if row[1] else None,
                "title": row[2],
                "description": row[3],
                "status": row[4],
                "progress": row[5] or 0.0,
                "goal_type": row[6],
                "depth_level": row[7],
                "is_atomic": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
                "updated_at": row[10].isoformat() if row[10] else None
            })
        
        # Generate next cursor
        next_cursor = None
        if has_more and goals:
            last_goal = goals[-1]
            next_cursor = f"{last_goal['created_at']}_{last_goal['id']}"
        
        return {
            "goals": goals,
            "pagination": {
                "next_cursor": next_cursor,
                "has_more": has_more,
                "total_count": total_count
            },
            "filters_applied": {
                "status": status,
                "goal_type": goal_type,
                "is_atomic": is_atomic,
                "include_archived": include_archived,
                "created_after": created_after.isoformat() if created_after else None,
                "created_before": created_before.isoformat() if created_before else None
            }
        }


@router.get("/goals/count")
async def get_goals_count(
    status: Optional[str] = Query(None, description="Filter by status"),
    include_archived: bool = Query(False, description="Include archived")
) -> Dict[str, Any]:
    """Get goals count by status"""
    
    conditions = []
    if not include_archived:
        conditions.append("status != 'archived'")
    if status:
        conditions.append("status = :status")
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    async with AsyncSessionLocal() as db:
        query = f"""
            SELECT status, COUNT(*) as cnt 
            FROM goals 
            WHERE {where_clause}
            GROUP BY status
            ORDER BY cnt DESC
        """
        result = await db.execute(text(query), {"status": status} if status else {})
        
        by_status = {}
        total = 0
        for row in result.fetchall():
            by_status[row[0]] = row[1]
            total += row[1]
        
        return {
            "total": total,
            "by_status": by_status
        }