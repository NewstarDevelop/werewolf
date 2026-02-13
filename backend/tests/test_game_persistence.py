"""Tests for game state persistence (serialization + SQLite snapshots)."""
import os
import pytest
import tempfile

from app.models.game import Game, Player, Message, Action, GameStore, game_store
from app.schemas.enums import (
    GameStatus, GamePhase, Role, ActionType, MessageType, Winner
)
from app.services.game_persistence import (
    _serialize_game,
    _deserialize_game,
    GamePersistence,
)


class TestSerialization:
    """Test Game serialize/deserialize round-trip."""

    def _make_game(self) -> Game:
        """Create a game via game_store for testing."""
        store = GameStore(enable_persistence=False)
        game = store.create_game(human_seat=1, game_id="test-ser")
        # Add some state
        game.add_message(1, "Hello world", MessageType.SPEECH)
        game.add_action(1, ActionType.VOTE, target_id=2)
        game.day_votes = {1: 2, 3: 2}
        game.wolf_chat_completed = {1, 2}
        game.player_mapping = {"player-abc": 1, "player-def": 2}
        game.human_seats = [1]
        return game

    def test_round_trip(self):
        """Serialize then deserialize produces equivalent game."""
        original = self._make_game()
        data = _serialize_game(original)
        restored = _deserialize_game(data)

        assert restored.id == original.id
        assert restored.status == original.status
        assert restored.day == original.day
        assert restored.phase == original.phase
        assert restored.language == original.language
        assert restored.state_version == original.state_version
        assert restored.human_seat == original.human_seat
        assert restored.human_seats == original.human_seats
        assert restored.player_mapping == original.player_mapping

    def test_players_round_trip(self):
        """Player data survives serialization."""
        original = self._make_game()
        data = _serialize_game(original)
        restored = _deserialize_game(data)

        assert len(restored.players) == len(original.players)
        for seat_id, orig_player in original.players.items():
            rest_player = restored.players[seat_id]
            assert rest_player.seat_id == orig_player.seat_id
            assert rest_player.role == orig_player.role
            assert rest_player.is_human == orig_player.is_human
            assert rest_player.is_alive == orig_player.is_alive
            assert rest_player.teammates == orig_player.teammates

    def test_messages_round_trip(self):
        """Messages survive serialization."""
        original = self._make_game()
        data = _serialize_game(original)
        restored = _deserialize_game(data)

        assert len(restored.messages) == len(original.messages)
        for orig_msg, rest_msg in zip(original.messages, restored.messages):
            assert rest_msg.id == orig_msg.id
            assert rest_msg.content == orig_msg.content
            assert rest_msg.msg_type == orig_msg.msg_type

    def test_actions_round_trip(self):
        """Actions survive serialization."""
        original = self._make_game()
        data = _serialize_game(original)
        restored = _deserialize_game(data)

        assert len(restored.actions) == len(original.actions)
        for orig_act, rest_act in zip(original.actions, restored.actions):
            assert rest_act.action_type == orig_act.action_type
            assert rest_act.target_id == orig_act.target_id

    def test_sets_round_trip(self):
        """Set fields (wolf_chat_completed, _spoken_seats) survive serialization."""
        original = self._make_game()
        data = _serialize_game(original)
        restored = _deserialize_game(data)

        assert restored.wolf_chat_completed == original.wolf_chat_completed
        assert restored._spoken_seats_this_round == original._spoken_seats_this_round

    def test_day_votes_round_trip(self):
        """Dict fields with int keys survive serialization."""
        original = self._make_game()
        data = _serialize_game(original)
        restored = _deserialize_game(data)

        assert restored.day_votes == original.day_votes

    def test_finished_game_with_winner(self):
        """Finished game with winner serializes correctly."""
        original = self._make_game()
        original.status = GameStatus.FINISHED
        original.winner = Winner.VILLAGER
        data = _serialize_game(original)
        restored = _deserialize_game(data)

        assert restored.status == GameStatus.FINISHED
        assert restored.winner == Winner.VILLAGER


class TestGamePersistence:
    """Test SQLite-backed persistence service."""

    @pytest.fixture
    def persistence(self, tmp_path):
        db_path = str(tmp_path / "test_snapshots.db")
        return GamePersistence(db_path=db_path)

    @pytest.fixture
    def sample_game(self):
        store = GameStore(enable_persistence=False)
        return store.create_game(human_seat=1, game_id="persist-test")

    def test_save_and_load(self, persistence, sample_game):
        """Save a snapshot and load it back."""
        persistence.save_snapshot(sample_game)
        loaded = persistence.load_all_active()

        assert "persist-test" in loaded
        game = loaded["persist-test"]
        assert game.id == sample_game.id
        assert game.status == sample_game.status
        assert len(game.players) == len(sample_game.players)

    def test_delete_snapshot(self, persistence, sample_game):
        """Deleted snapshot is not loaded."""
        persistence.save_snapshot(sample_game)
        persistence.delete_snapshot(sample_game.id)

        loaded = persistence.load_all_active()
        assert sample_game.id not in loaded

    def test_finished_games_excluded(self, persistence, sample_game):
        """Finished games are not loaded as active."""
        sample_game.status = GameStatus.FINISHED
        persistence.save_snapshot(sample_game)

        loaded = persistence.load_all_active()
        assert sample_game.id not in loaded

    def test_cleanup_finished(self, persistence, sample_game):
        """cleanup_finished removes finished game snapshots."""
        sample_game.status = GameStatus.FINISHED
        persistence.save_snapshot(sample_game)

        count = persistence.cleanup_finished()
        assert count == 1

    def test_overwrite_snapshot(self, persistence, sample_game):
        """Saving twice overwrites the previous snapshot."""
        persistence.save_snapshot(sample_game)
        sample_game.day = 5
        persistence.save_snapshot(sample_game)

        loaded = persistence.load_all_active()
        assert loaded[sample_game.id].day == 5


class TestGameStoreIntegration:
    """Test GameStore with persistence enabled."""

    @pytest.fixture
    def store(self, tmp_path):
        db_path = str(tmp_path / "integration_snapshots.db")
        persistence = GamePersistence(db_path=db_path)
        s = GameStore(enable_persistence=True)
        s._persistence = persistence
        return s

    def test_create_saves_snapshot(self, store):
        """Creating a game saves a snapshot."""
        game = store.create_game(human_seat=1, game_id="int-create")
        loaded = store._persistence.load_all_active()
        assert "int-create" in loaded

    def test_delete_removes_snapshot(self, store):
        """Deleting a game removes its snapshot."""
        store.create_game(human_seat=1, game_id="int-delete")
        store.delete_game("int-delete")
        loaded = store._persistence.load_all_active()
        assert "int-delete" not in loaded

    def test_save_game_state_explicit(self, store):
        """Explicit save_game_state persists current state."""
        game = store.create_game(human_seat=1, game_id="int-explicit")
        game.day = 3
        game.phase = GamePhase.DAY_VOTE
        store.save_game_state("int-explicit")

        loaded = store._persistence.load_all_active()
        assert loaded["int-explicit"].day == 3
        assert loaded["int-explicit"].phase == GamePhase.DAY_VOTE

    def test_recover_from_snapshots(self, store):
        """recover_from_snapshots restores games into memory."""
        game = store.create_game(human_seat=1, game_id="int-recover")
        # Clear in-memory but keep snapshot
        store.games.clear()
        store._last_access.clear()

        count = store.recover_from_snapshots()
        assert count == 1
        assert "int-recover" in store.games
        assert store.games["int-recover"].id == game.id
