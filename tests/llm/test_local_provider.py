from app.llm.local_provider import LocalRuleBasedProvider, build_default_llm_client
from app.llm.schemas import PromptEnvelope, SpeechResponse, TargetedActionResponse, VoteResponse


def build_prompt(*, known_role: str = "SEER", killed_tonight: str = "[]") -> PromptEnvelope:
    return PromptEnvelope(
        system_prompt="系统规则",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            "你的性格：谨慎分析\n"
            "公开历史：['1号发言：先听后置位']\n"
            "私有记忆：[]\n"
            f"玩家视图：[{{'seat_id': 1, 'is_alive': True, 'is_self': True, 'known_role': '{known_role}'}}, "
            "{'seat_id': 2, 'is_alive': True, 'is_self': False, 'known_role': 'WOLF'}, "
            "{'seat_id': 3, 'is_alive': True, 'is_self': False, 'known_role': None}, "
            "{'seat_id': 4, 'is_alive': False, 'is_self': False, 'known_role': None}]\n"
            f"今晚死亡名单：{killed_tonight}"
        ),
        task_prompt="当前任务",
    )


def test_local_provider_returns_speech_payload() -> None:
    provider = LocalRuleBasedProvider()

    payload = provider.complete(
        prompt=build_prompt(),
        response_schema=SpeechResponse,
    )

    assert payload["speech_text"]


def test_local_provider_picks_first_alive_vote_target() -> None:
    provider = LocalRuleBasedProvider()

    payload = provider.complete(
        prompt=build_prompt(known_role="SEER"),
        response_schema=VoteResponse,
    )

    assert payload["vote_target"] == 2


def test_local_provider_avoids_known_wolf_teammates_for_wolf_actor() -> None:
    provider = LocalRuleBasedProvider()

    payload = provider.complete(
        prompt=build_prompt(known_role="WOLF"),
        response_schema=TargetedActionResponse,
    )

    assert payload["target"] == 3


def test_local_provider_prefers_antidote_when_night_has_death() -> None:
    provider = LocalRuleBasedProvider()

    payload = provider.complete(
        prompt=build_prompt(known_role="WITCH", killed_tonight="[3]"),
        response_schema=TargetedActionResponse,
    )

    assert payload["use_antidote"] is True
    assert payload["use_poison"] is False


def test_build_default_llm_client_returns_callable_fallback_client() -> None:
    client = build_default_llm_client()

    response = client.request_vote(
        prompt=build_prompt(),
        allowed_targets=[2, 3],
    )

    assert response.vote_target == 2
