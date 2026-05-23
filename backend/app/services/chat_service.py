"""Chat-over-observation: follow-up Q/A grounded in the observation + history.

A thin Qwen client that loads the observation, the most recent ReportAgent
trace if any, the prior chat turns, and answers a new user question.
"""

from __future__ import annotations

import time
import uuid

from openai import OpenAI

from app.config import settings
from app.schemas.chat import ChatMessage, ChatRole
from app.schemas.observation import VisualObservation
from app.schemas.report import Report

SYSTEM_PROMPT_TEMPLATE = """You are a follow-up Q/A assistant for a
visual-task agent runtime.

CONTEXT FOR THIS CONVERSATION (this is the ONLY ground truth — do not
substitute generic examples for it):

{context}

Rules:
- Quote the actual OCR text and the actual error/text from the context
  verbatim when relevant.
- Never substitute a different error message or a textbook example for
  the one in the context. If the context's error is "X", do not pivot to
  some other error like "Cannot read property of undefined".
- If the user asks something you cannot infer from the evidence above,
  say so briefly and ask what extra info would help.
- Output plain markdown. No preamble. No signoff.
"""


def _format_history(history: list[ChatMessage], limit: int = 12) -> list[dict]:
    recent = history[-limit:]
    return [
        {"role": msg.role.value, "content": msg.content}
        for msg in recent
    ]


def _build_context_block(
    observation: VisualObservation, report: Report | None
) -> str:
    block = (
        f"VisualObservation\n"
        f"  image_type: {observation.image_type.value}\n"
        f"  vision_description: {observation.vision_description}\n"
        f"  OCR text (truncated):\n{observation.ocr_text[:1800]}"
    )
    if report is not None:
        block += (
            f"\n\nReport ({report.title}, by {report.model_used}):\n"
            f"{report.markdown[:4000]}"
        )
    return block


class ChatService:
    def __init__(self) -> None:
        if not settings.hf_token:
            raise RuntimeError("HF_TOKEN is empty")
        self._client = OpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.hf_token,
        )
        self._model = settings.vision_model

    def reply(
        self,
        observation: VisualObservation,
        report: Report | None,
        history: list[ChatMessage],
        question: str,
    ) -> ChatMessage:
        context = _build_context_block(observation, report)
        system_msg = SYSTEM_PROMPT_TEMPLATE.format(context=context)
        messages: list[dict] = [
            {"role": "system", "content": system_msg},
            *_format_history(history),
            {"role": "user", "content": question},
        ]
        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=600,
            messages=messages,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        content = (response.choices[0].message.content or "").strip()
        return ChatMessage(
            message_id=str(uuid.uuid4()),
            observation_id=observation.observation_id,
            role=ChatRole.ASSISTANT,
            content=content,
            model_used=self._model,
            latency_ms=elapsed_ms,
        )
