#!/usr/bin/env bash
set -euo pipefail

REPO="sabre-ai/hive"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/hive"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hive"
BIN_DIR="${HOME}/.local/bin"

info()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m  ✓\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m  !\033[0m %s\n" "$*"; }
fail()  { printf "\033[1;31m  ✗\033[0m %s\n" "$*"; exit 1; }

# ── Prerequisites ───────────────────────────────────────────────────

info "Checking prerequisites..."
command -v curl >/dev/null 2>&1 || fail "curl not found"

if ! command -v uv >/dev/null 2>&1; then
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv >/dev/null 2>&1 || fail "uv install failed"
    ok "uv installed"
fi
ok "Prerequisites found"

# ── Detect platform (for macOS-specific steps) ───────────────────

OS="$(uname -s)"

# ── Fetch latest release info ──────────────────────────────────────

info "Finding latest release..."
RELEASE_URL="https://api.github.com/repos/$REPO/releases/latest"
RELEASE_JSON=$(curl -sfL "$RELEASE_URL") || fail "Could not fetch release info. Check https://github.com/$REPO/releases"

WHEEL_URL=$(echo "$RELEASE_JSON" | grep -o '"browser_download_url": *"[^"]*\.whl"' | head -1 | cut -d'"' -f4)
[ -n "$WHEEL_URL" ] || fail "No .whl found in latest release"
ok "Found release"

# ── Download and install Python package ────────────────────────────

info "Installing hive Python package..."
WHEEL_NAME=$(basename "$WHEEL_URL")
TMP_WHEEL=$(mktemp -d)/"$WHEEL_NAME"
curl -sfL -o "$TMP_WHEEL" "$WHEEL_URL" || fail "Failed to download $WHEEL_NAME"
uv pip install --system "$TMP_WHEEL" || uv pip install "$TMP_WHEEL"
rm -f "$TMP_WHEEL"
ok "Python package installed"

# Verify hive is available
HIVE_BIN=$(command -v hive 2>/dev/null || true)
if [ -z "$HIVE_BIN" ]; then
    for candidate in "$BIN_DIR/hive" "$HOME/.local/pipx/venvs/hive-team/bin/hive"; do
        if [ -x "$candidate" ]; then
            HIVE_BIN="$candidate"
            break
        fi
    done
fi
[ -n "$HIVE_BIN" ] || fail "hive CLI not found after install. Ensure ~/.local/bin is on your PATH."
ok "hive CLI at $HIVE_BIN"

# ── Config ─────────────────────────────────────────────────────────

info "Setting up hive config..."
mkdir -p "$DATA_DIR" "$CONFIG_DIR"

CONFIG_FILE="$CONFIG_DIR/config.toml"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" <<TOML
# hive configuration
# watch_path = "~/.claude/projects/"
# server_port = 3000
TOML
    ok "Created $CONFIG_FILE"
else
    ok "Config already exists at $CONFIG_FILE"
fi

# ── Configure Claude Code MCP ─────────────────────────────────────

info "Configuring Claude Code MCP server..."
if command -v claude >/dev/null 2>&1; then
    if claude mcp add --scope user --transport stdio hive -- "$HIVE_BIN" mcp 2>/dev/null; then
        ok "Claude Code MCP server configured"
    else
        warn "claude mcp add returned an error (hive may already be configured)"
        ok "Verify with: claude mcp list"
    fi
else
    warn "claude CLI not found — skipping Claude Code MCP setup"
    echo "    To configure later: claude mcp add --scope user --transport stdio hive -- $HIVE_BIN mcp"
fi

# ── Configure Claude Desktop MCP (macOS) ──────────────────────────

if [ "$OS" = "Darwin" ]; then
    info "Configuring Claude Desktop MCP server..."
    CLAUDE_DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

    RESULT=$(python3 -c "
import json, os, sys

config_path = sys.argv[1]
hive_bin = sys.argv[2]

hive_entry = {'command': hive_bin, 'args': ['mcp']}

if os.path.isfile(config_path):
    with open(config_path) as f:
        text = f.read().strip()
        config = json.loads(text) if text else {}
else:
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    config = {}

servers = config.setdefault('mcpServers', {})
if servers.get('hive') == hive_entry:
    print('already_configured')
else:
    servers['hive'] = hive_entry
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
        f.write('\n')
    print('configured')
" "$CLAUDE_DESKTOP_CONFIG" "$HIVE_BIN" 2>&1) || true

    case "$RESULT" in
        already_configured) ok "Claude Desktop MCP already configured" ;;
        configured)         ok "Claude Desktop MCP configured" ;;
        *)
            warn "Could not configure Claude Desktop automatically"
            echo "    Add to $CLAUDE_DESKTOP_CONFIG:"
            echo "    {\"mcpServers\": {\"hive\": {\"command\": \"$HIVE_BIN\", \"args\": [\"mcp\"]}}}"
            ;;
    esac
fi

# ── Done ───────────────────────────────────────────────────────────

echo ""
info "Installation complete!"
echo ""
echo "  hive CLI:  $HIVE_BIN"
echo "  config:    $CONFIG_FILE"
echo ""
echo "  ── Enable capture for a project ──────────────────────────"
echo ""
echo "  hive captures sessions per-project. To start capturing in a project:"
echo ""
echo "    cd /path/to/your-project"
echo "    hive init"
echo ""
echo "  This installs Claude Code hooks, a git post-commit hook, and"
echo "  backfills any existing sessions. Repeat for each project you"
echo "  want to track."
echo ""
echo "  ── Restart Claude ────────────────────────────────────────"
echo ""
echo "  Restart Claude Code and Claude Desktop to pick up the new"
echo "  MCP server. Then verify by typing /mcp in Claude Code —"
echo "  you should see 'hive' listed."
echo ""
echo "  ── Try it ────────────────────────────────────────────────"
echo ""
echo "    hive log                  # see captured sessions"
echo "    hive search \"auth\"        # full-text search"
echo ""
echo "  Or ask Claude: \"What did I work on today?\""
echo ""
