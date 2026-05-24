"""On-disk index format for repo_index.

We persist three artefacts under runs/repo_index/{index_id}/:
  - vectors.npy   (float32 ndarray of shape (n_chunks, EMBED_DIM))
  - chunks.jsonl  (one JSON object per chunk: file_path, chunk_index, ranges, text)
  - meta.json     (index_id, workspace_path, model, n_chunks, n_files, created_at)

We deliberately avoid FAISS: numpy cosine over a few thousand vectors is
faster than the FAISS import cost, and skips a heavy dependency. If a repo
grows past ~50K chunks we'll revisit.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import numpy as np

from app.config import REPO_ROOT
from app.repo_index.chunker import Chunk
from app.repo_index.embedder import EMBED_DIM

INDEX_ROOT = REPO_ROOT / "runs" / "repo_index"


def _ensure_dir(index_id: str) -> Path:
    target = INDEX_ROOT / index_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_index(
    index_id: str,
    workspace_path: str,
    model_name: str,
    chunks: list[Chunk],
    vectors: np.ndarray,
    created_at: str,
) -> Path:
    """Write vectors + chunks + meta. Returns the index directory."""
    if vectors.shape[0] != len(chunks):
        raise ValueError(
            f"vector count {vectors.shape[0]} != chunk count {len(chunks)}"
        )

    target = _ensure_dir(index_id)
    np.save(target / "vectors.npy", vectors.astype(np.float32, copy=False))
    with (target / "chunks.jsonl").open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(asdict(chunk), ensure_ascii=False))
            fh.write("\n")
    n_files = len({c.file_path for c in chunks})
    embed_dim = int(vectors.shape[1]) if vectors.size else EMBED_DIM
    meta = {
        "index_id": index_id,
        "workspace_path": workspace_path,
        "model": model_name,
        "n_chunks": len(chunks),
        "n_files": n_files,
        "embed_dim": embed_dim,
        "created_at": created_at,
    }
    (target / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return target


def load_index(index_id: str) -> tuple[dict, list[Chunk], np.ndarray]:
    """Read meta + chunks + vectors back. Raises FileNotFoundError if absent."""
    target = INDEX_ROOT / index_id
    meta_path = target / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"index {index_id} not found at {target}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    chunks: list[Chunk] = []
    with (target / "chunks.jsonl").open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            chunks.append(Chunk(**obj))
    vectors = np.load(target / "vectors.npy")
    return meta, chunks, vectors


def list_indexes() -> list[dict]:
    """Return every index's meta.json (most recent first)."""
    if not INDEX_ROOT.exists():
        return []
    out: list[dict] = []
    for entry in sorted(INDEX_ROOT.iterdir(), key=lambda p: p.name, reverse=True):
        if not entry.is_dir():
            continue
        meta_path = entry / "meta.json"
        if not meta_path.exists():
            continue
        try:
            out.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def search_top_k(
    query_vector: np.ndarray,
    vectors: np.ndarray,
    chunks: list[Chunk],
    k: int = 10,
) -> list[tuple[Chunk, float]]:
    """Cosine top-k. fastembed already L2-normalizes both sides, so this is
    a dot product."""
    if vectors.size == 0 or len(chunks) == 0:
        return []
    if query_vector.ndim == 2:
        query_vector = query_vector[0]
    scores = vectors @ query_vector.astype(np.float32, copy=False)
    k = min(k, len(chunks))
    top_idx = np.argsort(-scores)[:k]
    return [(chunks[int(i)], float(scores[int(i)])) for i in top_idx]


def search_for_files(
    query_vector: np.ndarray,
    vectors: np.ndarray,
    chunks: list[Chunk],
    k_files: int = 10,
    chunks_per_file: int = 2,
) -> list[tuple[str, float, list[Chunk]]]:
    """Collapse chunk-level results into file-level: each file's score is the
    max of its chunk scores; we keep up to `chunks_per_file` per file."""
    if vectors.size == 0 or len(chunks) == 0:
        return []
    if query_vector.ndim == 2:
        query_vector = query_vector[0]
    scores = vectors @ query_vector.astype(np.float32, copy=False)
    by_file: dict[str, list[tuple[float, Chunk]]] = {}
    for chunk, score in zip(chunks, scores):
        by_file.setdefault(chunk.file_path, []).append((float(score), chunk))
    ranked: list[tuple[str, float, list[Chunk]]] = []
    for file_path, items in by_file.items():
        items.sort(key=lambda pair: pair[0], reverse=True)
        top = items[:chunks_per_file]
        file_score = top[0][0]
        ranked.append((file_path, file_score, [chunk for _, chunk in top]))
    ranked.sort(key=lambda triple: triple[1], reverse=True)
    return ranked[:k_files]


def iter_chunks_in_batches(chunks: Iterable[Chunk], batch: int = 64) -> Iterable[list[Chunk]]:
    bucket: list[Chunk] = []
    for chunk in chunks:
        bucket.append(chunk)
        if len(bucket) >= batch:
            yield bucket
            bucket = []
    if bucket:
        yield bucket
