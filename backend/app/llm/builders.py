from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer
from app.domain.view_mask import build_player_view
from app.llm.prompts import (
    GOOD_SIDE_OBJECTIVE,
    NIGHT_TASK_TEMPLATE,
    SPEECH_TASK_TEMPLATE,
    SYSTEM_GUARDRAILS,
    VOTE_TASK_TEMPLATE,
    WOLF_SIDE_OBJECTIVE,
)
from app.llm.schemas import PromptEnvelope


def _objective_for_role(role: Role) -> str:
    return WOLF_SIDE_OBJECTIVE if role is Role.WOLF else GOOD_SIDE_OBJECTIVE


def _context_section(view: dict[str, object], personality: str) -> str:
    return (
        f"当前阶段：{view['phase']}\n"
        f"当前天数：第 {view['day_count']} 天\n"
        f"你的性格：{personality}\n"
        f"公开历史：{view['public_chat_history']}\n"
        f"私有记忆：{view['private_log']}\n"
        f"玩家视图：{view['players']}\n"
        f"今晚死亡名单：{view['killed_tonight']}"
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
        system_prompt=f"{SYSTEM_GUARDRAILS}\n{_objective_for_role(player.role)}",
        context_prompt=_context_section(view, personality),
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
        system_prompt=f"{SYSTEM_GUARDRAILS}\n{_objective_for_role(player.role)}",
        context_prompt=_context_section(view, personality),
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
        system_prompt=f"{SYSTEM_GUARDRAILS}\n{_objective_for_role(player.role)}",
        context_prompt=_context_section(view, personality),
        task_prompt=_task_with_allowed_targets(NIGHT_TASK_TEMPLATE, allowed_targets),
    )
