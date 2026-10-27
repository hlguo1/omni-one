#!/usr/bin/env python3
"""Inactive-branch cleanup with email notice and opt-out.

Policy
------
For every non-protected remote branch:

* day 12, 13, 14 of inactivity -> email the branch creator (once per day)
* day 15 of inactivity         -> delete the branch unless opted out

Protected branches (main/master/develop/staging/production, release/*,
hotfix/*, dependabot/*) are never touched. Deletion is also skipped when the
branch has an open pull request, when the tracking issue's comments cannot be
read, or when no email notice was successfully sent. Branches discovered after
the normal notice window get a fresh 3-day notice window instead of being
deleted immediately.

Opting out can be done either by commenting ``/opt-out`` on the tracking
GitHub issue linked from the email, or by running::

    python scripts/branch_cleanup.py remove <branch>

Only the branch creator/notification contact (resolved through the GitHub
commit API) or a repository owner/member/collaborator can opt out via the
issue.

Notification addresses come from the branch creator's commit email. A commit is
only linked to a GitHub account when that email is verified on the account, so
contributors must set a real, deliverable address before pushing and verify it
on their GitHub account (see CONTRIBUTING.md). GitHub noreply and unverified
addresses are not deliverable. Branches whose creator has no verified address
are sent to ``FALLBACK_NOTIFY_EMAIL`` when that environment secret is set;
otherwise they are skipped. Email addresses are never written to state or logs.

The script is safe by default when run with ``--dry-run``: it prints what it
would do and does not send email, create issues, delete branches, or write
state.

Useful commands::

    python scripts/branch_cleanup.py status
    python scripts/branch_cleanup.py add    <branch>   # enroll / opt back in
    python scripts/branch_cleanup.py remove <branch>   # opt out (never delete)
    python scripts/branch_cleanup.py run --dry-run

Email configuration (GitHub Actions secrets / environment):
    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
    SMTP_FROM, SMTP_TLS (default true), SMTP_SSL (default false),
    SMTP_REPLY_TO (optional), FALLBACK_NOTIFY_EMAIL (optional, secret/env only)

GitHub configuration:
    GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_API_URL (optional)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from urllib import error, parse, request
from zoneinfo import ZoneInfo

STATE_VERSION = 1
DEFAULT_STATE_PATH = Path(".github/branch-cleanup/state.json")
PACIFIC = ZoneInfo("America/Los_Angeles")

PROTECTED_PATTERNS = [
    re.compile(r"^(main|master|develop|development|staging|production)$"),
    re.compile(r"^(release|hotfix)/"),
    re.compile(r"^dependabot/"),
]

OPT_OUT_RE = re.compile(r"(?i)(?:^|\s)/opt-out(?:\s|$)|^\s*opt[\s-]?out\s*$")
OPT_IN_RE = re.compile(r"(?i)(?:^|\s)/opt-in(?:\s|$)|^\s*opt[\s-]?in\s*$")
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def redact_emails(text: str) -> str:
    """Keep email addresses out of logs and public issue bodies."""
    return EMAIL_RE.sub("<redacted>", text)


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------
def load_state(path: Path) -> dict[str, Any]:
    """Load state. Email addresses are never stored in state."""
    if not path.exists():
        return {"version": STATE_VERSION, "last_run_date": None,
                "excluded": {}, "notices": {}}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("version", STATE_VERSION)
    data.setdefault("last_run_date", None)
    data.setdefault("excluded", {})
    data.setdefault("notices", {})
    for key in ("emails", "logins", "fallback_email"):
        data.pop(key, None)
    for notice in data["notices"].values():
        if isinstance(notice, dict):
            notice.pop("email", None)
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def reset_notice_window(notice: dict[str, Any]) -> None:
    notice.update({
        "last_notified_on": None,
        "first_notified_on": None,
        "notified_days": [],
        "email_sent": False,
        "delete_on": None,
        "late_notice": False,
        "notice_window_days": None,
    })


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------
def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True, capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def remote_branches(repo: Path, default_branch: str) -> list[str]:
    out = git(repo, "for-each-ref", "--format=%(refname:short)",
              "refs/remotes/origin")
    branches = []
    for ref in out.splitlines():
        ref = ref.strip()
        if not ref or ref == "origin/HEAD":
            continue
        branch = ref.removeprefix("origin/")
        if branch and branch != default_branch:
            branches.append(branch)
    return sorted(set(branches))


@dataclass
class CommitInfo:
    sha: str
    timestamp: int
    email: str
    name: str


def _commit_from_line(line: str) -> CommitInfo | None:
    try:
        ts, sha, email, name = line.split("\x00", 3)
        return CommitInfo(sha=sha, timestamp=int(ts), email=email, name=name)
    except (TypeError, ValueError):
        return None


def last_commit(repo: Path, branch: str) -> CommitInfo | None:
    try:
        out = git(repo, "log", "-1", "--format=%ct%x00%H%x00%ae%x00%an",
                  f"origin/{branch}").strip("\n")
    except RuntimeError:
        return None
    return _commit_from_line(out) if out else None


def first_branch_author(repo: Path, branch: str, default_branch: str) -> CommitInfo | None:
    """Best-effort branch creator: first commit unique to this branch."""
    try:
        out = git(repo, "log", "--reverse",
                  "--format=%ct%x00%H%x00%ae%x00%an",
                  f"origin/{default_branch}..origin/{branch}")
    except RuntimeError:
        out = ""
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        return last_commit(repo, branch)
    return _commit_from_line(lines[0])


def usable_email(email: str | None) -> bool:
    """True if the address is deliverable enough to use for notices."""
    if not email:
        return False
    email = email.strip()
    if any(ch in email for ch in "\r\n,; \t"):
        return False
    local, sep, domain = email.rpartition("@")
    if not sep or not local or "." not in domain:
        return False
    low = email.lower()
    return "noreply" not in low and not low.endswith("users.noreply.github.com")


def notification_contact(creator: CommitInfo | None,
                         fallback: CommitInfo | None) -> CommitInfo | None:
    """Return the branch creator iff their commit email is deliverable.

    Only the creator is notified. Other commit authors are not substitutes:
    every contributor is expected to set a real, verified email during
    onboarding. GitHub noreply addresses are rejected because mail cannot be
    delivered to them.
    """
    candidate = creator or fallback
    if candidate and usable_email(candidate.email):
        return candidate
    return None


def is_protected(branch: str) -> bool:
    return any(pattern.search(branch) for pattern in PROTECTED_PATTERNS)


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------
class GitHub:
    def __init__(self, repo: str, token: str, api_url: str = "https://api.github.com"):
        if "/" not in repo:
            raise ValueError("GITHUB_REPOSITORY must be owner/repo")
        self.owner, self.name = repo.split("/", 1)
        self.token = token
        self.api_url = api_url.rstrip("/")

    def request(self, method: str, path: str, payload: dict | None = None) -> Any:
        url = f"{self.api_url}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:500]
            raise RuntimeError(
                f"GitHub API {method} {path} -> {exc.code}: {body}"
            ) from exc

    def open_pr_exists(self, branch: str) -> bool:
        query = parse.urlencode({
            "state": "open",
            "head": f"{self.owner}:{branch}",
            "per_page": 1,
        })
        data = self.request("GET", f"/repos/{self.owner}/{self.name}/pulls?{query}")
        return bool(data)

    def find_issue(self, branch: str) -> dict | None:
        prefix = "[branch-cleanup] branch: "
        for page in range(1, 11):
            issues = self.request(
                "GET",
                f"/repos/{self.owner}/{self.name}/issues?"
                f"state=all&sort=created&direction=desc&per_page=100&page={page}",
            )
            for issue in issues or []:
                if "pull_request" in issue:
                    continue
                title = issue.get("title", "")
                if not title.startswith(prefix) or title[len(prefix):] != branch:
                    continue
                if "branch-cleanup:trace" in issue.get("body", ""):
                    return issue
            if len(issues or []) < 100:
                break
        return None

    def commit_author_login(self, sha: str) -> str | None:
        data = self.request(
            "GET", f"/repos/{self.owner}/{self.name}/commits/{sha}"
        )
        return ((data or {}).get("author") or {}).get("login")

    def reopen_issue(self, issue_number: int) -> None:
        self.request(
            "PATCH",
            f"/repos/{self.owner}/{self.name}/issues/{issue_number}",
            {"state": "open"},
        )

    def create_issue(self, branch: str, title: str, body: str) -> dict:
        return self.request(
            "POST",
            f"/repos/{self.owner}/{self.name}/issues",
            {"title": title, "body": body},
        )

    def comment(self, issue_number: int, body: str) -> None:
        self.request(
            "POST",
            f"/repos/{self.owner}/{self.name}/issues/{issue_number}/comments",
            {"body": body},
        )

    def close_issue(self, issue_number: int) -> None:
        self.request(
            "PATCH",
            f"/repos/{self.owner}/{self.name}/issues/{issue_number}",
            {"state": "closed"},
        )

    def comments(self, issue_number: int) -> list[dict]:
        result = []
        for page in range(1, 11):
            data = self.request(
                "GET",
                f"/repos/{self.owner}/{self.name}/issues/{issue_number}/comments?"
                f"per_page=100&page={page}",
            ) or []
            result.extend(data)
            if len(data) < 100:
                break
        return result

    def delete_branch(self, branch: str) -> None:
        encoded = parse.quote(branch, safe="")
        self.request(
            "DELETE",
            f"/repos/{self.owner}/{self.name}/git/refs/heads/{encoded}",
        )


def github_from_env() -> GitHub | None:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    api_url = os.getenv("GITHUB_API_URL") or "https://api.github.com"
    return GitHub(repo, token, api_url)


def resolve_trusted_logins(gh: GitHub | None, notice: dict[str, Any] | None,
                           creator: CommitInfo | None,
                           contact: CommitInfo | None) -> tuple[str | None, set[str]]:
    """Resolve GitHub logins allowed to opt a branch out.

    Commit emails are not authoritative for GitHub identity: a commit is only
    linked to an account when its author email is verified on that account. Ask
    the API for the creator and notification contact, and keep previously
    resolved logins as fallbacks.
    """
    creator_login = (notice or {}).get("creator_login")
    trusted = {
        str(login).lower()
        for login in (notice or {}).get("trusted_logins", [])
        if login
    }
    if gh:
        seen: set[str] = set()
        for candidate, is_creator in ((creator, True), (contact, False)):
            if not candidate or candidate.sha in seen:
                continue
            seen.add(candidate.sha)
            try:
                login = gh.commit_author_login(candidate.sha)
            except Exception as exc:
                print(f"  warning: could not resolve GitHub login for "
                      f"{candidate.sha[:12]}: {exc}", file=sys.stderr)
                continue
            if login:
                if is_creator:
                    creator_login = login
                trusted.add(login.lower())
    trusted.discard("")
    return creator_login, trusted


# ---------------------------------------------------------------------------
# email
# ---------------------------------------------------------------------------
class EmailNotConfigured(RuntimeError):
    pass


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if not value or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def email_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def configured_fallback_email() -> str:
    """Fallback address from the environment/secret; never from state."""
    value = (os.getenv("FALLBACK_NOTIFY_EMAIL") or "").strip()
    return value if usable_email(value) else ""


def send_email(to: str, subject: str, body: str) -> None:
    if not email_configured():
        raise EmailNotConfigured(
            "SMTP_HOST and SMTP_FROM must be set (GitHub Actions secrets)."
        )
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT") or "587")
    sender = os.environ["SMTP_FROM"]
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    use_ssl = env_bool("SMTP_SSL", False)
    use_tls = env_bool("SMTP_TLS", True)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    if os.getenv("SMTP_REPLY_TO"):
        msg["Reply-To"] = os.environ["SMTP_REPLY_TO"]
    msg.set_content(body)

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as smtp:
            if user:
                smtp.login(user, password or "")
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if use_tls:
                smtp.starttls(context=context)
            if user:
                smtp.login(user, password or "")
            smtp.send_message(msg)


# ---------------------------------------------------------------------------
# policy
# ---------------------------------------------------------------------------
def pacific_today() -> str:
    return datetime.now(PACIFIC).date().isoformat()


def notice_subject(branch: str, delete_on: str) -> str:
    return f"[branch-cleanup:{branch}] Branch will be deleted on {delete_on} unless you opt out"


def deletion_reason(commit: CommitInfo, delete_on: str, start_days: int,
                    delete_after_days: int) -> str:
    policy_date = (
        datetime.fromtimestamp(commit.timestamp, PACIFIC).date()
        + timedelta(days=delete_after_days)
    ).isoformat()
    if delete_on == policy_date:
        return f"day {delete_after_days} of inactivity"
    window = max(1, delete_after_days - start_days)
    return f"{window}-day catch-up notice window after a delayed notice"


def build_notice(*, branch: str, commit: CommitInfo, creator: CommitInfo,
                 age_days: int, delete_on: str, issue_url: str | None,
                 start_days: int, delete_after_days: int,
                 fallback_author: CommitInfo | None = None) -> tuple[str, str]:
    subject = notice_subject(branch, delete_on)
    greeting = "Hi," if fallback_author else (
        f"Hi {creator.name}," if creator.name else "Hi,"
    )
    lines = [
        greeting,
        "",
        f"The branch `{branch}` has had no commits for {age_days} days.",
        f"Last commit: {commit.sha[:12]} on "
        f"{datetime.fromtimestamp(commit.timestamp, PACIFIC).date().isoformat()} "
        f"by {commit.name}.",
    ]
    if fallback_author:
        lines += [
            "",
            f"The commit author ({fallback_author.name}) has no deliverable "
            f"email, so this notice was sent to the fallback maintainer "
            f"address.",
        ]
    lines += [
        "",
        f"Per policy, it will be deleted on {delete_on} "
        f"({deletion_reason(commit, delete_on, start_days, delete_after_days)}).",
        "",
        "To keep this branch, opt out before then:",
    ]
    if issue_url:
        lines += [
            f"  1. Open {issue_url} and comment `/opt-out`.",
            "  2. Or run: python scripts/branch_cleanup.py remove "
            f"{branch}",
        ]
    else:
        lines.append(
            "  Run: python scripts/branch_cleanup.py remove " + branch
        )
    lines += [
        "",
        "If you do nothing, it will be deleted automatically.",
        "",
        f"(Notice window: days {start_days}-{delete_after_days - 1} of inactivity.)",
    ]
    return subject, "\n".join(lines)


def build_issue_body(*, branch: str, commit: CommitInfo, creator: CommitInfo,
                     age_days: int, delete_on: str, start_days: int,
                     delete_after_days: int) -> str:
    return "\n".join([
        "<!-- branch-cleanup:trace -->",
        f"Automated inactivity notice for branch `{branch}`.",
        "",
        f"- Creator: {creator.name}",
        f"- Last commit: {commit.sha[:12]} on "
        f"{datetime.fromtimestamp(commit.timestamp, PACIFIC).date().isoformat()}",
        f"- Inactive for: {age_days} days",
        f"- Scheduled deletion: {delete_on} "
        f"({deletion_reason(commit, delete_on, start_days, delete_after_days)})",
        "",
        "To keep this branch, comment `/opt-out` before the deletion date.",
        f"To opt back in later, comment `/opt-in` or run "
        f"`python scripts/branch_cleanup.py add {branch}`.",
        "",
        f"Notice window: days {start_days}-{delete_after_days - 1} of inactivity.",
    ])


def process_issue_replies(gh: GitHub, state: dict[str, Any], branch: str,
                          notice: dict[str, Any], *, dry_run: bool) -> bool:
    """Apply /opt-out and /opt-in comments.

    Returns True when the branch should be skipped (excluded, or the replies
    could not be read). Failing closed prevents deleting a branch whose opt-out
    comment we were unable to check.
    """
    issue_number = notice.get("issue_number")
    if not issue_number:
        return branch in state["excluded"]
    try:
        comments = gh.comments(int(issue_number))
    except Exception as exc:
        print(f"  warning: could not read comments for {branch}: {exc}; "
              f"keeping branch for this run", file=sys.stderr)
        return True

    last_seen = int(notice.get("last_processed_comment_id") or 0)
    trusted_logins = {
        str(login).lower()
        for login in (
            [notice.get("creator_login")]
            + list(notice.get("trusted_logins") or [])
        )
        if login
    }
    for comment in sorted(comments, key=lambda c: int(c.get("id", 0))):
        cid = int(comment.get("id", 0))
        if cid <= last_seen:
            continue
        user = comment.get("user") or {}
        if user.get("type") == "Bot":
            last_seen = cid
            continue
        login = (user.get("login") or "").lower()
        association = (comment.get("author_association") or "").upper()
        if not login or (
            association not in TRUSTED_ASSOCIATIONS
            and login not in trusted_logins
        ):
            print(f"  ignore: comment by {login or 'unknown'} on #{issue_number} "
                  f"(not branch creator or maintainer)")
            last_seen = cid
            continue
        body = comment.get("body", "") or ""
        if OPT_OUT_RE.search(body):
            state["excluded"][branch] = {
                "reason": "opted out via tracking issue",
                "at": datetime.now(timezone.utc).isoformat(),
                "by": login,
            }
            print(f"  opt-out: {branch} (issue #{issue_number})")
            if not dry_run:
                gh.comment(int(issue_number),
                           "Opt-out recorded. This branch will not be deleted automatically.")
                gh.close_issue(int(issue_number))
                notice["closed_at"] = datetime.now(timezone.utc).isoformat()
        elif OPT_IN_RE.search(body):
            state["excluded"].pop(branch, None)
            reset_notice_window(notice)
            print(f"  opt-in: {branch} (issue #{issue_number})")
        last_seen = cid
    notice["last_processed_comment_id"] = last_seen
    return branch in state["excluded"]


def cmd_run(args: argparse.Namespace) -> int:
    repo = Path(args.repo_path).resolve()
    state_path = Path(args.state_file)
    state = load_state(state_path)
    today = args.today or pacific_today()

    if state.get("last_run_date") == today and not args.force:
        print(f"branch-cleanup already ran for {today}; use --force to rerun.")
        return 0

    gh = None if args.offline else github_from_env()
    if not args.offline and gh is None:
        print("warning: GITHUB_TOKEN/GITHUB_REPOSITORY not set; "
              "issue tracking and API deletion are disabled.", file=sys.stderr)

    branches = remote_branches(repo, args.default_branch)
    if not branches:
        print("No remote branches found. Did you fetch with --prune?")
        return 1

    today_date = date.fromisoformat(today)
    fallback_email = configured_fallback_email()
    changed = False
    delete_candidates = 0
    notify_candidates = 0

    for branch in branches:
        if is_protected(branch):
            continue
        commit = last_commit(repo, branch)
        if commit is None:
            continue
        commit_date = datetime.fromtimestamp(commit.timestamp, PACIFIC).date()
        age_days = max(0, (today_date - commit_date).days)
        policy_delete_on = (
            commit_date + timedelta(days=args.delete_after_days)
        ).isoformat()
        late_window_days = max(1, args.delete_after_days - args.start_notice_days)
        creator = first_branch_author(repo, branch, args.default_branch) or commit
        contact = notification_contact(creator, commit)

        notice = state["notices"].get(branch)
        if notice and notice.get("last_commit") != commit.sha:
            notice.update({
                "last_commit": commit.sha,
                "last_commit_at": commit.timestamp,
            })
            reset_notice_window(notice)
            changed = True

        notices_sent = len(set((notice or {}).get("notified_days", [])))
        if notice and notice.get("email_sent"):
            is_late = bool(notice.get("late_notice"))
            delete_on = notice.get("delete_on") or (
                (today_date + timedelta(days=late_window_days)).isoformat()
                if is_late else policy_delete_on
            )
            if (is_late and notices_sent < late_window_days
                    and date.fromisoformat(delete_on) <= today_date):
                delete_on = (today_date + timedelta(days=1)).isoformat()
        else:
            is_late = age_days >= args.delete_after_days
            delete_on = (
                (today_date + timedelta(days=late_window_days)).isoformat()
                if is_late else policy_delete_on
            )

        creator_login = (notice or {}).get("creator_login")
        trusted_logins: set[str] = set()
        login_resolved = False
        if gh and (notice or age_days >= args.start_notice_days):
            creator_login, trusted_logins = resolve_trusted_logins(
                gh, notice, creator, contact
            )
            login_resolved = True
            if notice:
                known_trusted = sorted(notice.get("trusted_logins") or [])
                if (notice.get("creator_login") != creator_login
                        or known_trusted != sorted(trusted_logins)):
                    notice["creator_login"] = creator_login
                    notice["trusted_logins"] = sorted(trusted_logins)
                    changed = True

        if (notice and gh and not args.dry_run
                and process_issue_replies(gh, state, branch, notice,
                                          dry_run=args.dry_run)):
            changed = True
            continue

        if branch in state["excluded"]:
            if (notice and gh and not args.dry_run
                    and notice.get("issue_number") and not notice.get("closed_at")):
                try:
                    gh.comment(int(notice["issue_number"]),
                               "Branch is opted out; no automatic deletion.")
                    gh.close_issue(int(notice["issue_number"]))
                    notice["closed_at"] = datetime.now(timezone.utc).isoformat()
                    changed = True
                except Exception as exc:
                    print(f"  warning: could not close issue for {branch}: {exc}")
            if args.dry_run:
                print(f"skip    {branch}: opted out")
            continue

        if age_days < args.start_notice_days:
            continue
        notice_delete_on = (notice or {}).get("delete_on") or policy_delete_on
        enough_notices = (
            not (notice or {}).get("late_notice")
            or notices_sent >= late_window_days
        )
        if (age_days >= args.delete_after_days and notice
                and notice.get("email_sent")
                and today_date >= date.fromisoformat(notice_delete_on)
                and enough_notices):
            delete_candidates += 1
            if gh is None and notice.get("issue_number"):
                print(f"keep    {branch}: GitHub token required to verify "
                      f"issue opt-outs")
                continue
            if args.skip_open_prs and gh:
                try:
                    if gh.open_pr_exists(branch):
                        print(f"keep    {branch}: open pull request")
                        continue
                except Exception as exc:
                    print(f"keep    {branch}: could not check open PRs ({exc})")
                    continue
            print(f"delete  {branch}: inactive {age_days} days "
                  f"(last commit {commit.sha[:12]})")
            if args.dry_run:
                continue
            try:
                if gh:
                    gh.delete_branch(branch)
                else:
                    git(repo, "push", "origin", "--delete", branch)
            except Exception as exc:
                print(f"  warning: failed to delete {branch}: {exc}", file=sys.stderr)
                continue
            if notice.get("issue_number") and gh:
                try:
                    gh.comment(int(notice["issue_number"]),
                               f"Branch deleted after {age_days} days of inactivity.")
                    gh.close_issue(int(notice["issue_number"]))
                except Exception as exc:
                    print(f"  warning: could not close issue for {branch}: {exc}")
            notice["deleted_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
            continue

        # Notification window, or a missed window (age >= 15 without notice).
        already_notified_today = notice and notice.get("last_notified_on") == today
        if already_notified_today:
            continue

        creator_linked = True
        if gh:
            creator_linked = bool(creator_login)
        recipient = contact.email if contact and creator_linked else ""
        used_fallback = False
        if not recipient and fallback_email:
            recipient = fallback_email
            used_fallback = True
        if not recipient:
            reason = ("branch creator's commit email is not verified/linked "
                      "to a GitHub account" if gh and not creator_linked
                      else "branch creator has no deliverable commit email")
            print(
                f"skip    {branch}: {reason} (creator: {creator.name}). "
                f"The creator must set git user.email to a real, verified "
                f"address, or a maintainer must configure "
                f"FALLBACK_NOTIFY_EMAIL.",
                file=sys.stderr,
            )
            continue

        notify_candidates += 1
        issue_url = (notice or {}).get("issue_url")
        title = f"[branch-cleanup] branch: {branch}"
        issue_body = build_issue_body(
            branch=branch, commit=commit, creator=creator, age_days=age_days,
            delete_on=delete_on, start_days=args.start_notice_days,
            delete_after_days=args.delete_after_days,
        )

        recipient_label = "fallback" if used_fallback else "branch creator"
        if args.dry_run:
            print(f"notify  {branch}: inactive {age_days} days -> "
                  f"{recipient_label} (dry-run)")
            continue

        if gh and not issue_url:
            try:
                issue = gh.find_issue(branch) or gh.create_issue(branch, title, issue_body)
                issue_url = issue.get("html_url")
                notice = state["notices"].setdefault(branch, {})
                notice["issue_number"] = issue.get("number")
                notice["issue_url"] = issue_url
                if login_resolved or trusted_logins:
                    notice["creator_login"] = creator_login
                    notice["trusted_logins"] = sorted(trusted_logins)
            except Exception as exc:
                print(f"  warning: could not create issue for {branch}: {exc}",
                      file=sys.stderr)
            else:
                try:
                    if process_issue_replies(gh, state, branch, notice,
                                             dry_run=args.dry_run):
                        changed = True
                        continue
                except Exception as exc:
                    print(f"  warning: could not read issue replies for {branch}: "
                          f"{exc}", file=sys.stderr)
                if issue.get("state") == "closed":
                    try:
                        gh.reopen_issue(int(issue["number"]))
                        notice["closed_at"] = None
                    except Exception as exc:
                        print(f"  warning: could not reopen issue for {branch}: "
                              f"{exc}", file=sys.stderr)
        elif gh and notice and notice.get("issue_number") and notice.get("closed_at"):
            try:
                gh.reopen_issue(int(notice["issue_number"]))
                notice["closed_at"] = None
            except Exception as exc:
                print(f"  warning: could not reopen issue for {branch}: {exc}",
                      file=sys.stderr)

        subject, body = build_notice(
            branch=branch, commit=commit, creator=contact or creator,
            age_days=age_days, delete_on=delete_on, issue_url=issue_url,
            start_days=args.start_notice_days,
            delete_after_days=args.delete_after_days,
            fallback_author=creator if used_fallback else None,
        )

        if not email_configured():
            print(f"skip    {branch}: SMTP is not configured; branch will not be "
                  f"deleted without a sent notice.", file=sys.stderr)
            continue
        try:
            send_email(recipient, subject, body)
        except Exception as exc:
            detail = redact_emails(str(exc))
            print(f"  warning: failed to email {recipient_label} for "
                  f"{branch}: {detail}", file=sys.stderr)
            continue

        notice = state["notices"].setdefault(branch, {})
        notice.update({
            "email_fallback": used_fallback,
            "last_commit": commit.sha,
            "last_commit_at": commit.timestamp,
            "last_notified_on": today,
            "first_notified_on": notice.get("first_notified_on") or today,
            "notified_days": sorted(set(notice.get("notified_days", []) + [age_days])),
            "email_sent": True,
            "delete_on": delete_on,
            "late_notice": is_late,
            "notice_window_days": late_window_days,
        })
        if login_resolved or trusted_logins:
            notice["creator_login"] = creator_login
            notice["trusted_logins"] = sorted(trusted_logins)
        changed = True
        print(f"notify  {branch}: inactive {age_days} days -> "
              f"{recipient_label}")

    state["last_run_date"] = today
    if changed and not args.dry_run:
        save_state(state_path, state)
        print(f"state updated: {state_path}")
    print(f"done: {notify_candidates} notice(s), {delete_candidates} deletion candidate(s)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo_path).resolve()
    state = load_state(Path(args.state_file))
    today_date = date.fromisoformat(pacific_today())
    branches = remote_branches(repo, args.default_branch)
    gh = github_from_env()
    if gh is None:
        print("note: GITHUB_TOKEN/GITHUB_REPOSITORY not set; email "
              "verification was not checked.", file=sys.stderr)
    fallback_email = configured_fallback_email()
    missing_contacts: list[str] = []
    for branch in branches:
        commit = last_commit(repo, branch)
        if commit is None:
            continue
        commit_date = datetime.fromtimestamp(commit.timestamp, PACIFIC).date()
        age = max(0, (today_date - commit_date).days)
        notice = state["notices"].get(branch) or {}
        protected = is_protected(branch)
        if protected:
            status = "protected"
        elif branch in state.get("excluded", {}):
            status = "excluded"
        elif notice.get("deleted_at"):
            status = "deleted"
        elif notice.get("email_sent"):
            status = f"notified ({notice.get('last_notified_on')})"
            if notice.get("delete_on"):
                status += f", delete {notice['delete_on']}"
            if notice.get("late_notice"):
                sent = len(set(notice.get("notified_days", [])))
                need = notice.get("notice_window_days") or 3
                status += f", catch-up {sent}/{need}"
        elif age >= args.start_notice_days:
            status = "notice due"
        else:
            status = "active"

        creator = first_branch_author(repo, branch, args.default_branch) or commit
        contact = notification_contact(creator, commit)
        creator_login = notice.get("creator_login")
        creator_linked = True
        if gh and not protected:
            creator_login, _ = resolve_trusted_logins(gh, notice, creator, contact)
            creator_linked = bool(creator_login)
        notify_email = contact.email if contact and creator_linked else ""
        is_fallback = False
        if not notify_email and fallback_email:
            notify_email = fallback_email
            is_fallback = True
        if not protected and not notify_email:
            missing_contacts.append(branch)
        login = creator_login or notice.get("creator_login")
        contact_text = "fallback" if is_fallback else (
            "branch creator" if notify_email else "MISSING"
        )
        if contact and not creator_linked:
            contact_text += " (email unverified)"
        if login:
            contact_text += f" (login {login})"
        print(f"{branch}\t{age}d\t{status}\t{commit.sha[:12]}\t"
              f"notify={contact_text}")

    if missing_contacts:
        print("\nNo deliverable branch-creator email (missing/noreply/unverified):")
        print("  The creator must set git user.email to a real, verified "
              "address (see CONTRIBUTING.md), or a maintainer must configure "
              "FALLBACK_NOTIFY_EMAIL.")
        for branch in missing_contacts:
            print(f"  {branch}")

    excluded = state.get("excluded", {})
    if excluded:
        print("\nExcluded:")
        for branch, meta in sorted(excluded.items()):
            print(f"  {branch}\t{meta.get('reason', '')}\t{meta.get('at', '')}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    path = Path(args.state_file)
    state = load_state(path)
    removed = state.get("excluded", {}).pop(args.branch, None)
    if removed:
        print(f"added {args.branch} back to the auto-deletion program")
    else:
        print(f"{args.branch} is already in the auto-deletion program")
    if args.clear_notice:
        state.get("notices", {}).pop(args.branch, None)
    elif args.branch in state.get("notices", {}):
        reset_notice_window(state["notices"][args.branch])
    save_state(path, state)
    print(f"state: {path} (commit this file to persist the change)")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    path = Path(args.state_file)
    state = load_state(path)
    state.setdefault("excluded", {})[args.branch] = {
        "reason": args.note or "manual opt-out",
        "at": datetime.now(timezone.utc).isoformat(),
        "by": os.getenv("GITHUB_ACTOR", "local"),
    }
    save_state(path, state)
    print(f"excluded {args.branch} from auto-deletion")
    print(f"state: {path} (commit this file to persist the change)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--state-file", default=str(DEFAULT_STATE_PATH),
                        help="path to state JSON")
    common.add_argument("--repo-path", default=".",
                        help="git repository path")
    common.add_argument("--default-branch", default=os.getenv("DEFAULT_BRANCH", "main"))

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", parents=[common], help="run the cleanup policy")
    run_p.add_argument("--dry-run", action="store_true")
    run_p.add_argument("--offline", action="store_true",
                       help="do not call the GitHub API")
    run_p.add_argument("--force", action="store_true",
                       help="run even if already ran today")
    run_p.add_argument("--today", help="YYYY-MM-DD override for tests")
    run_p.add_argument("--start-notice-days", type=int, default=12)
    run_p.add_argument("--delete-after-days", type=int, default=15)
    run_p.add_argument("--no-open-pr-check", dest="skip_open_prs",
                       action="store_false", default=True)
    run_p.set_defaults(func=cmd_run)

    status_p = sub.add_parser("status", parents=[common], help="show branch ages/state")
    status_p.add_argument("--start-notice-days", type=int, default=12)
    status_p.set_defaults(func=cmd_status)

    add_p = sub.add_parser("add", parents=[common],
                           help="enroll a branch / opt back in")
    add_p.add_argument("branch")
    add_p.add_argument("--clear-notice", action="store_true")
    add_p.set_defaults(func=cmd_add)

    remove_p = sub.add_parser("remove", parents=[common],
                              help="opt a branch out of auto-deletion")
    remove_p.add_argument("branch")
    remove_p.add_argument("--note")
    remove_p.set_defaults(func=cmd_remove)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    start_days = getattr(args, "start_notice_days", 12)
    delete_days = getattr(args, "delete_after_days", 15)
    if start_days < 1 or delete_days < 1:
        parser.error("--start-notice-days and --delete-after-days must be positive")
    if start_days >= delete_days:
        parser.error("--start-notice-days must be less than --delete-after-days")
    if getattr(args, "today", None):
        try:
            date.fromisoformat(args.today)
        except ValueError:
            parser.error("--today must be YYYY-MM-DD")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
