"""hive CLI — capture, search, and replay AI sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hive.config import Config
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

    console.print("\n  [#E8A317]h›[/#E8A317]  [bold]hive[/bold]\n")

    # 1. Create ~/.hive/ and DB
    console.print("  Creating database...", end=" ")
    init_db(config)
    console.print("[green]✓[/green]")

    # 2. Create default config if missing
    from hive.config import HIVE_CONFIG_DIR

    config_path = HIVE_CONFIG_DIR / "config.toml"
    if not config_path.exists():
        HIVE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
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
    count = 0
    console.print("  Backfilling existing sessions...", end=" ")
    try:
        from hive.capture.claude_code import ClaudeCodeAdapter

        adapter = ClaudeCodeAdapter()
        count = adapter.backfill(project=project_path)
        console.print(f"[green]✓[/green] ({count} sessions)")
    except Exception as e:
        console.print(f"[yellow]skipped[/yellow] ({e})")

    # 7. Offer MCP setup
    console.print()
    _offer_mcp_setup()

    console.print("\n[bold green]hive is ready![/bold green]")
    console.print(f"  Database: {config.db_path}")
    console.print(f"  Config:   {config_path}")

    # 8. Build search index in background
    if count > 0:
        import shutil
        import subprocess

        hive_bin = shutil.which("hive")
        if hive_bin:
            console.print(
                f"\n  [dim]Indexing {count} sessions for search in the background."
                " Search results may be incomplete until indexing finishes.[/dim]"
            )
            subprocess.Popen(
                [hive_bin, "reindex"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )


def _install_claude_hooks(project_path: Path):
    """Install Claude Code hooks into .claude/settings.json."""
    import shutil

    console.print("  Installing Claude Code hooks...", end=" ")

    # Resolve the absolute path to the hive binary so hooks work outside the venv
    hive_bin = shutil.which("hive")
    if not hive_bin:
        # Fallback: look for 'hive' next to the current Python executable
        bin_dir = Path(sys.executable).parent
        candidate = bin_dir / "hive"
        hive_bin = str(candidate) if candidate.exists() else "hive"

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
        "SessionStart": [f"{hive_bin} capture session-start"],
        "Stop": [f"{hive_bin} capture stop"],
        "PostToolUse": [f"{hive_bin} capture post-tool-use"],
        "PreCompact": [f"{hive_bin} capture pre-compact"],
    }

    for event, commands in hook_defs.items():
        existing = hooks.get(event, [])
        # Remove any old hive capture hooks (bare or absolute-path)
        cleaned = []
        for group in existing:
            if isinstance(group, dict):
                non_hive = [
                    h
                    for h in group.get("hooks", [])
                    if not (isinstance(h, dict) and "hive capture" in h.get("command", ""))
                ]
                if non_hive:
                    cleaned.append({**group, "hooks": non_hive})
                # Drop groups that become empty after removing hive hooks
            else:
                cleaned.append(group)
        # Add fresh hive hooks
        cleaned.append(
            {"matcher": "", "hooks": [{"type": "command", "command": cmd} for cmd in commands]}
        )
        hooks[event] = cleaned

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
    """Show MCP setup instructions only if not already configured."""
    import shutil
    import subprocess

    hive_bin = shutil.which("hive") or "hive"

    # Check if Claude Code MCP is already configured
    mcp_configured = False
    if shutil.which("claude"):
        try:
            result = subprocess.run(
                ["claude", "mcp", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "hive" in result.stdout:
                mcp_configured = True
        except Exception:
            pass

    if not mcp_configured:
        console.print("  MCP server configuration:")
        console.print("    [bold]Claude Code:[/bold]")
        console.print(f"    claude mcp add --transport stdio hive -- {hive_bin} mcp")
        console.print("    Then restart Claude Code and verify with /mcp")
        console.print()
        console.print("    [bold]Claude Desktop (optional):[/bold]")
        console.print("    Add to ~/Library/Application Support/Claude/claude_desktop_config.json:")
        console.print(
            f'    {{"mcpServers": {{"hive": {{"command": "{hive_bin}", "args": ["mcp"]}}}}}}'
        )


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
@click.option("--file", "file_path", help="File path to get lineage for")
@click.option("--commit", "commit_sha", help="Git commit SHA (full or prefix)")
def lineage(file_path: str | None, commit_sha: str | None):
    """Show sessions linked to a file or commit via the edges graph."""
    api = QueryAPI()

    if commit_sha:
        results = api.get_sessions_by_commit(commit_sha)
        if not results:
            console.print(f"[dim]No sessions found for commit {commit_sha}[/dim]")
            return

        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="cyan", max_width=12)
        table.add_column("Date", style="green")
        table.add_column("Author")
        table.add_column("Summary", max_width=50)

        for s in results:
            table.add_row(
                s["id"][:12],
                str(s.get("started_at", ""))[:10],
                s.get("author", ""),
                s.get("summary", ""),
            )

        console.print(table)
        return

    if not file_path:
        console.print("[red]Provide --file or --commit[/red]")
        return

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


# ── import ─────────────────────────────────────────────────────────


@cli.command(name="import")
@click.option("--file", "file_path", type=click.Path(exists=True), help="Import from file")
@click.option("--title", help="Session title/summary")
@click.option("--project", help="Associated project path")
@click.option("--tag", multiple=True, help="Tags to apply")
@click.option("--source", default="claude_desktop", help="Source adapter name")
@click.option("--author", help="Author name")
def import_cmd(
    file_path: str | None,
    title: str | None,
    project: str | None,
    tag: tuple[str, ...],
    source: str,
    author: str | None,
):
    """Import a conversation from file or stdin."""
    from hive.capture.claude_desktop import ClaudeDesktopAdapter

    if file_path:
        content = Path(file_path).read_text()
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        console.print("[red]Provide --file or pipe content via stdin.[/red]")
        return

    if not content.strip():
        console.print("[red]No content to import.[/red]")
        return

    adapter = ClaudeDesktopAdapter()
    data = {
        "content": content,
        "title": title or "",
        "project": str(Path(project).resolve()) if project else None,
        "tags": list(tag),
        "author": author,
    }
    session_id = adapter._ingest(data)
    console.print(f"[green]Imported session {session_id[:12]}[/green]")
    console.print(f"  Source: {source}")
    if title:
        console.print(f"  Title: {title}")
    if tag:
        console.print(f"  Tags: {', '.join(tag)}")


# ── link ──────────────────────────────────────────────────────────


_VALID_RELATIONSHIPS = ("implements", "continues", "references", "refines")


@cli.command()
@click.argument("source_session_id")
@click.argument("target_session_id")
@click.option(
    "-r",
    "--relationship",
    default="references",
    type=click.Choice(_VALID_RELATIONSHIPS),
    help="Relationship type",
)
def link(source_session_id: str, target_session_id: str, relationship: str):
    """Create a lineage link between two sessions."""
    api = QueryAPI()
    api.insert_edge("session", source_session_id, "session", target_session_id, relationship)
    console.print(
        f"[green]Linked {source_session_id[:12]} --({relationship})--> "
        f"{target_session_id[:12]}[/green]"
    )


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
@click.option("--no-search", is_flag=True, help="Disable semantic search backend")
def serve(port: int | None, no_search: bool):
    """Start the team server."""
    import shutil
    import signal
    import subprocess
    import time

    import uvicorn

    from hive.serve.api import create_app
    from hive.store.db import init_db

    config = Config.load()
    actual_port = port or config.server_port

    # Initialize server database
    db_path = None if config.db_url else config.server_db_path
    init_db(config, db_path=db_path)

    # Start search backend if needed
    search_proc = None
    if not no_search:
        if config.search_backend == "witchcraft" and config.search_assets_path:
            binary = shutil.which(config.search_binary)
            if binary:
                db_path = str(config.db_path).replace("store.db", "search.db")
                cmd = [
                    binary,
                    "--db-path",
                    db_path,
                    "--assets",
                    str(config.search_assets_path),
                    "--port",
                    str(config.search_url.rsplit(":", 1)[-1]),
                ]
                console.print(f"[dim]Starting search backend: {config.search_binary}[/dim]")
                search_proc = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                # Wait for search backend to be ready
                from hive.search import SearchClient

                client = SearchClient(config.search_url)
                for _ in range(60):  # up to 30s
                    if client.is_available():
                        console.print("[green]Search backend ready.[/green]")
                        break
                    time.sleep(0.5)
                else:
                    console.print(
                        "[yellow]Search backend did not start in time "
                        "(continuing without it).[/yellow]"
                    )
            else:
                console.print(
                    f"[dim]Search binary '{config.search_binary}' not found "
                    f"(FTS5 fallback active).[/dim]"
                )
        elif config.search_backend == "sqlite-vec":
            console.print("[dim]Using sqlite-vec search (in-process, no server needed).[/dim]")
        elif config.search_backend == "pgvector":
            console.print("[dim]Using pgvector search (PostgreSQL, in-database).[/dim]")
        else:
            console.print(f"[dim]Search backend: {config.search_backend}[/dim]")

    console.print(f"[bold]Starting hive server on http://0.0.0.0:{actual_port}[/bold]")
    if config.db_url:
        # Mask password in displayed URL
        display_url = config.db_url
        if "@" in display_url:
            scheme_rest = display_url.split("://", 1)
            if len(scheme_rest) == 2:
                after_scheme = scheme_rest[1]
                display_url = f"{scheme_rest[0]}://***@{after_scheme.split('@', 1)[-1]}"
        console.print(f"  Server DB: {display_url}")
    else:
        console.print(f"  Server DB: {config.server_db_path}")
    app = create_app(config=config, db_path=db_path)

    def _shutdown(signum, frame):
        if search_proc:
            search_proc.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        uvicorn.run(app, host="0.0.0.0", port=actual_port, log_level="info")
    finally:
        if search_proc:
            search_proc.terminate()
            search_proc.wait(timeout=5)


# ── reindex ─────────────────────────────────────────────────────────


def _reindex_sessions(config: Config, verbose: bool = False) -> int:
    """Index all sessions into the search backend. Returns count indexed."""
    from hive.search import build_metadata, build_search_body, get_search_backend
    from hive.store.query import QueryAPI

    backend = get_search_backend(config)
    if not backend.is_available():
        raise RuntimeError(f"Search backend ({config.search_backend}) is not available")

    api = QueryAPI(config)
    sessions = api.list_sessions(limit=100000)
    total = len(sessions)

    if verbose:
        console.print(f"Reindexing {total} sessions into {config.search_backend} search backend...")

    indexed = 0
    for i, session in enumerate(sessions, 1):
        full = api.get_session(session["id"], detail="messages")
        if not full or not full.get("messages"):
            continue

        body, chunk_lengths = build_search_body(full["messages"])
        if not body:
            continue

        metadata = build_metadata(full)
        try:
            backend.add_document(full["id"], full.get("started_at"), metadata, body, chunk_lengths)
            indexed += 1
        except Exception as e:
            if verbose:
                console.print(f"  [red]Failed[/red] {full['id'][:12]}: {e}")

        if verbose and i % 10 == 0:
            console.print(f"  [{i}/{total}] processed...")

    backend.trigger_index()
    return indexed


@cli.command()
def reindex():
    """Rebuild the search index from all stored sessions."""
    config = Config.load()
    try:
        console.print("Triggering embedding and indexing...")
        indexed = _reindex_sessions(config, verbose=True)
        console.print(f"[green]Done.[/green] Indexed {indexed} sessions.")
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")


# ── mcp ─────────────────────────────────────────────────────────────


@cli.command()
def mcp():
    """Start the MCP server (stdio)."""
    import asyncio

    from hive.mcp_server import main as mcp_main

    asyncio.run(mcp_main())


if __name__ == "__main__":
    cli()
