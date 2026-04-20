# Writing a Custom Adapter

Capture adapters ingest session data from AI coding tools. Hive ships with a Claude Code adapter, but the protocol is designed for extension. This tutorial walks through building a skeleton Cursor adapter.

## The CaptureAdapter Protocol

Every adapter implements three methods:

```python
class CaptureAdapter:
    def name(self) -> str:
        """Unique identifier for this adapter."""
        ...

    def setup(self) -> None:
        """Install hooks, watchers, or other prerequisites."""
        ...

    def handle(self, event_name: str, data: dict) -> None:
        """Process an incoming event."""
        ...
```

- `name()` -- identifies the source in the database (e.g., `"claude_code"`, `"cursor"`).
- `setup()` -- called by `hive init` to install hooks or configure the tool.
- `handle()` -- called for each event with the event name and parsed JSON payload.

## Full Example: Cursor Adapter

Create `src/hive/capture/cursor.py`:

```python
# src/hive/capture/cursor.py
from __future__ import annotations

from typing import Any

from hive.capture.base import CaptureAdapter
from hive.config import Config
from hive.privacy import scrub
from hive.store.query import QueryAPI


class CursorAdapter(CaptureAdapter):
    """Capture adapter for Cursor AI editor sessions."""

    def __init__(self, config: Config | None = None):
        self._config = config or Config.load()
        self._api = QueryAPI(self._config)

    def name(self) -> str:
        return "cursor"

    def setup(self) -> None:
        """Install Cursor-specific hooks or file watchers."""
        # Cursor stores conversations in its own format.
        # This method would set up a file watcher on Cursor's
        # data directory, or register a plugin hook.
        pass  # (1)!

    def handle(self, event_name: str, data: dict[str, Any]) -> None:
        """Process a Cursor session event."""
        if event_name == "session_end":
            self._ingest_session(data)

    def _ingest_session(self, data: dict[str, Any]) -> None:
        session_id = data["id"]

        # 1. Upsert the session record
        self._api.upsert_session(
            {
                "id": session_id,
                "source": self.name(),
                "project_path": data.get("project_path"),
                "author": data.get("author"),
                "started_at": data.get("started_at"),
                "ended_at": data.get("ended_at"),
                "summary": data.get("summary"),
            }
        )

        # 2. Normalize and insert messages
        messages = []
        for msg in data.get("messages", []):
            messages.append(
                {
                    "session_id": session_id,
                    "role": msg["role"],
                    "content": scrub(msg.get("content", "")),  # (2)!
                }
            )
        self._api.insert_messages(messages)

        # 3. Index for full-text search
        content = " ".join(m.get("content", "") for m in messages)
        self._api.index_session_fts(session_id, scrub(content))

        # 4. Create edges for file lineage
        for file_path in data.get("files_touched", []):
            self._api.insert_edge(
                {
                    "source_type": "session",
                    "source_id": session_id,
                    "target_type": "file",
                    "target_id": file_path,
                    "relation": "touched",
                }
            )
```

1. Implementation depends on how Cursor exposes its session data. You might watch `~/.cursor/conversations/` for new files, or use a Cursor extension API.
2. Always call `scrub()` on content before storing. This removes secrets matched by patterns in `scrub_patterns.toml`.

## Key Patterns

### Use QueryAPI for All Database Writes

Never open the database directly. `QueryAPI` handles WAL mode, schema migrations, and concurrent access:

```python
self._api = QueryAPI(self._config)
self._api.upsert_session({...})
self._api.insert_messages([...])
self._api.index_session_fts(session_id, content)
self._api.insert_edge({...})
```

### Scrub Content for Privacy

Always pass user content through `scrub()` before storage:

```python
from hive.privacy import scrub

clean_content = scrub(raw_content)
```

This applies regex patterns from `scrub_patterns.toml` to remove API keys, tokens, and other secrets.

### Create Edges for Lineage

File lineage only works if your adapter creates edges. For every file touched during a session:

```python
self._api.insert_edge({
    "source_type": "session",
    "source_id": session_id,
    "target_type": "file",
    "target_id": "/absolute/path/to/file.py",
    "relation": "touched",
})
```

Use absolute paths for file targets so lineage queries match regardless of working directory.

## Register the Adapter

Add your adapter to `src/hive/capture/__init__.py`:

```python
from hive.capture.cursor import CursorAdapter

ADAPTERS = {
    "claude_code": ClaudeCodeAdapter,
    "cursor": CursorAdapter,
}
```

## Wire into the CLI

Add a CLI command or extend `hive capture` to accept Cursor events:

```python
@cli.command()
@click.argument("event_name")
def capture_cursor(event_name):
    """Capture a Cursor session event."""
    data = json.load(sys.stdin)
    adapter = CursorAdapter()
    adapter.handle(event_name, data)
```

## Verify

Run the test suite:

```bash
pytest tests/ -v
```

!!! tip "Testing adapters"
    Write tests that call `handle()` with sample payloads and verify the session, messages, and edges are stored correctly. Use a temporary database (`:memory:` or a temp file) in your test config.
