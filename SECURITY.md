# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in hive, please report it responsibly.

**Email:** TODO@example.com

**What to include:**
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)

**Response SLA:**
- Acknowledgment within 48 hours
- Initial assessment within 1 week
- Fix or mitigation plan within 30 days for confirmed vulnerabilities

**Please do not:**
- Open a public GitHub issue for security vulnerabilities
- Exploit the vulnerability beyond what is necessary to demonstrate it

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Security Considerations

hive handles AI session transcripts which may contain sensitive information:

- **Secret scrubbing** runs automatically before any data leaves the developer's machine. Default patterns cover API keys, tokens, and credentials.
- **Local-first storage** — all data stays in local SQLite by default. Sharing to a team server is opt-in per project.
- **No authentication in MVP** — the team server does not enforce access control. Run it on a trusted network or behind a reverse proxy with auth.
- **File permissions** — `~/.hive/` is created with `700` permissions.
