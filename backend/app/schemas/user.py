from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: int
    email: str
    nickname: str
    avatar_url: str | None = None
    bio: str | None = None
    is_admin: bool = False

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
