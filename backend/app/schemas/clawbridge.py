from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow


class ClawRunStatus(str, Enum):
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


class ClawPermissionProfile(str, Enum):
    READ_ONLY = "read_only"  # agent.exe --permission-mode deny + workspace scanner context
    PLAN = "plan"            # agent.exe --permission-mode plan


class ClawRun(BaseModel):
    run_id: str
    workspace_path: str
    prompt: str
    permission_profile: ClawPermissionProfile
    status: ClawRunStatus
    output: str = ""
    files_scanned: list[str] = Field(default_factory=list)
    files_read: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    timeout_s: int = 120
    model_used: str = ""
    latency_ms: int = 0
    error: str = ""
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
