from dataclasses import dataclass, field
from typing import Literal

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer

TacticLabel = Literal[
    "悍跳",
    "倒钩",
    "冲锋",
    "深水",
    "报验人",
    "盘狼坑",
    "归票",
    "保留身份",
]


@dataclass(slots=True, kw_only=True)
class AITactic:
    label: TacticLabel
    objective: str
    target_seats: list[int] = field(default_factory=list)
    guidance: str

    def to_prompt_line(self) -> str:
        targets = "无" if not self.target_seats else "、".join(
            f"{seat_id}号" for seat_id in self.target_seats
        )
        return f"{self.label}；目标：{targets}；公开打法：{self.guidance}"


def select_ai_tactic(context: GameContext, seat_id: int) -> AITactic:
    player = context.players[seat_id]
    if player.role is Role.WOLF:
        return _select_wolf_tactic(context, seat_id)
    return _select_good_tactic(context, seat_id)


def _select_wolf_tactic(context: GameContext, seat_id: int) -> AITactic:
    player = context.players[seat_id]
    alive_wolves = _alive_seats_by_role(context, Role.WOLF)
    living_teammates = [wolf_seat for wolf_seat in alive_wolves if wolf_seat != seat_id]
    pressured_teammate = _first_scored_seat(player, living_teammates, minimum_score=2)
    suspected_good = _first_scored_seat(
        player,
        [
            candidate
            for candidate in context.alive_seat_ids()
            if candidate != seat_id and context.players[candidate].role is not Role.WOLF
        ],
        minimum_score=1,
    )

    if pressured_teammate is not None:
        return AITactic(
            label="倒钩",
            objective="顺势质疑被场上盯住的狼同伴，换取自己的好人面。",
            target_seats=[pressured_teammate],
            guidance="可以轻踩目标的发言漏洞，但不要暴露你知道对方身份。",
        )

    personality = getattr(player, "personality", "")
    if "悍跳" in personality and len(alive_wolves) >= 2:
        return AITactic(
            label="悍跳",
            objective="主动抢夺神职视角，把焦点引向外置位。",
            target_seats=([suspected_good] if suspected_good is not None else []),
            guidance="可以伪装成有信息的一方，但必须给出像好人视角的理由。",
        )

    if suspected_good is not None and len(alive_wolves) >= 2:
        return AITactic(
            label="冲锋",
            objective="集中火力推动一个好人位成为白天焦点。",
            target_seats=[suspected_good],
            guidance="发言要明确给压力，争取把票型集中到目标身上。",
        )

    return AITactic(
        label="深水",
        objective="降低存在感，保留狼队生存空间。",
        target_seats=[],
        guidance="少跳身份，多顺着场上共识补逻辑，避免无理由强冲。",
    )


def _select_good_tactic(context: GameContext, seat_id: int) -> AITactic:
    player = context.players[seat_id]
    checked_wolf = _latest_alive_seer_check(context, seat_id, result="WOLF")
    if player.role is Role.SEER and checked_wolf is not None:
        return AITactic(
            label="报验人",
            objective="公开查杀并推动白天放逐。",
            target_seats=[checked_wolf],
            guidance="稳定复述验人链，明确今天优先出查杀。",
        )

    checked_good = _latest_alive_seer_check(context, seat_id, result="GOOD")
    if player.role is Role.SEER and checked_good is not None:
        return AITactic(
            label="报验人",
            objective="公开或半公开金水信息，建立可信视角。",
            target_seats=[checked_good],
            guidance="保护金水，同时给出下一晚查验方向。",
        )

    suspected_target = _first_scored_seat(
        player,
        [candidate for candidate in context.alive_seat_ids() if candidate != seat_id],
        minimum_score=1,
    )
    if suspected_target is not None:
        label: TacticLabel = "归票" if _should_push_vote(context, player, suspected_target) else "盘狼坑"
        return AITactic(
            label=label,
            objective="把已有怀疑转化为可检验的公开压力。",
            target_seats=[suspected_target],
            guidance=(
                "明确建议大家集中票型。"
                if label == "归票"
                else "列出目标的发言、票型或站边矛盾。"
            ),
        )

    if player.role in {Role.WITCH, Role.HUNTER}:
        return AITactic(
            label="保留身份",
            objective="不急着暴露神职身份，先观察发言和票型。",
            target_seats=[],
            guidance="可以暗示自己有判断，但不要无理由交出全部身份信息。",
        )

    return AITactic(
        label="盘狼坑",
        objective="从公开发言和票型中整理可能的狼人范围。",
        target_seats=[],
        guidance="先提出可验证的问题，等后置位补充信息后再收束。",
    )


def _alive_seats_by_role(context: GameContext, role: Role) -> list[int]:
    return [
        seat_id
        for seat_id, player in sorted(context.players.items())
        if player.is_alive and player.role is role
    ]


def _first_scored_seat(
    player: object,
    candidates: list[int],
    *,
    minimum_score: int,
) -> int | None:
    if not isinstance(player, AIPlayer):
        return candidates[0] if candidates and minimum_score <= 0 else None
    candidate_set = set(candidates)
    for seat_id, score in player.top_suspicions(limit=9):
        if seat_id in candidate_set and score >= minimum_score:
            return seat_id
    return None


def _latest_alive_seer_check(
    context: GameContext,
    seat_id: int,
    *,
    result: Literal["GOOD", "WOLF"],
) -> int | None:
    alive_seats = set(context.alive_seat_ids())
    for night in reversed(context.night_actions):
        if (
            night.seer_seat == seat_id
            and night.seer_result == result
            and night.seer_target in alive_seats
        ):
            return night.seer_target
    return None


def _should_push_vote(context: GameContext, player: object, target_seat: int) -> bool:
    if context.phase == "VOTING":
        return True
    if not isinstance(player, AIPlayer):
        return False
    return player.suspicion_scores.get(target_seat, 0) >= 3
