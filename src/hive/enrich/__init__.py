"""Enrichment pipeline — attaches derived context to captured sessions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hive.enrich.base import Enricher
from hive.enrich.files import FilesEnricher
from hive.enrich.git import GitEnricher
from hive.enrich.quality import QualityEnricher

if TYPE_CHECKING:
    from hive.store.query import QueryAPI

log = logging.getLogger(__name__)

ALL_ENRICHERS: list[Enricher] = [GitEnricher(), FilesEnricher(), QualityEnricher()]


def run_enrichers(session_id: str, session: dict, query_api: QueryAPI) -> None:
    """Execute every applicable enricher and persist results."""
    for enricher in ALL_ENRICHERS:
        try:
            if not enricher.should_run(session):
                continue
            results = enricher.run(session)
            for key, value in results.items():
                query_api.insert_enrichment(
                    session_id, enricher.name(), key, str(value), upsert=True
                )
        except Exception:
            log.exception("Enricher %s failed for session %s", enricher.name(), session_id)
