"""LLM-as-classifier intent decision over a VisualObservation and user prompt.

The classifier is intentionally a thin wrapper: send observation + prompt to
Qwen3-VL with a strict JSON output contract, parse, and normalize. No
rule-based fallback — if the model fails to produce valid JSON we surface that
as IntentKind.UNKNOWN with the failure noted in `ambiguity`.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import OpenAI

from app.config import settings
from app.schemas.intent import IntentKind
from app.schemas.observation import VisualObservation

CLASSIFY_SYSTEM_PROMPT = """You classify a user's PRIMARY intent in a visual task runtime.

You receive:
- a VisualObservation (image_type, vision_description, OCR text)
- a user prompt (may be empty)

Pick ONE intent:
  error_debug : user wants to understand or fix an error / exception / failure
  repo_review : user wants a review or summary of a code repository
  ui_help     : user wants help navigating or understanding a UI screen
  unknown     : none of the above clearly applies

Respond with VALID JSON only (no markdown fences, no prose):

{
  "primary_intent": "error_debug" | "repo_review" | "ui_help" | "unknown",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<1-2 sentence rationale>",
  "ambiguity": ["<conflicting signals, optional>"],
  "suggested_next_step": "<one short sentence>"
}

If the user prompt and the visual evidence conflict, list both signals in
"ambiguity" rather than silently picking one.
"""

_JSON_RE = re.compile(r"\{[\s\S]*\}")
_ALLOWED = {e.value for e in IntentKind}


def _parse(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    match = _JSON_RE.search(stripped)
    if not match:
        return {
            "primary_intent": "unknown",
            "confidence": 0.0,
            "reasoning": text[:300],
            "ambiguity": ["model did not return JSON"],
        }
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return {
            "primary_intent": "unknown",
            "confidence": 0.0,
            "reasoning": text[:300],
            "ambiguity": [f"JSON parse failed: {exc}"],
        }


def _normalize(value: str) -> IntentKind:
    norm = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return IntentKind(norm) if norm in _ALLOWED else IntentKind.UNKNOWN


class IntentClassifier:
    def __init__(self) -> None:
        if not settings.hf_token:
            raise RuntimeError(
                "HF_TOKEN is empty; configure .env before calling the classifier."
            )
        self._client = OpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.hf_token,
        )
        self._model = settings.vision_model

    def classify(
        self, observation: VisualObservation, user_prompt: str = ""
    ) -> dict[str, Any]:
        context = (
            f"image_type: {observation.image_type.value}\n"
            f"vision_description: {observation.vision_description}\n"
            f"ocr_text:\n{observation.ocr_text[:2000]}\n\n"
            f"user_prompt: {user_prompt or '(none)'}"
        )
        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=256,
            messages=[
                {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raw = response.choices[0].message.content or ""
        parsed = _parse(raw)

        try:
            confidence = float(parsed.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        return {
            "primary_intent": _normalize(str(parsed.get("primary_intent", ""))),
            "confidence": confidence,
            "reasoning": str(parsed.get("reasoning") or "").strip(),
            "ambiguity": [str(a) for a in (parsed.get("ambiguity") or [])],
            "suggested_next_step": str(parsed.get("suggested_next_step") or "").strip(),
            "model_used": self._model,
            "latency_ms": elapsed_ms,
        }
