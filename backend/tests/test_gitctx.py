"""Git context tests.

We initialise a tiny git repo inside tmp_path, then assert that
collect_git_context() reports a sensible snapshot. Tests skip cleanly if
`git` is not on PATH (which can happen on minimal CI containers).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.gitctx.diff import (
    GitContext,
    collect_git_context,
    format_context_block,
    git_available,
    is_git_repo,
)

pytestmark = pytest.mark.skipif(not git_available(), reason="git not on PATH")


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], path)
    _git(["config", "user.email", "pytest@example.com"], path)
    _git(["config", "user.name", "pytest"], path)
    _git(["config", "commit.gpgsign", "false"], path)


def test_is_git_repo_negative(tmp_path: Path) -> None:
    assert is_git_repo(tmp_path) is False


def test_collect_git_context_on_nongit_returns_empty(tmp_path: Path) -> None:
    ctx = collect_git_context(tmp_path)
    assert ctx == GitContext()
    assert format_context_block(ctx) == ""


def test_collect_git_context_reports_branch_diff_and_log(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    # First commit on main
    (repo / "README.md").write_text("# repo\n")
    _git(["add", "README.md"], repo)
    _git(["commit", "-m", "initial"], repo)

    # Branch and add a change
    _git(["checkout", "-b", "feature"], repo)
    (repo / "feature.py").write_text("def f(): return 42\n")
    _git(["add", "feature.py"], repo)
    _git(["commit", "-m", "add feature"], repo)

    # Also leave one uncommitted edit
    (repo / "README.md").write_text("# repo (edited)\n")

    ctx = collect_git_context(repo, base_ref="main")
    assert ctx.is_repo is True
    assert ctx.branch == "feature"
    assert ctx.base_ref == "main"
    assert ctx.ahead == 1
    assert ctx.behind == 0
    assert any(line.endswith("add feature") for line in ctx.recent_commits)
    assert "feature.py" in ctx.diff
    assert "README.md" in ctx.uncommitted_files

    block = format_context_block(ctx)
    assert "Git context" in block
    assert "feature" in block
    assert "```diff" in block


def test_diff_truncation_flag(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    (repo / "a.txt").write_text("x\n")
    _git(["add", "."], repo)
    _git(["commit", "-m", "init"], repo)
    _git(["checkout", "-b", "huge"], repo)

    (repo / "huge.txt").write_text("z\n" * 30_000)
    _git(["add", "."], repo)
    _git(["commit", "-m", "big change"], repo)

    ctx = collect_git_context(repo, base_ref="main", max_diff_chars=2000)
    assert ctx.diff_truncated is True
    assert len(ctx.diff) <= 2000
    assert any("truncated" in w for w in ctx.warnings)
