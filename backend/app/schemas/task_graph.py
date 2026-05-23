from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow
from app.schemas.intent import IntentKind


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskNode(BaseModel):
    task_id: str
    task_type: str
    description: str
    required_agent: str
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    output_summary: str = ""


class TaskGraph(BaseModel):
    graph_id: str
    intent_id: str
    asset_id: str
    observation_id: str
    intent_kind: IntentKind
    nodes: list[TaskNode]
    created_at: datetime = Field(default_factory=utcnow)
