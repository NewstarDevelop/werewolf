"""Authentication API endpoints."""
import logging
import uuid
from datetime import datetime
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import create_user_token
from app.core.security import hash_password, verify_password
from app.core.config import settings
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
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new user with email and password.

    Security: Sets HttpOnly cookie in addition to returning token in response
    for backward compatibility.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(
        User.email == body.email.lower()
    ).first()

    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create new user
    user = User(
        id=str(uuid.uuid4()),
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        nickname=body.nickname,
        is_active=True,
        is_email_verified=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_login_at=datetime.utcnow(),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate token
    access_token = create_user_token(user_id=user.id)

    # Create response with cookie
    response = Response(
        content=AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.from_orm(user)
        ).json(),
        media_type="application/json"
    )

    # Set HttpOnly cookie
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
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Login with email and password.

    Security: Sets HttpOnly cookie in addition to returning token in response
    for backward compatibility.
    """
    # Find user by email
    user = db.query(User).filter(
        User.email == body.email.lower()
    ).first()

    # Verify password
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()

    # Generate token
    access_token = create_user_token(user_id=user.id)

    # Create response with cookie
    response = Response(
        content=AuthResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.from_orm(user)
        ).json(),
        media_type="application/json"
    )

    # Set HttpOnly cookie
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
    response = Response(
        content='{"message":"Logged out successfully"}',
        media_type="application/json",
        status_code=200
    )

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
    db: Session = Depends(get_db)
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

    authorize_url, state = LinuxdoOAuthService.generate_authorization_url(
        db=db,
        next_url=validated_next,
        bind_user_id=bind_user_id
    )

    return OAuthStateResponse(authorize_url=authorize_url, state=state)


@router.get("/callback/linuxdo")
async def oauth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    db: Session = Depends(get_db)
):
    """
    Handle linux.do OAuth2 callback.

    Security: Token is set as HttpOnly cookie instead of URL parameter
    to prevent token leakage via browser history, logs, and Referer headers.
    """
    try:
        # Verify state
        oauth_state = LinuxdoOAuthService.verify_state(db, state)

        # Exchange code for token
        token_response = await LinuxdoOAuthService.exchange_code_for_token(code)
        access_token = token_response.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to obtain access token")

        # Fetch user info
        userinfo = await LinuxdoOAuthService.fetch_userinfo(access_token)

        provider_user_id = userinfo.get("sub") or userinfo.get("id")
        provider_email = userinfo.get("email")
        provider_username = userinfo.get("preferred_username") or userinfo.get("username") or userinfo.get("name")
        avatar_url = userinfo.get("picture") or userinfo.get("avatar_url")

        if not provider_user_id:
            raise HTTPException(status_code=400, detail="Failed to get user ID from OAuth provider")

        # Find or create user
        user = LinuxdoOAuthService.find_or_create_user(
            db=db,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            provider_username=provider_username,
            avatar_url=avatar_url,
            bind_user_id=oauth_state.bind_user_id
        )

        # Update last login
        user.last_login_at = datetime.utcnow()
        db.commit()

        # Generate JWT token
        jwt_token = create_user_token(user_id=user.id)

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
    except Exception:
        logger.error("OAuth callback failed", exc_info=True)
        raise HTTPException(status_code=500, detail="OAuth callback failed")


@router.post("/reset-password")
async def reset_password(body: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Request password reset (always returns 202 to prevent email enumeration).
    """
    # Always return success to prevent email enumeration
    # In production, send email with reset link here

    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/logout")
async def logout():
    """
    用户退出登录
    POST /api/auth/logout

    清除 HttpOnly Cookie 中的 JWT token
    前端需要额外清除 localStorage 中的 player_id
    """
    response = Response(
        content='{"message":"退出登录成功"}',
        media_type="application/json"
    )

    # 清除 user_access_token cookie
    response.delete_cookie(
        key="user_access_token",
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax"
    )

    return response
