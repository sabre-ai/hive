# Enrich Layer

The enrich layer attaches derived context to captured sessions. Each enricher inspects a session and produces key-value pairs that are persisted to the `enrichments` table.

## Quick Example

```python
from hive.enrich import run_enrichers
from hive.store.query import QueryAPI

api = QueryAPI()
session_data = {"project_path": "/my/project", "messages": [...]}
run_enrichers("session-abc-123", session_data, api)
# Enrichments now stored: git/branch, quality/message_count, files/files_touched, ...
```

## Enricher Protocol

Every enricher satisfies the protocol defined in `src/hive/enrich/base.py`:

```python
class Enricher(Protocol):
    def name(self) -> str: ...
        # Unique identifier, used as `source` column in the enrichments table

    def should_run(self, session: dict[str, Any]) -> bool: ...
        # Return True when this enricher is applicable

    def run(self, session: dict[str, Any]) -> dict[str, Any]: ...
        # Execute enrichment, return key->value pairs to persist
```

## Pipeline Execution

The `run_enrichers()` function in `src/hive/enrich/__init__.py` iterates over `ALL_ENRICHERS` and persists results:

```python
ALL_ENRICHERS = [GitEnricher(), FilesEnricher(), QualityEnricher()]

def run_enrichers(session_id, session, query_api):
    for enricher in ALL_ENRICHERS:
        if not enricher.should_run(session):
            continue
        results = enricher.run(session)
        for key, value in results.items():
            query_api.insert_enrichment(session_id, enricher.name(), key, str(value))
```

!!! important "Error Isolation"
    Exceptions are caught **per enricher**. A failing enricher logs the exception but does not block other enrichers from running. This means a git timeout never prevents quality metrics from being recorded.

## Built-in Enrichers

### GitEnricher

**Source:** `src/hive/enrich/git.py` | **Name:** `git`

Captures repository context at the time of the session.

| Key | Value | Example |
|-----|-------|---------|
| `branch` | Current branch name | `feat/mcp-solo-mode` |
| `commit_sha` | HEAD commit SHA | `5b1dd62...` |
| `remote_url` | Origin remote URL | `git@github.com:org/repo.git` |
| `diff_stat` | Output of `git diff --stat` | `3 files changed, 42 insertions(+)` |
| `user_name` | Git config `user.name` | `Alice` |

!!! note "Eligibility"
    Only runs if `session["project_path"]` points to a directory containing a `.git` folder. Non-git projects are silently skipped.

### FilesEnricher

**Source:** `src/hive/enrich/files.py` | **Name:** `files`

Extracts file paths mentioned during the session. Uses two strategies:

=== "Structured Extraction"
    Parses tool-use messages that carry JSON with `file_path`, `path`, `filePath`, or `filename` keys. This covers Read, Write, Edit, and similar tool calls.

=== "Regex Fallback"
    Scans free-text content for absolute paths (`/foo/bar.py`) and relative paths (`src/main.py`). Filters out URLs and version-number-like strings.

| Key | Value |
|-----|-------|
| `files_touched` | Comma-separated sorted list of file paths |

### QualityEnricher

**Source:** `src/hive/enrich/quality.py` | **Name:** `quality`

Computes lightweight conversational quality signals.

| Key | Type | Description |
|-----|------|-------------|
| `message_count` | int | Total messages in the session |
| `human_assistant_ratio` | float | Human messages / assistant messages (0.0 if no assistant messages) |
| `correction_frequency` | float | Fraction of human messages containing correction signals ("no", "actually", "that's wrong", "instead", "wait") |
| `session_duration` | float | Duration in seconds between first and last message timestamps |

### Token Usage

Token usage is **not** an enricher. It is extracted by `ClaudeCodeAdapter` during backfill by scanning JSONL transcript lines for `assistant` records with `message.usage` fields.

| Key | Source | Description |
|-----|--------|-------------|
| `input_tokens` | `tokens` | Total input tokens across all assistant turns |
| `output_tokens` | `tokens` | Total output tokens |
| `cache_read_input_tokens` | `tokens` | Tokens read from prompt cache |
| `cache_creation_input_tokens` | `tokens` | Tokens written to prompt cache |
| `total_tokens` | `tokens` | Sum of all four token counters |
| `model` | `tokens` | Model identifier (e.g., `claude-sonnet-4-20250514`) |

## Creating a Custom Enricher

To add a new enricher:

1. Create a new file in `src/hive/enrich/` implementing the protocol
2. Add your enricher instance to `ALL_ENRICHERS` in `src/hive/enrich/__init__.py`

```python
# src/hive/enrich/my_enricher.py
class MyEnricher:
    def name(self) -> str:
        return "my_enricher"

    def should_run(self, session: dict) -> bool:
        return True  # or check session contents

    def run(self, session: dict) -> dict:
        return {"my_key": "computed_value"}
```

Then register it:

```python
# src/hive/enrich/__init__.py
from hive.enrich.my_enricher import MyEnricher

ALL_ENRICHERS = [GitEnricher(), FilesEnricher(), QualityEnricher(), MyEnricher()]
```

!!! tip "Convention"
    The enricher's `name()` becomes the `source` column in the enrichments table. Use a short, stable, snake_case identifier.
