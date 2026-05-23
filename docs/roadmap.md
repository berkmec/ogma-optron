# Roadmap

## Done (weeks 1-7)

See the README's *Roadmap* section for the per-week commit map.

## Week 8 (current)

- Documentation pass (this folder).
- Docker Compose for backend + frontend.
- Demo screenshots / GIF (manual capture).

## Near-term, post-MVP

These are things the code is already shaped to absorb, but they were intentionally left out to keep the 2-month build honest.

- **Real-screenshot eval set.** The current eval is 10 PIL-drawn cases. Real screenshots (with anti-aliased fonts, system UI chrome, dark mode, non-Latin text) will degrade accuracy and reveal OCR cliffs. Need a labeled set of ~50 captures.
- **Parallel executor branches.** The topological sort already returns level information; replacing the sequential dispatcher with an asyncio gather over each level is a half-day change.
- **Provider abstraction at the call site.** `backend/app/api/analyze.py` and `backend/app/intent/classifier.py` both hard-wire `HFQwenVLProvider`. A small `provider_registry` would let `VISION_PROVIDER=ollama` flip everything.
- **Frontend graph rendering.** Cytoscape or Mermaid for the task graph view — the JSON is already structured to drive it.
- **Session detail page.** `GET /api/sessions/{asset_id}` returns the full summary; the frontend currently only lists recent sessions, doesn't link to them.

## Out of scope, separate projects

- **Browser / mouse / keyboard automation.** Discussed in `scope-decisions` memory. Computer-Use-class problem; a 6-12 month build of its own. ogma-optron does *not* drive the user's Chrome or click on their screen by design.
- **Foundation vision model training.** No GPU budget, no model weights shipped, no claim to compete with GPT-4V / Claude vision / native Qwen-VL.
- **Production SaaS.** No multi-tenant auth, no quota system, no observability stack, no SOC2 anything.
- **Native Windows installer / packaged release.** `cargo install`, `pip install`, `npm install` is the supported path.

## Known issues

- HF router provider availability can flip; see `docs/providers.md` for the recovery procedure.
- Chart / diagram screenshots currently classify as `other` with a warning (which is the honest behavior, not a bug). Future versions could add `chart_or_diagram` to `ImageType` if there is real demand.
- The CodeAgent prompt currently lists files but reads only "important" ones (README, manifests, …). A repo with mostly source files and no manifests gets a thin review.
