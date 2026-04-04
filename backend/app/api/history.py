from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.history import GameSession, GameParticipant
from app.models.user import User
from app.schemas.history import HistoryDetail, HistoryListItem, HistoryListResponse, HistoryParticipant

router = APIRouter(prefix="/game-history", tags=["history"])


@router.get("/", response_model=HistoryListResponse)
async def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List completed game sessions for the current user."""
    count_q = (
        select(func.count())
        .select_from(GameSession)
        .join(GameParticipant, GameParticipant.session_id == GameSession.id)
        .where(GameParticipant.user_id == user.id)
    )
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    q = (
        select(GameSession)
        .join(GameParticipant, GameParticipant.session_id == GameSession.id)
        .where(GameParticipant.user_id == user.id)
        .order_by(GameSession.finished_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(q)
    sessions = list(result.scalars().all())

    items = []
    for s in sessions:
        items.append(HistoryListItem(
            id=s.id,
            room_id=s.room_id,
            mode=s.mode,
            winner=s.winner,
            player_count=s.player_count,
            duration_seconds=s.duration_seconds,
            finished_at=s.finished_at,
        ))

    return HistoryListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{session_id}", response_model=HistoryDetail)
async def get_history(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a completed game session."""
    session = (await db.execute(
        select(GameSession).where(GameSession.id == session_id)
    )).scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Game session not found")

    # Check user participated
    participant = (await db.execute(
        select(GameParticipant).where(
            GameParticipant.session_id == session_id,
            GameParticipant.user_id == user.id,
        )
    )).scalar_one_or_none()

    if not participant and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not a participant")

    # Get all participants
    result = await db.execute(
        select(GameParticipant)
        .where(GameParticipant.session_id == session_id)
        .order_by(GameParticipant.seat)
    )
    participants = [
        HistoryParticipant(
            seat=p.seat,
            nickname=p.nickname,
            role=p.role,
            faction=p.faction,
            is_ai=p.is_ai,
            survived=p.survived,
        )
        for p in result.scalars().all()
    ]

    import json
    events = json.loads(session.events_json) if session.events_json else []

    return HistoryDetail(
        id=session.id,
        room_id=session.room_id,
        mode=session.mode,
        winner=session.winner,
        player_count=session.player_count,
        duration_seconds=session.duration_seconds,
        finished_at=session.finished_at,
        participants=participants,
        events=events,
    )
