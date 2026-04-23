<p align="center">
  <img src="docs/assets/hive-mark.svg" width="56" height="56" alt="hive">
</p>
<h1 align="center">hive</h1>
<p align="center">Every conversation with AI is institutional knowledge. Hive makes sure none of it is lost.</p>

> **Full documentation:** [sabre-ai.github.io/hive](https://sabre-ai.github.io/hive/)

Design decisions, debugging sessions, architecture discussions, code reviews — your AI conversations hold context that doesn't make it into commits or docs. Hive captures it all automatically and makes it searchable by Claude via MCP.

**Solo:** Search your own history across Claude Code and Claude Desktop. *"What was that approach I tried last week?"*

**Cross-tool:** Link conversations across tools — a Claude Desktop design discussion connects to the Claude Code session that implemented it.

**Team:** Share sessions across your team so every developer's Claude can learn from everyone's work.

## Quick Start

```bash
git clone https://github.com/sabre-ai/hive.git
cd hive
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

cd your-project
hive init
claude mcp add --scope user --transport stdio hive -- /path/to/hive/.venv/bin/hive mcp
```

Ask Claude: *"What did I work on today?"*

See the [Getting Started guide](https://sabre-ai.github.io/hive/getting-started/) for Claude Desktop setup, team server deployment, and Docker.

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
