# Enrichers

Enrichers attach derived metadata to captured sessions. They run automatically after a session's transcript is parsed (on the `Stop` event) and during backfill.

## When Enrichers Run

```python
# Simplified flow inside the Stop hook handler
def handle_stop(session_id, session_data, query_api):
    parse_jsonl_transcript()
    insert_messages()
    run_enrichers(session_id, session_data, query_api)
    #   -> for each enricher in ALL_ENRICHERS:
    #        if enricher.should_run(session):
    #            results = enricher.run(session)
    #            for key, value in results:
    #                insert_enrichment(session_id, enricher.name(), key, value)
```

Results are stored in the `enrichments` table with columns: `session_id`, `source` (enricher name), `key`, `value`, `enriched_at`.

!!! info "Error isolation"
    Exceptions in individual enrichers are caught and logged without blocking
    other enrichers. A failing enricher does not prevent session capture.

## Built-in Enrichers

### GitEnricher

**Source**: `src/hive/enrich/git.py` | **Enrichment source**: `"git"`

Captures repository state at session time. Only runs if the project directory contains a `.git` folder.

| Key | Value |
|-----|-------|
| `branch` | Current branch name |
| `commit_sha` | HEAD commit hash |
| `remote_url` | Origin remote URL |
| `diff_stat` | Output of `git diff --stat` |
| `user_name` | Git config `user.name` |

!!! tip "When it runs"
    Only when the project directory is a git repository. Non-git projects
    skip this enricher automatically.

### FilesEnricher

**Source**: `src/hive/enrich/files.py` | **Enrichment source**: `"files"`

Extracts file paths mentioned in session messages. Uses two strategies: structured extraction from tool-use JSON (`file_path`, `path` keys) and regex fallback for paths in free text.

| Key | Value |
|-----|-------|
| `files_touched` | Comma-separated sorted list of file paths |

Always runs.

### QualityEnricher

**Source**: `src/hive/enrich/quality.py` | **Enrichment source**: `"quality"`

Computes lightweight quality signals from the conversation.

| Key | Value |
|-----|-------|
| `message_count` | Total messages in session |
| `human_assistant_ratio` | Ratio of human to assistant messages |
| `correction_frequency` | Fraction of human messages containing correction signals |
| `session_duration` | Duration in seconds (from timestamps) |

!!! info "Correction signals"
    The correction detector looks for keywords: "no", "actually",
    "that's wrong", "instead", "wait". This is a heuristic -- not perfect,
    but useful for spotting sessions that required significant course correction.

Always runs.

### Token Usage

Token data is extracted directly by `ClaudeCodeAdapter._extract_token_usage()` during backfill, not via the enricher pipeline. Stored with `source = "tokens"`.

| Key | Value |
|-----|-------|
| `input_tokens` | Total input tokens |
| `output_tokens` | Total output tokens |
| `cache_read_input_tokens` | Tokens read from cache |
| `cache_creation_input_tokens` | Tokens used creating cache |
| `total_tokens` | Sum of all token types |
| `model` | Model identifier string |

## Writing a Custom Enricher

### 1. Implement the Enricher Protocol

Create a new file in `src/hive/enrich/`. Your class must satisfy the `Enricher` protocol defined in `src/hive/enrich/base.py`:

```python
# src/hive/enrich/complexity.py
from __future__ import annotations
from typing import Any


class ComplexityEnricher:
    """Estimate session complexity from message length and tool usage."""

    def name(self) -> str:  # (1)!
        return "complexity"

    def should_run(self, session: dict[str, Any]) -> bool:  # (2)!
        return bool(session.get("messages"))

    def run(self, session: dict[str, Any]) -> dict[str, Any]:  # (3)!
        messages = session.get("messages", [])
        total_chars = sum(len(m.get("content", "")) for m in messages)
        tool_count = sum(1 for m in messages if m.get("tool_name"))
        return {
            "total_chars": total_chars,
            "tool_use_count": tool_count,
        }
```

1. Unique identifier, used as the `source` column in `enrichments`.
2. Guards execution. The `session` dict contains `project_path` and `messages`.
3. Returns key-value pairs. All values are cast to `str` before storage.

### 2. Register in `__init__.py`

Add your enricher to the `ALL_ENRICHERS` list in `src/hive/enrich/__init__.py`:

```python
from hive.enrich.complexity import ComplexityEnricher

ALL_ENRICHERS: list[Enricher] = [
    GitEnricher(),
    FilesEnricher(),
    QualityEnricher(),
    ComplexityEnricher(),  # add here
]
```

!!! tip "No schema changes needed"
    The `run_enrichers()` function iterates `ALL_ENRICHERS` and persists
    results automatically. The `enrichments` table is key-value, so new
    enrichers work without migrations.
