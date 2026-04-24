# FAQ

??? question "Does hive send any data off my machine in solo mode?"
    **No.** In solo mode, everything stays local. Sessions are stored in `~/.local/share/hive/store.db` on your machine. No network calls, no telemetry, no phoning home. Data only leaves your laptop if you explicitly enable sharing to a team server.

??? question "What's the difference between `store.db` and `server.db`?"
    `store.db` is your **local** database — every captured session lives here. `server.db` only exists if you run a team server. When you opt in to sharing, sessions are pushed from your local `store.db` to the team `server.db`. In solo mode, `server.db` doesn't exist.

??? question "Are my secrets safe?"
    Hive scrubs secrets (API keys, tokens, passwords) from session content before storage using 25+ regex patterns. When sharing is enabled, scrubbing runs again before anything leaves your machine. See [Security & Privacy](../security.md) for details.
