"""Tests for game_state_service.

Validates pending action computation and state serialization (NEW-11).
"""
import os

os.environ["DEBUG"] = "true"
os.environ["LLM_USE_MOCK"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"

import pytest
from app.models.game import Game, Player
from app.schemas.enums import (
    GameStatus, GamePhase, Role, ActionType, MessageType,
)
from app.services.game_state_service import (
    get_pending_action_for_player,
    build_state_for_player,
)


# ============================================================================
# Helpers
# ============================================================================

def _make_game(player_count: int = 9) -> Game:
    """Create a game with standard 9-player role distribution."""
    game = Game(id="test-state-svc", language="zh")
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
    return game


# ============================================================================
# get_pending_action_for_player Tests
# ============================================================================

class TestGetPendingAction:
    """Tests for get_pending_action_for_player()."""

    # --- Werewolf kill phase ---
    def test_wolf_gets_kill_action(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        wolf = game.players[1]  # Role.WEREWOLF
        action = get_pending_action_for_player(game, wolf)
        assert action is not None
        assert action["type"] == ActionType.KILL.value

    def test_wolf_no_action_after_voting(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        game.wolf_votes[1] = 4  # Wolf 1 already voted
        wolf = game.players[1]
        action = get_pending_action_for_player(game, wolf)
        assert action is None

    def test_non_wolf_no_action_in_wolf_phase(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        seer = game.players[7]  # Role.SEER
        action = get_pending_action_for_player(game, seer)
        assert action is None

    # --- Seer verify phase ---
    def test_seer_gets_verify_action(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_SEER
        seer = game.players[7]
        action = get_pending_action_for_player(game, seer)
        assert action is not None
        assert action["type"] == ActionType.VERIFY.value
        # Should not include self in choices
        assert 7 not in action["choices"]

    def test_seer_no_action_after_verify(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_SEER
        game.seer_verified_this_night = True
        seer = game.players[7]
        action = get_pending_action_for_player(game, seer)
        assert action is None

    def test_seer_excludes_already_verified(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_SEER
        seer = game.players[7]
        seer.verified_players = {4: True, 5: False}
        action = get_pending_action_for_player(game, seer)
        assert action is not None
        assert 4 not in action["choices"]
        assert 5 not in action["choices"]

    # --- Witch save phase ---
    def test_witch_gets_save_action(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WITCH
        game.night_kill_target = 4
        witch = game.players[8]
        action = get_pending_action_for_player(game, witch)
        assert action is not None
        assert action["type"] == ActionType.SAVE.value
        assert 4 in action["choices"]
        assert 0 in action["choices"]  # skip option

    def test_witch_no_save_without_potion(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WITCH
        game.night_kill_target = 4
        witch = game.players[8]
        witch.has_save_potion = False
        action = get_pending_action_for_player(game, witch)
        assert action is not None
        assert action["type"] == ActionType.SAVE.value
        assert action["choices"] == [0]  # Only skip

    # --- Witch poison phase ---
    def test_witch_gets_poison_action(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WITCH
        game.witch_save_decided = True
        witch = game.players[8]
        action = get_pending_action_for_player(game, witch)
        assert action is not None
        assert action["type"] == ActionType.POISON.value
        assert 0 in action["choices"]  # skip option

    def test_witch_no_poison_without_potion(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WITCH
        game.witch_save_decided = True
        witch = game.players[8]
        witch.has_poison_potion = False
        action = get_pending_action_for_player(game, witch)
        assert action is not None
        assert action["type"] == ActionType.POISON.value
        assert action["choices"] == [0]

    # --- Guard protect phase ---
    def test_guard_gets_protect_action(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_GUARD
        # Add a guard player
        game.players[10] = Player(seat_id=10, role=Role.GUARD, is_human=False)
        guard = game.players[10]
        action = get_pending_action_for_player(game, guard)
        assert action is not None
        assert action["type"] == ActionType.PROTECT.value
        assert 0 in action["choices"]

    def test_guard_excludes_last_target(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_GUARD
        game.players[10] = Player(seat_id=10, role=Role.GUARD, is_human=False)
        game.guard_last_target = 3
        guard = game.players[10]
        action = get_pending_action_for_player(game, guard)
        assert action is not None
        assert 3 not in action["choices"]

    # --- Day vote phase ---
    def test_player_gets_vote_action(self):
        game = _make_game()
        game.phase = GamePhase.DAY_VOTE
        villager = game.players[4]
        action = get_pending_action_for_player(game, villager)
        assert action is not None
        assert action["type"] == ActionType.VOTE.value
        assert 4 not in action["choices"]  # Can't vote self
        assert 0 in action["choices"]  # Abstain

    def test_player_no_vote_after_voting(self):
        game = _make_game()
        game.phase = GamePhase.DAY_VOTE
        game.day_votes[4] = 1
        villager = game.players[4]
        action = get_pending_action_for_player(game, villager)
        assert action is None

    # --- Dead player ---
    def test_dead_player_no_action(self):
        game = _make_game()
        game.phase = GamePhase.DAY_VOTE
        villager = game.players[4]
        villager.is_alive = False
        action = get_pending_action_for_player(game, villager)
        assert action is None

    # --- Day speech phase ---
    def test_current_speaker_gets_speak_action(self):
        game = _make_game()
        game.phase = GamePhase.DAY_SPEECH
        game.speech_order = [4, 5, 6]
        game.current_speech_index = 0
        speaker = game.players[4]
        action = get_pending_action_for_player(game, speaker)
        assert action is not None
        assert action["type"] == ActionType.SPEAK.value

    def test_non_speaker_no_action_in_speech(self):
        game = _make_game()
        game.phase = GamePhase.DAY_SPEECH
        game.speech_order = [4, 5, 6]
        game.current_speech_index = 0
        non_speaker = game.players[5]
        action = get_pending_action_for_player(game, non_speaker)
        assert action is None


# ============================================================================
# build_state_for_player Tests
# ============================================================================

class TestBuildStateForPlayer:
    """Tests for build_state_for_player()."""

    def test_base_state_fields(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        state = build_state_for_player(game, player_id=None)
        assert state["game_id"] == "test-state-svc"
        assert state["status"] == GameStatus.PLAYING.value
        assert state["phase"] == GamePhase.NIGHT_WEREWOLF.value
        assert "players" in state
        assert "message_log" in state

    def test_observer_view_hides_roles(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        state = build_state_for_player(game, player_id=None)
        for p in state["players"]:
            assert p["role"] is None

    def test_player_sees_own_role(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        game.player_mapping["user1"] = 1
        state = build_state_for_player(game, player_id="user1")
        assert state["my_seat"] == 1
        assert state["my_role"] == Role.WEREWOLF.value
        own = [p for p in state["players"] if p["seat_id"] == 1][0]
        assert own["role"] == Role.WEREWOLF.value

    def test_player_cannot_see_others_roles(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        game.player_mapping["user1"] = 1
        state = build_state_for_player(game, player_id="user1")
        others = [p for p in state["players"] if p["seat_id"] != 1]
        for p in others:
            assert p["role"] is None

    def test_finished_game_shows_all_roles(self):
        game = _make_game()
        game.status = GameStatus.FINISHED
        game.phase = GamePhase.GAME_OVER
        state = build_state_for_player(game, player_id=None)
        for p in state["players"]:
            assert p["role"] is not None

    def test_wolf_sees_teammates(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        game.player_mapping["wolf1"] = 1
        game.players[1].teammates = [2, 3]
        state = build_state_for_player(game, player_id="wolf1")
        assert state["wolf_teammates"] == [2, 3]

    def test_non_wolf_no_teammates(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_SEER
        game.player_mapping["seer1"] = 7
        state = build_state_for_player(game, player_id="seer1")
        assert state["wolf_teammates"] == []

    def test_seer_sees_verified_results(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_SEER
        game.player_mapping["seer1"] = 7
        game.players[7].verified_players = {1: False, 4: True}
        state = build_state_for_player(game, player_id="seer1")
        assert state["verified_results"] == {1: False, 4: True}

    def test_witch_sees_potions(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WITCH
        game.player_mapping["witch1"] = 8
        state = build_state_for_player(game, player_id="witch1")
        assert state["has_save_potion"] is True
        assert state["has_poison_potion"] is True

    def test_vote_thought_messages_hidden(self):
        game = _make_game()
        game.phase = GamePhase.DAY_VOTE
        game.add_message(1, "I think 4 is wolf", MessageType.VOTE_THOUGHT)
        game.add_message(1, "Hello everyone", MessageType.SPEECH)
        game.player_mapping["user1"] = 1
        state = build_state_for_player(game, player_id="user1")
        types = [m["type"] for m in state["message_log"]]
        assert MessageType.VOTE_THOUGHT.value not in types
        assert MessageType.SPEECH.value in types

    def test_wolf_chat_visible_to_wolves(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF_CHAT
        game.add_message(1, "Let's kill 7", MessageType.WOLF_CHAT)
        game.player_mapping["wolf1"] = 1
        state = build_state_for_player(game, player_id="wolf1")
        types = [m["type"] for m in state["message_log"]]
        assert MessageType.WOLF_CHAT.value in types

    def test_wolf_chat_hidden_from_non_wolves(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF_CHAT
        game.add_message(1, "Let's kill 7", MessageType.WOLF_CHAT)
        game.player_mapping["seer1"] = 7
        state = build_state_for_player(game, player_id="seer1")
        types = [m["type"] for m in state["message_log"]]
        assert MessageType.WOLF_CHAT.value not in types

    def test_default_fields_always_present(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_WEREWOLF
        state = build_state_for_player(game, player_id=None)
        assert "wolf_teammates" in state
        assert "verified_results" in state
        assert state["wolf_teammates"] == []
        assert state["verified_results"] == {}

    def test_guard_sees_last_target(self):
        game = _make_game()
        game.phase = GamePhase.NIGHT_GUARD
        game.players[10] = Player(seat_id=10, role=Role.GUARD, is_human=False)
        game.player_mapping["guard1"] = 10
        game.guard_last_target = 3
        state = build_state_for_player(game, player_id="guard1")
        assert state["guard_last_target"] == 3

    def test_pending_action_included(self):
        game = _make_game()
        game.phase = GamePhase.DAY_VOTE
        game.player_mapping["user4"] = 4
        state = build_state_for_player(game, player_id="user4")
        assert state["pending_action"] is not None
        assert state["pending_action"]["type"] == ActionType.VOTE.value
