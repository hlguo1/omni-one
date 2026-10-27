"""Fail a pull request when its commits use noreply or unverified emails.

Onboarding requirement: see ``CONTRIBUTING.md``. This check never prints email
addresses; it only reports commit SHAs and the reason.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from branch_cleanup import redact_emails, usable_email

API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")


def commit_email_violations(commits: list[dict[str, Any]]) -> list[str]:
    """Return human-readable violations for non-bot, non-merge commits."""
    problems: list[str] = []
    for commit in commits:
        sha = str(commit.get("sha") or "unknown")
        short = sha[:12]
        if len(commit.get("parents") or []) > 1:
            continue
        user = commit.get("author") or {}
        login = str(user.get("login") or "")
        if user.get("type") == "Bot" or login.endswith("[bot]"):
            continue
        author = (commit.get("commit") or {}).get("author") or {}
        email = author.get("email")
        if not usable_email(email):
            problems.append(
                f"{short}: author email is a GitHub noreply or invalid address"
            )
        elif not login:
            problems.append(
                f"{short}: author email is not verified/linked to a GitHub account"
            )
    return problems


def fetch_pr_commits(repo: str, pr_number: str, token: str) -> list[dict[str, Any]]:
    commits: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            f"{API_URL}/repos/{repo}/pulls/{pr_number}/commits"
            f"?per_page=100&page={page}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "omni-one-commit-email-check",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                batch = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = redact_emails(
                exc.read().decode("utf-8", "replace")
            ).strip()[:300]
            print(
                f"error: GitHub API returned HTTP {exc.code}: {detail}",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        except Exception as exc:
            print(
                f"error: could not read pull request commits: "
                f"{redact_emails(str(exc))}",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        if not isinstance(batch, list):
            print("error: unexpected GitHub API response", file=sys.stderr)
            raise SystemExit(2)
        commits.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return commits


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    pr_number = os.getenv("PR_NUMBER", "").strip()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not repo or not pr_number:
        print(
            "error: GITHUB_REPOSITORY and PR_NUMBER are required",
            file=sys.stderr,
        )
        return 2
    if not token:
        print("error: GITHUB_TOKEN is required", file=sys.stderr)
        return 2

    commits = fetch_pr_commits(repo, pr_number, token)
    problems = commit_email_violations(commits)
    if not problems:
        print(f"commit-email check passed ({len(commits)} commit(s)).")
        return 0

    print(
        f"commit-email check failed ({len(problems)} problem(s)):",
        file=sys.stderr,
    )
    for problem in problems:
        print(f"  {problem}", file=sys.stderr)
    print(
        "Set a real, verified git user.email (see CONTRIBUTING.md) and "
        "rewrite the affected commits.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
