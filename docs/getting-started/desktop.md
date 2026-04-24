# Connect Claude Desktop

Sessions from Claude Desktop brainstorms become searchable alongside your Claude Code sessions.

!!! info "On-demand capture"
    Claude Code sessions are captured **automatically** via hooks. Claude Desktop has no hook system, so capture is **on demand** — you ask Claude to save conversations worth keeping. This is by design: not every brainstorm belongs in your project history.

Claude Desktop is sandboxed on macOS and cannot access `~/Documents/`. Install hive with pipx so the binary lives outside the sandbox:

```bash
pipx install /path/to/hive   # use the directory where you cloned hive
```

Then add hive as an MCP server in `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hive": {
      "command": "/Users/YOUR_USERNAME/.local/bin/hive",
      "args": ["mcp"]
    }
  }
}
```

!!! note "Picking up source changes"
    Since this is a non-editable install, re-run `pipx install --force /path/to/hive` after making source changes to update the Claude Desktop copy.

**Save a conversation:** When a Desktop conversation is worth keeping, ask Claude:

```
Save this conversation to hive
```

Claude calls the `capture_session` MCP tool and the conversation is stored with source `claude_desktop`.

**Cross-tool lineage:** When Claude Code later references that design session during implementation, hive automatically links the two sessions. View the chain with:

```bash
hive lineage <session-id>
```

You now have unified history across Claude Code and Claude Desktop.

!!! tip "Team server access"
    Once you connect to a [team server](team-server.md), Claude Desktop automatically searches team-wide history too — no extra MCP configuration needed. The `server_url` in your global config applies to both Claude Code and Claude Desktop.

## Next Steps

- [Team Server](team-server.md) — share sessions across your team
- [Asking Claude](../tutorials/asking-claude.md) — MCP tools and prompt examples
