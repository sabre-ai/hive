#!/usr/bin/env bash
set -euo pipefail

REPO="sabre-ai/hive"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/hive"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hive"
BIN_DIR="${HOME}/.local/bin"
BINARY="$BIN_DIR/hive-search"
ASSETS_DIR="$DATA_DIR/assets"
PLIST_LABEL="com.sabre-ai.hive-search"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

info()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m  ✓\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m  !\033[0m %s\n" "$*"; }
fail()  { printf "\033[1;31m  ✗\033[0m %s\n" "$*"; exit 1; }

# ── Prerequisites ───────────────────────────────────────────────────

info "Checking prerequisites..."
command -v uv   >/dev/null 2>&1 || fail "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v curl >/dev/null 2>&1 || fail "curl not found"
ok "Prerequisites found"

# ── Detect platform ────────────────────────────────────────────────

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS-$ARCH" in
    Darwin-arm64) ARTIFACT="hive-search-darwin-arm64" ;;
    Linux-x86_64) ARTIFACT="hive-search-linux-x64"    ;;
    *) fail "Unsupported platform: $OS-$ARCH" ;;
esac
ok "Platform: $OS $ARCH"

# ── Fetch latest release info ──────────────────────────────────────

info "Finding latest release..."
RELEASE_URL="https://api.github.com/repos/$REPO/releases/latest"
RELEASE_JSON=$(curl -sfL "$RELEASE_URL") || fail "Could not fetch release info. Check https://github.com/$REPO/releases"

# Extract download URLs
BINARY_URL=$(echo "$RELEASE_JSON" | grep -o "\"browser_download_url\": *\"[^\"]*$ARTIFACT\"" | head -1 | cut -d'"' -f4)
WHEEL_URL=$(echo "$RELEASE_JSON" | grep -o '"browser_download_url": *"[^"]*\.whl"' | head -1 | cut -d'"' -f4)

[ -n "$BINARY_URL" ] || fail "No $ARTIFACT found in latest release"
[ -n "$WHEEL_URL" ]   || fail "No .whl found in latest release"
ok "Found release artifacts"

# ── Download and install hive-search binary ────────────────────────

info "Installing hive-search binary..."
mkdir -p "$BIN_DIR"
curl -sfL -o "$BINARY" "$BINARY_URL" || fail "Failed to download $ARTIFACT"
chmod +x "$BINARY"
ok "Installed to $BINARY"

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
    # Try common uv/pip locations
    for candidate in "$HOME/.local/bin/hive" "$HOME/.local/pipx/venvs/hive-team/bin/hive"; do
        if [ -x "$candidate" ]; then
            HIVE_BIN="$candidate"
            break
        fi
    done
fi
[ -n "$HIVE_BIN" ] || fail "hive CLI not found after install. Ensure ~/.local/bin is on your PATH."
ok "hive CLI at $HIVE_BIN"

# ── Model assets ────────────────────────────────────────────────────

if [ -f "$ASSETS_DIR/xtr.gguf" ]; then
    ok "Model assets already present"
else
    info "Obtaining T5 model assets (~60MB)..."
    mkdir -p "$ASSETS_DIR"

    FOUND=false
    for candidate in \
        "${WITCHCRAFT_DIR:-}" \
        "$HOME/dev/witchcraft" \
    ; do
        if [ -n "$candidate" ] && [ -f "$candidate/assets/xtr.gguf" ]; then
            cp "$candidate/assets"/{config.json,tokenizer.json,xtr.gguf} "$ASSETS_DIR/"
            ok "Copied assets from $candidate/assets"
            FOUND=true
            break
        fi
    done

    if [ "$FOUND" = false ]; then
        echo ""
        echo "  Model assets not found. Generate them from the witchcraft repo:"
        echo ""
        echo "    git clone https://github.com/dropbox/witchcraft.git"
        echo "    cd witchcraft && make download"
        echo "    export WITCHCRAFT_DIR=\$(pwd)"
        echo ""
        echo "  Then re-run this installer."
        fail "Set WITCHCRAFT_DIR and re-run, or copy config.json, tokenizer.json, xtr.gguf into $ASSETS_DIR"
    fi
fi

# ── Config ─────────────────────────────────────────────────────────

info "Setting up hive config..."
mkdir -p "$DATA_DIR" "$CONFIG_DIR"

CONFIG_FILE="$CONFIG_DIR/config.toml"
if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" <<TOML
# hive configuration

[search]
url = "http://localhost:3033"
binary = "$BINARY"
assets_path = "$ASSETS_DIR"
TOML
    ok "Created $CONFIG_FILE"
else
    ok "Config already exists at $CONFIG_FILE"
fi

# ── hive init (DB + hooks) ─────────────────────────────────────────

info "Running hive init..."
"$HIVE_BIN" init --project "$HOME" <<< "n" 2>/dev/null || "$HIVE_BIN" init --project "$HOME" || true
ok "hive initialized"

# ── Launch hive-search as a persistent service ─────────────────────

info "Installing hive-search as a background service..."

SEARCH_DB="$DATA_DIR/search.db"
LOG_DIR="$DATA_DIR/logs"
mkdir -p "$LOG_DIR"

if [ "$OS" = "Darwin" ]; then
    mkdir -p "$(dirname "$PLIST_PATH")"
    cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BINARY</string>
        <string>--db-path</string>
        <string>$SEARCH_DB</string>
        <string>--assets</string>
        <string>$ASSETS_DIR</string>
        <string>--port</string>
        <string>3033</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/hive-search.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/hive-search.err</string>
</dict>
</plist>
PLIST

    launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
    ok "hive-search installed as launchd service (auto-starts on login)"
else
    if pgrep -f "hive-search.*--port 3033" >/dev/null 2>&1; then
        ok "hive-search already running"
    else
        nohup "$BINARY" --db-path "$SEARCH_DB" --assets "$ASSETS_DIR" --port 3033 \
            > "$LOG_DIR/hive-search.log" 2> "$LOG_DIR/hive-search.err" &
        ok "hive-search started (PID $!)"
        warn "Add to your init system for persistence across reboots"
    fi
fi

# ── Wait for server and reindex ────────────────────────────────────

info "Waiting for search server..."
for i in $(seq 1 60); do
    if curl -sf http://localhost:3033/health >/dev/null 2>&1; then
        ok "Search server ready"
        break
    fi
    sleep 0.5
done

if curl -sf http://localhost:3033/health >/dev/null 2>&1; then
    info "Reindexing existing sessions..."
    "$HIVE_BIN" reindex
else
    warn "Search server not ready yet — run 'hive reindex' once it starts"
fi

# ── Done ───────────────────────────────────────────────────────────

echo ""
info "Installation complete!"
echo ""
echo "  hive CLI:       hive search \"your query\""
echo "  search server:  http://localhost:3033/health"
echo "  logs:           $LOG_DIR/hive-search.log"
echo "  config:         $CONFIG_FILE"
echo ""
if [ "$OS" = "Darwin" ]; then
    echo "  To stop:      launchctl bootout gui/$(id -u)/$PLIST_LABEL"
    echo "  To uninstall: rm $PLIST_PATH && launchctl bootout gui/$(id -u)/$PLIST_LABEL"
fi
