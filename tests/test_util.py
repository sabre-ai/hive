"""Tests for hive.util."""

from __future__ import annotations

import pytest

from hive.util import normalize_repo_url


class TestNormalizeRepoUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("git@github.com:acme/app.git", "github.com/acme/app"),
            ("git@github.com:acme/app", "github.com/acme/app"),
            ("https://github.com/acme/app.git", "github.com/acme/app"),
            ("https://github.com/acme/app", "github.com/acme/app"),
            ("ssh://git@github.com/acme/app.git", "github.com/acme/app"),
            ("ssh://git@github.com/acme/app", "github.com/acme/app"),
            # Trailing slashes
            ("https://github.com/acme/app.git/", "github.com/acme/app"),
            # Mixed case host
            ("git@GitHub.COM:acme/app.git", "github.com/acme/app"),
            ("https://GitHub.COM/acme/app.git", "github.com/acme/app"),
            # GitLab / self-hosted
            ("git@gitlab.myco.com:team/project.git", "gitlab.myco.com/team/project"),
            ("https://git.internal.io/org/repo.git", "git.internal.io/org/repo"),
            # Nested paths
            ("git@github.com:org/sub/repo.git", "github.com/org/sub/repo"),
        ],
    )
    def test_valid_urls(self, url: str, expected: str):
        assert normalize_repo_url(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "   ",
            "not-a-url",
            "ftp://",
        ],
    )
    def test_invalid_urls_return_none(self, url: str):
        assert normalize_repo_url(url) is None
