from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import repo_index as repo_index_pkg
from app.repo_index.embedder import DEFAULT_MODEL
from app.schemas.repo_index import RepoIndexInfo, SearchHit, SearchResponse
from app.services import sqlite_store

router = APIRouter(prefix="/api/repo-index", tags=["repo-index"])


class BuildRequest(BaseModel):
    workspace_path: str
    model: str | None = None


class SearchRequest(BaseModel):
    workspace_path: str
    query: str
    k_files: int = 10
    chunks_per_file: int = 2


@router.post("/build", response_model=RepoIndexInfo)
def build(req: BuildRequest) -> RepoIndexInfo:
    try:
        info = repo_index_pkg.build_index(
            workspace_path=req.workspace_path,
            model_name=req.model or DEFAULT_MODEL,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    sqlite_store.save_repo_index(info)
    return info


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest) -> SearchResponse:
    loaded = repo_index_pkg.load_for_workspace(req.workspace_path)
    if loaded is None:
        raise HTTPException(
            404,
            f"No index found for {req.workspace_path}. Run /api/repo-index/build first.",
        )
    hits_raw = repo_index_pkg.search(
        loaded, req.query, k_files=req.k_files, chunks_per_file=req.chunks_per_file
    )
    hits = [
        SearchHit(
            file_path=path,
            score=score,
            excerpts=[c.text[:600] for c in chunks],
        )
        for path, score, chunks in hits_raw
    ]
    return SearchResponse(
        query=req.query,
        index_id=loaded.info.index_id,
        workspace_path=loaded.info.workspace_path,
        hits=hits,
    )


@router.get("", response_model=list[RepoIndexInfo])
def list_indexes(workspace_path: str | None = None) -> list[RepoIndexInfo]:
    return sqlite_store.list_repo_indexes(workspace_path)


@router.get("/{index_id}", response_model=RepoIndexInfo)
def get(index_id: str) -> RepoIndexInfo:
    info = sqlite_store.get_repo_index(index_id)
    if not info:
        raise HTTPException(404, f"index not found: {index_id}")
    return info
