import secrets

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.room import Room, RoomPlayer
from app.models.user import User
from app.schemas.room import RoomCreateRequest


MODE_MAX_PLAYERS = {"classic_9": 9, "classic_12": 12}


class RoomService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_room(self, owner: User, body: RoomCreateRequest) -> Room:
        mode = body.mode
        max_players = MODE_MAX_PLAYERS.get(mode, 9)

        if mode == "classic_12" and not body.variant:
            raise ValueError("12-player mode requires a variant (wolf_king or white_wolf_king)")

        room = Room(
            name=body.name,
            owner_id=owner.id,
            mode=mode,
            variant=body.variant,
            language=body.language,
            max_players=max_players,
            token=secrets.token_hex(32),
        )
        self.db.add(room)
        await self.db.flush()

        # Owner joins as seat 0, auto-ready
        owner_player = RoomPlayer(
            room_id=room.id, user_id=owner.id, seat=0, is_ready=True, is_ai=False
        )
        self.db.add(owner_player)
        await self.db.flush()
        await self.db.refresh(room, ["players"])
        return room

    async def list_rooms(self, page: int = 1, page_size: int = 20) -> tuple[list[Room], int]:
        offset = (page - 1) * page_size
        count_q = select(func.count()).select_from(Room).where(Room.status == "waiting")
        total = (await self.db.execute(count_q)).scalar() or 0

        q = (
            select(Room)
            .options(selectinload(Room.players))
            .where(Room.status == "waiting")
            .order_by(Room.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(q)
        rooms = list(result.scalars().all())
        return rooms, total

    async def get_room(self, room_id: int) -> Room | None:
        result = await self.db.execute(
            select(Room).options(selectinload(Room.players)).where(Room.id == room_id)
        )
        return result.scalar_one_or_none()

    async def get_room_by_token(self, token: str) -> Room | None:
        result = await self.db.execute(select(Room).where(Room.token == token))
        return result.scalar_one_or_none()

    async def join_room(self, room: Room, user: User) -> RoomPlayer:
        if room.status != "waiting":
            raise ValueError("Room is not accepting new players")

        # Check if already in room
        existing = await self.db.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.user_id == user.id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Already in this room")

        # Count current players
        count_q = select(func.count()).select_from(RoomPlayer).where(RoomPlayer.room_id == room.id)
        current = (await self.db.execute(count_q)).scalar() or 0

        if current >= room.max_players:
            raise ValueError("Room is full")

        player = RoomPlayer(
            room_id=room.id, user_id=user.id, seat=current, is_ready=False, is_ai=False
        )
        self.db.add(player)
        await self.db.flush()
        return player

    async def leave_room(self, room: Room, user: User) -> None:
        if room.owner_id == user.id:
            raise ValueError("Owner cannot leave. Delete the room instead.")
        if room.status != "waiting":
            raise ValueError("Cannot leave a room in progress")

        result = await self.db.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.user_id == user.id)
        )
        player = result.scalar_one_or_none()
        if not player:
            raise ValueError("Not in this room")

        await self.db.delete(player)
        await self.db.flush()

    async def delete_room(self, room: Room, user: User) -> None:
        if room.owner_id != user.id:
            raise ValueError("Only the owner can delete the room")
        if room.status != "waiting":
            raise ValueError("Cannot delete a room in progress")

        await self.db.delete(room)
        await self.db.flush()

    async def toggle_ready(self, room: Room, user: User) -> bool:
        if room.status != "waiting":
            raise ValueError("Cannot toggle ready in a non-waiting room")

        result = await self.db.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room.id, RoomPlayer.user_id == user.id)
        )
        player = result.scalar_one_or_none()
        if not player:
            raise ValueError("Not in this room")
        if room.owner_id == user.id:
            raise ValueError("Owner is always ready")

        player.is_ready = not player.is_ready
        await self.db.flush()
        return player.is_ready

    async def fill_ai(self, room: Room, count: int = 1, provider: str | None = None) -> list[RoomPlayer]:
        if room.status != "waiting":
            raise ValueError("Room is not accepting new players")

        current_q = select(func.count()).select_from(RoomPlayer).where(RoomPlayer.room_id == room.id)
        current = (await self.db.execute(current_q)).scalar() or 0
        available = room.max_players - current

        actual_count = min(count, available)
        if actual_count <= 0:
            raise ValueError("Room is full")

        ai_players = []
        for i in range(actual_count):
            seat = current + i
            ai = RoomPlayer(
                room_id=room.id,
                user_id=0,  # AI has no real user
                seat=seat,
                is_ready=True,
                is_ai=True,
                ai_provider=provider or "mock",
            )
            self.db.add(ai)
            ai_players.append(ai)

        await self.db.flush()
        return ai_players

    async def can_start(self, room: Room) -> bool:
        if room.status != "waiting":
            return False

        count_q = select(func.count()).select_from(RoomPlayer).where(RoomPlayer.room_id == room.id)
        total = (await self.db.execute(count_q)).scalar() or 0

        if total != room.max_players:
            return False

        ready_q = select(func.count()).select_from(RoomPlayer).where(
            RoomPlayer.room_id == room.id, RoomPlayer.is_ready == True  # noqa: E712
        )
        ready = (await self.db.execute(ready_q)).scalar() or 0
        return ready == total

    async def start_game(self, room: Room, user: User) -> int:
        if room.owner_id != user.id:
            raise ValueError("Only the owner can start the game")
        if not await self.can_start(room):
            raise ValueError("Cannot start: not all players ready or room not full")

        from app.services.game_lifecycle import GameLifecycleService
        svc = GameLifecycleService(self.db)
        game = await svc.start_game(room)
        return game.id
