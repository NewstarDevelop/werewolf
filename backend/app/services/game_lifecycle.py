"""Game lifecycle service — orchestration layer."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game, Phase
from app.models.history import GameSession, GameParticipant
from app.models.room import Room, RoomPlayer
from app.services.game_store import GameStore


class GameLifecycleService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.store = GameStore.get_instance()

    async def start_game(self, room: Room) -> Game:
        """Start a game from a room. Caller must verify can_start."""
        result = await self.db.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id).order_by(RoomPlayer.seat)
        )
        room_players = list(result.scalars().all())

        player_data = [
            {
                "seat": rp.seat,
                "user_id": rp.user_id,
                "nickname": f"AI-{rp.seat}" if rp.is_ai else f"Player-{rp.user_id}",
                "is_ai": rp.is_ai,
                "ai_provider": rp.ai_provider,
            }
            for rp in room_players
        ]

        game = Game.from_room(
            room_id=room.id,
            game_id=room.id,
            mode=room.mode,
            player_data=player_data,
        )
        game.start()
        self.store.add(game)

        room.status = "playing"
        room.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        return game

    def get_game(self, game_id: int) -> Game | None:
        return self.store.get(game_id)

    async def end_game(self, game: Game) -> None:
        """Mark game as finished and persist results to history."""
        game.phase = Phase.GAME_OVER
        game.finished_at = datetime.now(timezone.utc).isoformat()

        # Save to history
        await self._save_history(game)

        self.store.remove(game.id)

        # Update room
        result = await self.db.execute(select(Room).where(Room.id == game.room_id))
        room = result.scalar_one_or_none()
        if room:
            room.status = "finished"
            room.finished_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def _save_history(self, game: Game) -> None:
        """Persist game results to history tables."""
        alive_count = len(game.alive_players())
        total_count = len(game.players)

        # Calculate duration
        duration = None
        if game.created_at and game.finished_at:
            try:
                start = datetime.fromisoformat(game.created_at)
                end = datetime.fromisoformat(game.finished_at)
                duration = int((end - start).total_seconds())
            except (ValueError, TypeError):
                pass

        # Serialize events
        events_json = json.dumps([
            {
                "type": e.event_type,
                "phase": e.phase.value if hasattr(e.phase, "value") else str(e.phase),
                "round": e.round_num,
                "data": e.data,
                "timestamp": e.timestamp,
            }
            for e in game.events
        ])

        session = GameSession(
            room_id=game.room_id,
            mode=game.mode,
            winner=game.winner.value if game.winner else None,
            player_count=total_count,
            rounds_played=game.round_num,
            duration_seconds=duration,
            events_json=events_json,
            finished_at=datetime.now(timezone.utc),
        )
        self.db.add(session)
        await self.db.flush()

        # Save participants
        for p in game.players:
            participant = GameParticipant(
                session_id=session.id,
                seat=p.seat,
                user_id=p.user_id,
                nickname=p.nickname,
                role=p.role.value if p.role else "unknown",
                faction=p.faction.value if hasattr(p.faction, "value") else str(p.faction),
                is_ai=p.is_ai,
                survived=p.alive,
            )
            self.db.add(participant)

        await self.db.flush()
