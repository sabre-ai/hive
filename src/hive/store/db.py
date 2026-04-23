"""Database initialization and connection management using SQLAlchemy + Alembic."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from hive.config import Config

logger = logging.getLogger(__name__)

# Cache engines per URL to avoid creating multiple engines for the same DB
_engines: dict[str, Engine] = {}


def get_engine(config: Config | None = None, db_path: Path | None = None) -> Engine:
    """Create or retrieve a cached SQLAlchemy engine."""
    if config is None:
        config = Config.load()
    url = _build_url(config, db_path)
    if url not in _engines:
        kwargs: dict = {"echo": False}
        if url.startswith("postgresql"):
            kwargs.update(pool_size=5, max_overflow=10)
        engine = create_engine(url, **kwargs)
        # Set SQLite PRAGMAs on every new connection
        if engine.dialect.name == "sqlite":

            @event.listens_for(engine, "connect")
            def _set_sqlite_pragmas(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _engines[url] = engine
    return _engines[url]


def get_session_factory(
    config: Config | None = None, db_path: Path | None = None
) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the engine."""
    engine = get_engine(config, db_path)
    return sessionmaker(bind=engine)


def init_db(config: Config | None = None, db_path: Path | None = None) -> Engine:
    """Run Alembic migrations to ensure the schema is current.

    For fresh databases, creates all tables. For existing pre-migration databases,
    stamps the current version without re-running DDL. Returns the engine.
    """
    if config is None:
        config = Config.load()

    url = _build_url(config, db_path)

    # Only create directories for SQLite databases
    if not url.startswith("postgresql"):
        path = db_path or config.db_path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    from alembic import command
    from alembic.config import Config as AlembicConfig

    alembic_cfg = AlembicConfig()
    alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(alembic_cfg, "head")
    logger.debug("Database migrations applied for %s", url)

    return get_engine(config, db_path)


def reset_engines() -> None:
    """Dispose all cached engines. Useful for testing."""
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()


def _build_url(config: Config, db_path: Path | None = None) -> str:
    """Build a SQLAlchemy connection URL from config."""
    if config.db_url:
        return config.db_url
    path = db_path or config.db_path
    return f"sqlite:///{path}"
