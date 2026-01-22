"""User profile and statistics API endpoints.

Async endpoints using SQLAlchemy 2.0 async API.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database_async import get_async_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.game_history import GameParticipant
from app.schemas.auth import UserResponse
from app.schemas.user import UpdateProfileRequest, UserStatsResponse
from app.schemas.preferences import UserPreferences, UserPreferencesResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current user's profile.
    """
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_orm(user)


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update current user's profile.
    """
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check nickname uniqueness before update
    if body.nickname is not None and body.nickname != user.nickname:
        existing_result = await db.execute(
            select(User).where(User.nickname == body.nickname, User.id != user.id)
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Nickname already taken")

    # Update fields if provided
    if body.nickname is not None:
        user.nickname = body.nickname

    if body.bio is not None:
        user.bio = body.bio

    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url

    user.updated_at = datetime.utcnow()

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Nickname already taken")

    return UserResponse.from_orm(user)


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current user's game statistics.
    """
    user_id = current_user["user_id"]

    # Query game statistics
    stats_result = await db.execute(
        select(
            func.count(GameParticipant.id).label("games_played"),
            func.sum(GameParticipant.is_winner).label("games_won")
        ).where(GameParticipant.user_id == user_id)
    )
    stats = stats_result.first()

    games_played = stats.games_played or 0 if stats else 0
    games_won = int(stats.games_won or 0) if stats else 0
    win_rate = (games_won / games_played) if games_played > 0 else 0.0

    # Get recent games
    recent_result = await db.execute(
        select(GameParticipant)
        .where(GameParticipant.user_id == user_id)
        .order_by(GameParticipant.created_at.desc())
        .limit(10)
    )
    recent_participations = recent_result.scalars().all()

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


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get current user's preferences.
    Returns merged defaults for missing fields.
    """
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get preferences from DB, default to empty dict
    prefs_data = user.preferences or {}

    # Merge with defaults
    try:
        user_prefs = UserPreferences(**prefs_data)
    except Exception:
        # If parsing fails, return defaults
        user_prefs = UserPreferences()

    return UserPreferencesResponse(preferences=user_prefs)


@router.put("/me/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    body: UserPreferences,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update current user's preferences (idempotent PUT).
    Returns the updated preferences with merged defaults.
    """
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Normalize volume to 2 decimal places to reduce write churn
    prefs_dict = body.dict()
    if 'sound_effects' in prefs_dict and 'volume' in prefs_dict['sound_effects']:
        prefs_dict['sound_effects']['volume'] = round(prefs_dict['sound_effects']['volume'], 2)

    # Update preferences (MutableDict will track changes)
    user.preferences = prefs_dict
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    # Return updated preferences
    return UserPreferencesResponse(preferences=UserPreferences(**user.preferences))
