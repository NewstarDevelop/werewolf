#!/usr/bin/env python3
"""
Werewolf Update Agent (方案 B：Runner)

目标：
- 提供最小 HTTP 服务：/v1/check /v1/run /v1/status
- /v1/run 不在本进程直接执行更新，而是启动 Runner 容器后台执行：
  1) git fetch + compare（check）
  2) git pull --ff-only + docker compose up -d --build（run）
  3) /v1/status 通过 docker inspect/docker logs 查询 Runner 状态（可跨 update-agent 重启）

安全：
- 强制 Bearer Token 鉴权（UPDATE_AGENT_TOKEN）
- 仅执行白名单序列，不接受任意命令输入
- 需要挂载 /var/run/docker.sock（高权限），务必限制访问范围

Usage:
    export UPDATE_AGENT_TOKEN='your-strong-token'
    export UPDATE_AGENT_REPO_PATH='/path/to/Werewolf'
    python3 update_agent.py
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hmac
import json
import os
import shutil
import subprocess
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


def _utc_now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _read_env(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    if v is None:
        return default or ""
    return v.strip()


class _AgentConfig:
    """Configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.token = _read_env("UPDATE_AGENT_TOKEN")
        self.repo_path = _read_env("UPDATE_AGENT_REPO_PATH")
        self.remote = _read_env("UPDATE_AGENT_REMOTE", "origin")
        self.branch = _read_env("UPDATE_AGENT_BRANCH", "main")
        self.host = _read_env("UPDATE_AGENT_BIND_HOST", "127.0.0.1")
        self.port = int(_read_env("UPDATE_AGENT_BIND_PORT", "9999") or "9999")
        self.keep_log_lines = int(_read_env("UPDATE_AGENT_KEEP_LOG_LINES", "200") or "200")
        self.runner_image = _read_env("UPDATE_AGENT_RUNNER_IMAGE", "werewolf-update-agent")
        self.runner_container_prefix = _read_env("UPDATE_AGENT_RUNNER_CONTAINER_PREFIX", "werewolf-update-runner")
        self.compose_project_name = (
            _read_env("UPDATE_AGENT_COMPOSE_PROJECT_NAME")
            or _read_env("COMPOSE_PROJECT_NAME", "werewolf")
        )
        self.compose_file = _read_env("UPDATE_AGENT_COMPOSE_FILE")
        self.git_set_safe_directory = _read_env("UPDATE_AGENT_GIT_SET_SAFE_DIRECTORY", "false").lower() == "true"
        # CRITICAL: Command timeout to prevent hanging tasks
        self.command_timeout = int(_read_env("UPDATE_AGENT_COMMAND_TIMEOUT", "300") or "300")  # 5 minutes default

    def validate_common(self) -> None:
        if not self.repo_path:
            raise RuntimeError("UPDATE_AGENT_REPO_PATH is required")
        if not os.path.isdir(self.repo_path):
            raise RuntimeError(f"UPDATE_AGENT_REPO_PATH not found: {self.repo_path}")

    def validate_server(self) -> None:
        self.validate_common()
        if not self.token:
            raise RuntimeError("UPDATE_AGENT_TOKEN is required")
        # CRITICAL: Enforce strong token (min 32 chars)
        if len(self.token) < 32:
            raise RuntimeError("UPDATE_AGENT_TOKEN must be at least 32 characters for security")
        # MAJOR FIX: Enforce localhost binding by default for security
        # Docker.sock access = root-equivalent access to host system
        if self.host not in ("127.0.0.1", "localhost", "::1"):
            # Check if explicit override is set
            allow_remote = _read_env("UPDATE_AGENT_ALLOW_REMOTE_BINDING", "false").lower() == "true"
            if not allow_remote:
                raise RuntimeError(
                    f"SECURITY: Refusing to bind to {self.host}. "
                    "Update agent has docker.sock access (root-equivalent). "
                    "Set UPDATE_AGENT_ALLOW_REMOTE_BINDING=true to override (NOT RECOMMENDED)."
                )
            logger.warning(
                "⚠️  SECURITY WARNING: Update Agent binding to %s:%s "
                "with docker.sock access = remote root access! "
                "Ensure firewall/network isolation is properly configured.",
                self.host,
                self.port
            )

    def validate_runner(self) -> None:
        self.validate_common()


CFG = _AgentConfig()


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    """Verify Bearer token authentication."""
    auth = handler.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return False
    provided = auth.split(" ", 1)[1].strip()
    return hmac.compare_digest(provided, CFG.token)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    """Send JSON response."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    """Read JSON from request body."""
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    # CRITICAL: Limit request body size to prevent DoS
    MAX_BODY_SIZE = 1024 * 1024  # 1MB
    if length > MAX_BODY_SIZE:
        raise ValueError(f"Request body too large: {length} bytes (max {MAX_BODY_SIZE})")
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _run_cmd(args: list[str], cwd: str, timeout: int | None = None) -> tuple[int, str]:
    """Run a command and return (returncode, stdout+stderr).

    Args:
        args: Command and arguments
        cwd: Working directory
        timeout: Timeout in seconds (default: use CFG.command_timeout)
    """
    if timeout is None:
        timeout = CFG.command_timeout
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or ""
    except subprocess.TimeoutExpired as e:
        return -1, f"Command timed out after {timeout}s: {' '.join(args)}"


def _ensure_git_safe_directory() -> None:
    """Set git safe.directory using LOCAL config to avoid polluting global config."""
    if not CFG.git_set_safe_directory:
        return
    # CRITICAL FIX: Use --local instead of --global to avoid polluting host's global git config
    _run_cmd(["git", "config", "--local", "--add", "safe.directory", CFG.repo_path], cwd=CFG.repo_path)


def _git(args: list[str]) -> tuple[int, str]:
    """Run git command in repo directory."""
    _ensure_git_safe_directory()
    return _run_cmd(["git", "-C", CFG.repo_path, *args], cwd=CFG.repo_path)


def _detect_compose_cmd() -> list[str]:
    """Detect available docker compose command."""
    if shutil.which("docker"):
        code, _ = _run_cmd(["docker", "compose", "version"], cwd=CFG.repo_path)
        if code == 0:
            return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return []


def _docker(args: list[str]) -> tuple[int, str]:
    """Run docker command (talking to host via /var/run/docker.sock)."""
    return _run_cmd(["docker", *args], cwd=CFG.repo_path)


def _compute_revisions(fetch: bool = True) -> tuple[str | None, str | None, bool, str | None]:
    """Fetch and compare local vs remote revisions.

    Returns:
        (current_revision, remote_revision, update_available, error_message)
    """
    # CRITICAL: Validate remote/branch to prevent git parameter injection
    if CFG.remote.startswith("-") or CFG.branch.startswith("-"):
        return None, None, False, "Invalid remote or branch name (cannot start with '-')"

    if fetch:
        # Use -- to separate options from arguments
        code, out = _git(["fetch", "--", CFG.remote, CFG.branch])
        if code != 0:
            return None, None, False, out.strip()[-4000:]

    code, head = _git(["rev-parse", "HEAD"])
    if code != 0:
        return None, None, False, head.strip()[-4000:]
    current = head.strip()

    code, remote_head = _git(["rev-parse", f"{CFG.remote}/{CFG.branch}"])
    if code != 0:
        return current, None, False, remote_head.strip()[-4000:]
    remote = remote_head.strip()

    return current, remote, current != remote, None


def _runner_container_name(job_id: str) -> str:
    return f"{CFG.runner_container_prefix}-{job_id}"


# Fixed runner name for atomic mutual exclusion
FIXED_RUNNER_NAME = "werewolf-update-runner"


def _list_runner_containers(all_containers: bool) -> list[tuple[str, str]]:
    """List runner containers with creation time.

    Returns:
        List of (container_name, created_at) tuples, sorted by creation time descending (newest first).
    """
    args = ["ps"]
    if all_containers:
        args.append("-a")
    args += [
        "--filter",
        "label=werewolf.update.runner=true",
        "--format",
        "{{.Names}}\t{{.CreatedAt}}",
    ]
    code, out = _docker(args)
    if code != 0:
        return []
    containers = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        name = parts[0].strip()
        created = parts[1].strip() if len(parts) > 1 else ""
        containers.append((name, created))
    # Sort by created time descending (newest first)
    # Format: "2026-01-21 12:00:00 +0000 UTC" - lexicographic sort works
    containers.sort(key=lambda x: x[1], reverse=True)
    return containers


def _cleanup_old_runners(keep: int = 3) -> None:
    """Remove old exited runner containers, keeping the most recent ones.

    Args:
        keep: Number of recent containers to keep.
    """
    containers = _list_runner_containers(all_containers=True)
    # Filter to only exited containers
    exited = []
    for name, _ in containers:
        inspect = _inspect_container(name)
        if inspect:
            state = inspect.get("State") or {}
            if not state.get("Running") and state.get("Status") != "created":
                exited.append(name)
    # Remove old ones beyond keep limit
    for name in exited[keep:]:
        _docker(["rm", "-f", name])


def _inspect_container(container_name: str) -> dict | None:
    code, out = _docker(["inspect", container_name])
    if code != 0:
        return None
    try:
        data = json.loads(out)
        if isinstance(data, list) and data:
            return data[0]
    except Exception:
        return None
    return None


def _docker_logs_tail(container_name: str, tail: int) -> list[str]:
    code, out = _docker(["logs", "--tail", str(int(tail)), container_name])
    if code != 0:
        return []
    lines = [x.rstrip("\n") for x in out.splitlines() if x.strip()]
    return lines[-tail:]


def _normalize_rfc3339(ts: str | None) -> str | None:
    if not ts:
        return None
    if ts.startswith("0001-01-01"):
        return None
    return ts


def _status_from_inspect(inspect: dict) -> tuple[str, str | None, str | None, str | None]:
    state = inspect.get("State") or {}
    status = (state.get("Status") or "").lower()
    started_at = _normalize_rfc3339(state.get("StartedAt"))
    finished_at = _normalize_rfc3339(state.get("FinishedAt"))

    if status in ("created", "restarting"):
        return "queued", None, started_at, finished_at
    if state.get("Running"):
        return "running", None, started_at, finished_at

    exit_code = state.get("ExitCode")
    err = (state.get("Error") or "").strip() or None
    if exit_code == 0:
        return "success", err, started_at, finished_at
    return "error", err, started_at, finished_at


def _start_runner_container(force: bool) -> str:
    """Start a runner container to execute the update.

    Uses a fixed container name for atomic mutual exclusion.
    docker run --name will fail if a container with the same name exists.

    Returns:
        job_id of the started runner.

    Raises:
        RuntimeError: If runner is already running or docker run fails.
    """
    job_id = str(uuid.uuid4())

    # Clean up old exited runners first
    _cleanup_old_runners(keep=3)

    # Check if fixed runner exists
    inspect = _inspect_container(FIXED_RUNNER_NAME)
    if inspect:
        state = inspect.get("State") or {}
        if state.get("Running"):
            # Runner is currently running
            labels = (inspect.get("Config") or {}).get("Labels") or {}
            existing_job_id = labels.get("werewolf.update.job_id", "unknown")
            raise RuntimeError(f"Update already running (job_id={existing_job_id})")
        # Container exists but not running - remove it first
        _docker(["rm", "-f", FIXED_RUNNER_NAME])

    args: list[str] = [
        "run",
        "-d",
        "--name",
        FIXED_RUNNER_NAME,
        "--label",
        "werewolf.update.runner=true",
        "--label",
        f"werewolf.update.job_id={job_id}",
        "--volume",
        "/var/run/docker.sock:/var/run/docker.sock",
        "--volume",
        f"{CFG.repo_path}:{CFG.repo_path}",
        "--workdir",
        CFG.repo_path,
        "--env",
        f"UPDATE_AGENT_REPO_PATH={CFG.repo_path}",
        "--env",
        f"UPDATE_AGENT_REMOTE={CFG.remote}",
        "--env",
        f"UPDATE_AGENT_BRANCH={CFG.branch}",
        "--env",
        f"UPDATE_AGENT_COMPOSE_PROJECT_NAME={CFG.compose_project_name}",
        "--env",
        f"UPDATE_AGENT_GIT_SET_SAFE_DIRECTORY={'true' if CFG.git_set_safe_directory else 'false'}",
    ]
    if CFG.compose_file:
        args += ["--env", f"UPDATE_AGENT_COMPOSE_FILE={CFG.compose_file}"]

    # Note: The runner image uses ENTRYPOINT ["python3", "/app/update_agent.py"]
    # so we only need to pass the mode argument, not the full command
    args += [CFG.runner_image, "runner"]
    if force:
        args.append("--force")

    code, out = _docker(args)
    if code != 0:
        error_msg = out.strip()[-2000:] or "docker run failed"
        # Check if name conflict (another request won the race)
        if "is already in use" in error_msg or "Conflict" in error_msg:
            raise RuntimeError("Update already running (race condition)")
        raise RuntimeError(error_msg)

    return job_id


def _runner_main(force: bool) -> int:
    CFG.validate_runner()

    print(f"[runner] repo={CFG.repo_path} remote={CFG.remote} branch={CFG.branch}", flush=True)

    cur, remote, available, err = _compute_revisions(fetch=True)
    if err:
        print(f"[check] {err}", flush=True)
        return 2

    print(f"[check] current={cur} remote={remote} update_available={available}", flush=True)
    if not available and not force:
        print("[runner] Already up to date", flush=True)
        return 0

    print("[git] pull --ff-only", flush=True)
    code, out = _git(["pull", CFG.remote, CFG.branch, "--ff-only"])
    if out.strip():
        for line in out.splitlines():
            print(f"[git] {line}", flush=True)
    if code != 0:
        print("[git] pull failed", flush=True)
        return 1

    compose = _detect_compose_cmd()
    if not compose:
        print("[docker] docker compose/docker-compose not found", flush=True)
        return 1

    compose_file = CFG.compose_file or os.path.join(CFG.repo_path, "docker-compose.yml")
    project_name = CFG.compose_project_name

    cmd: list[str] = []
    if compose == ["docker", "compose"]:
        cmd = [
            *compose,
            "-f",
            compose_file,
            "-p",
            project_name,
            "--project-directory",
            CFG.repo_path,
            "up",
            "-d",
            "--build",
        ]
    else:
        cmd = [
            *compose,
            "-f",
            compose_file,
            "-p",
            project_name,
            "up",
            "-d",
            "--build",
        ]

    print("[docker] " + " ".join(cmd), flush=True)
    code, out = _run_cmd(cmd, cwd=CFG.repo_path)
    if out.strip():
        for line in out.splitlines():
            print(f"[docker] {line}", flush=True)
    if code != 0:
        print("[docker] compose up failed", flush=True)
        return 1

    cur2, remote2, available2, err2 = _compute_revisions(fetch=False)
    if err2:
        print(f"[post-check] {err2}", flush=True)
    print(f"[post-check] current={cur2} remote={remote2} update_available={available2}", flush=True)
    return 0


class UpdateAgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for update agent API."""

    server_version = "WerewolfUpdateAgent/1.0"

    def do_GET(self) -> None:
        if not _check_auth(self):
            _json_response(self, HTTPStatus.UNAUTHORIZED, {"detail": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        if parsed.path == "/v1/check":
            cur, remote, available, err = _compute_revisions(fetch=True)
            if err:
                _json_response(self, HTTPStatus.BAD_GATEWAY, {"detail": "git check failed"})
                return
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "update_available": bool(available),
                    "current_revision": cur,
                    "remote_revision": remote,
                },
            )
            return

        if parsed.path == "/v1/status":
            qs = parse_qs(parsed.query or "")
            job_id = qs.get("job_id", [None])[0]

            # Always check the fixed runner name (single-task model)
            container_name = FIXED_RUNNER_NAME

            # Check if docker is available
            if not shutil.which("docker"):
                _json_response(
                    self,
                    HTTPStatus.BAD_GATEWAY,
                    {
                        "job_id": None,
                        "state": "error",
                        "message": "docker CLI not found",
                        "started_at": None,
                        "finished_at": None,
                        "current_revision": None,
                        "remote_revision": None,
                        "last_log_lines": [],
                    },
                )
                return

            inspect = _inspect_container(container_name)
            if not inspect:
                # No runner container exists - system is idle
                cur, remote, _, _ = _compute_revisions(fetch=False)
                _json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "job_id": None,
                        "state": "idle",
                        "message": None,
                        "started_at": None,
                        "finished_at": None,
                        "current_revision": cur,
                        "remote_revision": remote,
                        "last_log_lines": [],
                    },
                )
                return

            labels = (inspect.get("Config") or {}).get("Labels") or {}
            job_id_from_label = labels.get("werewolf.update.job_id")
            state, err, started_at, finished_at = _status_from_inspect(inspect)
            logs = _docker_logs_tail(container_name, CFG.keep_log_lines)
            cur, remote, _, _ = _compute_revisions(fetch=False)

            message = err or f"runner={container_name}"
            _json_response(
                self,
                HTTPStatus.OK,
                {
                    "job_id": job_id_from_label or job_id,
                    "state": state,
                    "message": message,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "current_revision": cur,
                    "remote_revision": remote,
                    "last_log_lines": logs[-CFG.keep_log_lines:],
                },
            )
            return

        _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "Not found"})

    def do_POST(self) -> None:
        if not _check_auth(self):
            _json_response(self, HTTPStatus.UNAUTHORIZED, {"detail": "Unauthorized"})
            return

        parsed = urlparse(self.path)
        if parsed.path != "/v1/run":
            _json_response(self, HTTPStatus.NOT_FOUND, {"detail": "Not found"})
            return

        payload = _read_json(self)
        force = bool(payload.get("force", False))

        if not shutil.which("docker"):
            _json_response(self, HTTPStatus.BAD_GATEWAY, {"detail": "docker CLI not found"})
            return

        try:
            job_id = _start_runner_container(force=force)
        except Exception as e:
            msg = str(e) or type(e).__name__
            if "Update already running" in msg:
                _json_response(self, HTTPStatus.CONFLICT, {"detail": msg})
                return
            _json_response(self, HTTPStatus.BAD_GATEWAY, {"detail": msg})
            return

        _json_response(self, HTTPStatus.ACCEPTED, {"job_id": job_id})

    def log_message(self, fmt: str, *args) -> None:
        """Log request without sensitive headers."""
        msg = fmt % args
        print(f"[{_utc_now_iso()}] {self.client_address[0]} {self.command} {self.path} {msg}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="update_agent.py")
    sub = p.add_subparsers(dest="mode")

    sub.add_parser("serve")

    r = sub.add_parser("runner")
    r.add_argument("--force", action="store_true", help="Force update even if no remote changes detected")

    args = p.parse_args()
    if not args.mode:
        args.mode = "serve"
    return args


def _serve_main() -> None:
    print(f"[config] repo_path={CFG.repo_path or '(not set)'}", flush=True)
    print(f"[config] token={'(set)' if CFG.token else '(NOT SET)'}", flush=True)
    print(f"[config] remote={CFG.remote} branch={CFG.branch}", flush=True)

    CFG.validate_server()
    httpd = ThreadingHTTPServer((CFG.host, CFG.port), UpdateAgentHandler)
    print(f"Update Agent listening on http://{CFG.host}:{CFG.port}", flush=True)
    print(f"Repository path: {CFG.repo_path}", flush=True)
    print(f"Remote: {CFG.remote}/{CFG.branch}", flush=True)
    print(f"Runner image: {CFG.runner_image}", flush=True)
    print(f"Compose project: {CFG.compose_project_name}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    import sys
    import traceback

    print("=" * 44, flush=True)
    print("Werewolf Update Agent Starting", flush=True)
    print("=" * 44, flush=True)

    try:
        a = _parse_args()
        if a.mode == "runner":
            raise SystemExit(_runner_main(force=bool(getattr(a, "force", False))))
        _serve_main()
    except Exception as e:
        print(f"[FATAL] Failed to start update agent: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        raise SystemExit(1)
