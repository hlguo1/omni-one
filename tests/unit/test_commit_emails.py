"""Commit-email onboarding check: verified authors pass, noreply/unlinked fail."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import check_commit_emails as cce  # noqa: E402


def _commit(
    sha: str,
    email: str | None,
    *,
    login: str | None = "alice",
    user_type: str = "User",
    parents: int = 1,
) -> dict:
    return {
        "sha": sha,
        "parents": [{"sha": "parent"}] * parents,
        "commit": {"author": {"email": email}},
        "author": (
            {"login": login, "type": user_type} if login is not None else None
        ),
    }


def test_verified_author_passes():
    assert cce.commit_email_violations(
        [_commit("a" * 40, "alice@example.com")]
    ) == []


def test_noreply_fails():
    problems = cce.commit_email_violations([
        _commit("b" * 40, "123+alice@users.noreply.github.com"),
    ])
    assert len(problems) == 1
    assert "noreply or invalid" in problems[0]
    assert "@" not in problems[0]


def test_unverified_email_fails():
    problems = cce.commit_email_violations([
        _commit("c" * 40, "alice@example.com", login=None),
    ])
    assert len(problems) == 1
    assert "not verified/linked" in problems[0]
    assert "@" not in problems[0]


def test_bot_commit_is_skipped():
    assert cce.commit_email_violations([
        _commit(
            "d" * 40,
            "49699333+dependabot[bot]@users.noreply.github.com",
            login="dependabot[bot]",
            user_type="Bot",
        ),
    ]) == []


def test_merge_commit_is_skipped():
    assert cce.commit_email_violations([
        _commit("e" * 40, "123+alice@users.noreply.github.com", parents=2),
    ]) == []


def test_missing_email_fails():
    problems = cce.commit_email_violations([_commit("f" * 40, None)])
    assert len(problems) == 1
    assert "noreply or invalid" in problems[0]
