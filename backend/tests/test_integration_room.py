"""Integration tests for room CRUD operations."""
import pytest


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


class TestCreateRoom:
    """Test room creation."""

    def test_create_room_success(self, client):
        """Authenticated user can create a room."""
        token = _register_and_get_token(client, "room_create@test.com", "RoomCreator")
        resp = client.post(
            "/api/rooms",
            json={"name": "Test Room", "game_mode": "classic_9"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "room" in data
        assert data["room"]["name"] == "Test Room"
        assert data["room"]["game_mode"] == "classic_9"
        assert data["room"]["max_players"] == 9
        assert "token" in data
        assert "player_id" in data

    def test_create_room_requires_auth(self, client):
        """Room creation without auth returns 401."""
        resp = client.post("/api/rooms", json={"name": "No Auth Room"})
        assert resp.status_code == 401

    def test_create_room_invalid_game_mode(self, client):
        """Invalid game_mode returns 400."""
        token = _register_and_get_token(client, "room_invalid@test.com", "InvalidMode")
        resp = client.post(
            "/api/rooms",
            json={"name": "Bad Mode", "game_mode": "invalid_mode"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 400

    def test_create_room_12p_requires_variant(self, client):
        """12-player mode requires wolf_king_variant."""
        token = _register_and_get_token(client, "room_12p@test.com", "TwelvePlayer")
        resp = client.post(
            "/api/rooms",
            json={"name": "12P Room", "game_mode": "classic_12"},
            headers=_auth_header(token),
        )
        assert resp.status_code == 400

    def test_create_room_one_per_user(self, client):
        """User cannot create a second room while one is active."""
        token = _register_and_get_token(client, "room_dup@test.com", "DupRoom")
        resp1 = client.post(
            "/api/rooms",
            json={"name": "Room 1"},
            headers=_auth_header(token),
        )
        assert resp1.status_code == 200

        resp2 = client.post(
            "/api/rooms",
            json={"name": "Room 2"},
            headers=_auth_header(token),
        )
        assert resp2.status_code == 409


class TestListRooms:
    """Test room listing."""

    def test_list_rooms(self, client):
        """List rooms returns array."""
        resp = client.get("/api/rooms")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestRoomDetail:
    """Test room detail retrieval."""

    def test_get_room_detail(self, client):
        """Get room detail by ID."""
        token = _register_and_get_token(client, "room_detail@test.com", "DetailUser")
        create_resp = client.post(
            "/api/rooms",
            json={"name": "Detail Room"},
            headers=_auth_header(token),
        )
        room_id = create_resp.json()["room"]["id"]

        resp = client.get(
            f"/api/rooms/{room_id}",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["room"]["id"] == room_id
        assert "players" in data
        assert len(data["players"]) == 1  # Creator is in the room

    def test_get_nonexistent_room(self, client):
        """Getting a non-existent room returns 404."""
        token = _register_and_get_token(client, "room_404@test.com", "Room404")
        resp = client.get(
            "/api/rooms/nonexistent-id",
            headers=_auth_header(token),
        )
        assert resp.status_code == 404


class TestJoinRoom:
    """Test room join flow."""

    def test_join_room_success(self, client):
        """A player can join an existing room."""
        # Create room
        creator_token = _register_and_get_token(client, "join_creator@test.com", "JoinCreator")
        create_resp = client.post(
            "/api/rooms",
            json={"name": "Join Room"},
            headers=_auth_header(creator_token),
        )
        room_id = create_resp.json()["room"]["id"]

        # Join as another player (no auth required for joining)
        join_resp = client.post(
            f"/api/rooms/{room_id}/join",
            json={"nickname": "Joiner"},
        )
        assert join_resp.status_code == 200
        data = join_resp.json()
        assert "token" in data
        assert "player_id" in data

    def test_join_nonexistent_room(self, client):
        """Joining a non-existent room returns 404."""
        resp = client.post(
            "/api/rooms/nonexistent-id/join",
            json={"nickname": "Ghost"},
        )
        assert resp.status_code == 404
