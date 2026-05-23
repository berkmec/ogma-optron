# ogma-optron

> Visual task understanding and agent routing runtime. Turns screenshots, images, and visual documents into structured task graphs and routes them to specialized agents. Delegates to the `agent-code` (claw) CLI in read-only mode for repository-aware code analysis.

**Status:** Week 2 — visual pipeline working end-to-end. Upload a screenshot → OCR + Qwen3-VL classification → VisualObservation in ~4-5s. Frontend can drive the flow.

## What this is

ogma-optron takes a screenshot or image, extracts visual intent (error screen, repo view, UI dashboard, etc.), builds a small task graph, and routes the work to agents:

- Vision + OCR analysis via Qwen/Qwen3-VL-30B-A3B-Instruct on HuggingFace.
- Code/repo understanding via `agent-code` (the `claw` CLI) running in safe read-only mode.
- A short markdown action plan or report as the final output.

## What this is not

- Not a foundation vision model. No model weights are shipped or trained here.
- Not a website audit tool.
- Not a browser automation tool.
- Not affiliated with or dependent on the OGMA core. The `ogma-` prefix is a personal brand only.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + SQLite |
| Frontend | Vite + React |
| Vision model | `Qwen/Qwen3-VL-30B-A3B-Instruct` via [HF Inference Providers](https://huggingface.co/docs/inference-providers) |
| Code agent | `agent-code` CLI (the upstream binary for `claw-code`) in read-only mode |
| OCR | RapidOCR (CPU, planned for week 2) |

## Setup (work in progress)

1. Copy `.env.example` to `.env` and add your `HF_TOKEN`.
2. Install Rust (`rustup`) and the agent binary: `cargo install agent-code`.
3. Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`.
4. Frontend: `cd frontend && npm install && npm run dev`.

## Roadmap

- Week 1: skeleton, sanity tests for Qwen and `agent.exe`.
- Week 2: upload pipeline + Qwen-VL observation.
- Week 3: 3 intents (`error_debug`, `repo_review`, `ui_help`) + report agent.
- Week 4: agent runtime with 3 agents.
- Week 5: ClawBridge wrapper (read-only).
- Week 6: frontend complete + chat over observation.
- Week 7: eval set + benchmark + tests.
- Week 8: demo, README polish, docs.

## License

MIT
