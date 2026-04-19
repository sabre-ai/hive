"""Factory for creating search backend instances from config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hive.search.base import SearchBackend

if TYPE_CHECKING:
    from hive.config import Config


def get_search_backend(config: Config) -> SearchBackend:
    """Return the configured search backend instance.

    Reads ``config.search_backend`` and returns the appropriate backend:
    - ``"sqlite-vec"`` (default) — in-process vector search via sqlite-vec
    - ``"witchcraft"`` — HTTP client to the Rust hive-search server
    - ``"pgvector"`` — PostgreSQL pgvector (not yet implemented)
    - ``"elasticsearch"`` — Elasticsearch (not yet implemented)
    """
    backend = config.search_backend

    if backend == "witchcraft":
        from hive.search.witchcraft import WitchcraftBackend

        return WitchcraftBackend(base_url=config.search_url)

    if backend == "sqlite-vec":
        from hive.search.sqlite_vec import SqliteVecBackend

        return SqliteVecBackend(
            db_path=config.search_vec_db_path,
            model_name=config.search_embedding_model,
        )

    if backend == "pgvector":
        from hive.search.pgvector import PgvectorBackend

        return PgvectorBackend()

    if backend == "elasticsearch":
        from hive.search.elasticsearch import ElasticsearchBackend

        return ElasticsearchBackend()

    raise ValueError(
        f"Unknown search backend: {backend!r}. "
        f"Supported: sqlite-vec, witchcraft, pgvector, elasticsearch"
    )
