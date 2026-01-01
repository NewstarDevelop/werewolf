"""User profile schemas."""
from pydantic import BaseModel, Field
from typing import Optional


class UpdateProfileRequest(BaseModel):
    """Update user profile request."""
    nickname: Optional[str] = Field(None, min_length=2, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=512)


class UserStatsResponse(BaseModel):
    """User game statistics response."""
    games_played: int
    games_won: int
    win_rate: float
    recent_games: list
