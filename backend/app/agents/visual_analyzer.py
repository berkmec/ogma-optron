"""VisualAnalyzerAgent: re-examines the observation through the lens of a task.

The vision pipeline already produced a generic VisualObservation. This agent
narrows in on what the current TaskNode actually cares about — e.g. for
extract_error_text, it focuses on the error message and stack frames; for
identify_screen, it focuses on the screen's purpose.

One Qwen3-VL call per invocation, text-only (no image re-upload).
"""

from __future__ import annotations

import time
from typing import ClassVar

from openai import OpenAI

from app.agents.base import AgentBase, AgentContext, AgentResult
from app.config import settings

SYSTEM_PROMPT = """You are a visual-task analyzer in a multi-agent runtime.

Given:
- a TaskNode (what to do)
- a VisualObservation (what was already extracted from the screenshot)

Produce a short, grounded analysis (3-6 sentences) that DIRECTLY satisfies
the task. Quote OCR text or the vision description verbatim where useful.
Do NOT invent files, error codes, or UI elements that are not present.

Output plain prose. No markdown headings. No preamble.
"""


def _user_message(context: AgentContext) -> str:
    return (
        f"Task: {context.task_node.task_type}\n"
        f"Task description: {context.task_node.description}\n"
        f"User intent: {context.intent.primary_intent.value} "
        f"(confidence {context.intent.confidence:.2f})\n"
        f"User prompt: {context.user_prompt or '(none)'}\n\n"
        f"Observation:\n"
        f"  image_type: {context.observation.image_type.value}\n"
        f"  vision_description: {context.observation.vision_description}\n\n"
        f"OCR text (truncated to 2500 chars):\n{context.observation.ocr_text[:2500]}"
    )


class VisualAnalyzerAgent(AgentBase):
    name: ClassVar[str] = "VisualAnalyzerAgent"

    def __init__(self) -> None:
        if not settings.hf_token:
            raise RuntimeError("HF_TOKEN is empty")
        self._client = OpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.hf_token,
        )
        self._model = settings.vision_model

    def run(self, context: AgentContext) -> AgentResult:
        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=400,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_message(context)},
            ],
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        text = (response.choices[0].message.content or "").strip()
        return AgentResult(
            output_summary=text,
            detail_markdown=text,
            model_used=self._model,
            latency_ms=elapsed_ms,
        )
