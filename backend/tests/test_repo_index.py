"""Repo intelligence: chunker + embedder + store + search.

We monkey-patch the embedder so the real fastembed model doesn't get
loaded during pytest (model download + first-run cost would dominate the
suite). Cosine math is verified against numpy ground truth.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.repo_index import build_index, load_for_workspace, search
from app.repo_index.chunker import (
    CHUNK_CHARS,
    CHUNK_OVERLAP,
    INDEXABLE_EXTENSIONS,
    Chunk,
    iter_chunks,
)
from app.repo_index.store import search_for_files, search_top_k

# ---------- chunker ----------


def test_indexable_extensions_cover_common_languages() -> None:
    for ext in (".py", ".ts", ".tsx", ".rs", ".md", ".toml", ".json"):
        assert ext in INDEXABLE_EXTENSIONS


def test_iter_chunks_skips_ignored_dirs_and_unindexable_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('hi')\n" * 5)
    (tmp_path / "a.bin").write_bytes(b"\x00" * 50)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("module.exports = {}\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("export const x = 1;\n" * 3)

    chunks = list(iter_chunks(tmp_path))
    file_paths = {c.file_path for c in chunks}

    assert "a.py" in file_paths
    assert "src/main.ts" in file_paths
    # ignored dirs and unindexable extensions stay out
    assert not any(fp.startswith(".git/") for fp in file_paths)
    assert not any(fp.startswith("node_modules/") for fp in file_paths)
    assert "a.bin" not in file_paths


def test_iter_chunks_uses_sliding_window_on_large_files(tmp_path: Path) -> None:
    big = "x" * (CHUNK_CHARS * 3)  # 3 windows
    (tmp_path / "big.txt").write_text(big)
    chunks = list(iter_chunks(tmp_path))
    # >= 3 chunks because of the sliding window with overlap
    assert len(chunks) >= 3
    for i in range(1, len(chunks)):
        # overlap region should overlap by CHUNK_OVERLAP characters
        prev_end = chunks[i - 1].end_char
        cur_start = chunks[i].start_char
        assert prev_end - cur_start == CHUNK_OVERLAP


# ---------- store / search ----------


def _make(vec: list[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return (arr / norm).astype(np.float32) if norm else arr


def test_search_top_k_returns_descending_scores() -> None:
    chunks = [
        Chunk("a.py", 0, 0, 5, "alpha"),
        Chunk("b.py", 0, 0, 4, "beta"),
        Chunk("c.py", 0, 0, 5, "gamma"),
    ]
    vectors = np.stack([_make([1, 0]), _make([0, 1]), _make([1, 1])])
    query = _make([1, 0])

    hits = search_top_k(query, vectors, chunks, k=3)
    assert [c.file_path for c, _ in hits] == ["a.py", "c.py", "b.py"]
    assert hits[0][1] > hits[1][1] > hits[2][1]


def test_search_for_files_collapses_chunks_per_file_with_max_score() -> None:
    chunks = [
        Chunk("a.py", 0, 0, 5, "x"),
        Chunk("a.py", 1, 4, 9, "y"),
        Chunk("b.py", 0, 0, 5, "z"),
    ]
    vectors = np.stack([_make([1, 0]), _make([1, 1]), _make([0, 1])])
    query = _make([1, 0])

    out = search_for_files(query, vectors, chunks, k_files=10, chunks_per_file=2)
    paths = [path for path, _, _ in out]
    assert paths[0] == "a.py"  # higher max score
    # a.py keeps two chunks, b.py one
    by_file = {path: chunks for path, _, chunks in out}
    assert len(by_file["a.py"]) == 2
    assert len(by_file["b.py"]) == 1


def test_search_top_k_empty_inputs_returns_empty() -> None:
    assert search_top_k(np.zeros(2), np.zeros((0, 2)), [], k=5) == []


# ---------- build_index / load_for_workspace (with mocked embedder) ----------


def _fake_embed_texts(texts, model_name=None):  # noqa: ARG001
    return np.stack([_make([float(len(t)), 1.0]) for t in texts])


def _fake_embed_query(text, model_name=None):  # noqa: ARG001
    return _make([float(len(text)), 1.0])


def test_build_index_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.repo_index.embed_texts", _fake_embed_texts)
    monkeypatch.setattr("app.repo_index.embed_query", _fake_embed_query)
    # also patch INDEX_ROOT so we don't write into runs/ during pytest
    monkeypatch.setattr(
        "app.repo_index.store.INDEX_ROOT", tmp_path / "indexes"
    )

    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "a.py").write_text("def foo(): return 1\n")
    (workspace / "b.md").write_text("# Hello\nThis is a doc.\n")

    info = build_index(str(workspace), model_name="fake-model")
    assert info.n_files == 2
    assert info.n_chunks >= 2
    assert info.workspace_path == str(workspace.resolve())

    loaded = load_for_workspace(str(workspace))
    assert loaded is not None
    assert loaded.info.index_id == info.index_id
    assert loaded.vectors.shape[0] == loaded.info.n_chunks

    hits = search(loaded, "foo function", k_files=5)
    assert hits
    assert all(0.0 <= score <= 1.0 + 1e-3 for _, score, _ in hits)


def test_build_index_missing_workspace_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_index(str(tmp_path / "nonexistent"))
