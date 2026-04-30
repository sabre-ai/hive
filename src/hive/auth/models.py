"""SQLAlchemy models for authentication."""

from __future__ import annotations

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from hive.store.models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    oidc_subject: Mapped[str | None] = mapped_column(String)
    oidc_issuer: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str | None] = mapped_column(String, server_default=text("CURRENT_TIMESTAMP"))
    last_login_at: Mapped[str | None] = mapped_column(String)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str | None] = mapped_column(String, server_default=text("CURRENT_TIMESTAMP"))
    revoked_at: Mapped[str | None] = mapped_column(String)

    __table_args__ = (
        Index("idx_refresh_tokens_user", "user_id"),
        Index("idx_refresh_tokens_hash", "token_hash"),
    )
