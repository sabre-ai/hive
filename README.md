<p align="center">
  <img src="docs/assets/hive-mark.svg" width="56" height="56" alt="hive">
</p>
<h1 align="center">hive</h1>
<p align="center">Every conversation with AI is institutional knowledge. Hive makes sure none of it is lost.</p>

> **Full documentation:** [sabre-ai.github.io/hive](https://sabre-ai.github.io/hive/)

Design decisions, debugging sessions, architecture discussions, code reviews — your AI conversations hold context that doesn't make it into commits or docs. Hive captures it all automatically and makes it searchable by Claude via MCP.

**Automatic cross-tool capture:** Claude Code and Claude Desktop conversations in one history, no setup per-session.

**Searchable by Claude:** Ask about past decisions, designs, and debugging context across your full history.

**Solo to team:** Works on your laptop, scales to a shared server when you're ready.

## Quick Start

```bash
curl https://sabre-ai.github.io/hive/install.sh | bash
```

This installs hive and configures the MCP server for both Claude Code and Claude Desktop. Then enable capture for each project:

```bash
cd your-project
hive init
```

Ask Claude: *"What did I work on today?"*

See the [Getting Started guide](https://sabre-ai.github.io/hive/getting-started/) for team server deployment and Docker.

> **Developing hive?** See [Install from Source](https://sabre-ai.github.io/hive/getting-started/install-from-source/) for the git clone + venv workflow.

## What Claude Can Do

Claude is the interface. These MCP tools are available when hive is connected:

| Tool | Description | Required Args |
|------|-------------|---------------|
| `search` | Full-text and semantic search across sessions | `query` |
| `get_session` | Retrieve complete session with messages | `session_id` |
| `lineage` | Sessions and commits connected to a file | `file_path` |
| `recent` | Latest sessions, filterable by project/author | — |
| `stats` | Quality metrics, token usage, patterns | — |
| `delete` | Remove a session from the server | `session_id` |

### Example Prompts

- *"What sessions touched the auth middleware this week?"*
- *"Show me the conversation that led to the payment service refactor"*
- *"How many tokens did the team use on the sabre-ai project?"*
- *"Which sessions had the most corrections?"*
- *"Delete my session from yesterday about the client review"*

## License

Apache-2.0
