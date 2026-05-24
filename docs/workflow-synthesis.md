# Multi-screenshot workflow synthesis

Single-screenshot review is fine for "explain this error". Real bug reports, real onboarding flows, real QA repros come as **a sequence** of screens. M1.4 lets you feed an ordered list of observations and get back one synthesised markdown block instead of N disconnected reports.

## Shape

```text
WorkflowSession
  session_id, title, user_prompt
  observation_ids   [ "obs-uuid-1", "obs-uuid-2", ... ]
  synthesis_markdown                ← Qwen output
  model_used, latency_ms, created_at
```

The image bytes are **not** re-sent to the model — we feed the already-extracted `image_type / vision_description / OCR text` per observation. Cost is linear in N screens.

## Synthesis output structure (enforced by system prompt)

```text
## What this flow is
1-2 sentences.

## What happened, step by step
1. screen 1 ...
2. screen 2 ...
3. screen 3 ...

## Where it broke or what's missing
evidence-grounded.

## Recommended next step
one concrete action.
```

If the model invents a screen not in the input, that's a regression — file an issue with the failing observation_ids.

## CLI

```bash
optron workflow login.png error.png retry.png -p "User can't log in"
```

Backend will:
1. analyse each image (full pipeline up to and including `vision/analyze`),
2. collect the observation_ids in order,
3. call `synthesise_workflow()`,
4. persist the resulting `WorkflowSession` to `sessions.db`,
5. print the markdown synthesis.

`--json` available. `-t/--title` lets you tag the session (useful when listing later).

## API

```text
POST  /api/workflows                 { observation_ids: [...], title?, user_prompt?, synthesise? } -> WorkflowSession
POST  /api/workflows/{id}/synthesise { user_prompt? }                                              -> WorkflowSession  (re-runs synthesis on the same observations)
GET   /api/workflows                                                                                -> WorkflowSession[]
GET   /api/workflows/{id}                                                                           -> WorkflowSession
```

If `synthesise=false` on create, we just persist the observation chain and you can re-synthesise later with different prompts.

## Bounds

| | value |
|---|---|
| OCR text per observation | truncated to 1200 chars |
| max model tokens | 900 |
| list limit (GET /api/workflows) | 30 (configurable up to 100) |
