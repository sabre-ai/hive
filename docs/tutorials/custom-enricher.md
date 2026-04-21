# Writing a Custom Enricher

Enrichers extract metadata from sessions after capture. Hive runs every registered enricher on each session and stores the results as enrichment records. This tutorial walks through building a "test coverage" enricher that counts test files touched in a session.

## The Enricher Protocol

Every enricher implements three methods:

```python
class Enricher:
    def name(self) -> str:
        """Unique identifier for this enricher."""
        ...

    def should_run(self, session: dict[str, Any]) -> bool:
        """Return True if this enricher applies to the session."""
        ...

    def run(self, session: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata. Returns a dict stored as JSON."""
        ...
```

- `name()` -- used as the enrichment type in the database.
- `should_run()` -- skip sessions that have no relevant data.
- `run()` -- do the work, return a dict. No schema changes needed; the dict is stored as JSON.

## Full Example: Test Coverage Enricher

Create `src/hive/enrich/test_coverage.py`:

```python
# src/hive/enrich/test_coverage.py
from __future__ import annotations

from typing import Any


class TestCoverageEnricher:
    """Count test-related files touched in a session."""

    def name(self) -> str:
        return "test_coverage"

    def should_run(self, session: dict[str, Any]) -> bool:
        return bool(session.get("messages"))

    def run(self, session: dict[str, Any]) -> dict[str, Any]:
        messages = session.get("messages", [])
        test_files = set()
        source_files = set()

        for msg in messages:
            content = msg.get("content", "")  # (1)!
            tool_name = msg.get("tool_name", "")

            if tool_name in ("Read", "Write", "Edit"):
                # Extract file path from tool input
                path = msg.get("file_path", "") or ""
                if "/test" in path or path.startswith("test"):
                    test_files.add(path)
                elif path.endswith(".py"):
                    source_files.add(path)

        ratio = len(test_files) / max(len(source_files), 1)

        return {
            "test_files_touched": len(test_files),
            "source_files_touched": len(source_files),
            "test_ratio": f"{ratio:.2f}",
        }
```

1. The `content` variable is available for more advanced analysis, such as scanning for test-related keywords.

## How It Works

The enricher scans every message in the session for tool uses that reference files. It classifies each file path as a test file (contains `/test` or starts with `test`) or a source file (ends with `.py`). The output includes counts and a ratio.

Example enrichment output stored in the database:

```json
{
  "test_files_touched": 3,
  "source_files_touched": 8,
  "test_ratio": "0.38"
}
```

## Register the Enricher

Add your enricher to `src/hive/enrich/__init__.py` so hive discovers it:

```python
from hive.enrich.test_coverage import TestCoverageEnricher

# Add to the list of enrichers
ENRICHERS = [
    # ... existing enrichers ...
    TestCoverageEnricher(),
]
```

!!! note
    No database schema changes are needed. Enrichment data is stored as JSON in the `enrichments` table, keyed by the enricher's `name()`.

## Verify

Run the test suite to make sure nothing is broken:

```bash
pytest tests/ -v
```

Then trigger a session (or re-enrich an existing one) and check the result:

```bash
hive show <session_id>
```

The enrichment section should include your `test_coverage` data.

## Design Guidelines

When writing enrichers, follow these patterns:

- **Keep `should_run` cheap.** It is called for every session. Check for a required field, not the full message list.
- **Keep `run` pure.** Read from the session dict, return a new dict. No side effects, no database writes.
- **Return flat dicts when possible.** Nested structures work but are harder to query.
- **Handle missing data gracefully.** Sessions may have empty messages or missing fields. Use `.get()` with defaults.

!!! tip "Built-in enrichers for reference"
    Look at the existing enrichers in `src/hive/enrich/` for patterns:

    - `git.py` -- extracts branch, commit, remote, diff stats
    - `files.py` -- extracts file paths from messages
    - `quality.py` -- computes message counts, human/assistant ratio, corrections, duration
