"""Game history service - business logic for game history queries.

Migrated to async database access using SQLAlchemy 2.0 async API.
"""
from typing import Tuple, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, select

from app.models.game_history import GameSession, GameParticipant, GameMessage
from app.models.room import Room


class GameHistoryService:
    """Service for game history operations."""

    @staticmethod
    async def get_user_games(
        db: AsyncSession,
        user_id: str,
        winner_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[GameSession], int]:
        """
        Get user's game history with optional filtering and pagination.

        Args:
            db: Database session
            user_id: User ID to filter games
            winner_filter: Optional winner filter ("werewolf" or "villager")
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (games list, total count)
        """
        # Base WHERE conditions
        conditions = [
            GameParticipant.user_id == user_id,
            GameSession.finished_at.isnot(None),
        ]
        if winner_filter:
            conditions.append(GameSession.winner == winner_filter)

        # Count total
        count_stmt = (
            select(func.count(GameSession.id))
            .join(GameParticipant, GameSession.id == GameParticipant.game_id)
            .where(*conditions)
        )
        total = int((await db.execute(count_stmt)).scalar() or 0)

        # Fetch page
        stmt = (
            select(GameSession)
            .join(GameParticipant, GameSession.id == GameParticipant.game_id)
            .where(*conditions)
            .order_by(GameSession.finished_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        games = (await db.execute(stmt)).scalars().all()

        return (list(games), total)

    @staticmethod
    async def get_game_detail(
        db: AsyncSession,
        game_id: str,
        user_id: str
    ) -> Optional[GameSession]:
        """
        Get game detail with permission check.

        Args:
            db: Database session
            game_id: Game ID
            user_id: User ID (for permission check)

        Returns:
            GameSession if found and user has permission, None otherwise
        """
        stmt = (
            select(GameSession)
            .join(GameParticipant, GameSession.id == GameParticipant.game_id)
            .where(
                GameSession.id == game_id,
                GameParticipant.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_room_name(db: AsyncSession, room_id: str) -> str:
        """
        Get room name by room ID.

        Args:
            db: Database session
            room_id: Room ID

        Returns:
            Room name or "Unknown Room" if not found
        """
        result = await db.execute(
            select(Room).where(Room.id == room_id)
        )
        room = result.scalars().first()
        return room.name if room else "Unknown Room"

    @staticmethod
    async def get_user_participant(db: AsyncSession, game_id: str, user_id: str) -> Optional[GameParticipant]:
        """
        Get user's participant record in a game.

        Args:
            db: Database session
            game_id: Game ID
            user_id: User ID

        Returns:
            GameParticipant if found, None otherwise
        """
        result = await db.execute(
            select(GameParticipant).where(
                GameParticipant.game_id == game_id,
                GameParticipant.user_id == user_id,
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_all_participants(db: AsyncSession, game_id: str) -> List[GameParticipant]:
        """
        Get all participants of a game.

        Args:
            db: Database session
            game_id: Game ID

        Returns:
            List of GameParticipant records
        """
        result = await db.execute(
            select(GameParticipant).where(GameParticipant.game_id == game_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_game_replay_messages(
        db: AsyncSession,
        game_id: str,
        user_id: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> Optional[Tuple[List[GameMessage], int]]:
        """
        Get persisted replay messages with permission check.

        MVP scope: messages only (no actions/state snapshots).

        Args:
            db: Database session
            game_id: Game ID
            user_id: User ID (for permission check)
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            (messages, total) if user can access the game, otherwise None.
        """
        # Permission check: user must have participated in the game
        game = await GameHistoryService.get_game_detail(db, game_id, user_id)
        if not game:
            return None

        # Get total count
        count_result = await db.execute(
            select(func.count(GameMessage.id))
            .where(GameMessage.game_id == game_id)
        )
        total = int(count_result.scalar() or 0)

        # Get messages with pagination
        result = await db.execute(
            select(GameMessage)
            .where(GameMessage.game_id == game_id)
            .order_by(GameMessage.seq.asc(), GameMessage.id.asc())
            .offset(offset)
            .limit(limit)
        )
        messages = list(result.scalars().all())

        return (messages, total)
