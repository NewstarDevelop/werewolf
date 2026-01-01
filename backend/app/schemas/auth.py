"""Authentication request and response schemas."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    nickname: str = Field(..., min_length=2, max_length=50)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token."""
    token: str
    new_password: str = Field(..., min_length=6, max_length=100)


class UserResponse(BaseModel):
    """User profile response."""
    id: str
    email: Optional[str]
    nickname: str
    avatar_url: Optional[str]
    bio: Optional[str]
    is_email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Authentication success response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class OAuthStateResponse(BaseModel):
    """OAuth authorization URL response."""
    authorize_url: str
    state: str
