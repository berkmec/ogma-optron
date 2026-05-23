"""Week 5 E2E: drive the full chain with a workspace_path so CodeAgent runs.

Generates a GitHub-like synthetic screenshot to push the intent classifier
toward repo_review (which is the only template that includes the
claw_repo_read node). Then calls /api/agents/run with workspace_path set to
this repo, so CodeAgent invokes the real agent.exe via ClawBridge.
"""

from __future__ import annotations

import sys
import time
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

API = "http://127.0.0.1:8000"
WORKSPACE = r"C:\Users\pc\Desktop\ogma-optron"


def github_png() -> bytes:
    img = Image.new("RGB", (900, 480), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (900, 56)], fill=(13, 17, 23))
    d.text((20, 18), "GitHub  /  ultraworkers / claw-code", fill=(240, 246, 252))
    d.text((780, 18), "Star  Fork  Watch", fill=(240, 246, 252))
    d.text((20, 90), "Branches:  main  *", fill=(36, 41, 47))
    d.text((20, 130), "Latest commit  d3f4a2c  by berkmm1  2 hours ago", fill=(110, 119, 129))
    d.text((20, 180), "src/", fill=(9, 105, 218))
    d.text((20, 210), "tests/", fill=(9, 105, 218))
    d.text((20, 240), "README.md", fill=(9, 105, 218))
    d.text((20, 270), "LICENSE", fill=(9, 105, 218))
    d.text((20, 320), "Issues 12   Pull requests 3   Actions   Projects", fill=(36, 41, 47))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def post(path: str, **kwargs) -> dict:
    r = httpx.post(f"{API}{path}", timeout=300, **kwargs)
    r.raise_for_status()
    return r.json()


def main() -> None:
    png = github_png()

    print("[1/5] upload")
    t = time.perf_counter()
    asset = post("/api/assets/upload", files={"file": ("gh.png", png, "image/png")})
    print(f"   asset_id={asset['asset_id'][:8]}...  +{(time.perf_counter()-t)*1000:.0f}ms")

    print("[2/5] analyze")
    t = time.perf_counter()
    obs = post("/api/vision/analyze", json={"asset_id": asset["asset_id"]})
    print(f"   image_type={obs['image_type']}  +{(time.perf_counter()-t)*1000:.0f}ms")

    print("[3/5] intent.classify")
    t = time.perf_counter()
    intent = post(
        "/api/intent/classify",
        json={
            "observation_id": obs["observation_id"],
            "user_prompt": "Give me a quick review of this repository.",
        },
    )
    print(
        f"   intent={intent['primary_intent']}  conf={intent['confidence']:.2f}  +{(time.perf_counter()-t)*1000:.0f}ms"
    )

    print("[4/5] task-graph.build")
    t = time.perf_counter()
    graph = post("/api/task-graph/build", json={"intent_id": intent["intent_id"]})
    print(f"   {len(graph['nodes'])} nodes  +{(time.perf_counter()-t)*1000:.0f}ms")
    for n in graph["nodes"]:
        print(f"     - {n['task_type']:24s} {n['required_agent']}")

    print(f"[5/5] agents.run  workspace_path={WORKSPACE}")
    t = time.perf_counter()
    run = post(
        "/api/agents/run",
        json={"graph_id": graph["graph_id"], "workspace_path": WORKSPACE},
    )
    print(f"   run_id={run['run_id'][:8]}...  status={run['status']}")
    print(f"   total_latency_ms={run['total_latency_ms']}  failed={run['failed_count']}  skipped={run['skipped_count']}")
    print()
    print("   trace:")
    for t_ in run["traces"]:
        glyph = {"done": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(t_["status"], t_["status"])
        print(f"     [{glyph:4s}] {t_['task_type']:24s} {t_['agent_name']:22s} {t_['latency_ms']:>6} ms")
        if t_["error"]:
            print(f"       error: {t_['error'][:200]}")
        if t_["warnings"]:
            print(f"       warn:  {t_['warnings']}")

    code_trace = next((t for t in run["traces"] if t["agent_name"] == "CodeAgent"), None)
    if code_trace and code_trace["detail_markdown"]:
        print()
        print("=== CodeAgent (ClawBridge) detail_markdown — first 2000 chars ===")
        md = code_trace["detail_markdown"]
        print(md[:2000])

    report_trace = next((t for t in run["traces"] if t["task_type"] == "draft_report"), None)
    if report_trace and report_trace["detail_markdown"]:
        print()
        print("=== ReportAgent markdown — first 1500 chars ===")
        print(report_trace["detail_markdown"][:1500])


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
