"""Authentication API endpoints.

Migrated to async database access using SQLAlchemy 2.0 async API.
"""
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Cookie, Request
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database_async import get_async_db
from app.core.auth import create_user_token, create_admin_token
from app.core.security import hash_password, verify_password
from app.core.config import settings
from app.core.client_ip import get_client_ip, get_client_ip_for_logging  # A5-FIX
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    UserResponse,
    OAuthStateResponse,
    PasswordResetRequest
)
from app.services.oauth import LinuxdoOAuthService
from app.services.login_rate_limiter import admin_login_limiter, user_login_limiter
from app.api.dependencies import get_current_user, get_optional_user

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

COOKIE_SECURE = not settings.DEBUG


def sanitize_next_url(next_url: str) -> str:
    """
    Validate next URL to prevent open redirect attacks.
    Only allows site-relative paths (e.g., /lobby, /profile).
    Rejects absolute URLs, scheme-relative URLs, and non-root paths.
    """
    if not next_url:
        return "/lobby"

    # Reject CRLF injection attempts
    if "\r" in next_url or "\n" in next_url:
        raise HTTPException(status_code=400, detail="Invalid next URL: control characters not allowed")

    parsed = urlparse(next_url)

    # Reject if has scheme (http://, https://) or netloc (domain)
    if parsed.scheme or parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid next URL: absolute URLs not allowed")

    # Reject scheme-relative URLs (//evil.com)
    if next_url.startswith("//"):
        raise HTTPException(status_code=400, detail="Invalid next URL: scheme-relative URLs not allowed")

    # Must start with /
    if not next_url.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid next URL: must be a root-relative path")

    return next_url


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Register a new user with email and password.

    Security: Sets HttpOnly cookie in addition to returning token in response
    for backward compatibility.
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check if nickname already exists
    result = await db.execute(
        select(User).where(User.nickname == body.nickname)
    )
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Nickname already taken")

    # Create new user
    from sqlalchemy.exc import IntegrityError
    try:
        user = User(
            id=str(uuid.uuid4()),
            email=body.email.lower(),
            password_hash=hash_password(body.password),
            nickname=body.nickname,
            is_active=True,
            is_email_verified=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_login_at=datetime.now(timezone.utc),
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        # Handle unique constraint violation at DB level
        error_str = str(e.orig).lower() if e.orig else str(e).lower()
        if "nickname" in error_str:
            raise HTTPException(status_code=409, detail="Nickname already taken")
        elif "email" in error_str:
            raise HTTPException(status_code=409, detail="Email already registered")
        else:
            raise HTTPException(status_code=409, detail="Registration failed due to conflict")

    # Generate token (include is_admin flag from user model)
    access_token = create_user_token(user_id=user.id, is_admin=user.is_admin)

    # Create response data
    response_data = AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

    # Create JSON response with cookie (mode='json' ensures datetime serialization)
    response = JSONResponse(content=response_data.model_dump(mode='json'))
    response.set_cookie(
        key="user_access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/"
    )

    return response


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Login with email and password.

    Security: Sets HttpOnly cookie in addition to returning token in response
    for backward compatibility.
    Security: Rate limited to prevent brute-force attacks.
    """
    # Rate limiting to prevent brute-force attacks
    client_ip = get_client_ip(request)
    is_allowed, retry_after = user_login_limiter.check_rate_limit(client_ip)
    if not is_allowed:
        logger.warning(f"User login rate limited for IP {get_client_ip_for_logging(request)}")
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )

    # Find user by email
    result = await db.execute(
        select(User).where(User.email == body.email.lower())
    )
    user = result.scalars().first()

    # Verify password
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        # Record failed attempt
        user_login_limiter.record_attempt(client_ip, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Record successful attempt
    user_login_limiter.record_attempt(client_ip, success=True)

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Generate token (include is_admin flag from user model)
    access_token = create_user_token(user_id=user.id, is_admin=user.is_admin)

    # Create response data
    response_data = AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

    # Create JSON response with cookie (mode='json' ensures datetime serialization)
    response = JSONResponse(content=response_data.model_dump(mode='json'))
    response.set_cookie(
        key="user_access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/"
    )

    return response


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout current user and clear HttpOnly cookie.

    Security: Deletes the user_access_token cookie to prevent automatic re-login.
    """
    response = JSONResponse(content={"message": "Logged out successfully"})

    # Delete the HttpOnly cookie
    response.delete_cookie(
        key="user_access_token",
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax"
    )

    return response


@router.get("/oauth/linuxdo", response_model=OAuthStateResponse)
async def oauth_linuxdo(
    next: str = Query("/lobby", description="Redirect URL after login"),
    bind: bool = Query(False, description="Bind mode (requires existing login)"),
    current_user: dict = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Initiate linux.do OAuth2 authorization flow.

    Security:
    - next URL is validated to prevent open redirect attacks
    - State parameter provides CSRF protection for OAuth flow
    - Note: Uses GET method as required by OAuth 2.0 standard
    """
    # Validate next URL before storing in state
    validated_next = sanitize_next_url(next)

    bind_user_id = current_user.get("user_id") if bind and current_user else None

    authorize_url, state = await LinuxdoOAuthService.generate_authorization_url(
        db=db,
        next_url=validated_next,
        bind_user_id=bind_user_id
    )

    return OAuthStateResponse(authorize_url=authorize_url, state=state)


@router.get("/callback/linuxdo")
async def oauth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Handle linux.do OAuth2 callback.

    Security: Token is set as HttpOnly cookie instead of URL parameter
    to prevent token leakage via browser history, logs, and Referer headers.
    """
    try:
        # Verify state
        oauth_state = await LinuxdoOAuthService.verify_state(db, state)

        # Exchange code for token
        token_response = await LinuxdoOAuthService.exchange_code_for_token(code)
        access_token = token_response.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token")

        # Fetch user info
        userinfo = await LinuxdoOAuthService.fetch_userinfo(access_token)

        # LinuxDO returns: id, username, name, avatar_template (no email field)
        provider_user_id = userinfo.get("id")
        provider_email = None  # LinuxDO doesn't provide email
        provider_username = userinfo.get("username") or userinfo.get("name")
        avatar_url = userinfo.get("avatar_template")

        if not provider_user_id:
            raise HTTPException(status_code=400, detail="Failed to get user ID from OAuth provider")

        # Find or create user
        user = await LinuxdoOAuthService.find_or_create_user(
            db=db,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            provider_username=provider_username,
            avatar_url=avatar_url,
            bind_user_id=oauth_state.bind_user_id
        )

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

        # Generate JWT token (include is_admin flag from user model)
        jwt_token = create_user_token(user_id=user.id, is_admin=user.is_admin)

        # Validate and sanitize redirect URL
        next_url = sanitize_next_url(oauth_state.next_url or "/lobby")

        # Create redirect response with HttpOnly cookie
        response = RedirectResponse(url=next_url, status_code=302)
        response.set_cookie(
            key="user_access_token",
            value=jwt_token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            max_age=settings.JWT_EXPIRE_MINUTES * 60,
            path="/"
        )

        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e) or "Invalid OAuth request")
    except Exception:
        logger.error("OAuth callback failed", exc_info=True)
        raise HTTPException(status_code=500, detail="OAuth callback failed")


@router.post("/reset-password")
async def reset_password(body: PasswordResetRequest):
    """
    Request password reset (always returns 202 to prevent email enumeration).
    """
    # Always return success to prevent email enumeration
    # In production, send email with reset link here

    return {"message": "If the email exists, a password reset link has been sent"}


class AdminLoginRequest(BaseModel):
    """Request body for admin password login."""
    password: str


class AdminLoginResponse(BaseModel):
    """Response for admin login."""
    access_token: str
    token_type: str = "bearer"


@router.post("/admin-login", response_model=AdminLoginResponse)
async def admin_login(body: AdminLoginRequest, request: Request):
    """
    Login to admin panel with password.

    This endpoint validates the admin password configured in ADMIN_PASSWORD
    environment variable and returns a JWT admin token.

    Security:
    - Uses constant-time comparison to prevent timing attacks
    - Returns generic error message to prevent password enumeration
    - Rate limited to prevent brute-force attacks
    """
    # A5-FIX: 使用 get_client_ip 获取真实客户端 IP
    client_ip = get_client_ip(request)

    # Check rate limit
    is_allowed, retry_after = admin_login_limiter.check_rate_limit(client_ip)
    if not is_allowed:
        logger.warning(f"Admin login rate limited for IP {get_client_ip_for_logging(request)}")
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )

    # Check if ADMIN_PASSWORD is configured
    if not settings.ADMIN_PASSWORD:
        logger.warning("Admin login attempted but ADMIN_PASSWORD is not configured")
        raise HTTPException(
            status_code=503,
            detail="Admin password authentication is not configured"
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(body.password, settings.ADMIN_PASSWORD):
        # Record failed attempt
        admin_login_limiter.record_attempt(client_ip, success=False)
        logger.warning(f"Admin login failed: invalid password from IP {get_client_ip_for_logging(request)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid admin password"
        )

    # Record successful attempt
    admin_login_limiter.record_attempt(client_ip, success=True)

    # Generate admin JWT token
    admin_token = create_admin_token()
    logger.info(f"Admin login successful via password authentication from IP {get_client_ip_for_logging(request)}")

    return AdminLoginResponse(access_token=admin_token)


class AdminVerifyResponse(BaseModel):
    """Response for admin token verification."""
    valid: bool
    is_admin: bool = True


@router.get("/admin-verify", response_model=AdminVerifyResponse)
async def verify_admin_token(
    authorization: Optional[str] = Header(None),
    user_access_token: Optional[str] = Cookie(None)
):
    """
    Verify admin token validity.

    GET /api/auth/admin-verify

    This endpoint validates whether the provided JWT token has admin privileges.
    Used by frontend to verify admin access without depending on env management endpoints.

    Security:
    - Supports both Authorization header (Bearer token) and HttpOnly cookie
    - Returns valid=true only if token is valid AND has is_admin=True
    """
    from app.core.auth import verify_player_token
    import jwt as pyjwt

    # Extract token from header or cookie
    token = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    elif user_access_token:
        token = user_access_token

    if not token:
        return AdminVerifyResponse(valid=False, is_admin=False)

    try:
        payload = verify_player_token(token)
        is_admin = payload.get("is_admin", False)
        return AdminVerifyResponse(valid=is_admin, is_admin=is_admin)
    except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError, Exception):
        return AdminVerifyResponse(valid=False, is_admin=False)
