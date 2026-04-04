from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.room import Room
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.room import (
    AiFillRequest,
    ReadyToggleResponse,
    RoomCreateRequest,
    RoomResponse,
    StartGameResponse,
)
from app.services.room_service import RoomService

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _room_to_response(room: Room) -> dict:
    """Build a room response dict with players included."""
    return {
        "id": room.id,
        "name": room.name,
        "owner_id": room.owner_id,
        "mode": room.mode,
        "variant": room.variant,
        "language": room.language,
        "max_players": room.max_players,
        "status": room.status,
        "token": room.token,
        "players": [
            {
                "user_id": p.user_id,
                "nickname": None,
                "seat": p.seat,
                "is_ready": p.is_ready,
                "is_ai": p.is_ai,
                "ai_provider": p.ai_provider,
            }
            for p in room.players
        ],
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "started_at": room.started_at.isoformat() if room.started_at else None,
        "finished_at": room.finished_at.isoformat() if room.finished_at else None,
    }


async def _get_room_or_404(db: AsyncSession, room_id: int) -> Room:
    svc = RoomService(db)
    room = await svc.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@router.get("/")
async def list_rooms(page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    svc = RoomService(db)
    rooms, total = await svc.list_rooms(page, page_size)
    items = []
    for r in rooms:
        items.append({
            "id": r.id,
            "name": r.name,
            "owner_id": r.owner_id,
            "mode": r.mode,
            "variant": r.variant,
            "language": r.language,
            "max_players": r.max_players,
            "player_count": len(r.players),
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_room(
    body: RoomCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RoomService(db)
    try:
        room = await svc.create_room(user, body)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return _room_to_response(room)


@router.get("/{room_id}")
async def get_room(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await _get_room_or_404(db, room_id)
    return _room_to_response(room)


@router.delete("/{room_id}")
async def delete_room(
    room_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room_or_404(db, room_id)
    svc = RoomService(db)
    try:
        await svc.delete_room(room, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    await db.commit()
    return {"message": "Room deleted"}


@router.post("/{room_id}/join")
async def join_room(
    room_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room_or_404(db, room_id)
    svc = RoomService(db)
    try:
        await svc.join_room(room, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    await db.refresh(room, ["players"])
    return _room_to_response(room)


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room_or_404(db, room_id)
    svc = RoomService(db)
    try:
        await svc.leave_room(room, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return {"message": "Left room"}


@router.post("/{room_id}/ready", response_model=ReadyToggleResponse)
async def toggle_ready(
    room_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room_or_404(db, room_id)
    svc = RoomService(db)
    try:
        is_ready = await svc.toggle_ready(room, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return ReadyToggleResponse(is_ready=is_ready)


@router.post("/{room_id}/fill-ai")
async def fill_ai(
    room_id: int,
    body: AiFillRequest = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room_or_404(db, room_id)
    if room.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner can fill AI")
    svc = RoomService(db)
    try:
        body = body or AiFillRequest()
        await svc.fill_ai(room, body.count, body.provider)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    await db.refresh(room, ["players"])
    return _room_to_response(room)


@router.post("/{room_id}/start", response_model=StartGameResponse)
async def start_game(
    room_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await _get_room_or_404(db, room_id)
    svc = RoomService(db)
    try:
        game_id = await svc.start_game(room, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    return StartGameResponse(game_id=game_id)
