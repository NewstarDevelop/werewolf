from datetime import datetime

from pydantic import BaseModel, Field


class RoomCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    mode: str = Field(pattern=r"^(classic_9|classic_12)$")
    variant: str | None = Field(None, pattern=r"^(wolf_king|white_wolf_king)$")
    language: str = Field(default="zh", pattern=r"^(zh|en)$")


class RoomPlayerBrief(BaseModel):
    user_id: int
    nickname: str | None = None
    seat: int
    is_ready: bool
    is_ai: bool
    ai_provider: str | None = None

    model_config = {"from_attributes": True}


class RoomResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    mode: str
    variant: str | None
    language: str
    max_players: int
    status: str
    token: str
    players: list[RoomPlayerBrief]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class RoomListItem(BaseModel):
    id: int
    name: str
    owner_id: int
    owner_nickname: str
    mode: str
    variant: str | None
    language: str
    max_players: int
    player_count: int
    status: str
    created_at: datetime


class AiFillRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=12)
    provider: str | None = None


class ReadyToggleResponse(BaseModel):
    is_ready: bool


class StartGameResponse(BaseModel):
    game_id: int
    message: str = "Game started"
