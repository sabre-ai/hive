# Upgrading Hive

## Pull and reinstall

If you installed from source (venv):

```bash
cd /path/to/hive
git pull
pip install -e .
```

If you installed with pipx (for Claude Desktop):

```bash
pipx install --force /path/to/hive
```

## Post-upgrade

Run `hive init` in any project to apply database migrations and update hooks:

```bash
cd your-project
hive init
```

This is safe to run multiple times — it only applies pending migrations and updates hooks to the latest version.

## Restart Claude Code and Claude Desktop

After upgrading, restart **Claude Code** and **Claude Desktop** so their MCP
server subprocesses pick up the new code. The old version stays in memory until
you restart.

> **Note:** Claude Desktop uses its own pipx install, so make sure you run
> `pipx install --force /path/to/hive` (see above) before restarting — otherwise
> it will still run the old version.

## Rebuild the search index

If the upgrade includes changes to how sessions are indexed, rebuild the semantic search index:

```bash
hive reindex
```

This re-embeds all sessions. It may take a few minutes depending on your session count.

## Verify

```bash
hive log -n 3        # confirm sessions are still accessible
hive search "test"   # confirm search works
```
