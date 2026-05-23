"""Week 4 E2E: upload -> analyze -> classify -> build graph -> RUN AGENTS.

Drives the full chain. The final step replaces the single ReportAgent call
from week 3 with the executor running the full task graph through the
AgentManager.
"""

from __future__ import annotations

import sys
import time
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

API = "http://127.0.0.1:8000"


def error_png() -> bytes:
    img = Image.new("RGB", (760, 420), color=(20, 22, 30))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "ERROR: ConnectionRefusedError", fill=(255, 90, 90))
    d.text((30, 80), "Could not connect to host api.example.com:443", fill=(220, 220, 220))
    d.text((30, 140), "Traceback (most recent call last):", fill=(180, 180, 180))
    d.text((30, 180), '  File "main.py", line 42, in <module>', fill=(180, 180, 180))
    d.text((30, 220), "    response = client.get(url, timeout=5)", fill=(180, 180, 180))
    d.text((30, 280), "ConnectionError: [Errno 111] Connection refused", fill=(255, 120, 120))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def post(path: str, **kwargs) -> dict:
    r = httpx.post(f"{API}{path}", timeout=300, **kwargs)
    r.raise_for_status()
    return r.json()


def main() -> None:
    png = error_png()

    print("[1/5] upload")
    t = time.perf_counter()
    asset = post(
        "/api/assets/upload", files={"file": ("err.png", png, "image/png")}
    )
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
            "user_prompt": "What does this error mean and how do I fix it?",
        },
    )
    print(f"   intent={intent['primary_intent']}  conf={intent['confidence']:.2f}  +{(time.perf_counter()-t)*1000:.0f}ms")

    print("[4/5] task-graph.build")
    t = time.perf_counter()
    graph = post("/api/task-graph/build", json={"intent_id": intent["intent_id"]})
    print(f"   {len(graph['nodes'])} nodes  +{(time.perf_counter()-t)*1000:.0f}ms")

    print("[5/5] agents.run  (executor walks the graph)")
    t = time.perf_counter()
    run = post("/api/agents/run", json={"graph_id": graph["graph_id"]})
    wall = (time.perf_counter() - t) * 1000
    print(f"   run_id={run['run_id'][:8]}...  status={run['status']}")
    print(f"   total_latency_ms={run['total_latency_ms']}  wall={wall:.0f}ms")
    print(f"   failed={run['failed_count']}  skipped={run['skipped_count']}")
    print()
    print("   trace:")
    for t_ in run["traces"]:
        glyph = {"done": "OK", "failed": "FAIL", "skipped": "SKIP"}.get(t_["status"], t_["status"])
        print(
            f"     [{glyph:4s}] {t_['task_type']:24s} {t_['agent_name']:22s} {t_['latency_ms']:>6} ms"
        )
        if t_["error"]:
            print(f"       error: {t_['error']}")
        if t_["warnings"]:
            print(f"       warn:  {t_['warnings']}")

    # Show the report node's markdown
    report_trace = next(
        (t for t in run["traces"] if t["task_type"] == "draft_report"), None
    )
    if report_trace and report_trace["detail_markdown"]:
        print()
        print("=" * 72)
        print(report_trace["detail_markdown"])
        print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
