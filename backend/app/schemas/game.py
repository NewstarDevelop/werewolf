"""Game schemas."""
from typing import Optional, Dict
from pydantic import BaseModel, Field

from .enums import GameStatus, GamePhase, Role, ActionType, Winner
from .player import PlayerPublic, PlayerPrivate
from .message import MessageInGame


class GameStartRequest(BaseModel):
    """Request schema for starting a new game."""
    human_seat: Optional[int] = None  # If None, random seat
    human_role: Optional[Role] = None  # If None, random role
    language: str = "zh"  # Game language: "zh" or "en"


class GameStartResponse(BaseModel):
    """Response schema for game start."""
    game_id: str
    player_role: Role
    player_seat: int
    players: list[PlayerPublic]
    token: str  # JWT token for authentication


class PendingAction(BaseModel):
    """Pending action for human player."""
    type: ActionType
    choices: list[int]  # Available target seat_ids
    message: Optional[str] = None


class GameState(BaseModel):
    """Full game state response."""
    game_id: str
    status: GameStatus
    day: int
    phase: GamePhase
    current_actor: Optional[int] = None  # Current speaker/actor seat_id
    my_seat: Optional[int] = None  # None for observer视角
    my_role: Optional[Role] = None  # None for observer视角
    players: list[PlayerPublic]
    message_log: list[MessageInGame]
    pending_action: Optional[PendingAction] = None
    winner: Optional[Winner] = None
    # Night info for specific roles
    night_kill_target: Optional[int] = None  # For witch to see who was killed
    wolf_teammates: list[int] = Field(default_factory=list)  # For werewolf to see teammates
    verified_results: Dict[int, bool] = Field(default_factory=dict)  # For seer: seat_id -> is_werewolf
    wolf_votes_visible: Dict[int, int] = Field(default_factory=dict)  # For werewolf: teammate_seat -> target_seat


class StepResponse(BaseModel):
    """Response for game step."""
    status: str  # "updated", "waiting_for_human", "game_over"
    new_phase: Optional[GamePhase] = None
    message: Optional[str] = None


class GameSummary(BaseModel):
    """Game summary for replay."""
    game_id: str
    winner: Winner
    days_played: int
    players: list[PlayerPrivate]
    all_messages: list[MessageInGame]
