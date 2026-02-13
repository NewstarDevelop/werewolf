"""OAuth2 service for linux.do authentication.

Migrated to async database access using SQLAlchemy 2.0 async API.
"""
import httpx
import uuid
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from typing import Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_random_token, hash_token
from app.models.user import OAuthState, OAuthAccount, User
from app.services.http_client import get_oauth_client, OAUTH_TIMEOUT

logger = logging.getLogger(__name__)


class LinuxdoOAuthService:
    """Service for linux.do OAuth2 authentication."""

    @staticmethod
    async def generate_authorization_url(
        db: AsyncSession,
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
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(oauth_state)
        await db.commit()

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

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If response status is 4xx/5xx
        """
        async with get_oauth_client() as client:
            try:
                response = await client.post(
                    settings.LINUXDO_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": settings.LINUXDO_REDIRECT_URI,
                        "client_id": settings.LINUXDO_CLIENT_ID,
                        "client_secret": settings.LINUXDO_CLIENT_SECRET,
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json"
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                logger.error("OAuth token exchange timed out")
                raise
            except httpx.HTTPStatusError as e:
                logger.error(f"OAuth token exchange failed: {e.response.status_code}")
                raise

    @staticmethod
    async def fetch_userinfo(access_token: str) -> Dict:
        """
        Fetch user information from OAuth provider.

        Args:
            access_token: Access token from token exchange

        Returns:
            User info dict

        Raises:
            httpx.TimeoutException: If request times out
            httpx.HTTPStatusError: If response status is 4xx/5xx
        """
        async with get_oauth_client() as client:
            try:
                response = await client.get(
                    settings.LINUXDO_USERINFO_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                logger.error("OAuth userinfo fetch timed out")
                raise
            except httpx.HTTPStatusError as e:
                logger.error(f"OAuth userinfo fetch failed: {e.response.status_code}")
                raise

    @staticmethod
    async def verify_state(db: AsyncSession, state: str) -> OAuthState:
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
        result = await db.execute(
            select(OAuthState).where(
                OAuthState.provider == "linuxdo",
                OAuthState.state_hash == state_hash,
            )
        )
        oauth_state = result.scalars().first()

        if not oauth_state:
            raise ValueError("Invalid state parameter")

        if oauth_state.is_expired():
            raise ValueError("State has expired")

        if oauth_state.is_used():
            raise ValueError("State has already been used")

        # Mark as used
        oauth_state.used_at = datetime.now(timezone.utc)
        await db.commit()

        return oauth_state

    @staticmethod
    async def find_or_create_user(
        db: AsyncSession,
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
        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == "linuxdo",
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        oauth_account = result.scalars().first()

        if oauth_account:
            # User already linked
            return await db.get(User, oauth_account.user_id)

        # Binding mode: link to existing user
        if bind_user_id:
            user = await db.get(User, bind_user_id)
            if not user:
                raise ValueError("Bind target user not found")

            # Create OAuth link
            new_oauth = OAuthAccount(
                user_id=user.id,
                provider="linuxdo",
                provider_user_id=provider_user_id,
                provider_username=provider_username,
                provider_email=provider_email,
                linked_at=datetime.now(timezone.utc),
            )
            db.add(new_oauth)
            await db.commit()
            return user

        # Create new user with unique nickname handling
        base_nickname = provider_username or f"user_{provider_user_id[:8]}"
        nickname = base_nickname

        # Check for nickname conflicts and generate unique one
        suffix = 1
        while True:
            result = await db.execute(
                select(User).where(User.nickname == nickname)
            )
            if not result.scalars().first():
                break
            nickname = f"{base_nickname}_{suffix}"
            suffix += 1
            if suffix > 100:  # Safety limit
                nickname = f"{base_nickname}_{provider_user_id[:8]}"
                break

        user = User(
            id=str(uuid.uuid4()),
            email=provider_email.lower() if provider_email else None,
            nickname=nickname,
            avatar_url=avatar_url,
            is_active=True,
            is_email_verified=bool(provider_email),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

        # Create OAuth link
        oauth_link = OAuthAccount(
            user_id=user.id,
            provider="linuxdo",
            provider_user_id=provider_user_id,
            provider_username=provider_username,
            provider_email=provider_email,
            linked_at=datetime.now(timezone.utc),
        )
        db.add(oauth_link)
        await db.commit()
        await db.refresh(user)

        return user
