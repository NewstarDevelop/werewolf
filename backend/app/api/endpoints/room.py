"""Room API endpoints - multi-room support."""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth import create_player_token
from app.api.dependencies import get_current_player, get_optional_user, get_current_user
from app.services.room_manager import room_manager
from app.models.room import RoomStatus
from app.models.user import User
from app.services.notification_emitter import emit_notification, emit_to_users
from app.schemas.notification import NotificationCategory, NotificationPersistPolicy

router = APIRouter(prefix="/rooms", tags=["rooms"])
logger = logging.getLogger(__name__)


# ==================== Request/Response Models ====================

class CreateRoomRequest(BaseModel):
    """创建房间请求

    要求用户必须登录。直接使用用户的 nickname 作为创建者名称。
    """
    name: str = Field(..., min_length=1, max_length=50, description="房间名称")
    game_mode: str = Field(default="classic_9", description="游戏模式: classic_9 或 classic_12")
    wolf_king_variant: Optional[str] = Field(default=None, description="狼王类型: wolf_king 或 white_wolf_king (仅12人局)")
    language: str = Field(default="zh", description="游戏语言: zh 或 en")


class JoinRoomRequest(BaseModel):
    """加入房间请求

    P2-3 Fix: Added length validation for nickname field.
    CRITICAL FIX: Removed player_id to prevent identity spoofing.
    Server now generates UUID to ensure client cannot forge identities.
    """
    nickname: str = Field(..., min_length=1, max_length=20, description="玩家昵称")


class ReadyRequest(BaseModel):
    """准备请求"""
    player_id: str


class StartGameRequest(BaseModel):
    """开始游戏请求

    P1-API-001 Fix: player_id is Optional because it's derived from JWT token
    on the server side, not trusted from client input.
    """
    player_id: Optional[str] = None  # Ignored by server, kept for backward compatibility
    fill_ai: bool = False  # 是否填充AI（默认False=多人模式）


class RoomResponse(BaseModel):
    """房间响应"""
    id: str
    name: str
    creator_nickname: str
    status: str
    current_players: int
    max_players: int
    game_mode: str
    wolf_king_variant: Optional[str]
    created_at: str
    game_id: Optional[str] = None  # FIX: 当房间状态为 PLAYING 时返回 game_id，用于非房主玩家导航


class RoomPlayerResponse(BaseModel):
    """房间玩家响应

    P0-SEC-001 Fix: Removed player_id to prevent identity spoofing.
    Attackers could enumerate player_ids and impersonate other players.

    P1-SEC-004 Fix: Removed user_id to prevent privacy leakage.
    Use is_me to identify current user, and has_same_user in RoomDetailResponse
    to detect if the authenticated user is already in the room.
    """
    id: int
    nickname: str
    seat_id: Optional[int]
    is_ready: bool
    is_creator: bool
    is_me: bool  # 标识是否为当前请求用户
    joined_at: str


class RoomDetailResponse(BaseModel):
    """房间详情响应"""
    room: RoomResponse
    players: List[RoomPlayerResponse]
    has_same_user: bool = False  # P1-SEC-004: 当前登录用户是否已在房间中（用于重复加入检测）


# ==================== API Endpoints ====================

@router.post("")
async def create_room(
    request: CreateRoomRequest,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_user)
):
    """
    创建房间
    POST /api/rooms

    要求用户必须登录。检查用户是否已有活跃房间（一人一房限制）。
    直接使用用户的 nickname 作为创建者名称。

    Returns: { room: RoomResponse, token: str, player_id: str }
    """
    try:
        # 验证 game_mode
        if request.game_mode not in ["classic_9", "classic_12"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid game_mode. Must be 'classic_9' or 'classic_12'"
            )

        if request.game_mode == "classic_12":
            if not request.wolf_king_variant:
                raise HTTPException(
                    status_code=400,
                    detail="12-player mode requires wolf_king_variant ('wolf_king' or 'white_wolf_king')"
                )
            if request.wolf_king_variant not in ["wolf_king", "white_wolf_king"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid wolf_king_variant. Must be 'wolf_king' or 'white_wolf_king'"
                )
        elif request.game_mode == "classic_9" and request.wolf_king_variant:
            raise HTTPException(
                status_code=400,
                detail="9-player mode does not support wolf_king_variant"
            )

        # 验证 language
        if request.language not in ["zh", "en"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid language. Must be 'zh' or 'en'"
            )

        # 获取用户信息
        user_id = current_user.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # 检查用户是否已有活跃房间（一人一房限制）
        from app.models.room import Room
        existing_room = db.query(Room).filter(
            Room.creator_user_id == user_id,
            Room.status.in_([RoomStatus.WAITING, RoomStatus.PLAYING])
        ).first()

        if existing_room:
            raise HTTPException(
                status_code=409,
                detail="You already have an active room. Please finish or close it first."
            )

        # 确定最大玩家数
        max_players = 12 if request.game_mode == "classic_12" else 9

        # 服务端生成 creator_id
        creator_id = str(uuid.uuid4())

        # 创建房间，使用用户的 nickname
        room = room_manager.create_room(
            db,
            request.name,
            user.nickname,  # 使用用户的真实昵称
            creator_id,
            user_id=user_id,
            game_mode=request.game_mode,
            wolf_king_variant=request.wolf_king_variant,
            language=request.language,
            max_players=max_players
        )

        # 签发 JWT token
        token = create_player_token(
            player_id=creator_id,
            room_id=room.id
        )

        # 发送房间创建成功通知
        try:
            await emit_notification(
                db,
                user_id=user_id,
                category=NotificationCategory.ROOM,
                title="房间创建成功",
                body=f"房间「{room.name}」已创建，等待玩家加入",
                data={"room_id": room.id, "room_name": room.name},
                persist_policy=NotificationPersistPolicy.DURABLE,
                idempotency_key=f"room_created:{room.id}",
            )
        except Exception as e:
            logger.warning(f"Failed to send room creation notification: {e}")

        return {
            "room": RoomResponse(
                id=room.id,
                name=room.name,
                creator_nickname=room.creator_nickname,
                status=room.status.value,
                current_players=room.current_players,
                max_players=room.max_players,
                game_mode=room.game_mode,
                wolf_king_variant=room.wolf_king_variant,
                created_at=room.created_at.isoformat()
            ),
            "token": token,
            "player_id": creator_id  # 返回服务端生成的player_id
        }
    except HTTPException:
        raise
    except Exception as e:
        # Rollback any pending transaction to prevent session corruption
        db.rollback()
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to create room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create room")


@router.get("", response_model=List[RoomResponse])
def get_rooms(
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    获取房间列表
    GET /api/rooms?status=waiting&limit=50
    """
    try:
        # 转换状态参数
        room_status = None
        if status:
            try:
                room_status = RoomStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: waiting, playing, finished"
                )

        rooms = room_manager.get_rooms(db, room_status, limit)
        return [
            RoomResponse(
                id=r.id,
                name=r.name,
                creator_nickname=r.creator_nickname,
                status=r.status.value,
                current_players=r.current_players,
                max_players=r.max_players,
                game_mode=r.game_mode,
                wolf_king_variant=r.wolf_king_variant,
                created_at=r.created_at.isoformat()
            )
            for r in rooms
        ]
    except HTTPException:
        raise
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to get rooms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve room list")


@router.get("/{room_id}", response_model=RoomDetailResponse)
def get_room_detail(
    room_id: str,
    db: Session = Depends(get_db),
    current_player: Dict = Depends(get_current_player)
):
    """
    获取房间详情（包含玩家列表）
    GET /api/rooms/{room_id}

    Requires: JWT authentication
    HIGH FIX: Added room membership validation to prevent unauthorized access.
    Only room members can view room details.
    """
    try:
        room = room_manager.get_room(db, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="房间不存在")

        # 验证访问权限
        # 允许持有 User Token 的用户查看公开房间（大厅浏览）
        # 仅对已加入房间的玩家强制验证 room_id 匹配
        token_room_id = current_player.get("room_id")
        token_type = current_player.get("token_type")

        # User Token（大厅浏览）：允许查看所有房间
        # Game Token（已加入房间）：必须匹配 room_id
        if token_type != "user" and token_room_id != room_id:
            raise HTTPException(status_code=403, detail="无权访问该房间")

        players = room_manager.get_room_players(db, room_id)

        # 获取当前用户的 player_id 用于标识 is_me
        current_player_id = current_player.get("player_id")

        # P1-SEC-004: 检查当前登录用户是否已在房间中（用于重复加入检测）
        current_user_id = current_player.get("user_id")
        has_same_user = False
        if current_user_id:
            has_same_user = any(p.user_id == current_user_id for p in players)

        return RoomDetailResponse(
            room=RoomResponse(
                id=room.id,
                name=room.name,
                creator_nickname=room.creator_nickname,
                status=room.status.value,
                current_players=room.current_players,
                max_players=room.max_players,
                game_mode=room.game_mode,
                wolf_king_variant=room.wolf_king_variant,
                created_at=room.created_at.isoformat(),
                # FIX: 当房间状态为 PLAYING 时返回 game_id（game_id == room_id）
                game_id=room.id if room.status == RoomStatus.PLAYING else None
            ),
            players=[
                RoomPlayerResponse(
                    id=p.id,
                    nickname=p.nickname,
                    seat_id=p.seat_id,
                    is_ready=p.is_ready,
                    is_creator=p.is_creator,
                    # FIX: 同时支持 player_id 和 user_id 匹配，解决房主返回大厅后重新进入房间丢失权限的问题
                    is_me=(p.player_id == current_player_id) or (current_user_id is not None and p.user_id == current_user_id),
                    joined_at=p.joined_at.isoformat()
                )
                for p in players
            ],
            has_same_user=has_same_user
        )
    except HTTPException:
        raise
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to get room detail for {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve room details")


@router.post("/{room_id}/join")
async def join_room(
    room_id: str,
    request: JoinRoomRequest,
    db: Session = Depends(get_db),
    auth_user: Optional[Dict] = Depends(get_optional_user)
):
    """
    加入房间
    POST /api/rooms/{room_id}/join

    CRITICAL FIX: Server generates UUID for player_id to prevent identity spoofing.
    Client cannot provide their own ID.

    Returns: { success: bool, message: str, token: str, player_id: str }
    """
    try:
        # CRITICAL FIX: 服务端生成player_id，防止客户端伪造身份
        player_id = str(uuid.uuid4())

        # 提取 user_id（如果用户已登录）
        user_id = auth_user.get("user_id") if auth_user else None

        # 获取房间信息（用于通知房主）
        room = room_manager.get_room(db, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="房间不存在")

        player = room_manager.join_room(
            db,
            room_id,
            player_id,
            request.nickname,
            user_id=user_id
        )

        # 签发 JWT token
        token = create_player_token(
            player_id=player.player_id,
            room_id=room_id
        )

        # 通知房主有新玩家加入
        if room.creator_user_id:
            try:
                await emit_notification(
                    db,
                    user_id=room.creator_user_id,
                    category=NotificationCategory.ROOM,
                    title="新玩家加入",
                    body=f"玩家「{request.nickname}」加入了房间「{room.name}」",
                    data={
                        "room_id": room_id,
                        "room_name": room.name,
                        "player_nickname": request.nickname,
                    },
                    persist_policy=NotificationPersistPolicy.DURABLE,
                    idempotency_key=f"player_joined:{room_id}:{player_id}",
                )
            except Exception as e:
                logger.warning(f"Failed to send player join notification: {e}")

        return {
            "success": True,
            "message": "加入成功",
            "token": token,
            "player_id": player_id  # 返回服务端生成的player_id
        }
    except ValueError as e:
        # ValueError is expected for user errors (room full, etc.)
        # WL-014 Fix: Return safe user-facing message
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to join room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to join room")


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: str,
    db: Session = Depends(get_db),
    current_player: Dict = Depends(get_current_player)
):
    """
    退出房间（仅非房主可调用）
    POST /api/rooms/{room_id}/leave

    Requires: JWT authentication

    广播 player_left 事件给房间内其他玩家。
    """
    from app.services.websocket_manager import websocket_manager

    try:
        # 验证玩家在该房间中
        player_id = current_player["player_id"]
        if current_player.get("room_id") != room_id:
            raise HTTPException(status_code=403, detail="You are not in this room")

        # 调用服务层离开房间，获取广播信息
        result = room_manager.leave_room(db, room_id, player_id)

        # WebSocket 广播 player_left 事件（失败不阻断主流程）
        room_key = f"room_{room_id}"
        try:
            await websocket_manager.broadcast_to_game(
                room_key,
                "player_left",
                {
                    "room_id": room_id,
                    "player_id": player_id,
                    "nickname": result["nickname"],
                    "current_players": result["current_players"]
                }
            )
            logger.info(f"Broadcasted player_left to room {room_id}")
        except Exception as e:
            logger.warning(f"Failed to broadcast player_left to room {room_id}: {e}")

        return {"success": True, "message": "已退出房间"}
    except ValueError as e:
        error_msg = str(e)
        # 房间不存在应返回 404，其他业务错误返回 400
        if "房间不存在" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to leave room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to leave room")


@router.post("/{room_id}/ready")
def toggle_ready(
    room_id: str,
    db: Session = Depends(get_db),
    current_player: Dict = Depends(get_current_player)
):
    """
    切换准备状态
    POST /api/rooms/{room_id}/ready

    Requires: JWT authentication
    """
    try:
        # 验证玩家在该房间中
        player_id = current_player["player_id"]
        if current_player.get("room_id") != room_id:
            raise HTTPException(status_code=403, detail="You are not in this room")

        is_ready = room_manager.toggle_ready(
            db,
            room_id,
            player_id
        )
        return {
            "success": True,
            "is_ready": is_ready,
            "message": "已准备" if is_ready else "已取消准备"
        }
    except HTTPException:
        raise
    except ValueError as e:
        # ValueError is expected for user errors
        # WL-014 Fix: Return safe user-facing message
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to toggle ready in room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update ready status")


@router.post("/{room_id}/start")
async def start_game(
    room_id: str,
    request: StartGameRequest,
    db: Session = Depends(get_db),
    current_player: Dict = Depends(get_current_player)
):
    """
    开始游戏（仅房主可调用）
    POST /api/rooms/{room_id}/start
    Body: { "player_id": "...", "fill_ai": false }
    - fill_ai=false: 多人模式，需要9人全部准备
    - fill_ai=true: AI填充模式，允许少于9人，剩余座位自动填充AI

    Requires: JWT authentication + room owner

    FIX: 游戏开始后通过 WebSocket 广播 game_started 事件给房间内所有玩家，
    解决非房主玩家无法获知游戏已开始的问题。
    """
    from app.services.websocket_manager import websocket_manager

    try:
        # 验证玩家在该房间中
        player_id = current_player["player_id"]
        if current_player.get("room_id") != room_id:
            raise HTTPException(status_code=403, detail="You are not in this room")

        # 获取房间信息用于通知
        room = room_manager.get_room(db, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="房间不存在")

        # 获取房间内所有玩家的 user_id（用于发送通知）
        players = room_manager.get_room_players(db, room_id)
        player_user_ids = [p.user_id for p in players if p.user_id]

        # start_game 内部会验证是否为房主
        game_id = room_manager.start_game(
            db,
            room_id,
            player_id,  # 使用认证的 player_id
            request.fill_ai
        )

        # 广播 game_started 事件给房间内所有玩家
        # 使用房间 WebSocket 的 key 格式: room_{room_id}
        room_key = f"room_{room_id}"
        try:
            await websocket_manager.broadcast_to_game(
                room_key,
                "game_started",
                {"room_id": room_id, "game_id": game_id}
            )
            logger.info(f"Broadcasted game_started to room {room_id}")
        except Exception as e:
            # WebSocket 广播失败不应阻止游戏开始
            logger.warning(f"Failed to broadcast game_started to room {room_id}: {e}")

        # 发送游戏开始通知给所有玩家
        if player_user_ids:
            try:
                await emit_to_users(
                    db,
                    user_ids=player_user_ids,
                    category=NotificationCategory.GAME,
                    title="游戏开始",
                    body=f"房间「{room.name}」的游戏已开始",
                    data={"room_id": room_id, "game_id": game_id, "room_name": room.name},
                    persist_policy=NotificationPersistPolicy.DURABLE,
                    idempotency_key_prefix=f"game_started:{game_id}",
                )
            except Exception as e:
                logger.warning(f"Failed to send game start notifications: {e}")

        mode = "AI填充" if request.fill_ai else "多人对战"
        return {
            "success": True,
            "message": f"游戏已开始（{mode}）",
            "game_id": game_id
        }
    except HTTPException:
        raise
    except ValueError as e:
        # ValueError is expected for user errors (not owner, not enough players, etc.)
        # WL-014 Fix: Return safe user-facing message
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to start game in room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start game")


@router.delete("/{room_id}")
def delete_room(
    room_id: str,
    db: Session = Depends(get_db),
    current_player: Dict = Depends(get_current_player)
):
    """
    删除房间（仅房主可调用）
    DELETE /api/rooms/{room_id}

    Requires: JWT authentication + room owner
    """
    try:
        # 验证玩家在该房间中且为房主
        player_id = current_player["player_id"]
        if current_player.get("room_id") != room_id:
            raise HTTPException(status_code=403, detail="You are not in this room")

        # 获取房间信息验证房主
        room = room_manager.get_room(db, room_id)
        if not room:
            raise HTTPException(status_code=404, detail="房间不存在")

        # 验证是否为房主（通过creator_id）
        players = room_manager.get_room_players(db, room_id)
        creator = next((p for p in players if p.is_creator), None)
        if not creator or creator.player_id != player_id:
            raise HTTPException(status_code=403, detail="Only room owner can delete the room")

        success = room_manager.delete_room(db, room_id)
        if success:
            return {"success": True, "message": "房间已删除"}
        raise HTTPException(status_code=404, detail="房间不存在")
    except HTTPException:
        raise
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to delete room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete room")
