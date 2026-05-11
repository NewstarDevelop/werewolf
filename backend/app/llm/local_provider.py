import ast
from dataclasses import dataclass
import json
import re

from app.llm.client import JSONModeClient, LLMProvider
from app.llm.fallback import FallbackLLMClient
from app.llm.phrasebook import (
    render_checked_chain_speech,
    render_checked_wolf_speech,
    render_default_speech,
    render_suspicion_speech,
    render_tactic_speech,
)
from app.llm.schemas import PromptEnvelope, SpeechResponse, TargetedActionResponse, VoteResponse

_SEER_CHECK_PATTERN = re.compile(r"查验结果：\s*(\d+)\s*号是\s*(狼人|好人)")
_SEER_WOLF_CHECK_PATTERN = re.compile(r"查验结果：\s*(\d+)\s*号是\s*狼人")
_STANCE_ITEM_PATTERN = re.compile(r"(\d+)号\((\d+)\)")
_TACTIC_LABEL_PATTERN = re.compile(r"本轮战术目标：([^；\n]+)")
_TACTIC_TARGET_PATTERN = re.compile(r"(?:^|；)目标：([^；\n]+)")
_SEAT_PATTERN = re.compile(r"(\d+)号")


def _extract_section(prompt: PromptEnvelope, label: str) -> str | None:
    for line in prompt.context_prompt.splitlines():
        prefix = f"{label}："
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _extract_tactic_label(prompt: PromptEnvelope) -> str | None:
    match = _TACTIC_LABEL_PATTERN.search(prompt.context_prompt)
    if match is None:
        return None
    return match.group(1).strip()


def _extract_tactic_targets(prompt: PromptEnvelope) -> list[int]:
    match = _TACTIC_TARGET_PATTERN.search(prompt.context_prompt)
    if match is None:
        return []
    return [int(seat_match.group(1)) for seat_match in _SEAT_PATTERN.finditer(match.group(1))]


def _pick_tactic_target(prompt: PromptEnvelope) -> int | None:
    alive_targets = set(_extract_alive_targets(prompt))
    for seat_id in _extract_tactic_targets(prompt):
        if seat_id in alive_targets:
            return seat_id
    return None


def _extract_view(prompt: PromptEnvelope) -> dict[str, object]:
    raw_view = _extract_section(prompt, "玩家视图JSON")
    if not raw_view:
        return {}

    try:
        payload = json.loads(raw_view)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _extract_players(prompt: PromptEnvelope) -> list[dict[str, object]]:
    view = _extract_view(prompt)
    players_payload = view.get("players")
    if isinstance(players_payload, list):
        return [player for player in players_payload if isinstance(player, dict)]

    raw_players = _extract_section(prompt, "玩家视图")
    if not raw_players:
        return []

    try:
        payload = ast.literal_eval(raw_players)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(payload, list):
        return []

    players: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            players.append(item)
    return players


def _extract_private_log(prompt: PromptEnvelope) -> list[str]:
    view = _extract_view(prompt)
    private_log_payload = view.get("private_log")
    if isinstance(private_log_payload, list):
        return [message for message in private_log_payload if isinstance(message, str)]

    raw_log = _extract_section(prompt, "私有记忆")
    if not raw_log:
        return []

    try:
        payload = ast.literal_eval(raw_log)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(payload, list):
        return []

    return [message for message in payload if isinstance(message, str)]


def _extract_self_role(prompt: PromptEnvelope) -> str | None:
    for player in _extract_players(prompt):
        if player.get("is_self") is True:
            known_role = player.get("known_role")
            return known_role if isinstance(known_role, str) else None
    return None


def _extract_checked_wolf_targets(prompt: PromptEnvelope) -> list[int]:
    checked_targets: list[int] = []
    for message in _extract_private_log(prompt):
        match = _SEER_WOLF_CHECK_PATTERN.search(message)
        if match is not None:
            checked_targets.append(int(match.group(1)))
    return checked_targets


def _extract_checked_results(prompt: PromptEnvelope) -> list[tuple[int, str]]:
    checked_results: list[tuple[int, str]] = []
    for message in _extract_private_log(prompt):
        match = _SEER_CHECK_PATTERN.search(message)
        if match is not None:
            checked_results.append((int(match.group(1)), match.group(2)))
    return checked_results


def _pick_checked_wolf_target(prompt: PromptEnvelope) -> int | None:
    alive_targets = set(_extract_alive_targets(prompt))
    for seat_id in _extract_checked_wolf_targets(prompt):
        if seat_id in alive_targets:
            return seat_id
    return None


def _extract_stance_targets(prompt: PromptEnvelope, label: str) -> list[int]:
    stance_line = _extract_section(prompt, "立场摘要")
    if not stance_line:
        return []
    section_match = re.search(fr"{label}：([^；]+)", stance_line)
    if section_match is None:
        return []
    scored_seats = [
        (int(match.group(1)), int(match.group(2)))
        for match in _STANCE_ITEM_PATTERN.finditer(section_match.group(1))
    ]
    return [
        seat_id
        for seat_id, _ in sorted(scored_seats, key=lambda item: (-item[1], item[0]))
    ]


def _pick_stance_target(prompt: PromptEnvelope, *, label: str = "怀疑") -> int | None:
    alive_targets = set(_extract_alive_targets(prompt))
    for seat_id in _extract_stance_targets(prompt, label):
        if seat_id in alive_targets:
            return seat_id
    return None


def _extract_alive_targets(prompt: PromptEnvelope) -> list[int]:
    players = _extract_players(prompt)
    self_seat = next(
        (
            int(player["seat_id"])
            for player in players
            if player.get("is_self") is True and isinstance(player.get("seat_id"), int)
        ),
        None,
    )
    self_role = next(
        (
            str(player.get("known_role"))
            for player in players
            if player.get("is_self") is True
        ),
        None,
    )

    targets: list[int] = []
    for player in players:
        seat_id = player.get("seat_id")
        if not isinstance(seat_id, int):
            continue
        if player.get("is_alive") is not True:
            continue
        if seat_id == self_seat:
            continue
        if self_role == "WOLF" and player.get("known_role") == "WOLF":
            continue
        targets.append(seat_id)
    return sorted(targets)


def _extract_killed_tonight(prompt: PromptEnvelope) -> list[int]:
    view = _extract_view(prompt)
    killed_payload = view.get("killed_tonight")
    if isinstance(killed_payload, list):
        return [seat_id for seat_id in killed_payload if isinstance(seat_id, int)]

    raw_killed = _extract_section(prompt, "今晚死亡名单")
    if not raw_killed:
        return []

    try:
        payload = ast.literal_eval(raw_killed)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(payload, list):
        return []

    return [seat_id for seat_id in payload if isinstance(seat_id, int)]


@dataclass(slots=True)
class LocalRuleBasedProvider(LLMProvider):
    def complete(
        self,
        *,
        prompt: PromptEnvelope,
        response_schema: type[object],
    ) -> dict[str, object]:
        if response_schema is SpeechResponse:
            self_role = _extract_self_role(prompt)
            tactic_label = _extract_tactic_label(prompt)
            tactic_target = _pick_tactic_target(prompt)
            checked_wolf = _pick_checked_wolf_target(prompt)
            suspected_target = _pick_stance_target(prompt)
            if self_role == "SEER" and checked_wolf is not None:
                return {
                    "inner_thought": "预言家已有查杀，公开推动白天放逐。",
                    "speech_text": render_checked_wolf_speech(checked_wolf),
                }
            if self_role == "SEER":
                checked_results = _extract_checked_results(prompt)
                if checked_results:
                    return {
                        "inner_thought": "预言家需要稳定复述验人链和后续查验顺序。",
                        "speech_text": render_checked_chain_speech(checked_results[-3:]),
                    }

            tactic_speech = render_tactic_speech(tactic_label, tactic_target)
            if tactic_speech is not None:
                return {
                    "inner_thought": "按本轮战术目标组织局内话术。",
                    "speech_text": tactic_speech,
                }

            if suspected_target is not None:
                return {
                    "inner_thought": "延续已有怀疑对象，给出可被票型验证的公开压力。",
                    "speech_text": render_suspicion_speech(suspected_target),
                }

            return {
                "inner_thought": "先给出保守公开发言。",
                "speech_text": render_default_speech(),
            }

        if response_schema is VoteResponse:
            checked_wolf = _pick_checked_wolf_target(prompt)
            if _extract_self_role(prompt) == "SEER" and checked_wolf is not None:
                return {
                    "inner_thought": "优先投给自己查验到的狼人。",
                    "vote_target": checked_wolf,
                }

            tactic_target = _pick_tactic_target(prompt)
            if _extract_tactic_label(prompt) in {"归票", "冲锋", "倒钩"} and tactic_target is not None:
                return {
                    "inner_thought": "按本轮战术目标集中票型。",
                    "vote_target": tactic_target,
                }

            suspected_target = _pick_stance_target(prompt)
            if suspected_target is not None:
                return {
                    "inner_thought": "延续当前怀疑分最高的对象投票。",
                    "vote_target": suspected_target,
                }

            targets = _extract_alive_targets(prompt)
            return {
                "inner_thought": "优先投给当前最靠前的合法目标。",
                "vote_target": targets[0] if targets else 0,
            }

        if response_schema is TargetedActionResponse:
            killed_tonight = _extract_killed_tonight(prompt)
            if killed_tonight:
                return {
                    "inner_thought": "夜里已经有人倒下，优先考虑救人。",
                    "target": None,
                    "use_antidote": True,
                    "use_poison": False,
                }

            targets = _extract_alive_targets(prompt)
            suspected_target = _pick_stance_target(prompt)
            tactic_target = _pick_tactic_target(prompt)
            return {
                "inner_thought": "优先选择当前最有压力的合法目标。",
                "target": (
                    tactic_target
                    if tactic_target is not None
                    else suspected_target
                    if suspected_target is not None
                    else targets[0] if targets else None
                ),
                "use_antidote": False,
                "use_poison": False,
            }

        raise TypeError(f"unsupported response schema: {response_schema}")


def build_local_llm_client() -> FallbackLLMClient:
    return FallbackLLMClient(
        client=JSONModeClient(provider=LocalRuleBasedProvider()),
    )
