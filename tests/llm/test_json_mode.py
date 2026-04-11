import pytest
from pydantic import ValidationError

from app.llm.schemas import PromptEnvelope, SpeechResponse, TargetedActionResponse, VoteResponse


def test_speech_response_requires_short_public_output() -> None:
    response = SpeechResponse(
        inner_thought="我要伪装成好人。",
        speech_text="4号这轮视角有问题，我建议先从他说辞里找破绽。",
    )

    assert response.speech_text.startswith("4号")


def test_vote_response_accepts_abstain_and_valid_targets() -> None:
    abstain = VoteResponse(inner_thought="信息不够，先弃票。", vote_target=0)
    vote = VoteResponse(inner_thought="4号像狼。", vote_target=4)

    assert abstain.vote_target == 0
    assert vote.vote_target == 4


def test_targeted_action_rejects_conflicting_or_invalid_shape() -> None:
    with pytest.raises(ValidationError):
        TargetedActionResponse(
            inner_thought="两瓶药一起交。",
            target=3,
            use_antidote=True,
            use_poison=True,
        )

    with pytest.raises(ValidationError):
        TargetedActionResponse(
            inner_thought="直接毒人。",
            use_poison=True,
        )


def test_prompt_envelope_requires_three_segments() -> None:
    envelope = PromptEnvelope(
        system_prompt="系统规则",
        context_prompt="上下文",
        task_prompt="当前任务",
    )

    assert envelope.model_dump() == {
        "system_prompt": "系统规则",
        "context_prompt": "上下文",
        "task_prompt": "当前任务",
    }
