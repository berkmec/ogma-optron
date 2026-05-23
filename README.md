# ogma-optron

> A visual task understanding and agent routing runtime. Turns screenshots into structured task graphs, dispatches them through a small fleet of agents, and optionally engages a read-only code agent (claw / `agent.exe`) for repository-aware reasoning.

**Status:** Weeks 1-7 complete. Pipeline is end-to-end, persisted to SQLite, and covered by 50 unit tests + an eval driver. Week 8 is documentation and polish.

[![CI](https://img.shields.io/badge/ci-pytest%20%2B%20ruff%20%2B%20tsc-blue)](.github/workflows/test.yml)
[![tests](https://img.shields.io/badge/tests-50%2F50-brightgreen)](backend/tests)
[![eval](https://img.shields.io/badge/eval-9%2F10%20image__type%20%2F%209%2F10%20intent-brightgreen)](benchmarks/)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## What this is

ogma-optron takes a screenshot (an error screen, a GitHub page, a UI, a code editor, a document) and walks it through a fixed sequence:

```
upload  →  Qwen3-VL + RapidOCR  →  intent classifier  →  task graph (per intent)  →
sequential executor over 4 agents  →  markdown report  →  follow-up chat
```

When the intent is `repo_review` and the user supplies a workspace path, the `CodeAgent` step spawns the upstream `agent.exe` (claw) binary in a strict read-only profile and feeds it a pre-scanned snapshot of the workspace.

## What this is *not*

- Not a foundation vision model. No weights are shipped or trained here.
- Not a website auditor or browser automation tool. Optron does not click, type, or drive a browser.
- Not affiliated with the OGMA core. The `ogma-` prefix is a personal brand only.

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI + SQLite (`sessions.db`) |
| Frontend | Vite + React + TypeScript |
| Vision model | `Qwen/Qwen3-VL-30B-A3B-Instruct` via [HF Inference Providers](https://huggingface.co/docs/inference-providers) |
| OCR | RapidOCR (ONNX, CPU) |
| Code agent | `agent.exe` (upstream `agent-code` crate, the `claw` binary) in `--permission-mode deny` |
| Markdown | `react-markdown` + `remark-gfm` |
| Tests | pytest + ruff (lint) + tsc (type check) |
| CI | GitHub Actions |

## End-to-end shape

```
            ┌─────────────────────────────────────────────────────────────┐
            │  POST /api/assets/upload                                    │
client ──►  │  POST /api/vision/analyze    →  VisualObservation          │
            │  POST /api/intent/classify   →  IntentResult                │
            │  POST /api/task-graph/build  →  TaskGraph (4 fixed nodes)   │
            │  POST /api/agents/run        →  AgentRun (4 traces)         │
            │  POST /api/chat              →  follow-up turn              │
            │  GET  /api/sessions          →  recent runs                 │
            └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                  ┌─────────────────────┐
                  │  AgentManager       │
                  │   VisualAnalyzer    │
                  │   Planner           │
                  │   Report            │
                  │   Code  (ClawBridge → agent.exe, read-only)
                  └─────────────────────┘
```

Detailed architecture: [`docs/architecture.md`](docs/architecture.md). Safety model for the code agent: [`docs/clawbridge.md`](docs/clawbridge.md). Security model overall: [`docs/security.md`](docs/security.md).

## Benchmarks (synthetic eval)

10 PIL-drawn screenshots across the 5 image types in [`scripts/eval_cases.py`](scripts/eval_cases.py). Baseline run on Qwen3-VL-30B-A3B-Instruct:

| metric | value |
|---|---|
| image_type accuracy | **9 / 10 (90 %)** |
| intent accuracy | **9 / 10 (90 %)** |
| analyze p50 / p95 | 3.6 s / 5.4 s |
| intent p50 / p95 | 1.8 s / 5.3 s |
| wall (10 cases) | 63.9 s |

Two `PARTIAL` cases (`ui_login` and `code_python`) are honest label edge cases, not bugs — see [`benchmarks/eval_2026-05-23.md`](benchmarks/eval_2026-05-23.md).

Synthetic accuracy is a smoke gate, not a benchmark for real screenshots. Real-world numbers will be lower; chart / diagram screenshots in particular currently degrade to `other` with a warning (which is the honest behavior).

## Setup

### 1. Backend

```powershell
# Python 3.11+
python -m venv .venv
.\.venv\Scripts\activate

pip install -r backend\requirements.txt
# Or for development (adds pytest + ruff):
pip install -r backend\requirements-dev.txt

# Configure secrets
cp .env.example .env
# Edit .env: set HF_TOKEN to a HuggingFace fine-grained token with
# "Make calls to Inference Providers" permission.

cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Code agent (claw / `agent.exe`)

```powershell
# Install Rust toolchain via rustup if you don't have it
# https://rustup.rs/
cargo install agent-code

# Result: %USERPROFILE%\.cargo\bin\agent.exe
# Set AGENT_CODE_BIN in .env to this path.
```

The wrapper passes `--permission-mode deny` and pre-scans the workspace in Python; see [`docs/clawbridge.md`](docs/clawbridge.md).

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173
```

### 4. Smoke

```powershell
# Sanity probe Qwen3-VL on HF router
python scripts\sanity_qwen_vl.py

# End-to-end (week 5: includes CodeAgent if workspace_path is provided)
python scripts\e2e_week5.py

# Live eval
python scripts\run_eval.py
```

### 5. Tests

```powershell
cd backend
pytest tests/ -v
ruff check app tests --select=E,F,B --ignore=E501
```

## API surface

| Method | Path | Returns |
|---|---|---|
| GET | `/health`, `/api/health` | service status |
| POST | `/api/assets/upload` | `VisualAsset` |
| GET | `/api/assets/{id}` | `VisualAsset` |
| POST | `/api/vision/analyze` | `VisualObservation` |
| GET | `/api/vision/observations/{id}` | `VisualObservation` |
| POST | `/api/intent/classify` | `IntentResult` |
| GET | `/api/intent/{id}` | `IntentResult` |
| POST | `/api/task-graph/build` | `TaskGraph` |
| GET | `/api/task-graph/{id}` | `TaskGraph` |
| POST | `/api/reports/generate` | `Report` (legacy single-shot) |
| GET | `/api/reports/{id}` | `Report` |
| POST | `/api/agents/run` | `AgentRun` |
| GET | `/api/agents/runs/{id}` | `AgentRun` |
| POST | `/api/clawbridge/review` | `ClawRun` (direct) |
| GET | `/api/clawbridge/runs/{id}` | `ClawRun` |
| POST | `/api/chat` | `ChatTurnResponse` |
| GET | `/api/chat/{observation_id}` | `list[ChatMessage]` |
| GET | `/api/sessions` | `list[SessionSummary]` |
| GET | `/api/sessions/{asset_id}` | `SessionSummary` |

Swagger UI: <http://127.0.0.1:8000/docs>.

## Roadmap

Done (this 8-week build):
- W1: skeleton (FastAPI + Vite + Rust + agent.exe sanity)
- W2: vision pipeline (upload + RapidOCR + Qwen-VL → observation)
- W3: intent + task graph + report
- W4: agent runtime (4 agents, sequential executor)
- W5: ClawBridge (read-only `agent.exe` subprocess)
- W6: chat-over-observation + recent sessions list
- W7: eval set + benchmark + 50 pytests + GitHub Actions CI

In progress (W8):
- Docs (architecture, clawbridge, security, providers, roadmap)
- Docker Compose
- Demo screenshots / GIF

Not in scope of this MVP, see [`docs/roadmap.md`](docs/roadmap.md):
- Mouse/keyboard or browser automation (`scope-decisions` memory documents the why — separate project).
- Foundation vision model training.
- Production-grade auth / multi-tenant SaaS.

## Limitations (honest)

- **Provider availability is fluid.** HF router routes to whichever provider currently serves a model serverless. Models can flip to non-serverless overnight (this happened mid-build for `Qwen/Qwen3-VL-8B-Instruct` → switched to `30B-A3B` in commit `83fceaf`).
- **Synthetic eval ≠ real screenshots.** Real captures will hit OCR edge cases, font rendering issues, and ambiguous layouts. Expect lower accuracy.
- **CodeAgent is read-only by design.** It cannot edit your repo. For a richer review, run `agent.exe` separately in your shell.
- **Sequential executor.** Parallel branches are safe but not exploited yet.
- **No auth.** Localhost only; do not expose the backend to the network.
- **No tests for HF / agent.exe paths.** The full pipeline depends on live services; only offline pure code is unit-tested. The eval driver fills that gap by exercising the live system on a synthetic set.

## License

MIT. See [`LICENSE`](LICENSE).

The vendored sources under `oveQ.-main/` (the parent directory of this repo during development) are not redistributed here; ogma-optron does not contain copied code from MiroFish, quantum_agentic_engine, or claw-code. The `agent.exe` binary is installed from the upstream `agent-code` crate via `cargo install agent-code` and runs as an external subprocess.
