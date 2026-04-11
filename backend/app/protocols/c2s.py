from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class SubmitActionPayload(BaseModel):
    action_type: Literal[
        "SPEAK",
        "VOTE",
        "WOLF_KILL",
        "SEER_CHECK",
        "WITCH_SAVE",
        "WITCH_POISON",
        "PASS",
    ]
    target: int | None = None
    text: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "SubmitActionPayload":
        targeted_actions = {"VOTE", "WOLF_KILL", "SEER_CHECK", "WITCH_POISON"}
        text_actions = {"SPEAK"}

        if self.action_type in targeted_actions and self.target is None:
            raise ValueError("target is required for targeted actions")
        if self.action_type in text_actions and not self.text:
            raise ValueError("text is required for speech actions")

        return self


class ClientEnvelope(BaseModel):
    type: Literal["SUBMIT_ACTION"]
    data: SubmitActionPayload
    meta: dict[str, Any] = Field(default_factory=dict)
