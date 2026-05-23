from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow


class ImageType(str, Enum):
    ERROR_SCREEN = "error_screen"
    GITHUB_REPO = "github_repo"
    UI_DASHBOARD = "ui_dashboard"
    CODE_EDITOR = "code_editor"
    DOCUMENT_PAGE = "document_page"
    CHAT_OR_MESSAGING = "chat_or_messaging"
    OTHER = "other"


class VisualObservation(BaseModel):
    observation_id: str
    asset_id: str
    image_type: ImageType
    ocr_text: str = ""
    vision_description: str = ""
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    model_used: str = ""
    latency_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow)
