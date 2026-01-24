"""Client for Update Agent (方案 B: 更新代理)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)


class UpdateAgentClientError(RuntimeError):
    """Exception raised when update agent communication fails."""

    pass


@dataclass(frozen=True)
class UpdateAgentCheckResult:
    """Result from update agent check endpoint."""

    update_available: bool
    current_revision: Optional[str] = None
    remote_revision: Optional[str] = None


@dataclass(frozen=True)
class UpdateAgentStatusResult:
    """Result from update agent status endpoint."""

    job_id: Optional[str] = None
    state: str = "idle"
    message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    current_revision: Optional[str] = None
    remote_revision: Optional[str] = None
    last_log_lines: list[str] = field(default_factory=list)


class UpdateAgentClient:
    """HTTP client for communicating with the update agent service."""

    def __init__(
        self, base_url: str, token: str, timeout_seconds: float = 3.0
    ) -> None:
        # MAJOR FIX: Validate base_url to prevent token leakage
        self._validate_base_url(base_url)
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds

    @staticmethod
    def _validate_base_url(url: str) -> None:
        """Validate base_url to prevent security issues.

        Only allows localhost addresses to prevent SSRF and token leakage.

        Raises:
            ValueError: If URL is not a valid localhost address
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid UPDATE_AGENT_URL: {url}. Failed to parse: {e}")

        # Enforce scheme is http or https only
        if parsed.scheme not in ["http", "https"]:
            raise ValueError(
                f"Invalid UPDATE_AGENT_URL: {url}. "
                f"Scheme must be 'http' or 'https', got '{parsed.scheme}'."
            )

        # Reject URLs with userinfo (username:password@host)
        if parsed.username or parsed.password:
            raise ValueError(
                f"Invalid UPDATE_AGENT_URL: {url}. "
                "URLs with credentials are not allowed."
            )

        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Invalid UPDATE_AGENT_URL: {url}. Missing hostname.")

        hostname_lower = hostname.lower()

        # SECURITY: Only allow localhost/loopback addresses (exact match)
        # This prevents SSRF attacks and token leakage to external servers
        if hostname_lower not in ["127.0.0.1", "localhost", "::1", "0.0.0.0"]:
            raise ValueError(
                f"Invalid UPDATE_AGENT_URL: {url}. "
                f"Only localhost addresses are allowed (127.0.0.1, localhost, ::1, 0.0.0.0), got '{hostname}'."
            )

        logger.info(f"Update agent URL validated: {url}")

    @classmethod
    def from_settings(cls, settings: "Settings") -> "UpdateAgentClient":
        """Create client from application settings."""
        return cls(
            base_url=settings.UPDATE_AGENT_URL,
            token=settings.UPDATE_AGENT_TOKEN,
            timeout_seconds=settings.UPDATE_AGENT_TIMEOUT_SECONDS,
        )

    def _headers(self) -> dict[str, str]:
        """Build request headers with authentication."""
        return {"Authorization": f"Bearer {self._token}"}

    async def check(self) -> UpdateAgentCheckResult:
        """Check if updates are available.

        Calls GET /v1/check on the update agent.

        Returns:
            UpdateAgentCheckResult with update availability info.

        Raises:
            UpdateAgentClientError: If agent is unreachable or returns error.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/v1/check",
                    headers=self._headers(),
                )
        except Exception as e:
            logger.error(f"Update agent check failed: {type(e).__name__}: {e}")
            raise UpdateAgentClientError(
                f"Update agent unreachable: {type(e).__name__}"
            ) from e

        if resp.status_code == 401:
            raise UpdateAgentClientError(
                "Update agent authentication failed (401). Check UPDATE_AGENT_TOKEN."
            )
        if resp.status_code >= 400:
            raise UpdateAgentClientError(f"Update agent error ({resp.status_code}).")

        data = resp.json()
        return UpdateAgentCheckResult(
            update_available=bool(data.get("update_available", False)),
            current_revision=data.get("current_revision"),
            remote_revision=data.get("remote_revision"),
        )

    async def run(self, force: bool = False) -> str:
        """Trigger an update job.

        Calls POST /v1/run on the update agent.

        Args:
            force: Whether to force update even if no changes detected.

        Returns:
            Job ID of the started update job.

        Raises:
            UpdateAgentClientError: If agent is unreachable or returns error.
        """
        payload = {"force": bool(force)}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/run",
                    headers={**self._headers(), "Content-Type": "application/json"},
                    json=payload,
                )
        except Exception as e:
            logger.error(f"Update agent run failed: {type(e).__name__}: {e}")
            raise UpdateAgentClientError(
                f"Update agent unreachable: {type(e).__name__}"
            ) from e

        if resp.status_code == 401:
            raise UpdateAgentClientError(
                "Update agent authentication failed (401). Check UPDATE_AGENT_TOKEN."
            )
        if resp.status_code == 409:
            detail = None
            if resp.headers.get("content-type", "").startswith("application/json"):
                detail = resp.json().get("detail")
            raise UpdateAgentClientError(
                f"Update agent busy/conflict (409). {detail or ''}".strip()
            )
        if resp.status_code >= 400:
            raise UpdateAgentClientError(f"Update agent error ({resp.status_code}).")

        data = resp.json()
        job_id = data.get("job_id")
        if not job_id:
            raise UpdateAgentClientError("Update agent response missing job_id.")
        return str(job_id)

    async def status(self, job_id: Optional[str] = None) -> UpdateAgentStatusResult:
        """Get update job status.

        Calls GET /v1/status on the update agent.

        Args:
            job_id: Optional job ID to query. If None, returns current/latest job status.

        Returns:
            UpdateAgentStatusResult with job status info.

        Raises:
            UpdateAgentClientError: If agent is unreachable or returns error.
        """
        params = {}
        if job_id:
            params["job_id"] = job_id

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/v1/status",
                    headers=self._headers(),
                    params=params,
                )
        except Exception as e:
            logger.error(f"Update agent status failed: {type(e).__name__}: {e}")
            raise UpdateAgentClientError(
                f"Update agent unreachable: {type(e).__name__}"
            ) from e

        if resp.status_code == 401:
            raise UpdateAgentClientError(
                "Update agent authentication failed (401). Check UPDATE_AGENT_TOKEN."
            )
        if resp.status_code >= 400:
            raise UpdateAgentClientError(f"Update agent error ({resp.status_code}).")

        data = resp.json()
        lines = data.get("last_log_lines") or []
        if not isinstance(lines, list):
            lines = []

        return UpdateAgentStatusResult(
            job_id=data.get("job_id"),
            state=data.get("state", "idle"),
            message=data.get("message"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            current_revision=data.get("current_revision"),
            remote_revision=data.get("remote_revision"),
            last_log_lines=[str(x) for x in lines][-200:],
        )
