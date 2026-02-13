"""Integration tests for authentication flows (register, login, logout)."""
import pytest


class TestRegisterFlow:
    """Test user registration end-to-end."""

    def test_register_success(self, client):
        """Register a new user and receive token + cookie."""
        resp = client.post("/api/auth/register", json={
            "email": "newuser@example.com",
            "password": "StrongPass123!",
            "nickname": "NewUser",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["nickname"] == "NewUser"
        # Cookie should be set
        assert "user_access_token" in resp.cookies

    def test_register_duplicate_email(self, client):
        """Registering with an existing email returns 409."""
        payload = {
            "email": "dup@example.com",
            "password": "StrongPass123!",
            "nickname": "Dup1",
        }
        resp1 = client.post("/api/auth/register", json=payload)
        assert resp1.status_code == 200

        payload["nickname"] = "Dup2"
        resp2 = client.post("/api/auth/register", json=payload)
        assert resp2.status_code == 409
        assert "Email already registered" in resp2.json()["detail"]

    def test_register_duplicate_nickname(self, client):
        """Registering with an existing nickname returns 409."""
        client.post("/api/auth/register", json={
            "email": "nick1@example.com",
            "password": "StrongPass123!",
            "nickname": "SameNick",
        })
        resp = client.post("/api/auth/register", json={
            "email": "nick2@example.com",
            "password": "StrongPass123!",
            "nickname": "SameNick",
        })
        assert resp.status_code == 409
        assert "Nickname already taken" in resp.json()["detail"]


class TestLoginFlow:
    """Test user login end-to-end."""

    def _register(self, client, email="login@example.com", password="Pass123!", nickname="LoginUser"):
        return client.post("/api/auth/register", json={
            "email": email, "password": password, "nickname": nickname,
        })

    def test_login_success(self, client):
        """Login with correct credentials returns token."""
        self._register(client)
        resp = client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "Pass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "login@example.com"
        assert "user_access_token" in resp.cookies

    def test_login_wrong_password(self, client):
        """Login with wrong password returns 401."""
        self._register(client, email="wrong@example.com", nickname="WrongPw")
        resp = client.post("/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "BadPassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client):
        """Login with non-existent email returns 401."""
        resp = client.post("/api/auth/login", json={
            "email": "ghost@example.com",
            "password": "Pass123!",
        })
        assert resp.status_code == 401


class TestLogoutFlow:
    """Test logout end-to-end."""

    def test_logout_clears_cookie(self, client):
        """Logout clears the auth cookie."""
        reg = client.post("/api/auth/register", json={
            "email": "logout@example.com",
            "password": "Pass123!",
            "nickname": "LogoutUser",
        })
        token = reg.json()["access_token"]

        resp = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out successfully"

    def test_logout_without_token(self, client):
        """Logout without auth returns 401."""
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401


class TestProtectedEndpoints:
    """Test that protected endpoints require authentication."""

    def test_me_requires_auth(self, client):
        """GET /api/users/me requires authentication."""
        resp = client.get("/api/users/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client):
        """GET /api/users/me returns user info with valid token."""
        reg = client.post("/api/auth/register", json={
            "email": "me@example.com",
            "password": "Pass123!",
            "nickname": "MeUser",
        })
        token = reg.json()["access_token"]

        resp = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"
