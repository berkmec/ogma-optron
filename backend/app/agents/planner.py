"""PlannerAgent: turns upstream findings into concrete next steps or causes.

Owns task types like classify_error_cause, suggest_debug_steps,
list_review_concerns, list_visible_actions, guide_steps, request_clarification.

Consumes upstream_results (other agents' output_summary values) and produces
a focused plan slice.
"""

from __future__ import annotations

import time
from typing import ClassVar

from openai import OpenAI

from app.agents.base import AgentBase, AgentContext, AgentResult
from app.config import settings

SYSTEM_PROMPT = """You are a planner agent in a multi-agent runtime.

Given a TaskNode plus upstream agent outputs, you write a SHORT focused
response that satisfies just this task. Stay grounded in the upstream
findings; do not invent details.

Output as plain prose or a numbered list, no markdown headings, no preamble.
"""


def _format_upstream(context: AgentContext) -> str:
    if not context.upstream_results:
        return "  (no upstream results)"
    lines = []
    for task_id, summary in context.upstream_results.items():
        node = next((n for n in context.graph.nodes if n.task_id == task_id), None)
        label = node.task_type if node else task_id[:8]
        lines.append(f"  [{label}]\n    {summary.strip()}")
    return "\n".join(lines)


def _user_message(context: AgentContext) -> str:
    return (
        f"Task: {context.task_node.task_type}\n"
        f"Task description: {context.task_node.description}\n"
        f"User intent: {context.intent.primary_intent.value}\n"
        f"User prompt: {context.user_prompt or '(none)'}\n\n"
        f"Upstream findings:\n{_format_upstream(context)}\n\n"
        f"Now produce the response for this task only."
    )


class PlannerAgent(AgentBase):
    name: ClassVar[str] = "PlannerAgent"

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
            max_tokens=500,
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
