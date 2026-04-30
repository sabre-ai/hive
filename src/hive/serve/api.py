"""FastAPI REST API for the hive dashboard."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from hive.auth.config import AuthConfig
from hive.auth.middleware import require_auth, set_auth_config
from hive.config import Config
from hive.store.query import QueryAPI

logger = logging.getLogger(__name__)


# ── Request / response models ───────────────────────────────────────


class AnnotationRequest(BaseModel):
    session_id: str
    type: str
    value: str
    author: str | None = None


class AnnotationResponse(BaseModel):
    id: int
    session_id: str
    type: str
    value: str
    author: str


class SessionPushPayload(BaseModel):
    id: str
    source: str
    project_path: str | None = None
    project_id: str | None = None
    author: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    message_count: int = 0
    summary: str | None = None
    messages: list[dict] = []
    enrichments: list[dict] = []
    annotations: list[dict] = []
    edges: list[dict] = []


# ── App factory ─────────────────────────────────────────────────────


def create_app(
    config: Config | None = None,
    db_path: Path | None = None,
    raw_config: dict | None = None,
) -> FastAPI:
    """Build and return a configured FastAPI application."""
    cfg = config or Config.load()
    query = QueryAPI(cfg, db_path=db_path)

    # Load auth configuration
    auth_cfg = AuthConfig.load(raw_config)
    set_auth_config(auth_cfg)

    app = FastAPI(
        title="hive",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # CORS — wide open for local development; tighten for production.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount auth routes if enabled
    if auth_cfg.enabled:
        from hive.auth.routes import create_auth_router
        from hive.store.db import get_session_factory

        session_factory = get_session_factory(cfg, db_path=db_path)
        app.include_router(create_auth_router(auth_cfg, session_factory))

    # ── API routes ──────────────────────────────────────────────────

    @app.get("/")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/sessions")
    def list_sessions(
        source: str | None = None,
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        tag: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        sort_by: str | None = None,
        min_tokens: int | None = None,
        model: str | None = None,
        min_correction_rate: float | None = None,
    ) -> list[dict[str, Any]]:
        return query.list_sessions(
            source=source,
            project=project,
            author=author,
            since=since,
            until=until,
            tag=tag,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            min_tokens=min_tokens,
            model=model,
            min_correction_rate=min_correction_rate,
        )

    @app.post("/api/sessions", status_code=201)
    def import_session(
        body: SessionPushPayload,
        user: dict | None = Depends(require_auth),  # noqa: B008
    ) -> dict[str, Any]:
        data = body.model_dump()
        # When auth is enabled, enforce identity from JWT
        if user is not None:
            data["author"] = user.get("email", data.get("author"))
            data["user_id"] = user.get("sub")
        query.import_session(data)
        return {"status": "ok", "session_id": body.id}

    @app.get("/api/sessions/{session_id}")
    def get_session(
        session_id: str,
        detail: str | None = None,
        role: str | None = None,
        msg_limit: int | None = None,
        msg_offset: int = 0,
    ) -> dict[str, Any]:
        result = query.get_session(
            session_id,
            detail=detail,
            role=role,
            msg_limit=msg_limit,
            msg_offset=msg_offset,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return result

    @app.delete("/api/sessions/{session_id}")
    def delete_session(
        session_id: str,
        user: dict | None = Depends(require_auth),  # noqa: B008
    ) -> dict[str, Any]:
        deleted = query.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "ok", "session_id": session_id}

    @app.get("/api/search")
    def search(
        q: str = Query(..., min_length=1),
        project: str | None = None,
        author: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = Query(default=20, ge=1, le=200),
    ) -> list[dict[str, Any]]:
        return query.search_sessions(
            query=q,
            project=project,
            author=author,
            since=since,
            until=until,
            limit=limit,
        )

    @app.get("/api/lineage/session/{session_id}")
    def get_session_lineage(session_id: str) -> list[dict[str, Any]]:
        return query.get_lineage(session_id, id_type="session")

    @app.get("/api/lineage/{path:path}")
    def get_lineage(path: str) -> list[dict[str, Any]]:
        return query.get_lineage(path, id_type="file")

    @app.get("/api/stats")
    def get_stats(
        project: str | None = None,
        since: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        return query.get_stats(project=project, since=since, group_by=group_by)

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        return query.list_projects()

    @app.post("/api/annotations", status_code=201)
    def create_annotation(
        body: AnnotationRequest,
        user: dict | None = Depends(require_auth),  # noqa: B008
    ) -> AnnotationResponse:
        # When auth is enabled, use identity from JWT
        if user is not None:
            author = user.get("email", body.author or "user")
        else:
            author = body.author or "user"
        row_id = query.write_annotation(
            session_id=body.session_id,
            ann_type=body.type,
            value=body.value,
            author=author,
        )
        return AnnotationResponse(
            id=row_id,
            session_id=body.session_id,
            type=body.type,
            value=body.value,
            author=author,
        )

    return app
