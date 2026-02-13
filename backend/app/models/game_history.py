"""Game history models for user statistics."""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from .base import Base


class GameSession(Base):
    """对局会话模型 - 记录完整对局信息"""
    __tablename__ = "game_sessions"

    id = Column(String(36), primary_key=True)  # game_id (与room_id相同)
    room_id = Column(String(36), ForeignKey('rooms.id', ondelete='SET NULL'), nullable=True, unique=True)
    winner = Column(String(32), nullable=True, index=True)  # "werewolf" / "villager" / "draw" / null
    started_at = Column(DateTime, nullable=True, index=True)
    finished_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    participants = relationship("GameParticipant", back_populates="game_session", cascade="all, delete-orphan")
    messages = relationship("GameMessage", back_populates="game_session", cascade="all, delete-orphan")


class GameParticipant(Base):
    """对局参与者模型 - 记录每个玩家在对局中的信息"""
    __tablename__ = "game_participants"

    __table_args__ = (
        Index('idx_user_stats', 'user_id', 'is_winner'),  # 用于统计查询优化
        Index('idx_game_user', 'game_id', 'user_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(36), ForeignKey('game_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)  # 匿名玩家为NULL
    player_id = Column(String(36), nullable=False, index=True)  # 该局内的player_id
    seat_id = Column(Integer, nullable=False)  # 座位号 (1-9)
    nickname = Column(String(50), nullable=False)  # 该局昵称
    is_ai = Column(Boolean, default=False, nullable=False, index=True)  # 是否AI玩家
    role = Column(String(32), nullable=True)  # 角色（可选：游戏结束后写入）
    is_winner = Column(Boolean, default=False, nullable=False, index=True)  # 是否胜利
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    game_session = relationship("GameSession", back_populates="participants")
    user = relationship("User", back_populates="game_participations")


class GameMessage(Base):
    """游戏消息持久化模型 - 用于回放功能（MVP：仅消息）"""
    __tablename__ = "game_messages"

    __table_args__ = (
        UniqueConstraint("game_id", "seq", name="uq_game_messages_game_seq"),
        Index("idx_game_messages_game_seq", "game_id", "seq"),
        Index("idx_game_messages_game_day", "game_id", "day"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(36), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # seq 是游戏内消息序号（对应内存 Message.id），用于稳定排序
    seq = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False, index=True)
    seat_id = Column(Integer, nullable=False)  # 0 表示系统
    content = Column(Text, nullable=False)
    msg_type = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    game_session = relationship("GameSession", back_populates="messages")
