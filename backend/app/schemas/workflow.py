from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow


class WorkflowSession(BaseModel):
    """A logical sequence of observations from the same user flow.

    Example: a 4-screenshot bug report (login -> failure -> retry -> stack
    trace). The synthesis is a single markdown summary of what the flow is
    and where it broke."""

    session_id: str
    title: str = ""
    observation_ids: list[str] = Field(default_factory=list)
    synthesis_markdown: str = ""
    user_prompt: str = ""
    model_used: str = ""
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow)
