"""
Core API Routes

Dashboard compatibility layer - Universal API endpoints.
"""

from fastapi import APIRouter, Query

from .handlers import (
    handle_api_status,
    handle_api_goals,
    handle_api_agents,
    handle_api_artifacts,
)

# Create router with prefix
router = APIRouter(prefix="/api", tags=["dashboard-compatibility"])


@router.get("/status")
async def api_status():
    """
    Universal status endpoint for dashboards.
    
    Returns:
        System health, database status, and goal statistics
    """
    return await handle_api_status()


@router.get("/goals")
async def api_goals(
    limit: int = Query(default=500, ge=1, le=1000, description="Max goals to return"),
    status: str = Query(default=None, description="Filter by status"),
    offset: int = Query(default=0, ge=0, description="Pagination offset")
):
    """
    Get goals list for dashboards.
    
    Args:
        limit: Maximum number of goals to return (1-1000)
        status: Filter by status (optional)
        offset: Pagination offset
    
    Returns:
        Goals list with total count
    """
    return await handle_api_goals(limit=limit, status=status, offset=offset)


@router.get("/agents")
async def api_agents():
    """
    Get agents status for dashboards.
    
    Returns:
        Agent status (currently empty - not yet implemented)
    """
    return await handle_api_agents()


@router.get("/artifacts")
async def api_artifacts(
    limit: int = Query(default=50, ge=1, le=1000, description="Max artifacts to return")
):
    """
    Get artifacts list for dashboards.
    
    Args:
        limit: Maximum number of artifacts to return (1-1000)
    
    Returns:
        Artifacts list with total count
    """
    return await handle_api_artifacts(limit=limit)
