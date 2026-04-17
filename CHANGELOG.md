# Changelog

## [0.1.0] - 2026-04-16

### Added
- Initial release
- Claude Code capture adapter with four hooks (SessionStart, Stop, PostToolUse, PreCompact)
- Git, Files, Quality, and Token enrichers
- SQLite storage with FTS5 search
- Team server with auto-push and secret scrubbing
- MCP server for Claude Code integration
- REST API for session push, query, and delete
- CLI commands: init, serve, mcp, push, search, show, log, lineage, stats, projects, tag, delete, config sharing
- Per-project sharing controls
- Backfill of existing Claude Code sessions
