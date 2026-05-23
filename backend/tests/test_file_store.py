"""File store: filename sanitation + path traversal guard."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services.file_store import asset_full_path, sanitize_filename


def test_sanitize_filename_strips_unsafe_chars() -> None:
    # Path separators and shell-special chars must be removed. Dots are
    # kept (legitimate for extensions), but with separators gone there is
    # no path traversal vector left.
    cleaned = sanitize_filename("../../etc/passwd")
    assert "/" not in cleaned and "\\" not in cleaned
    assert cleaned.endswith("etcpasswd")

    assert sanitize_filename("hello world!.png") == "helloworld.png"
    assert sanitize_filename("ok-name_42.PNG") == "ok-name_42.PNG"


def test_sanitize_filename_caps_length() -> None:
    long = "a" * 500
    assert len(sanitize_filename(long)) <= 128


def test_sanitize_filename_fallback_when_empty() -> None:
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename("///") == "unnamed"


def test_asset_full_path_blocks_traversal(tmp_path: Path, monkeypatch) -> None:
    # Make uploads/ point at a sandbox; the helper resolves relative paths
    # against REPO_ROOT, so we move that too.
    import app.services.file_store as fs
    monkeypatch.setattr(fs, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fs, "UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "ok.png").write_bytes(b"\x89PNG\r\n")

    # Allowed path resolves cleanly.
    real = asset_full_path("uploads/ok.png")
    assert real.exists()

    # Path traversal is refused.
    with pytest.raises(HTTPException) as exc:
        asset_full_path("uploads/../../etc/passwd")
    assert exc.value.status_code == 403


def test_asset_full_path_404_when_missing(tmp_path: Path, monkeypatch) -> None:
    import app.services.file_store as fs
    monkeypatch.setattr(fs, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fs, "UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    with pytest.raises(HTTPException) as exc:
        asset_full_path("uploads/missing.png")
    assert exc.value.status_code == 404
