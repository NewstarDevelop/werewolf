"""FastAPI dependency injection functions for authentication."""
from fastapi import Header, HTTPException, Depends, Cookie
from typing import Optional, Dict
from sqlalchemy.orm import Session
import jwt

from app.core.auth import verify_player_token
from app.core.database import get_db


async def get_current_player(
    authorization: Optional[str] = Header(None),
    user_access_token: Optional[str] = Cookie(None)
) -> Dict:
    """
    Dependency to get current authenticated player from JWT token.

    Security: Supports both Authorization header and HttpOnly cookie.
    Cookie takes precedence for user tokens (OAuth flow).

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        user_access_token: HttpOnly cookie containing JWT token

    Returns:
        Dict containing player info: {player_id, room_id, is_admin, ...}

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    # Try cookie first (OAuth flow), then Authorization header (legacy/game tokens)
    token = None
    if user_access_token:
        token = user_access_token
    elif authorization:
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
    db: Session = Depends(get_db)
) -> Dict:
    """
    Dependency to get current authenticated user from JWT token.
    Requires user_id in token payload (user must be logged in).

    Security: Validates user exists and is active in real-time
    to enable effective token revocation.

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        db: Database session

    Returns:
        Dict containing user info: {user_id, player_id, token_type, ...}

    Raises:
        HTTPException: 401 if token is missing/invalid or no user_id
                      403 if user account is disabled
    """
    payload = await get_current_player(authorization)

    # Verify user_id exists (distinguishes user tokens from anonymous player tokens)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="User authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Real-time user validation
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found. Token may be invalid.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is disabled. Please contact support."
        )

    return payload


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    user_access_token: Optional[str] = Cookie(None)
) -> Optional[Dict]:
    """
    Dependency to get current user if authenticated, None otherwise.
    Used for endpoints that work for both logged-in and anonymous users.

    Security: Supports both Authorization header and HttpOnly cookie.

    Args:
        authorization: Authorization header (format: "Bearer <token>")
        user_access_token: HttpOnly cookie containing JWT token

    Returns:
        Dict containing user info if authenticated, None otherwise
    """
    # Try cookie first, then Authorization header
    token = None
    if user_access_token:
        token = user_access_token
    elif authorization:
        token = authorization.replace("Bearer ", "").strip()

    if not token:
        return None

    try:
        payload = verify_player_token(token)
        return payload if payload.get("user_id") else None
    except Exception:
        return None


async def get_admin(
    authorization: Optional[str] = Header(None)
) -> Dict:
    """
    Dependency to verify admin privileges.

    Args:
        authorization: Authorization header (format: "Bearer <token>")

    Returns:
        Dict containing admin info

    Raises:
        HTTPException: 401 if token is missing/invalid, 403 if not admin
    """
    # First verify it's a valid player token
    player = await get_current_player(authorization)

    # Check if player has admin privileges
    if not player.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required"
        )

    return player
