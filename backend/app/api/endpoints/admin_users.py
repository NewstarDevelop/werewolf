"""Admin user management endpoints."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.endpoints.game import verify_admin
from app.core.database_async import get_async_db
from app.models.user import User
from app.schemas.admin_users import (
    AdminFlagFilter,
    AdminSetUserActiveRequest,
    AdminSetUserAdminRequest,
    AdminUpdateUserProfileRequest,
    AdminUserBatchAction,
    AdminUserBatchRequest,
    AdminUserBatchResponse,
    UserDetailResponse,
    UserListItem,
    UserListResponse,
    UserSort,
    UserStatusFilter,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
logger = logging.getLogger(__name__)


# CSV injection prevention pattern
CSV_INJECTION_CHARS = {'=', '+', '-', '@', '\t', '\r', '\n'}


def sanitize_csv_value(value) -> str:
    """Sanitize a value for CSV export to prevent formula injection.

    Checks the first non-whitespace character to prevent bypasses
    like "  =1+1" which could still be executed by spreadsheet software.
    """
    if value is None:
        return ""
    str_value = str(value)
    # Check first non-whitespace character
    stripped = str_value.lstrip()
    if stripped and stripped[0] in CSV_INJECTION_CHARS:
        return "'" + str_value
    return str_value


@router.get("", response_model=UserListResponse)
async def list_users(
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
    q: Optional[str] = Query(None, min_length=1, max_length=100),
    status: UserStatusFilter = Query(default=UserStatusFilter.ALL),
    admin: AdminFlagFilter = Query(default=AdminFlagFilter.ALL),
    sort: UserSort = Query(default=UserSort.CREATED_AT_DESC),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List users with filtering and pagination.
    GET /api/admin/users
    """
    # Build WHERE conditions
    conditions = []
    if status == UserStatusFilter.ACTIVE:
        conditions.append(User.is_active.is_(True))
    elif status == UserStatusFilter.BANNED:
        conditions.append(User.is_active.is_(False))

    if admin == AdminFlagFilter.YES:
        conditions.append(User.is_admin.is_(True))
    elif admin == AdminFlagFilter.NO:
        conditions.append(User.is_admin.is_(False))

    if q:
        search_pattern = f"%{q}%"
        conditions.append(
            or_(
                func.lower(User.nickname).like(func.lower(search_pattern)),
                func.lower(User.email).like(func.lower(search_pattern)),
            )
        )

    # Get total count
    count_result = await db.execute(
        select(func.count(User.id)).where(*conditions) if conditions
        else select(func.count(User.id))
    )
    total = int(count_result.scalar() or 0)

    # Build data query with selected columns
    stmt = select(
        User.id,
        User.nickname,
        User.email,
        User.avatar_url,
        User.is_active,
        User.is_admin,
        User.created_at,
        User.last_login_at,
    )
    if conditions:
        stmt = stmt.where(*conditions)

    # Apply sorting
    if sort == UserSort.CREATED_AT_DESC:
        stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
    elif sort == UserSort.LAST_LOGIN_AT_DESC:
        # SQLite-compatible NULLS LAST: sort by is_null first, then desc
        stmt = stmt.order_by(
            User.last_login_at.is_(None),
            User.last_login_at.desc(),
            User.id.desc(),
        )
    elif sort == UserSort.ID_ASC:
        stmt = stmt.order_by(User.id.asc())

    # Apply pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.all()

    return UserListResponse(
        items=[
            UserListItem(
                id=item.id,
                nickname=item.nickname,
                email=item.email,
                avatar_url=item.avatar_url,
                is_active=item.is_active,
                is_admin=item.is_admin,
                created_at=item.created_at,
                last_login_at=item.last_login_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export.csv")
async def export_users_csv(
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
    q: Optional[str] = Query(None, min_length=1, max_length=100),
    status: UserStatusFilter = Query(default=UserStatusFilter.ALL),
    admin: AdminFlagFilter = Query(default=AdminFlagFilter.ALL),
    sort: UserSort = Query(default=UserSort.CREATED_AT_DESC),
    max_rows: int = Query(5000, ge=1, le=50000),
):
    """
    Export users to CSV with filtering.
    GET /api/admin/users/export.csv
    """
    # Build conditions (same as list_users)
    conditions = []
    if status == UserStatusFilter.ACTIVE:
        conditions.append(User.is_active.is_(True))
    elif status == UserStatusFilter.BANNED:
        conditions.append(User.is_active.is_(False))

    if admin == AdminFlagFilter.YES:
        conditions.append(User.is_admin.is_(True))
    elif admin == AdminFlagFilter.NO:
        conditions.append(User.is_admin.is_(False))

    if q:
        search_pattern = f"%{q}%"
        conditions.append(
            or_(
                func.lower(User.nickname).like(func.lower(search_pattern)),
                func.lower(User.email).like(func.lower(search_pattern)),
            )
        )

    stmt = select(
        User.id,
        User.nickname,
        User.email,
        User.avatar_url,
        User.is_active,
        User.is_admin,
        User.created_at,
        User.last_login_at,
    )
    if conditions:
        stmt = stmt.where(*conditions)

    # Apply sorting
    if sort == UserSort.CREATED_AT_DESC:
        stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
    elif sort == UserSort.LAST_LOGIN_AT_DESC:
        stmt = stmt.order_by(
            User.last_login_at.is_(None),
            User.last_login_at.desc(),
            User.id.desc(),
        )
    elif sort == UserSort.ID_ASC:
        stmt = stmt.order_by(User.id.asc())

    # Limit rows
    result = await db.execute(stmt.limit(max_rows))
    items = result.all()

    # Generate CSV
    def generate():
        output = io.StringIO()
        # Add BOM for Excel compatibility
        yield '\ufeff'

        writer = csv.writer(output)
        # Header
        writer.writerow([
            'id', 'nickname', 'email', 'avatar_url',
            'is_active', 'is_admin', 'created_at', 'last_login_at'
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Data rows
        for item in items:
            writer.writerow([
                sanitize_csv_value(item.id),
                sanitize_csv_value(item.nickname),
                sanitize_csv_value(item.email),
                sanitize_csv_value(item.avatar_url),
                str(item.is_active),
                str(item.is_admin),
                item.created_at.isoformat() if item.created_at else '',
                item.last_login_at.isoformat() if item.last_login_at else '',
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"users_{timestamp}.csv"

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: str,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get user detail.
    GET /api/admin/users/{user_id}
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserDetailResponse.model_validate(user)


@router.patch("/{user_id}/profile", response_model=UserDetailResponse)
async def update_user_profile(
    user_id: str,
    body: AdminUpdateUserProfileRequest,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update user profile (nickname, avatar, bio).
    PATCH /api/admin/users/{user_id}/profile
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check nickname uniqueness if changing
    if body.nickname is not None and body.nickname != user.nickname:
        dup_result = await db.execute(
            select(User).where(User.nickname == body.nickname, User.id != user.id)
        )
        if dup_result.scalars().first():
            raise HTTPException(status_code=409, detail="Nickname already taken")

    # Update fields
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.bio is not None:
        user.bio = body.bio
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url

    user.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Nickname already taken")

    return UserDetailResponse.model_validate(user)


@router.patch("/{user_id}/status", response_model=UserDetailResponse)
async def set_user_status(
    user_id: str,
    body: AdminSetUserActiveRequest,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Set user active status (ban/unban).
    PATCH /api/admin/users/{user_id}/status
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = body.is_active
    user.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update user status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user status")

    logger.warning(
        "USER_STATUS_CHANGED actor=%s user_id=%s is_active=%s",
        actor.get("player_id", "unknown"),
        user_id,
        body.is_active,
    )

    return UserDetailResponse.model_validate(user)


@router.patch("/{user_id}/admin", response_model=UserDetailResponse)
async def set_user_admin(
    user_id: str,
    body: AdminSetUserAdminRequest,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Set user admin flag.
    PATCH /api/admin/users/{user_id}/admin
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_admin = body.is_admin
    user.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update user admin status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user admin status")

    logger.warning(
        "USER_ADMIN_CHANGED actor=%s user_id=%s is_admin=%s",
        actor.get("player_id", "unknown"),
        user_id,
        body.is_admin,
    )

    return UserDetailResponse.model_validate(user)


@router.post("/batch", response_model=AdminUserBatchResponse)
async def batch_operation(
    body: AdminUserBatchRequest,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Batch operations on users.
    POST /api/admin/users/batch
    """
    accepted = len(body.ids)

    # Find existing users
    result = await db.execute(select(User.id).where(User.id.in_(body.ids)))
    existing_ids = {row[0] for row in result.all()}
    failed = [uid for uid in body.ids if uid not in existing_ids]

    # Determine new is_active value based on action
    if body.action == AdminUserBatchAction.BAN:
        new_is_active = False
    elif body.action == AdminUserBatchAction.UNBAN:
        new_is_active = True
    elif body.action == AdminUserBatchAction.DELETE:
        # Soft delete = ban
        new_is_active = False
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    # Bulk update
    updated = 0
    if existing_ids:
        try:
            result = await db.execute(
                update(User)
                .where(User.id.in_(existing_ids))
                .values(
                    is_active=new_is_active,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            updated = result.rowcount or 0
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Batch operation failed: {e}")
            raise HTTPException(status_code=500, detail="Batch operation failed")

    logger.warning(
        "USER_BATCH_OPERATION actor=%s action=%s count=%d updated=%d failed=%d",
        actor.get("player_id", "unknown"),
        body.action.value,
        accepted,
        updated,
        len(failed),
    )

    return AdminUserBatchResponse(
        accepted=accepted,
        updated=updated,
        failed=failed,
    )
