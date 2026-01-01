"""Message schemas."""
from typing import Optional
from pydantic import BaseModel

from .enums import MessageType


class MessageCreate(BaseModel):
    """Message creation schema."""
    seat_id: int  # 0 for system
    content: str
    msg_type: MessageType = MessageType.SPEECH


class MessageInGame(BaseModel):
    """Message in game state."""
    seat_id: int
    text: str
    type: MessageType
    day: int
