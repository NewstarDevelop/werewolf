"""Unified WebSocket authentication and security utilities.

This module provides centralized authentication, origin validation,
and rate limiting for all WebSocket endpoints.
"""
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

from fastapi import WebSocket, WebSocketException, status
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.core.auth import verify_player_token, verify_admin_token

logger = logging.getLogger(__name__)


class WebSocketAuthError(Exception):
    """Exception for WebSocket authentication failures."""
    def __init__(self, message: str, code: int = 4001):
        self.message = message
        self.code = code
        super().__init__(message)


async def extract_token(
    websocket: WebSocket,
    allow_query_token: bool = False,
) -> Tuple[Optional[str], str]:
    """Extract authentication token from WebSocket connection.

    Priority:
    1. Sec-WebSocket-Protocol header (subprotocol)
    2. Cookie (user_access_token)
    3. Query parameter (deprecated, disabled by default)

    Args:
        websocket: WebSocket connection
        allow_query_token: Whether to allow token in query string (deprecated)

    Returns:
        Tuple of (token, source) where source is 'protocol', 'cookie', or 'query'

    Raises:
        WebSocketAuthError: If no valid token found
    """
    # Priority 1: Sec-WebSocket-Protocol header
    # Client sends: ['auth', 'token_value']
    protocols = websocket.scope.get("subprotocols", [])
    if len(protocols) >= 2 and protocols[0] == "auth":
        token = protocols[1]
        if token:
            return token, "protocol"

    # Priority 2: Cookie
    cookies = websocket.cookies
    token = cookies.get("user_access_token")
    if token:
        return token, "cookie"

    # Priority 3: Query parameter (deprecated)
    if allow_query_token:
        query_params = websocket.query_params
        token = query_params.get("token")
        if token:
            logger.warning(
                "DEPRECATED: Token passed via query parameter. "
                "This method will be removed in a future version. "
                "Use Sec-WebSocket-Protocol or cookies instead."
            )
            return token, "query"

    return None, "none"


def validate_origin(
    websocket: WebSocket,
    allowed_origins: Optional[list[str]] = None,
) -> Tuple[bool, str]:
    """Validate WebSocket connection origin.

    Args:
        websocket: WebSocket connection
        allowed_origins: List of allowed origins. If None, uses settings.ALLOWED_WS_ORIGINS

    Returns:
        Tuple of (is_valid, origin)
    """
    if allowed_origins is None:
        allowed_origins = settings.ALLOWED_WS_ORIGINS

    # Get origin header
    headers = dict(websocket.headers)
    origin = headers.get("origin", "")
    host = headers.get("host", "")

    # Check if origin matches host (same-origin requests) - always allowed
    if host:
        expected_origins = [
            f"http://{host}",
            f"https://{host}",
        ]
        if origin in expected_origins:
            return True, origin

    # Check if origin matches any allowed origin
    if allowed_origins and origin in allowed_origins:
        return True, origin

    # If no allowed origins configured, handle based on mode
    if not allowed_origins:
        if settings.DEBUG:
            logger.debug(f"Origin validation skipped in DEBUG mode: {origin}")
            return True, origin
        else:
            logger.warning(f"No ALLOWED_WS_ORIGINS configured, rejecting: {origin}")
            return False, origin

    # In debug mode with localhost, be more permissive
    if settings.DEBUG:
        parsed = urlparse(origin)
        if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
            logger.debug(f"Allowing localhost origin in DEBUG mode: {origin}")
            return True, origin

    logger.warning(f"Origin validation failed: {origin} not in {allowed_origins}")
    return False, origin


async def authenticate_websocket(
    websocket: WebSocket,
    require_auth: bool = True,
    allow_query_token: bool = False,
    validate_origin_header: bool = True,
) -> Optional[dict]:
    """Authenticate WebSocket connection.

    This is the main entry point for WebSocket authentication.
    It combines token extraction, validation, and origin checking.

    Args:
        websocket: WebSocket connection
        require_auth: Whether authentication is required
        allow_query_token: Whether to allow deprecated query token
        validate_origin_header: Whether to validate origin header

    Returns:
        Token payload dict if authenticated, None if not required and not provided

    Raises:
        WebSocketAuthError: If authentication fails
    """
    # Validate origin first
    if validate_origin_header:
        is_valid_origin, origin = validate_origin(websocket)
        if not is_valid_origin:
            raise WebSocketAuthError(
                f"Invalid origin: {origin}",
                code=4003
            )

    # Extract token
    token, source = await extract_token(websocket, allow_query_token)

    if not token:
        if require_auth:
            raise WebSocketAuthError("Authentication required", code=4001)
        return None

    # Verify token
    try:
        payload = verify_player_token(token)
        logger.debug(f"WebSocket authenticated via {source}: user_id={payload.get('sub')}")
        return payload
    except Exception as e:
        logger.warning(f"WebSocket token verification failed: {e}")
        raise WebSocketAuthError(f"Invalid token: {str(e)}", code=4002)


async def authenticate_admin_websocket(
    websocket: WebSocket,
    allow_query_token: bool = False,
) -> dict:
    """Authenticate WebSocket connection for admin endpoints.

    Similar to authenticate_websocket but uses admin token verification.

    Args:
        websocket: WebSocket connection
        allow_query_token: Whether to allow deprecated query token

    Returns:
        Token payload dict

    Raises:
        WebSocketAuthError: If authentication fails
    """
    token, source = await extract_token(websocket, allow_query_token)

    if not token:
        raise WebSocketAuthError("Admin authentication required", code=4001)

    try:
        payload = verify_admin_token(token)
        logger.debug(f"Admin WebSocket authenticated via {source}")
        return payload
    except Exception as e:
        logger.warning(f"Admin WebSocket token verification failed: {e}")
        raise WebSocketAuthError(f"Invalid admin token: {str(e)}", code=4002)


async def close_with_error(
    websocket: WebSocket,
    code: int,
    message: str = "",
) -> None:
    """Close WebSocket with an error code and message.

    Args:
        websocket: WebSocket connection
        code: WebSocket close code (e.g. 4001, 4002, 4003, 4004)
        message: Human-readable error message
    """
    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.close(code=code, reason=message)
    elif websocket.client_state == WebSocketState.CONNECTING:
        # Not yet accepted - just close
        await websocket.close(code=code)
