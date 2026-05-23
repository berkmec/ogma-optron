"""HuggingFace Inference Providers (router) backed Qwen3-VL provider.

Calls https://router.huggingface.co/v1/chat/completions with image_url content
and parses the model's JSON response into a VisionAnalysisResult.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from openai import OpenAI

from app.config import settings
from app.providers.base import VisionAnalysisResult, VisionProvider
from app.schemas.observation import ImageType

VISION_OBSERVE_PROMPT = """You are a visual-task observer for a code/dev agent runtime.

Look at the image and respond with VALID JSON ONLY (no markdown fences):

{
  "image_type": one of [
    "error_screen", "github_repo", "ui_dashboard",
    "code_editor", "document_page", "chat_or_messaging", "other"
  ],
  "description": "1-3 sentence concise description of what is visible",
  "key_text": "the most important visible text, verbatim",
  "warnings": ["any uncertainty or limit, optional"]
}

If the image is ambiguous, pick "other" and add a warning rather than guessing.
"""

_JSON_RE = re.compile(r"\{[\s\S]*\}")
_ALLOWED_TYPES = {e.value for e in ImageType}


def _to_data_url(image_path: Path) -> str:
    raw = image_path.read_bytes()
    suffix = (image_path.suffix.lstrip(".").lower() or "png")
    if suffix == "jpg":
        suffix = "jpeg"
    return f"data:image/{suffix};base64,{base64.b64encode(raw).decode('ascii')}"


def _parse_response(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    match = _JSON_RE.search(stripped)
    if not match:
        return {
            "image_type": "other",
            "description": text[:300],
            "warnings": ["model did not return JSON"],
        }
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "image_type": "other",
            "description": text[:300],
            "warnings": ["JSON parse failed"],
        }


def _normalize_type(value: str) -> str:
    norm = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return norm if norm in _ALLOWED_TYPES else "other"


class HFQwenVLProvider(VisionProvider):
    def __init__(self) -> None:
        if not settings.hf_token:
            raise RuntimeError(
                "HF_TOKEN is empty; configure .env before calling the provider."
            )
        self._client = OpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.hf_token,
        )
        self._model = settings.vision_model

    def analyze(self, image_path: Path, prompt: str = "") -> VisionAnalysisResult:
        data_url = _to_data_url(image_path)
        user_prompt = prompt.strip() or VISION_OBSERVE_PROMPT
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        raw = response.choices[0].message.content or ""
        parsed = _parse_response(raw)
        warnings = [str(w) for w in (parsed.get("warnings") or [])]
        description = str(parsed.get("description") or "").strip()
        key_text = parsed.get("key_text")
        if key_text and key_text not in description:
            description = description.rstrip(". ") + f". Key text: {key_text}"
        return VisionAnalysisResult(
            image_type=_normalize_type(parsed.get("image_type", "")),
            description=description,
            confidence=0.7,
            warnings=warnings,
            model_used=self._model,
            raw_response=raw,
        )
