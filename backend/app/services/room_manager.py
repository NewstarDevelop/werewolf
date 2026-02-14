"""Room management service - handles room CRUD operations.

Async implementation using SQLAlchemy 2.0 async API.
"""
import asyncio
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, OperationalError
from app.models.room import Room, RoomPlayer, RoomStatus
from app.models.game import game_store, WOLF_ROLES
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class RoomManager:
    """房间管理服务 - 负责房间的创建、查询、加入、准备、开始等操作"""

    async def create_room(
        self,
        db: AsyncSession,
        name: str,
        creator_nickname: str,
        creator_id: str,
        user_id: str,
        game_mode: str = "classic_9",
        wolf_king_variant: Optional[str] = None,
        language: str = "zh",
        max_players: int = 9
    ) -> Room:
        """创建房间并添加创建者为第一个玩家

        Args:
            user_id: 创建者用户ID（必需，用户必须登录才能创建房间）
        """
        room_id = str(uuid.uuid4())

        # 创建房间记录
        room = Room(
            id=room_id,
            name=name,
            creator_user_id=user_id,  # 记录创建者用户ID
            creator_nickname=creator_nickname,
            status=RoomStatus.WAITING,
            current_players=1,
            max_players=max_players,
            game_mode=game_mode,
            wolf_king_variant=wolf_king_variant,
            language=language
        )
        db.add(room)

        # 添加创建者为第一个玩家
        player = RoomPlayer(
            room_id=room_id,
            player_id=creator_id,
            user_id=user_id,  # Link to user if authenticated
            nickname=creator_nickname,
            is_creator=True,
            is_ready=True  # 创建者自动准备
        )
        db.add(player)

        await db.commit()
        await db.refresh(room)

        logger.info(f"Room created: {room_id} by {creator_nickname} (user_id={user_id})")
        return room

    async def get_rooms(
        self,
        db: AsyncSession,
        status: Optional[RoomStatus] = None,
        limit: int = 50
    ) -> List[Room]:
        """获取房间列表（可按状态筛选）"""
        stmt = select(Room)

        if status:
            stmt = stmt.where(Room.status == status)

        stmt = stmt.order_by(Room.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_room(self, db: AsyncSession, room_id: str) -> Optional[Room]:
        """获取单个房间详情"""
        result = await db.execute(select(Room).where(Room.id == room_id))
        return result.scalar_one_or_none()

    async def get_room_players(self, db: AsyncSession, room_id: str) -> List[RoomPlayer]:
        """获取房间内的所有玩家"""
        result = await db.execute(
            select(RoomPlayer)
            .where(RoomPlayer.room_id == room_id)
            .order_by(RoomPlayer.joined_at)
        )
        return list(result.scalars().all())

    async def join_room(
        self,
        db: AsyncSession,
        room_id: str,
        player_id: str,
        nickname: str,
        user_id: Optional[str] = None
    ) -> RoomPlayer:
        """加入房间

        T-STAB-004: Improved concurrency handling:
        - Derive player count from RoomPlayer table instead of maintaining counter
        - UniqueConstraint on (room_id, player_id) prevents duplicate joins

        P1-STAB-002: Added retry logic for SQLite concurrency:
        - Handles IntegrityError from unique constraint violation
        - Retries on database lock errors
        """
        max_retries = 5  # Increased from 3 to handle higher concurrency
        retry_delay = 0.2  # Increased base delay from 100ms to 200ms

        for attempt in range(max_retries):
            try:
                # Get room (no FOR UPDATE needed for SQLite - not supported)
                result = await db.execute(select(Room).where(Room.id == room_id))
                room = result.scalar_one_or_none()
                if not room:
                    raise ValueError("房间不存在")

                if room.status != RoomStatus.WAITING:
                    raise ValueError("房间已开始游戏，无法加入")

                # 对已登录用户，检查user_id是否已在房间
                # FIX: 如果用户已在房间中，返回现有记录而不是抛出错误
                # 这样用户可以重新获取 room token（解决返回大厅后丢失权限的问题）
                if user_id:
                    existing_result = await db.execute(
                        select(RoomPlayer).where(
                            RoomPlayer.room_id == room_id,
                            RoomPlayer.user_id == user_id
                        )
                    )
                    existing_user = existing_result.scalar_one_or_none()
                    if existing_user:
                        logger.info(f"User {user_id} reconnecting to room {room_id}, returning existing player")
                        return existing_user

                # 检查是否已加入
                existing_result = await db.execute(
                    select(RoomPlayer).where(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.player_id == player_id
                    )
                )
                existing = existing_result.scalar_one_or_none()
                if existing:
                    logger.info(f"Player {player_id} already in room {room_id}")
                    return existing

                # T-STAB-004: Derive player count from actual RoomPlayer records
                count_result = await db.execute(
                    select(func.count(RoomPlayer.id)).where(RoomPlayer.room_id == room_id)
                )
                current_count = count_result.scalar() or 0

                if current_count >= room.max_players:
                    raise ValueError("房间已满")

                # 添加玩家
                player = RoomPlayer(
                    room_id=room_id,
                    player_id=player_id,
                    user_id=user_id,  # Link to user if authenticated
                    nickname=nickname,
                    is_ready=False
                )
                db.add(player)

                # T-STAB-004: Update current_players to match actual count (for backward compatibility)
                room.current_players = current_count + 1
                await db.commit()
                await db.refresh(player)

                logger.info(f"Player {nickname} joined room {room_id}")
                return player

            except IntegrityError:
                # P1-STAB-002: Unique constraint violation - player already joined in a race
                await db.rollback()
                # Check if player now exists (race condition resolved)
                existing_result = await db.execute(
                    select(RoomPlayer).where(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.player_id == player_id
                    )
                )
                existing = existing_result.scalar_one_or_none()
                if existing:
                    logger.info(f"Player {player_id} joined room {room_id} (race resolved)")
                    return existing
                raise ValueError("加入房间失败，请重试")

            except OperationalError:
                # P1-STAB-002: Database locked - retry with exponential backoff
                await db.rollback()
                if attempt < max_retries - 1:
                    # Exponential backoff: 0.2s, 0.4s, 0.8s, 1.6s, 3.2s
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Database locked on join_room attempt {attempt + 1}/{max_retries}, "
                        f"retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise ValueError("服务器繁忙，请稍后重试")

        raise ValueError("加入房间失败，请重试")

    async def leave_room(
        self,
        db: AsyncSession,
        room_id: str,
        player_id: str
    ) -> dict:
        """玩家退出房间

        与 join_room 对称的并发处理：
        - 真实计数回写 current_players
        - 处理 OperationalError 并重试

        Args:
            player_id: 退出房间的玩家ID

        Returns:
            dict: 包含 nickname 和 current_players 信息用于广播

        Raises:
            ValueError: 房间不存在、游戏已开始、房主尝试离开
        """
        max_retries = 5
        retry_delay = 0.2

        for attempt in range(max_retries):
            try:
                # Get room
                room_result = await db.execute(select(Room).where(Room.id == room_id))
                room = room_result.scalar_one_or_none()
                if not room:
                    raise ValueError("房间不存在")

                # Get player first for idempotency check
                player_result = await db.execute(
                    select(RoomPlayer).where(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.player_id == player_id
                    )
                )
                player = player_result.scalar_one_or_none()

                if not player:
                    # Player already gone, consider success (幂等性)
                    # 重算真实计数以确保一致性
                    count_result = await db.execute(
                        select(func.count(RoomPlayer.id)).where(RoomPlayer.room_id == room_id)
                    )
                    current_count = count_result.scalar() or 0
                    if room.current_players != current_count:
                        room.current_players = current_count
                        await db.commit()
                    return {"nickname": "Unknown", "current_players": current_count}

                # Check room status after confirming player exists
                if room.status != RoomStatus.WAITING:
                    raise ValueError("游戏已开始，无法退出")

                # Creator cannot leave, must delete room
                if player.is_creator:
                    raise ValueError("房主无法退出房间，请使用删除房间功能")

                # 保存昵称用于广播
                nickname = player.nickname

                # Remove player
                await db.delete(player)
                await db.flush()  # Ensure delete is processed for the transaction

                # Update player count (真实计数回写)
                count_result = await db.execute(
                    select(func.count(RoomPlayer.id)).where(RoomPlayer.room_id == room_id)
                )
                current_count = count_result.scalar() or 0

                room.current_players = current_count
                await db.commit()

                logger.info(f"Player {nickname} left room {room_id}")
                return {"nickname": nickname, "current_players": current_count}

            except OperationalError:
                # Database locked - retry with exponential backoff
                await db.rollback()
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Database locked on leave_room attempt {attempt + 1}/{max_retries}, "
                        f"retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise ValueError("服务器繁忙，请稍后重试")

        raise ValueError("退出房间失败，请重试")

    async def toggle_ready(
        self,
        db: AsyncSession,
        room_id: str,
        player_id: str
    ) -> bool:
        """切换玩家准备状态，返回新状态

        BUG-FIX: Added retry logic for SQLite concurrency, matching
        join_room/leave_room patterns to prevent OperationalError under load.
        """
        max_retries = 5
        retry_delay = 0.2

        for attempt in range(max_retries):
            try:
                result = await db.execute(
                    select(RoomPlayer).where(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.player_id == player_id
                    )
                )
                player = result.scalar_one_or_none()

                if not player:
                    raise ValueError("玩家未加入房间")

                player.is_ready = not player.is_ready
                await db.commit()

                logger.info(f"Player {player.nickname} ready status: {player.is_ready}")
                return player.is_ready

            except OperationalError:
                await db.rollback()
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Database locked on toggle_ready attempt {attempt + 1}/{max_retries}, "
                        f"retrying in {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise ValueError("服务器繁忙，请稍后重试")

        raise ValueError("操作失败，请重试")

    async def start_game(
        self,
        db: AsyncSession,
        room_id: str,
        player_id: str,
        fill_ai: bool = False
    ) -> str:
        """开始游戏（仅房主可调用）

        Args:
            db: 数据库会话
            room_id: 房间ID
            player_id: 玩家ID（必须是房主）
            fill_ai: 是否填充AI（True=允许少于9人，剩余座位自动填充AI）
        """
        # Get room
        room_result = await db.execute(select(Room).where(Room.id == room_id))
        room = room_result.scalar_one_or_none()
        if not room:
            raise ValueError("房间不存在")

        # 检查是否为创建者
        creator_result = await db.execute(
            select(RoomPlayer).where(
                RoomPlayer.room_id == room_id,
                RoomPlayer.player_id == player_id,
                RoomPlayer.is_creator == True
            )
        )
        creator = creator_result.scalar_one_or_none()
        if not creator:
            raise ValueError("只有房主可以开始游戏")

        # 获取所有玩家
        players_result = await db.execute(
            select(RoomPlayer)
            .where(RoomPlayer.room_id == room_id)
            .order_by(RoomPlayer.joined_at)
        )
        players = list(players_result.scalars().all())

        # DEBUG: Log fill_ai parameter
        logger.info(f"start_game called: room={room_id}, fill_ai={fill_ai}, players={len(players)}, max_players={room.max_players}")

        # 检查人数（如果不填充AI，必须满足房间最大人数）
        if not fill_ai:
            if len(players) < room.max_players:
                raise ValueError(f"人数不足，当前{len(players)}/{room.max_players}人")

            # 检查所有玩家是否准备
            if not all(p.is_ready for p in players):
                unready = [p.nickname for p in players if not p.is_ready]
                raise ValueError(f"还有玩家未准备: {', '.join(unready)}")
        else:
            # 填充AI模式：至少需要1个真人玩家
            if len(players) < 1:
                raise ValueError("至少需要1个玩家")

        # 分配座位号（按加入顺序）
        for idx, player in enumerate(players, start=1):
            player.seat_id = idx

        # WL-008 Fix: 创建支持多人的游戏实例
        # 使用room_id作为game_id，建立玩家到座位的映射
        # Determine game config based on max_players
        from app.models.game import CLASSIC_9_CONFIG, get_classic_12_config
        if room.max_players == 9:
            game_config = CLASSIC_9_CONFIG
        elif room.max_players == 12:
            # Phase 8 Fix: Read wolf_king_variant from room instead of hardcoded value
            if not room.wolf_king_variant:
                raise ValueError("12人模式必须指定狼王类型")
            game_config = get_classic_12_config(room.wolf_king_variant)
        else:
            raise ValueError(f"Unsupported max_players: {room.max_players}")

        game = game_store.create_game(
            human_seat=1 if players else 1,  # Deprecated, kept for compatibility
            human_role=None,  # 随机角色
            language=room.language,
            game_id=room_id,  # 使用room_id作为game_id
            config=game_config
        )

        # 设置多人对局映射
        human_seats = []
        player_mapping = {}

        if fill_ai:
            # AI填充模式：只有已准备的真人玩家占用座位
            ready_players = [p for p in players if p.is_ready]
            for p in ready_players:
                human_seats.append(p.seat_id)
                player_mapping[p.player_id] = p.seat_id
                # WL-BUG-001 Fix: Also map user_id for cookie-based auth fallback
                if p.user_id:
                    player_mapping[p.user_id] = p.seat_id
        else:
            # 多人模式：所有玩家都是真人
            for p in players:
                human_seats.append(p.seat_id)
                player_mapping[p.player_id] = p.seat_id
                # WL-BUG-001 Fix: Also map user_id for cookie-based auth fallback
                if p.user_id:
                    player_mapping[p.user_id] = p.seat_id

        game.human_seats = human_seats
        game.player_mapping = player_mapping

        # T-STAB-001 Fix: Sync Player.is_human with human_seats for multi-player games
        # This ensures game_engine phase handlers correctly identify human players
        for seat_id in range(1, room.max_players + 1):
            game_player = game.get_player(seat_id)
            if game_player:
                game_player.is_human = (seat_id in human_seats)

        # 更新房间状态
        room.status = RoomStatus.PLAYING
        room.started_at = datetime.now(timezone.utc)
        await db.commit()

        mode = "AI填充模式" if fill_ai else "多人模式"
        ai_count = room.max_players - len(human_seats)
        logger.info(f"Game started in room {room_id} ({mode}, {len(human_seats)} humans, {ai_count} AI)")
        return room_id

    async def finish_game(self, db: AsyncSession, room_id: str):
        """游戏结束，更新房间状态并记录游戏历史"""
        from app.models.game_history import GameSession, GameParticipant, GameMessage
        from app.schemas.enums import Winner, MessageType

        # 幂等性检查：防止重复处理
        existing_result = await db.execute(
            select(GameSession).where(GameSession.id == room_id)
        )
        if existing_result.scalar_one_or_none():
            logger.warning(f"Game session already exists for room {room_id}, skipping")
            return

        # 使用状态条件查询防止竞态条件
        room_result = await db.execute(
            select(Room).where(
                Room.id == room_id,
                Room.status != RoomStatus.FINISHED  # 只处理未完成的游戏
            )
        )
        room = room_result.scalar_one_or_none()
        if not room:
            logger.info(f"Room {room_id} not found or already finished, skipping")
            return

        # 更新房间状态
        room.status = RoomStatus.FINISHED
        room.finished_at = datetime.now(timezone.utc)

        # 获取游戏实例
        game = game_store.get_game(room_id)
        if game and game.winner:
            # 记录游戏会话
            session = GameSession(
                id=room_id,  # 使用 room_id 作为主键，确保关联正确
                room_id=room_id,
                started_at=room.started_at or datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                winner=game.winner.value
            )
            db.add(session)

            # 获取房间玩家映射（用于获取用户信息）
            players_result = await db.execute(
                select(RoomPlayer).where(RoomPlayer.room_id == room_id)
            )
            room_players_map = {
                p.seat_id: p for p in players_result.scalars().all()
            }

            # 遍历所有游戏内的座位（包括AI玩家），确保历史记录完整
            for seat_id in range(1, room.max_players + 1):
                game_player = game.get_player(seat_id)
                if not game_player:
                    continue

                # 获取对应的房间玩家信息（真人玩家有记录，AI玩家为None）
                room_player = room_players_map.get(seat_id)

                # 判断是否获胜（支持平局）
                is_wolf = game_player.role in WOLF_ROLES
                if game.winner == Winner.WEREWOLF:
                    is_winner = is_wolf
                elif game.winner == Winner.VILLAGER:
                    is_winner = not is_wolf
                elif game.winner == Winner.DRAW:
                    # 平局时所有人都标记为未获胜
                    is_winner = False
                else:
                    is_winner = False

                # 构造参与者字段：区分真人玩家和AI玩家
                is_ai = not game_player.is_human

                if is_ai:
                    participant_user_id = None
                    participant_player_id = str(uuid.uuid4())
                    participant_nickname = (
                        game_player.personality.name
                        if game_player.personality and game_player.personality.name
                        else f"AI_{seat_id}"
                    )
                else:
                    if room_player:
                        participant_user_id = room_player.user_id
                        participant_player_id = room_player.player_id
                        participant_nickname = room_player.nickname
                    else:
                        participant_user_id = None
                        participant_player_id = str(uuid.uuid4())
                        participant_nickname = f"Player_{seat_id}"

                participant = GameParticipant(
                    game_id=session.id,
                    user_id=participant_user_id,
                    player_id=participant_player_id,
                    seat_id=seat_id,
                    nickname=participant_nickname,
                    is_ai=is_ai,
                    role=game_player.role.value,
                    is_winner=is_winner
                )
                db.add(participant)

            # MVP: 持久化消息记录用于回放（排除内部投票思考）
            if game.messages:
                persisted_messages = []
                for msg in game.messages:
                    # 过滤内部投票思考消息
                    if msg.msg_type == MessageType.VOTE_THOUGHT:
                        continue
                    persisted_messages.append(
                        GameMessage(
                            game_id=session.id,
                            seq=msg.id,
                            day=msg.day,
                            seat_id=msg.seat_id,
                            content=msg.content,
                            msg_type=msg.msg_type.value,
                        )
                    )
                db.add_all(persisted_messages)

        await db.commit()
        logger.info(f"Game finished in room {room_id}")

    async def delete_room(self, db: AsyncSession, room_id: str) -> bool:
        """删除房间及其所有玩家记录"""
        # 删除玩家记录
        await db.execute(
            delete(RoomPlayer).where(RoomPlayer.room_id == room_id)
        )

        # 删除房间记录
        room_result = await db.execute(select(Room).where(Room.id == room_id))
        room = room_result.scalar_one_or_none()
        if room:
            await db.delete(room)
            await db.commit()
            logger.info(f"Room deleted: {room_id}")
            return True
        return False

    async def reset_orphaned_rooms(self, db: AsyncSession) -> int:
        """
        WL-011 Fix: 重启后恢复孤立房间状态

        将 PLAYING 状态且内存中无对应 game 对象的房间回滚到 WAITING。
        如果 game 对象已从快照恢复，则跳过该房间。

        Returns:
            重置的房间数量
        """
        from app.models.game import game_store

        # Query all PLAYING rooms
        result = await db.execute(
            select(Room).where(Room.status == RoomStatus.PLAYING)
        )
        playing_rooms = list(result.scalars().all())

        if not playing_rooms:
            logger.info("No orphaned rooms found on startup")
            return 0

        reset_count = 0
        for room in playing_rooms:
            # Skip rooms whose game was recovered from persistence snapshots
            if game_store.get_game(room.id) is not None:
                logger.info(
                    f"Room {room.id} ('{room.name}') has recovered game state, skipping reset"
                )
                continue

            # Reset room status
            room.status = RoomStatus.WAITING
            room.started_at = None
            room.finished_at = None

            # Reset player ready status (except creator)
            players_result = await db.execute(
                select(RoomPlayer).where(RoomPlayer.room_id == room.id)
            )
            players = players_result.scalars().all()

            for player in players:
                if not player.is_creator:
                    player.is_ready = False

            reset_count += 1
            logger.warning(
                f"Reset orphaned room {room.id} ('{room.name}') from PLAYING to WAITING. "
                f"Game state was lost due to server restart."
            )

        if reset_count > 0:
            await db.commit()
        logger.info(f"Reset {reset_count} orphaned rooms on startup")
        return reset_count


# 全局实例
room_manager = RoomManager()
