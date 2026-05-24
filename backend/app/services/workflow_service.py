"""Multi-screenshot workflow synthesis.

Takes a list of VisualObservation rows that belong to the same user flow
and produces a single markdown summary of:
  - what the flow appears to be,
  - what happened across the screens in order,
  - where it broke or what's missing,
  - the recommended next step.

We deliberately do NOT re-send the images; we feed the already-extracted
observation text + OCR. That keeps token cost roughly linear in N
screens, not quadratic.
"""

from __future__ import annotations

import time

from openai import OpenAI

from app.config import settings
from app.schemas.observation import VisualObservation

SYSTEM_PROMPT = """You are a workflow summariser inside a visual-task
agent runtime. You receive an ordered list of VisualObservation records
(each one already extracted from a separate screenshot: image_type,
vision_description, OCR text). They all belong to the same user flow.

Produce a SHORT markdown synthesis with this exact structure:

## What this flow is
1-2 sentences naming the flow.

## What happened, step by step
A numbered list, one item per screenshot, in the order given.

## Where it broke or what's missing
What evidence in the observations supports it.

## Recommended next step
One concrete action.

Rules:
- Quote OCR text verbatim only when it directly supports a claim.
- Do not invent screens beyond the observations given.
- No preamble, no signoff.
"""

OCR_TRUNC_CHARS = 1200


def _format_observation(idx: int, obs: VisualObservation) -> str:
    return (
        f"### Step {idx + 1} (observation {obs.observation_id[:8]})\n"
        f"image_type: {obs.image_type.value}\n"
        f"vision_description: {obs.vision_description}\n"
        f"OCR text (truncated):\n{obs.ocr_text[:OCR_TRUNC_CHARS]}\n"
    )


def synthesise_workflow(
    observations: list[VisualObservation],
    user_prompt: str = "",
) -> dict:
    """Call Qwen once on the ordered observations and return the synthesis."""
    if not observations:
        return {"markdown": "", "model_used": settings.vision_model, "latency_ms": 0}

    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN is empty; configure .env before calling workflow_service.")

    client = OpenAI(base_url=settings.openai_base_url, api_key=settings.hf_token)
    user_block_parts = [
        f"User prompt: {user_prompt or '(none)'}",
        f"Number of screens: {len(observations)}",
        "",
        *(_format_observation(i, obs) for i, obs in enumerate(observations)),
    ]
    user_message = "\n".join(user_block_parts)

    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=settings.vision_model,
        max_tokens=900,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    markdown = (response.choices[0].message.content or "").strip()
    return {
        "markdown": markdown,
        "model_used": settings.vision_model,
        "latency_ms": elapsed_ms,
    }
