"""Tests for cross-instance game broadcaster."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.storage.game_broadcaster import GameUpdateBroadcaster, CHANNEL_PREFIX


@pytest.fixture
def mock_ws_manager():
    """Create a mock ConnectionManager."""
    manager = MagicMock()
    manager.get_connection_count = MagicMock(return_value=0)
    manager.broadcast_to_game_players = AsyncMock()
    manager.broadcast_to_game = AsyncMock()
    return manager


@pytest.fixture
def broadcaster(mock_ws_manager):
    """Create a broadcaster without Redis (local-only mode)."""
    b = GameUpdateBroadcaster(mock_ws_manager)
    return b


class TestBroadcasterLocalMode:
    """Test broadcaster in local-only mode (no Redis)."""

    @pytest.mark.asyncio
    async def test_start_without_redis_url(self, broadcaster):
        """Should start in local-only mode when REDIS_URL is not set."""
        with patch.dict("os.environ", {"REDIS_URL": ""}):
            await broadcaster.start()
        assert broadcaster._redis_client is None

    @pytest.mark.asyncio
    async def test_publish_without_redis_is_noop(self, broadcaster):
        """publish_game_update should be a no-op without Redis."""
        broadcaster._redis_client = None
        # Should not raise
        await broadcaster.publish_game_update("game-1")

    @pytest.mark.asyncio
    async def test_stop_without_redis(self, broadcaster):
        """stop should work gracefully without Redis."""
        await broadcaster.stop()


class TestBroadcasterPublish:
    """Test publish behavior with mocked Redis."""

    @pytest.mark.asyncio
    async def test_publish_sends_to_redis_channel(self, broadcaster):
        mock_redis = AsyncMock()
        broadcaster._redis_client = mock_redis

        await broadcaster.publish_game_update("game-123")

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert channel == f"{CHANNEL_PREFIX}game-123"
        assert payload["game_id"] == "game-123"
        assert payload["source"] == broadcaster._instance_id

    @pytest.mark.asyncio
    async def test_publish_error_is_handled(self, broadcaster):
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = ConnectionError("Redis down")
        broadcaster._redis_client = mock_redis

        # Should not raise
        await broadcaster.publish_game_update("game-1")


class TestBroadcasterMessageHandling:
    """Test _handle_message for incoming cross-instance updates."""

    @pytest.mark.asyncio
    async def test_ignores_own_messages(self, broadcaster, mock_ws_manager):
        """Messages from the same instance should be ignored."""
        msg = {
            "data": json.dumps({
                "game_id": "game-1",
                "source": broadcaster._instance_id,
            })
        }
        await broadcaster._handle_message(msg)
        mock_ws_manager.broadcast_to_game_players.assert_not_called()
        mock_ws_manager.broadcast_to_game.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_games_without_local_connections(self, broadcaster, mock_ws_manager):
        """Should skip games with no local WebSocket connections."""
        mock_ws_manager.get_connection_count.return_value = 0
        msg = {
            "data": json.dumps({
                "game_id": "game-1",
                "source": "other-instance",
            })
        }
        await broadcaster._handle_message(msg)
        mock_ws_manager.broadcast_to_game_players.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcasts_to_local_multiplayer_connections(self, broadcaster, mock_ws_manager):
        """Should broadcast to local connections for multiplayer games."""
        mock_ws_manager.get_connection_count.return_value = 3

        # Create a real game in game_store
        from app.models.game import game_store
        game = game_store.create_game(language="zh")
        game.player_mapping = {"player-1": 1, "player-2": 2}

        msg = {
            "data": json.dumps({
                "game_id": game.id,
                "source": "other-instance",
            })
        }
        await broadcaster._handle_message(msg)

        mock_ws_manager.broadcast_to_game_players.assert_called_once()
        call_args = mock_ws_manager.broadcast_to_game_players.call_args
        assert call_args[0][0] == game.id
        assert call_args[0][1] == "game_update"

        # Cleanup
        game_store.delete_game(game.id)

    @pytest.mark.asyncio
    async def test_broadcasts_to_local_singleplayer_connections(self, broadcaster, mock_ws_manager):
        """Should broadcast to local connections for single-player games."""
        mock_ws_manager.get_connection_count.return_value = 1

        from app.models.game import game_store
        game = game_store.create_game(language="zh")
        # Single-player: no player_mapping

        msg = {
            "data": json.dumps({
                "game_id": game.id,
                "source": "other-instance",
            })
        }
        await broadcaster._handle_message(msg)

        mock_ws_manager.broadcast_to_game.assert_called_once()
        call_args = mock_ws_manager.broadcast_to_game.call_args
        assert call_args[0][0] == game.id
        assert call_args[0][1] == "game_update"

        # Cleanup
        game_store.delete_game(game.id)

    @pytest.mark.asyncio
    async def test_handles_malformed_message(self, broadcaster, mock_ws_manager):
        """Should not crash on malformed messages."""
        msg = {"data": "not valid json {{{"}
        # Should not raise
        await broadcaster._handle_message(msg)

    @pytest.mark.asyncio
    async def test_handles_missing_game_id(self, broadcaster, mock_ws_manager):
        """Should ignore messages without game_id."""
        msg = {"data": json.dumps({"source": "other"})}
        await broadcaster._handle_message(msg)
        mock_ws_manager.broadcast_to_game_players.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_nonexistent_game(self, broadcaster, mock_ws_manager):
        """Should handle gracefully when game doesn't exist in store."""
        mock_ws_manager.get_connection_count.return_value = 1
        msg = {
            "data": json.dumps({
                "game_id": "nonexistent-game",
                "source": "other-instance",
            })
        }
        await broadcaster._handle_message(msg)
        mock_ws_manager.broadcast_to_game_players.assert_not_called()
        mock_ws_manager.broadcast_to_game.assert_not_called()
