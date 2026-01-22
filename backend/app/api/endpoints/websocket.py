"""WebSocket endpoints for real-time game updates."""
import logging
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from app.services.websocket_manager import websocket_manager
from app.services.websocket_auth import (
    authenticate_websocket,
    validate_origin,
    WebSocketAuthError,
    close_with_error,
)
from app.models.game import game_store
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# A2-FIX: 生产环境禁用 query token，防止 URL token 泄露
# 仅在 DEBUG 模式下允许，用于开发和测试
ALLOW_QUERY_TOKEN = settings.DEBUG


@router.websocket("/ws/game/{game_id}")
async def game_websocket(
    websocket: WebSocket,
    game_id: str,
    token: Optional[str] = Query(None)  # Keep for backward compatibility, but disabled in production
):
    """
    WebSocket endpoint for real-time game updates with JWT authentication.

    Authentication methods (in order of preference):
    1. Sec-WebSocket-Protocol header: ["auth", "<jwt_token>"] (recommended, secure)
    2. Cookie: user_access_token (secure, automatic)
    3. Query string: ?token=<jwt_token> (DISABLED in production, deprecated)

    Security:
    - Origin validation is enforced (CSWSH protection)
    - Query token is disabled in production to prevent URL token leakage

    Message format:
    {
        "type": "game_update" | "connected" | "error" | "pong",
        "data": { ... game state or error details ... }
    }
    """
    # A2-FIX: 使用统一的 authenticate_websocket 进行鉴权和 Origin 校验
    try:
        payload = await authenticate_websocket(
            websocket,
            require_auth=True,
            allow_query_token=ALLOW_QUERY_TOKEN,  # 生产环境下为 False
            validate_origin_header=True,  # 始终校验 Origin
        )
    except WebSocketAuthError as e:
        logger.warning(f"WebSocket auth failed for game {game_id}: {e.message}")
        await close_with_error(websocket, e.code, e.message)
        return

    # 从 payload 提取 player_id
    player_id = payload.get("player_id") or payload.get("sub")
    user_id = payload.get("user_id")  # WL-BUG-001: Extract user_id for fallback lookup
    room_id = payload.get("room_id")

    # A2-FIX: 校验 room_id 与 game_id 匹配（如果 token 包含 room_id）
    if room_id and room_id != game_id:
        await close_with_error(websocket, 4002, "Token room_id does not match game_id")
        return

    if not player_id:
        await close_with_error(websocket, 4002, "Invalid token: missing player_id")
        return

    # Step 2: Verify game exists
    game = game_store.get_game(game_id)
    if not game:
        await close_with_error(websocket, 4004, f"Game {game_id} not found")
        return

    # Step 3: Verify player is in this game
    # WL-BUG-001 Fix: Try player_id first, then fallback to user_id for cookie auth
    player = game.get_player_by_id(player_id)
    effective_player_id = player_id
    if not player and user_id and user_id != player_id:
        # Fallback: try user_id (cookie auth may use user_id as player_id)
        player = game.get_player_by_id(user_id)
        if player:
            effective_player_id = user_id
            logger.info(f"WL-BUG-001: Used user_id {user_id} as fallback for player lookup in game {game_id}")

    if not player:
        await close_with_error(websocket, 4004, "Player not in game")
        return

    # Step 4: Establish connection with player identity
    # If using subprotocol auth, respond with "auth" to confirm
    subprotocols = websocket.scope.get("subprotocols", [])
    accepted_subprotocol = "auth" if subprotocols and subprotocols[0] == "auth" else None
    await websocket_manager.connect(game_id, effective_player_id, websocket, subprotocol=accepted_subprotocol)

    try:
        # Send initial state filtered for this player
        initial_state = game.get_state_for_player(effective_player_id)
        await websocket.send_json({
            "type": "connected",
            "data": initial_state
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()

            # Handle ping/pong for connection keepalive
            if data == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "data": {}
                })

    except WebSocketDisconnect:
        logger.info(f"Player {effective_player_id} disconnected from game {game_id}")
    except Exception as e:
        logger.error(f"WebSocket error for player {effective_player_id} in game {game_id}: {e}", exc_info=True)
    finally:
        websocket_manager.disconnect(game_id, effective_player_id, websocket)


@router.websocket("/ws/room/{room_id}")
async def room_websocket(
    websocket: WebSocket,
    room_id: str,
):
    """
    WebSocket endpoint for real-time room updates (lobby).

    Clients connect to this endpoint while in the room lobby to receive
    instant updates when players join/leave/ready up.

    Security:
    - Origin validation to prevent CSWSH (Cross-Site WebSocket Hijacking)
    - Optional authentication (if token provided, validates it)
    """
    # Validate origin to prevent CSWSH attacks
    is_valid_origin, origin = validate_origin(websocket)
    if not is_valid_origin:
        logger.warning(f"Room WS rejected invalid origin: {origin} for room {room_id}")
        await websocket.close(code=4003, reason="Invalid origin")
        return

    # Optional authentication - if token provided, validate it
    # This allows anonymous viewing but tracks authenticated users
    user_id = None
    try:
        payload = await authenticate_websocket(
            websocket,
            require_auth=False,  # Authentication optional for room lobby
            allow_query_token=ALLOW_QUERY_TOKEN,
            validate_origin_header=False,  # Already validated above
        )
        if payload:
            user_id = payload.get("sub") or payload.get("user_id")
    except WebSocketAuthError as e:
        logger.warning(f"Room WS auth failed: {e.message}")
        # Continue without authentication for public room viewing

    room_key = f"room_{room_id}"
    connection_id = user_id or str(uuid.uuid4())
    await websocket_manager.connect(room_key, connection_id, websocket)

    try:
        # Send initial confirmation
        await websocket.send_json({
            "type": "connected",
            "data": {"room_id": room_id, "authenticated": user_id is not None}
        })

        # Keep connection alive
        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "data": {}
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally for room {room_id}")
    except Exception as e:
        logger.error(f"WebSocket error for room {room_id}: {e}", exc_info=True)
    finally:
        websocket_manager.disconnect(room_key, connection_id, websocket)
