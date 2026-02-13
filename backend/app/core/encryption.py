"""
Symmetric encryption utilities for sensitive data at rest.

Uses Fernet (AES-128-CBC with HMAC-SHA256) via the `cryptography` library.
The encryption key is derived from the application's TOKEN_ENCRYPTION_KEY
setting using PBKDF2-HMAC-SHA256 with a fixed salt and 480,000 iterations.

Usage:
    from app.core.encryption import encrypt_value, decrypt_value

    ciphertext = encrypt_value("my-secret-token")
    plaintext  = decrypt_value(ciphertext)

If TOKEN_ENCRYPTION_KEY is not configured, values are stored as plaintext
with a "plain:" prefix to distinguish from encrypted values.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

# Module-level cached Fernet instance
_fernet: Optional[Fernet] = None
_initialized = False

# Prefix markers to distinguish encrypted vs plaintext storage
_ENCRYPTED_PREFIX = "enc:"
_PLAIN_PREFIX = "plain:"


def _get_fernet() -> Optional[Fernet]:
    """
    Lazily initialize Fernet cipher from settings.

    Derives a 32-byte key from TOKEN_ENCRYPTION_KEY using PBKDF2-HMAC-SHA256.
    This is deterministic so the same key always produces the same Fernet key.
    """
    global _fernet, _initialized

    if _initialized:
        return _fernet

    _initialized = True

    try:
        from app.core.config import settings
        key = getattr(settings, "TOKEN_ENCRYPTION_KEY", None)
        if not key:
            logger.warning(
                "TOKEN_ENCRYPTION_KEY not set. OAuth tokens will be stored as plaintext."
            )
            return None

        # Derive a 32-byte key via PBKDF2-HMAC-SHA256 with fixed salt and
        # 480,000 iterations (OWASP 2023 recommendation for SHA-256).
        # The salt is application-scoped (not per-value) because Fernet
        # already includes a unique IV per encryption call.
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"werewolf-ai-token-encryption-v1",
            iterations=480_000,
        )
        derived = kdf.derive(key.encode("utf-8"))
        fernet_key = base64.urlsafe_b64encode(derived)
        _fernet = Fernet(fernet_key)
        return _fernet

    except Exception as e:
        logger.error(f"Failed to initialize encryption: {e}")
        return None


def encrypt_value(plaintext: Optional[str]) -> Optional[str]:
    """
    Encrypt a string value for database storage.

    Returns:
        - None if input is None
        - "enc:<base64-ciphertext>" if encryption key is available
        - "plain:<plaintext>" if no encryption key (development fallback)
    """
    if plaintext is None:
        return None

    fernet = _get_fernet()
    if fernet is None:
        return f"{_PLAIN_PREFIX}{plaintext}"

    ciphertext = fernet.encrypt(plaintext.encode("utf-8"))
    return f"{_ENCRYPTED_PREFIX}{ciphertext.decode('utf-8')}"


def decrypt_value(stored: Optional[str]) -> Optional[str]:
    """
    Decrypt a value retrieved from database storage.

    Handles:
        - None → None
        - "enc:..." → decrypt with Fernet
        - "plain:..." → strip prefix, return plaintext
        - No prefix (legacy) → return as-is
    """
    if stored is None:
        return None

    if stored.startswith(_ENCRYPTED_PREFIX):
        fernet = _get_fernet()
        if fernet is None:
            logger.error(
                "Cannot decrypt value: TOKEN_ENCRYPTION_KEY not configured"
            )
            return None
        try:
            ciphertext = stored[len(_ENCRYPTED_PREFIX):].encode("utf-8")
            return fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken:
            logger.error("Failed to decrypt value: invalid token or wrong key")
            return None

    if stored.startswith(_PLAIN_PREFIX):
        return stored[len(_PLAIN_PREFIX):]

    # Legacy: no prefix, return as-is
    return stored
