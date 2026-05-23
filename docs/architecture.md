# Architecture

ogma-optron is a thin, sequential pipeline. Each step is a small layer with a single concern.

## Layers (top down)

```
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend (Vite + React + TS)                                        │
│    Upload form · pipeline progress · intent badge · task graph view  │
│    Agent trace list · markdown report · follow-up chat · sessions    │
└──────────────────────────────────────────────────────────────────────┘
                                  │  HTTP (Vite proxies /api → :8000)
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FastAPI routers (backend/app/api)                                   │
│   upload · analyze · intent · task_graph · reports · agents · chat   │
│   clawbridge · sessions                                              │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                ┌─────────────────┴────────────────────┐
                ▼                                      ▼
┌────────────────────────────────┐    ┌──────────────────────────────────┐
│ Vision + intent + report path  │    │  Storage + reads                 │
│  vision/ocr (RapidOCR)         │    │   services/file_store (uploads/) │
│  providers/hf_qwen_vl          │    │   services/sqlite_store          │
│  intent/classifier             │    │     (assets, observations,       │
│  runtime/task_graph_templates  │    │      intents, task_graphs,       │
│  agents/{base, manager,        │    │      reports, agent_runs,        │
│         visual_analyzer,       │    │      claw_runs, chat_messages)   │
│         planner, report_agent} │    │                                  │
│  services/chat_service         │    │                                  │
└────────────────────────────────┘    └──────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  ClawBridge (backend/app/clawbridge)                                 │
│    workspace_scanner (Python-side read-only walk)                    │
│    wrapper (subprocess agent.exe --permission-mode deny)             │
│    run_store (runs/claw/{run_id}/ artifacts)                         │
└──────────────────────────────────────────────────────────────────────┘
                │
                ▼  subprocess
┌──────────────────────────────────────────────────────────────────────┐
│  agent.exe (upstream `agent-code` crate, the claw binary)            │
│    Connects out to HF Inference Providers (router) using             │
│    AGENT_CODE_API_BASE_URL / AGENT_CODE_API_KEY / AGENT_CODE_MODEL   │
└──────────────────────────────────────────────────────────────────────┘
```

## Data flow for a single pipeline run

```
Image bytes
   │
   ▼
POST /api/assets/upload                ── file_store.save_upload
   │   asset_id, width, height
   ▼
POST /api/vision/analyze               ── RapidOCR + Qwen3-VL
   │   observation { image_type, ocr_text, vision_description }
   ▼
POST /api/intent/classify              ── Qwen-as-JSON-classifier
   │   intent { primary_intent, confidence, reasoning, suggested_next_step }
   ▼
POST /api/task-graph/build             ── fixed template per intent
   │   graph { 4 nodes, depends_on edges }
   ▼
POST /api/agents/run                   ── executor.execute
   │   AgentRun { traces[] }
   │
   │   for each node in topological order:
   │     ctx = AgentContext(node, observation, intent, graph,
   │                        upstream_results, user_prompt, workspace_path)
   │     result = manager.get(node.required_agent).run(ctx)
   │     trace = AgentTrace(...)
   │
   │   draft_report is the final node, owned by ReportAgent
   ▼
(optional) POST /api/chat              ── ChatService over observation+report+history
```

## Why this shape

- **Sequential, not parallel.** Parallel branches are safe (no shared state, no side effects beyond the LLM calls), but the API surface, trace ordering, and debugging stay simpler when serial. The executor's topological sort already handles the dep graph; flipping to a worker pool is mechanical when needed.
- **One model for everything.** `Qwen/Qwen3-VL-30B-A3B-Instruct` does vision, intent classification, planning, report, and follow-up chat. Easier to demo and bill; no separate coder model. See [`docs/providers.md`](providers.md).
- **JSON blobs in SQLite.** Each table stores the Pydantic model as JSON. Migrations are cheap during week-to-week churn; schemas can evolve without ALTER TABLE.
- **Agent.exe via Python wrapper.** Read-only contract is enforced *outside* the subprocess — `--permission-mode deny` blocks tool calls; the workspace context is injected from a Python-side scan. See [`docs/clawbridge.md`](clawbridge.md).

## File layout (truncated)

```
backend/
  app/
    api/        FastAPI routers (one module per resource)
    agents/     base + 4 agent implementations + manager
    clawbridge/ wrapper, workspace_scanner, run_store
    intent/     classifier
    providers/  base + hf_qwen_vl
    runtime/    executor, task_graph_templates
    schemas/    pydantic models
    services/   file_store, sqlite_store, chat_service
    vision/     ocr
  tests/        pytest (50 tests, offline)
  requirements.txt / requirements-dev.txt
frontend/       Vite + React + TS
scripts/        sanity probes, e2e drivers, eval driver, eval cases
benchmarks/     dated JSON + MD eval reports
.github/workflows/test.yml
```
