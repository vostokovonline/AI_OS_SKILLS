"""
Core API Dependencies

Common dependencies used across API endpoints.
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os

# Security
security = HTTPBearer(auto_error=False)

# Get secret key from environment
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")


async def get_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Extract and validate API key from Authorization header.
    
    For now, returns None (auth disabled for development).
    Enable authentication by implementing JWT validation here.
    """
    if credentials:
        return credentials.credentials
    return None


async def require_auth(
    api_key: Optional[str] = Depends(get_api_key)
) -> str:
    """
    Require authentication for endpoint.
    
    Raises HTTPException if not authenticated.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key


async def get_request_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host if request.client else "unknown"


# Rate limit key function
async def rate_limit_key(request: Request) -> str:
    """Generate rate limit key based on IP."""
    return await get_request_ip(request)
