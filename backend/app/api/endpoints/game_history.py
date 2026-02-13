"""Game history API endpoints.

Migrated to async database access using SQLAlchemy 2.0 async API.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, select

from app.core.database_async import get_async_db
from app.api.dependencies import get_current_user
from app.models.game_history import GameSession, GameParticipant
from app.models.room import Room
from app.services.game_history_service import GameHistoryService
from app.schemas.game_history import (
    GameHistoryListResponse,
    GameHistoryItem,
    GameHistoryDetail,
    PlayerInfo,
    GameReplayResponse,
)
from app.schemas.message import MessageInGame

router = APIRouter(prefix="/game-history", tags=["game-history"])


@router.get("", response_model=GameHistoryListResponse)
async def get_game_history_list(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    winner: Optional[str] = Query(None, description="Filter by winner: 'werewolf', 'villager', or 'draw'"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Get current user's game history with optional filtering and pagination.

    Requires: JWT authentication
    Returns: Paginated list of game history items
    """
    user_id = current_user["user_id"]

    # Validate winner filter
    if winner and winner not in ["werewolf", "villager", "draw"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid winner filter. Must be 'werewolf', 'villager', or 'draw'"
        )

    # Optimized query using JOINs to avoid N+1 queries in the loop
    player_counts = (
        select(
            GameParticipant.game_id,
            func.count(GameParticipant.id).label("count")
        ).group_by(GameParticipant.game_id)
    ).subquery()

    conditions = [
        GameSession.finished_at.isnot(None),
    ]
    if winner:
        conditions.append(GameSession.winner == winner)

    # Count total
    count_stmt = (
        select(func.count(GameSession.id))
        .join(GameParticipant, and_(GameSession.id == GameParticipant.game_id, GameParticipant.user_id == user_id))
        .where(*conditions)
    )
    total = int((await db.execute(count_stmt)).scalar() or 0)

    # Fetch page with JOINs
    stmt = (
        select(
            GameSession,
            Room.name.label("room_name"),
            GameParticipant.role.label("my_role"),
            GameParticipant.is_winner.label("my_is_winner"),
            player_counts.c.count.label("player_count"),
        )
        .join(GameParticipant, and_(GameSession.id == GameParticipant.game_id, GameParticipant.user_id == user_id))
        .outerjoin(Room, GameSession.room_id == Room.id)
        .join(player_counts, GameSession.id == player_counts.c.game_id)
        .where(*conditions)
        .order_by(GameSession.finished_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    results = (await db.execute(stmt)).all()

    game_items = [
        GameHistoryItem(
            game_id=game.id,
            room_name=room_name or "Unknown Room",
            started_at=game.started_at,
            finished_at=game.finished_at,
            winner=game.winner or "unknown",
            player_count=player_count,
            my_role=my_role or "Unknown",
            is_winner=is_winner
        )
        for game, room_name, my_role, is_winner, player_count in results
    ]

    return GameHistoryListResponse(
        games=game_items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{game_id}", response_model=GameHistoryDetail)
async def get_game_history_detail(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed information about a specific game.

    Requires: JWT authentication
    Permissions: User must have participated in the game
    Returns: Game detail with full player list
    """
    user_id = current_user["user_id"]

    # Get game with permission check
    game = await GameHistoryService.get_game_detail(db, game_id, user_id)

    if not game:
        raise HTTPException(
            status_code=404,
            detail="Game not found or you don't have permission to view it"
        )

    # Get room name
    room_name = await GameHistoryService.get_room_name(db, game.room_id) if game.room_id else "Unknown Room"

    # Get user's participant info
    participant = await GameHistoryService.get_user_participant(db, game.id, user_id)
    my_role = participant.role if participant and participant.role else "Unknown"
    is_winner = participant.is_winner if participant else False

    # Get all participants
    all_participants = await GameHistoryService.get_all_participants(db, game.id)

    # Build player list
    players = [
        PlayerInfo(
            nickname=p.nickname,
            role=p.role if p.role else "Unknown",
            is_winner=p.is_winner
        )
        for p in all_participants
    ]

    # Calculate duration
    duration_seconds = 0
    if game.started_at and game.finished_at:
        duration_seconds = int((game.finished_at - game.started_at).total_seconds())

    return GameHistoryDetail(
        game_id=game.id,
        room_name=room_name,
        started_at=game.started_at,
        finished_at=game.finished_at,
        winner=game.winner or "unknown",
        player_count=len(players),
        my_role=my_role,
        is_winner=is_winner,
        players=players,
        duration_seconds=duration_seconds
    )


@router.get("/{game_id}/replay", response_model=GameReplayResponse)
async def get_game_replay(
    game_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(2000, ge=1, le=5000, description="Pagination limit (max 5000)"),
):
    """
    Get replay data for a finished game (MVP: persisted messages only).

    Requires: JWT authentication
    Permissions: User must have participated in the game
    Returns: Game replay with message timeline
    """
    user_id = current_user["user_id"]

    result = await GameHistoryService.get_game_replay_messages(db, game_id, user_id, offset=offset, limit=limit)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Game not found or you don't have permission to view it"
        )

    db_messages, total = result
    messages = [
        MessageInGame(
            seat_id=m.seat_id,
            text=m.content,
            type=m.msg_type,
            day=m.day,
        )
        for m in db_messages
    ]

    return GameReplayResponse(
        game_id=game_id,
        total=total,
        offset=offset,
        limit=limit,
        messages=messages,
    )
