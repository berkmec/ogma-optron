"""Read-only workspace scanner for ClawBridge.

The agent.exe subprocess runs with --permission-mode deny, meaning it cannot
read files on its own. Instead, we scan the workspace in Python (bounded by
size, depth, count) and inject the structure + key file contents into the
prompt as context. This keeps the read-only guarantee enforceable from the
Python side and avoids depending on agent.exe's permission internals.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

MAX_FILES = 200
MAX_DEPTH = 4
MAX_FILE_BYTES = 50_000

IMPORTANT_FILENAMES: set[str] = {
    "README", "README.md", "README.txt", "README.rst",
    "LICENSE", "LICENSE.md", "LICENSE.txt",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "Pipfile", "poetry.lock",
    "package.json", "tsconfig.json", "vite.config.ts", "vite.config.js",
    "Cargo.toml",
    "go.mod",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".gitignore", ".env.example",
    "CHANGELOG.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
}

IGNORED_DIRS: set[str] = {
    ".git", "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".idea", ".vscode",
    "target", "dist", "build", ".next", ".turbo",
    "out", ".cache",
}


class WorkspaceScan(NamedTuple):
    files: list[str]
    file_contents: dict[str, str]
    truncated: bool


def scan_workspace(workspace: Path) -> WorkspaceScan:
    files: list[str] = []
    file_contents: dict[str, str] = {}
    truncated = False

    for root, dirs, file_list in os.walk(workspace):
        rel_root = Path(root).relative_to(workspace)
        depth = 0 if str(rel_root) == "." else len(rel_root.parts)
        if depth > MAX_DEPTH:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
        dirs.sort()
        for name in sorted(file_list):
            if len(files) >= MAX_FILES:
                truncated = True
                break
            full = Path(root) / name
            try:
                rel = full.relative_to(workspace).as_posix()
            except ValueError:
                continue
            files.append(rel)
            if name in IMPORTANT_FILENAMES:
                try:
                    size = full.stat().st_size
                except OSError:
                    continue
                if size > MAX_FILE_BYTES:
                    continue
                try:
                    file_contents[rel] = full.read_text(
                        encoding="utf-8", errors="replace"
                    )[:MAX_FILE_BYTES]
                except OSError:
                    continue
        if len(files) >= MAX_FILES:
            truncated = True
            break

    return WorkspaceScan(files=files, file_contents=file_contents, truncated=truncated)
