from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.asset import utcnow


class RepoIndexInfo(BaseModel):
    """Lightweight metadata about a persisted index. The actual vectors and
    chunks live under runs/repo_index/{index_id}/ — see app.repo_index.store."""

    index_id: str
    workspace_path: str
    model: str
    n_chunks: int
    n_files: int
    created_at: datetime = Field(default_factory=utcnow)


class SearchHit(BaseModel):
    """One file-level search result."""

    file_path: str
    score: float
    excerpts: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    index_id: str
    workspace_path: str
    hits: list[SearchHit] = Field(default_factory=list)
