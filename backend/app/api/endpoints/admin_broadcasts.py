"""Admin broadcast management endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api.endpoints.game import verify_admin
from app.core.database import get_db
from app.models.notification_broadcast import NotificationBroadcast
from app.models.user import User
from app.schemas.notification_broadcast import (
    BatchAction,
    BroadcastBatchRequest,
    BroadcastBatchResponse,
    BroadcastCreateRequest,
    BroadcastCreateResponse,
    BroadcastDetail,
    BroadcastListItem,
    BroadcastListResponse,
    BroadcastResendRequest,
    BroadcastStatus,
    BroadcastUpdateRequest,
    DeleteMode,
    ResendScope,
)
from app.schemas.notification import NotificationCategory, NotificationPersistPolicy
from app.services.notification_emitter import emit_to_users
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/admin/notifications/broadcasts", tags=["admin-broadcasts"])
logger = logging.getLogger(__name__)

DEFAULT_BROADCAST_PAGE_SIZE = 500


async def _execute_broadcast(
    db: Session,
    broadcast: NotificationBroadcast,
    actor_id: str,
) -> None:
    """Execute the actual broadcast to users."""
    # Update status to SENDING
    broadcast.status = BroadcastStatus.SENDING.value
    db.commit()

    # Query active users with pagination
    base_query = db.query(User.id).filter(User.is_active.is_(True))
    total_targets = int(base_query.count() or 0)
    broadcast.total_targets = total_targets

    processed = 0
    sent_count = 0
    failed_count = 0
    offset = 0

    try:
        while True:
            user_ids = [
                row[0]
                for row in base_query.order_by(User.id)
                .offset(offset)
                .limit(DEFAULT_BROADCAST_PAGE_SIZE)
                .all()
            ]
            if not user_ids:
                break

            try:
                await emit_to_users(
                    db,
                    user_ids=user_ids,
                    category=NotificationCategory(broadcast.category),
                    title=broadcast.title,
                    body=broadcast.body,
                    data=broadcast.data or {},
                    persist_policy=NotificationPersistPolicy(broadcast.persist_policy),
                    idempotency_key_prefix=broadcast.idempotency_key,
                    broadcast_id=broadcast.id,
                )
                sent_count += len(user_ids)
            except Exception as e:
                logger.error(f"Broadcast batch failed: {e}")
                failed_count += len(user_ids)
                broadcast.last_error = str(e)[:500]

            processed += len(user_ids)
            offset += DEFAULT_BROADCAST_PAGE_SIZE

            # Update progress
            broadcast.processed = processed
            broadcast.sent_count = sent_count
            broadcast.failed_count = failed_count
            db.commit()

        # Determine final status
        if failed_count == 0:
            broadcast.status = BroadcastStatus.SENT.value
        elif sent_count == 0:
            broadcast.status = BroadcastStatus.FAILED.value
        else:
            broadcast.status = BroadcastStatus.PARTIAL_FAILED.value

        broadcast.sent_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        logger.error(f"Broadcast execution failed: {e}")
        broadcast.status = BroadcastStatus.FAILED.value
        broadcast.last_error = str(e)[:500]
        db.commit()
        raise


@router.get("", response_model=BroadcastListResponse)
async def list_broadcasts(
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
    status: Optional[BroadcastStatus] = Query(None),
    category: Optional[NotificationCategory] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    q: Optional[str] = Query(None, min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List broadcast history with filtering and pagination.
    GET /api/admin/notifications/broadcasts
    """
    query = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.deleted_at.is_(None)
    )

    # Apply filters
    if status:
        query = query.filter(NotificationBroadcast.status == status.value)
    if category:
        query = query.filter(NotificationBroadcast.category == category.value)
    if date_from:
        query = query.filter(NotificationBroadcast.created_at >= date_from)
    if date_to:
        query = query.filter(NotificationBroadcast.created_at <= date_to)
    if q:
        search_pattern = f"%{q}%"
        query = query.filter(
            or_(
                NotificationBroadcast.title.ilike(search_pattern),
                NotificationBroadcast.body.ilike(search_pattern),
            )
        )

    # Get total count
    total = query.count()

    # Apply pagination
    items = (
        query.order_by(NotificationBroadcast.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return BroadcastListResponse(
        items=[BroadcastListItem.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{broadcast_id}", response_model=BroadcastDetail)
async def get_broadcast(
    broadcast_id: str,
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Get broadcast detail.
    GET /api/admin/notifications/broadcasts/{broadcast_id}
    """
    broadcast = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.id == broadcast_id
    ).first()

    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    return BroadcastDetail.model_validate(broadcast)


@router.post("", response_model=BroadcastCreateResponse, status_code=202)
async def create_broadcast(
    request: Request,
    body: BroadcastCreateRequest,
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Create and optionally send a broadcast.
    POST /api/admin/notifications/broadcasts
    """
    client_ip: Optional[str] = None
    try:
        if request.client:
            client_ip = request.client.host
    except Exception:
        client_ip = "unknown"

    actor_id = actor.get("player_id", "unknown")
    logger.warning(
        "BROADCAST_CREATE actor=%s ip=%s idem=%s category=%s send_now=%s",
        actor_id,
        client_ip,
        body.idempotency_key,
        body.category.value,
        body.send_now,
    )

    # Check idempotency
    existing = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.idempotency_key == body.idempotency_key
    ).first()
    if existing:
        return BroadcastCreateResponse(
            id=existing.id,
            status=BroadcastStatus(existing.status),
            total_targets=existing.total_targets,
            processed=existing.processed,
        )

    # Create broadcast record
    broadcast = NotificationBroadcast(
        id=str(uuid.uuid4()),
        idempotency_key=body.idempotency_key,
        title=body.title,
        body=body.body,
        category=body.category.value,
        data=body.data,
        persist_policy=body.persist_policy.value,
        status=BroadcastStatus.DRAFT.value if not body.send_now else BroadcastStatus.SENDING.value,
        created_by=actor_id if actor_id != "unknown" else None,
    )
    db.add(broadcast)
    db.commit()
    db.refresh(broadcast)

    if body.send_now:
        await _execute_broadcast(db, broadcast, actor_id)
        db.refresh(broadcast)

    logger.warning(
        "BROADCAST_CREATED actor=%s id=%s status=%s",
        actor_id,
        broadcast.id,
        broadcast.status,
    )

    return BroadcastCreateResponse(
        id=broadcast.id,
        status=BroadcastStatus(broadcast.status),
        total_targets=broadcast.total_targets,
        processed=broadcast.processed,
    )


@router.patch("/{broadcast_id}", response_model=BroadcastDetail)
async def update_broadcast(
    broadcast_id: str,
    body: BroadcastUpdateRequest,
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Update a draft broadcast.
    PATCH /api/admin/notifications/broadcasts/{broadcast_id}
    Only DRAFT status allows editing.
    """
    broadcast = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.id == broadcast_id
    ).first()

    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    if broadcast.status != BroadcastStatus.DRAFT.value:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot edit broadcast with status {broadcast.status}. Only DRAFT broadcasts can be edited.",
        )

    # Update fields
    if body.title is not None:
        broadcast.title = body.title
    if body.body is not None:
        broadcast.body = body.body
    if body.category is not None:
        broadcast.category = body.category.value
    if body.data is not None:
        broadcast.data = body.data
    if body.persist_policy is not None:
        broadcast.persist_policy = body.persist_policy.value

    broadcast.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(broadcast)

    return BroadcastDetail.model_validate(broadcast)


@router.post("/{broadcast_id}/send", response_model=BroadcastCreateResponse, status_code=202)
async def send_draft_broadcast(
    broadcast_id: str,
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Send a draft broadcast.
    POST /api/admin/notifications/broadcasts/{broadcast_id}/send
    """
    broadcast = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.id == broadcast_id
    ).first()

    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    if broadcast.status != BroadcastStatus.DRAFT.value:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot send broadcast with status {broadcast.status}. Only DRAFT broadcasts can be sent.",
        )

    actor_id = actor.get("player_id", "unknown")
    await _execute_broadcast(db, broadcast, actor_id)
    db.refresh(broadcast)

    return BroadcastCreateResponse(
        id=broadcast.id,
        status=BroadcastStatus(broadcast.status),
        total_targets=broadcast.total_targets,
        processed=broadcast.processed,
    )


@router.post("/{broadcast_id}/resend", response_model=BroadcastCreateResponse, status_code=202)
async def resend_broadcast(
    broadcast_id: str,
    body: BroadcastResendRequest,
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Resend a broadcast (creates a new broadcast linked to original).
    POST /api/admin/notifications/broadcasts/{broadcast_id}/resend
    """
    original = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.id == broadcast_id
    ).first()

    if not original:
        raise HTTPException(status_code=404, detail="Original broadcast not found")

    if original.status not in [
        BroadcastStatus.SENT.value,
        BroadcastStatus.PARTIAL_FAILED.value,
        BroadcastStatus.FAILED.value,
    ]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot resend broadcast with status {original.status}.",
        )

    actor_id = actor.get("player_id", "unknown")

    # Check idempotency key collision
    existing = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.idempotency_key == body.idempotency_key
    ).first()
    if existing:
        # Return existing broadcast if idempotency key already used
        return BroadcastCreateResponse(
            id=existing.id,
            status=BroadcastStatus(existing.status),
            total_targets=existing.total_targets,
            processed=existing.processed,
        )

    # Create new broadcast linked to original
    new_broadcast = NotificationBroadcast(
        id=str(uuid.uuid4()),
        idempotency_key=body.idempotency_key,
        title=original.title,
        body=original.body,
        category=original.category,
        data=original.data,
        persist_policy=original.persist_policy,
        status=BroadcastStatus.SENDING.value,
        created_by=actor_id if actor_id != "unknown" else None,
        resend_of_id=original.id,
    )
    db.add(new_broadcast)
    db.commit()
    db.refresh(new_broadcast)

    await _execute_broadcast(db, new_broadcast, actor_id)
    db.refresh(new_broadcast)

    return BroadcastCreateResponse(
        id=new_broadcast.id,
        status=BroadcastStatus(new_broadcast.status),
        total_targets=new_broadcast.total_targets,
        processed=new_broadcast.processed,
    )


@router.delete("/{broadcast_id}", status_code=204)
async def delete_broadcast(
    broadcast_id: str,
    mode: DeleteMode = Query(default=DeleteMode.HISTORY),
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a broadcast (soft delete).
    DELETE /api/admin/notifications/broadcasts/{broadcast_id}
    """
    broadcast = db.query(NotificationBroadcast).filter(
        NotificationBroadcast.id == broadcast_id
    ).first()

    if not broadcast:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    if broadcast.status == BroadcastStatus.SENDING.value:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete broadcast while sending.",
        )

    broadcast.status = BroadcastStatus.DELETED.value
    broadcast.deleted_at = datetime.utcnow()
    db.commit()

    # Note: CASCADE mode would delete associated notifications
    # This is intentionally not implemented for safety
    if mode == DeleteMode.CASCADE:
        logger.warning(
            "CASCADE delete requested but not implemented for safety. "
            "Broadcast %s soft-deleted only.",
            broadcast_id,
        )

    return None


@router.post("/batch", response_model=BroadcastBatchResponse)
async def batch_operation(
    body: BroadcastBatchRequest,
    actor: Dict = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    """
    Batch operations on broadcasts.
    POST /api/admin/notifications/broadcasts/batch
    """
    accepted = len(body.ids)
    updated = 0
    failed: list[str] = []

    for broadcast_id in body.ids:
        try:
            broadcast = db.query(NotificationBroadcast).filter(
                NotificationBroadcast.id == broadcast_id
            ).first()

            if not broadcast:
                failed.append(broadcast_id)
                continue

            if body.action == BatchAction.DELETE:
                if broadcast.status == BroadcastStatus.SENDING.value:
                    failed.append(broadcast_id)
                    continue

                broadcast.status = BroadcastStatus.DELETED.value
                broadcast.deleted_at = datetime.utcnow()
                updated += 1

        except Exception as e:
            logger.error(f"Batch operation failed for {broadcast_id}: {e}")
            db.rollback()
            failed.append(broadcast_id)

    db.commit()

    return BroadcastBatchResponse(
        accepted=accepted,
        updated=updated,
        failed=failed,
    )
