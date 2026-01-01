"""Action schemas."""
from typing import Optional
from pydantic import BaseModel, Field

from .enums import ActionType


class ActionRequest(BaseModel):
    """Request schema for player action.

    P1-API-001 Fix: seat_id is Optional because it's derived from JWT token
    on the server side, not trusted from client input.
    """
    seat_id: Optional[int] = None  # Ignored by server, kept for backward compatibility
    action_type: ActionType
    target_id: Optional[int] = None
    content: Optional[str] = Field(None, max_length=500, description="Speech content (max 500 chars)")


class ActionRecord(BaseModel):
    """Record of an action taken."""
    id: int
    game_id: str
    day: int
    phase: str
    player_id: int
    target_id: Optional[int] = None
    action_type: ActionType


class ActionResponse(BaseModel):
    """Response schema for action."""
    success: bool
    message: Optional[str] = None
