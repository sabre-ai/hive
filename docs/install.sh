#!/usr/bin/env bash
set -euo pipefail

REPO="sabre-ai/hive"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hive"
BIN_DIR="${HOME}/.local/bin"

info()  { printf "\n\033[1;34m==>\033[0m \033[1m%s\033[0m\n" "$*"; }
ok()    { printf "    \033[1;32m✓\033[0m %s\n" "$*"; }
warn()  { printf "    \033[1;33m!\033[0m %s\n" "$*"; }
fail()  { printf "    \033[1;31m✗\033[0m %s\n" "$*"; exit 1; }
dim()   { printf "    \033[2m%s\033[0m\n" "$*"; }

# ── Prerequisites ───────────────────────────────────────────────────

info "Checking prerequisites"
command -v curl >/dev/null 2>&1 || fail "curl not found"

if ! command -v uv >/dev/null 2>&1; then
    dim "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
    export PATH="$BIN_DIR:$PATH"
    command -v uv >/dev/null 2>&1 || fail "uv install failed"
    ok "uv installed"
fi
ok "curl and uv found"

# ── Detect platform (for macOS-specific steps) ───────────────────

OS="$(uname -s)"

# ── Install hive ─────────────────────────────────────────────────

info "Installing hive"

dim "Fetching latest release..."
RELEASE_URL="https://api.github.com/repos/$REPO/releases/latest"
RELEASE_JSON=$(curl -sfL "$RELEASE_URL") || fail "Could not fetch release info. Check https://github.com/$REPO/releases"

WHEEL_URL=$(echo "$RELEASE_JSON" | grep -o '"browser_download_url": *"[^"]*\.whl"' | head -1 | cut -d'"' -f4)
[ -n "$WHEEL_URL" ] || fail "No .whl found in latest release"

dim "Downloading package..."
WHEEL_NAME=$(basename "$WHEEL_URL")
TMP_WHEEL=$(mktemp -d)/"$WHEEL_NAME"
curl -sfL -o "$TMP_WHEEL" "$WHEEL_URL" || fail "Failed to download $WHEEL_NAME"

dim "Installing..."
uv tool install --force --from "$TMP_WHEEL" hive-team 2>/dev/null || fail "Failed to install hive"
rm -f "$TMP_WHEEL"

# Verify hive is on PATH
export PATH="$BIN_DIR:$PATH"
HIVE_BIN=$(command -v hive 2>/dev/null || true)
if [ -z "$HIVE_BIN" ]; then
    for candidate in "$BIN_DIR/hive"; do
        if [ -x "$candidate" ]; then
            HIVE_BIN="$candidate"
            break
        fi
    done
fi
[ -n "$HIVE_BIN" ] || fail "hive CLI not found after install. Ensure ~/.local/bin is on your PATH."
ok "Installed hive at $HIVE_BIN"

# ── Config ─────────────────────────────────────────────────────────

info "Setting up config"
mkdir -p "$CONFIG_DIR"

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

info "Configuring MCP servers"
if command -v claude >/dev/null 2>&1; then
    if claude mcp add --scope user --transport stdio hive -- "$HIVE_BIN" mcp 2>/dev/null; then
        ok "Claude Code MCP configured"
    else
        warn "claude mcp add returned an error (hive may already be configured)"
        dim "Verify with: claude mcp list"
    fi
else
    warn "claude CLI not found — skipping Claude Code MCP"
    dim "To configure later:"
    dim "  claude mcp add --scope user --transport stdio hive -- $HIVE_BIN mcp"
fi

# ── Configure Claude Desktop MCP (macOS) ──────────────────────────

if [ "$OS" = "Darwin" ]; then
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
            dim "Add to $CLAUDE_DESKTOP_CONFIG:"
            dim "  {\"mcpServers\": {\"hive\": {\"command\": \"$HIVE_BIN\", \"args\": [\"mcp\"]}}}"
            ;;
    esac
fi

# ── Done ───────────────────────────────────────────────────────────

echo ""
printf "\033[1;32m══════════════════════════════════════════════════════════\033[0m\n"
printf "\033[1;32m  Installation complete!\033[0m\n"
printf "\033[1;32m══════════════════════════════════════════════════════════\033[0m\n"
echo ""
printf "  \033[1mhive CLI:\033[0m  %s\n" "$HIVE_BIN"
printf "  \033[1mconfig:\033[0m    %s\n" "$CONFIG_FILE"
echo ""
printf "\033[1;34m  ── Next steps ──────────────────────────────────────────\033[0m\n"
echo ""
printf "  \033[1m1. Enable capture for a project\033[0m\n"
echo ""
echo "     hive captures sessions per-project. To start capturing:"
echo ""
printf "     \033[36mcd /path/to/your-project\033[0m\n"
printf "     \033[36mhive init\033[0m\n"
echo ""
echo "     This installs Claude Code hooks, a git post-commit hook,"
echo "     and backfills any existing sessions. Repeat for each project."
echo ""
printf "  \033[1m2. Restart Claude\033[0m\n"
echo ""
echo "     Restart Claude Code and Claude Desktop to pick up the MCP"
echo "     server. Verify by typing /mcp in Claude Code — you should"
echo "     see 'hive' listed."
echo ""
printf "  \033[1m3. Try it\033[0m\n"
echo ""
printf "     \033[36mhive log\033[0m                  # see captured sessions\n"
printf "     \033[36mhive search \"auth\"\033[0m        # full-text search\n"
echo ""
echo "     Or ask Claude: \"What did I work on today?\""
echo ""
