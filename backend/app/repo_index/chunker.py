"""Bounded, language-aware file chunker.

Two-stage approach:
  1. Walk the workspace with the same ignore rules as the read-only scanner.
  2. For each file we want to index, split into overlapping chunks that fit
     under a token budget (approximated as characters).

We deliberately keep this simple: a sliding window with overlap. A Python AST
chunker would be nicer but is brittle across languages; the embedder gives us
robustness against rough boundaries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.clawbridge.workspace_scanner import IGNORED_DIRS

MAX_FILES = 2000
MAX_FILE_BYTES = 200_000  # 200 KB upper bound per file
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200

INDEXABLE_EXTENSIONS: set[str] = {
    ".py", ".pyi",
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx",
    ".rs",
    ".go",
    ".java", ".kt", ".swift",
    ".rb",
    ".php",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx",
    ".cs",
    ".md", ".rst", ".txt",
    ".toml", ".yaml", ".yml", ".json",
    ".sh", ".bash", ".ps1",
    ".html", ".css", ".scss",
    ".sql",
}


@dataclass(frozen=True)
class Chunk:
    """One sliding-window slice of a single source file."""

    file_path: str          # workspace-relative, forward-slashes
    chunk_index: int        # 0-based index within the file
    start_char: int
    end_char: int
    text: str

    @property
    def chunk_id(self) -> str:
        return f"{self.file_path}#{self.chunk_index}"


def _should_index(path: Path) -> bool:
    if path.suffix.lower() not in INDEXABLE_EXTENSIONS:
        return False
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def _read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _slide(text: str, file_path: str) -> Iterable[Chunk]:
    if not text:
        return
    if len(text) <= CHUNK_CHARS:
        yield Chunk(
            file_path=file_path,
            chunk_index=0,
            start_char=0,
            end_char=len(text),
            text=text,
        )
        return
    step = CHUNK_CHARS - CHUNK_OVERLAP
    idx = 0
    pos = 0
    while pos < len(text):
        end = min(pos + CHUNK_CHARS, len(text))
        yield Chunk(
            file_path=file_path,
            chunk_index=idx,
            start_char=pos,
            end_char=end,
            text=text[pos:end],
        )
        if end == len(text):
            break
        pos += step
        idx += 1


def iter_chunks(workspace: Path) -> Iterable[Chunk]:
    """Yield every Chunk we plan to embed for a workspace, bounded by MAX_FILES."""
    workspace = workspace.resolve()
    seen = 0
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        dirs.sort()
        for name in sorted(files):
            if seen >= MAX_FILES:
                return
            full = Path(root) / name
            if not _should_index(full):
                continue
            try:
                rel = full.relative_to(workspace).as_posix()
            except ValueError:
                continue
            text = _read_text_safe(full)
            if text is None:
                continue
            for chunk in _slide(text, rel):
                yield chunk
            seen += 1
