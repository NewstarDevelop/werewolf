"""Room API endpoints - multi-room support."""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth import create_player_token
from app.api.dependencies import get_current_player, get_optional_user
from app.services.room_manager import room_manager
from app.models.room import RoomStatus

router = APIRouter(prefix="/rooms", tags=["rooms"])
logger = logging.getLogger(__name__)


# ==================== Request/Response Models ====================

class CreateRoomRequest(BaseModel):
    """创建房间请求

    P2-3 Fix: Added length validation for name and nickname fields.
    CRITICAL FIX: Removed creator_id to prevent identity spoofing.
    Server now generates UUID to ensure client cannot forge identities.
    Phase 8 Fix: Added game_mode and wolf_king_variant for 12-player support.
    """
    name: str = Field(..., min_length=1, max_length=50, description="房间名称")
    creator_nickname: str = Field(..., min_length=1, max_length=20, description="创建者昵称")
    game_mode: str = Field(default="classic_9", description="游戏模式: classic_9 或 classic_12")
    wolf_king_variant: Optional[str] = Field(default=None, description="狼王类型: wolf_king 或 white_wolf_king (仅12人局)")


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


class RoomPlayerResponse(BaseModel):
    """房间玩家响应

    P0-SEC-001 Fix: Removed player_id to prevent identity spoofing.
    Attackers could enumerate player_ids and impersonate other players.
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


# ==================== API Endpoints ====================

@router.post("")
def create_room(
    request: CreateRoomRequest,
    db: Session = Depends(get_db),
    auth_user: Optional[Dict] = Depends(get_optional_user)
):
    """
    创建房间
    POST /api/rooms

    CRITICAL FIX: Server generates UUID for creator_id to prevent identity spoofing.
    Client cannot provide their own ID.
    Phase 8 Fix: Validate game_mode and wolf_king_variant for 12-player support.

    Returns: { room: RoomResponse, token: str, player_id: str }
    """
    try:
        # Phase 8 Fix: Validate game_mode and wolf_king_variant
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

        # Determine max_players based on game_mode
        max_players = 12 if request.game_mode == "classic_12" else 9

        # CRITICAL FIX: 服务端生成creator_id，防止客户端伪造身份
        creator_id = str(uuid.uuid4())

        # 提取 user_id（如果用户已登录）
        user_id = auth_user.get("user_id") if auth_user else None

        room = room_manager.create_room(
            db,
            request.name,
            request.creator_nickname,
            creator_id,
            user_id=user_id,
            game_mode=request.game_mode,
            wolf_king_variant=request.wolf_king_variant,
            max_players=max_players
        )

        # 签发 JWT token
        token = create_player_token(
            player_id=creator_id,
            room_id=room.id
        )

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
                created_at=room.created_at.isoformat()
            ),
            players=[
                RoomPlayerResponse(
                    id=p.id,
                    nickname=p.nickname,
                    seat_id=p.seat_id,
                    is_ready=p.is_ready,
                    is_creator=p.is_creator,
                    is_me=(p.player_id == current_player_id),
                    joined_at=p.joined_at.isoformat()
                )
                for p in players
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to get room detail for {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve room details")


@router.post("/{room_id}/join")
def join_room(
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
    except Exception as e:
        # WL-014 Fix: Log detailed error, return generic message
        logger.error(f"Failed to join room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to join room")


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
def start_game(
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
    """
    try:
        # 验证玩家在该房间中
        player_id = current_player["player_id"]
        if current_player.get("room_id") != room_id:
            raise HTTPException(status_code=403, detail="You are not in this room")

        # start_game 内部会验证是否为房主
        game_id = room_manager.start_game(
            db,
            room_id,
            player_id,  # 使用认证的 player_id
            request.fill_ai
        )
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
