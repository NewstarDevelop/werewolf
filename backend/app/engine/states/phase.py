from enum import StrEnum


class GamePhase(StrEnum):
    INIT = "INIT"
    CHECK_WIN = "CHECK_WIN"
    NIGHT_START = "NIGHT_START"
    DAY_START = "DAY_START"
    VOTING = "VOTING"
    GAME_OVER = "GAME_OVER"
