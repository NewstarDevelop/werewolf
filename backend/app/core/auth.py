"""JWT authentication utilities."""
import jwt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from app.core.config import settings


def create_player_token(player_id: str, room_id: Optional[str] = None) -> str:
    """
    Create JWT token for a player.

    Args:
        player_id: Unique player identifier
        room_id: Optional room identifier

    Returns:
        JWT token string
    """
    if not settings.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY not configured")

    payload = {
        "player_id": player_id,
        "is_admin": False,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    }

    if room_id:
        payload["room_id"] = room_id

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_admin_token() -> str:
    """
    Create JWT token for admin operations.

    Returns:
        JWT token string
    """
    if not settings.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY not configured")

    payload = {
        "player_id": "admin",
        "is_admin": True,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_user_token(
    user_id: str,
    player_id: Optional[str] = None,
    room_id: Optional[str] = None,
    is_admin: bool = False
) -> str:
    """
    Create JWT token for a logged-in user (with optional room context).

    Args:
        user_id: User ID from users table
        player_id: Optional player ID for room context
        room_id: Optional room ID
        is_admin: Whether user has admin privileges

    Returns:
        JWT token string
    """
    if not settings.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY not configured")

    payload = {
        "user_id": user_id,
        "player_id": player_id or user_id,  # Use user_id as player_id if not provided
        "token_type": "user",
        "is_admin": is_admin,
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    }

    if room_id:
        payload["room_id"] = room_id

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(claims: Dict) -> str:
    """
    Create a JWT access token with custom claims.

    Args:
        claims: Custom claims to include in token

    Returns:
        JWT token string
    """
    if not settings.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY not configured")

    # Add standard claims
    payload = {
        "jti": str(uuid.uuid4()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        **claims
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_player_token(token: str) -> Dict:
    """
    Verify and decode JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    if not settings.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY not configured")

    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM]
    )

    return payload


def verify_admin_token(token: str) -> Dict:
    """
    Verify and decode JWT token, ensuring it has admin privileges.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
        ValueError: Token does not have admin privileges
    """
    payload = verify_player_token(token)

    if not payload.get("is_admin", False):
        raise ValueError("Token does not have admin privileges")

    return payload
