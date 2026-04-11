from typing import Literal, TypedDict

from app.domain.enums import Role
from app.domain.game_context import GameContext

WinningSide = Literal["GOOD", "WOLF"]


class WinCheckResult(TypedDict):
    winning_side: WinningSide
    summary: str


def check_win(context: GameContext) -> WinCheckResult | None:
    alive_roles = [
        player.role
        for player in context.players.values()
        if player.is_alive
    ]

    alive_wolves = [role for role in alive_roles if role is Role.WOLF]
    alive_villagers = [role for role in alive_roles if role is Role.VILLAGER]
    alive_specials = [
        role
        for role in alive_roles
        if role in {Role.SEER, Role.WITCH, Role.HUNTER}
    ]

    if not alive_wolves:
        return {
            "winning_side": "GOOD",
            "summary": "狼人已全部出局，好人阵营获胜。",
        }

    if not alive_villagers:
        return {
            "winning_side": "WOLF",
            "summary": "平民已全部出局，狼人阵营获胜。",
        }

    if not alive_specials:
        return {
            "winning_side": "WOLF",
            "summary": "神职已全部出局，狼人阵营获胜。",
        }

    return None
