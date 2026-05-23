from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VisualAsset(BaseModel):
    asset_id: str
    filename: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    storage_path: str
    created_at: datetime = Field(default_factory=utcnow)
