#!/usr/bin/env bash
set -euo pipefail

HIVE_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/hive"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hive"
ASSETS_DIR="$HIVE_DIR/hive-server/assets"
BINARY="$HIVE_DIR/hive-server/target/release/hive-search"
PLIST_LABEL="com.sabre-ai.hive-search"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

info()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m  ✓\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m  !\033[0m %s\n" "$*"; }
fail()  { printf "\033[1;31m  ✗\033[0m %s\n" "$*"; exit 1; }

# ── Prerequisites ───────────────────────────────────────────────────

info "Checking prerequisites..."

command -v uv   >/dev/null 2>&1 || fail "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v cargo >/dev/null 2>&1 || fail "cargo not found. Install: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
ok "uv and cargo found"

# ── Python package ──────────────────────────────────────────────────

info "Installing hive Python package..."
cd "$HIVE_DIR"
uv sync --dev
ok "Python package installed"

# ── Model assets ────────────────────────────────────────────────────

if [ -f "$ASSETS_DIR/xtr.gguf" ]; then
    ok "Model assets already present"
else
    info "Obtaining T5 model assets (~60MB)..."
    mkdir -p "$ASSETS_DIR"

    # Look for pre-built assets in the witchcraft repo
    FOUND=false
    for candidate in \
        "${WITCHCRAFT_DIR:-}" \
        "$HOME/dev/witchcraft" \
        "$HIVE_DIR/../witchcraft" \
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
        echo "    cd /path/to/witchcraft && make download"
        echo "    export WITCHCRAFT_DIR=/path/to/witchcraft"
        echo "    $0"
        echo ""
        fail "Set WITCHCRAFT_DIR and re-run, or copy config.json, tokenizer.json, xtr.gguf into $ASSETS_DIR"
    fi
fi

# ── Build Rust binary ──────────────────────────────────────────────

if [ -f "$BINARY" ]; then
    ok "hive-search binary already built"
else
    info "Building hive-search (this takes a few minutes the first time)..."
    cd "$HIVE_DIR/hive-server"

    FEATURES="t5-quantized,progress"
    # Enable Metal on Apple Silicon
    if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
        FEATURES="$FEATURES,metal"
    fi

    cargo build --release --features "$FEATURES"
    ok "hive-search built at $BINARY"
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
assets_path = "$ASSETS_DIR"
TOML
    ok "Created $CONFIG_FILE"
else
    ok "Config already exists at $CONFIG_FILE"
fi

# ── hive init (DB + hooks) ─────────────────────────────────────────

info "Running hive init..."
cd "$HIVE_DIR"
uv run hive init --project "$HIVE_DIR" <<< "n" 2>/dev/null || uv run hive init --project "$HIVE_DIR" || true
ok "hive initialized"

# ── Launch hive-search as a persistent service ─────────────────────

info "Installing hive-search as a background service..."

SEARCH_DB="$DATA_DIR/search.db"
LOG_DIR="$DATA_DIR/logs"
mkdir -p "$LOG_DIR"

if [ "$(uname -s)" = "Darwin" ]; then
    # macOS: use launchd
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

    # Stop existing service if running, then start
    launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
    ok "hive-search installed as launchd service (auto-starts on login)"
else
    # Linux: start in background
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
    cd "$HIVE_DIR"
    uv run hive reindex
else
    warn "Search server not ready yet — run 'hive reindex' once it starts"
fi

# ── Done ───────────────────────────────────────────────────────────

echo ""
info "Installation complete!"
echo ""
echo "  hive CLI:       uv run hive search \"your query\""
echo "  search server:  http://localhost:3033/health"
echo "  logs:           $LOG_DIR/hive-search.log"
echo "  config:         $CONFIG_FILE"
echo ""
echo "  To stop:        launchctl bootout gui/$(id -u)/$PLIST_LABEL"
echo "  To uninstall:   rm $PLIST_PATH && launchctl bootout gui/$(id -u)/$PLIST_LABEL"
