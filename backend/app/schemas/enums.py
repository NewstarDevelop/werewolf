"""Game enums definition."""
from enum import Enum


class GameStatus(str, Enum):
    """Game status enum."""
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


class GamePhase(str, Enum):
    """Game phase enum."""
    NIGHT_START = "night_start"
    NIGHT_WEREWOLF_CHAT = "night_werewolf_chat"
    NIGHT_WEREWOLF = "night_werewolf"
    NIGHT_SEER = "night_seer"
    NIGHT_WITCH = "night_witch"
    DAY_ANNOUNCEMENT = "day_announcement"
    DAY_LAST_WORDS = "day_last_words"
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"
    DAY_VOTE_RESULT = "day_vote_result"
    HUNTER_SHOOT = "hunter_shoot"
    GAME_OVER = "game_over"


class Role(str, Enum):
    """Player role enum."""
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"


class ActionType(str, Enum):
    """Action type enum."""
    KILL = "kill"
    VERIFY = "verify"
    SAVE = "save"
    POISON = "poison"
    VOTE = "vote"
    SHOOT = "shoot"
    SPEAK = "speak"
    SKIP = "skip"


class MessageType(str, Enum):
    """Message type enum."""
    SPEECH = "speech"
    SYSTEM = "system"
    THOUGHT = "thought"
    LAST_WORDS = "last_words"
    WOLF_CHAT = "wolf_chat"
    VOTE_THOUGHT = "vote_thought"  # 投票阶段的内心思考（不传递给其他AI）


class Winner(str, Enum):
    """Winner enum."""
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    NONE = "none"
