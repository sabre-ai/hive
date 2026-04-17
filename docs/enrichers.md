# Enrichers

Enrichers attach derived metadata to captured sessions. They run automatically after a session's transcript is parsed (on the `Stop` event) and during backfill.

## When Enrichers Run

```
Stop hook fires
  -> parse JSONL transcript
  -> insert messages
  -> run_enrichers(session_id, session_data, query_api)
       -> for each enricher in ALL_ENRICHERS:
            if enricher.should_run(session):
                results = enricher.run(session)
                for key, value in results:
                    insert_enrichment(session_id, enricher.name(), key, value)
```

Results are stored in the `enrichments` table with columns: `session_id`, `source` (enricher name), `key`, `value`, `enriched_at`.

## Built-in Enrichers

### GitEnricher (`source = "git"`)

Captures repository state at session time. Only runs if the project directory contains a `.git` folder.

| Key | Value |
|-----|-------|
| `branch` | Current branch name |
| `commit_sha` | HEAD commit hash |
| `remote_url` | Origin remote URL |
| `diff_stat` | Output of `git diff --stat` |
| `user_name` | Git config `user.name` |

**Source**: `src/hive/enrich/git.py`

### FilesEnricher (`source = "files"`)

Extracts file paths mentioned in session messages. Uses two strategies: structured extraction from tool-use JSON (`file_path`, `path` keys) and regex fallback for paths in free text.

| Key | Value |
|-----|-------|
| `files_touched` | Comma-separated sorted list of file paths |

Always runs. **Source**: `src/hive/enrich/files.py`

### QualityEnricher (`source = "quality"`)

Computes lightweight quality signals from the conversation.

| Key | Value |
|-----|-------|
| `message_count` | Total messages in session |
| `human_assistant_ratio` | Ratio of human to assistant messages |
| `correction_frequency` | Fraction of human messages containing correction signals ("no", "actually", "that's wrong", "instead", "wait") |
| `session_duration` | Duration in seconds (from timestamps) |

Always runs. **Source**: `src/hive/enrich/quality.py`

### Token Usage (captured during backfill)

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

    def name(self) -> str:
        return "complexity"

    def should_run(self, session: dict[str, Any]) -> bool:
        # Return True if this enricher applies to the session.
        # session has keys: project_path, messages
        return bool(session.get("messages"))

    def run(self, session: dict[str, Any]) -> dict[str, Any]:
        # Return a dict of key -> value pairs.
        # Each pair becomes one row in the enrichments table.
        messages = session.get("messages", [])
        total_chars = sum(len(m.get("content", "")) for m in messages)
        tool_count = sum(1 for m in messages if m.get("tool_name"))
        return {
            "total_chars": total_chars,
            "tool_use_count": tool_count,
        }
```

The protocol requires three methods:

- `name() -> str` -- Unique identifier, used as the `source` column in `enrichments`.
- `should_run(session) -> bool` -- Guards execution. The `session` dict contains `project_path` and `messages`.
- `run(session) -> dict[str, Any]` -- Returns key-value pairs. All values are cast to `str` before storage.

### 2. Register in `__init__.py`

Add your enricher to the `ALL_ENRICHERS` list in `src/hive/enrich/__init__.py`:

```python
from hive.enrich.complexity import ComplexityEnricher

ALL_ENRICHERS: list[Enricher] = [
    GitEnricher(),
    FilesEnricher(),
    QualityEnricher(),
    ComplexityEnricher(),  # <-- add here
]
```

That is all. The `run_enrichers()` function iterates `ALL_ENRICHERS` and persists results automatically. Exceptions in individual enrichers are caught and logged without blocking other enrichers.
