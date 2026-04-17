"""hive CLI — capture, search, and replay AI sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hive.config import HIVE_DIR, Config
from hive.store.db import init_db
from hive.store.query import QueryAPI

console = Console()


@click.group()
def cli():
    """hive — capture, enrich, store, and serve AI sessions."""
    pass


# ── init ────────────────────────────────────────────────────────────


@cli.command()
@click.option("--project", default=".", help="Project directory to set up hooks in")
def init(project: str):
    """Set up hive: create DB, install hooks, backfill sessions."""
    config = Config.load()
    project_path = Path(project).resolve()

    console.print("[bold]Setting up hive...[/bold]\n")

    # 1. Create ~/.hive/ and DB
    console.print("  Creating database...", end=" ")
    init_db(config)
    console.print("[green]✓[/green]")

    # 2. Create default config if missing
    config_path = HIVE_DIR / "config.toml"
    if not config_path.exists():
        config_path.write_text(
            '# hive configuration\n# watch_path = "~/.claude/projects/"\n# server_port = 3000\n'
        )
        console.print("  Created config.toml...", end=" ")
        console.print("[green]✓[/green]")

    # 3. Install Claude Code hooks
    _install_claude_hooks(project_path)

    # 4. Install git post-commit hook
    _install_git_hook(project_path)

    # 5. Ask about sharing
    from hive.config import ProjectConfig, load_project_config, save_project_config

    current_pc = load_project_config(project_path)
    if not current_pc.sharing:
        console.print("  Session sharing...", end=" ")
        enable = click.confirm("Enable sharing to team server?", default=False)
        if enable:
            save_project_config(project_path, ProjectConfig(sharing=True))
            console.print(f"    Server URL: {config.server_url}")
        else:
            save_project_config(project_path, ProjectConfig(sharing=False))
    else:
        console.print(f"  Sharing already enabled (server: {config.server_url})")

    # 6. Backfill existing sessions
    console.print("  Backfilling existing sessions...", end=" ")
    try:
        from hive.capture.claude_code import ClaudeCodeAdapter

        adapter = ClaudeCodeAdapter()
        count = adapter.backfill()
        console.print(f"[green]✓[/green] ({count} sessions)")
    except Exception as e:
        console.print(f"[yellow]skipped[/yellow] ({e})")

    # 7. Offer MCP setup
    console.print()
    _offer_mcp_setup()

    console.print("\n[bold green]hive is ready![/bold green]")
    console.print(f"  Database: {config.db_path}")
    console.print(f"  Config:   {config_path}")


def _install_claude_hooks(project_path: Path):
    """Install Claude Code hooks into .claude/settings.json."""
    console.print("  Installing Claude Code hooks...", end=" ")

    settings_dir = project_path / ".claude"
    settings_dir.mkdir(exist_ok=True)
    settings_file = settings_dir / "settings.json"

    settings: dict = {}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
        except json.JSONDecodeError:
            pass

    hooks = settings.setdefault("hooks", {})

    hook_defs = {
        "SessionStart": ["hive capture session-start"],
        "Stop": ["hive capture stop"],
        "PostToolUse": ["hive capture post-tool-use"],
        "PreCompact": ["hive capture pre-compact"],
    }

    for event, commands in hook_defs.items():
        existing = hooks.get(event, [])
        # Collect all commands already present across all matcher groups
        existing_cmds: set[str] = set()
        for group in existing:
            if isinstance(group, dict):
                for h in group.get("hooks", []):
                    if isinstance(h, dict):
                        existing_cmds.add(h.get("command", ""))
        # Build list of new hooks to add
        new_hooks = [
            {"type": "command", "command": cmd}
            for cmd in commands
            if cmd not in existing_cmds
        ]
        if new_hooks:
            existing.append({"matcher": "", "hooks": new_hooks})
        hooks[event] = existing

    settings["hooks"] = hooks
    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    console.print("[green]✓[/green]")


def _install_git_hook(project_path: Path):
    """Install post-commit git hook."""
    console.print("  Installing git post-commit hook...", end=" ")

    git_dir = project_path / ".git"
    if not git_dir.exists():
        console.print("[yellow]skipped[/yellow] (not a git repo)")
        return

    from hive.capture.git_hook import GitCommitHook

    try:
        hook = GitCommitHook()
        hook.install_hook(str(project_path))
        console.print("[green]✓[/green]")
    except FileNotFoundError:
        console.print("[yellow]skipped[/yellow] (no .git directory)")
    except Exception as e:
        console.print(f"[yellow]skipped[/yellow] ({e})")


def _offer_mcp_setup():
    """Offer to add hive MCP server to Claude Code config."""
    import shutil

    console.print("  MCP server configuration:")

    # Find the hive binary
    hive_bin = shutil.which("hive")
    if not hive_bin:
        hive_bin = "hive"

    console.print("    Run this command to register hive with Claude Code:")
    console.print(f"    [bold]claude mcp add --transport stdio hive -- {hive_bin} mcp[/bold]")
    console.print("    Then restart Claude Code and verify with /mcp")


# ── config ─────────────────────────────────────────────────────────


@cli.group(name="config")
def config_cmd():
    """Manage hive configuration."""
    pass


@config_cmd.command()
@click.argument("state", type=click.Choice(["on", "off"]))
@click.option("--project", default=".", help="Project directory")
def sharing(state: str, project: str):
    """Enable or disable session sharing for a project."""
    from hive.config import ProjectConfig, save_project_config

    project_path = Path(project).resolve()
    pc = ProjectConfig(sharing=(state == "on"))
    save_project_config(project_path, pc)
    status = "enabled" if pc.sharing else "disabled"
    console.print(f"[green]Sharing {status} for {project_path}[/green]")


# ── capture (called by hooks) ──────────────────────────────────────


@cli.command()
@click.argument("event_name")
def capture(event_name: str):
    """Capture a hook event (called by Claude Code hooks)."""
    # Map CLI kebab-case to PascalCase event names
    event_map = {
        "session-start": "SessionStart",
        "stop": "Stop",
        "post-tool-use": "PostToolUse",
        "pre-compact": "PreCompact",
    }
    normalized = event_map.get(event_name, event_name)

    data = {}
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                pass

    from hive.capture.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    adapter.handle(normalized, data)


# ── search ──────────────────────────────────────────────────────────


@cli.command()
@click.argument("query")
@click.option("--project", help="Filter by project path")
@click.option("--author", help="Filter by author")
@click.option("--since", help="Sessions after this date (YYYY-MM-DD)")
@click.option("--until", help="Sessions before this date (YYYY-MM-DD)")
def search(
    query: str, project: str | None, author: str | None, since: str | None, until: str | None
):
    """Full-text search across sessions."""
    api = QueryAPI()
    results = api.search_sessions(query, project=project, author=author, since=since, until=until)

    if not results:
        console.print("[dim]No results found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", max_width=12)
    table.add_column("Date", style="green")
    table.add_column("Author")
    table.add_column("Source")
    table.add_column("Summary", max_width=50)
    table.add_column("Match", max_width=40)

    for r in results:
        table.add_row(
            r["id"][:12],
            str(r.get("started_at", ""))[:10],
            r.get("author", ""),
            r.get("source", ""),
            r.get("summary", ""),
            r.get("snippet", ""),
        )

    console.print(table)


# ── show ────────────────────────────────────────────────────────────


@cli.command()
@click.argument("session_id")
@click.option("--expand-tools", is_flag=True, help="Expand tool use messages")
def show(session_id: str, expand_tools: bool):
    """Show a session in detail."""
    api = QueryAPI()
    session = api.get_session(session_id, detail="messages")

    if not session:
        # Try prefix match
        sessions = api.list_sessions(limit=100)
        matches = [s for s in sessions if s["id"].startswith(session_id)]
        if len(matches) == 1:
            session = api.get_session(matches[0]["id"], detail="messages")
        else:
            console.print(f"[red]Session not found: {session_id}[/red]")
            return

    # Header
    console.print(
        Panel(
            f"[bold]{session.get('summary', 'No summary')}[/bold]\n"
            f"Source: {session.get('source', '')}  |  "
            f"Author: {session.get('author', '')}  |  "
            f"Messages: {session.get('message_count', 0)}\n"
            f"Started: {session.get('started_at', '')}  |  "
            f"Ended: {session.get('ended_at', '')}",
            title=f"Session {session['id'][:12]}",
            border_style="cyan",
        )
    )

    # Enrichments
    enrichments = session.get("enrichments", {})
    if enrichments:
        console.print("\n[bold]Enrichments:[/bold]")
        for key, value in enrichments.items():
            val = str(value).replace("[", "\\[")
            console.print(f"  [dim]{key}[/dim]: {val}")

    # Annotations
    annotations = session.get("annotations", [])
    if annotations:
        console.print("\n[bold]Annotations:[/bold]")
        for a in annotations:
            icon = {"tag": "🏷", "comment": "💬", "rating": "⭐"}.get(a["type"], "•")
            console.print(f"  {icon} [{a['type']}] {a['value']} — {a.get('author', '')}")

    # Messages
    console.print("\n[bold]Messages:[/bold]\n")
    for msg in session.get("messages", []):
        role = msg["role"]
        color = {"human": "green", "assistant": "blue", "tool": "yellow"}.get(role, "white")

        if role == "tool" and not expand_tools:
            tool = msg.get("tool_name", "tool")
            console.print(f"  [dim][{tool}] (use --expand-tools to see)[/dim]")
            continue

        prefix = {"human": "▶ Human", "assistant": "◀ Assistant", "tool": "⚙ Tool"}.get(role, role)
        tool_suffix = f" ({msg.get('tool_name', '')})" if msg.get("tool_name") else ""

        console.print(f"  [{color}]{prefix}{tool_suffix}[/{color}]")
        content = msg.get("content", "")
        if content:
            for line in content.split("\n")[:20]:
                console.print(f"    {line}")
            if content.count("\n") > 20:
                console.print(f"    [dim]... ({content.count(chr(10)) - 20} more lines)[/dim]")
        console.print()


# ── lineage ─────────────────────────────────────────────────────────


@cli.command()
@click.argument("file_path")
def lineage(file_path: str):
    """Show sessions linked to a file via the edges graph."""
    api = QueryAPI()
    resolved = str(Path(file_path).resolve())
    edges = api.get_lineage(resolved, id_type="file")

    if not edges:
        console.print(f"[dim]No lineage found for {file_path}[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Date", style="green")
    table.add_column("Summary", max_width=50)
    table.add_column("Commit", style="cyan", max_width=10)
    table.add_column("Author")
    table.add_column("Relationship")

    for e in edges:
        # New aggregated format from file lineage
        commits = e.get("commit_shas", "") or ""
        first_commit = commits.split(",")[0][:8] if commits else ""
        relationships = e.get("relationships", "") or e.get("relationship", "")

        table.add_row(
            str(e.get("started_at", ""))[:10],
            e.get("summary", ""),
            first_commit,
            e.get("author", ""),
            relationships,
        )

    console.print(table)


# ── projects ────────────────────────────────────────────────────────


@cli.command()
def projects():
    """List all known projects with session counts."""
    api = QueryAPI()
    results = api.list_projects()

    if not results:
        console.print("[dim]No projects found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Project", style="cyan", min_width=40)
    table.add_column("Sessions", justify="right")
    table.add_column("Messages", justify="right")
    table.add_column("Last Active", style="green")

    for p in results:
        path = p["project_path"]
        # Show shortened path for readability
        short = path.replace(str(Path.home()), "~") if path else ""
        table.add_row(
            short,
            str(p.get("session_count", 0)),
            str(p.get("total_messages", 0)),
            str(p.get("last_active", ""))[:10],
        )

    console.print(table)


# ── stats ───────────────────────────────────────────────────────────


@cli.command()
@click.option("--project", help="Filter by project path")
@click.option("--since", help="Sessions after this date (YYYY-MM-DD)")
def stats(project: str | None, since: str | None):
    """Show aggregated session statistics."""
    api = QueryAPI()
    result = api.get_stats(project=project, since=since)

    # Token stats
    tokens = api.get_token_stats(project=project, since=since)

    def _fmt(n: int | None) -> str:
        if n is None or n == 0:
            return "—"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    avg_msgs = result.get("avg_messages")
    avg_str = f"{avg_msgs:.1f}" if avg_msgs else "—"

    console.print(
        Panel(
            f"[bold]Total sessions:[/bold] {result.get('total_sessions', 0)}\n"
            f"[bold]Total messages:[/bold] {result.get('total_messages', 0)}\n"
            f"[bold]Avg messages/session:[/bold] {avg_str}\n"
            f"[bold]Date range:[/bold] {result.get('earliest', 'N/A')} → {result.get('latest', 'N/A')}",
            title="Session Statistics",
            border_style="cyan",
        )
    )

    if tokens:
        console.print("\n[bold]Token Usage:[/bold]")
        console.print(f"  Input tokens:          {_fmt(tokens.get('input_tokens'))}")
        console.print(f"  Output tokens:         {_fmt(tokens.get('output_tokens'))}")
        console.print(f"  Cache read tokens:     {_fmt(tokens.get('cache_read_input_tokens'))}")
        console.print(f"  Cache creation tokens: {_fmt(tokens.get('cache_creation_input_tokens'))}")
        console.print(f"  [bold]Total tokens:          {_fmt(tokens.get('total_tokens'))}[/bold]")

    quality = result.get("quality", {})
    if quality:
        console.print("\n[bold]Quality Metrics:[/bold]")
        for key, vals in quality.items():
            console.print(f"  {key}: avg={vals['avg']:.2f}, total={vals['total']:.0f}")


# ── log ─────────────────────────────────────────────────────────────


@cli.command(name="log")
@click.option("--project", help="Filter by project path")
@click.option("-n", "--count", default=20, help="Number of sessions to show")
def log_cmd(project: str | None, count: int):
    """Show recent sessions (like git log for thinking)."""
    api = QueryAPI()
    sessions = api.list_sessions(project=project, limit=count)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    for s in sessions:
        sid = s["id"][:12]
        date = str(s.get("started_at", ""))[:16]
        summary = s.get("summary", "No summary")
        source = s.get("source", "")
        msg_count = s.get("message_count", 0)
        tags = s.get("tags", "")

        console.print(
            f"[cyan]{sid}[/cyan] [green]{date}[/green] [dim]{source}[/dim] ({msg_count} msgs)"
        )
        console.print(f"  {summary}")
        if tags:
            console.print(f"  [yellow]tags: {tags}[/yellow]")
        console.print()


# ── tag ─────────────────────────────────────────────────────────────


@cli.command()
@click.argument("session_id")
@click.argument("tag_value")
def tag(session_id: str, tag_value: str):
    """Add a tag to a session."""
    api = QueryAPI()
    api.write_annotation(session_id, "tag", tag_value)
    console.print(f"[green]Tagged {session_id[:12]} with '{tag_value}'[/green]")


# ── delete ─────────────────────────────────────────────────────────


@cli.command()
@click.argument("session_id")
def delete(session_id: str):
    """Delete a session from the local store."""
    api = QueryAPI()
    if api.delete_session(session_id):
        console.print(f"[green]Deleted session {session_id[:12]}[/green]")
    else:
        console.print(f"[red]Session not found: {session_id}[/red]")


# ── push ──────────────────────────────────────────────────────────


@cli.command()
@click.option("--project", help="Only push sessions from this project")
@click.option("--since", help="Only push sessions after this date (YYYY-MM-DD)")
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without pushing")
def push(project: str | None, since: str | None, dry_run: bool):
    """Push local sessions to the team server."""
    import httpx

    from hive.privacy import scrub_payload

    config = Config.load()
    local_api = QueryAPI()
    sessions = local_api.list_sessions(project=project, since=since, limit=10000)

    if not sessions:
        console.print("[dim]No sessions to push.[/dim]")
        return

    console.print(f"Found [bold]{len(sessions)}[/bold] sessions to push to {config.server_url}")

    if dry_run:
        for s in sessions:
            sid = s["id"][:12]
            summary = (s.get("summary") or "No summary")[:60]
            msgs = s.get("message_count", 0)
            console.print(f"  [cyan]{sid}[/cyan] ({msgs} msgs) {summary}")
        console.print("\n[dim]Dry run — nothing pushed. Remove --dry-run to push.[/dim]")
        return

    pushed = 0
    failed = 0
    skipped = 0

    with httpx.Client(timeout=60) as client:
        # Check server health first
        try:
            r = client.get(f"{config.server_url}/")
            r.raise_for_status()
        except Exception:
            console.print(f"[red]Cannot connect to server at {config.server_url}[/red]")
            console.print("[dim]Is 'hive serve' running?[/dim]")
            return

        for s in sessions:
            sid = s["id"]
            payload = local_api.export_session(sid)
            if not payload:
                skipped += 1
                continue

            payload = scrub_payload(payload, config)

            try:
                r = client.post(
                    f"{config.server_url}/api/sessions",
                    json=payload,
                )
                r.raise_for_status()
                pushed += 1
                console.print(f"  [green]✓[/green] {sid[:12]} — {(s.get('summary') or '')[:50]}")
            except Exception as e:
                failed += 1
                console.print(f"  [red]✗[/red] {sid[:12]} — {e}")

    console.print(f"\n[bold]Pushed {pushed}, skipped {skipped}, failed {failed}[/bold]")


# ── serve ───────────────────────────────────────────────────────────


@cli.command()
@click.option("--port", default=None, type=int, help="Port (default from config or 3000)")
def serve(port: int | None):
    """Start the team server."""
    import uvicorn

    from hive.serve.api import create_app
    from hive.store.db import init_db

    config = Config.load()
    actual_port = port or config.server_port

    # Initialize server database
    init_db(config, db_path=config.server_db_path)

    console.print(f"[bold]Starting hive server on http://0.0.0.0:{actual_port}[/bold]")
    console.print(f"  Server DB: {config.server_db_path}")
    app = create_app(config=config, db_path=config.server_db_path)
    uvicorn.run(app, host="0.0.0.0", port=actual_port, log_level="info")


# ── mcp ─────────────────────────────────────────────────────────────


@cli.command()
def mcp():
    """Start the MCP server (stdio)."""
    import asyncio

    from hive.mcp_server import main as mcp_main

    asyncio.run(mcp_main())


if __name__ == "__main__":
    cli()
