"""Game data models for in-memory storage."""
import uuid
import random
import time
from typing import Optional
from dataclasses import dataclass, field

from app.schemas.enums import (
    GameStatus, GamePhase, Role, ActionType, MessageType, Winner
)
from app.schemas.player import Personality


# AI personality templates
AI_PERSONALITIES = [
    Personality(name="暴躁的老王", trait="激进", speaking_style="口语化"),
    Personality(name="理性的Alice", trait="逻辑流", speaking_style="严谨"),
    Personality(name="沉默的张三", trait="保守", speaking_style="简短"),
    Personality(name="热情的小红", trait="直觉流", speaking_style="幽默"),
    Personality(name="老练的李四", trait="随波逐流", speaking_style="口语化"),
    Personality(name="精明的王五", trait="逻辑流", speaking_style="严谨"),
    Personality(name="冲动的赵六", trait="激进", speaking_style="口语化"),
    Personality(name="稳重的钱七", trait="保守", speaking_style="简短"),
]


# Role alignment sets for win condition and game logic
WOLF_ROLES = {Role.WEREWOLF, Role.WOLF_KING, Role.WHITE_WOLF_KING}
VILLAGER_ROLES = {Role.VILLAGER}
GOD_ROLES = {Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD}


@dataclass
class GameConfig:
    """Game configuration for different game modes."""
    player_count: int  # 9 or 12
    roles: list[Role]
    night_order: list[GamePhase]
    wolf_king_variant: Optional[str] = None  # "wolf_king" or "white_wolf_king" (only for 12-player)


# Classic 9-player configuration
CLASSIC_9_CONFIG = GameConfig(
    player_count=9,
    roles=[
        Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
        Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
        Role.SEER, Role.WITCH, Role.HUNTER
    ],
    night_order=[
        GamePhase.NIGHT_WEREWOLF_CHAT,
        GamePhase.NIGHT_WEREWOLF,
        GamePhase.NIGHT_SEER,
        GamePhase.NIGHT_WITCH
    ]
)


def get_classic_12_config(wolf_king_variant: str) -> GameConfig:
    """Get classic 12-player configuration with specified wolf king variant.

    Args:
        wolf_king_variant: Either "wolf_king" or "white_wolf_king"

    Returns:
        GameConfig for 12-player mode
    """
    if wolf_king_variant not in ["wolf_king", "white_wolf_king"]:
        raise ValueError(f"Invalid wolf_king_variant: {wolf_king_variant}")

    wolf_king_role = Role.WOLF_KING if wolf_king_variant == "wolf_king" else Role.WHITE_WOLF_KING

    return GameConfig(
        player_count=12,
        roles=[
            Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
            wolf_king_role,
            Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD,
            Role.VILLAGER, Role.VILLAGER, Role.VILLAGER, Role.VILLAGER
        ],
        night_order=[
            GamePhase.NIGHT_WEREWOLF_CHAT,
            GamePhase.NIGHT_WEREWOLF,
            GamePhase.NIGHT_GUARD,
            GamePhase.NIGHT_SEER,
            GamePhase.NIGHT_WITCH
        ],
        wolf_king_variant=wolf_king_variant
    )


@dataclass
class Player:
    """Player model."""
    seat_id: int
    role: Role
    is_human: bool = False
    is_alive: bool = True
    personality: Optional[Personality] = None
    # Witch specific
    has_save_potion: bool = True
    has_poison_potion: bool = True
    # Hunter specific
    can_shoot: bool = True  # False if poisoned
    # Seer specific
    verified_players: dict[int, bool] = field(default_factory=dict)
    # Werewolf specific
    teammates: list[int] = field(default_factory=list)

    def __post_init__(self):
        if self.verified_players is None:
            self.verified_players = {}
        if self.teammates is None:
            self.teammates = []


@dataclass
class Message:
    """Message model."""
    id: int
    game_id: str
    day: int
    seat_id: int  # 0 for system
    content: str
    msg_type: MessageType = MessageType.SPEECH


@dataclass
class Action:
    """Action record model."""
    id: int
    game_id: str
    day: int
    phase: str
    player_id: int
    action_type: ActionType
    target_id: Optional[int] = None


@dataclass
class Game:
    """Game model."""
    id: str
    status: GameStatus = GameStatus.WAITING
    day: int = 1
    phase: GamePhase = GamePhase.NIGHT_START
    winner: Optional[Winner] = None
    language: str = "zh"  # Game language: "zh" or "en"
    players: dict[int, Player] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    current_actor_seat: Optional[int] = None
    human_seat: int = 1  # Deprecated: use human_seats instead
    # Multi-player support (WL-008 fix)
    human_seats: list[int] = field(default_factory=list)  # List of human player seats
    player_mapping: dict[str, int] = field(default_factory=dict)  # {player_id: seat_id}
    # Night phase tracking
    night_kill_target: Optional[int] = None
    wolf_votes: dict[int, int] = field(default_factory=dict)  # wolf_seat -> target_seat
    wolf_chat_completed: set[int] = field(default_factory=set)  # Seats that completed wolf chat
    guard_target: Optional[int] = None  # Guard's protection target this night
    guard_last_target: Optional[int] = None  # Last night's protection target (for consecutive guard rule)
    white_wolf_king_used_explode: bool = False  # Whether white wolf king has used self-destruct
    white_wolf_king_explode_target: Optional[int] = None  # Target of white wolf king's self-destruct this night
    seer_verified_this_night: bool = False  # Track if seer verified this night
    witch_save_decided: bool = False  # Track if witch save decision made this night
    witch_poison_decided: bool = False  # Track if witch poison decision made this night
    # Day phase tracking
    day_votes: dict[int, int] = field(default_factory=dict)  # voter_seat -> target_seat
    speech_order: list[int] = field(default_factory=list)
    current_speech_index: int = 0
    _spoken_seats_this_round: set[int] = field(default_factory=set)  # P0 Fix: Track who spoke
    # Death tracking
    pending_deaths: list[int] = field(default_factory=list)  # Seats to die (can be blocked by guard/witch)
    pending_deaths_unblockable: list[int] = field(default_factory=list)  # Deaths that cannot be blocked (white wolf king explode)
    last_night_deaths: list[int] = field(default_factory=list)
    # Message counter
    _message_counter: int = 0
    _action_counter: int = 0

    def get_player(self, seat_id: int) -> Optional[Player]:
        """Get player by seat ID."""
        return self.players.get(seat_id)

    def get_alive_players(self) -> list[Player]:
        """Get all alive players."""
        return [p for p in self.players.values() if p.is_alive]

    def get_alive_seats(self) -> list[int]:
        """Get all alive player seat IDs, sorted by seat_id."""
        return sorted([p.seat_id for p in self.get_alive_players()])

    def get_werewolves(self) -> list[Player]:
        """Get all werewolf players (includes wolf king and white wolf king)."""
        return [p for p in self.players.values() if p.role in WOLF_ROLES]

    def get_alive_werewolves(self) -> list[Player]:
        """Get alive werewolves (includes wolf king and white wolf king)."""
        return [p for p in self.get_werewolves() if p.is_alive]

    def get_player_by_role(self, role: Role) -> Optional[Player]:
        """Get player by role (for unique roles)."""
        for p in self.players.values():
            if p.role == role:
                return p
        return None

    def add_message(
        self,
        seat_id: int,
        content: str,
        msg_type: MessageType = MessageType.SPEECH
    ) -> Message:
        """Add a message to the game."""
        self._message_counter += 1
        msg = Message(
            id=self._message_counter,
            game_id=self.id,
            day=self.day,
            seat_id=seat_id,
            content=content,
            msg_type=msg_type
        )
        self.messages.append(msg)
        return msg

    def add_action(
        self,
        player_id: int,
        action_type: ActionType,
        target_id: Optional[int] = None
    ) -> Action:
        """Record an action."""
        self._action_counter += 1
        action = Action(
            id=self._action_counter,
            game_id=self.id,
            day=self.day,
            phase=self.phase.value,
            player_id=player_id,
            action_type=action_type,
            target_id=target_id
        )
        self.actions.append(action)
        return action

    def kill_player(self, seat_id: int, by_poison: bool = False) -> None:
        """Kill a player."""
        player = self.get_player(seat_id)
        if player:
            player.is_alive = False
            if by_poison and player.role == Role.HUNTER:
                player.can_shoot = False

    def check_winner(self) -> Optional[Winner]:
        """
        Check if game has a winner.

        Win conditions for 12-player mode:
        - Villagers win if: all werewolves are dead (includes wolf king/white wolf king)
        - Werewolves win if:
          1. alive_wolves >= alive_good_people (屠边，狼数 >= 好人总数，含神职)
          2. all villagers are dead (屠民)
          3. all gods are dead (屠神)
        """
        alive_players = self.get_alive_players()

        # Count by alignment
        alive_wolves = [p for p in alive_players if p.role in WOLF_ROLES]
        alive_villagers = [p for p in alive_players if p.role in VILLAGER_ROLES]
        alive_gods = [p for p in alive_players if p.role in GOD_ROLES]

        # Villagers win if all werewolves are dead
        if len(alive_wolves) == 0:
            return Winner.VILLAGER

        # Werewolves win condition 1: 屠边 (wolves >= total good people including gods)
        alive_good_people = len(alive_villagers) + len(alive_gods)
        if len(alive_wolves) >= alive_good_people:
            return Winner.WEREWOLF

        # Werewolves win condition 2: 屠民 (all villagers dead)
        if len(alive_villagers) == 0:
            return Winner.WEREWOLF

        # Werewolves win condition 3: 屠神 (all gods dead)
        if len(alive_gods) == 0:
            return Winner.WEREWOLF

        # Game continues
        return None

    def is_player_turn(self, player_id: str) -> bool:
        """
        Check if it's the given player's turn to act.

        Args:
            player_id: Player identifier

        Returns:
            True if it's this player's turn, False otherwise
        """
        if player_id not in self.player_mapping:
            return False

        seat_id = self.player_mapping[player_id]
        return self.current_actor_seat == seat_id

    def _get_pending_action_for_player(self, player: Player) -> Optional[dict]:
        """
        Determine what action the player needs to take.

        Returns a dict matching PendingAction schema, or None if no action needed.
        """
        phase = self.phase
        role = player.role

        # Hunter can shoot after being eliminated (by vote/kill)
        # Wolf king can shoot when voted out during day
        if phase == GamePhase.DEATH_SHOOT:
            if self.current_actor_seat == player.seat_id:
                # Hunter must be able to shoot (not poisoned)
                if player.role == Role.HUNTER and not player.can_shoot:
                    return None
                # Wolf king can always shoot when in this phase
                if player.role in [Role.HUNTER, Role.WOLF_KING]:
                    alive_seats = self.get_alive_seats()
                    return {
                        "type": ActionType.SHOOT.value,
                        "choices": alive_seats + [0],  # 0 = skip
                        "message": "你可以开枪带走一名玩家"
                    }

        # Legacy hunter shoot phase (backward compatibility)
        if phase == GamePhase.HUNTER_SHOOT and role == Role.HUNTER:
            if self.current_actor_seat == player.seat_id and player.can_shoot:
                alive_seats = self.get_alive_seats()
                return {
                    "type": ActionType.SHOOT.value,
                    "choices": alive_seats + [0],  # 0 = skip
                    "message": "你可以开枪带走一名玩家"
                }

        if not player.is_alive:
            return None

        alive_seats = self.get_alive_seats()
        other_alive = [s for s in alive_seats if s != player.seat_id]

        # Night werewolf chat phase
        if phase == GamePhase.NIGHT_WEREWOLF_CHAT and role == Role.WEREWOLF:
            if player.seat_id not in self.wolf_chat_completed:
                return {
                    "type": ActionType.SPEAK.value,
                    "choices": [],
                    "message": "与狼队友讨论今晚击杀目标（发言后自动进入投票）"
                }

        # Night werewolf phase
        if phase == GamePhase.NIGHT_WEREWOLF and role == Role.WEREWOLF:
            if player.seat_id not in self.wolf_votes:
                kill_targets = [s for s in alive_seats if s != player.seat_id]
                return {
                    "type": ActionType.KILL.value,
                    "choices": kill_targets,
                    "message": "请选择今晚要击杀的目标"
                }

        # Night werewolf phase - White wolf king can choose to self-destruct
        elif phase == GamePhase.NIGHT_WEREWOLF and role == Role.WHITE_WOLF_KING:
            if player.seat_id not in self.wolf_votes:
                # White wolf king can either vote for kill OR self-destruct
                if not self.white_wolf_king_used_explode:
                    kill_targets = [s for s in alive_seats if s != player.seat_id]
                    return {
                        "type": ActionType.KILL.value,  # Frontend will show both KILL and SELF_DESTRUCT options
                        "choices": kill_targets,
                        "message": "请投票击杀目标，或选择自爆（使用自爆动作）"
                    }
                else:
                    # Already used self-destruct, can only vote for normal kill
                    kill_targets = [s for s in alive_seats if s != player.seat_id]
                    return {
                        "type": ActionType.KILL.value,
                        "choices": kill_targets,
                        "message": "请选择今晚要击杀的目标"
                    }

        # Night guard phase
        elif phase == GamePhase.NIGHT_GUARD and role == Role.GUARD:
            # Guard can protect any alive player (including self)
            # Filter out last night's target (cannot guard same person consecutively)
            protect_choices = alive_seats.copy()
            if self.guard_last_target and self.guard_last_target in protect_choices:
                protect_choices.remove(self.guard_last_target)

            return {
                "type": ActionType.PROTECT.value,
                "choices": protect_choices + [0],  # 0 = skip
                "message": "请选择今晚要守护的玩家，或跳过"
            }

        # Night seer phase
        elif phase == GamePhase.NIGHT_SEER and role == Role.SEER:
            if self.seer_verified_this_night:
                return None
            unverified = [s for s in other_alive if s not in player.verified_players]
            if not unverified:
                return None
            return {
                "type": ActionType.VERIFY.value,
                "choices": unverified,
                "message": "请选择要查验的玩家"
            }

        # Night witch phase
        elif phase == GamePhase.NIGHT_WITCH and role == Role.WITCH:
            used_save_this_night = any(
                a.day == self.day
                and a.player_id == player.seat_id
                and a.action_type == ActionType.SAVE
                for a in self.actions
            )

            # Step 1: Save potion decision
            if not self.witch_save_decided:
                if player.has_save_potion and self.night_kill_target:
                    return {
                        "type": ActionType.SAVE.value,
                        "choices": [self.night_kill_target, 0],  # 0 = skip
                        "message": f"今晚{self.night_kill_target}号被杀，是否使用解药？"
                    }

                no_save_reason = "今晚无人被杀" if self.night_kill_target is None else "你没有解药"
                return {
                    "type": ActionType.SAVE.value,
                    "choices": [0],
                    "message": f"{no_save_reason}，点击技能按钮跳过解药决策"
                }

            # Step 2: Poison potion decision
            if not self.witch_poison_decided:
                if used_save_this_night:
                    return {
                        "type": ActionType.POISON.value,
                        "choices": [0],
                        "message": "你今晚已使用解药，无法再使用毒药，点击技能按钮继续"
                    }

                if player.has_poison_potion:
                    return {
                        "type": ActionType.POISON.value,
                        "choices": other_alive + [0],  # 0 = skip
                        "message": f"今晚{self.night_kill_target}号被杀，是否使用毒药？选择目标或跳过"
                        if self.night_kill_target is not None
                        else "是否使用毒药？选择目标或跳过"
                    }

                return {
                    "type": ActionType.POISON.value,
                    "choices": [0],
                    "message": "你没有可用的毒药，点击技能按钮继续"
                }

        # Day speech phase
        elif phase == GamePhase.DAY_SPEECH:
            if (self.current_speech_index < len(self.speech_order) and
                self.speech_order[self.current_speech_index] == player.seat_id):
                return {
                    "type": ActionType.SPEAK.value,
                    "choices": [],
                    "message": "轮到你发言了"
                }

        # Day vote phase
        elif phase == GamePhase.DAY_VOTE:
            if player.seat_id not in self.day_votes:
                return {
                    "type": ActionType.VOTE.value,
                    "choices": other_alive + [0],  # 0 = abstain
                    "message": "请投票选择要放逐的玩家，或弃票"
                }

        return None

    def get_state_for_player(self, player_id: Optional[str] = None) -> dict:
        """
        Get game state filtered for specific player's perspective.

        This replaces the P0 temporary filter_sensitive_info method with
        proper multi-player support using player_mapping.

        Args:
            player_id: Player identifier. If None, returns observer view.

        Returns:
            Filtered game state dictionary safe for the requesting player.
        """
        # Find the player's seat using player_mapping
        seat = self.player_mapping.get(player_id) if player_id else None
        player = self.get_player(seat) if seat else None

        # Base state (always safe to share)
        state = {
            "game_id": self.id,
            "status": self.status.value,
            "day": self.day,
            "phase": self.phase.value,
            "current_actor": self.current_actor_seat,  # Renamed: current_actor_seat -> current_actor
            "alive_seats": self.get_alive_seats(),
            "pending_deaths": self.pending_deaths,
            "current_speech_index": self.current_speech_index,
        }

        # Add players list (frontend expects this field)
        players = []
        for p in self.players.values():
            player_public = {
                "seat_id": p.seat_id,
                "is_alive": p.is_alive,
                "is_human": p.is_human,
                "name": p.personality.name if p.personality else None,
                "role": None  # Default: hide role
            }

            # Show role when: 1) Game finished, or 2) It's the requesting player
            if self.status == GameStatus.FINISHED:
                player_public["role"] = p.role.value
            elif player and p.seat_id == seat:
                player_public["role"] = p.role.value

            players.append(player_public)

        state["players"] = players

        # Filter messages - remove vote_thought and wolf_chat from non-privileged players
        filtered_messages = []
        for msg in self.messages:
            # Always hide vote_thought
            if msg.msg_type == MessageType.VOTE_THOUGHT:
                continue
            # Hide wolf_chat unless player is a werewolf
            if msg.msg_type == MessageType.WOLF_CHAT:
                if not player or player.role != Role.WEREWOLF:
                    continue
            filtered_messages.append({
                "seat_id": msg.seat_id,
                "text": msg.content,  # Renamed: content -> text
                "type": msg.msg_type.value,
                "day": msg.day
            })
        state["message_log"] = filtered_messages  # Renamed: messages -> message_log

        # Add winner field (always include, null if game not finished)
        state["winner"] = self.winner.value if self.winner else None

        # Add player-specific info if authenticated
        if player:
            state["my_seat"] = seat
            state["my_role"] = player.role.value

            # Werewolf-specific info
            if player.role == Role.WEREWOLF:
                state["wolf_teammates"] = player.teammates
                state["night_kill_target"] = self.night_kill_target
                # Wolf votes visible (for frontend to show teammate votes)
                state["wolf_votes_visible"] = self.wolf_votes
            else:
                state["wolf_votes_visible"] = {}

            # Witch-specific info
            if player.role == Role.WITCH:
                state["has_save_potion"] = player.has_save_potion
                state["has_poison_potion"] = player.has_poison_potion
                # Only show kill target while witch is making night decisions
                if self.phase == GamePhase.NIGHT_WITCH and not self.witch_poison_decided:
                    state["night_kill_target"] = self.night_kill_target

            # Seer-specific info
            if player.role == Role.SEER:
                state["verified_results"] = player.verified_players

            # Calculate pending_action for human player
            state["pending_action"] = self._get_pending_action_for_player(player)
        else:
            # Observer view - minimal info
            state["my_seat"] = None
            state["my_role"] = None
            state["wolf_votes_visible"] = {}
            state["pending_action"] = None

        return state

    # Backward compatibility alias for P0 hotfix
    def filter_sensitive_info(self, player_id: Optional[str] = None) -> dict:
        """Deprecated: Use get_state_for_player instead."""
        return self.get_state_for_player(player_id)


class GameStore:
    """In-memory game storage with LRU/TTL management.

    P0-PERF-001 Fix: Added capacity limits and TTL-based cleanup to prevent
    unbounded memory growth from malicious or accidental game creation.

    P0-STAB-001 Fix: Added per-game locks to prevent concurrent state corruption.
    """

    MAX_GAMES = 1000  # Maximum concurrent games
    GAME_TTL_SECONDS = 7200  # 2 hours TTL for inactive games

    def __init__(self):
        self.games: dict[str, Game] = {}
        self._last_access: dict[str, float] = {}  # game_id -> timestamp
        self._locks: dict[str, "asyncio.Lock"] = {}  # P0-STAB-001: per-game locks

    def get_lock(self, game_id: str) -> "asyncio.Lock":
        """Get or create a lock for the specified game.

        P0-STAB-001 Fix: Ensures thread-safe access to game state.
        """
        import asyncio
        if game_id not in self._locks:
            self._locks[game_id] = asyncio.Lock()
        return self._locks[game_id]

    def _cleanup_old_games(self) -> int:
        """Remove games that haven't been accessed within TTL.

        Returns:
            Number of games cleaned up
        """
        from app.services.log_manager import clear_game_logs

        now = time.time()
        to_remove = []

        for game_id, last_access in self._last_access.items():
            if now - last_access > self.GAME_TTL_SECONDS:
                to_remove.append(game_id)

        for game_id in to_remove:
            if game_id in self.games:
                del self.games[game_id]
            if game_id in self._last_access:
                del self._last_access[game_id]
            if game_id in self._locks:
                del self._locks[game_id]
            # Clean up associated logs
            clear_game_logs(game_id)

        return len(to_remove)

    def create_game(
        self,
        human_seat: Optional[int] = None,
        human_role: Optional[Role] = None,
        language: str = "zh",
        game_id: Optional[str] = None,
        config: Optional[GameConfig] = None
    ) -> Game:
        """Create a new game with random role assignment.

        P0-PERF-001 Fix: Enforces capacity limits and cleans up old games.

        Args:
            human_seat: Seat ID for human player (1-based). If None, random.
            human_role: Specific role for human player. If None, random.
            language: Game language ("zh" or "en")
            game_id: Custom game ID. If None, auto-generated.
            config: Game configuration. If None, defaults to CLASSIC_9_CONFIG.
        """
        # Use default 9-player config if not specified (backward compatibility)
        if config is None:
            config = CLASSIC_9_CONFIG

        # Check capacity and cleanup if needed
        if len(self.games) >= self.MAX_GAMES:
            cleaned = self._cleanup_old_games()
            if len(self.games) >= self.MAX_GAMES:
                raise ValueError(
                    f"Server at capacity ({self.MAX_GAMES} games). "
                    f"Cleaned {cleaned} old games but still full. Try again later."
                )

        if game_id is None:
            game_id = str(uuid.uuid4())[:8]
        game = Game(id=game_id, language=language)

        # Get role distribution from config
        roles = config.roles.copy()

        # Determine human seat
        if human_seat is None:
            human_seat = random.randint(1, config.player_count)
        game.human_seat = human_seat

        # If human role is specified, ensure they get it
        if human_role:
            if human_role in roles:
                roles.remove(human_role)
            else:
                raise ValueError(f"Role {human_role} not available in this game mode")
            random.shuffle(roles)
            roles.insert(human_seat - 1, human_role)
        else:
            random.shuffle(roles)

        # Shuffle personalities
        personalities = AI_PERSONALITIES.copy()
        random.shuffle(personalities)

        # Create players
        wolf_seats = []  # All wolf-aligned seats (including wolf king variants)
        for i, role in enumerate(roles):
            seat_id = i + 1
            is_human = (seat_id == human_seat)

            player = Player(
                seat_id=seat_id,
                role=role,
                is_human=is_human,
                personality=None if is_human else personalities[i % len(personalities)]
            )

            # Track all wolf-aligned roles for teammate relationship
            if role in WOLF_ROLES:
                wolf_seats.append(seat_id)

            game.players[seat_id] = player

        # Set werewolf teammates (includes wolf king/white wolf king)
        for seat_id in wolf_seats:
            player = game.players[seat_id]
            player.teammates = [s for s in wolf_seats if s != seat_id]

        game.status = GameStatus.PLAYING
        self.games[game_id] = game
        self._last_access[game_id] = time.time()  # P0-PERF-001: Track access time
        return game

    def get_game(self, game_id: str) -> Optional[Game]:
        """Get game by ID.

        P0-PERF-001 Fix: Updates last access time for TTL management.
        """
        game = self.games.get(game_id)
        if game:
            self._last_access[game_id] = time.time()
        return game

    def delete_game(self, game_id: str) -> bool:
        """Delete a game.

        P0-PERF-001 Fix: Also cleans up associated logs and access tracking.
        P0-STAB-001 Fix: Also cleans up per-game lock.
        """
        from app.services.log_manager import clear_game_logs

        if game_id in self.games:
            del self.games[game_id]
            # Clean up access tracking
            if game_id in self._last_access:
                del self._last_access[game_id]
            # Clean up lock
            if game_id in self._locks:
                del self._locks[game_id]
            # Clean up associated logs
            clear_game_logs(game_id)
            return True
        return False


# Global game store instance
game_store = GameStore()
