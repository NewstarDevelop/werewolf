"""Game history schemas."""
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field


class PlayerInfo(BaseModel):
    """Player information in game history."""
    nickname: str
    role: str
    is_winner: bool


class GameHistoryItem(BaseModel):
    """Game history list item."""
    game_id: str
    room_name: str
    started_at: datetime
    finished_at: datetime
    winner: str  # "werewolf" / "villager"
    player_count: int
    my_role: str
    is_winner: bool

    class Config:
        from_attributes = True


class GameHistoryDetail(GameHistoryItem):
    """Game history detail with full player list."""
    players: List[PlayerInfo] = Field(default_factory=list)
    duration_seconds: int

    class Config:
        from_attributes = True


class GameHistoryListResponse(BaseModel):
    """Game history list response with pagination."""
    games: List[GameHistoryItem]
    total: int
    page: int
    page_size: int
