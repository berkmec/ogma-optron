# Roadmap

## Done (weeks 1-8 + UI integration)

The 8-week MVP build is committed (`3d44bbf` → `fa93f28` + the React 19 / Tailwind v4 minimalist UI upgrade). See the README's *Roadmap* section for the per-week commit map.

Headline numbers from the synthetic eval baseline:

- image_type accuracy: **9 / 10 (90 %)**
- intent accuracy: **9 / 10 (90 %)**
- 50 / 50 pytests green, ~1.6 s
- 19 endpoints across 9 routers, 7 SQLite tables, 4 agents (one of them the real subprocess CodeAgent)

That made an "AI sees your screenshot and writes a report" tool. The honest gap: **most of what's there a generic ChatGPT-vision call also does.** The next four milestones build the differentiation.

## Active plan — 4 milestones, ~16 weeks total

> Each milestone ends in a demo-able, commit-able state. Total ~4 months solo dev. The framing is **dev-tool first, browser-automation as an optional agent.**

### M1 · Dev-tool core expansion — 5 weeks

Make the differentiation we already have (ClawBridge / repo-aware review) actually usable.

| # | Work | Time | Deliverable |
|---|---|---|---|
| M1.1 | **CLI** (`optron analyze / review / chat / eval`) | 5 d | Terminal-driven full pipeline + `--workspace` flag |
| M1.2 | **Repo intelligence index** (sentence-transformers + FAISS) | 3 wk | `optron index ./repo` → semantic chunk selection during every review, instead of feeding 200 files blind |
| M1.3 | **Git-aware code review** | 1 wk | `optron review --branch feature/x` consumes screenshot + diff + index, returns a grounded markdown PR review |
| M1.4 | **Multi-screenshot session synthesis** | 0.5 wk | 3-5 screenshots → workflow-level summary |
| M1.5 | **Agent replay / debugger** | 1 wk | Every trace's raw prompt + raw model response visible; "re-run from step N" with prompt edits |

**M1 acceptance:** On a real Python repo, CLI runs review → semantic search picks 10 relevant files → git diff included → markdown comes back. Agent replay UI lets you edit a prompt mid-graph and re-run from that node.

### M2 · Vision expansion — 4 weeks

Move from "describe + classify" to a real visual layer. This is the "comprehensive vision" answer the user asked for — **adopting** mature VL models, not training a new one.

| # | Work | Time | Deliverable |
|---|---|---|---|
| M2.1 | **Layout-aware OCR** (Surya or PaddleOCR layout mode) | 1 wk | Bounding boxes + reading order in `VisualObservation` |
| M2.2 | **Object / UI element detection** (OWL-ViT or YOLO-World) | 1 wk | Buttons, inputs, icons with bboxes + labels |
| M2.3 | **LLM-driven scene graph** (Qwen prompt, not rule-based) | 0.5 wk | Entity / relation list |
| M2.4 | **Video frame analysis** | 1 wk | mp4 / gif uploads; ffmpeg samples key frames; per-frame analyze + cross-frame summary |
| M2.5 | **Screen-grounding provider** (UI-TARS-7B-DPO or special-prompted Qwen2.5-VL-72B) | 0.5 wk | A VL model that returns coordinates, not just descriptions. Pre-requisite for M3. |

**M2 acceptance:** Single screenshot now produces layout + objects + scene graph; a short screen-recording produces a frame-by-frame story.

### M3 · Computer use, L2 (sandboxed) — 5 weeks

A `BrowserAgent` that drives a **headless Chromium sandbox**, never the user's real Chrome. This is the "klavye / mouse / sekmelerde gezinti" answer — but scoped to L2 (browser only, isolated) for both safety and feasibility.

| # | Work | Time | Deliverable |
|---|---|---|---|
| M3.1 | **Playwright + headless Chromium sandbox** | 1 wk | Fresh profile per run, no host cookies / passwords reachable |
| M3.2 | **BrowserAgent class + action taxonomy** (navigate, click, type, scroll, screenshot, wait, extract_text) | 1 wk | Each action separately testable |
| M3.3 | **Iteration loop**: screenshot → screen-ground (M2.5) → next action → repeat | 2 wk | Loop limit, timeout, success heuristic |
| M3.4 | **Safety**: domain whitelist, max-action cap, full action log, optional confirm-before-action mode | 0.5 wk | Visible guard rails |
| M3.5 | **Frontend live preview**: browser screenshot stream + action log | 0.5 wk | The user sees what Optron is doing in real time |

**M3 acceptance:** Goal "Open github.com, find the ogma-optron repo, summarize its latest commit" completes successfully in an isolated Chromium, with the user watching the live preview, and no host browser is touched.

### M4 · Reasoning toggle + closing — 2 weeks

The deepthink mode + everything that polishes the project for portfolio.

| # | Work | Time | Deliverable |
|---|---|---|---|
| M4.1 | **Deepthink toggle**: UI switch + backend `reasoning_model` config | 0.5 wk | Toggle on → `Qwen/Qwen3-VL-235B-A22B-Thinking` or `openai/gpt-oss-120b` |
| M4.2 | **Plan-and-critic loop** (deepthink only): draft → CriticAgent → revise | 0.5 wk | Quality up, latency ~2× |
| M4.3 | **100+ case real-screenshot eval set** | 0.5 wk | Replaces the 10-case synthetic baseline as the headline benchmark |
| M4.4 | **Demo video + blog post draft + README final** | 0.5 wk | Portfolio-ready content |

## Cost reality check

| Model | Role | Approx $/1M tokens (HF router) | Tokens / demo | $/demo |
|---|---|---|---|---|
| `Qwen/Qwen3-VL-30B-A3B-Instruct` | default vision + 4 agents | ~$0.15 | ~6K | **$0.0009** |
| `Qwen/Qwen3-Coder-30B-A3B-Instruct` | CodeAgent / review | ~$0.10 | ~8K | $0.0008 |
| `Qwen/Qwen3-VL-235B-A22B-Thinking` | deepthink toggle | ~$0.40 | ~10K | $0.0040 |
| `openai/gpt-oss-120b` | deepthink alt | ~$0.20 | ~8K | $0.0016 |
| `bytedance/UI-TARS-7B-DPO` | screen grounding (M2.5 / M3) | not on HF router → Replicate ~$0.30 / s | per browser step ~1 frame | ~$0.05 / step |

Typical month: 100 demo runs in default mode = **~$0.10-0.50**. Heavy deepthink + browser sessions = **~$5-15**. Token cost is genuinely not the constraint.

## Out of scope (separate projects)

- **Training our own foundation vision model.** Reaffirmed during this planning round (option A). 6-12 months + GPU cluster + $50K+ + a labeled dataset. Out of scope; if ever pursued it would be a separate repo, not this one.
- **L3 computer use** (real desktop mouse / keyboard via pyautogui). Considered, rejected for security reasons. The L2 sandboxed-Chromium answer covers the "klavye / mouse" need without giving an LLM access to the user's actual screen.
- **Browser extension for the host Chrome.** Out of scope; we'd hand the agent the user's cookies, defeating the safety argument.
- **Multi-tenant SaaS deployment.** No auth, no quota, no observability stack. Self-hosted only.

## Known issues / debts inherited from M0-M8

- HF router provider availability is fluid — already saw `Qwen3-VL-8B` flip non-serverless mid-build. M2.5 may have to add a fallback if `UI-TARS` ever leaves Replicate's pricing tier.
- Synthetic eval is a smoke gate, not a benchmark. M4.3 replaces it with a real-screenshot set.
- Frontend has one App component; once M1.5 (agent replay) lands it will need a real router. Don't add routing earlier — that work piggybacks on M1.5.
