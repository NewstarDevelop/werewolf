from typing import Any, Literal

from pydantic import BaseModel, Field


class SystemMessagePayload(BaseModel):
    message: str = Field(min_length=1)


class ChatUpdatePayload(BaseModel):
    message: str = Field(min_length=1)
    seat_id: int | None = None
    speaker: str | None = None
    visibility: Literal["public", "private"] = "public"


class AIThinkingPayload(BaseModel):
    seat_id: int = Field(ge=1, le=9)
    is_thinking: bool
    message: str | None = None


class RequireInputPayload(BaseModel):
    action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "HUNTER_SHOOT", "WITCH_ACTION"]
    prompt: str = Field(min_length=1)
    allowed_targets: list[int] = Field(default_factory=list)


class GameOverPayload(BaseModel):
    winning_side: Literal["GOOD", "WOLF"]
    summary: str = Field(min_length=1)
    revealed_roles: dict[int, str] = Field(default_factory=dict)


class SystemMessageEnvelope(BaseModel):
    type: Literal["SYSTEM_MSG"]
    data: SystemMessagePayload
    meta: dict[str, Any] = Field(default_factory=dict)


class ChatUpdateEnvelope(BaseModel):
    type: Literal["CHAT_UPDATE"]
    data: ChatUpdatePayload
    meta: dict[str, Any] = Field(default_factory=dict)


class AIThinkingEnvelope(BaseModel):
    type: Literal["AI_THINKING"]
    data: AIThinkingPayload
    meta: dict[str, Any] = Field(default_factory=dict)


class RequireInputEnvelope(BaseModel):
    type: Literal["REQUIRE_INPUT"]
    data: RequireInputPayload
    meta: dict[str, Any] = Field(default_factory=dict)


class GameOverEnvelope(BaseModel):
    type: Literal["GAME_OVER"]
    data: GameOverPayload
    meta: dict[str, Any] = Field(default_factory=dict)


ServerEnvelope = (
    SystemMessageEnvelope
    | ChatUpdateEnvelope
    | AIThinkingEnvelope
    | RequireInputEnvelope
    | GameOverEnvelope
)
