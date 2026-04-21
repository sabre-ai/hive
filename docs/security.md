# Security

hive handles AI session transcripts which may contain sensitive information. This page covers the threat model, built-in protections, and how to report vulnerabilities.

## Threat Model

hive is designed as a **local-first** tool with optional team sharing. The security model assumes:

- **Trusted local machine**: The developer's laptop is trusted. Local `store.db` is not encrypted at rest.
- **Trusted network for team mode**: The MVP team server does not enforce authentication. It should run on a trusted network or behind a reverse proxy with auth.
- **No auth in MVP**: The REST API accepts unauthenticated requests. Authentication is on the [roadmap](roadmap.md).
- **Secrets in transcripts**: AI coding sessions routinely contain API keys, tokens, and passwords. hive scrubs these before storage and before push.

!!! warning "Team server access control"
    The team server has no built-in authentication. Run it behind a reverse
    proxy (nginx, Caddy, etc.) with your preferred auth mechanism, or restrict
    access at the network level.

## Secret Scrubbing

All sessions are scrubbed automatically using regex patterns **before** data is stored locally and **before** any push to the team server. Secrets never leave the developer's machine in cleartext.

### How It Works

1. During JSONL transcript parsing, `scrub()` runs on all message content
2. Before push to the team server, `scrub_payload()` runs on the entire payload
3. Matched patterns are replaced with `[REDACTED]`

### Pattern Categories

hive ships with 9 categories of default patterns in `scrub_patterns.toml`:

| Category | What It Catches |
|----------|----------------|
| `ai_providers` | OpenAI (`sk-`), Anthropic (`sk-ant-`), generic API keys |
| `cloud` | AWS access keys (`AKIA`), Google API keys, OAuth tokens |
| `vcs_tokens` | GitHub PATs (`ghp_`, `gho_`, `ghs_`, `ghr_`), GitLab PATs |
| `auth_tokens` | Bearer tokens, Basic auth, Slack tokens, JWTs |
| `connection_strings` | MongoDB, PostgreSQL, Redis, AMQP connection URIs |
| `private_keys` | RSA, EC, DSA, OPENSSH private key headers, certificates |
| `generic_secrets` | `api_key=...`, `password=...`, `secret_key=...`, `client_secret=...` |
| `webhooks` | Slack and Discord webhook URLs |
| `env_vars` | Exported secrets like `AWS_SECRET_KEY=...`, `*_TOKEN=...` |

### Customizing Patterns

Disable specific patterns or add your own in `~/.config/hive/config.toml`:

```toml
[scrub]
disabled_patterns = ["jwt", "basic_auth"]
extra_patterns = [
    'my-internal-token-[a-zA-Z0-9]{32}',
]
```

See [Configuration](reference/configuration.md#scrub-configuration) for details.

## File Permissions

- `~/.local/share/hive/` is created with `700` permissions (owner-only access)
- `store.db` and `server.db` contain session transcripts and should be treated as sensitive
- Per-project `.hive/` directories contain only the sharing config (no sensitive data)

!!! tip "Database backups"
    If you back up `store.db` or `server.db`, ensure the backup location has
    equivalent access controls. These files contain scrubbed but still
    potentially sensitive session transcripts.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Responsible Disclosure

If you discover a security vulnerability in hive, please report it responsibly.

**Email**: TODO@example.com

**What to include**:

- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)

**Response SLA**:

- Acknowledgment within 48 hours
- Initial assessment within 1 week
- Fix or mitigation plan within 30 days for confirmed vulnerabilities

!!! danger "Do not open public issues"
    Please do **not** open a public GitHub issue for security vulnerabilities.
    Do not exploit the vulnerability beyond what is necessary to demonstrate it.
