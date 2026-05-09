import json

from app.llm.local_provider import LocalRuleBasedProvider, build_local_llm_client
from app.llm.schemas import PromptEnvelope, SpeechResponse, TargetedActionResponse, VoteResponse


def build_prompt(
    *,
    known_role: str = "SEER",
    killed_tonight: list[int] | None = None,
    private_log: list[str] | None = None,
) -> PromptEnvelope:
    view = {
        "day_count": 2,
        "phase": "NIGHT_ACTION",
        "players": [
            {"seat_id": 1, "is_alive": True, "is_self": True, "known_role": known_role},
            {"seat_id": 2, "is_alive": True, "is_self": False, "known_role": "WOLF"},
            {"seat_id": 3, "is_alive": True, "is_self": False, "known_role": None},
            {"seat_id": 4, "is_alive": False, "is_self": False, "known_role": None},
        ],
        "public_chat_history": ["1号发言：先听后置位"],
        "private_log": private_log or [],
        "killed_tonight": killed_tonight or [],
    }
    view_json = json.dumps(
        view,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return PromptEnvelope(
        system_prompt="系统规则",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            "你的性格：谨慎分析\n"
            '公开历史：["1号发言：先听后置位"]\n'
            f"私有记忆：{json.dumps(private_log or [], ensure_ascii=False)}\n"
            f"玩家视图JSON：{view_json}"
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


def test_local_provider_seer_pushes_checked_wolf_in_speech_and_vote() -> None:
    provider = LocalRuleBasedProvider()
    prompt = build_prompt(
        known_role="SEER",
        private_log=["查验结果：3 号是狼人。"],
    )

    speech_payload = provider.complete(prompt=prompt, response_schema=SpeechResponse)
    vote_payload = provider.complete(prompt=prompt, response_schema=VoteResponse)

    assert "3号是狼人" in str(speech_payload["speech_text"])
    assert "警徽流" in str(speech_payload["speech_text"])
    assert vote_payload["vote_target"] == 3


def test_local_provider_seer_restates_good_check_chain_in_speech() -> None:
    provider = LocalRuleBasedProvider()
    prompt = build_prompt(
        known_role="SEER",
        private_log=["查验结果：2 号是好人。"],
    )

    speech_payload = provider.complete(prompt=prompt, response_schema=SpeechResponse)

    assert "验人链" in str(speech_payload["speech_text"])
    assert "2号是好人" in str(speech_payload["speech_text"])
    assert "警徽流" in str(speech_payload["speech_text"])


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
        prompt=build_prompt(known_role="WITCH", killed_tonight=[3]),
        response_schema=TargetedActionResponse,
    )

    assert payload["use_antidote"] is True
    assert payload["use_poison"] is False


def test_build_local_llm_client_returns_callable_fallback_client() -> None:
    client = build_local_llm_client()

    response = client.request_vote(
        prompt=build_prompt(),
        allowed_targets=[2, 3],
    )

    assert response.vote_target == 2


# ===== 新增测试：覆盖未分支 (42条未覆盖行) =====

# --- helper edge cases ---

def test_extract_section_returns_none_when_label_missing() -> None:
    """Line 19: _extract_section returns None when no matching section label"""
    provider = LocalRuleBasedProvider()
    # No "私有记忆" section at all — _extract_section returns None
    prompt = PromptEnvelope(
        system_prompt="系统规则",
        context_prompt="当前阶段：NIGHT_ACTION\n当前天数：第 1 天\n",
        task_prompt="当前任务",
    )
    # _extract_private_log → view empty → _extract_section None → returns [](line 68)
    # Then VoteResponse falls through to default path
    payload = provider.complete(prompt=prompt, response_schema=VoteResponse)
    assert payload["vote_target"] == 0  # no alive targets, returns 0


def test_view_empty_json_decode_error_and_non_dict() -> None:
    """Lines 25,29-30,32: _extract_view returns {} on empty/malformed/non-dict view"""
    provider = LocalRuleBasedProvider()

    # Case 1: Line 25 — no "玩家视图JSON" section
    prompt_no_view = PromptEnvelope(
        system_prompt="x",
        context_prompt="当前阶段：NIGHT_ACTION\n当前天数：第 1 天\n",
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt_no_view, response_schema=SpeechResponse)
    assert payload["speech_text"]  # falls through to default speech

    # Case 2: Lines 29-30 — invalid JSON view
    prompt_bad_json = PromptEnvelope(
        system_prompt="x",
        context_prompt="当前阶段：NIGHT_ACTION\n玩家视图JSON：{invalid-json!!!\n",
        task_prompt="x",
    )
    payload2 = provider.complete(prompt=prompt_bad_json, response_schema=VoteResponse)
    assert payload2["vote_target"] == 0  # no targets parsed

    # Case 3: Line 32 — view is JSON but not a dict (e.g., string)
    prompt_not_dict = PromptEnvelope(
        system_prompt="x",
        context_prompt='当前阶段：NIGHT_ACTION\n玩家视图JSON："just_a_string"\n',
        task_prompt="x",
    )
    payload3 = provider.complete(prompt=prompt_not_dict, response_schema=VoteResponse)
    assert payload3["vote_target"] == 0


def test_extract_players_ast_fallback_path() -> None:
    """Lines 42-57: _extract_players falls back to AST parsing of '玩家视图' section"""
    provider = LocalRuleBasedProvider()
    # No view JSON, but has "玩家视图" section on ONE line → triggers AST literal_eval path
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            # Must be single line; use Python True/False (not JSON true/false) for ast.literal_eval
            '玩家视图：[{"seat_id": 1, "is_alive": True, "is_self": True, "known_role": "SEER"}, {"seat_id": 2, "is_alive": True, "is_self": False, "known_role": "WOLF"}]\n'
        ),
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt, response_schema=VoteResponse)
    assert payload["vote_target"] == 2  # first non-self alive target


def test_extract_players_ast_fallback_non_list_and_bad_syntax() -> None:
    """Lines 44~51: AST path where raw_players is None / not list / bad syntax"""
    provider = LocalRuleBasedProvider()

    # Line 44: section exists but empty
    prompt_empty = PromptEnvelope(
        system_prompt="x",
        context_prompt="玩家视图：\n当前阶段：NIGHT_ACTION\n",
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt_empty, response_schema=SpeechResponse)
    assert payload["speech_text"]

    # Bad syntax (line 48-49)
    prompt_bad_syntax = PromptEnvelope(
        system_prompt="x",
        context_prompt='玩家视图：{not valid python list}\n当前阶段：NIGHT_ACTION\n',
        task_prompt="x",
    )
    payload2 = provider.complete(prompt=prompt_bad_syntax, response_schema=SpeechResponse)
    assert payload2["speech_text"]

    # Not a list (line 50-51)
    prompt_not_list = PromptEnvelope(
        system_prompt="x",
        context_prompt='玩家视图：{"key": "value"}\n当前阶段：NIGHT_ACTION\n',
        task_prompt="x",
    )
    payload3 = provider.complete(prompt=prompt_not_list, response_schema=SpeechResponse)
    assert payload3["speech_text"]


def test_extract_private_log_ast_fallback_path() -> None:
    """Lines 66-77: _extract_private_log falls back to AST parsing of '私有记忆' section"""
    provider = LocalRuleBasedProvider()
    # View JSON has players (with SEER self) but NO private_log key
    # "私有记忆" text section provides the private log via AST
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"day_count":2,"phase":"NIGHT_ACTION","players":[{"seat_id":1,"is_alive":true,"is_self":true,"known_role":"SEER"},{"seat_id":3,"is_alive":true,"is_self":false,"known_role":"VILLAGER"},{"seat_id":5,"is_alive":true,"is_self":false,"known_role":"WOLF"}],"killed_tonight":[]}\n'
            "私有记忆：['查验结果： 3 号是 好人', '查验结果： 5 号是 狼人']\n"
        ),
        task_prompt="x",
    )
    # SEER with checked wolf (5) → triggers checked_wolf vote path
    payload = provider.complete(prompt=prompt, response_schema=VoteResponse)
    assert payload["vote_target"] == 5  # checked wolf #5


def test_extract_private_log_ast_fallback_edge_cases() -> None:
    """Lines 68-75: edge cases in private_log AST path"""
    provider = LocalRuleBasedProvider()

    # Line 68: section exists but empty
    prompt_empty = PromptEnvelope(
        system_prompt="x",
        context_prompt="私有记忆：\n玩家视图JSON：{}\n当前阶段：NIGHT_ACTION\n",
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt_empty, response_schema=VoteResponse)
    assert payload["vote_target"] == 0

    # Line 72-73: bad syntax
    prompt_bad = PromptEnvelope(
        system_prompt="x",
        context_prompt='私有记忆：{bad syntax}\n玩家视图JSON：{"players":[]}\n当前阶段：NIGHT_ACTION\n',
        task_prompt="x",
    )
    payload2 = provider.complete(prompt=prompt_bad, response_schema=VoteResponse)
    assert payload2["vote_target"] == 0

    # Line 74-75: not a list
    prompt_not_list = PromptEnvelope(
        system_prompt="x",
        context_prompt='私有记忆："just a string"\n玩家视图JSON：{"players":[]}\n当前阶段：NIGHT_ACTION\n',
        task_prompt="x",
    )
    payload3 = provider.complete(prompt=prompt_not_list, response_schema=VoteResponse)
    assert payload3["vote_target"] == 0


def test_extract_self_role_no_self_player() -> None:
    """Line 85: _extract_self_role returns None when no player has is_self=True"""
    provider = LocalRuleBasedProvider()
    # All players have is_self=False → _extract_self_role returns None
    # Then in VoteResponse: _extract_self_role ≠ "SEER", so falls through to default
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"players":[{"seat_id":1,"is_alive":true,"is_self":false,"known_role":"SEER"},{"seat_id":2,"is_alive":true,"is_self":false,"known_role":"WOLF"}]}\n'
        ),
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt, response_schema=VoteResponse)
    assert payload["vote_target"] == 1  # first alive target


def test_extract_alive_targets_non_int_seat_id() -> None:
    """Line 137: skip player with non-integer seat_id"""
    provider = LocalRuleBasedProvider()
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"players":[{"seat_id":"abc","is_alive":true,"is_self":true,"known_role":"VILLAGER"},{"seat_id":2,"is_alive":true,"is_self":false,"known_role":"WOLF"}]}\n'
        ),
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt, response_schema=VoteResponse)
    assert payload["vote_target"] == 2  # skips seat_id="abc", picks seat 2


def test_extract_killed_tonight_ast_fallback() -> None:
    """Lines 154-165: _extract_killed_tonight falls back to AST from '今晚死亡名单' section"""
    provider = LocalRuleBasedProvider()
    # View JSON has no killed_tonight key, but "今晚死亡名单" text section exists
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"day_count":2,"phase":"NIGHT_ACTION","players":[]}\n'
            "今晚死亡名单：[3, 5]\n"
        ),
        task_prompt="x",
    )
    # TargetedActionResponse with killed_tonight → returns antidote=True
    payload = provider.complete(prompt=prompt, response_schema=TargetedActionResponse)
    assert payload["use_antidote"] is True
    assert payload["use_poison"] is False
    assert payload["target"] is None


def test_extract_killed_tonight_ast_fallback_edge_cases() -> None:
    """Lines 154-163: edge cases in killed_tonight AST path"""
    provider = LocalRuleBasedProvider()

    # Section missing (line 154-156)
    prompt_no_section = PromptEnvelope(
        system_prompt="x",
        context_prompt='玩家视图JSON：{"players":[]}\n当前阶段：NIGHT_ACTION\n',
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt_no_section, response_schema=TargetedActionResponse)
    assert payload["use_antidote"] is False  # no killed_tonight → default action

    # Bad syntax (lines 159-161)
    prompt_bad = PromptEnvelope(
        system_prompt="x",
        context_prompt='今晚死亡名单：{bad}\n当前阶段：NIGHT_ACTION\n玩家视图JSON：{"players":[]}\n',
        task_prompt="x",
    )
    payload2 = provider.complete(prompt=prompt_bad, response_schema=TargetedActionResponse)
    assert payload2["use_antidote"] is False

    # Not a list (lines 162-163)
    prompt_not_list = PromptEnvelope(
        system_prompt="x",
        context_prompt='今晚死亡名单："only_one"\n当前阶段：NIGHT_ACTION\n玩家视图JSON：{"players":[]}\n',
        task_prompt="x",
    )
    payload3 = provider.complete(prompt=prompt_not_list, response_schema=TargetedActionResponse)
    assert payload3["use_antidote"] is False


# --- 业务相关的补充分支 ---

def test_local_provider_witch_default_action_no_killed() -> None:
    """WITCH TargetedActionResponse without killed_tonight→ picks first alive target"""
    provider = LocalRuleBasedProvider()
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"players":[{"seat_id":1,"is_alive":true,"is_self":true,"known_role":"WITCH"},{"seat_id":2,"is_alive":true,"is_self":false,"known_role":"VILLAGER"}],"killed_tonight":[]}\n'
        ),
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt, response_schema=TargetedActionResponse)
    assert payload["target"] == 2  # first alive non-self
    assert payload["use_antidote"] is False
    assert payload["use_poison"] is False


def test_local_provider_vote_non_seer() -> None:
    """non-SEER (VILLAGER) vote → default first alive target"""
    provider = LocalRuleBasedProvider()
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"players":[{"seat_id":1,"is_alive":true,"is_self":true,"known_role":"VILLAGER"},{"seat_id":3,"is_alive":true,"is_self":false,"known_role":"WOLF"}],"private_log":[]}\n'
        ),
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt, response_schema=VoteResponse)
    assert payload["vote_target"] == 3  # first alive non-self


def test_local_provider_speech_non_seer() -> None:
    """non-SEER (VILLAGER) speech → conservative default response"""
    provider = LocalRuleBasedProvider()
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"players":[{"seat_id":1,"is_alive":true,"is_self":true,"known_role":"VILLAGER"}],"private_log":[]}\n'
        ),
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt, response_schema=SpeechResponse)
    assert payload["speech_text"] == "信息还不够，我先听后置位怎么聊。"


def test_local_provider_vote_seer_no_checked_wolf() -> None:
    """SEER vote with no checked wolf → first alive target"""
    provider = LocalRuleBasedProvider()
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt=(
            "当前阶段：NIGHT_ACTION\n"
            "当前天数：第 2 天\n"
            '玩家视图JSON：{"players":[{"seat_id":1,"is_alive":true,"is_self":true,"known_role":"SEER"},{"seat_id":3,"is_alive":true,"is_self":false,"known_role":"VILLAGER"}],"private_log":[]}\n'
        ),
        task_prompt="x",
    )
    payload = provider.complete(prompt=prompt, response_schema=VoteResponse)
    assert payload["vote_target"] == 3  # first alive non-self


def test_local_provider_raises_type_error_for_unsupported_schema() -> None:
    """Line 233: TypeError for unsupported response schema"""
    provider = LocalRuleBasedProvider()
    prompt = PromptEnvelope(
        system_prompt="x",
        context_prompt="当前阶段：NIGHT_ACTION\n",
        task_prompt="x",
    )
    try:
        provider.complete(prompt=prompt, response_schema=dict)
        assert False, "Expected TypeError"
    except TypeError as e:
        assert "unsupported response schema" in str(e)
