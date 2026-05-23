"""RapidOCR wrapper. CPU-only ONNX; supports Latin and CJK scripts.

First call downloads model files (~80MB) into ~/.cache/rapidocr/.
The engine is a process-wide singleton via lru_cache.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


@lru_cache(maxsize=1)
def _engine() -> RapidOCR:
    return RapidOCR()


def extract_text(image_path: Path) -> str:
    engine = _engine()
    result, _ = engine(str(image_path))
    if not result:
        return ""
    lines: list[str] = []
    for row in result:
        if len(row) >= 2 and row[1]:
            lines.append(str(row[1]))
    return "\n".join(lines)
