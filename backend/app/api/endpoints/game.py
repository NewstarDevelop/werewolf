"""Game API endpoints."""
import logging
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import List, Dict, Optional

from app.core.config import settings
from app.core.auth import create_player_token
from app.core.database_async import get_async_db
from app.models.game import game_store
from app.api.dependencies import get_current_player, get_optional_user
from app.schemas.enums import GameStatus
from app.schemas.game import (
    GameStartRequest, GameStartResponse, StepResponse
)
from app.schemas.action import ActionRequest, ActionResponse
from app.schemas.player import PlayerPublic
from app.schemas.message import MessageInGame
from app.services.game_engine import game_engine
from app.services.log_manager import get_game_logs
from app.services.game_analyzer import analyze_game
from app.services.analysis_cache import AnalysisCache
from app.services.room_manager import room_manager
from app.services.websocket_manager import websocket_manager
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/game", tags=["game"])
logger = logging.getLogger(__name__)


async def _persist_game_over(
    db: AsyncSession,
    game_id: str,
    status: Optional[str],
    winner: Optional[str]
) -> None:
    """
    Persist game completion to database.

    Args:
        db: Async database session
        game_id: Game/room ID
        status: Game result status
        winner: Winner identifier if game ended
    """
    if status != "game_over" or not winner:
        return

    try:
        await room_manager.finish_game(db, game_id)
        logger.info(
            "Game history persisted successfully",
            extra={"game_id": game_id}
        )
    except Exception:
        # Rollback on error
        try:
            await db.rollback()
        except Exception:
            logger.error(
                "Database rollback failed",
                extra={"game_id": game_id},
                exc_info=True
            )

        logger.error(
            "Failed to persist game history",
            extra={"game_id": game_id},
            exc_info=True
        )


# T-SEC-004: Admin verification (JWT admin token only)
async def verify_admin(
    authorization: Optional[str] = Header(None),
):
    """
    Admin verification using JWT admin token.

    Authorization header must contain an admin token:
    - Created via create_admin_token()
    - Token must have is_admin=True
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


def verify_game_membership(game_id: str, current_player: Dict):
    """
    T-SEC-003: Verify player is authorized to access the game.

    Authorization rules:
    - If token has room_id: it must match game_id
    - Always: player_id must exist in game.player_mapping

    WL-BUG-001 Fix: Also try user_id as fallback for cookie-based auth

    Args:
        game_id: Game ID from URL path
        current_player: Player info from JWT token

    Returns:
        Game instance if authorized

    Raises:
        HTTPException: 404 if game not found, 403 if not authorized
    """
    game = game_store.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player_id = current_player["player_id"]
    user_id = current_player.get("user_id")  # WL-BUG-001: Extract user_id for fallback
    room_id = current_player.get("room_id")

    # Room mode: token has room_id, must match game_id
    if room_id and room_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Game does not match your room"
        )

    # WL-BUG-001 Fix: Try player_id first, then fallback to user_id
    effective_player_id = player_id
    if player_id not in game.player_mapping:
        if user_id and user_id in game.player_mapping:
            # Fallback: use user_id (cookie auth may have user_id mapped)
            effective_player_id = user_id
            logger.info(f"WL-BUG-001: Used user_id {user_id} as fallback for game {game_id}")
        else:
            raise HTTPException(
                status_code=403,
                detail="You are not a player in this game"
            )

    # Store effective_player_id in current_player for use by callers
    current_player["effective_player_id"] = effective_player_id

    return game


@router.post("/start", response_model=GameStartResponse)
async def start_game(
    request: GameStartRequest,
    current_user: Optional[Dict] = Depends(get_optional_user)
) -> GameStartResponse:
    """
    Create a new game and assign roles.
    POST /api/game/start

    Returns JWT token for authentication in subsequent API calls.
    """
    user_id = current_user.get("user_id") if current_user else None

    game = game_store.create_game(
        human_seat=request.human_seat,
        human_role=request.human_role,
        language=request.language,
        user_id=user_id
    )

    human_player = game.get_player(game.human_seat)
    if not human_player:
        raise HTTPException(status_code=500, detail="Failed to create game")

    # Generate player_id and JWT token for single-player mode
    player_id = f"solo_{game.id}_{human_player.seat_id}"
    token = create_player_token(player_id, room_id=game.id)

    # Set up player_mapping for authentication
    game.player_mapping[player_id] = human_player.seat_id
    game.human_seats = [human_player.seat_id]

    players = [
        PlayerPublic(
            seat_id=p.seat_id,
            is_alive=p.is_alive,
            is_human=p.is_human,
            name=p.personality.name if p.personality else None
        )
        for p in game.players.values()
    ]

    return GameStartResponse(
        game_id=game.id,
        player_role=human_player.role,
        player_seat=human_player.seat_id,
        players=players,
        token=token
    )


@router.get("/{game_id}/state")
async def get_game_state(
    game_id: str,
    current_player: Dict = Depends(get_current_player)
) -> dict:
    """
    Get current game state with player-specific view.
    GET /api/game/{game_id}/state

    Requires: JWT authentication
    Security: T-SEC-003 - Room mode validates room_id matches game_id
    Returns: Filtered game state based on player's perspective
    """
    # T-SEC-003: Verify game membership (handles 404 and 403)
    game = verify_game_membership(game_id, current_player)

    # WL-BUG-001 Fix: Use effective_player_id which may be user_id fallback
    player_id = current_player.get("effective_player_id") or current_player["player_id"]
    return game.get_state_for_player(player_id)


@router.post("/{game_id}/step", response_model=StepResponse)
async def step_game(
    game_id: str,
    current_player: Dict = Depends(get_current_player),
    db: AsyncSession = Depends(get_async_db)
) -> StepResponse:
    """
    Advance the game state by one step (WL-010: async).
    POST /api/game/{game_id}/step

    Requires: JWT authentication
    Security: T-SEC-003 - Room mode validates room_id matches game_id
    P0-STAB-001 Fix: Uses per-game lock to prevent concurrent state corruption
    """
    # T-SEC-003: Verify game membership (handles 404 and 403)
    game = verify_game_membership(game_id, current_player)

    # P0-STAB-001: Acquire per-game lock to prevent concurrent state corruption
    async with game_store.get_lock(game_id):
        result = await game_engine.step(game_id)  # WL-010: await async step

        status = result.get("status", "error")
        new_phase = result.get("new_phase")
        message = result.get("message")
        winner = result.get("winner")

        if status == "error":
            raise HTTPException(status_code=400, detail=message or "Unknown error")

        # Persist game completion if game ended
        await _persist_game_over(db, game_id, status, winner)

        # WebSocket: 推送游戏状态更新到所有连接的客户端
        try:
            # Get all player IDs for this game to broadcast to
            if game.player_mapping:
                # Multi-player mode: use new broadcast_to_game_players with per-player filtering
                await websocket_manager.broadcast_to_game_players(
                    game_id,
                    "game_update",
                    lambda pid: game.get_state_for_player(pid)
                )
            else:
                # Single-player mode: send full state
                full_state = game.get_state_for_player(None)
                await websocket_manager.broadcast_to_game(
                    game_id,
                    "game_update",
                    full_state
                )
        except Exception as e:
            logger.warning(
                "Failed to broadcast game update via WebSocket",
                extra={"game_id": game_id, "error": str(e)},
                exc_info=True
            )

        return StepResponse(
            status=status,
            new_phase=new_phase,
            message=message or (f"Winner: {winner}" if winner else None)
        )


@router.post("/{game_id}/action", response_model=ActionResponse)
async def submit_action(
    game_id: str,
    request: ActionRequest,
    current_player: Dict = Depends(get_current_player),
    db: AsyncSession = Depends(get_async_db)
) -> ActionResponse:
    """
    Submit a player action.
    POST /api/game/{game_id}/action

    Requires: JWT authentication
    Security: T-SEC-003 - Room mode validates room_id matches game_id
             seat_id is derived from token, not trusted from request body
    P0-STAB-001 Fix: Uses per-game lock to prevent concurrent state corruption
    """
    # T-SEC-003: Verify game membership (handles 404 and 403)
    game = verify_game_membership(game_id, current_player)

    # WL-BUG-001 Fix: Use effective_player_id which may be user_id fallback
    player_id = current_player.get("effective_player_id") or current_player["player_id"]

    # Use seat_id from token mapping for security
    seat_id = game.player_mapping.get(player_id)
    if seat_id is None:
        raise HTTPException(
            status_code=403,
            detail="You are not a player in this game"
        )

    # P0-STAB-001: Acquire per-game lock to prevent concurrent state corruption
    async with game_store.get_lock(game_id):
        result = await game_engine.process_human_action(
            game_id=game_id,
            seat_id=seat_id,  # From token, not request.seat_id
            action_type=request.action_type,
            target_id=request.target_id,
            content=request.content
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Action failed")
            )

        # Persist game completion if action ended the game
        await _persist_game_over(db, game_id, result.get("status"), result.get("winner"))

        # WebSocket: 推送游戏状态更新到所有连接的客户端
        try:
            if game.player_mapping:
                # Multi-player mode: use new broadcast_to_game_players with per-player filtering
                await websocket_manager.broadcast_to_game_players(
                    game_id,
                    "game_update",
                    lambda pid: game.get_state_for_player(pid)
                )
            else:
                # Single-player mode
                player_state = game.get_state_for_player(player_id)
                await websocket_manager.broadcast_to_game(
                    game_id,
                    "game_update",
                    player_state
                )
        except Exception as e:
            logger.warning(
                "Failed to broadcast action update via WebSocket",
                extra={"game_id": game_id, "error": str(e)},
                exc_info=True
            )

        return ActionResponse(
            success=True,
            message=result.get("message")
        )


@router.delete("/{game_id}")
async def delete_game(
    game_id: str,
    _: Dict = Depends(verify_admin)
) -> dict:
    """
    Delete a game.
    DELETE /api/game/{game_id}

    Security: T-SEC-004 - Admin auth (JWT admin token)
    """
    if game_store.delete_game(game_id):
        return {"success": True, "message": "Game deleted"}
    raise HTTPException(status_code=404, detail="Game not found")


@router.get("/{game_id}/logs")
async def get_logs(
    game_id: str,
    limit: int = 100,
    current_player: Dict = Depends(get_current_player)
) -> Dict[str, List[Dict]]:
    """
    Get sanitized game logs (filtered to remove spoilers).
    GET /api/game/{game_id}/logs?limit=100

    Requires: JWT authentication
    Security: T-SEC-003 - Room mode validates room_id matches game_id
    """
    # T-SEC-003: Verify game membership (handles 404 and 403)
    verify_game_membership(game_id, current_player)

    logs = get_game_logs(game_id, limit)
    return {"logs": logs}


@router.get("/{game_id}/debug-messages")
async def get_debug_messages(
    game_id: str,
    current_player: Dict = Depends(get_current_player)
) -> Dict[str, List[MessageInGame]]:
    """
    Get all game messages including vote thoughts (for debugging).
    GET /api/game/{game_id}/debug-messages

    Requires: JWT authentication + DEBUG_MODE=true
    Security: T-SEC-003 - Room mode validates room_id matches game_id
    """
    # P0 Security Fix: Protect debug endpoint
    if not settings.DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Not found")

    # T-SEC-003: Verify game membership (handles 404 and 403)
    game = verify_game_membership(game_id, current_player)

    # Return all messages without filtering (including VOTE_THOUGHT)
    all_messages = [
        MessageInGame(
            seat_id=m.seat_id,
            text=m.content,
            type=m.msg_type,
            day=m.day
        )
        for m in game.messages
    ]

    return {"messages": all_messages}


@router.get("/{game_id}/analyze")
async def analyze_game_performance(
    game_id: str,
    current_player: Dict = Depends(get_current_player)
) -> Dict:
    """
    Generate comprehensive AI analysis of game performance.
    Evaluates player performance and match quality using AI.
    GET /api/game/{game_id}/analyze

    Requires: JWT authentication
    Security: T-SEC-003 - Room mode validates room_id matches game_id
              High-cost operation, only game members can request

    T-PERF-001: Now async with rate limiting (max 3 concurrent analyses)
    """
    # T-SEC-003: Verify game membership (handles 404 and 403)
    game = verify_game_membership(game_id, current_player)

    # Only analyze finished games
    if game.status != GameStatus.FINISHED:
        raise HTTPException(
            status_code=400,
            detail="Game must be finished before analysis"
        )

    try:
        # T-PERF-001: Async call with rate limiting
        analysis = await analyze_game(game)
        return analysis
    except Exception as e:
        # P0-2 Fix: Log detailed error, return generic message
        logger.error(f"Analysis failed for game {game_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Analysis failed. Please try again later."
        )


@router.delete("/{game_id}/analysis-cache")
async def clear_game_analysis_cache(
    game_id: str,
    _: Dict = Depends(verify_admin)
) -> Dict:
    """
    Clear cached analysis for specific game.
    DELETE /api/game/{game_id}/analysis-cache

    Security: T-SEC-004 - Admin auth (JWT admin token)
    """
    count = AnalysisCache.clear(game_id)
    return {
        "message": f"Cleared {count} cache entries",
        "game_id": game_id
    }


@router.delete("/analysis-cache/all")
async def clear_all_analysis_cache(
    _: Dict = Depends(verify_admin)
) -> Dict:
    """
    Clear all cached analyses.
    DELETE /api/game/analysis-cache/all

    Security: T-SEC-004 - Admin auth (JWT admin token)
    """
    count = AnalysisCache.clear()
    return {
        "message": f"Cleared {count} cache entries"
    }
