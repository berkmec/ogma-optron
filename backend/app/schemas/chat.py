from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    message_id: str
    observation_id: str
    role: ChatRole
    content: str
    model_used: str = ""
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow)
