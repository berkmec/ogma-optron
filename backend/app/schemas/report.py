from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow
from app.schemas.intent import IntentKind


class Report(BaseModel):
    report_id: str
    asset_id: str
    observation_id: str
    intent_id: str
    graph_id: str
    intent_kind: IntentKind
    title: str
    markdown: str
    model_used: str = ""
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow)
