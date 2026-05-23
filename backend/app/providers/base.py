"""Vision provider abstraction.

A provider takes an image (and optional prompt) and returns a normalized
VisionAnalysisResult. Concrete providers (HF Qwen, OpenAI-compatible, local
Ollama, etc.) live in sibling modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class VisionAnalysisResult(BaseModel):
    image_type: str
    description: str
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    model_used: str = ""
    raw_response: str = ""


class VisionProvider(ABC):
    @abstractmethod
    def analyze(self, image_path: Path, prompt: str = "") -> VisionAnalysisResult:
        """Run vision analysis on the image at image_path."""
