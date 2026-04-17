#!/usr/bin/env bash
set -euo pipefail

REPO="sabre-ai/hive"
HIVE_INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/hive"
DATA_DIR="$HIVE_INSTALL_DIR"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/hive"
BIN_DIR="${HOME}/.local/bin"
BINARY="$BIN_DIR/hive-search"
ASSETS_DIR="$HIVE_INSTALL_DIR/assets"
PLIST_LABEL="com.sabre-ai.hive-search"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

info()  { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m  ✓\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m  !\033[0m %s\n" "$*"; }
fail()  { printf "\033[1;31m  ✗\033[0m %s\n" "$*"; exit 1; }

# ── Prerequisites ───────────────────────────────────────────────────

info "Checking prerequisites..."
command -v uv    >/dev/null 2>&1 || fail "uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
command -v curl  >/dev/null 2>&1 || fail "curl not found"
ok "Prerequisites found"

# ── Detect platform ────────────────────────────────────────────────

OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS-$ARCH" in
    Darwin-arm64)  ARTIFACT="hive-search-darwin-arm64" ;;
    Darwin-x86_64) ARTIFACT="hive-search-darwin-x64"   ;;
    Linux-x86_64)  ARTIFACT="hive-search-linux-x64"    ;;
    *) fail "Unsupported platform: $OS-$ARCH" ;;
esac
ok "Platform: $OS $ARCH ($ARTIFACT)"

# ── Clone or update repo ──────────────────────────────────────────

REPO_DIR="$HIVE_INSTALL_DIR/repo"

if [ -d "$REPO_DIR/.git" ]; then
    info "Updating hive repo..."
    git -C "$REPO_DIR" pull --ff-only 2>/dev/null || true
    ok "Repo updated"
else
    info "Cloning hive repo..."
    mkdir -p "$HIVE_INSTALL_DIR"
    git clone "https://github.com/$REPO.git" "$REPO_DIR"
    ok "Cloned to $REPO_DIR"
fi

# ── Install Python package ─────────────────────────────────────────

info "Installing hive Python package..."
cd "$REPO_DIR"
uv sync --dev
ok "Python package installed"

# ── Download hive-search binary ────────────────────────────────────

if [ -f "$BINARY" ]; then
    ok "hive-search binary already installed"
else
    info "Downloading hive-search binary..."
    mkdir -p "$BIN_DIR"

    # Try latest release first
    DOWNLOAD_URL="https://github.com/$REPO/releases/latest/download/$ARTIFACT"
    HTTP_CODE=$(curl -sL -o "$BINARY" -w "%{http_code}" "$DOWNLOAD_URL")

    if [ "$HTTP_CODE" = "200" ] && [ -s "$BINARY" ]; then
        chmod +x "$BINARY"
        ok "Downloaded $ARTIFACT"
    else
        rm -f "$BINARY"
        # Fall back to building from source if cargo is available
        if command -v cargo >/dev/null 2>&1; then
            warn "No pre-built binary found — building from source..."
            cd "$REPO_DIR/hive-server"

            FEATURES="t5-quantized,progress"
            if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
                FEATURES="$FEATURES,metal"
            fi

            cargo build --release --features "$FEATURES"
            cp "target/release/hive-search" "$BINARY"
            chmod +x "$BINARY"
            ok "Built from source"
        else
            fail "No pre-built binary and cargo not found. Either tag a release or install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
        fi
    fi
fi

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
        "$REPO_DIR/../witchcraft" \
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
cd "$REPO_DIR"
uv run hive init --project "$HOME" <<< "n" 2>/dev/null || uv run hive init --project "$HOME" || true
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
    cd "$REPO_DIR"
    uv run hive reindex
else
    warn "Search server not ready yet — run 'uv run hive reindex' once it starts"
fi

# ── Done ───────────────────────────────────────────────────────────

echo ""
info "Installation complete!"
echo ""
echo "  hive CLI:       cd $REPO_DIR && uv run hive search \"your query\""
echo "  search server:  http://localhost:3033/health"
echo "  logs:           $LOG_DIR/hive-search.log"
echo "  config:         $CONFIG_FILE"
echo ""
if [ "$OS" = "Darwin" ]; then
    echo "  To stop:      launchctl bootout gui/$(id -u)/$PLIST_LABEL"
    echo "  To uninstall: rm $PLIST_PATH && launchctl bootout gui/$(id -u)/$PLIST_LABEL"
fi
