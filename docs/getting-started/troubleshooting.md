# Troubleshooting

??? tip "`command not found: hive`"
    **Installed in a venv?** Activate it first:
    `source /path/to/hive/.venv/bin/activate`

    **Installed with pipx?** Run `pipx ensurepath` and open a new terminal.

    **Installed with pip --user?**
    ```bash
    python -m site --user-base    # find the install prefix
    export PATH="$HOME/.local/bin:$PATH"
    ```

??? tip "`ModuleNotFoundError: No module named 'tomllib'`"
    You need Python 3.11+. Check with `python3 --version`.

??? tip "`sqlite3.OperationalError: no such module: fts5`"
    Your Python was built without FTS5. On Ubuntu: `sudo apt install libsqlite3-dev` and rebuild Python.

??? tip "Sessions not appearing on the team server"
    Run `hive config sharing on` and check `.hive/config.toml` has `sharing = "on"`. Verify the server URL with `curl`.
