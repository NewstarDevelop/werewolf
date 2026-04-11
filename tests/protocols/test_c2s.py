import pytest
from pydantic import ValidationError

from app.protocols.c2s import ClientEnvelope, SubmitActionPayload


def test_vote_action_requires_target() -> None:
    payload = ClientEnvelope.model_validate(
        {
            "type": "SUBMIT_ACTION",
            "data": {"action_type": "VOTE", "target": 5},
        }
    )

    assert payload.data == SubmitActionPayload(action_type="VOTE", target=5)


def test_speak_action_requires_text() -> None:
    payload = ClientEnvelope.model_validate(
        {
            "type": "SUBMIT_ACTION",
            "data": {"action_type": "SPEAK", "text": "我先听后置位"},
        }
    )

    assert payload.data.text == "我先听后置位"


def test_targeted_action_rejects_missing_target() -> None:
    with pytest.raises(ValidationError):
        ClientEnvelope.model_validate(
            {
                "type": "SUBMIT_ACTION",
                "data": {"action_type": "VOTE"},
            }
        )


def test_pass_action_can_omit_target() -> None:
    payload = ClientEnvelope.model_validate(
        {
            "type": "SUBMIT_ACTION",
            "data": {"action_type": "PASS"},
        }
    )

    assert payload.data == SubmitActionPayload(action_type="PASS")


def test_speak_action_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        ClientEnvelope.model_validate(
            {
                "type": "SUBMIT_ACTION",
                "data": {"action_type": "SPEAK"},
            }
        )
