<p align="center">
  <img src="docs/assets/hive-mark.svg" width="56" height="56" alt="hive">
</p>
<h1 align="center">hive</h1>
<p align="center">The team layer for Claude. Every AI session across your team — captured, searchable, and available as Claude's working context.</p>

> **Full documentation:** [sabre-ai.github.io/hive](https://sabre-ai.github.io/hive/)

Design decisions, debugging sessions, architecture discussions, code reviews — your team's AI conversations hold context that doesn't make it into commits or docs. Hive captures it all and makes it searchable by Claude via MCP.

**Automatic cross-tool capture:** Claude Code and Claude Desktop conversations in one history, no setup per-session.

**Searchable by Claude:** Ask about past decisions, designs, and debugging context across your team's full history.

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

### Claude Code — automatic

Every Claude Code session is captured automatically via hooks. No manual steps — just use Claude Code as normal and hive records every conversation in the background.

### Claude Desktop — on demand

Claude Desktop has no hook system, so capture is on demand. When a conversation is worth keeping, tell Claude:

```
Save this conversation to hive
```

Claude calls the `capture_session` MCP tool and the conversation is stored. Save once at the end of a conversation — that captures the full thread. Claude Code sessions are always saved automatically.

---

Ask Claude: *"What did I work on today?"*

## Team Server

Ready to share sessions across your team? See the [Team Server guide](https://sabre-ai.github.io/hive/getting-started/team-server/) for setup, deployment, and Docker.

## What Claude Can Do

With the team server connected, Claude can answer questions across your entire team's history:

- *"Has anyone on the team built this before?"*
- *"What worked when Alice hit this last week?"*
- *"Show me the conversation that led to the payment service refactor"*

See the [MCP Tools Reference](https://sabre-ai.github.io/hive/reference/mcp-tools/) and [CLI Reference](https://sabre-ai.github.io/hive/reference/cli/) for the full list of tools and commands.

> **Developing hive?** See [Install from Source](https://sabre-ai.github.io/hive/getting-started/install-from-source/) for the git clone + venv workflow.

## License

Apache-2.0
