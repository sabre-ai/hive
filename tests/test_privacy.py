"""Tests for hive.privacy scrubbing utilities."""

from __future__ import annotations

from hive.config import Config
from hive.privacy import scrub, scrub_payload


def _config() -> Config:
    """Return a Config with default scrub patterns loaded."""
    return Config.load()


# ── AI provider keys ─────────────────────────────────────────────


class TestAIProviderKeys:
    def test_openai_key(self):
        result = scrub("key: sk-abc123XYZdef456GHIjkl789", _config())
        assert "sk-abc123" not in result
        assert "[REDACTED]" in result

    def test_openai_proj_key(self):
        result = scrub("sk-proj-abcdefghijklmnopqrstuvwxyz1234", _config())
        assert "sk-proj-" not in result

    def test_anthropic_key(self):
        result = scrub("sk-ant-abcdefghijklmnopqrstuvwxyz1234", _config())
        assert "sk-ant-" not in result


# ── Cloud credentials ────────────────────────────────────────────


class TestCloudCredentials:
    def test_aws_access_key(self):
        result = scrub("AKIAIOSFODNN7EXAMPLE", _config())
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_aws_secret_key(self):
        result = scrub(
            "aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", _config()
        )
        assert "wJalrXUtnFEMI" not in result

    def test_google_api_key(self):
        result = scrub("AIzaSyA-abcdefghijklmnopqrstuvwxyz12345", _config())
        assert "AIzaSyA-" not in result

    def test_google_oauth_token(self):
        token = "ya29." + "a" * 60
        result = scrub(token, _config())
        assert "ya29." not in result


# ── VCS tokens ───────────────────────────────────────────────────


class TestVCSTokens:
    def test_github_pat(self):
        result = scrub("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm", _config())
        assert "ghp_" not in result

    def test_github_oauth(self):
        result = scrub("gho_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm", _config())
        assert "gho_" not in result

    def test_github_app_token(self):
        result = scrub("ghs_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm", _config())
        assert "ghs_" not in result

    def test_github_fine_grained(self):
        result = scrub("github_pat_abcdefghijklmnopqrstuv12", _config())
        assert "github_pat_" not in result

    def test_gitlab_pat(self):
        result = scrub("glpat-abcdefghijklmnopqrstuvwx", _config())
        assert "glpat-" not in result


# ── Auth tokens ──────────────────────────────────────────────────


class TestAuthTokens:
    def test_bearer_token(self):
        result = scrub(
            "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123", _config()
        )
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result

    def test_basic_auth(self):
        result = scrub("Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQxMjM=", _config())
        assert "dXNlcm5hbWU6cGFzc3dvcmQxMjM=" not in result

    def test_slack_token(self):
        result = scrub("xoxb-123456789-abcdefghij", _config())
        assert "xoxb-" not in result

    def test_jwt(self):
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = scrub(jwt, _config())
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result


# ── Connection strings ───────────────────────────────────────────


class TestConnectionStrings:
    def test_postgres_uri(self):
        result = scrub("postgres://user:pass@host:5432/dbname", _config())
        assert "postgres://user:pass" not in result

    def test_mongodb_uri(self):
        result = scrub("mongodb://admin:secretpass@mongo.example.com:27017/mydb", _config())
        assert "mongodb://admin:secretpass" not in result

    def test_redis_uri(self):
        result = scrub("redis://default:mysecretpassword@redis.example.com:6379", _config())
        assert "redis://default:mysecretpassword" not in result

    def test_database_url_env(self):
        result = scrub("DATABASE_URL=postgres://user:pass@host/db", _config())
        assert "postgres://user:pass" not in result


# ── Private keys ─────────────────────────────────────────────────


class TestPrivateKeys:
    def test_rsa_private_key(self):
        result = scrub("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAK...", _config())
        assert "-----BEGIN RSA PRIVATE KEY-----" not in result

    def test_generic_private_key(self):
        result = scrub("-----BEGIN PRIVATE KEY-----", _config())
        assert "-----BEGIN PRIVATE KEY-----" not in result

    def test_certificate(self):
        result = scrub("-----BEGIN CERTIFICATE-----", _config())
        assert "-----BEGIN CERTIFICATE-----" not in result


# ── Generic secrets ──────────────────────────────────────────────


class TestGenericSecrets:
    def test_api_key_equals(self):
        result = scrub("api_key=sk_live_abcdefghijkl", _config())
        assert "sk_live_abcdefghijkl" not in result

    def test_secret_key_colon(self):
        result = scrub('secret_key: "my_super_secret_value_123"', _config())
        assert "my_super_secret_value_123" not in result

    def test_password_equals(self):
        result = scrub("password=MyS3cr3tP@ss!", _config())
        assert "MyS3cr3tP@ss!" not in result

    def test_env_var_with_secret_suffix(self):
        result = scrub("export STRIPE_SECRET_KEY=sk_live_abc123def456ghi789", _config())
        assert "sk_live_abc123def456ghi789" not in result


# ── Webhooks ─────────────────────────────────────────────────────


class TestWebhooks:
    def test_slack_webhook(self):
        result = scrub("https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXX", _config())
        assert "hooks.slack.com/services/T00000000" not in result

    def test_discord_webhook(self):
        result = scrub("https://discord.com/api/webhooks/123456789/abcdef_ghijkl", _config())
        assert "discord.com/api/webhooks/123456789" not in result


# ── Preserves safe text ──────────────────────────────────────────


class TestPreservesSafeText:
    def test_normal_text_unchanged(self):
        text = "Just a normal message about refactoring code."
        assert scrub(text, _config()) == text

    def test_short_strings_unchanged(self):
        text = "key=abc"
        assert scrub(text, _config()) == text

    def test_code_with_sk_prefix_in_regex(self):
        # The regex pattern definition itself contains "sk-" but shouldn't
        # be scrubbed because the full match requires 20+ chars
        text = 'pattern = r"sk-[a-z]"'
        assert scrub(text, _config()) == text


# ── Payload deep-walk ────────────────────────────────────────────


class TestScrubPayload:
    def test_deep_nested_scrub(self):
        payload = {
            "summary": "Used sk-secretKeyThatIsVeryLong123",
            "messages": [
                {"content": "Token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"},
                {"content": "No secrets here"},
            ],
            "nested": {"deep": {"value": "aws AKIAIOSFODNN7EXAMPLE credential"}},
            "count": 42,
            "flag": True,
        }
        result = scrub_payload(payload, _config())
        assert "sk-secret" not in result["summary"]
        assert "ghp_" not in result["messages"][0]["content"]
        assert "AKIAIOSFODNN7EXAMPLE" not in result["nested"]["deep"]["value"]
        assert result["messages"][1]["content"] == "No secrets here"
        assert result["count"] == 42
        assert result["flag"] is True

    def test_empty_payload(self):
        assert scrub_payload({}, _config()) == {}

    def test_list_values(self):
        payload = {"items": ["safe", "key sk-longSecretKeyValue1234567890"]}
        result = scrub_payload(payload, _config())
        assert result["items"][0] == "safe"
        assert "sk-" not in result["items"][1]


# ── User customization ───────────────────────────────────────────


class TestUserCustomization:
    def test_extra_patterns_applied(self):
        config = Config.load()
        config.scrub_patterns.append(r"CUSTOM_[A-Z0-9]{10,}")
        result = scrub("found CUSTOM_ABCDEFGHIJ1234", config)
        assert "CUSTOM_ABCDEFGHIJ1234" not in result
        assert "[REDACTED]" in result

    def test_disabled_patterns(self):
        from hive.config import _load_scrub_patterns

        # Disable the "password" pattern
        patterns = _load_scrub_patterns({"scrub": {"disabled_patterns": ["password"]}})
        config = Config()
        config.scrub_patterns = patterns
        # Password should NOT be scrubbed now
        result = scrub("password=MyS3cr3tP@ss!", config)
        assert "MyS3cr3tP@ss!" in result

    def test_extra_and_disabled_together(self):
        from hive.config import _load_scrub_patterns

        patterns = _load_scrub_patterns(
            {
                "scrub": {
                    "extra_patterns": [r"INTERNAL_[A-Z]{20,}"],
                    "disabled_patterns": ["jwt"],
                }
            }
        )
        config = Config()
        config.scrub_patterns = patterns

        # Extra pattern works
        result = scrub("INTERNAL_ABCDEFGHIJKLMNOPQRSTU", config)
        assert "INTERNAL_" not in result

        # JWT pattern disabled — JWT should pass through
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = scrub(jwt, config)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" in result


# ── Pattern count ────────────────────────────────────────────────


class TestPatternCount:
    def test_default_patterns_loaded(self):
        config = Config.load()
        # Should have 25+ patterns from the default file
        assert len(config.scrub_patterns) >= 25, (
            f"Only {len(config.scrub_patterns)} patterns loaded"
        )
