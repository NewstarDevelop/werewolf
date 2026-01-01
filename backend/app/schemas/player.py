"""Player schemas."""
from typing import Optional
from pydantic import BaseModel

from .enums import Role


class Personality(BaseModel):
    """AI personality configuration."""
    name: str  # e.g., "暴躁的老王"
    trait: str  # e.g., "激进", "保守", "逻辑流"
    speaking_style: str  # e.g., "口语化", "严谨", "幽默"


class PlayerBase(BaseModel):
    """Base player schema."""
    seat_id: int
    is_human: bool = False
    is_alive: bool = True


class PlayerCreate(PlayerBase):
    """Player creation schema."""
    role: Role
    personality: Optional[Personality] = None


class PlayerPublic(BaseModel):
    """Public player info (visible to all)."""
    seat_id: int
    is_alive: bool
    is_human: bool
    avatar: Optional[str] = None
    name: Optional[str] = None
    role: Optional[Role] = None  # Only shown when game is finished


class PlayerPrivate(PlayerPublic):
    """Private player info (visible to self or after game)."""
    role: Role
    personality: Optional[Personality] = None


class PlayerInGame(BaseModel):
    """Full player state in game."""
    seat_id: int
    is_human: bool
    is_alive: bool
    role: Role
    personality: Optional[Personality] = None
    # Witch specific
    has_save_potion: bool = True
    has_poison_potion: bool = True
    # Hunter specific
    can_shoot: bool = True  # False if poisoned
    # Seer specific
    verified_players: dict[int, bool] = {}  # seat_id -> is_werewolf
    # Werewolf specific
    teammates: list[int] = []  # seat_ids of other werewolves
