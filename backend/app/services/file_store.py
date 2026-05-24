"""Upload validation and disk storage for visual assets.

Two entry points share the same validate-and-persist core:
  - save_upload(UploadFile)      — used by the FastAPI route
  - save_upload_from_path(Path)  — used by the CLI (no HTTP layer)

Both eventually call _persist_bytes(), which is the single source of truth
for MIME / extension / size / image validity / on-disk write.
"""

from __future__ import annotations

import mimetypes
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import REPO_ROOT
from app.schemas.asset import VisualAsset

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
UPLOAD_DIR = REPO_ROOT / "uploads"


def ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def sanitize_filename(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in "._-")
    return safe[:128] or "unnamed"


def _persist_bytes(
    raw: bytes,
    filename: str,
    mime_type: str,
) -> VisualAsset:
    """Validate, write to UPLOAD_DIR, return VisualAsset.

    Raises HTTPException so the FastAPI path keeps its 4xx semantics. The CLI
    converts these to plain stderr lines.
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, f"Unsupported MIME type: {mime_type}")
    if not raw:
        raise HTTPException(400, "Empty upload")
    if len(raw) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            413,
            f"File too large: {len(raw)} bytes (limit {MAX_FILE_SIZE_BYTES})",
        )

    ext = Path(filename or "upload.png").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported extension: {ext}")

    try:
        Image.open(BytesIO(raw)).verify()
        with Image.open(BytesIO(raw)) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, f"Invalid image: {exc}") from exc

    asset_id = str(uuid.uuid4())
    safe_name = sanitize_filename(filename or f"{asset_id}{ext}")
    storage_dir = ensure_upload_dir()
    storage_path = storage_dir / f"{asset_id}{ext}"
    storage_path.write_bytes(raw)

    return VisualAsset(
        asset_id=asset_id,
        filename=safe_name,
        mime_type=mime_type,
        width=width,
        height=height,
        size_bytes=len(raw),
        storage_path=str(storage_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    )


async def save_upload(file: UploadFile) -> VisualAsset:
    raw = await file.read()
    return _persist_bytes(
        raw=raw,
        filename=file.filename or "",
        mime_type=file.content_type or "",
    )


def save_upload_from_path(path: Path) -> VisualAsset:
    """CLI entry: read the file from disk, guess MIME from extension, persist."""
    path = path.expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(404, f"File not found: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        # mimetypes does not know .webp on every install; fall back by extension.
        ext_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        mime_type = ext_map.get(path.suffix.lower(), "")
    raw = path.read_bytes()
    return _persist_bytes(raw=raw, filename=path.name, mime_type=mime_type)


def asset_full_path(relative_path: str) -> Path:
    full = (REPO_ROOT / relative_path).resolve()
    upload_root = UPLOAD_DIR.resolve()
    if not str(full).startswith(str(upload_root)):
        raise HTTPException(403, "Path traversal blocked")
    if not full.exists():
        raise HTTPException(404, "Asset file missing on disk")
    return full
