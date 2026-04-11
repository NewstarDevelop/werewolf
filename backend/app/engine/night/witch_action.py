from dataclasses import dataclass

from app.domain.enums import Role
from app.domain.game_context import GameContext


@dataclass(slots=True, kw_only=True)
class WitchResources:
    has_antidote: bool = True
    has_poison: bool = True


def resolve_witch_action(
    context: GameContext,
    *,
    witch_seat: int,
    resources: WitchResources,
    save_target: int | None = None,
    poison_target: int | None = None,
) -> WitchResources:
    witch = context.players[witch_seat]
    if not witch.is_alive or witch.role is not Role.WITCH:
        raise ValueError("witch seat must belong to a living witch")

    if save_target is not None:
        if not resources.has_antidote:
            raise ValueError("antidote is not available")
        if save_target == witch_seat:
            raise ValueError("witch cannot save self")
        if save_target not in context.killed_tonight:
            raise ValueError("save target must already be in killed_tonight")
        context.killed_tonight.remove(save_target)
        resources.has_antidote = False

    if poison_target is not None:
        if not resources.has_poison:
            raise ValueError("poison is not available")
        if poison_target == witch_seat:
            raise ValueError("witch cannot poison self")
        target = context.players[poison_target]
        if not target.is_alive:
            raise ValueError("poison target must be alive")
        context.mark_killed_tonight(poison_target)
        resources.has_poison = False

    return resources
