---
hide:
  - navigation
  - toc
---

<div class="hive-hero" markdown>

# Every conversation with AI is institutional knowledge. **Hive** makes sure none of it is lost.

Design decisions, debugging sessions, architecture discussions — captured automatically and searchable by Claude.

[Get started :material-arrow-right:](getting-started/index.md){ .md-button .md-button--primary }
[View on GitHub :fontawesome-brands-github:](https://github.com/sabre-ai/hive){ .md-button }

</div>

## What Hive does

<div class="grid cards" markdown>

- :material-record-rec:{ .lg .middle } __Automatic cross-tool capture__

    ---

    Claude Code and Claude Desktop conversations in one history, no setup per-session. Prompts, tool calls, and outputs are preserved automatically.

- :material-magnify:{ .lg .middle } __Searchable by Claude__

    ---

    Ask Claude about past decisions, designs, and debugging context across your full history. Full-text and semantic search via MCP.

- :material-arrow-expand-all:{ .lg .middle } __Solo to team__

    ---

    Works on your laptop, scales to a shared server when you're ready. SQLite or PostgreSQL, self-hosted, Apache 2.0.

</div>

## How it works

```mermaid
flowchart LR
    A[Claude Code<br/>hooks] -->|stdin JSON| B[Capture]
    B --> C[Enrich<br/>git · files · quality]
    C --> D[(store.db<br/>SQLite + FTS5)]
    D -->|auto-push| E[(server.db<br/>team)]
    E --> F[MCP<br/>REST API<br/>CLI]
    F --> G[Claude]
```

## Get involved

- [Contributing](contributing.md) — adapters, enrichers, and more
- [Security](security.md) — how we handle secrets
- [GitHub](https://github.com/sabre-ai/hive) — issues, discussions, PRs welcome

**Apache 2.0** — self-host, fork, audit. The server, the scrubber, and the MCP surface are all in-repo.
