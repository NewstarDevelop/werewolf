"""Game data models for in-memory storage."""
import asyncio
import logging
import uuid
import secrets
import time
from typing import Optional
from dataclasses import dataclass, field

from app.schemas.enums import (
    GameStatus, GamePhase, Role, ActionType, MessageType, Winner
)
from app.schemas.player import Personality


_rng = secrets.SystemRandom()

# AI personality trait/style templates (14 unique combos for 12-player games)
# Names are loaded from i18n at runtime via get_ai_personalities()
_PERSONALITY_TEMPLATES = [
    ("激进", "口语化"),
    ("逻辑流", "严谨"),
    ("保守", "简短"),
    ("直觉流", "幽默"),
    ("随波逐流", "口语化"),
    ("逻辑流", "严谨"),
    ("激进", "口语化"),
    ("保守", "简短"),
    ("逻辑流", "幽默"),
    ("随波逐流", "简短"),
    ("直觉流", "严谨"),
    ("保守", "口语化"),
    ("激进", "幽默"),
    ("逻辑流", "口语化"),
]


def get_ai_personalities(language: str = "zh") -> list:
    """Get AI personalities with names from i18n translations."""
    from app.i18n.translations import load_translations
    translations = load_translations(language)
    names = translations.get("personality", {}).get("names", [])
    result = []
    for i, (trait, style) in enumerate(_PERSONALITY_TEMPLATES):
        name = names[i] if i < len(names) else f"Player_{i+1}"
        result.append(Personality(name=name, trait=trait, speaking_style=style))
    return result


# Role alignment sets for win condition and game logic
WOLF_ROLES = {Role.WEREWOLF, Role.WOLF_KING, Role.WHITE_WOLF_KING}
VILLAGER_ROLES = {Role.VILLAGER}
GOD_ROLES = {Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD}

# P2优化：狼人战术角色类型
WOLF_PERSONAS = ["aggressive", "hook", "deep"]  # 冲锋狼、倒钩狼、深水狼


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
    wolf_persona: Optional[str] = None  # P2优化：狼人战术角色 (aggressive/hook/deep)
    user_id: Optional[str] = None  # Link to authenticated user

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
    i18n_key: Optional[str] = None       # e.g. "system_messages.night_falls"
    i18n_params: Optional[dict] = None   # e.g. {"day": 1}


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
    state_version: int = 0  # State version for preventing race conditions
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
    wolf_night_plan: Optional[str] = None  # Summary of wolf team's night discussion and strategy
    guard_target: Optional[int] = None  # Guard's protection target this night
    guard_last_target: Optional[int] = None  # Last night's protection target (for consecutive guard rule)
    guard_decided: bool = False  # Track if guard has made decision this night
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
    # Role claim tracking (NEW-7: structured claims replace text matching)
    claimed_roles: dict[int, str] = field(default_factory=dict)  # seat_id -> claimed role (e.g. "seer")
    # Death tracking
    pending_deaths: list[int] = field(default_factory=list)  # Seats to die (can be blocked by guard/witch)
    pending_deaths_unblockable: list[int] = field(default_factory=list)  # Deaths that cannot be blocked (white wolf king explode)
    last_night_deaths: list[int] = field(default_factory=list)
    # Message counter
    _message_counter: int = 0
    _action_counter: int = 0

    def increment_version(self) -> int:
        """Increment state version on critical state changes."""
        self.state_version += 1
        return self.state_version

    def is_human_player(self, seat_id: int) -> bool:
        """Check if a seat belongs to a human player.

        P0-HIGH-002: Unified fallback logic for multi-player and single-player modes.
        Priority: human_seats (room mode) > is_human flag (single-player mode).
        """
        if self.human_seats:
            return seat_id in self.human_seats
        player = self.players.get(seat_id)
        return player.is_human if player else False

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

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """Get player by JWT player_id using player_mapping."""
        seat_id = self.player_mapping.get(player_id)
        if seat_id:
            return self.players.get(seat_id)
        return None

    def add_message(
        self,
        seat_id: int,
        content: str,
        msg_type: MessageType = MessageType.SPEECH,
        i18n_key: Optional[str] = None,
        i18n_params: Optional[dict] = None
    ) -> Message:
        """Add a message to the game."""
        self._message_counter += 1
        msg = Message(
            id=self._message_counter,
            game_id=self.id,
            day=self.day,
            seat_id=seat_id,
            content=content,
            msg_type=msg_type,
            i18n_key=i18n_key,
            i18n_params=i18n_params
        )
        self.messages.append(msg)
        # NEW-7: Detect role claims from player speech
        if seat_id > 0 and msg_type == MessageType.SPEECH:
            from app.services.claim_detector import detect_role_claim
            claimed = detect_role_claim(content)
            if claimed:
                self.claimed_roles[seat_id] = claimed
        self.increment_version()
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
            self.increment_version()

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
        """Determine what action the player needs to take.

        Delegates to game_state_service.get_pending_action_for_player.
        """
        from app.services.game_state_service import get_pending_action_for_player
        return get_pending_action_for_player(self, player)

    def get_state_for_player(self, player_id: Optional[str] = None) -> dict:
        """Get game state filtered for specific player's perspective.

        Delegates to game_state_service.build_state_for_player.
        """
        from app.services.game_state_service import build_state_for_player
        return build_state_for_player(self, player_id)

    # Backward compatibility alias for P0 hotfix
    def filter_sensitive_info(self, player_id: Optional[str] = None) -> dict:
        """Deprecated: Use get_state_for_player instead."""
        return self.get_state_for_player(player_id)

    # NOTE: _get_pending_action_for_player and get_state_for_player implementations
    # have been extracted to app/services/game_state_service.py (NEW-11 refactor).
    # The methods above are thin wrappers for backward compatibility.


class GameStore:
    """Game storage with LRU/TTL management and optional persistence.

    Uses a pluggable backend (default: InMemoryBackend) for game state storage,
    enabling future migration to Redis or other backends.

    P0-PERF-001 Fix: Added capacity limits and TTL-based cleanup to prevent
    unbounded memory growth from malicious or accidental game creation.

    P0-STAB-001 Fix: Added per-game locks to prevent concurrent state corruption.

    Persistence: Snapshots are saved to SQLite on key state changes for crash
    recovery. The in-memory backend remains the primary store for performance.
    """

    MAX_GAMES = 1000  # Maximum concurrent games
    GAME_TTL_SECONDS = 7200  # 2 hours TTL for inactive games

    def __init__(self, enable_persistence: bool = True, backend=None):
        from app.storage import create_backend
        self._backend = backend or create_backend()
        self._last_access: dict[str, float] = {}  # game_id -> timestamp
        self._locks: dict[str, "asyncio.Lock"] = {}  # P0-STAB-001: per-game locks (local)
        self._lock_manager = None  # Lazy-init distributed lock manager
        self._write_cache: dict[str, Game] = {}  # Write-back cache for non-reference backends
        self._persistence_enabled = enable_persistence
        self._persistence = None  # Lazy init to avoid import cycles
        # Cleanup hooks: list of async callables invoked with game_id when a game is removed.
        # Used by LLMService to clean up per-game rate limiter resources.
        self._cleanup_hooks: list = []

    @property
    def game_count(self) -> int:
        """Return the number of active games without materializing all objects."""
        return self._backend.count()

    @property
    def games(self) -> dict[str, Game]:
        """Backward-compatible access to games dict.

        For InMemoryBackend, returns the underlying dict directly.
        For other backends, returns a snapshot (read-only view).

        WARNING: For RedisBackend this triggers a full scan (O(N)).
        Prefer game_count for size checks, or get_game() for single access.
        """
        from app.storage.memory import InMemoryBackend
        if isinstance(self._backend, InMemoryBackend):
            return self._backend._games
        # Fallback: build dict from backend (for non-memory backends)
        return {gid: self._backend.get(gid) for gid in self._backend.all_ids()}

    def get_lock(self, game_id: str):
        """Get or create a lock for the specified game.

        P0-STAB-001 Fix: Ensures thread-safe access to game state.

        Returns asyncio.Lock for InMemoryBackend (single-instance),
        or RedisLock for RedisBackend (multi-instance distributed lock).
        Both support `async with` context manager.
        """
        from app.storage.redis_backend import RedisBackend
        if isinstance(self._backend, RedisBackend):
            if self._lock_manager is None:
                from app.storage.distributed_lock import RedisLockManager
                self._lock_manager = RedisLockManager(self._backend._client)
            return self._lock_manager.get_lock(game_id)
        # Local asyncio.Lock for in-memory backend
        return self._locks.setdefault(game_id, asyncio.Lock())

    def _run_cleanup_hooks(self, game_id: str) -> None:
        """Invoke registered cleanup hooks for a removed game.

        Hooks are best-effort: failures are logged but do not propagate.
        Supports both sync and async callables.
        """
        import inspect
        for hook in self._cleanup_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    # Schedule async hook on the running event loop
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(hook(game_id))
                    except RuntimeError:
                        # No running loop — skip async hook
                        logging.getLogger(__name__).warning(
                            f"Cannot run async cleanup hook for game {game_id}: no event loop"
                        )
                else:
                    hook(game_id)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    f"Cleanup hook failed for game {game_id}: {e}"
                )

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
            self._backend.delete(game_id)
            self._write_cache.pop(game_id, None)
            if game_id in self._last_access:
                del self._last_access[game_id]
            if game_id in self._locks:
                del self._locks[game_id]
            # Clean up associated logs
            clear_game_logs(game_id)
            # Clean up persistence snapshot to prevent stale recovery
            self._delete_snapshot(game_id)
            # Invoke cleanup hooks (e.g., per-game rate limiter)
            self._run_cleanup_hooks(game_id)

        return len(to_remove)

    def create_game(
        self,
        human_seat: Optional[int] = None,
        human_role: Optional[Role] = None,
        language: str = "zh",
        game_id: Optional[str] = None,
        config: Optional[GameConfig] = None,
        user_id: Optional[str] = None
    ) -> Game:
        """Create a new game with random role assignment.

        P0-PERF-001 Fix: Enforces capacity limits and cleans up old games.

        Args:
            human_seat: Seat ID for human player (1-based). If None, random.
            human_role: Specific role for human player. If None, random.
            language: Game language ("zh" or "en")
            game_id: Custom game ID. If None, auto-generated.
            config: Game configuration. If None, defaults to CLASSIC_9_CONFIG.
            user_id: Optional user ID for authenticated players.
        """
        # Use default 9-player config if not specified (backward compatibility)
        if config is None:
            config = CLASSIC_9_CONFIG

        # Check capacity and cleanup if needed
        if self._backend.count() >= self.MAX_GAMES:
            cleaned = self._cleanup_old_games()
            if self._backend.count() >= self.MAX_GAMES:
                raise ValueError(
                    f"Server at capacity ({self.MAX_GAMES} games). "
                    f"Cleaned {cleaned} old games but still full. Try again later."
                )

        if game_id is None:
            game_id = str(uuid.uuid4())
        game = Game(id=game_id, language=language)

        # Get role distribution from config
        roles = config.roles.copy()

        # Determine human seat
        if human_seat is None:
            human_seat = _rng.randint(1, config.player_count)
        game.human_seat = human_seat

        # If human role is specified, ensure they get it
        if human_role:
            if human_role in roles:
                roles.remove(human_role)
            else:
                raise ValueError(f"Role {human_role} not available in this game mode")
            _rng.shuffle(roles)
            roles.insert(human_seat - 1, human_role)
        else:
            _rng.shuffle(roles)

        # Shuffle personalities (names loaded from i18n based on game language)
        personalities = get_ai_personalities(language)
        _rng.shuffle(personalities)

        # Create players
        wolf_seats = []  # All wolf-aligned seats (including wolf king variants)
        for i, role in enumerate(roles):
            seat_id = i + 1
            is_human = (seat_id == human_seat)

            player = Player(
                seat_id=seat_id,
                role=role,
                is_human=is_human,
                personality=None if is_human else personalities[i % len(personalities)],
                user_id=user_id if is_human else None
            )

            # Track all wolf-aligned roles for teammate relationship
            if role in WOLF_ROLES:
                wolf_seats.append(seat_id)

            game.players[seat_id] = player

        # Set werewolf teammates (includes wolf king/white wolf king)
        # P2优化：为狼人分配差异化战术角色
        shuffled_personas = WOLF_PERSONAS.copy()
        _rng.shuffle(shuffled_personas)
        for idx, seat_id in enumerate(wolf_seats):
            player = game.players[seat_id]
            player.teammates = [s for s in wolf_seats if s != seat_id]
            # 为非人类狼人分配战术角色（循环使用，确保多样性）
            if not player.is_human:
                player.wolf_persona = shuffled_personas[idx % len(shuffled_personas)]

        game.status = GameStatus.PLAYING
        self._backend.put(game_id, game)
        self._last_access[game_id] = time.time()  # P0-PERF-001: Track access time
        self._save_snapshot(game)
        return game

    def get_game(self, game_id: str) -> Optional[Game]:
        """Get game by ID.

        P0-PERF-001 Fix: Updates last access time for TTL management.
        """
        game = self._backend.get(game_id)
        if game:
            self._last_access[game_id] = time.time()
            self._write_cache[game_id] = game
        return game

    def delete_game(self, game_id: str) -> bool:
        """Delete a game.

        P0-PERF-001 Fix: Also cleans up associated logs and access tracking.
        P0-STAB-001 Fix: Also cleans up per-game lock.
        """
        from app.services.log_manager import clear_game_logs

        if self._backend.delete(game_id):
            # Clean up write cache
            self._write_cache.pop(game_id, None)
            # Clean up access tracking
            if game_id in self._last_access:
                del self._last_access[game_id]
            # Clean up lock
            if game_id in self._locks:
                del self._locks[game_id]
            # Clean up associated logs
            clear_game_logs(game_id)
            # Remove snapshot
            self._delete_snapshot(game_id)
            # Invoke cleanup hooks (e.g., per-game rate limiter)
            self._run_cleanup_hooks(game_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _get_persistence(self):
        """Lazy-init persistence to avoid import cycles."""
        if self._persistence is None and self._persistence_enabled:
            try:
                from app.services.game_persistence import game_persistence
                self._persistence = game_persistence
            except Exception:
                self._persistence_enabled = False
        return self._persistence

    def _save_snapshot(self, game: Game) -> None:
        """Save game snapshot (best-effort, never raises)."""
        p = self._get_persistence()
        if p:
            p.save_snapshot(game)

    def _delete_snapshot(self, game_id: str) -> None:
        """Delete game snapshot (best-effort, never raises)."""
        p = self._get_persistence()
        if p:
            p.delete_snapshot(game_id)

    async def save_game_state(self, game_id: str) -> None:
        """Explicitly save current game state snapshot.

        Call this after important state transitions (phase changes, etc.)
        Also writes the cached game object back to the storage backend,
        which is essential for non-reference backends like Redis.

        B-4 FIX: Now async — offloads blocking SQLite persistence to thread pool.
        """
        game = self._write_cache.get(game_id) or self._backend.get(game_id)
        if game:
            self._backend.put(game_id, game)
            # Offload blocking SQLite write to thread pool
            await asyncio.to_thread(self._save_snapshot, game)

    def recover_from_snapshots(self) -> int:
        """Recover active games from persistence on startup.

        Returns:
            Number of games recovered.
        """
        p = self._get_persistence()
        if not p:
            return 0
        recovered = p.load_all_active()
        count = 0
        for game_id, game in recovered.items():
            if not self._backend.exists(game_id):
                self._backend.put(game_id, game)
                self._last_access[game_id] = time.time()
                count += 1
        if count:
            logging.getLogger(__name__).info(f"Recovered {count} games from snapshots")
        return count


def create_game_store(**kwargs) -> GameStore:
    """Factory function for creating GameStore instances.

    Supports dependency injection for testing. Accepts all GameStore __init__ kwargs
    (backend, enable_persistence, etc.).
    """
    return GameStore(**kwargs)


# Global game store instance
game_store = GameStore()
