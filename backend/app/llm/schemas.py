from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SpeechResponse(BaseModel):
    inner_thought: str = Field(min_length=1)
    speech_text: str = Field(min_length=1, max_length=150)


class VoteResponse(BaseModel):
    inner_thought: str = Field(min_length=1)
    vote_target: int | Literal[0] = Field(ge=0, le=9)


class TargetedActionResponse(BaseModel):
    inner_thought: str = Field(min_length=1)
    target: int | None = Field(default=None, ge=1, le=9)
    use_antidote: bool = False
    use_poison: bool = False

    @model_validator(mode="after")
    def validate_action_shape(self) -> "TargetedActionResponse":
        if self.use_antidote and self.use_poison:
            raise ValueError("cannot use antidote and poison at the same time")
        if self.use_poison and self.target is None:
            raise ValueError("poison action requires a target")
        return self


class PromptEnvelope(BaseModel):
    system_prompt: str = Field(min_length=1)
    context_prompt: str = Field(min_length=1)
    task_prompt: str = Field(min_length=1)
