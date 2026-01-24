"""Admin update management endpoints (方案 B: 更新代理)."""

from __future__ import annotations

import hmac
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.endpoints.game import verify_admin
from app.core.config import settings
from app.core.database_async import get_async_db
from app.models.room import Room, RoomStatus
from app.schemas.admin_update import (
    AdminUpdateCheckResponse,
    AdminUpdateRunRequest,
    AdminUpdateRunResponse,
    AdminUpdateStatusResponse,
)
from app.services.update_agent_client import UpdateAgentClient, UpdateAgentClientError
from app.services.websocket_manager import websocket_manager

router = APIRouter(prefix="/admin/update", tags=["admin-update"])
logger = logging.getLogger(__name__)


def _require_update_enabled() -> None:
    """Raise 503 if update feature is disabled."""
    if not settings.UPDATE_AGENT_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Update feature is disabled. Set UPDATE_AGENT_ENABLED=true in .env to enable.",
        )


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request."""
    try:
        if request.client:
            return request.client.host
    except Exception:
        pass
    return "unknown"


async def _get_update_blocking_reasons(db: AsyncSession) -> list[str]:
    """Check conditions that should block an update.

    Returns:
        List of blocking reason strings. Empty list means update is allowed.
    """
    reasons: list[str] = []

    # Check for active games (rooms in PLAYING status)
    if settings.UPDATE_BLOCK_IF_PLAYING_ROOMS:
        result = await db.execute(
            select(func.count()).select_from(Room).filter(Room.status == RoomStatus.PLAYING)
        )
        playing_count = result.scalar() or 0
        if playing_count > 0:
            reasons.append(
                f"存在进行中对局（rooms.status=playing，count={playing_count}）"
            )

    # Check for active WebSocket connections
    if settings.UPDATE_BLOCK_IF_ACTIVE_GAME_WS:
        ws_count = websocket_manager.get_total_connection_count()
        if ws_count > 0:
            active_games = websocket_manager.get_active_game_ids()
            reasons.append(
                f"存在活跃 WebSocket 连接（count={ws_count}，games={len(active_games)}）"
            )

    return reasons


@router.get("/check", response_model=AdminUpdateCheckResponse)
async def check_update(
    request: Request,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Check if repository updates are available.
    GET /api/admin/update/check

    Security: Admin only (JWT admin token)
    """
    _require_update_enabled()

    actor_id = actor.get("player_id", "unknown")
    client_ip = _get_client_ip(request)

    blocking_reasons = await _get_update_blocking_reasons(db)
    blocked = len(blocking_reasons) > 0

    try:
        client = UpdateAgentClient.from_settings(settings)
    except ValueError as e:
        logger.error(
            "UPDATE_CONFIG_INVALID actor=%s ip=%s error=%s",
            actor_id,
            client_ip,
            str(e),
        )
        raise HTTPException(
            status_code=503,
            detail=f"Update agent configuration error: {str(e)}"
        ) from e

    try:
        agent_check = await client.check()
        agent_status = await client.status(job_id=None)
    except UpdateAgentClientError as e:
        logger.error(
            "UPDATE_CHECK_FAILED actor=%s ip=%s error=%s",
            actor_id,
            client_ip,
            str(e),
        )
        raise HTTPException(status_code=502, detail=str(e)) from e

    logger.info(
        "UPDATE_CHECK actor=%s ip=%s update_available=%s blocked=%s",
        actor_id,
        client_ip,
        agent_check.update_available,
        blocked,
    )

    return AdminUpdateCheckResponse(
        update_available=agent_check.update_available,
        current_revision=agent_check.current_revision,
        remote_revision=agent_check.remote_revision,
        blocked=blocked,
        blocking_reasons=blocking_reasons,
        agent_reachable=True,
        agent_job_running=agent_status.state in ("running", "queued"),
        agent_job_id=agent_status.job_id,
        agent_message=agent_status.message,
    )


@router.post("/run", response_model=AdminUpdateRunResponse, status_code=202)
async def run_update(
    request: Request,
    body: AdminUpdateRunRequest,
    actor: Dict = Depends(verify_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Trigger update via update agent.
    POST /api/admin/update/run

    Security: Admin only (JWT admin token)
    Notes:
    - Update may restart containers; active users will be interrupted in single-instance deployment.
    """
    _require_update_enabled()

    actor_id = actor.get("player_id", "unknown")
    client_ip = _get_client_ip(request)

    blocking_reasons = await _get_update_blocking_reasons(db)
    if blocking_reasons and not body.force:
        logger.warning(
            "UPDATE_BLOCKED actor=%s ip=%s reasons=%s",
            actor_id,
            client_ip,
            "; ".join(blocking_reasons),
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Update blocked due to active users/games. Use force=true to override.",
                "blocking_reasons": blocking_reasons,
            },
        )

    if body.force:
        expected = settings.UPDATE_FORCE_CONFIRM_PHRASE
        provided = (body.confirm_phrase or "").strip()
        if not hmac.compare_digest(provided, expected):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid confirmation phrase. Provide confirm_phrase='{expected}' to force update.",
            )

    try:
        client = UpdateAgentClient.from_settings(settings)
    except ValueError as e:
        logger.error(
            "UPDATE_CONFIG_INVALID actor=%s ip=%s error=%s",
            actor_id,
            client_ip,
            str(e),
        )
        raise HTTPException(
            status_code=503,
            detail=f"Update agent configuration error: {str(e)}"
        ) from e

    try:
        agent_status = await client.status(job_id=None)
        if agent_status.state in ("running", "queued"):
            raise HTTPException(
                status_code=409,
                detail=f"Update agent is busy (job_id={agent_status.job_id}). Try again later.",
            )

        agent_check = await client.check()
        if not agent_check.update_available and not body.force:
            raise HTTPException(
                status_code=409,
                detail="No repository updates available.",
            )

        job_id = await client.run(force=body.force)
    except HTTPException:
        raise
    except UpdateAgentClientError as e:
        logger.error(
            "UPDATE_RUN_FAILED actor=%s ip=%s error=%s",
            actor_id,
            client_ip,
            str(e),
        )
        raise HTTPException(status_code=502, detail=str(e)) from e

    logger.warning(
        "UPDATE_REQUESTED actor=%s ip=%s force=%s job_id=%s",
        actor_id,
        client_ip,
        body.force,
        job_id,
    )

    return AdminUpdateRunResponse(
        status="accepted",
        job_id=job_id,
        message="Update job accepted. Service may restart during deployment.",
    )


@router.get("/status", response_model=AdminUpdateStatusResponse)
async def get_update_status(
    actor: Dict = Depends(verify_admin),
    job_id: Optional[str] = Query(default=None),
):
    """
    Get update agent status (current or by job_id).
    GET /api/admin/update/status?job_id=...

    Security: Admin only (JWT admin token)
    """
    _require_update_enabled()

    client = UpdateAgentClient.from_settings(settings)
    try:
        agent_status = await client.status(job_id=job_id)
    except UpdateAgentClientError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return AdminUpdateStatusResponse(
        job_id=agent_status.job_id,
        state=agent_status.state,
        message=agent_status.message,
        started_at=agent_status.started_at,
        finished_at=agent_status.finished_at,
        current_revision=agent_status.current_revision,
        remote_revision=agent_status.remote_revision,
        last_log_lines=agent_status.last_log_lines,
    )
