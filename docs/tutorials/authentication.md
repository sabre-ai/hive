# Authentication with WorkOS

Protect your team server with OpenID Connect (OIDC) so only authorized team members can push sessions. This guide walks through setting up authentication using [WorkOS](https://workos.com) as your identity provider.

## Prerequisites

- A running hive team server (see [Team Server](../getting-started/team-server.md))
- A [WorkOS account](https://dashboard.workos.com/signup) with an organization and SSO connection configured
- hive CLI installed on each developer's machine

## 1. Configure WorkOS

In the [WorkOS Dashboard](https://dashboard.workos.com):

1. Go to **Authentication** and note your **Client ID** (starts with `client_`)
2. Go to **API Keys** and note your **API Key** (starts with `sk_`)
3. Under your SSO connection, add a **Redirect URI**:

    ```
    http://localhost/callback
    ```

    !!! info "Why localhost?"
        The hive CLI starts a temporary local server to receive the OAuth callback during login. The port is assigned dynamically, so the redirect URI only needs the host and path.

4. Note your **Issuer URL** from the connection's OIDC discovery endpoint. This is typically:

    ```
    https://api.workos.com
    ```

    You can verify by checking that the discovery document is accessible:

    ```bash
    curl -s https://api.workos.com/.well-known/openid-configuration | jq .issuer
    ```

## 2. Configure the Hive server

Add the auth environment variables to your `docker-compose.yml`:

```yaml title="docker-compose.yml" hl_lines="7-11"
services:
  hive:
    build: .
    ports:
      - "3000:3000"
    environment:
      HIVE_DB_URL: "postgresql://hive:hive@postgres:5432/hive"
      HIVE_SEARCH_BACKEND: "pgvector"
      HIVE_AUTH_ENABLED: "true"
      HIVE_AUTH_ISSUER_URL: "https://api.workos.com"
      HIVE_AUTH_CLIENT_ID: "client_YOUR_CLIENT_ID"
      HIVE_AUTH_CLIENT_SECRET: "sk_YOUR_API_KEY"
    depends_on:
      postgres:
        condition: service_healthy
```

Then restart the server:

```bash
docker compose down && docker compose up -d
```

!!! tip "Keep secrets out of version control"
    Use a `.env` file or Docker secrets instead of hardcoding credentials in `docker-compose.yml`:

    ```yaml title="docker-compose.yml"
    environment:
      HIVE_AUTH_ENABLED: "true"
      HIVE_AUTH_ISSUER_URL: "https://api.workos.com"
      HIVE_AUTH_CLIENT_ID: "${WORKOS_CLIENT_ID}"
      HIVE_AUTH_CLIENT_SECRET: "${WORKOS_CLIENT_SECRET}"
    ```

    ```bash title=".env"
    WORKOS_CLIENT_ID=client_YOUR_CLIENT_ID
    WORKOS_CLIENT_SECRET=sk_YOUR_API_KEY
    ```

### Configuration reference

All auth settings can be set via environment variables or in `~/.config/hive/config.toml`:

| Environment Variable | TOML Key | Default | Description |
|---|---|---|---|
| `HIVE_AUTH_ENABLED` | `auth.enabled` | `false` | Enable OIDC authentication |
| `HIVE_AUTH_ISSUER_URL` | `auth.issuer_url` | | OIDC provider base URL |
| `HIVE_AUTH_CLIENT_ID` | `auth.client_id` | | OAuth2 client ID |
| `HIVE_AUTH_CLIENT_SECRET` | `auth.client_secret` | | OAuth2 client secret |
| `HIVE_AUTH_JWT_SECRET` | `auth.jwt_secret` | auto-generated | Signing key for Hive JWTs |
| `HIVE_AUTH_ALLOWED_DOMAINS` | `auth.allowed_domains` | | Comma-separated email domain allowlist |

## 3. Log in from the CLI

Each developer authenticates by running:

```bash
hive login --server http://team-server:3000
```

This will:

1. Fetch the OIDC configuration from the server
2. Open your browser to the WorkOS login page
3. After you authenticate, redirect back to a local callback
4. Exchange the authorization code for tokens (using PKCE for security)
5. Store tokens locally in `~/.config/hive/config.toml`

You should see:

```
Opening browser for authentication...
Logged in as alice@yourcompany.com
```

!!! info "Can't open a browser?"
    If the browser doesn't open automatically, the CLI prints the authorization URL. Copy and paste it into a browser manually.

## 4. Verify

Check your identity:

```bash
hive whoami
```

```
alice@yourcompany.com
Token expires: 2026-04-28T15:30:00Z
```

Confirm that unauthenticated writes are rejected:

```bash
curl -s -X POST http://team-server:3000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{}' | jq .detail
```

```
"Missing authentication token. Run 'hive login' to authenticate."
```

Read endpoints remain open so MCP tools and search work without tokens:

```bash
curl -s http://team-server:3000/api/sessions | jq 'length'
```

## 5. Restrict by email domain (optional)

Limit who can log in by setting an email domain allowlist:

```yaml title="docker-compose.yml"
environment:
  HIVE_AUTH_ALLOWED_DOMAINS: "yourcompany.com,contractor.io"
```

Users with email addresses outside these domains will be rejected at login even if they authenticate successfully with WorkOS.

## 6. Log out

```bash
hive logout
```

This revokes the refresh token on the server and clears local tokens from `~/.config/hive/config.toml`.

## How it works

The authentication flow uses standard OpenID Connect with PKCE:

```
Developer                CLI              Team Server           WorkOS
    │                     │                    │                    │
    │  hive login         │                    │                    │
    │────────────────────>│                    │                    │
    │                     │  GET /auth/discovery                   │
    │                     │───────────────────>│                    │
    │                     │  {authorization_endpoint, ...}         │
    │                     │<───────────────────│                    │
    │                     │                    │                    │
    │  Browser opens      │                    │                    │
    │<────────────────────│                    │                    │
    │                     │                    │                    │
    │  Authenticate at WorkOS ────────────────────────────────────>│
    │  Redirect to localhost/callback?code=... │                   │
    │<─────────────────────────────────────────────────────────────│
    │                     │                    │                    │
    │  code + PKCE verifier                   │                    │
    │────────────────────>│                    │                    │
    │                     │  POST /auth/callback                   │
    │                     │───────────────────>│                    │
    │                     │                    │  Exchange code     │
    │                     │                    │───────────────────>│
    │                     │                    │  {id_token, ...}   │
    │                     │                    │<───────────────────│
    │                     │                    │                    │
    │                     │  {access_token, refresh_token}         │
    │                     │<───────────────────│                    │
    │                     │                    │                    │
    │  Logged in as alice@co.com              │                    │
    │<────────────────────│                    │                    │
```

Key security properties:

- **PKCE** prevents authorization code interception
- **Short-lived access tokens** (60 minutes by default) limit exposure
- **Refresh token rotation** — each refresh issues a new token and revokes the old one
- **Replay detection** — reuse of an old refresh token revokes all tokens for that user
- **Client-side storage** — tokens stored with `0600` file permissions (owner-only)

## Troubleshooting

### "Discovery fetch failed" or connection errors

The server cannot reach WorkOS's OIDC discovery endpoint. Verify:

```bash
# From the server container
docker compose exec hive curl -s https://api.workos.com/.well-known/openid-configuration | head -5
```

If this fails, check that the container has outbound HTTPS access.

### "Invalid authentication token" after login

The `HIVE_AUTH_JWT_SECRET` may have changed between server restarts (it auto-generates if not set). Set a fixed secret:

```yaml
environment:
  HIVE_AUTH_JWT_SECRET: "your-random-secret-here"
```

Then re-login:

```bash
hive login --server http://team-server:3000
```

### "Token expired" errors

Access tokens expire after 60 minutes by default. The CLI auto-refreshes transparently, but if the refresh token has also expired (30 days), log in again:

```bash
hive login --server http://team-server:3000
```

### Domain not allowed

If you see a domain rejection error, check that the user's email domain is in `HIVE_AUTH_ALLOWED_DOMAINS`. Remove this variable entirely to allow all domains.

## Next Steps

- [Sharing Controls](sharing-controls.md) — per-project sharing settings
- [Security & Privacy](../security.md) — threat model and secret scrubbing
- [Configuration](../reference/configuration.md) — full config reference
