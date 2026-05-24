"""Repo intelligence: chunk a workspace, embed it, semantic search.

Public surface:
    build_index(workspace_path) -> RepoIndexInfo
    load_for_workspace(workspace_path) -> LoadedIndex | None
    search(loaded, query, k_files=...) -> list[(file_path, score, [Chunk])]
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.repo_index.chunker import Chunk, iter_chunks
from app.repo_index.embedder import DEFAULT_MODEL, embed_query, embed_texts
from app.repo_index.store import (
    INDEX_ROOT,
    iter_chunks_in_batches,
    list_indexes,
    load_index,
    save_index,
    search_for_files,
    search_top_k,
)
from app.schemas.asset import utcnow
from app.schemas.repo_index import RepoIndexInfo


@dataclass(frozen=True)
class LoadedIndex:
    info: RepoIndexInfo
    chunks: list[Chunk]
    vectors: np.ndarray


def build_index(
    workspace_path: str,
    model_name: str = DEFAULT_MODEL,
) -> RepoIndexInfo:
    """Walk + chunk + embed + persist. Returns metadata only."""
    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise FileNotFoundError(f"workspace not found: {workspace}")

    chunks = list(iter_chunks(workspace))
    index_id = str(uuid.uuid4())
    created_at = utcnow()

    if not chunks:
        save_index(
            index_id=index_id,
            workspace_path=str(workspace),
            model_name=model_name,
            chunks=[],
            vectors=np.zeros((0, 0), dtype=np.float32),
            created_at=created_at.isoformat(),
        )
    else:
        batches = list(iter_chunks_in_batches(chunks, batch=64))
        per_batch_vecs: list[np.ndarray] = []
        for batch in batches:
            per_batch_vecs.append(embed_texts([c.text for c in batch], model_name))
        vectors = (
            np.concatenate(per_batch_vecs, axis=0)
            if per_batch_vecs
            else np.zeros((0, 0), dtype=np.float32)
        )
        save_index(
            index_id=index_id,
            workspace_path=str(workspace),
            model_name=model_name,
            chunks=chunks,
            vectors=vectors,
            created_at=created_at.isoformat(),
        )

    return RepoIndexInfo(
        index_id=index_id,
        workspace_path=str(workspace),
        model=model_name,
        n_chunks=len(chunks),
        n_files=len({c.file_path for c in chunks}),
        created_at=created_at,
    )


def load_for_workspace(workspace_path: str) -> LoadedIndex | None:
    """Return the most recent index for the resolved workspace, or None."""
    workspace_resolved = str(Path(workspace_path).expanduser().resolve())
    for meta in list_indexes():
        if meta.get("workspace_path") == workspace_resolved:
            loaded_meta, chunks, vectors = load_index(meta["index_id"])
            info = RepoIndexInfo(
                index_id=loaded_meta["index_id"],
                workspace_path=loaded_meta["workspace_path"],
                model=loaded_meta.get("model", DEFAULT_MODEL),
                n_chunks=loaded_meta["n_chunks"],
                n_files=loaded_meta.get("n_files", 0),
                created_at=loaded_meta["created_at"],
            )
            return LoadedIndex(info=info, chunks=chunks, vectors=vectors)
    return None


def search(
    loaded: LoadedIndex,
    query: str,
    k_files: int = 10,
    chunks_per_file: int = 2,
) -> list[tuple[str, float, list[Chunk]]]:
    """Semantic search at file granularity."""
    q = embed_query(query, loaded.info.model)
    return search_for_files(q, loaded.vectors, loaded.chunks, k_files, chunks_per_file)


__all__ = [
    "Chunk",
    "LoadedIndex",
    "INDEX_ROOT",
    "build_index",
    "load_for_workspace",
    "search",
    "search_top_k",
    "list_indexes",
]
