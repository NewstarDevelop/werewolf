"""Game history service - business logic for game history queries."""
from typing import Tuple, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.game_history import GameSession, GameParticipant
from app.models.room import Room


class GameHistoryService:
    """Service for game history operations."""

    @staticmethod
    def get_user_games(
        db: Session,
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
        # Base query: games that user participated in and are finished
        query = db.query(GameSession).join(
            GameParticipant,
            GameSession.id == GameParticipant.game_id
        ).filter(
            and_(
                GameParticipant.user_id == user_id,
                GameSession.finished_at.isnot(None)
            )
        )

        # Apply winner filter if specified
        if winner_filter:
            query = query.filter(GameSession.winner == winner_filter)

        # Get total count before pagination
        total = query.count()

        # Apply pagination and ordering
        games = query.order_by(GameSession.finished_at.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        return (games, total)

    @staticmethod
    def get_game_detail(
        db: Session,
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
        # Query game and verify user participated
        game = db.query(GameSession).join(
            GameParticipant,
            GameSession.id == GameParticipant.game_id
        ).filter(
            and_(
                GameSession.id == game_id,
                GameParticipant.user_id == user_id
            )
        ).first()

        return game

    @staticmethod
    def get_room_name(db: Session, room_id: str) -> str:
        """
        Get room name by room ID.

        Args:
            db: Database session
            room_id: Room ID

        Returns:
            Room name or "Unknown Room" if not found
        """
        room = db.query(Room).filter(Room.id == room_id).first()
        return room.name if room else "Unknown Room"

    @staticmethod
    def get_user_participant(db: Session, game_id: str, user_id: str) -> Optional[GameParticipant]:
        """
        Get user's participant record in a game.

        Args:
            db: Database session
            game_id: Game ID
            user_id: User ID

        Returns:
            GameParticipant if found, None otherwise
        """
        return db.query(GameParticipant).filter(
            and_(
                GameParticipant.game_id == game_id,
                GameParticipant.user_id == user_id
            )
        ).first()

    @staticmethod
    def get_all_participants(db: Session, game_id: str) -> List[GameParticipant]:
        """
        Get all participants of a game.

        Args:
            db: Database session
            game_id: Game ID

        Returns:
            List of GameParticipant records
        """
        return db.query(GameParticipant).filter(
            GameParticipant.game_id == game_id
        ).all()
