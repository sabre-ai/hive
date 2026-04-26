# Install from Source

For developers who want to contribute to hive or run from the latest source.

## Clone and install

```bash
git clone https://github.com/sabre-ai/hive.git
cd hive
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

!!! warning "venv installs are terminal-specific"
    The `hive` command only works while the venv is active. Each new terminal
    needs `source /path/to/hive/.venv/bin/activate`. For a global install
    (works in all terminals), use `pipx install /path/to/hive` instead.

## Configure Claude Code MCP

Register hive as an MCP server so Claude can search your history:

```bash
claude mcp add --scope user --transport stdio hive -- /path/to/hive/.venv/bin/hive mcp
```

Restart Claude Code and verify with `/mcp`.

## Configure Claude Desktop (optional)

Claude Desktop is sandboxed on macOS and cannot access `~/Documents/`. Install hive with pipx so the binary lives outside the sandbox:

```bash
pipx install /path/to/hive
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

## Enable capture for a project

```bash
cd your-project
hive init
```

## Development commands

```bash
# Run tests
pytest tests/ -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Start the server
hive serve --port 3000
```
