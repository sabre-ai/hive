---
hide:
  - navigation
  - toc
---

<div class="hive-hero" markdown>

# Team Layer for <span style="color: var(--hive-amber)">Claude</span>.

↳ so Claude can answer

<div style="text-align: left; width: fit-content; margin: 0 auto 1rem; font-size: 1.1rem;">
<span style="color: var(--hive-amber)">›</span> <em>"Has anyone on the team built this before?"</em><br>
<span style="color: var(--hive-amber)">›</span> <em>"What worked when Alice hit this last week?"</em><br>
<span style="color: var(--hive-amber)">›</span> <em>"Why did we choose this architecture?"</em>
</div>

Every Claude Code and Claude Desktop session across your team — now Claude's working context.

<div class="hive-install" role="group" aria-label="Install Hive">
  <code class="hive-install__cmd">
    <span class="hive-install__prompt">$</span><span class="hive-install__bin">curl</span>&nbsp;<span class="hive-install__url">https://sabre-ai.github.io/hive/install.sh</span>&nbsp;<span class="hive-install__pipe">|</span>&nbsp;<span class="hive-install__url">bash</span>
  </code>
  <button
    class="hive-install__copy"
    type="button"
    data-hive-copy="curl https://sabre-ai.github.io/hive/install.sh | bash"
    aria-label="Copy install command">COPY</button>
</div>

[Read the Docs :material-arrow-right:](getting-started/index.md){ .md-button .md-button--primary }
[View on GitHub :fontawesome-brands-github:](https://github.com/sabre-ai/hive){ .md-button }

</div>

## What you get

<div class="grid cards" markdown>

- :material-magnify:{ .lg .middle } __Skip the duplicate work__

    ---

    Search across teammate sessions before starting yours.

- :material-account-group:{ .lg .middle } __Onboard new teammates faster__

    ---

    They get the team's prompt history on day one.

- :material-file-document-check:{ .lg .middle } __Stop re-deriving decisions__

    ---

    Every "why did we..." has a transcript attached.

</div>

## How it works

```mermaid
flowchart LR
    CC[Claude Code<br/>hooks] --> E[Enrich] --> DB[(store.db)]
    MCP[MCP Server] --> DB
    Claude[Claude Code<br/>Claude Desktop] --> MCP
    CLI[hive CLI] --> DB
```

See [Architecture](architecture/overview.md) for the full pipeline including team mode.

## Get involved

- [Contributing](contributing.md) — adapters, enrichers, and more
- [Security](security.md) — how we handle secrets
- [GitHub](https://github.com/sabre-ai/hive) — issues, discussions, PRs welcome

**Apache 2.0** — self-host, fork, audit. The server, the scrubber, and the MCP surface are all in-repo.
