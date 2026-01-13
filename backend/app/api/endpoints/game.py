"""Game API endpoints."""
import secrets
import time
import logging
from fastapi import APIRouter, HTTPException, Header, Depends, Request
from fastapi.concurrency import run_in_threadpool
from typing import List, Dict, Optional

from app.core.config import settings
from app.core.auth import create_player_token
from app.core.database import get_db
from app.models.game import game_store, WOLF_ROLES
from app.api.dependencies import get_current_player, get_optional_user
from app.schemas.enums import (
    GamePhase, GameStatus, Role, ActionType, MessageType
)
from app.schemas.game import (
    GameStartRequest, GameStartResponse, GameState, StepResponse, PendingAction
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
from sqlalchemy.orm import Session

router = APIRouter(prefix="/game", tags=["game"])
logger = logging.getLogger(__name__)


def _persist_game_over_sync(db: Session, game_id: str) -> None:
    """
    Synchronous helper to persist game completion.

    This function is designed to be called via run_in_threadpool to avoid
    blocking the async event loop. It handles both the persistence and
    rollback within the same thread to ensure Session safety.

    Args:
        db: Database session
        game_id: Game/room ID
    """
    try:
        room_manager.finish_game(db, game_id)
        logger.info(
            "Game history persisted successfully",
            extra={"game_id": game_id}
        )
    except Exception:
        # Rollback in the same thread to maintain Session safety
        try:
            db.rollback()
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


async def _persist_game_over(
    db: Session,
    game_id: str,
    status: Optional[str],
    winner: Optional[str]
) -> None:
    """
    Persist game completion to database.

    Executes synchronous DB operations in a threadpool to avoid blocking the event loop.
    Ensures proper transaction rollback on errors within the same thread.

    Args:
        db: Database session
        game_id: Game/room ID
        status: Game result status
        winner: Winner identifier if game ended
    """
    if status != "game_over" or not winner:
        return

    # Execute entire DB operation (including potential rollback) in a single thread
    await run_in_threadpool(_persist_game_over_sync, db, game_id)

# P1-SEC-002: Rate limiting for admin key authentication
_admin_key_failures: Dict[str, Dict] = {}  # ip -> {"count": int, "locked_until": float}
ADMIN_KEY_MAX_FAILURES = 5
ADMIN_KEY_LOCKOUT_SECONDS = 600  # 10 minutes


def _is_trusted_proxy(ip: str) -> bool:
    """Check if the given IP is in the trusted proxies list."""
    import ipaddress
    if not settings.TRUSTED_PROXIES:
        return False
    try:
        client_ip = ipaddress.ip_address(ip)
        for proxy in settings.TRUSTED_PROXIES:
            try:
                # Support both single IPs and CIDR notation
                if '/' in proxy:
                    if client_ip in ipaddress.ip_network(proxy, strict=False):
                        return True
                else:
                    if client_ip == ipaddress.ip_address(proxy):
                        return True
            except ValueError:
                continue
    except ValueError:
        return False
    return False


def _get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, handling proxies securely.

    P1-SEC-003: Only trust X-Forwarded-For/X-Real-IP headers when the
    direct client IP is in TRUSTED_PROXIES. This prevents IP spoofing
    attacks where malicious clients forge these headers.
    """
    # Get direct client IP first
    direct_ip = request.client.host if request.client else "unknown"

    # Only trust forwarded headers if request comes from a trusted proxy
    if direct_ip != "unknown" and _is_trusted_proxy(direct_ip):
        # Check X-Forwarded-For header (set by reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()
        # Check X-Real-IP header (set by some proxies)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    # Fall back to direct client IP (don't trust forwarded headers)
    return direct_ip


# T-SEC-004: Unified admin verification
# Supports both JWT admin (primary) and X-Admin-Key (emergency fallback)
async def verify_admin(
    request: Request,
    authorization: Optional[str] = Header(None),
    admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    Unified admin verification supporting two methods:

    1. JWT Admin (primary): Authorization header with admin token
       - Created via create_admin_token()
       - Token must have is_admin=True

    2. X-Admin-Key (fallback): Legacy header-based auth
       - Only works if ADMIN_KEY_ENABLED=true (P1-SEC-002)
       - Intended for emergency/maintenance access
       - Rate limited with lockout after failures

    Priority: JWT > X-Admin-Key
    """
    # Method 1: Try JWT admin token first
    if authorization:
        try:
            player = await get_current_player(authorization, user_access_token=None)
            if player.get("is_admin", False):
                return player
        except HTTPException:
            pass  # Fall through to X-Admin-Key

    # Method 2: Fallback to X-Admin-Key (P1-SEC-002: with restrictions)
    if admin_key:
        # P1-SEC-002: Check if X-Admin-Key is enabled
        if not settings.ADMIN_KEY_ENABLED:
            logger.warning("X-Admin-Key auth attempted but ADMIN_KEY_ENABLED=false")
            raise HTTPException(
                status_code=403,
                detail="X-Admin-Key authentication is disabled. Use JWT admin token."
            )

        # P1-SEC-002: Check rate limit using real client IP
        client_ip = _get_client_ip(request)
        now = time.time()

        if client_ip in _admin_key_failures:
            failure_info = _admin_key_failures[client_ip]
            if failure_info.get("locked_until", 0) > now:
                remaining = int(failure_info["locked_until"] - now)
                logger.warning(f"Admin key auth blocked for {client_ip}, locked for {remaining}s")
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many failed attempts. Try again in {remaining} seconds."
                )

        # P0-3 Fix: Use constant-time comparison to prevent timing attacks
        if settings.ADMIN_KEY and secrets.compare_digest(admin_key, settings.ADMIN_KEY):
            # Success - clear failure count
            if client_ip in _admin_key_failures:
                del _admin_key_failures[client_ip]
            logger.info(f"Admin key auth successful from {client_ip}")
            return {"player_id": "admin_key", "is_admin": True}

        # P1-SEC-002: Record failure
        if client_ip not in _admin_key_failures:
            _admin_key_failures[client_ip] = {"count": 0, "locked_until": 0}

        _admin_key_failures[client_ip]["count"] += 1
        failure_count = _admin_key_failures[client_ip]["count"]

        if failure_count >= ADMIN_KEY_MAX_FAILURES:
            _admin_key_failures[client_ip]["locked_until"] = now + ADMIN_KEY_LOCKOUT_SECONDS
            logger.warning(f"Admin key auth locked for {client_ip} after {failure_count} failures")

        logger.warning(f"Admin key auth failed from {client_ip} (attempt {failure_count})")

    # Neither method succeeded
    raise HTTPException(
        status_code=403,
        detail="Admin access required. Provide JWT admin token or X-Admin-Key header."
    )


def verify_game_membership(game_id: str, current_player: Dict):
    """
    T-SEC-003: Verify player is authorized to access the game.

    Authorization rules:
    - If token has room_id: it must match game_id
    - Always: player_id must exist in game.player_mapping

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
    room_id = current_player.get("room_id")

    # Room mode: token has room_id, must match game_id
    if room_id and room_id != game_id:
        raise HTTPException(
            status_code=403,
            detail="Game does not match your room"
        )

    # Always enforce membership via player_mapping
    if player_id not in game.player_mapping:
        raise HTTPException(
            status_code=403,
            detail="You are not a player in this game"
        )

    return game


@router.post("/start", response_model=GameStartResponse)
def start_game(
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
def get_game_state(
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

    # Use proper multi-player support with JWT authentication
    player_id = current_player["player_id"]
    return game.get_state_for_player(player_id)


def _get_pending_action(game, human_player) -> PendingAction | None:
    """Determine what action the human player needs to take."""
    phase = game.phase
    role = human_player.role

    # Hunter can shoot after being eliminated (by vote/kill). This phase is explicitly a "last action".
    if phase == GamePhase.HUNTER_SHOOT and role == Role.HUNTER:
        if game.current_actor_seat == human_player.seat_id and human_player.can_shoot:
            alive_seats = game.get_alive_seats()
            return PendingAction(
                type=ActionType.SHOOT,
                choices=alive_seats + [0],  # 0 = skip
                message="你可以开枪带走一名玩家"
            )

    if not human_player.is_alive:
        return None

    alive_seats = game.get_alive_seats()
    other_alive = [s for s in alive_seats if s != human_player.seat_id]

    # Night werewolf chat phase - all wolf-aligned roles participate
    if phase == GamePhase.NIGHT_WEREWOLF_CHAT and role in WOLF_ROLES:
        if human_player.seat_id not in game.wolf_chat_completed:
            return PendingAction(
                type=ActionType.SPEAK,
                choices=[],
                message="与狼队友讨论今晚击杀目标（发言后自动进入投票）"
            )

    # Night werewolf phase - regular werewolf and wolf king vote
    # Note: White wolf king has separate handling in models/game.py with self-destruct option
    # TODO: Add white wolf king handling here for single-player mode parity
    if phase == GamePhase.NIGHT_WEREWOLF and role in {Role.WEREWOLF, Role.WOLF_KING}:
        if human_player.seat_id not in game.wolf_votes:
            # 狼人可以击杀任何存活玩家（包括自己和队友，实现自刀策略）
            kill_targets = alive_seats[:]
            return PendingAction(
                type=ActionType.KILL,
                choices=kill_targets,
                message="请选择今晚要击杀的目标"
            )

    # Night seer phase
    elif phase == GamePhase.NIGHT_SEER and role == Role.SEER:
        # If already verified this night, allow auto-step to proceed.
        if game.seer_verified_this_night:
            return None
        unverified = [s for s in other_alive if s not in human_player.verified_players]
        if not unverified:
            return None
        return PendingAction(
            type=ActionType.VERIFY,
            choices=unverified,
            message="请选择要查验的玩家"
        )

    # Night witch phase
    elif phase == GamePhase.NIGHT_WITCH and role == Role.WITCH:
        used_save_this_night = any(
            a.day == game.day
            and a.player_id == human_player.seat_id
            and a.action_type == ActionType.SAVE
            for a in game.actions
        )

        # 第一步：先决策解药（或跳过解药）
        if not game.witch_save_decided:
            if human_player.has_save_potion and game.night_kill_target:
                return PendingAction(
                    type=ActionType.SAVE,
                    choices=[game.night_kill_target, 0],  # 0 = skip
                    message=f"今晚{game.night_kill_target}号被杀，是否使用解药？"
                )

            no_save_reason = "今晚无人被杀" if game.night_kill_target is None else "你没有解药"
            # 为保持前端兼容，这里仍返回 SAVE 类型；前端点“技能”按钮将发送 SKIP 来跳过。
            return PendingAction(
                type=ActionType.SAVE,
                choices=[0],
                message=f"{no_save_reason}，点击技能按钮跳过解药决策"
            )

        # 第二步：再决策毒药（或跳过毒药）
        if not game.witch_poison_decided:
            # 规则：同一晚使用了解药则不能再用毒药
            if used_save_this_night:
                return PendingAction(
                    type=ActionType.POISON,
                    choices=[0],
                    message="你今晚已使用解药，无法再使用毒药，点击技能按钮继续"
                )

            if human_player.has_poison_potion:
                return PendingAction(
                    type=ActionType.POISON,
                    choices=other_alive + [0],  # 0 = skip
                    message=f"今晚{game.night_kill_target}号被杀，是否使用毒药？选择目标或跳过"
                    if game.night_kill_target is not None else "是否使用毒药？选择目标或跳过"
                )

            return PendingAction(
                type=ActionType.POISON,
                choices=[0],
                message="你没有可用的毒药，点击技能按钮继续"
            )

    # Day speech phase
    elif phase == GamePhase.DAY_SPEECH:
        if (game.current_speech_index < len(game.speech_order) and
            game.speech_order[game.current_speech_index] == human_player.seat_id):
            return PendingAction(
                type=ActionType.SPEAK,
                choices=[],
                message="轮到你发言了"
            )

    # Day vote phase
    elif phase == GamePhase.DAY_VOTE:
        if human_player.seat_id not in game.day_votes:
            return PendingAction(
                type=ActionType.VOTE,
                choices=other_alive + [0],  # 0 = abstain
                message="请投票选择要放逐的玩家，或弃票"
            )

    return None


@router.post("/{game_id}/step", response_model=StepResponse)
async def step_game(
    game_id: str,
    current_player: Dict = Depends(get_current_player),
    db: Session = Depends(get_db)
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
    db: Session = Depends(get_db)
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

    # Get seat_id from token mapping (don't trust client-provided seat_id)
    player_id = current_player["player_id"]

    # Use seat_id from token mapping for security
    seat_id = game.player_mapping.get(player_id)
    if seat_id is None:
        raise HTTPException(
            status_code=403,
            detail="You are not a player in this game"
        )

    # P0-STAB-001: Acquire per-game lock to prevent concurrent state corruption
    async with game_store.get_lock(game_id):
        result = game_engine.process_human_action(
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

    Security: T-SEC-004 - Unified admin auth (JWT admin or X-Admin-Key)
    """
    if game_store.delete_game(game_id):
        return {"success": True, "message": "Game deleted"}
    raise HTTPException(status_code=404, detail="Game not found")


@router.get("/{game_id}/logs")
def get_logs(
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
def get_debug_messages(
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
        import logging
        logging.getLogger(__name__).error(f"Analysis failed for game {game_id}: {e}", exc_info=True)
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

    Security: T-SEC-004 - Unified admin auth (JWT admin or X-Admin-Key)
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

    Security: T-SEC-004 - Unified admin auth (JWT admin or X-Admin-Key)
    """
    count = AnalysisCache.clear()
    return {
        "message": f"Cleared {count} cache entries"
    }
