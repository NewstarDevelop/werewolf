"""Admin configuration management endpoints."""

from __future__ import annotations

import logging
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.api.endpoints.game import verify_admin
from app.schemas.config_env import EnvVarResponse, EnvUpdateRequest, EnvUpdateResult
from app.services.env_file_manager import (
    EnvFileManager,
    EnvFileNotFoundError,
    EnvFilePermissionError,
    EnvFileConcurrentUpdateError,
    EnvFileValidationError,
    EnvFileError,
)

router = APIRouter(prefix="/config", tags=["config"])
logger = logging.getLogger(__name__)

_env_manager = EnvFileManager()


def _require_env_management_enabled() -> None:
    if settings.DEBUG:
        return
    if not getattr(settings, "ENV_MANAGEMENT_ENABLED", False):
        raise HTTPException(
            status_code=403,
            detail="Env management is disabled. Set ENV_MANAGEMENT_ENABLED=true to enable.",
        )


@router.get("/env", response_model=List[EnvVarResponse])
async def get_env_vars(
    _: Dict = Depends(verify_admin),
):
    """
    Get all environment variables from .env file.
    GET /api/config/env

    Security: Admin only (JWT admin or X-Admin-Key)
    Sensitive variables return value=null
    """
    _require_env_management_enabled()

    try:
        env_path, env = await run_in_threadpool(_env_manager.read_env)
    except EnvFileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except EnvFilePermissionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except EnvFileError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    items: list[EnvVarResponse] = []
    for name in sorted(env.keys()):
        value = env.get(name, "")
        is_sensitive = _env_manager.is_sensitive_key(name)
        is_set = bool(value)
        items.append(
            EnvVarResponse(
                name=name,
                value=None if is_sensitive else value,
                is_sensitive=is_sensitive,
                is_set=is_set,
                source="env_file",
            )
        )
    return items


@router.put("/env", response_model=EnvUpdateResult)
async def put_env_vars(
    request: Request,
    body: EnvUpdateRequest,
    actor: Dict = Depends(verify_admin),
):
    """
    Update environment variables in .env file.
    PUT /api/config/env

    Security: Admin only (JWT admin or X-Admin-Key)
    Sensitive variables require confirm_sensitive=true
    All changes require server restart to take effect
    """
    _require_env_management_enabled()

    # Enforce sensitive update confirmation (server-side hard requirement)
    for u in body.updates:
        if u.action == "set" and _env_manager.is_sensitive_key(u.name):
            if not u.confirm_sensitive:
                raise HTTPException(
                    status_code=400,
                    detail=f"confirm_sensitive is required when setting sensitive key: {u.name}",
                )

    try:
        env_path, results, changed = await run_in_threadpool(
            _env_manager.apply_updates,
            updates=body.updates,
        )
    except EnvFileConcurrentUpdateError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except EnvFileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except EnvFileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except EnvFilePermissionError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except EnvFileError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Audit log (no secret values)
    client_ip: Optional[str] = None
    try:
        if request.client:
            client_ip = request.client.host
    except Exception:
        client_ip = None

    for r in results:
        if r.status in ("created", "updated", "deleted"):
            logger.info(
                "ENV_AUDIT %s",
                _env_manager.build_audit_log(
                    actor=actor,
                    key=r.name,
                    action=r.action,
                    env_path=env_path,
                    client_ip=client_ip,
                ),
            )

    return EnvUpdateResult(
        success=True,
        results=results,
        restart_required=bool(changed),
        env_file_path=str(env_path),
    )
