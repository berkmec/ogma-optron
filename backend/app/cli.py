"""optron CLI — full pipeline from the terminal.

Subcommands:
  health    Print resolved configuration.
  analyze   Upload an image + full pipeline (vision -> intent -> graph -> agents -> report).
  review    Read-only repo review via agent.exe (claw). No screenshot needed.
  chat      Follow-up question on an existing observation_id.
  eval      Run the synthetic eval suite (delegates to scripts/run_eval.py).

CLI is in-process: it calls the same handler functions the HTTP routers do,
so there is no need to start uvicorn separately. Each command initializes
the SQLite schema on first use.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.config import settings
from app.services import file_store, sqlite_store
from app.services.sqlite_store import init_db


def _dump_pydantic(obj: Any) -> Any:
    """Pydantic v2 → JSON-safe dict, falling back to str for unknown types."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return str(obj)


def cmd_health(_: argparse.Namespace) -> int:
    payload = {
        "vision_model": settings.vision_model,
        "openai_base_url": settings.openai_base_url,
        "hf_token_configured": bool(settings.hf_token),
        "agent_code_bin_set": bool(settings.agent_code_bin),
        "agent_code_bin": settings.agent_code_bin,
        "agent_code_model": settings.agent_code_model,
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    init_db()
    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists() or not image_path.is_file():
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        return 2

    # 1. Asset
    asset = file_store.save_upload_from_path(image_path)
    sqlite_store.save_asset(asset)

    # 2. Observation (vision + OCR via the existing handler)
    from app.api.analyze import AnalyzeRequest, analyze as analyze_handler

    observation = analyze_handler(AnalyzeRequest(asset_id=asset.asset_id))

    # 3. Intent
    from app.api.intent import ClassifyRequest, classify as classify_handler

    intent = classify_handler(
        ClassifyRequest(
            observation_id=observation.observation_id,
            user_prompt=args.prompt or "",
        )
    )

    # 4. Task graph
    from app.api.task_graph import BuildRequest, build as build_handler

    graph = build_handler(BuildRequest(intent_id=intent.intent_id))

    # 5. Agents
    from app.api.agents import RunRequest, run as run_handler

    agent_run = run_handler(
        RunRequest(graph_id=graph.graph_id, workspace_path=args.workspace or "")
    )

    if args.json:
        out = {
            "asset": _dump_pydantic(asset),
            "observation": _dump_pydantic(observation),
            "intent": _dump_pydantic(intent),
            "task_graph": _dump_pydantic(graph),
            "agent_run": _dump_pydantic(agent_run),
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(
        f"asset:       {asset.asset_id[:8]}...  "
        f"{asset.width}x{asset.height}  {asset.size_bytes}B  "
        f"({asset.filename})"
    )
    print(f"image_type:  {observation.image_type.value}")
    print(f"intent:      {intent.primary_intent.value}  (conf {intent.confidence:.2f})")
    if intent.reasoning:
        print(f"reasoning:   {intent.reasoning}")
    if intent.ambiguity:
        print(f"ambiguity:   {'; '.join(intent.ambiguity)}")
    print(f"graph:       {len(graph.nodes)} nodes")
    for n in graph.nodes:
        print(f"  - {n.task_type:24s}  {n.required_agent}")
    print()
    print(
        f"agent run:   {agent_run.status.value}  "
        f"total {agent_run.total_latency_ms}ms  "
        f"failed={agent_run.failed_count}  skipped={agent_run.skipped_count}"
    )
    for t in agent_run.traces:
        print(
            f"  [{t.status.value:7s}]  {t.task_type:24s}  {t.agent_name:22s}  {t.latency_ms}ms"
        )
        if t.error:
            print(f"            error: {t.error[:200]}")

    report_trace = next(
        (t for t in agent_run.traces if t.task_type == "draft_report"), None
    )
    if report_trace and report_trace.detail_markdown:
        print()
        print("=" * 72)
        print(report_trace.detail_markdown)
        print("=" * 72)

    return 0 if agent_run.status.value in ("done", "partial") else 1


def cmd_review(args: argparse.Namespace) -> int:
    init_db()
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        return 2

    from app.api.clawbridge import ReviewRequest, review as review_handler
    from app.schemas.clawbridge import ClawPermissionProfile

    claw_run = review_handler(
        ReviewRequest(
            workspace_path=str(workspace),
            prompt=args.prompt or "Review this repository.",
            permission_profile=ClawPermissionProfile.READ_ONLY,
            timeout_s=args.timeout,
            git_base_ref=args.base or None,
        )
    )

    if args.json:
        print(json.dumps(_dump_pydantic(claw_run), indent=2, default=str))
        return 0 if claw_run.status.value == "done" else 1

    print(f"run_id:        {claw_run.run_id[:8]}...")
    print(f"status:        {claw_run.status.value}")
    print(f"latency_ms:    {claw_run.latency_ms}")
    print(f"files_scanned: {len(claw_run.files_scanned)}")
    print(f"files_read:    {len(claw_run.files_read)}")
    if claw_run.warnings:
        print(f"warnings:      {'; '.join(claw_run.warnings)}")
    if claw_run.error:
        print(f"error:         {claw_run.error}")
    print()
    print("=" * 72)
    print(claw_run.output or "(no output)")
    print("=" * 72)
    return 0 if claw_run.status.value == "done" else 1


def cmd_chat(args: argparse.Namespace) -> int:
    init_db()
    from app.api.chat import ChatRequest, chat as chat_handler

    turn = chat_handler(
        ChatRequest(observation_id=args.observation_id, question=args.question)
    )

    if args.json:
        out = {
            "user_message": _dump_pydantic(turn.user_message),
            "assistant_message": _dump_pydantic(turn.assistant_message),
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    print("> you:")
    print(f"  {turn.user_message.content}")
    print()
    print(f"> assistant ({turn.assistant_message.latency_ms} ms):")
    print(turn.assistant_message.content)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Delegate to scripts/run_eval.py with whatever extra args were passed."""
    import subprocess

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "run_eval.py"
    if not script.exists():
        print(f"ERROR: eval script not found at {script}", file=sys.stderr)
        return 2
    return subprocess.call([sys.executable, str(script), *(args.extra or [])])


def cmd_workflow(args: argparse.Namespace) -> int:
    init_db()
    image_paths = [Path(p).expanduser().resolve() for p in args.images]
    missing = [p for p in image_paths if not p.exists() or not p.is_file()]
    if missing:
        for p in missing:
            print(f"ERROR: image not found: {p}", file=sys.stderr)
        return 2

    from app.api.analyze import AnalyzeRequest, analyze as analyze_handler
    from app.api.workflows import CreateWorkflowRequest, create as create_handler

    observation_ids: list[str] = []
    for i, image_path in enumerate(image_paths):
        print(f"[{i + 1}/{len(image_paths)}] analysing {image_path.name} ...")
        asset = file_store.save_upload_from_path(image_path)
        sqlite_store.save_asset(asset)
        observation = analyze_handler(AnalyzeRequest(asset_id=asset.asset_id))
        observation_ids.append(observation.observation_id)
        print(f"    image_type={observation.image_type.value}  obs={observation.observation_id[:8]}...")

    print(f"\nsynthesising {len(observation_ids)} observations ...")
    session = create_handler(
        CreateWorkflowRequest(
            observation_ids=observation_ids,
            title=args.title or "",
            user_prompt=args.prompt or "",
            synthesise=True,
        )
    )

    if args.json:
        print(json.dumps(_dump_pydantic(session), indent=2, default=str))
        return 0

    print(f"session_id:    {session.session_id}")
    print(f"observations:  {len(session.observation_ids)}")
    print(f"model:         {session.model_used}")
    print(f"latency_ms:    {session.latency_ms}")
    print()
    print("=" * 72)
    print(session.synthesis_markdown or "(no synthesis)")
    print("=" * 72)
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    init_db()
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.exists() or not workspace.is_dir():
        print(f"ERROR: workspace not found: {workspace}", file=sys.stderr)
        return 2

    from app import repo_index as repo_index_pkg

    print(f"indexing {workspace} ...")
    try:
        info = repo_index_pkg.build_index(str(workspace), model_name=args.model)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    sqlite_store.save_repo_index(info)

    if args.json:
        print(json.dumps(_dump_pydantic(info), indent=2, default=str))
    else:
        print(f"index_id:       {info.index_id}")
        print(f"workspace:      {info.workspace_path}")
        print(f"model:          {info.model}")
        print(f"n_files:        {info.n_files}")
        print(f"n_chunks:       {info.n_chunks}")
        print(f"created_at:     {info.created_at.isoformat()}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    init_db()
    workspace = Path(args.workspace).expanduser().resolve()
    from app import repo_index as repo_index_pkg

    loaded = repo_index_pkg.load_for_workspace(str(workspace))
    if loaded is None:
        print(
            f"ERROR: no index for {workspace}. Run `optron index -w {workspace}` first.",
            file=sys.stderr,
        )
        return 2
    hits = repo_index_pkg.search(
        loaded, args.query, k_files=args.k, chunks_per_file=args.per_file
    )

    if args.json:
        out = {
            "query": args.query,
            "index_id": loaded.info.index_id,
            "workspace_path": loaded.info.workspace_path,
            "hits": [
                {
                    "file_path": path,
                    "score": score,
                    "excerpts": [c.text[:600] for c in chunks],
                }
                for path, score, chunks in hits
            ],
        }
        print(json.dumps(out, indent=2, default=str))
    else:
        print(f"query:    {args.query}")
        print(f"index:    {loaded.info.index_id[:8]}...  ({loaded.info.n_files} files, {loaded.info.n_chunks} chunks)")
        print(f"hits:     {len(hits)}")
        for i, (path, score, chunks) in enumerate(hits, 1):
            print(f"\n  {i:>2}. {path}  (score {score:.3f})")
            for chunk in chunks:
                excerpt = chunk.text[:400].replace("\n", " ")
                print(f"      [{chunk.chunk_index}] {excerpt}...")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="optron",
        description="ogma-optron CLI: full pipeline from the terminal.",
    )
    p.add_argument("--version", action="version", version="optron 0.2.0")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("health", help="Print resolved configuration.")
    sp.set_defaults(func=cmd_health)

    sp = sub.add_parser(
        "analyze",
        help="Upload an image + run the full pipeline (vision + intent + graph + agents + report).",
    )
    sp.add_argument("image", help="Path to image file.")
    sp.add_argument(
        "--prompt", "-p", default="",
        help="Optional user prompt for intent classification.",
    )
    sp.add_argument(
        "--workspace", "-w", default="",
        help="Optional workspace path; enables CodeAgent for repo_review intents.",
    )
    sp.add_argument(
        "--json", action="store_true",
        help="Emit JSON instead of human-readable output.",
    )
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser(
        "review",
        help="Read-only repo review via agent.exe (claw). No screenshot required.",
    )
    sp.add_argument("--workspace", "-w", required=True, help="Workspace path to review.")
    sp.add_argument("--prompt", "-p", default="", help="Optional review prompt.")
    sp.add_argument(
        "--timeout", type=int, default=120,
        help="Subprocess timeout in seconds (default 120).",
    )
    sp.add_argument(
        "--base", "-b", default="",
        help="Git base ref for the diff (branch / SHA / HEAD~N). Default: origin/main, then main, then HEAD~5.",
    )
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_review)

    sp = sub.add_parser(
        "chat",
        help="Send a follow-up question for an existing observation_id.",
    )
    sp.add_argument(
        "observation_id",
        help="Observation ID from a previous `analyze` run.",
    )
    sp.add_argument(
        "question", help="Your follow-up question (quote multi-word strings).",
    )
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_chat)

    sp = sub.add_parser(
        "eval", help="Run the synthetic eval suite (delegates to scripts/run_eval.py).",
    )
    sp.add_argument(
        "extra", nargs=argparse.REMAINDER,
        help="Extra args passed to scripts/run_eval.py.",
    )
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser(
        "workflow",
        help="Analyse multiple screenshots in order and produce a workflow-level synthesis.",
    )
    sp.add_argument("images", nargs="+", help="Two or more image paths, in order.")
    sp.add_argument(
        "--prompt", "-p", default="",
        help="Optional user prompt describing what the flow is about.",
    )
    sp.add_argument(
        "--title", "-t", default="", help="Optional human-readable title for the session.",
    )
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_workflow)

    sp = sub.add_parser(
        "index",
        help="Build a semantic index over a workspace (chunker + embedder + numpy store).",
    )
    sp.add_argument("--workspace", "-w", required=True, help="Workspace path to index.")
    sp.add_argument(
        "--model",
        default="BAAI/bge-small-en-v1.5",
        help="fastembed model name (default: BAAI/bge-small-en-v1.5).",
    )
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_index)

    sp = sub.add_parser(
        "search",
        help="Semantic search over an already-built index.",
    )
    sp.add_argument("--workspace", "-w", required=True, help="Indexed workspace path.")
    sp.add_argument("query", help="Search query (quote multi-word).")
    sp.add_argument("-k", type=int, default=10, help="Top-K files (default 10).")
    sp.add_argument(
        "--per-file", type=int, default=2, help="Chunks shown per file (default 2)."
    )
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_search)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\n^C", file=sys.stderr)
        return 130
    except Exception as exc:
        # Surface HTTPException details from upstream handlers as plain stderr.
        try:
            from fastapi import HTTPException

            if isinstance(exc, HTTPException):
                print(f"ERROR ({exc.status_code}): {exc.detail}", file=sys.stderr)
                return 1
        except ImportError:
            pass
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
