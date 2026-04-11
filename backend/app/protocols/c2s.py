from typing import Any, Literal

from pydantic import BaseModel, Field


class SubmitActionPayload(BaseModel):
    action: str = Field(min_length=1)
    target: int | None = None
    text: str | None = None


class ClientEnvelope(BaseModel):
    type: Literal["SUBMIT_ACTION"]
    data: SubmitActionPayload
    meta: dict[str, Any] = Field(default_factory=dict)
