"""OAuth2 service for linux.do authentication."""
import httpx
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_random_token, hash_token
from app.models.user import OAuthState, OAuthAccount, User


class LinuxdoOAuthService:
    """Service for linux.do OAuth2 authentication."""

    @staticmethod
    def generate_authorization_url(
        db: Session,
        next_url: str = "/lobby",
        bind_user_id: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Generate OAuth2 authorization URL with state parameter.

        Args:
            db: Database session
            next_url: URL to redirect after successful authentication
            bind_user_id: Optional user ID for account binding mode

        Returns:
            Tuple of (authorize_url, state)
        """
        # Generate cryptographically secure state
        state = generate_random_token(32)
        state_hash = hash_token(state)

        # Store state in database for CSRF protection
        oauth_state = OAuthState(
            id=str(uuid.uuid4()),
            provider="linuxdo",
            state_hash=state_hash,
            next_url=next_url,
            bind_user_id=bind_user_id,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.add(oauth_state)
        db.commit()

        # Build authorization URL
        params = {
            "response_type": "code",
            "client_id": settings.LINUXDO_CLIENT_ID,
            "redirect_uri": settings.LINUXDO_REDIRECT_URI,
            "scope": settings.LINUXDO_SCOPES,
            "state": state,
        }

        authorize_url = f"{settings.LINUXDO_AUTHORIZE_URL}?{urlencode(params)}"
        return authorize_url, state

    @staticmethod
    async def exchange_code_for_token(code: str) -> Dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth provider

        Returns:
            Token response dict with access_token, token_type, etc.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.LINUXDO_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.LINUXDO_REDIRECT_URI,
                    "client_id": settings.LINUXDO_CLIENT_ID,
                    "client_secret": settings.LINUXDO_CLIENT_SECRET,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def fetch_userinfo(access_token: str) -> Dict:
        """
        Fetch user information from OAuth provider.

        Args:
            access_token: Access token from token exchange

        Returns:
            User info dict
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                settings.LINUXDO_USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def verify_state(db: Session, state: str) -> OAuthState:
        """
        Verify OAuth state parameter.

        Args:
            db: Database session
            state: State parameter from OAuth callback

        Returns:
            OAuthState object if valid

        Raises:
            ValueError: If state is invalid, expired, or already used
        """
        state_hash = hash_token(state)
        oauth_state = db.query(OAuthState).filter_by(
            provider="linuxdo",
            state_hash=state_hash
        ).first()

        if not oauth_state:
            raise ValueError("Invalid state parameter")

        if oauth_state.is_expired():
            raise ValueError("State has expired")

        if oauth_state.is_used():
            raise ValueError("State has already been used")

        # Mark as used
        oauth_state.used_at = datetime.utcnow()
        db.commit()

        return oauth_state

    @staticmethod
    def find_or_create_user(
        db: Session,
        provider_user_id: str,
        provider_email: Optional[str],
        provider_username: Optional[str],
        avatar_url: Optional[str],
        bind_user_id: Optional[str] = None
    ) -> User:
        """
        Find existing user by OAuth account or create new one.

        Args:
            db: Database session
            provider_user_id: OAuth provider's user ID
            provider_email: Email from OAuth provider
            provider_username: Username from OAuth provider
            avatar_url: Avatar URL from OAuth provider
            bind_user_id: Optional user ID to bind OAuth account to

        Returns:
            User object
        """
        # Check if OAuth account already exists
        oauth_account = db.query(OAuthAccount).filter_by(
            provider="linuxdo",
            provider_user_id=provider_user_id
        ).first()

        if oauth_account:
            # User already linked
            return db.query(User).get(oauth_account.user_id)

        # Binding mode: link to existing user
        if bind_user_id:
            user = db.query(User).get(bind_user_id)
            if not user:
                raise ValueError("Bind target user not found")

            # Create OAuth link
            new_oauth = OAuthAccount(
                user_id=user.id,
                provider="linuxdo",
                provider_user_id=provider_user_id,
                provider_username=provider_username,
                provider_email=provider_email,
                linked_at=datetime.utcnow(),
            )
            db.add(new_oauth)
            db.commit()
            return user

        # Create new user
        user = User(
            id=str(uuid.uuid4()),
            email=provider_email.lower() if provider_email else None,
            nickname=provider_username or f"user_{provider_user_id[:8]}",
            avatar_url=avatar_url,
            is_active=True,
            is_email_verified=bool(provider_email),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()

        # Create OAuth link
        oauth_link = OAuthAccount(
            user_id=user.id,
            provider="linuxdo",
            provider_user_id=provider_user_id,
            provider_username=provider_username,
            provider_email=provider_email,
            linked_at=datetime.utcnow(),
        )
        db.add(oauth_link)
        db.commit()
        db.refresh(user)

        return user
