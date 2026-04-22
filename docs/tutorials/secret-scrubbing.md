# Secret Scrubbing

All sessions are scrubbed client-side before being pushed to the team server. Secrets never leave your machine in cleartext.

## How it works

```python
# Simplified view of what happens before push
from hive.privacy import scrub_payload

payload = export_session(session)
clean = scrub_payload(payload)   # (1)!
post_to_server(clean)
```

1. Every string value in the payload is checked against all active patterns. Matches are replaced with `[REDACTED]`.

Scrubbing runs at two points in the pipeline:

1. **During JSONL parsing** -- as session transcripts are read from Claude Code's JSONL files.
2. **Before push** -- `scrub_payload()` walks the full session dict and scrubs every string value.

This double pass ensures secrets are caught regardless of how the session data is structured.

## Default patterns

Hive ships with patterns covering 9 categories in `scrub_patterns.toml`:

| Category | Patterns | Examples |
|---|---|---|
| **ai_providers** | `openai`, `openai_proj`, `anthropic`, `generic_api_key` | `sk-proj-...`, `sk-ant-...` |
| **cloud** | `aws_access_key`, `aws_secret`, `google_api_key`, `google_oauth` | `AKIA...`, `AIza...` |
| **vcs_tokens** | `github_pat`, `github_oauth`, `github_app`, `github_refresh`, `github_fine_grained`, `gitlab_pat` | `ghp_...`, `glpat-...` |
| **auth_tokens** | `bearer`, `basic_auth`, `slack`, `jwt` | `Bearer eyJ...`, `xoxb-...` |
| **connection_strings** | `db_uri`, `db_env` | `postgres://user:pass@...` |
| **private_keys** | `private_key_header`, `certificate_header` | `-----BEGIN RSA PRIVATE KEY-----` |
| **generic_secrets** | `key_value`, `password` | `api_key = sk-...`, `password: hunter2` |
| **webhooks** | `slack_webhook`, `discord_webhook` | `https://hooks.slack.com/...` |
| **env_vars** | `secret_env` | `export DB_PASSWORD=mysecret` |

## Customizing patterns

Edit `~/.config/hive/config.toml` to disable noisy patterns or add your own:

=== "Disable a pattern"

    ```toml title="~/.config/hive/config.toml"
    [scrub]
    disabled_patterns = ["generic_api_key", "password"]   # (1)!
    ```

    1. Use the pattern **name** (the key from `scrub_patterns.toml`), not the regex.

=== "Add custom patterns"

    ```toml title="~/.config/hive/config.toml"
    [scrub]
    extra_patterns = [
        "my-company-secret-[a-z0-9]+",       # (1)!
        "internal-token-[A-Za-z0-9]{32}",
    ]
    ```

    1. These are raw regex strings. They are appended to the default set.

=== "Both"

    ```toml title="~/.config/hive/config.toml"
    [scrub]
    disabled_patterns = ["generic_api_key"]
    extra_patterns = ["acme-key-[a-z0-9]{40}"]
    ```

## Verifying scrubbing

Test scrubbing on a string to confirm your patterns work:

```bash
python -c "
from hive.privacy import scrub
print(scrub('my key is sk-ant-abc123def456ghi789jkl012'))
"
```

Expected output:

```
my key is [REDACTED]
```

!!! warning "Scrubbing is regex-based"
    Pattern matching catches known secret formats but is not a guarantee. Avoid pasting raw secrets into Claude Code sessions when possible. If a secret format is not covered by the defaults, add it to `extra_patterns`.

## How patterns are loaded

1. Default patterns load from `scrub_patterns.toml` shipped with the package.
2. Patterns named in `disabled_patterns` are removed.
3. Strings from `extra_patterns` are appended.
4. The final list is compiled and applied to every string in the session payload.

```
scrub_patterns.toml (defaults)
        │
        ▼
  Remove disabled_patterns
        │
        ▼
  Append extra_patterns
        │
        ▼
  Final pattern list → scrub()
```

!!! note "Scrubbing is local only"
    Patterns are evaluated on the developer's machine. The team server never sees unredacted data. Changing patterns on the server has no effect on what gets scrubbed -- each client controls its own scrubbing config.
