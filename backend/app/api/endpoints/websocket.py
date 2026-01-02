"""WebSocket endpoints for real-time game updates."""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Optional, Dict

from app.services.websocket_manager import websocket_manager
from app.services.game_store import game_store
from app.core.auth import get_user_from_websocket

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/game/{game_id}")
async def game_websocket(
    websocket: WebSocket,
    game_id: str,
):
    """
    WebSocket endpoint for real-time game updates.

    Clients connect to this endpoint to receive instant game state updates
    instead of polling the REST API.

    Message format:
    {
        "type": "game_update" | "error" | "ping",
        "data": { ... game state or error details ... }
    }
    """
    # Accept the WebSocket connection
    await websocket_manager.connect(websocket, game_id)

    # Verify game exists
    game = game_store.get_game(game_id)
    if not game:
        await websocket.send_json({
            "type": "error",
            "data": {"message": f"Game {game_id} not found"}
        })
        await websocket.close()
        return

    try:
        # Send initial game state
        from app.api.endpoints.game import _build_game_state
        initial_state = _build_game_state(game, my_seat=None)  # Observer mode initially

        await websocket.send_json({
            "type": "game_update",
            "data": initial_state.dict()
        })

        # Keep connection alive and handle incoming messages
        while True:
            # Wait for any messages from client (e.g., ping/pong for keepalive)
            data = await websocket.receive_text()

            # Handle ping/pong for connection keepalive
            if data == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "data": {}
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected normally for game {game_id}")
    except Exception as e:
        logger.error(f"WebSocket error for game {game_id}: {e}", exc_info=True)
    finally:
        websocket_manager.disconnect(websocket, game_id)


@router.websocket("/ws/room/{room_id}")
async def room_websocket(
    websocket: WebSocket,
    room_id: str,
):
    """
    WebSocket endpoint for real-time room updates (lobby).

    Clients connect to this endpoint while in the room lobby to receive
    instant updates when players join/leave/ready up.
    """
    await websocket_manager.connect(websocket, f"room_{room_id}")

    try:
        # Send initial confirmation
        await websocket.send_json({
            "type": "connected",
            "data": {"room_id": room_id}
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
        websocket_manager.disconnect(websocket, f"room_{room_id}")
