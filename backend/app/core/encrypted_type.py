"""
SQLAlchemy TypeDecorator for transparent column-level encryption.

Encrypts values on write, decrypts on read — the application sees plaintext
while the database stores ciphertext.

Usage in models:
    from app.core.encrypted_type import EncryptedString

    class OAuthAccount(Base):
        access_token = Column(EncryptedString(512), nullable=True)
"""
from __future__ import annotations

from sqlalchemy import String, TypeDecorator

from app.core.encryption import decrypt_value, encrypt_value


class EncryptedString(TypeDecorator):
    """A String column that transparently encrypts/decrypts values."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypt before writing to DB."""
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        """Decrypt after reading from DB."""
        if value is None:
            return None
        return decrypt_value(value)
