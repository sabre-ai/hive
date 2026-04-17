# Capture Adapters

Capture adapters translate events from AI coding tools into hive's storage schema. Each adapter handles the specifics of one tool (hook format, transcript layout, metadata extraction) and writes normalized data through the shared `QueryAPI`.

## The CaptureAdapter Protocol

Defined in `src/hive/capture/base.py`:

```python
class CaptureAdapter(ABC):
    @abstractmethod
    def name(self) -> str:
        """Short stable identifier (e.g. 'claude_code')."""

    @abstractmethod
    def setup(self) -> None:
        """One-time init (install hooks, create dirs). Must be idempotent."""

    @abstractmethod
    def handle(self, event_name: str, data: dict) -> None:
        """Process a single hook event. Ignore unknown events silently."""
```

## ClaudeCodeAdapter

**Source**: `src/hive/capture/claude_code.py`

Ingests sessions from Claude Code's hook system. Claude Code emits JSON on stdin for each hook event, containing at minimum `session_id` and `project_path`.

### The Four Hooks

| Hook | Event Name | What It Does |
|------|-----------|--------------|
| `SessionStart` | `SessionStart` | Creates a new session row. Collects git state (branch, commit, remote, author) and stores as enrichments. |
| `Stop` | `Stop` | Parses the JSONL transcript, inserts all messages (with secret scrubbing), builds FTS index, derives summary from first human message, runs all enrichers, and triggers auto-push if sharing is enabled. |
| `PostToolUse` | `PostToolUse` | Extracts file paths from tool calls (Read, Write, Edit, Bash, Glob, Grep) and creates `session -> file` edges with relationship `"touched"`. |
| `PreCompact` | `PreCompact` | Snapshots the full transcript before Claude compacts it. Stores the scrubbed text as an enrichment (`compact_snapshot` / `transcript`). |

### Hook Installation

`hive init` writes hook definitions into `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{"type": "command", "command": "hive capture session-start"}],
    "Stop": [{"type": "command", "command": "hive capture stop"}],
    "PostToolUse": [{"type": "command", "command": "hive capture post-tool-use"}],
    "PreCompact": [{"type": "command", "command": "hive capture pre-compact"}]
  }
}
```

### Auto-Push Flow (Stop)

When a session ends and sharing is enabled for the project:

1. Export full session payload (session + messages + enrichments + annotations + edges)
2. Scrub all string values in the payload with `scrub_payload()`
3. POST to `{server_url}/api/sessions` in a daemon thread (non-blocking)

### Transcript Parsing

Claude Code transcripts are JSONL files where each line is:

```json
{"type": "user|assistant|progress|...", "message": {"role": "...", "content": ...}, "isMeta": bool, "timestamp": "ISO-8601", "cwd": "/path", "sessionId": "uuid"}
```

The adapter filters to `type = "user" | "assistant"`, skips `isMeta` lines, normalizes roles (`user` -> `human`), and extracts text from content blocks (text, tool_use, tool_result). All content is scrubbed for secrets before storage.

### Backfill

`ClaudeCodeAdapter.backfill()` scans `~/.claude/projects/` for existing `.jsonl` transcripts, imports any sessions not already in the database, and retroactively creates file edges, extracts token usage, and links commits that occurred during each session's time window.

## Writing a New Adapter

To capture sessions from another tool (Cursor, ChatGPT exports, etc.):

### 1. Create the adapter

```python
# src/hive/capture/cursor.py
from hive.capture.base import CaptureAdapter
from hive.config import Config
from hive.store.query import QueryAPI


class CursorAdapter(CaptureAdapter):
    def __init__(self, config: Config | None = None):
        self._config = config or Config.load()
        self._api = QueryAPI(self._config)

    def name(self) -> str:
        return "cursor"

    def setup(self) -> None:
        # Create any required directories or install hooks
        pass

    def handle(self, event_name: str, data: dict) -> None:
        # Map Cursor's event format to hive storage.
        # Use self._api.upsert_session(), insert_messages(),
        # insert_enrichment(), insert_edge(), index_session_fts()
        pass
```

### 2. Register in `__init__.py`

Add to `src/hive/capture/__init__.py`:

```python
from hive.capture.cursor import CursorAdapter

__all__ = ["CaptureAdapter", "ClaudeCodeAdapter", "CursorAdapter", "GitCommitHook"]
```

### 3. Wire into the CLI

Add a CLI command or modify the `capture` command in `src/hive/cli.py` to route events to your adapter.

### Key Points

- Use `QueryAPI` for all database writes -- it handles connection management.
- Call `scrub(text, config)` on any user-generated content before storage.
- Create edges for file and commit relationships so lineage queries work.
- Call `index_session_fts()` with scrubbed content so full-text search covers your sessions.
- Run enrichers after inserting messages: `run_enrichers(session_id, session_data, api)`.
