"""SQLAlchemy ORM models for the hive data store."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(String, server_default=text("CURRENT_TIMESTAMP"))
    created_by: Mapped[str | None] = mapped_column(String)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    project_path: Mapped[str | None] = mapped_column(String)
    project_id: Mapped[str | None] = mapped_column(String)
    author: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[str | None] = mapped_column(String)
    ended_at: Mapped[str | None] = mapped_column(String)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    enrichments: Mapped[list[Enrichment]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    annotations: Mapped[list[Annotation]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_sessions_project", "project_path"),
        Index("idx_sessions_project_id", "project_id"),
        Index("idx_sessions_started", "started_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String)
    timestamp: Mapped[str | None] = mapped_column(String)

    session: Mapped[Session] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('human', 'assistant', 'tool')", name="ck_messages_role"),
        Index("idx_messages_session", "session_id"),
    )


class Enrichment(Base):
    __tablename__ = "enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    enriched_at: Mapped[str | None] = mapped_column(
        String, server_default=text("CURRENT_TIMESTAMP")
    )

    session: Mapped[Session] = relationship(back_populates="enrichments")

    __table_args__ = (
        Index("idx_enrichments_session", "session_id"),
        Index("idx_enrichments_key", "session_id", "key"),
    )


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(String)
    user_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str | None] = mapped_column(String, server_default=text("CURRENT_TIMESTAMP"))

    session: Mapped[Session] = relationship(back_populates="annotations")

    __table_args__ = (
        CheckConstraint("type IN ('tag', 'comment', 'rating')", name="ck_annotations_type"),
        UniqueConstraint("session_id", "type", "value", name="uq_annotations_dedup"),
        Index("idx_annotations_session", "session_id"),
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    relationship_: Mapped[str] = mapped_column("relationship", String, nullable=False)
    created_at: Mapped[str | None] = mapped_column(String, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relationship",
            name="uq_edges_dedup",
        ),
        Index("idx_edges_source", "source_type", "source_id"),
        Index("idx_edges_target", "target_type", "target_id"),
    )
