"""FastAPI dependency injection functions for authentication."""
import time
from fastapi import Header, HTTPException, Depends, Cookie
from typing import Optional, Dict, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.core.auth import verify_player_token
from app.core.database_async import get_async_db


# PERF-FIX: Short TTL cache for user validation to reduce DB queries.
# Maps user_id -> (is_active, cached_at). Entries expire after _USER_CACHE_TTL seconds.
_USER_CACHE_TTL = 30  # seconds
_user_cache: Dict[str, Tuple[bool, float]] = {}
_USER_CACHE_MAX_SIZE = 1000


def _check_user_cache(user_id: str) -> Optional[bool]:
    """Return cached is_active status if fresh, else None."""
    entry = _user_cache.get(user_id)
    if entry and (time.time() - entry[1]) < _USER_CACHE_TTL:
        return entry[0]
    return None


def _set_user_cache(user_id: str, is_active: bool) -> None:
    """Cache user active status. Evict oldest entries if over capacity."""
    if len(_user_cache) >= _USER_CACHE_MAX_SIZE:
        # Evict ~10% oldest entries
        sorted_keys = sorted(_user_cache, key=lambda k: _user_cache[k][1])
        for k in sorted_keys[:_USER_CACHE_MAX_SIZE // 10]:
            _user_cache.pop(k, None)
    _user_cache[user_id] = (is_active, time.time())


def _extract_bearer_token(authorization: str) -> Optional[str]:
    """Extract JWT token from 'Authorization: Bearer <token>' header.

    Returns:
        Token string if valid format, None otherwise.
    """
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def _verify_token_safe(token: str) -> Optional[Dict]:
    """Verify JWT token without raising exceptions.

    Returns:
        Decoded payload if valid, None otherwise.
    """
    try:
        return verify_player_token(token)
    except Exception:
        return None


async def get_current_player(
    authorization: Optional[str] = Header(None),
    user_access_token: Optional[str] = Cookie(None)
) -> Dict:
    """
    Dependency to get current authenticated player from JWT token.

    Security: Supports both Authorization header and HttpOnly cookie.
    Authorization header takes precedence (for room/game tokens).

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        user_access_token: HttpOnly cookie containing JWT token

    Returns:
        Dict containing player info: {player_id, room_id, is_admin, ...}

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    # Try Authorization header first (room/game tokens), then cookie (user sessions)
    token = None
    if authorization:
        # Extract token from "Bearer <token>" format
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header format. Expected: Bearer <token>",
                headers={"WWW-Authenticate": "Bearer"}
            )
    elif user_access_token:
        token = user_access_token

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = verify_player_token(token)
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(
    authorization: Optional[str] = Header(None),
    user_access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_async_db)
) -> Dict:
    """
    Dependency to get current authenticated user from JWT token.
    Requires user_id in token payload (user must be logged in).

    Security: Supports both Authorization header and HttpOnly cookie.
    - If Authorization header contains a user token (with user_id), use it.
    - If Authorization header contains a room/player token (no user_id), fall back to cookie.
    - Detects conflicts when both sources have different user_ids.
    Validates user exists and is active in real-time to enable effective token revocation.

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        user_access_token: HttpOnly cookie containing JWT token
        db: Database session

    Returns:
        Dict containing user info: {user_id, player_id, token_type, ...}

    Raises:
        HTTPException: 401 if token is missing/invalid or no user_id
                      403 if user account is disabled
    """
    header_payload: Optional[Dict] = None
    cookie_payload: Optional[Dict] = None

    # Try to parse Authorization header
    if authorization:
        header_token = _extract_bearer_token(authorization)
        if header_token:
            header_payload = _verify_token_safe(header_token)

    # Try to parse Cookie
    if user_access_token:
        cookie_payload = _verify_token_safe(user_access_token)

    # Determine which payload to use
    header_user_id = header_payload.get("user_id") if header_payload else None
    cookie_user_id = cookie_payload.get("user_id") if cookie_payload else None

    payload: Optional[Dict] = None

    if header_user_id:
        # Authorization header has user token
        # Check for conflict with cookie
        if cookie_user_id and cookie_user_id != header_user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication conflict: mismatched user credentials.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        payload = header_payload
    elif cookie_user_id:
        # Authorization header missing or has room token (no user_id)
        # Fall back to cookie authentication
        payload = cookie_payload
    else:
        # Neither source has valid user token
        raise HTTPException(
            status_code=401,
            detail="User authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Verify user_id exists (should be guaranteed by logic above, but double-check)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # PERF-FIX: Check cache before hitting DB
    cached_active = _check_user_cache(user_id)
    if cached_active is not None:
        if not cached_active:
            raise HTTPException(
                status_code=403,
                detail="User account is disabled. Please contact support."
            )
        return payload

    # Real-time user validation (cache miss)
    from app.models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found. Token may be invalid.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    _set_user_cache(user_id, user.is_active)

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is disabled. Please contact support."
        )

    return payload


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    user_access_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_async_db)
) -> Optional[Dict]:
    """
    Dependency to get current user if authenticated, None otherwise.
    Used for endpoints that work for both logged-in and anonymous users.

    Security: Supports both Authorization header and HttpOnly cookie.
    Validates user exists and is active in database.

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        user_access_token: HttpOnly cookie containing JWT token
        db: Database session

    Returns:
        Dict containing user info if authenticated, None otherwise
    """
    # Try cookie first, then Authorization header
    token = None
    if user_access_token:
        token = user_access_token
    elif authorization:
        # Strict Bearer token parsing
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            return None

    if not token:
        return None

    try:
        payload = verify_player_token(token)
    except Exception:
        return None

    user_id = payload.get("user_id")
    if not user_id:
        return None

    # PERF-FIX: Check cache before hitting DB
    cached_active = _check_user_cache(user_id)
    if cached_active is not None:
        return payload if cached_active else None

    # Validate user exists and is active (cache miss)
    from app.models.user import User
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        if user:
            _set_user_cache(user_id, False)
        return None

    _set_user_cache(user_id, True)
    return payload


async def verify_admin(
    authorization: Optional[str] = Header(None),
) -> Dict:
    """
    Dependency to verify admin privileges (JWT admin token).

    Unified admin verification used by all admin endpoints.

    Args:
        authorization: Authorization header (format: "Bearer <token>")

    Returns:
        Dict containing admin info

    Raises:
        HTTPException: 403 if token is missing/invalid or not admin
    """
    detail = "Admin access required. Provide JWT admin token."
    if not authorization:
        raise HTTPException(status_code=403, detail=detail)

    try:
        player = await get_current_player(authorization, user_access_token=None)
    except HTTPException:
        raise HTTPException(status_code=403, detail=detail)

    if not player.get("is_admin", False):
        raise HTTPException(status_code=403, detail=detail)

    return player
