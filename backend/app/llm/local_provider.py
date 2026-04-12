import ast
from dataclasses import dataclass

from app.llm.client import JSONModeClient, LLMProvider
from app.llm.fallback import FallbackLLMClient
from app.llm.schemas import PromptEnvelope, SpeechResponse, TargetedActionResponse, VoteResponse


def _extract_section(prompt: PromptEnvelope, label: str) -> str | None:
    for line in prompt.context_prompt.splitlines():
        prefix = f"{label}："
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def _extract_players(prompt: PromptEnvelope) -> list[dict[str, object]]:
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
            return {
                "inner_thought": "先给出保守公开发言。",
                "speech_text": "信息还不够，我先听后置位怎么聊。",
            }

        if response_schema is VoteResponse:
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
            return {
                "inner_thought": "优先选择最靠前的合法目标。",
                "target": targets[0] if targets else None,
                "use_antidote": False,
                "use_poison": False,
            }

        raise TypeError(f"unsupported response schema: {response_schema}")


def build_local_llm_client() -> FallbackLLMClient:
    return FallbackLLMClient(
        client=JSONModeClient(provider=LocalRuleBasedProvider()),
    )
