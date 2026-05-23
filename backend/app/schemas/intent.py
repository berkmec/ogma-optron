from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow


class IntentKind(str, Enum):
    ERROR_DEBUG = "error_debug"
    REPO_REVIEW = "repo_review"
    UI_HELP = "ui_help"
    UNKNOWN = "unknown"


class IntentResult(BaseModel):
    intent_id: str
    asset_id: str
    observation_id: str
    primary_intent: IntentKind
    confidence: float = 0.0
    reasoning: str = ""
    ambiguity: list[str] = Field(default_factory=list)
    suggested_next_step: str = ""
    user_prompt: str = ""
    model_used: str = ""
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow)
