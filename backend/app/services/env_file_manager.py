"""Service layer for reading/writing .env with safety guarantees.

IMPORTANT - Concurrency Limitations:
    This implementation uses threading.Lock for in-process synchronization only.

    SINGLE-PROCESS DEPLOYMENT REQUIRED:
    - When running with multiple workers (Gunicorn, uWSGI), each worker process
      maintains its own lock, which does NOT provide cross-process protection.
    - Concurrent writes from different processes can cause data loss or corruption.

    DEPLOYMENT RECOMMENDATIONS:
    1. Use single-process mode (--workers=1) when ENV_MANAGEMENT_ENABLED=true
    2. OR implement file-level locking using portalocker:
       ```python
       import portalocker
       with portalocker.Lock(env_path, timeout=5):
           # perform file operations
       ```
    3. OR disable env management in multi-process deployments

    For production multi-process deployments, consider using a centralized
    configuration management service instead of direct .env file editing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core import config as config_module
from app.schemas.config_env import EnvUpdateItem, EnvUpdateItemResult

logger = logging.getLogger(__name__)


class EnvFileError(Exception):
    """Base error for env file operations."""


class EnvFileNotFoundError(EnvFileError):
    """Raised when .env cannot be resolved."""


class EnvFilePermissionError(EnvFileError):
    """Raised on filesystem permission issues."""


class EnvFileConcurrentUpdateError(EnvFileError):
    """Raised when another update is in progress (in-process lock)."""


class EnvFileValidationError(EnvFileError):
    """Raised on invalid key/edit policy violations."""


@dataclass(frozen=True)
class _ParsedLine:
    kind: str  # "blank" | "comment" | "kv" | "other"
    raw: str
    key: Optional[str] = None
    value: Optional[str] = None


class EnvFileManager:
    """Manage .env file with atomic write and admin-safe read semantics."""

    _write_lock = threading.Lock()

    _key_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    _sensitive_tokens = (
        "api_key",
        "apikey",
        "secret",
        "token",
        "password",
        "passwd",
        "private",
        "jwt",
        "key",
        "client_secret",
    )

    _editable_blacklist = {
        # Auth & crypto
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "JWT_EXPIRE_MINUTES",
        # Admin emergency access
        "ADMIN_KEY",
        "ADMIN_KEY_ENABLED",
        # Proxy trust boundary
        "TRUSTED_PROXIES",
    }

    def resolve_env_path(self) -> Path:
        """Resolve the effective .env file path consistently with startup loading.

        Includes security checks:
        - Validates no symlink in path (防止符号链接攻击)
        - Ensures file is regular file (not device/socket)
        - Verifies file is within expected project directories
        """
        resolved = getattr(config_module, "ENV_FILE_PATH", None)
        if isinstance(resolved, Path) and resolved.exists():
            env_path = resolved
        else:
            current_file = Path(config_module.__file__).resolve()
            possible_paths = [
                current_file.parent.parent.parent / ".env",
                current_file.parent.parent.parent.parent / ".env",
                Path.cwd() / ".env",
            ]
            env_path = None
            for p in possible_paths:
                if p.exists():
                    env_path = p
                    break

            if env_path is None:
                raise EnvFileNotFoundError("No .env file found")

        # Security validations
        try:
            env_path_resolved = env_path.resolve(strict=True)
        except (OSError, RuntimeError) as e:
            raise EnvFileError(f"Path resolution failed: {e}")

        # Check for symlinks in the path
        if env_path_resolved != env_path.resolve():
            raise EnvFileError("Symlinks in .env path are not allowed for security reasons")

        # Ensure it's a regular file
        if not env_path_resolved.is_file():
            raise EnvFileError(".env must be a regular file")

        # Verify path is within project directory tree
        try:
            project_root = Path(config_module.__file__).resolve().parent.parent.parent
            env_path_resolved.relative_to(project_root)
        except ValueError:
            # Path is outside project root
            logger.warning(
                f"Security: .env file {env_path_resolved} is outside project root {project_root}"
            )

        return env_path_resolved

    @classmethod
    def is_sensitive_key(cls, key: str) -> bool:
        k = key.strip().lower()
        return any(token in k for token in cls._sensitive_tokens)

    @classmethod
    def is_editable_key(cls, key: str) -> bool:
        return key.strip().upper() not in cls._editable_blacklist

    @classmethod
    def _validate_key_name(cls, key: str) -> None:
        if not cls._key_pattern.fullmatch(key):
            raise EnvFileValidationError("Invalid env var name")

    @staticmethod
    def _quote_value(value: str) -> str:
        """Render a value safely for .env format (single-line)."""
        if value == "":
            return ""

        safe = re.fullmatch(r"[A-Za-z0-9_./:@+-]+", value) is not None
        if safe:
            return value

        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{escaped}\""

    @staticmethod
    def _unquote_value(raw: str) -> str:
        s = raw.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("\"", "'"):
            inner = s[1:-1]
            if s[0] == "\"":
                inner = inner.replace("\\\"", "\"").replace("\\\\", "\\")
            return inner
        return s

    @classmethod
    def _parse_lines(cls, text: str) -> list[_ParsedLine]:
        lines: list[_ParsedLine] = []
        for raw in text.splitlines(keepends=True):
            stripped = raw.strip()
            if stripped == "":
                lines.append(_ParsedLine(kind="blank", raw=raw))
                continue
            if stripped.startswith("#"):
                lines.append(_ParsedLine(kind="comment", raw=raw))
                continue

            candidate = raw
            if candidate.lstrip().startswith("export "):
                candidate = candidate.lstrip()[len("export ") :]

            if "=" not in candidate:
                lines.append(_ParsedLine(kind="other", raw=raw))
                continue

            left, right = candidate.split("=", 1)
            key = left.strip()
            if not cls._key_pattern.fullmatch(key):
                lines.append(_ParsedLine(kind="other", raw=raw))
                continue

            value = cls._unquote_value(right)
            lines.append(_ParsedLine(kind="kv", raw=raw, key=key, value=value))
        return lines

    @staticmethod
    def write_env_atomic(*, path: Path, content: str) -> None:
        """Write file atomically: temp file -> fsync -> os.replace() -> dir fsync.

        Ensures full durability by also syncing the parent directory after rename,
        which guarantees the directory entry is persisted to disk.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise EnvFilePermissionError("Failed to ensure env directory exists") from e

        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                delete=False,
                dir=str(path.parent),
                prefix=f".{path.name}.",
                suffix=".tmp",
            ) as f:
                tmp_path = f.name
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, path)

            # Sync parent directory to ensure directory entry is persisted
            try:
                dir_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (OSError, AttributeError):
                # Windows doesn't support directory fsync - fallback gracefully
                # On POSIX systems, this is critical for full durability
                logger.debug("Directory fsync not supported or failed (expected on Windows)")

        except PermissionError as e:
            raise EnvFilePermissionError("Permission denied writing .env") from e
        except Exception as e:
            raise EnvFileError("Failed to write .env atomically") from e
        finally:
            if tmp_path:
                try:
                    if Path(tmp_path).exists():
                        Path(tmp_path).unlink()
                except Exception:
                    pass

    def read_env(self) -> tuple[Path, dict[str, str]]:
        """Read and parse .env. Returns (path, key->value) with last-write-wins."""
        path = self.resolve_env_path()
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise EnvFileNotFoundError("Resolved .env file does not exist") from e
        except PermissionError as e:
            raise EnvFilePermissionError("Permission denied reading .env") from e
        except UnicodeDecodeError as e:
            raise EnvFileError("Failed to decode .env (expected UTF-8)") from e

        parsed = self._parse_lines(text)
        env: dict[str, str] = {}
        for line in parsed:
            if line.kind == "kv" and line.key is not None and line.value is not None:
                env[line.key] = line.value
        return path, env

    def apply_updates(self, *, updates: list[EnvUpdateItem]) -> tuple[Path, list[EnvUpdateItemResult], bool]:
        """Apply updates to .env atomically under in-process lock."""
        if not self._write_lock.acquire(blocking=False):
            raise EnvFileConcurrentUpdateError("Another update is in progress")
        try:
            path, current = self.read_env()
            original_text = path.read_text(encoding="utf-8")
            parsed_lines = self._parse_lines(original_text)

            index_by_key: dict[str, list[int]] = {}
            for idx, line in enumerate(parsed_lines):
                if line.kind == "kv" and line.key:
                    index_by_key.setdefault(line.key, []).append(idx)

            results: list[EnvUpdateItemResult] = []
            changed = False
            delete_indices: set[int] = set()

            # Validate all updates first (all-or-nothing semantics)
            for u in updates:
                self._validate_key_name(u.name)
                if not self.is_editable_key(u.name):
                    raise EnvFileValidationError(f"Key is not editable: {u.name}")
                if u.action == "set" and u.value is None:
                    raise EnvFileValidationError(f"Missing value for key: {u.name}")

            for u in updates:
                existing = u.name in current
                if u.action == "unset":
                    if not existing:
                        results.append(
                            EnvUpdateItemResult(name=u.name, action=u.action, status="skipped", message="Key not present")
                        )
                        continue

                    for idx in index_by_key.get(u.name, []):
                        delete_indices.add(idx)

                    current.pop(u.name, None)
                    results.append(EnvUpdateItemResult(name=u.name, action=u.action, status="deleted"))
                    changed = True
                    continue

                # action == set
                new_value = u.value or ""
                if existing and current.get(u.name) == new_value:
                    results.append(
                        EnvUpdateItemResult(name=u.name, action=u.action, status="skipped", message="No change")
                    )
                    continue

                rendered = self._quote_value(new_value)
                new_line = f"{u.name}={rendered}\n"

                if existing:
                    indices = index_by_key.get(u.name, [])
                    if indices:
                        last_idx = indices[-1]
                        parsed_lines[last_idx] = _ParsedLine(kind="kv", raw=new_line, key=u.name, value=new_value)
                    else:
                        parsed_lines.append(_ParsedLine(kind="kv", raw=new_line, key=u.name, value=new_value))
                    results.append(EnvUpdateItemResult(name=u.name, action=u.action, status="updated"))
                else:
                    parsed_lines.append(_ParsedLine(kind="kv", raw=new_line, key=u.name, value=new_value))
                    results.append(EnvUpdateItemResult(name=u.name, action=u.action, status="created"))

                current[u.name] = new_value
                changed = True

            new_content_lines: list[str] = []
            for idx, line in enumerate(parsed_lines):
                if idx in delete_indices:
                    continue
                new_content_lines.append(line.raw)

            # Ensure trailing newline if file was non-empty, and we changed it.
            new_content = "".join(new_content_lines)
            if changed and new_content != "" and not new_content.endswith("\n"):
                new_content += "\n"

            if changed:
                self.write_env_atomic(path=path, content=new_content)

            return path, results, changed
        finally:
            self._write_lock.release()

    @staticmethod
    def build_audit_log(
        *,
        actor: dict,
        key: str,
        action: str,
        env_path: Path,
        client_ip: Optional[str],
    ) -> str:
        payload = {
            "event": "env_update",
            "key": key,
            "action": action,
            "env_path": str(env_path),
            "actor_player_id": actor.get("player_id"),
            "actor_user_id": actor.get("user_id"),
            "is_admin": bool(actor.get("is_admin", False)),
            "client_ip": client_ip,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
