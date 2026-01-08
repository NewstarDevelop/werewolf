"""Room management service - handles room CRUD operations."""
from sqlalchemy.orm import Session
from app.models.room import Room, RoomPlayer, RoomStatus
from app.models.game import game_store
from typing import List, Optional
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class RoomManager:
    """房间管理服务 - 负责房间的创建、查询、加入、准备、开始等操作"""

    def create_room(
        self,
        db: Session,
        name: str,
        creator_nickname: str,
        creator_id: str,
        user_id: Optional[str] = None,
        game_mode: str = "classic_9",
        wolf_king_variant: Optional[str] = None,
        language: str = "zh",
        max_players: int = 9
    ) -> Room:
        """创建房间并添加创建者为第一个玩家

        Phase 8 Fix: Added game_mode and wolf_king_variant parameters.
        """
        room_id = str(uuid.uuid4())[:8]

        # 创建房间记录
        room = Room(
            id=room_id,
            name=name,
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

        db.commit()
        db.refresh(room)

        logger.info(f"Room created: {room_id} by {creator_nickname} (user_id={user_id})")
        return room

    def get_rooms(
        self,
        db: Session,
        status: Optional[RoomStatus] = None,
        limit: int = 50
    ) -> List[Room]:
        """获取房间列表（可按状态筛选）"""
        query = db.query(Room)

        if status:
            query = query.filter(Room.status == status)

        return query.order_by(Room.created_at.desc()).limit(limit).all()

    def get_room(self, db: Session, room_id: str) -> Optional[Room]:
        """获取单个房间详情"""
        return db.query(Room).filter(Room.id == room_id).first()

    def get_room_players(self, db: Session, room_id: str) -> List[RoomPlayer]:
        """获取房间内的所有玩家"""
        return db.query(RoomPlayer).filter(
            RoomPlayer.room_id == room_id
        ).order_by(RoomPlayer.joined_at).all()

    def join_room(
        self,
        db: Session,
        room_id: str,
        player_id: str,
        nickname: str,
        user_id: Optional[str] = None
    ) -> RoomPlayer:
        """加入房间

        T-STAB-004: Improved concurrency handling:
        - Use SELECT FOR UPDATE to lock room row
        - Derive player count from RoomPlayer table instead of maintaining counter
        - UniqueConstraint on (room_id, player_id) prevents duplicate joins

        P1-STAB-002: Added retry logic for SQLite concurrency:
        - Handles IntegrityError from unique constraint violation
        - Retries on database lock errors
        """
        from sqlalchemy.exc import IntegrityError, OperationalError
        import time

        max_retries = 5  # Increased from 3 to handle higher concurrency
        retry_delay = 0.2  # Increased base delay from 100ms to 200ms

        for attempt in range(max_retries):
            try:
                # Lock room row to prevent concurrent join race conditions
                room = db.query(Room).filter(Room.id == room_id).with_for_update().first()
                if not room:
                    raise ValueError("房间不存在")

                if room.status != RoomStatus.WAITING:
                    raise ValueError("房间已开始游戏，无法加入")

                # 对已登录用户，检查user_id是否已在房间（防止重复加入）
                if user_id:
                    existing_user = db.query(RoomPlayer).filter(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.user_id == user_id
                    ).first()
                    if existing_user:
                        raise ValueError(f"您已在该房间中（房间ID: {room_id}），无法重复加入")

                # 检查是否已加入
                existing = db.query(RoomPlayer).filter(
                    RoomPlayer.room_id == room_id,
                    RoomPlayer.player_id == player_id
                ).first()
                if existing:
                    logger.info(f"Player {player_id} already in room {room_id}")
                    return existing

                # T-STAB-004: Derive player count from actual RoomPlayer records
                current_count = db.query(RoomPlayer).filter(
                    RoomPlayer.room_id == room_id
                ).count()

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
                db.commit()
                db.refresh(player)

                logger.info(f"Player {nickname} joined room {room_id}")
                return player

            except IntegrityError as e:
                # P1-STAB-002: Unique constraint violation - player already joined in a race
                db.rollback()
                # Check if player now exists (race condition resolved)
                existing = db.query(RoomPlayer).filter(
                    RoomPlayer.room_id == room_id,
                    RoomPlayer.player_id == player_id
                ).first()
                if existing:
                    logger.info(f"Player {player_id} joined room {room_id} (race resolved)")
                    return existing
                raise ValueError("加入房间失败，请重试")

            except OperationalError as e:
                # P1-STAB-002: Database locked - retry with exponential backoff
                db.rollback()
                if attempt < max_retries - 1:
                    # Exponential backoff: 0.2s, 0.4s, 0.8s, 1.6s, 3.2s
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Database locked on join_room attempt {attempt + 1}/{max_retries}, "
                        f"retrying in {wait_time:.2f}s..."
                    )
                    time.sleep(wait_time)
                    continue
                raise ValueError("服务器繁忙，请稍后重试")

        raise ValueError("加入房间失败，请重试")

    def toggle_ready(
        self,
        db: Session,
        room_id: str,
        player_id: str
    ) -> bool:
        """切换玩家准备状态，返回新状态"""
        player = db.query(RoomPlayer).filter(
            RoomPlayer.room_id == room_id,
            RoomPlayer.player_id == player_id
        ).first()

        if not player:
            raise ValueError("玩家未加入房间")

        player.is_ready = not player.is_ready
        db.commit()

        logger.info(f"Player {player.nickname} ready status: {player.is_ready}")
        return player.is_ready

    def start_game(
        self,
        db: Session,
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

        P1-1 Fix: Use SELECT FOR UPDATE to prevent concurrent start_game race condition.
        """
        # Lock room row to prevent concurrent start race conditions
        room = db.query(Room).filter(Room.id == room_id).with_for_update().first()
        if not room:
            raise ValueError("房间不存在")

        # 检查是否为创建者
        creator = db.query(RoomPlayer).filter(
            RoomPlayer.room_id == room_id,
            RoomPlayer.player_id == player_id,
            RoomPlayer.is_creator == True
        ).first()
        if not creator:
            raise ValueError("只有房主可以开始游戏")

        # 获取所有玩家
        players = db.query(RoomPlayer).filter(
            RoomPlayer.room_id == room_id
        ).order_by(RoomPlayer.joined_at).all()

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
        else:
            # 多人模式：所有玩家都是真人
            for p in players:
                human_seats.append(p.seat_id)
                player_mapping[p.player_id] = p.seat_id

        game.human_seats = human_seats
        game.player_mapping = player_mapping

        # T-STAB-001 Fix: Sync Player.is_human with human_seats for multi-player games
        # This ensures game_engine phase handlers correctly identify human players
        for seat_id in range(1, room.max_players + 1):
            player = game.get_player(seat_id)
            if player:
                player.is_human = (seat_id in human_seats)

        # 更新房间状态
        room.status = RoomStatus.PLAYING
        room.started_at = datetime.utcnow()
        db.commit()

        mode = "AI填充模式" if fill_ai else "多人模式"
        ai_count = room.max_players - len(human_seats)
        logger.info(f"Game started in room {room_id} ({mode}, {len(human_seats)} humans, {ai_count} AI)")
        return room_id

    def finish_game(self, db: Session, room_id: str):
        """游戏结束，更新房间状态并记录游戏历史"""
        from app.models.game_history import GameSession, GameParticipant
        from app.schemas.enums import Winner, RoomStatus

        # 幂等性检查：防止重复处理
        existing_session = db.query(GameSession).filter_by(id=room_id).first()
        if existing_session:
            logger.warning(f"Game session already exists for room {room_id}, skipping")
            return

        # 使用状态条件查询防止竞态条件
        room = db.query(Room).filter(
            Room.id == room_id,
            Room.status != RoomStatus.FINISHED  # 只处理未完成的游戏
        ).first()
        if not room:
            logger.info(f"Room {room_id} not found or already finished, skipping")
            return

        # 更新房间状态
        room.status = RoomStatus.FINISHED
        room.finished_at = datetime.utcnow()

        # 获取游戏实例
        game = game_store.get_game(room_id)
        if game and game.winner:
            # 记录游戏会话
            session = GameSession(
                id=room_id,  # 使用 room_id 作为主键，确保关联正确
                room_id=room_id,
                started_at=room.started_at or datetime.utcnow(),
                finished_at=datetime.utcnow(),
                winner=game.winner.value
            )
            db.add(session)

            # 获取房间玩家映射（用于获取用户信息）
            room_players_map = {
                p.seat_id: p for p in db.query(RoomPlayer).filter(
                    RoomPlayer.room_id == room_id
                ).all()
            }

            # 遍历所有游戏内的座位（包括AI玩家），确保历史记录完整
            for seat_id in range(1, room.max_players + 1):
                game_player = game.get_player(seat_id)
                if not game_player:
                    continue

                # 获取对应的房间玩家信息（真人玩家有记录，AI玩家为None）
                room_player = room_players_map.get(seat_id)

                # 判断是否获胜（支持平局）
                is_winner = False
                if game.winner == Winner.WEREWOLF:
                    is_winner = game_player.role.is_werewolf()
                elif game.winner == Winner.VILLAGER:
                    is_winner = not game_player.role.is_werewolf()
                elif game.winner == Winner.DRAW:
                    # 平局时所有人都标记为未获胜
                    is_winner = False

                participant = GameParticipant(
                    game_id=session.id,  # 修正：使用 game_id 字段
                    user_id=room_player.user_id if room_player else None,  # AI玩家为None
                    player_id=game_player.player_id,  # 补充：player_id 字段
                    seat_id=seat_id,
                    nickname=game_player.nickname,  # 补充：nickname 字段（从游戏内获取）
                    is_ai=game_player.is_ai,  # 补充：is_ai 字段（从游戏内获取）
                    role=game_player.role.value,
                    is_winner=is_winner
                )
                db.add(participant)

        db.commit()
        logger.info(f"Game finished in room {room_id}")

    def delete_room(self, db: Session, room_id: str) -> bool:
        """删除房间及其所有玩家记录"""
        # 删除玩家记录
        db.query(RoomPlayer).filter(RoomPlayer.room_id == room_id).delete()

        # 删除房间记录
        room = db.query(Room).filter(Room.id == room_id).first()
        if room:
            db.delete(room)
            db.commit()
            logger.info(f"Room deleted: {room_id}")
            return True
        return False

    def reset_orphaned_rooms(self, db: Session) -> int:
        """
        WL-011 Fix: 重启后恢复孤立房间状态

        将所有 PLAYING 状态的房间回滚到 WAITING，因为重启后
        内存中的 game 对象已丢失，无法继续游戏。

        Returns:
            重置的房间数量
        """
        # 查询所有 PLAYING 状态的房间
        playing_rooms = db.query(Room).filter(
            Room.status == RoomStatus.PLAYING
        ).all()

        if not playing_rooms:
            logger.info("No orphaned rooms found on startup")
            return 0

        reset_count = 0
        for room in playing_rooms:
            # 重置房间状态
            room.status = RoomStatus.WAITING
            room.started_at = None
            room.finished_at = None

            # 重置所有玩家的准备状态（房主除外保持准备）
            players = db.query(RoomPlayer).filter(
                RoomPlayer.room_id == room.id
            ).all()

            for player in players:
                if not player.is_creator:
                    player.is_ready = False

            reset_count += 1
            logger.warning(
                f"Reset orphaned room {room.id} ('{room.name}') from PLAYING to WAITING. "
                f"Game state was lost due to server restart."
            )

        db.commit()
        logger.info(f"Reset {reset_count} orphaned rooms on startup")
        return reset_count


# 全局实例
room_manager = RoomManager()
