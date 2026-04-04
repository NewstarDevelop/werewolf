from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="classic_9")  # classic_9 | classic_12
    variant: Mapped[str | None] = mapped_column(String(20), nullable=True)  # wolf_king | white_wolf_king
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="zh")
    max_players: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")  # waiting | playing | finished
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    players: Mapped[list["RoomPlayer"]] = relationship(
        "RoomPlayer", back_populates="room", cascade="all, delete-orphan", order_by="RoomPlayer.seat"
    )


class RoomPlayer(Base):
    __tablename__ = "room_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    seat: Mapped[int] = mapped_column(Integer, nullable=False)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    room: Mapped["Room"] = relationship("Room", back_populates="players")
