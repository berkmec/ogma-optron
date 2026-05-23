"""ReportAgent: one Qwen call that drafts a markdown report.

Given the observation, intent, and task graph, produce a short markdown
report tailored to the intent. The report is human-facing; it never tool-
calls. Week 4 will expand this with sibling agents.
"""

from __future__ import annotations

import time
from typing import Any

from openai import OpenAI

from app.config import settings
from app.schemas.intent import IntentKind, IntentResult
from app.schemas.observation import VisualObservation
from app.schemas.task_graph import TaskGraph

_INTENT_TITLES: dict[IntentKind, str] = {
    IntentKind.ERROR_DEBUG: "Debug Report",
    IntentKind.REPO_REVIEW: "Repository Review",
    IntentKind.UI_HELP: "UI Walkthrough",
    IntentKind.UNKNOWN: "Observation Notes",
}

_INTENT_GUIDES: dict[IntentKind, str] = {
    IntentKind.ERROR_DEBUG: (
        "Structure: ## Summary, ## Suspected cause, ## Suggested next steps "
        "(numbered, concrete), ## What we don't know yet. Quote the actual "
        "error text verbatim where useful."
    ),
    IntentKind.REPO_REVIEW: (
        "Structure: ## What this repo appears to be, ## Notable observations, "
        "## Concerns or open questions, ## Suggested follow-ups. Stay grounded "
        "in what is visible; do not invent files or APIs."
    ),
    IntentKind.UI_HELP: (
        "Structure: ## What this screen is, ## Visible actions, "
        "## Recommended next step. Use plain language; assume the user is not "
        "a developer of this UI."
    ),
    IntentKind.UNKNOWN: (
        "Structure: ## What we saw, ## Why the intent is unclear, "
        "## Clarifying question. Keep it short."
    ),
}

REPORT_SYSTEM_PROMPT = """You are a writing assistant inside a visual-task
agent runtime. Given a structured analysis of a screenshot and the user's
intent, you produce a SHORT, GROUNDED markdown report.

Rules:
- Use the heading structure given in the user message.
- Quote OCR text verbatim only when it directly supports a claim.
- Never invent file names, error codes, line numbers, or stack frames that
  are not present in the input.
- If the evidence is thin, say so in the relevant section.
- No preamble, no signoff. Just the markdown body.
"""


def _format_task_graph(graph: TaskGraph) -> str:
    lines = []
    for node in graph.nodes:
        deps = (
            " (depends on " + ", ".join(n[:8] for n in node.depends_on) + ")"
            if node.depends_on
            else ""
        )
        lines.append(
            f"- [{node.task_type}] {node.description} → {node.required_agent}{deps}"
        )
    return "\n".join(lines)


def _build_user_message(
    observation: VisualObservation,
    intent: IntentResult,
    graph: TaskGraph,
) -> str:
    guide = _INTENT_GUIDES.get(intent.primary_intent, _INTENT_GUIDES[IntentKind.UNKNOWN])
    return (
        f"Intent: {intent.primary_intent.value} "
        f"(confidence {intent.confidence:.2f})\n"
        f"User prompt: {intent.user_prompt or '(none)'}\n\n"
        f"Visual observation:\n"
        f"  image_type: {observation.image_type.value}\n"
        f"  description: {observation.vision_description}\n\n"
        f"OCR text:\n{observation.ocr_text[:2500]}\n\n"
        f"Planned tasks:\n{_format_task_graph(graph)}\n\n"
        f"Style guide for this intent:\n{guide}\n\n"
        f"Write the markdown report now."
    )


class ReportAgent:
    def __init__(self) -> None:
        if not settings.hf_token:
            raise RuntimeError(
                "HF_TOKEN is empty; configure .env before calling the ReportAgent."
            )
        self._client = OpenAI(
            base_url=settings.openai_base_url,
            api_key=settings.hf_token,
        )
        self._model = settings.vision_model

    def draft(
        self,
        observation: VisualObservation,
        intent: IntentResult,
        graph: TaskGraph,
    ) -> dict[str, Any]:
        user_message = _build_user_message(observation, intent, graph)
        start = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=900,
            messages=[
                {"role": "system", "content": REPORT_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        markdown = (response.choices[0].message.content or "").strip()
        title = _INTENT_TITLES.get(
            intent.primary_intent, _INTENT_TITLES[IntentKind.UNKNOWN]
        )
        return {
            "title": title,
            "markdown": markdown,
            "model_used": self._model,
            "latency_ms": elapsed_ms,
        }
