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
    ballots: dict[int, int] = Field(default_factory=dict)
    abstentions: list[int] = Field(default_factory=list)
    banished_seat: int | None = Field(default=None, ge=1, le=9)
    summary: str = Field(min_length=1)


class SettlementPlayerPayload(BaseModel):
    seat_id: int = Field(ge=1, le=9)
    role_code: str = Field(min_length=1)
    side: Literal["GOOD", "WOLF"]
    is_alive: bool
    is_human: bool


class SettlementEventPayload(BaseModel):
    day_count: int = Field(ge=1)
    phase: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    actor_seat: int | None = Field(default=None, ge=1, le=9)
    target_seats: list[int] = Field(default_factory=list)


class SettlementNightPayload(BaseModel):
    day_count: int = Field(ge=1)
    wolf_target: int | None = Field(default=None, ge=1, le=9)
    seer_seat: int | None = Field(default=None, ge=1, le=9)
    seer_target: int | None = Field(default=None, ge=1, le=9)
    seer_result: Literal["GOOD", "WOLF"] | None = None
    witch_seat: int | None = Field(default=None, ge=1, le=9)
    witch_save_target: int | None = Field(default=None, ge=1, le=9)
    witch_poison_target: int | None = Field(default=None, ge=1, le=9)
    dead_seats: list[int] = Field(default_factory=list)


class SettlementSpeechPayload(BaseModel):
    seat_id: int = Field(ge=1, le=9)
    message: str = Field(min_length=1)
    event_type: str = Field(min_length=1)


class SettlementDayPayload(BaseModel):
    day_count: int = Field(ge=1)
    speeches: list[SettlementSpeechPayload] = Field(default_factory=list)
    vote: VoteResolvedPayload | None = None
    vote_explanation: str | None = None


class SettlementRecapPayload(BaseModel):
    day_count: int = Field(ge=1)
    outcome_reason: str = Field(min_length=1)
    role_reveal_summary: str = Field(min_length=1)
    players: list[SettlementPlayerPayload] = Field(default_factory=list)
    nights: list[SettlementNightPayload] = Field(default_factory=list)
    days: list[SettlementDayPayload] = Field(default_factory=list)
    key_events: list[SettlementEventPayload] = Field(default_factory=list)
    timeline: list[SettlementEventPayload] = Field(default_factory=list)
    final_vote: VoteResolvedPayload | None = None


class RequireInputPayload(BaseModel):
    action_type: Literal["SPEAK", "VOTE", "WOLF_KILL", "SEER_CHECK", "HUNTER_SHOOT", "WITCH_ACTION"]
    request_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    allowed_targets: list[int] = Field(default_factory=list)
    available_actions: list[Literal["WITCH_SAVE", "WITCH_POISON", "PASS"]] | None = None
    save_targets: list[int] | None = None


class GameOverPayload(BaseModel):
    winning_side: Literal["GOOD", "WOLF", "DRAW"]
    summary: str = Field(min_length=1)
    revealed_roles: dict[int, str] = Field(default_factory=dict)
    recap: SettlementRecapPayload | None = None


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
