# Installation

## Quick Start

=== "pipx (recommended)"

    ```bash
    pipx install hive-team
    ```

    This installs `hive` in an isolated environment and adds it to your `PATH`.

=== "pip"

    ```bash
    pip install hive-team
    ```

=== "From source"

    ```bash
    git clone https://github.com/sabre-ai/hive.git
    cd hive
    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    ```

=== "One-liner"

    ```bash
    curl -fsSL https://raw.githubusercontent.com/sabre-ai/hive/main/install.sh | bash
    ```

    Requires `uv` to be installed. The script creates a virtual environment and installs hive automatically.

Verify the installation:

```bash
hive --help
```

## Prerequisites

- **Python 3.11+** is required. Check your version with `python3 --version`.
- **Git** should be installed for commit-linking enrichment.

## Search Extras

Hive uses **sqlite-vec** as the default search backend. It runs in-process and does not require any external services or model assets.

To enable it, install the search extras:

```bash
pip install "hive-team[search]"
```

!!! note "Optional: Witchcraft backend"
    The older `witchcraft` search backend requires separate model assets. Most users should stick with `sqlite-vec`. See [Configuration](configuration.md) for backend settings.

## Troubleshooting

### `command not found: hive`

The `hive` binary is not on your `PATH`. If you used `pip install`, the scripts directory may not be in your `PATH`.

```bash
# Find where pip installed the binary
python -m site --user-base
# Add the bin directory to your PATH, e.g.:
export PATH="$HOME/.local/bin:$PATH"
```

With `pipx`, this is handled automatically.

### `ModuleNotFoundError: No module named 'tomllib'`

You are running Python 3.10 or earlier. Hive requires Python 3.11+.

```bash
python3 --version  # Must be 3.11 or higher
```

### `sqlite3.OperationalError: no such module: fts5`

Your Python installation was compiled without FTS5 support. This is uncommon on macOS and most Linux distributions but can happen with custom builds.

```bash
# On Ubuntu/Debian, install the full SQLite package:
sudo apt install libsqlite3-dev
# Then rebuild Python or use the system package manager's Python
```

### Permission errors on `~/.config/hive/`

Hive stores its config at `~/.config/hive/config.toml` and its database at `~/.local/share/hive/store.db`. Ensure your user owns these directories:

```bash
mkdir -p ~/.config/hive ~/.local/share/hive
```

### `pip install "hive-team[search]"` fails

The `sqlite-vec` package requires a C compiler for building native extensions. On macOS, install Xcode command-line tools:

```bash
xcode-select --install
```

On Ubuntu/Debian:

```bash
sudo apt install build-essential
```

## Next Steps

Once installed, proceed to [Configuration](configuration.md) to set up hive, or jump straight to [Your First Session](first-session.md).
