"""Git-aware context for code review.

Read-only subprocess calls into `git` for a workspace path. Used by
ClawBridge / CodeAgent to inject the actual diff and recent commits into
the review prompt — instead of guessing what a "PR review" means from a
screenshot alone.

We DO NOT mutate the repository (no fetch, no checkout, no reset). Every
call is bounded by a timeout and an output cap.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT_S = 15
MAX_DIFF_CHARS = 30_000
MAX_LOG_ENTRIES = 20


def git_available() -> bool:
    return shutil.which("git") is not None


def _run_git(args: list[str], cwd: Path, timeout: int = DEFAULT_TIMEOUT_S) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, "", "git unavailable or timed out"
    return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()


def is_git_repo(workspace: Path) -> bool:
    if not git_available():
        return False
    code, out, _ = _run_git(["rev-parse", "--is-inside-work-tree"], workspace, timeout=5)
    return code == 0 and out == "true"


@dataclass
class GitContext:
    """A self-contained snapshot of the repo state the reviewer should see."""

    is_repo: bool = False
    branch: str = ""
    head_sha: str = ""
    base_ref: str = ""
    base_sha: str = ""
    ahead: int = 0
    behind: int = 0
    uncommitted_files: list[str] = field(default_factory=list)
    recent_commits: list[str] = field(default_factory=list)
    diff_summary: str = ""
    diff: str = ""
    diff_truncated: bool = False
    warnings: list[str] = field(default_factory=list)


def collect_git_context(
    workspace: Path,
    base_ref: str | None = None,
    max_diff_chars: int = MAX_DIFF_CHARS,
) -> GitContext:
    """Gather a bounded GitContext for `workspace`.

    base_ref:
      - None   -> derive a sensible default: `origin/main`, then `main`,
                  then `master`, then HEAD~5.
      - "X"    -> any valid git rev (branch / SHA / tag / "HEAD~N").
    """
    ctx = GitContext()
    if not is_git_repo(workspace):
        return ctx
    ctx.is_repo = True

    code, branch, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], workspace)
    if code == 0:
        ctx.branch = branch
    code, head, _ = _run_git(["rev-parse", "HEAD"], workspace)
    if code == 0:
        ctx.head_sha = head[:12]

    # Resolve base
    candidates: list[str] = []
    if base_ref:
        candidates.append(base_ref)
    candidates.extend(["origin/main", "origin/master", "main", "master", "HEAD~5"])
    for candidate in candidates:
        code, sha, _ = _run_git(["rev-parse", candidate], workspace)
        if code == 0 and sha:
            ctx.base_ref = candidate
            ctx.base_sha = sha[:12]
            break
    if not ctx.base_ref:
        ctx.warnings.append("no usable git base ref; diff omitted")
        return ctx

    # Ahead / behind
    code, counts, _ = _run_git(
        ["rev-list", "--left-right", "--count", f"{ctx.base_ref}...HEAD"], workspace
    )
    if code == 0 and counts:
        try:
            behind_str, ahead_str = counts.split()
            ctx.behind = int(behind_str)
            ctx.ahead = int(ahead_str)
        except ValueError:
            pass

    # Uncommitted files
    code, status, _ = _run_git(["status", "--porcelain"], workspace)
    if code == 0 and status:
        for line in status.splitlines():
            line = line.rstrip()
            if not line:
                continue
            # status --porcelain: "XY path"
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                ctx.uncommitted_files.append(parts[1])

    # Recent commits on this branch since base
    code, log, _ = _run_git(
        [
            "log",
            f"-{MAX_LOG_ENTRIES}",
            "--pretty=format:%h  %an  %s",
            f"{ctx.base_ref}..HEAD",
        ],
        workspace,
    )
    if code == 0 and log:
        ctx.recent_commits = log.splitlines()

    # Diff stat
    code, stat, _ = _run_git(
        ["diff", "--stat", f"{ctx.base_ref}...HEAD"], workspace
    )
    if code == 0:
        ctx.diff_summary = stat[: max_diff_chars // 4]

    # Diff content
    code, diff, _ = _run_git(
        ["diff", f"{ctx.base_ref}...HEAD"], workspace, timeout=30
    )
    if code == 0:
        if len(diff) > max_diff_chars:
            ctx.diff = diff[:max_diff_chars]
            ctx.diff_truncated = True
            ctx.warnings.append(
                f"diff truncated from {len(diff)} to {max_diff_chars} chars"
            )
        else:
            ctx.diff = diff

    return ctx


def format_context_block(ctx: GitContext) -> str:
    """Render GitContext as a markdown-ish block to inject into the prompt."""
    if not ctx.is_repo:
        return ""
    lines = ["Git context"]
    lines.append(f"  branch:         {ctx.branch} ({ctx.head_sha})")
    if ctx.base_ref:
        lines.append(f"  base:           {ctx.base_ref} ({ctx.base_sha})")
        lines.append(f"  ahead / behind: {ctx.ahead} / {ctx.behind}")
    if ctx.uncommitted_files:
        preview = ", ".join(ctx.uncommitted_files[:8])
        more = ""
        if len(ctx.uncommitted_files) > 8:
            more = f" (+{len(ctx.uncommitted_files) - 8} more)"
        lines.append(f"  uncommitted:    {preview}{more}")
    if ctx.recent_commits:
        lines.append("  recent commits:")
        for entry in ctx.recent_commits[:10]:
            lines.append(f"    {entry}")
    if ctx.diff_summary:
        lines.append("  diff --stat:")
        for stat_line in ctx.diff_summary.splitlines()[:20]:
            lines.append(f"    {stat_line}")
    if ctx.diff:
        lines.append("  diff (truncated)" if ctx.diff_truncated else "  diff:")
        lines.append("```diff")
        lines.append(ctx.diff)
        lines.append("```")
    if ctx.warnings:
        lines.append(f"  warnings: {'; '.join(ctx.warnings)}")
    return "\n".join(lines) + "\n\n"
