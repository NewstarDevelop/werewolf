"""Room and RoomPlayer models for multi-room support."""
from sqlalchemy import Column, String, Integer, DateTime, Enum as SQLEnum, Boolean, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from .base import Base


class RoomStatus(str, enum.Enum):
    """房间状态枚举"""
    WAITING = "waiting"      # 等待玩家加入
    PLAYING = "playing"      # 游戏进行中
    FINISHED = "finished"    # 游戏已结束


class Room(Base):
    """房间模型 - 存储房间基本信息"""
    __tablename__ = "rooms"

    id = Column(String(36), primary_key=True)  # 使用game_id作为房间ID (UUID标准长度)
    name = Column(String(100), nullable=False)  # 房间名称
    creator_user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)  # 创建者用户ID（必需，创建房间需登录）
    creator_nickname = Column(String(50), nullable=False)  # 创建者昵称（用户名快照）
    status = Column(SQLEnum(RoomStatus), default=RoomStatus.WAITING, nullable=False, index=True)
    max_players = Column(Integer, default=9, nullable=False)  # 最大玩家数
    current_players = Column(Integer, default=0, nullable=False)  # 当前玩家数
    is_private = Column(Boolean, default=False, nullable=False)  # 是否私密房间
    password = Column(String(128), nullable=True)  # 房间密码 (hash长度)
    game_mode = Column(String(20), default="classic_9", nullable=False)  # 游戏模式: classic_9, classic_12
    wolf_king_variant = Column(String(20), nullable=True)  # 狼王类型: wolf_king, white_wolf_king (仅12人局)
    language = Column(String(10), default="zh", nullable=False)  # 游戏语言: zh, en
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)  # 游戏开始时间
    finished_at = Column(DateTime, nullable=True)  # 游戏结束时间

    # Relationships
    players = relationship("RoomPlayer", back_populates="room", cascade="all, delete-orphan")


class RoomPlayer(Base):
    """房间玩家模型 - 存储房间内的玩家信息"""
    __tablename__ = "room_players"

    # T-STAB-004: Add unique constraint to prevent duplicate joins
    __table_args__ = (
        UniqueConstraint('room_id', 'player_id', name='uq_room_player'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String(36), ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False, index=True)  # 房间ID（外键，级联删除）
    player_id = Column(String(36), nullable=False)  # 玩家ID（浏览器生成的UUID）
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)  # 用户ID（登录用户关联，匿名玩家为NULL）
    nickname = Column(String(50), nullable=False)  # 玩家昵称
    seat_id = Column(Integer, nullable=True)  # 游戏中的座位号（1-9）
    is_ready = Column(Boolean, default=False, nullable=False)  # 是否准备
    is_creator = Column(Boolean, default=False, nullable=False)  # 是否为房主
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)  # 加入时间

    # Relationships
    room = relationship("Room", back_populates="players")
