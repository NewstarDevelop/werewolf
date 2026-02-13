"""User authentication and profile models."""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, UniqueConstraint, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
from datetime import datetime, timezone

from .base import Base
from app.core.encrypted_type import EncryptedString


class User(Base):
    """用户模型 - 存储用户账户信息"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)  # UUID
    email = Column(String(255), unique=True, nullable=True, index=True)  # 邮箱（OAuth用户可为空）
    password_hash = Column(String(128), nullable=True)  # bcrypt hash（OAuth用户为空）
    nickname = Column(String(50), unique=True, nullable=False)  # 昵称（唯一，unique自带索引）
    avatar_url = Column(String(512), nullable=True)  # 头像URL
    bio = Column(String(500), nullable=True)  # 个人简介
    is_active = Column(Boolean, default=True, nullable=False)  # 是否激活
    is_email_verified = Column(Boolean, default=False, nullable=False)  # 邮箱是否验证
    is_admin = Column(Boolean, default=False, nullable=False)  # 是否管理员
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    last_login_at = Column(DateTime, nullable=True)  # 最后登录时间
    preferences = Column(MutableDict.as_mutable(JSON), nullable=False, default=dict, server_default='{}')  # 用户偏好设置

    # Relationships
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    game_participations = relationship("GameParticipant", back_populates="user")


class OAuthAccount(Base):
    """OAuth账户关联模型"""
    __tablename__ = "oauth_accounts"

    __table_args__ = (
        UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)  # "linuxdo"
    provider_user_id = Column(String(255), nullable=False, index=True)  # OAuth提供商的user id
    provider_username = Column(String(255), nullable=True)  # OAuth提供商的username
    provider_email = Column(String(255), nullable=True)  # OAuth提供商的email
    access_token = Column(EncryptedString(512), nullable=True)  # 可选：存储access token (encrypted at rest)
    refresh_token = Column(EncryptedString(512), nullable=True)  # 可选：存储refresh token (encrypted at rest)
    linked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="oauth_accounts")


class RefreshToken(Base):
    """Refresh Token模型 - 用于安全会话管理"""
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True)  # UUID (jti)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, index=True)  # SHA-256 hash
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)  # 撤销时间
    replaced_by = Column(String(36), nullable=True)  # token rotation
    user_agent = Column(String(255), nullable=True)  # 用户代理（审计）
    ip_address = Column(String(64), nullable=True)  # IP地址（审计）

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class PasswordResetToken(Base):
    """密码重置令牌模型"""
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, index=True)  # SHA-256 hash
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)  # 使用时间
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class OAuthState(Base):
    """OAuth状态临时表 - 用于CSRF防护"""
    __tablename__ = "oauth_states"

    id = Column(String(36), primary_key=True)  # UUID
    provider = Column(String(32), nullable=False, index=True)  # "linuxdo"
    state_hash = Column(String(128), nullable=False, unique=True, index=True)  # SHA-256 hash
    next_url = Column(String(512), nullable=True)  # 登录成功后跳转URL
    bind_user_id = Column(String(36), nullable=True)  # 绑定模式：目标user_id
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)  # 使用时间

    def is_expired(self) -> bool:
        """检查state是否过期"""
        return datetime.now(timezone.utc) > self.expires_at

    def is_used(self) -> bool:
        """检查state是否已使用"""
        return self.used_at is not None
