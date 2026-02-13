"""Integration tests for game creation and actions."""
import pytest
from app.models.game import game_store


def _register_and_get_token(client, email, nickname):
    """Helper: register a user and return the access token."""
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": "StrongPass123!",
        "nickname": nickname,
    })
    assert resp.status_code == 200, f"Registration failed: {resp.text}"
    return resp.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_room_and_get_ids(client, token, name="GameRoom"):
    """Helper: create a room and return (room_id, player_token, player_id)."""
    resp = client.post(
        "/api/rooms",
        json={"name": name},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    return data["room"]["id"], data["token"], data["player_id"]


class TestGameCreation:
    """Test game start flow."""

    def test_start_game_with_ai_fill(self, client):
        """Creator can start a game with AI fill."""
        token = _register_and_get_token(client, "game_start@test.com", "GameStarter")
        room_id, player_token, player_id = _create_room_and_get_ids(client, token)

        resp = client.post(
            f"/api/rooms/{room_id}/start",
            json={"fill_ai": True},
            headers=_auth_header(player_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert data["game_id"] == room_id

        # Clean up game from in-memory store
        game_store.delete_game(room_id)

    def test_start_game_requires_room_token(self, client):
        """Starting a game requires a valid player token for that room."""
        token = _register_and_get_token(client, "game_nc@test.com", "NotCreator")
        room_id, _, _ = _create_room_and_get_ids(client, token, name="NCRoom")

        # Try to start with user token (not a player token)
        resp = client.post(
            f"/api/rooms/{room_id}/start",
            json={"fill_ai": True},
            headers=_auth_header(token),  # user token, not player token
        )
        assert resp.status_code in [401, 403]


class TestGameState:
    """Test game state retrieval."""

    def test_get_game_state(self, client):
        """Get game state after starting."""
        token = _register_and_get_token(client, "game_state@test.com", "StateUser")
        room_id, player_token, _ = _create_room_and_get_ids(client, token, name="StateRoom")

        # Start game with AI
        client.post(
            f"/api/rooms/{room_id}/start",
            json={"fill_ai": True},
            headers=_auth_header(player_token),
        )

        # Get state
        resp = client.get(
            f"/api/game/{room_id}/state",
            headers=_auth_header(player_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "players" in data
        assert "phase" in data
        assert "status" in data
        assert data["status"] == "playing"

        game_store.delete_game(room_id)

    def test_get_state_nonexistent_game(self, client):
        """Getting state for non-existent game returns 404."""
        token = _register_and_get_token(client, "game_404@test.com", "NoGame")
        _, player_token, _ = _create_room_and_get_ids(client, token, name="NoGameRoom")

        resp = client.get(
            "/api/game/nonexistent/state",
            headers=_auth_header(player_token),
        )
        assert resp.status_code in [403, 404]


class TestGameCleanup:
    """Test game store capacity and cleanup."""

    def test_game_store_operations(self):
        """Verify basic game_store create/get/delete."""
        game = game_store.create_game(human_seat=1)
        game_id = game.id

        assert game_store.get_game(game_id) is not None
        game_store.delete_game(game_id)
        assert game_store.get_game(game_id) is None
