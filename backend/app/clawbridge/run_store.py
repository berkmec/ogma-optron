"""Persist ClawBridge run artifacts under runs/claw/{run_id}/.

Stores the rendered prompt, raw stdout, raw stderr, and the serialized
ClawRun. These survive a backend restart so the user can inspect what was
actually sent and received later.
"""

from __future__ import annotations

from pathlib import Path

from app.config import REPO_ROOT
from app.schemas.clawbridge import ClawRun

RUNS_DIR = REPO_ROOT / "runs" / "claw"


def _ensure_dir(run_id: str) -> Path:
    target = RUNS_DIR / run_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_run_log(run: ClawRun, prompt: str, stdout: str, stderr: str) -> None:
    target = _ensure_dir(run.run_id)
    (target / "prompt.txt").write_text(prompt, encoding="utf-8")
    (target / "stdout.txt").write_text(stdout, encoding="utf-8")
    (target / "stderr.txt").write_text(stderr, encoding="utf-8")
    (target / "run.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
