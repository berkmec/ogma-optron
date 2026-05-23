from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow
from app.schemas.intent import IntentKind
from app.schemas.task_graph import TaskStatus


class AgentRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    PARTIAL = "partial"


class AgentTrace(BaseModel):
    task_id: str
    task_type: str
    agent_name: str
    status: TaskStatus
    output_summary: str = ""
    detail_markdown: str = ""
    warnings: list[str] = Field(default_factory=list)
    model_used: str = ""
    latency_ms: int = 0
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    error: str = ""


class AgentRun(BaseModel):
    run_id: str
    graph_id: str
    intent_id: str
    observation_id: str
    asset_id: str
    intent_kind: IntentKind
    status: AgentRunStatus
    traces: list[AgentTrace] = Field(default_factory=list)
    total_latency_ms: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    created_at: datetime = Field(default_factory=utcnow)
