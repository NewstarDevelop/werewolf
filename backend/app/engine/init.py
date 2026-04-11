import random
from dataclasses import dataclass

from app.domain.enums import Role
from app.domain.game_context import GameContext
from app.domain.player import AIPlayer, HumanPlayer

ROLE_DECK: tuple[Role, ...] = (
    Role.WOLF,
    Role.WOLF,
    Role.WOLF,
    Role.VILLAGER,
    Role.VILLAGER,
    Role.VILLAGER,
    Role.SEER,
    Role.WITCH,
    Role.HUNTER,
)

AI_PERSONALITIES: tuple[str, ...] = (
    "激进悍跳",
    "稳健分析",
    "沉默观察",
    "高压带票",
    "圆滑周旋",
    "情绪输出",
    "冷静拆点",
    "跟票伪装",
)


@dataclass(slots=True, kw_only=True)
class InitResult:
    context: GameContext
    human_seat_id: int
    human_role: Role


def initialize_game(*, rng: random.Random | None = None) -> InitResult:
    randomizer = rng or random.Random()
    shuffled_roles = list(ROLE_DECK)
    shuffled_personalities = list(AI_PERSONALITIES)
    randomizer.shuffle(shuffled_roles)
    randomizer.shuffle(shuffled_personalities)

    human_seat_id = randomizer.randint(1, 9)
    context = GameContext(phase="INIT")
    context.add_public_message("游戏开始，分配身份完毕。")

    personality_index = 0
    human_role = Role.VILLAGER

    for seat_id, role in enumerate(shuffled_roles, start=1):
        if seat_id == human_seat_id:
            human_role = role
            context.add_player(HumanPlayer(seat_id=seat_id, role=role))
            continue

        context.add_player(
            AIPlayer(
                seat_id=seat_id,
                role=role,
                personality=shuffled_personalities[personality_index],
            )
        )
        personality_index += 1

    return InitResult(
        context=context,
        human_seat_id=human_seat_id,
        human_role=human_role,
    )
