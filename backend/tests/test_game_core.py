"""Unit tests for game core logic: models, GameStore, validate_target, action handlers."""
import os
import asyncio
import time

# Set test environment before importing app modules
os.environ["DEBUG"] = "true"
os.environ["LLM_USE_MOCK"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"

import pytest
from app.models.game import (
    Game, Player, GameStore, GameConfig,
    WOLF_ROLES, VILLAGER_ROLES, GOD_ROLES,
    CLASSIC_9_CONFIG,
)
from app.schemas.enums import (
    GameStatus, GamePhase, Role, ActionType, MessageType, Winner,
)
from app.services.action_handlers.base import validate_target, ActionResult


# ============================================================================
# Helpers
# ============================================================================

def _make_game(player_count: int = 9) -> Game:
    """Create a simple game with players for testing."""
    game = Game(id="test-game", language="zh")
    roles = [
        Role.WEREWOLF, Role.WEREWOLF, Role.WEREWOLF,
        Role.VILLAGER, Role.VILLAGER, Role.VILLAGER,
        Role.SEER, Role.WITCH, Role.HUNTER,
    ]
    for i in range(player_count):
        seat = i + 1
        game.players[seat] = Player(
            seat_id=seat,
            role=roles[i],
            is_human=(seat == 1),
        )
    game.status = GameStatus.PLAYING
    game.phase = GamePhase.NIGHT_WEREWOLF
    return game


# ============================================================================
# Game Model Tests
# ============================================================================

class TestGameModel:
    """Tests for Game dataclass methods."""

    def test_get_player(self):
        game = _make_game()
        assert game.get_player(1) is not None
        assert game.get_player(1).seat_id == 1
        assert game.get_player(99) is None

    def test_get_alive_players(self):
        game = _make_game()
        assert len(game.get_alive_players()) == 9

        game.kill_player(3)
        assert len(game.get_alive_players()) == 8
        assert 3 not in game.get_alive_seats()

    def test_get_alive_seats_sorted(self):
        game = _make_game()
        game.kill_player(2)
        game.kill_player(5)
        seats = game.get_alive_seats()
        assert seats == [1, 3, 4, 6, 7, 8, 9]

    def test_get_werewolves(self):
        game = _make_game()
        wolves = game.get_werewolves()
        assert len(wolves) == 3
        for w in wolves:
            assert w.role in WOLF_ROLES

    def test_get_alive_werewolves(self):
        game = _make_game()
        game.kill_player(1)  # wolf seat 1
        alive_wolves = game.get_alive_werewolves()
        assert len(alive_wolves) == 2

    def test_get_player_by_role(self):
        game = _make_game()
        seer = game.get_player_by_role(Role.SEER)
        assert seer is not None
        assert seer.role == Role.SEER

    def test_get_player_by_id(self):
        game = _make_game()
        game.player_mapping["player-abc"] = 3
        player = game.get_player_by_id("player-abc")
        assert player is not None
        assert player.seat_id == 3
        assert game.get_player_by_id("nonexistent") is None

    def test_add_message(self):
        game = _make_game()
        msg = game.add_message(1, "Hello", MessageType.SPEECH)
        assert msg.seat_id == 1
        assert msg.content == "Hello"
        assert len(game.messages) == 1
        assert game.state_version > 0

    def test_add_action(self):
        game = _make_game()
        action = game.add_action(1, ActionType.KILL, 5)
        assert action.player_id == 1
        assert action.target_id == 5
        assert len(game.actions) == 1

    def test_kill_player_basic(self):
        game = _make_game()
        game.kill_player(5)
        assert not game.get_player(5).is_alive

    def test_kill_player_by_poison_disables_hunter_shoot(self):
        game = _make_game()
        hunter = game.get_player_by_role(Role.HUNTER)
        assert hunter.can_shoot is True
        game.kill_player(hunter.seat_id, by_poison=True)
        assert hunter.can_shoot is False

    def test_kill_player_not_by_poison_keeps_hunter_shoot(self):
        game = _make_game()
        hunter = game.get_player_by_role(Role.HUNTER)
        game.kill_player(hunter.seat_id, by_poison=False)
        assert hunter.can_shoot is True

    def test_increment_version(self):
        game = _make_game()
        v1 = game.state_version
        game.increment_version()
        assert game.state_version == v1 + 1

    def test_is_player_turn(self):
        game = _make_game()
        game.player_mapping["p1"] = 3
        game.current_actor_seat = 3
        assert game.is_player_turn("p1") is True
        assert game.is_player_turn("unknown") is False
        game.current_actor_seat = 5
        assert game.is_player_turn("p1") is False


# ============================================================================
# Win Condition Tests
# ============================================================================

class TestCheckWinner:
    """Tests for Game.check_winner() win conditions."""

    def test_no_winner_at_start(self):
        game = _make_game()
        assert game.check_winner() is None

    def test_villager_win_all_wolves_dead(self):
        game = _make_game()
        # Kill all wolves (seats 1, 2, 3)
        for seat in [1, 2, 3]:
            game.kill_player(seat)
        assert game.check_winner() == Winner.VILLAGER

    def test_werewolf_win_all_villagers_dead(self):
        game = _make_game()
        # Kill all villagers (seats 4, 5, 6)
        for seat in [4, 5, 6]:
            game.kill_player(seat)
        assert game.check_winner() == Winner.WEREWOLF

    def test_werewolf_win_all_gods_dead(self):
        game = _make_game()
        # Kill all gods (seer=7, witch=8, hunter=9)
        for seat in [7, 8, 9]:
            game.kill_player(seat)
        assert game.check_winner() == Winner.WEREWOLF

    def test_werewolf_win_wolves_outnumber(self):
        game = _make_game()
        # 3 wolves alive, kill enough good people so wolves >= good
        # Kill 4 good people: 4,5,6,7 => 2 good left (8,9), 3 wolves => 3>=2
        for seat in [4, 5, 6, 7]:
            game.kill_player(seat)
        assert game.check_winner() == Winner.WEREWOLF

    def test_game_continues_balanced(self):
        game = _make_game()
        # Kill 1 wolf and 1 villager - game should continue
        game.kill_player(1)  # wolf
        game.kill_player(4)  # villager
        assert game.check_winner() is None


# ============================================================================
# validate_target Tests
# ============================================================================

class TestValidateTarget:
    """Tests for action_handlers.base.validate_target."""

    def test_valid_target(self):
        game = _make_game()
        # Should not raise
        validate_target(game, 5, ActionType.KILL, 1)

    def test_invalid_target_nonexistent_seat(self):
        game = _make_game()
        with pytest.raises(ValueError, match="不存在"):
            validate_target(game, 99, ActionType.KILL, 1)

    def test_invalid_target_dead_player(self):
        game = _make_game()
        game.kill_player(5)
        with pytest.raises(ValueError, match="已死亡"):
            validate_target(game, 5, ActionType.KILL, 1)

    def test_abstain_allowed(self):
        game = _make_game()
        # target_id=0 with allow_abstain=True should pass
        validate_target(game, 0, ActionType.VOTE, 1, allow_abstain=True)

    def test_abstain_not_allowed(self):
        game = _make_game()
        with pytest.raises(ValueError, match="不能选择 0"):
            validate_target(game, 0, ActionType.VOTE, 1, allow_abstain=False)

    def test_self_target_kill_allowed(self):
        """Wolves can self-kill (自刀策略)."""
        game = _make_game()
        # KILL is intentionally NOT in no_self_target list
        validate_target(game, 1, ActionType.KILL, 1)

    def test_self_target_vote_blocked(self):
        game = _make_game()
        with pytest.raises(ValueError, match="不能.*自己"):
            validate_target(game, 1, ActionType.VOTE, 1)

    def test_self_target_poison_blocked(self):
        game = _make_game()
        with pytest.raises(ValueError, match="不能.*自己"):
            validate_target(game, 1, ActionType.POISON, 1)

    def test_self_target_shoot_blocked(self):
        game = _make_game()
        with pytest.raises(ValueError, match="不能.*自己"):
            validate_target(game, 1, ActionType.SHOOT, 1)

    def test_self_target_verify_blocked(self):
        game = _make_game()
        with pytest.raises(ValueError, match="不能.*自己"):
            validate_target(game, 1, ActionType.VERIFY, 1)


# ============================================================================
# GameStore Tests
# ============================================================================

class TestGameStore:
    """Tests for GameStore CRUD and lifecycle."""

    def test_create_game(self):
        store = GameStore()
        game = store.create_game(language="en")
        assert game.status == GameStatus.PLAYING
        assert len(game.players) == 9  # default CLASSIC_9_CONFIG
        assert game.language == "en"

    def test_create_game_custom_id(self):
        store = GameStore()
        game = store.create_game(game_id="my-game-id")
        assert game.id == "my-game-id"
        assert store.get_game("my-game-id") is game

    def test_create_game_with_human_role(self):
        store = GameStore()
        game = store.create_game(human_seat=1, human_role=Role.SEER)
        assert game.players[1].role == Role.SEER
        assert game.players[1].is_human is True

    def test_create_game_invalid_role(self):
        store = GameStore()
        with pytest.raises(ValueError, match="not available"):
            store.create_game(human_role=Role.GUARD)  # GUARD not in classic_9

    def test_get_game_exists(self):
        store = GameStore()
        game = store.create_game(game_id="g1")
        assert store.get_game("g1") is game

    def test_get_game_not_exists(self):
        store = GameStore()
        assert store.get_game("nonexistent") is None

    def test_delete_game(self):
        store = GameStore()
        store.create_game(game_id="g1")
        assert store.delete_game("g1") is True
        assert store.get_game("g1") is None

    def test_delete_game_not_exists(self):
        store = GameStore()
        assert store.delete_game("nonexistent") is False

    def test_capacity_limit(self):
        store = GameStore()
        store.MAX_GAMES = 3
        store.GAME_TTL_SECONDS = 0  # All games expire immediately

        # Create 3 games
        for i in range(3):
            store.create_game(game_id=f"g{i}")

        # Manually set old access times so cleanup works
        for gid in list(store._last_access):
            store._last_access[gid] = 0

        # 4th game should succeed after cleanup
        game = store.create_game(game_id="g3")
        assert game is not None

    def test_get_lock(self):
        store = GameStore()
        lock1 = store.get_lock("g1")
        lock2 = store.get_lock("g1")
        assert lock1 is lock2  # Same lock for same game_id

        lock3 = store.get_lock("g2")
        assert lock1 is not lock3  # Different lock for different game_id

    def test_delete_cleans_up_lock(self):
        store = GameStore()
        store.create_game(game_id="g1")
        store.get_lock("g1")
        assert "g1" in store._locks
        store.delete_game("g1")
        assert "g1" not in store._locks

    def test_wolf_teammates_assigned(self):
        store = GameStore()
        game = store.create_game()
        wolves = game.get_werewolves()
        for wolf in wolves:
            # Each wolf should have teammates (other wolves)
            assert len(wolf.teammates) == len(wolves) - 1
            assert wolf.seat_id not in wolf.teammates


# ============================================================================
# ActionResult Tests
# ============================================================================

class TestActionResult:
    """Tests for ActionResult helper class."""

    def test_ok(self):
        r = ActionResult.ok("success", extra_key="val")
        assert r.success is True
        assert r.message == "success"
        d = r.to_dict()
        assert d["success"] is True
        assert d["extra_key"] == "val"

    def test_fail(self):
        r = ActionResult.fail("error msg")
        assert r.success is False
        d = r.to_dict()
        assert d["success"] is False
        assert d["message"] == "error msg"
