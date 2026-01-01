"""User profile and statistics API endpoints."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.game_history import GameParticipant
from app.schemas.auth import UserResponse
from app.schemas.user import UpdateProfileRequest, UserStatsResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's profile.
    """
    user = db.query(User).get(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_orm(user)


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile.
    """
    user = db.query(User).get(current_user["user_id"])

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields if provided
    if body.nickname is not None:
        user.nickname = body.nickname

    if body.bio is not None:
        user.bio = body.bio

    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url

    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    return UserResponse.from_orm(user)


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's game statistics.
    """
    user_id = current_user["user_id"]

    # Query game statistics
    stats = db.query(
        func.count(GameParticipant.id).label("games_played"),
        func.sum(func.cast(GameParticipant.is_winner, db.bind.dialect.type_descriptor(int))).label("games_won")
    ).filter(
        GameParticipant.user_id == user_id
    ).first()

    games_played = stats.games_played or 0
    games_won = int(stats.games_won or 0)
    win_rate = (games_won / games_played) if games_played > 0 else 0.0

    # Get recent games
    recent_participations = db.query(GameParticipant).filter(
        GameParticipant.user_id == user_id
    ).order_by(
        GameParticipant.created_at.desc()
    ).limit(10).all()

    recent_games = [
        {
            "game_id": p.game_id,
            "seat_id": p.seat_id,
            "role": p.role,
            "is_winner": p.is_winner,
            "created_at": p.created_at.isoformat() if p.created_at else None
        }
        for p in recent_participations
    ]

    return UserStatsResponse(
        games_played=games_played,
        games_won=games_won,
        win_rate=round(win_rate, 3),
        recent_games=recent_games
    )
