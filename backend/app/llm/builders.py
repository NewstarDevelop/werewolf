import json

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer
from app.domain.view_mask import build_player_view
from app.llm.prompts import (
    GOOD_SIDE_OBJECTIVE,
    NIGHT_TASK_TEMPLATE,
    ROLE_STRATEGY_GUIDE,
    SPEECH_TASK_TEMPLATE,
    SYSTEM_GUARDRAILS,
    TACTICAL_REASONING_GUIDE,
    VOTE_TASK_TEMPLATE,
    WOLF_SIDE_OBJECTIVE,
)
from app.llm.schemas import PromptEnvelope
from app.llm.tactics import select_ai_tactic
from app.llm.phrasebook import phrasebook_prompt_guide


def _objective_for_role(role: Role) -> str:
    return WOLF_SIDE_OBJECTIVE if role is Role.WOLF else GOOD_SIDE_OBJECTIVE


def _players_from_view(view: dict[str, object]) -> list[dict[str, object]]:
    players = view.get("players")
    if not isinstance(players, list):
        return []
    return [player for player in players if isinstance(player, dict)]


def _seat_label(seat_id: object) -> str:
    return f"{seat_id}号" if isinstance(seat_id, int) else "未知座位"


def _seat_list(seats: list[int]) -> str:
    if not seats:
        return "无"
    return "、".join(_seat_label(seat_id) for seat_id in sorted(seats))


def _score_line(scores: list[tuple[int, int]]) -> str:
    if not scores:
        return "无"
    return "、".join(f"{_seat_label(seat_id)}({score})" for seat_id, score in scores)


def _ai_stance_summary(context: GameContext, seat_id: int) -> str:
    player = context.players[seat_id]
    if not isinstance(player, AIPlayer):
        return "无"
    return (
        f"怀疑：{_score_line(player.top_suspicions())}；"
        f"信任：{_score_line(player.top_trusts())}"
    )


def _recent_private_memory(context: GameContext, seat_id: int) -> list[str]:
    player = context.players[seat_id]
    if isinstance(player, AIPlayer):
        return player.private_memory[-8:]
    return context.get_private_log(seat_id)[-8:]


def _situation_summary(view: dict[str, object]) -> str:
    players = _players_from_view(view)
    alive_seats = [
        _seat_label(player.get("seat_id"))
        for player in players
        if player.get("is_alive") is True
    ]
    dead_seats = [
        _seat_label(player.get("seat_id"))
        for player in players
        if player.get("is_alive") is False
    ]
    known_roles = [
        f"{_seat_label(player.get('seat_id'))}={player.get('known_role')}"
        for player in players
        if player.get("known_role") is not None
    ]

    return (
        f"存活：{'、'.join(alive_seats) or '无'}；"
        f"出局：{'、'.join(dead_seats) or '无'}；"
        f"你已知身份：{'、'.join(known_roles) or '无'}"
    )


def _own_public_statements(view: dict[str, object], seat_id: int) -> list[str]:
    history = view.get("public_chat_history")
    if not isinstance(history, list):
        return []
    prefix = f"{seat_id}号发言："
    return [
        message
        for message in history
        if isinstance(message, str) and message.startswith(prefix)
    ][-5:]


def _recent_public_history(view: dict[str, object]) -> list[str]:
    history = view.get("public_chat_history")
    if not isinstance(history, list):
        return []
    return [message for message in history if isinstance(message, str)][-12:]


def _last_vote_line(context: GameContext, seat_id: int) -> str | None:
    snapshot = context.last_vote_result
    if snapshot is None:
        return None
    if seat_id in snapshot.ballots:
        return f"你上一轮投票给 {snapshot.ballots[seat_id]}号；结果：{snapshot.summary}"
    if seat_id in snapshot.abstentions:
        return f"你上一轮弃票；结果：{snapshot.summary}"
    return f"上一轮票型结果：{snapshot.summary}"


def _wolf_team_context(context: GameContext, seat_id: int) -> str:
    living_wolves = [
        player.seat_id
        for player in context.players.values()
        if player.role is Role.WOLF and player.is_alive
    ]
    dead_wolves = [
        player.seat_id
        for player in context.players.values()
        if player.role is Role.WOLF and not player.is_alive
    ]
    teammates = [wolf_seat for wolf_seat in sorted(living_wolves) if wolf_seat != seat_id]
    if not teammates:
        pressure = "你可能是场上最后一张狼，发言应更保守，避免无理由冲锋。"
    elif len(living_wolves) >= 3:
        pressure = "狼队人数完整，可分工悍跳、倒钩或冲票，但别同时暴露同一视角漏洞。"
    else:
        pressure = "狼队仍有队友在场，可根据局势选择保护队友、倒钩做身份，或集中冲票。"
    teammate_line = _seat_list(teammates) if teammates else "仅你自己"
    return f"狼队友存活：{teammate_line}；出局狼：{_seat_list(dead_wolves)}；{pressure}"


def _seer_check_chain(context: GameContext, seat_id: int) -> str:
    checks: list[str] = []
    checked_targets: set[int] = set()
    for night in context.night_actions:
        if night.seer_seat != seat_id or night.seer_target is None:
            continue
        checked_targets.add(night.seer_target)
        if night.seer_result == "WOLF":
            result = "狼人"
        elif night.seer_result == "GOOD":
            result = "好人"
        else:
            result = "未知"
        checks.append(f"第{night.day_count}夜验{night.seer_target}号={result}")

    unchecked_alive = [
        player.seat_id
        for player in context.players.values()
        if player.is_alive
        and player.seat_id != seat_id
        and player.seat_id not in checked_targets
    ]
    chain = "；".join(checks) if checks else "暂无验人链"
    badge_flow = _seat_list(unchecked_alive[:2])
    return (
        f"{chain}。发言应稳定复述验人顺序，给出后续警徽流/查验顺序："
        f"{badge_flow if badge_flow != '无' else '暂无可验目标'}。"
    )


def _strategic_continuity(context: GameContext, seat_id: int) -> str:
    player = context.players[seat_id]
    lines: list[str] = []

    last_vote = _last_vote_line(context, seat_id)
    if last_vote is not None:
        lines.append(last_vote)

    if player.role is Role.WOLF:
        lines.append(_wolf_team_context(context, seat_id))
    elif player.role is Role.SEER:
        lines.append(_seer_check_chain(context, seat_id))

    if not lines:
        lines.append("延续你之前公开表达过的站边和怀疑对象；若改站边，必须给出局内原因。")

    return " ".join(lines)


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _context_section(
    context: GameContext,
    view: dict[str, object],
    personality: str,
    *,
    seat_id: int,
) -> str:
    return (
        f"当前阶段：{view['phase']}\n"
        f"当前天数：第 {view['day_count']} 天\n"
        f"你的性格：{personality}\n"
        f"局势摘要：{_situation_summary(view)}\n"
        f"本轮战术目标：{select_ai_tactic(context, seat_id).to_prompt_line()}\n"
        f"战术连续性提示：{_strategic_continuity(context, seat_id)}\n"
        f"立场摘要：{_ai_stance_summary(context, seat_id)}\n"
        f"你的既往公开发言：{_stable_json(_own_public_statements(view, seat_id))}\n"
        f"公开历史：{_stable_json(_recent_public_history(view))}\n"
        f"私有记忆：{_stable_json(_recent_private_memory(context, seat_id))}\n"
        f"玩家视图JSON：{_stable_json(view)}"
    )


def _task_with_allowed_targets(task_prompt: str, allowed_targets: list[int] | None) -> str:
    if allowed_targets is None:
        return task_prompt
    return f"{task_prompt}\n合法目标：{allowed_targets}"


def build_speech_prompt(context: GameContext, *, seat_id: int) -> PromptEnvelope:
    player = context.players[seat_id]
    personality = player.personality if isinstance(player, AIPlayer) else "冷静判断"
    view = build_player_view(context, seat_id)
    return PromptEnvelope(
        system_prompt=(
            f"{SYSTEM_GUARDRAILS}\n"
            f"{_objective_for_role(player.role)}\n"
            f"{ROLE_STRATEGY_GUIDE}\n"
            f"{TACTICAL_REASONING_GUIDE}\n"
            f"{phrasebook_prompt_guide()}"
        ),
        context_prompt=_context_section(context, view, personality, seat_id=seat_id),
        task_prompt=SPEECH_TASK_TEMPLATE.format(seat_label=f"{seat_id}号"),
    )


def build_vote_prompt(
    context: GameContext,
    *,
    seat_id: int,
    allowed_targets: list[int] | None = None,
) -> PromptEnvelope:
    player = context.players[seat_id]
    personality = player.personality if isinstance(player, AIPlayer) else "冷静判断"
    view = build_player_view(context, seat_id)
    return PromptEnvelope(
        system_prompt=(
            f"{SYSTEM_GUARDRAILS}\n"
            f"{_objective_for_role(player.role)}\n"
            f"{ROLE_STRATEGY_GUIDE}\n"
            f"{TACTICAL_REASONING_GUIDE}\n"
            f"{phrasebook_prompt_guide()}"
        ),
        context_prompt=_context_section(context, view, personality, seat_id=seat_id),
        task_prompt=_task_with_allowed_targets(VOTE_TASK_TEMPLATE, allowed_targets),
    )


def build_night_prompt(
    context: GameContext,
    *,
    seat_id: int,
    allowed_targets: list[int] | None = None,
) -> PromptEnvelope:
    player = context.players[seat_id]
    personality = player.personality if isinstance(player, AIPlayer) else "冷静判断"
    view = build_player_view(context, seat_id)
    return PromptEnvelope(
        system_prompt=(
            f"{SYSTEM_GUARDRAILS}\n"
            f"{_objective_for_role(player.role)}\n"
            f"{ROLE_STRATEGY_GUIDE}\n"
            f"{TACTICAL_REASONING_GUIDE}\n"
            f"{phrasebook_prompt_guide()}"
        ),
        context_prompt=_context_section(context, view, personality, seat_id=seat_id),
        task_prompt=_task_with_allowed_targets(NIGHT_TASK_TEMPLATE, allowed_targets),
    )
