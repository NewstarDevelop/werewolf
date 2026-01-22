"""Tests for dual-auth cookie fallback in get_current_user().

Verifies:
1. Room token in Authorization + user cookie → falls back to cookie (fix scenario)
2. User token in Authorization → works normally
3. Conflicting user_ids in header and cookie → returns 401
4. Cookie-only auth → works normally
"""
import uuid
from datetime import datetime

import pytest
from app.core.auth import create_player_token, create_user_token
from app.models.user import User


def _unique_id() -> str:
    """Generate unique ID for test isolation."""
    return str(uuid.uuid4())


def _unique_email() -> str:
    """Generate unique email for test isolation."""
    return f"user_{uuid.uuid4().hex[:8]}@example.com"


class TestDualAuthCookieFallback:
    """Tests for cookie fallback when Authorization header has room token."""

    def test_room_token_in_header_falls_back_to_cookie(self, client, db_session):
        """
        Scenario: User logged in (cookie) + entered game room (Authorization header).
        Expected: User-related endpoints should use cookie auth, not fail.
        """
        # Create a test user
        user_id = _unique_id()
        user = User(
            id=user_id,
            email=_unique_email(),
            password_hash=None,
            nickname=f"TestUser_{user_id[:8]}",
            is_active=True,
            is_email_verified=False,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=None,
            preferences={},
        )
        db_session.add(user)
        db_session.commit()

        # Create user token (for cookie) and room token (for header)
        user_token = create_user_token(user_id=user_id, is_admin=False)
        room_token = create_player_token(
            player_id=_unique_id(),
            room_id=_unique_id()
        )

        # Make request with room token in header and user token in cookie
        response = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {room_token}"},
            cookies={"user_access_token": user_token}
        )

        # Should succeed by falling back to cookie auth
        assert response.status_code == 200
        assert response.json()["id"] == user_id

    def test_user_token_in_header_works_without_cookie(self, client, db_session):
        """User token via Authorization header should work (compatibility)."""
        user_id = _unique_id()
        user = User(
            id=user_id,
            email=_unique_email(),
            password_hash=None,
            nickname=f"TestUser_{user_id[:8]}",
            is_active=True,
            is_email_verified=False,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=None,
            preferences={},
        )
        db_session.add(user)
        db_session.commit()

        user_token = create_user_token(user_id=user_id, is_admin=False)

        response = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {user_token}"}
        )

        assert response.status_code == 200
        assert response.json()["id"] == user_id

    def test_cookie_only_auth_works(self, client, db_session):
        """Cookie-only auth should work (no Authorization header)."""
        user_id = _unique_id()
        user = User(
            id=user_id,
            email=_unique_email(),
            password_hash=None,
            nickname=f"TestUser_{user_id[:8]}",
            is_active=True,
            is_email_verified=False,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=None,
            preferences={},
        )
        db_session.add(user)
        db_session.commit()

        user_token = create_user_token(user_id=user_id, is_admin=False)

        response = client.get(
            "/api/users/me",
            cookies={"user_access_token": user_token}
        )

        assert response.status_code == 200
        assert response.json()["id"] == user_id

    def test_conflicting_user_ids_returns_401(self, client, db_session):
        """Different user_ids in header and cookie should be rejected."""
        # Create two users
        user1_id = _unique_id()
        user1 = User(
            id=user1_id,
            email=_unique_email(),
            password_hash=None,
            nickname=f"User1_{user1_id[:8]}",
            is_active=True,
            is_email_verified=False,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=None,
            preferences={},
        )
        db_session.add(user1)

        user2_id = _unique_id()
        user2 = User(
            id=user2_id,
            email=_unique_email(),
            password_hash=None,
            nickname=f"User2_{user2_id[:8]}",
            is_active=True,
            is_email_verified=False,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=None,
            preferences={},
        )
        db_session.add(user2)
        db_session.commit()

        # Create tokens for both users
        user1_token = create_user_token(user_id=user1_id, is_admin=False)
        user2_token = create_user_token(user_id=user2_id, is_admin=False)

        # Try to use different user tokens in header and cookie
        response = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {user1_token}"},
            cookies={"user_access_token": user2_token}
        )

        # Should fail with conflict error
        assert response.status_code == 401
        assert "conflict" in response.json()["detail"].lower()

    def test_invalid_header_token_falls_back_to_cookie(self, client, db_session):
        """Invalid header token should fall back to cookie auth."""
        user_id = _unique_id()
        user = User(
            id=user_id,
            email=_unique_email(),
            password_hash=None,
            nickname=f"TestUser_{user_id[:8]}",
            is_active=True,
            is_email_verified=False,
            is_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_login_at=None,
            preferences={},
        )
        db_session.add(user)
        db_session.commit()

        user_token = create_user_token(user_id=user_id, is_admin=False)

        # Invalid token in header, valid token in cookie
        response = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer invalid-token"},
            cookies={"user_access_token": user_token}
        )

        # Should succeed by falling back to cookie
        assert response.status_code == 200
        assert response.json()["id"] == user_id

    def test_no_auth_returns_401(self, client):
        """No auth credentials should return 401."""
        response = client.get("/api/users/me")
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()
