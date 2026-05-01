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


class PlayerStatePatch(BaseModel):
    seat_id: int = Field(ge=1, le=9)
    is_alive: bool | None = None
    is_human: bool | None = None
    role_code: str | None = None
    is_thinking: bool | None = None


class PlayerStatePatchPayload(BaseModel):
    players: list[PlayerStatePatch] = Field(min_length=1)


class PhaseChangedPayload(BaseModel):
    phase: str = Field(min_length=1)
    day_count: int = Field(ge=1)


class DeathRevealedPayload(BaseModel):
    dead_seats: list[int] = Field(default_factory=list)
    eligible_last_words: list[int] = Field(default_factory=list)
    day_count: int = Field(ge=1)


class VoteResolvedPayload(BaseModel):
    votes: dict[int, int] = Field(default_factory=dict)
    abstentions: list[int] = Field(default_factory=list)
    banished_seat: int | None = Field(default=None, ge=1, le=9)
    summary: str = Field(min_length=1)


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


class PlayerStatePatchEnvelope(BaseModel):
    type: Literal["PLAYER_STATE_PATCH"]
    data: PlayerStatePatchPayload
    meta: dict[str, Any] = Field(default_factory=dict)


class PhaseChangedEnvelope(BaseModel):
    type: Literal["PHASE_CHANGED"]
    data: PhaseChangedPayload
    meta: dict[str, Any] = Field(default_factory=dict)


class DeathRevealedEnvelope(BaseModel):
    type: Literal["DEATH_REVEALED"]
    data: DeathRevealedPayload
    meta: dict[str, Any] = Field(default_factory=dict)


class VoteResolvedEnvelope(BaseModel):
    type: Literal["VOTE_RESOLVED"]
    data: VoteResolvedPayload
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
    | PlayerStatePatchEnvelope
    | PhaseChangedEnvelope
    | DeathRevealedEnvelope
    | VoteResolvedEnvelope
    | RequireInputEnvelope
    | GameOverEnvelope
)
