"""ClawBridge safety: blocked dirs, missing workspace, empty workspace_path.

These tests verify the guard rails without launching agent.exe — they
exercise the validate / pre-flight paths that return BLOCKED/FAILED before
any subprocess is spawned.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.clawbridge.wrapper import _validate_workspace, run_repo_review
from app.config import settings
from app.schemas.clawbridge import ClawRunStatus


def test_validate_workspace_rejects_empty() -> None:
    with pytest.raises(ValueError):
        _validate_workspace("")


def test_validate_workspace_rejects_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no_such_dir"
    with pytest.raises(ValueError):
        _validate_workspace(str(missing))


def test_validate_workspace_accepts_real(tmp_path: Path) -> None:
    resolved = _validate_workspace(str(tmp_path))
    assert resolved.exists() and resolved.is_dir()


def test_run_returns_blocked_for_missing_workspace(tmp_path: Path, monkeypatch) -> None:
    # Make the binary check pass so we hit the validate step, not the
    # missing-binary branch.
    monkeypatch.setattr(settings, "agent_code_bin", str(tmp_path / "fake_agent.exe"))
    (tmp_path / "fake_agent.exe").write_bytes(b"")

    run = run_repo_review(
        workspace_path=str(tmp_path / "does_not_exist"),
        user_prompt="x",
    )
    assert run.status is ClawRunStatus.BLOCKED
    assert "does not exist" in run.error.lower() or "directory" in run.error.lower()


def test_run_returns_failed_when_binary_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_code_bin", str(tmp_path / "no_such_agent.exe"))
    run = run_repo_review(workspace_path=str(tmp_path), user_prompt="x")
    assert run.status is ClawRunStatus.FAILED
    assert "AGENT_CODE_BIN" in run.error


def test_validate_workspace_blocks_program_files(monkeypatch) -> None:
    # Construct a path inside a blocked system dir; we don't actually need
    # it to exist because _validate_workspace checks existence first, so
    # we patch Path.exists/is_dir for the synthetic candidate.
    import app.clawbridge.wrapper as wrapper

    blocked_root = Path(r"C:\Program Files")
    if not blocked_root.exists():
        pytest.skip("Program Files not present in this environment")
    monkeypatch.setattr(
        wrapper,
        "_BLOCKED_PATHS",
        (str(blocked_root),),
    )
    # Construct a child path inside the blocked root
    candidate = blocked_root / "Common Files"
    if not candidate.exists():
        pytest.skip("blocked candidate missing")
    with pytest.raises(ValueError):
        _validate_workspace(str(candidate))
