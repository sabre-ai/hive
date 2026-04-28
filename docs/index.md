---
hide:
  - navigation
  - toc
---

<div class="hive-home" markdown>

<!-- §4 Hero -->
<section class="hive-hero">

<h1 class="hive-hero__headline">The team layer<br>for <span class="claude-word">Claude</span></h1>

<p class="hive-hero__caption">— so Claude can answer —</p>

<!-- §6 Questions Block -->
<div class="questions-block">
  <div class="questions-block__row">
    <span class="questions-block__num">01</span>
    <span class="questions-block__arrow">›</span>
    <span class="questions-block__text">Has anyone on the team built this before?</span>
  </div>
  <div class="questions-block__row">
    <span class="questions-block__num">02</span>
    <span class="questions-block__arrow">›</span>
    <span class="questions-block__text">What worked when Alice hit this last week?</span>
  </div>
  <div class="questions-block__row">
    <span class="questions-block__num">03</span>
    <span class="questions-block__arrow">›</span>
    <span class="questions-block__text">Why did we choose this architecture?</span>
  </div>
</div>

<p class="hive-hero__lead">Hive captures every Claude Code and Claude Desktop session across your team — <strong>now Claude's working context.</strong></p>

<!-- §5 Install Pill -->
<div class="install-pill" role="group" aria-label="Install Hive">
  <code class="install-pill__cmd"><span class="install-pill__prompt">$</span> <span class="install-pill__mute">curl</span> <span class="install-pill__mute">-fsSL</span> <span class="install-pill__text">https://sabre-ai.github.io/hive/install.sh</span> <span class="install-pill__mute-deep">|</span> <span class="install-pill__text">bash</span></code>
  <button
    class="install-pill__copy"
    type="button"
    data-hive-copy="curl -fsSL https://sabre-ai.github.io/hive/install.sh | bash"
    aria-label="Copy install command">Copy</button>
</div>

<div class="hive-hero__cta">
  <a href="getting-started/" class="btn btn-primary">Read the docs →</a>
  <a href="https://github.com/sabre-ai/hive" class="btn btn-outline" target="_blank" rel="noopener">View on GitHub ↗</a>
</div>

</section>

<!-- §7 Why it matters -->
<section class="section-why">
<h2 class="section-why__title">Why it matters</h2>
<div class="why-grid">
  <div class="why-card">
    <p class="why-card__title">Skip the duplicate work</p>
    <p class="why-card__body">Search across teammate sessions before starting yours.</p>
  </div>
  <div class="why-card">
    <p class="why-card__title">Onboard new teammates faster</p>
    <p class="why-card__body">They get the team's prompt history on day one.</p>
  </div>
  <div class="why-card">
    <p class="why-card__title">Stop re-deriving decisions</p>
    <p class="why-card__body">Every "why did we…" has a transcript attached.</p>
  </div>
</div>
</section>

<!-- §8 How it works -->
<section class="section-how">
<h2 class="section-how__title">How it works</h2>
<svg class="section-how__diagram" viewBox="0 0 820 480" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Hive architecture diagram showing data flow from sources through enrichment to storage">
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#A89F8E"/>
    </marker>
  </defs>

  <!-- Row 1: Claude Code hooks → Enrich -->
  <rect x="40" y="40" width="200" height="80" rx="6" class="diagram-box diagram-box--filled"/>
  <text x="140" y="72" class="diagram-label">Claude Code</text>
  <text x="140" y="96" class="diagram-label">hooks</text>

  <rect x="340" y="40" width="200" height="80" rx="6" class="diagram-box diagram-box--filled"/>
  <text x="440" y="84" class="diagram-label">Enrich</text>

  <!-- Row 2: Claude Code/Desktop → MCP Server -->
  <rect x="40" y="190" width="200" height="100" rx="6" class="diagram-box diagram-box--filled"/>
  <text x="140" y="232" class="diagram-label">Claude Code</text>
  <text x="140" y="258" class="diagram-label">Claude Desktop</text>

  <rect x="340" y="200" width="200" height="80" rx="6" class="diagram-box diagram-box--filled"/>
  <text x="440" y="244" class="diagram-label">MCP Server</text>

  <!-- Row 3: hive CLI (positioned under MCP Server) -->
  <rect x="340" y="370" width="200" height="70" rx="6" class="diagram-box diagram-box--filled"/>
  <text x="440" y="409" class="diagram-label">hive CLI</text>

  <!-- Cylinder: store.db (centered with row 2) -->
  <ellipse cx="710" cy="210" rx="62" ry="16" fill="none" stroke="var(--accent)" stroke-width="1.5"/>
  <line x1="648" y1="210" x2="648" y2="275" stroke="var(--accent)" stroke-width="1.5"/>
  <line x1="772" y1="210" x2="772" y2="275" stroke="var(--accent)" stroke-width="1.5"/>
  <path d="M648,275 A62,16 0 0,0 772,275" fill="none" stroke="var(--accent)" stroke-width="1.5"/>
  <text x="710" y="250" class="diagram-label-mono">store.db</text>

  <!-- Arrows -->
  <!-- hooks → Enrich (straight horizontal) -->
  <line x1="240" y1="80" x2="338" y2="80" class="diagram-arrow"/>
  <!-- Enrich → store.db (curve down to cylinder top) -->
  <path d="M540,80 C610,80 630,180 648,215" class="diagram-arrow"/>
  <!-- Claude Code/Desktop → MCP Server (straight horizontal) -->
  <line x1="240" y1="240" x2="338" y2="240" class="diagram-arrow"/>
  <!-- MCP Server → store.db (straight to cylinder middle) -->
  <line x1="540" y1="240" x2="648" y2="245" class="diagram-arrow"/>
  <!-- hive CLI → store.db (curve up to cylinder bottom) -->
  <path d="M540,405 C610,405 630,310 648,275" class="diagram-arrow"/>
</svg>
<p class="section-how__caption">See <a href="architecture/overview/">Architecture</a> for the full pipeline including team mode.</p>
</section>

<!-- §9 Get involved -->
<section class="section-involved">
<h2 class="section-involved__title">Get involved</h2>
<ul>
  <li><a href="contributing/">Contributing</a> <span>— adapters, enrichers, and more</span></li>
  <li><a href="security/">Security</a> <span>— how we handle secrets</span></li>
  <li><a href="https://github.com/sabre-ai/hive" target="_blank" rel="noopener">GitHub</a> <span>— issues, discussions, PRs welcome</span></li>
</ul>
<p class="section-involved__license"><strong>Apache 2.0</strong> — self-host, fork, audit. The server, the scrubber, and the MCP surface are all in-repo.</p>
</section>

</div>
