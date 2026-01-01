"""Security utilities for password hashing and verification."""
import bcrypt
import secrets
import hashlib


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hash string
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to verify against

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def generate_random_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Number of bytes (token will be URL-safe base64 encoded)

    Returns:
        Random URL-safe token string
    """
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256.

    Args:
        token: Token to hash

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
