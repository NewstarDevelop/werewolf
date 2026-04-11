from typing import Any, Literal

from pydantic import BaseModel, Field


class SystemMessagePayload(BaseModel):
    message: str = Field(min_length=1)


class ServerEnvelope(BaseModel):
    type: Literal["SYSTEM_MSG"]
    data: SystemMessagePayload
    meta: dict[str, Any] = Field(default_factory=dict)
