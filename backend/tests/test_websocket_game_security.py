"""Tests for WebSocket game security - A2: Token leakage prevention and Origin validation.

Verifies that:
1. Production mode rejects query string tokens
2. Subprotocol authentication works
3. Origin validation is enforced
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


class TestWebSocketGameSecurity:
    """Test WebSocket game endpoint security."""

    @pytest.fixture
    def mock_game_store(self):
        """Mock game store with a test game."""
        with patch("app.api.endpoints.websocket.game_store") as mock:
            mock_game = MagicMock()
            mock_game.get_player_by_id.return_value = MagicMock(id="player1")
            mock_game.get_state_for_player.return_value = {"phase": "day"}
            mock.get_game.return_value = mock_game
            yield mock

    @pytest.fixture
    def mock_websocket_manager(self):
        """Mock websocket manager."""
        with patch("app.api.endpoints.websocket.websocket_manager") as mock:
            mock.connect = AsyncMock()
            mock.disconnect = MagicMock()
            yield mock

    def test_production_rejects_query_token(self, client, monkeypatch):
        """In production (DEBUG=False), query string token should be rejected."""
        # Set production mode
        monkeypatch.setenv("DEBUG", "false")

        # Reload settings and module to pick up change
        import importlib
        from app.core import config
        importlib.reload(config)

        from app.api.endpoints import websocket
        importlib.reload(websocket)

        # Verify ALLOW_QUERY_TOKEN is False
        assert websocket.ALLOW_QUERY_TOKEN == False

    def test_debug_allows_query_token(self, monkeypatch):
        """In debug mode (DEBUG=True), query string token should be allowed."""
        # Set debug mode
        monkeypatch.setenv("DEBUG", "true")

        # Reload settings and module
        import importlib
        from app.core import config
        importlib.reload(config)

        from app.api.endpoints import websocket
        importlib.reload(websocket)

        # Verify ALLOW_QUERY_TOKEN is True
        assert websocket.ALLOW_QUERY_TOKEN == True

    def test_subprotocol_auth_accepted(self):
        """Subprotocol authentication should be the preferred method."""
        from app.services.websocket_auth import extract_token

        # Create mock websocket with subprotocol
        mock_ws = MagicMock()
        mock_ws.scope = {"subprotocols": ["auth", "test_token_value"]}
        mock_ws.cookies = {}
        mock_ws.query_params = {}

        # Extract token should get from subprotocol
        import asyncio
        token, source = asyncio.run(
            extract_token(mock_ws, allow_query_token=False)
        )

        assert token == "test_token_value"
        assert source == "protocol"

    def test_cookie_auth_fallback(self):
        """Cookie authentication should work as fallback."""
        from app.services.websocket_auth import extract_token

        # Create mock websocket with cookie only
        mock_ws = MagicMock()
        mock_ws.scope = {"subprotocols": []}
        mock_ws.cookies = {"user_access_token": "cookie_token_value"}
        mock_ws.query_params = {}

        import asyncio
        token, source = asyncio.run(
            extract_token(mock_ws, allow_query_token=False)
        )

        assert token == "cookie_token_value"
        assert source == "cookie"

    def test_query_token_rejected_when_disabled(self):
        """Query token should be ignored when allow_query_token=False."""
        from app.services.websocket_auth import extract_token

        # Create mock websocket with only query token
        mock_ws = MagicMock()
        mock_ws.scope = {"subprotocols": []}
        mock_ws.cookies = {}
        mock_ws.query_params = {"token": "query_token_value"}

        import asyncio
        token, source = asyncio.run(
            extract_token(mock_ws, allow_query_token=False)
        )

        # Token should not be extracted
        assert token is None
        assert source == "none"

    def test_origin_validation_rejects_invalid(self, monkeypatch):
        """Invalid origins should be rejected in production."""
        from app.services.websocket_auth import validate_origin

        # Set production mode with specific allowed origins
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("ALLOWED_WS_ORIGINS", "https://example.com")

        import importlib
        from app.core import config
        importlib.reload(config)

        # Create mock websocket with invalid origin
        mock_ws = MagicMock()
        mock_ws.headers = {"origin": "https://malicious.com", "host": "api.example.com"}

        is_valid, origin = validate_origin(mock_ws, allowed_origins=["https://example.com"])

        assert is_valid == False
        assert origin == "https://malicious.com"

    def test_origin_validation_accepts_valid(self):
        """Valid origins should be accepted."""
        from app.services.websocket_auth import validate_origin

        # Create mock websocket with valid origin
        mock_ws = MagicMock()
        mock_ws.headers = {"origin": "https://example.com", "host": "api.example.com"}

        is_valid, origin = validate_origin(mock_ws, allowed_origins=["https://example.com"])

        assert is_valid == True
        assert origin == "https://example.com"

    def test_same_origin_always_allowed(self):
        """Same-origin requests should always be allowed."""
        from app.services.websocket_auth import validate_origin

        # Create mock websocket with same origin as host
        mock_ws = MagicMock()
        mock_ws.headers = {"origin": "https://api.example.com", "host": "api.example.com"}

        is_valid, origin = validate_origin(mock_ws, allowed_origins=[])

        assert is_valid == True
