# Upgrading Hive

## Re-run the installer

```bash
curl https://sabre-ai.github.io/hive/install.sh | bash
```

The installer is idempotent — it downloads the latest release, upgrades the package, and preserves your existing config and MCP settings.

## Installed from source?

If you installed from source for development:

```bash
cd /path/to/hive
git pull
pip install -e .
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

## Verify

```bash
hive log -n 3        # confirm sessions are still accessible
hive search "test"   # confirm search works
```
