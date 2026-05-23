from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.clawbridge.wrapper import (
    DEFAULT_MAX_OUTPUT_CHARS,
    DEFAULT_TIMEOUT_S,
    run_repo_review,
)
from app.schemas.clawbridge import ClawPermissionProfile, ClawRun
from app.services import sqlite_store

router = APIRouter(prefix="/api/clawbridge", tags=["clawbridge"])


class ReviewRequest(BaseModel):
    workspace_path: str
    prompt: str = "Review this repository."
    permission_profile: ClawPermissionProfile = ClawPermissionProfile.READ_ONLY
    timeout_s: int = DEFAULT_TIMEOUT_S
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS


@router.post("/review", response_model=ClawRun)
def review(req: ReviewRequest) -> ClawRun:
    run = run_repo_review(
        workspace_path=req.workspace_path,
        user_prompt=req.prompt,
        profile=req.permission_profile,
        timeout_s=req.timeout_s,
        max_output_chars=req.max_output_chars,
    )
    sqlite_store.save_claw_run(run)
    return run


@router.get("/runs/{run_id}", response_model=ClawRun)
def get_run(run_id: str) -> ClawRun:
    run = sqlite_store.get_claw_run(run_id)
    if not run:
        raise HTTPException(404, f"ClawRun not found: {run_id}")
    return run
