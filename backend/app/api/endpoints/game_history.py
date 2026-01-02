"""Game history API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.services.game_history_service import GameHistoryService
from app.schemas.game_history import (
    GameHistoryListResponse,
    GameHistoryItem,
    GameHistoryDetail,
    PlayerInfo
)

router = APIRouter(prefix="/game-history", tags=["game-history"])


@router.get("", response_model=GameHistoryListResponse)
async def get_game_history_list(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    winner: Optional[str] = Query(None, description="Filter by winner: 'werewolf' or 'villager'"),
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
    if winner and winner not in ["werewolf", "villager"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid winner filter. Must be 'werewolf' or 'villager'"
        )

    # Get games from service
    games, total = GameHistoryService.get_user_games(
        db=db,
        user_id=user_id,
        winner_filter=winner,
        page=page,
        page_size=page_size
    )

    # Convert to response format
    game_items = []
    for game in games:
        # Get room name
        room_name = GameHistoryService.get_room_name(db, game.room_id) if game.room_id else "Unknown Room"

        # Get user's participant info
        participant = GameHistoryService.get_user_participant(db, game.id, user_id)
        my_role = participant.role if participant and participant.role else "Unknown"
        is_winner = participant.is_winner if participant else False

        # Count total players
        all_participants = GameHistoryService.get_all_participants(db, game.id)
        player_count = len(all_participants)

        game_items.append(GameHistoryItem(
            game_id=game.id,
            room_name=room_name,
            started_at=game.started_at,
            finished_at=game.finished_at,
            winner=game.winner or "unknown",
            player_count=player_count,
            my_role=my_role,
            is_winner=is_winner
        ))

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
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific game.

    Requires: JWT authentication
    Permissions: User must have participated in the game
    Returns: Game detail with full player list
    """
    user_id = current_user["user_id"]

    # Get game with permission check
    game = GameHistoryService.get_game_detail(db, game_id, user_id)

    if not game:
        raise HTTPException(
            status_code=404,
            detail="Game not found or you don't have permission to view it"
        )

    # Get room name
    room_name = GameHistoryService.get_room_name(db, game.room_id) if game.room_id else "Unknown Room"

    # Get user's participant info
    participant = GameHistoryService.get_user_participant(db, game.id, user_id)
    my_role = participant.role if participant and participant.role else "Unknown"
    is_winner = participant.is_winner if participant else False

    # Get all participants
    all_participants = GameHistoryService.get_all_participants(db, game.id)

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
