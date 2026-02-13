"""Integration tests for admin endpoints."""
import pytest
from app.core.config import settings

ADMIN_PW = "test-admin-password"


@pytest.fixture(autouse=True)
def _set_admin_pw(monkeypatch):
    """Ensure ADMIN_PASSWORD is set for all admin tests."""
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", ADMIN_PW)


def _get_admin_token(client):
    """Helper: login as admin and return token."""
    resp = client.post("/api/auth/admin-login", json={
        "password": ADMIN_PW,
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _register_user(client, email, nickname):
    """Helper: register a user."""
    resp = client.post("/api/auth/register", json={
        "email": email,
        "password": "StrongPass123!",
        "nickname": nickname,
    })
    assert resp.status_code == 200
    return resp.json()


class TestAdminUserManagement:
    """Test admin user listing and management."""

    def test_list_users(self, client):
        """Admin can list users."""
        admin_token = _get_admin_token(client)
        # Create a user first
        _register_user(client, "admin_list@test.com", "AdminListUser")

        resp = client.get(
            "/api/admin/users",
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_users_requires_admin(self, client):
        """Non-admin cannot list users."""
        user_data = _register_user(client, "nonadmin_list@test.com", "NonAdminList")
        user_token = user_data["access_token"]

        resp = client.get(
            "/api/admin/users",
            headers=_auth_header(user_token),
        )
        assert resp.status_code == 403

    def test_get_user_detail(self, client):
        """Admin can get user detail."""
        admin_token = _get_admin_token(client)
        user_data = _register_user(client, "admin_detail@test.com", "AdminDetailUser")
        user_id = user_data["user"]["id"]

        resp = client.get(
            f"/api/admin/users/{user_id}",
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == user_id

    def test_get_nonexistent_user(self, client):
        """Admin getting non-existent user returns 404."""
        admin_token = _get_admin_token(client)
        resp = client.get(
            "/api/admin/users/nonexistent-id",
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 404


class TestAdminAccess:
    """Test admin access control."""

    def test_admin_verify_with_user_token(self, client):
        """Regular user token fails admin verification."""
        user_data = _register_user(client, "noadmin@test.com", "NoAdmin")
        resp = client.get(
            "/api/auth/admin-verify",
            headers=_auth_header(user_data["access_token"]),
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_admin_verify_no_token(self, client):
        """No token fails admin verification."""
        resp = client.get("/api/auth/admin-verify")
        assert resp.status_code == 200
        assert resp.json()["valid"] is False
