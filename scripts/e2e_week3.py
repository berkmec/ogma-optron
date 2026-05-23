"""Week 3 E2E: upload -> analyze -> classify intent -> build task graph -> report.

Drives the full chain end-to-end. Uses the synthetic error screenshot from
e2e_smoke.py to keep behavior reproducible.
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

    print("[1/4] upload")
    t = time.perf_counter()
    asset = post(
        "/api/assets/upload",
        files={"file": ("synth_error.png", png, "image/png")},
    )
    print(f"   asset_id={asset['asset_id'][:8]}...  {asset['width']}x{asset['height']}  +{(time.perf_counter()-t)*1000:.0f}ms")

    print("[2/4] analyze")
    t = time.perf_counter()
    obs = post("/api/vision/analyze", json={"asset_id": asset["asset_id"]})
    print(f"   image_type={obs['image_type']}  obs_id={obs['observation_id'][:8]}...  +{(time.perf_counter()-t)*1000:.0f}ms")

    print("[3/4] intent.classify")
    t = time.perf_counter()
    intent = post(
        "/api/intent/classify",
        json={
            "observation_id": obs["observation_id"],
            "user_prompt": "What does this error mean and how do I fix it?",
        },
    )
    print(f"   intent={intent['primary_intent']}  conf={intent['confidence']}  intent_id={intent['intent_id'][:8]}...  +{(time.perf_counter()-t)*1000:.0f}ms")
    print(f"   reasoning: {intent['reasoning']}")
    if intent["ambiguity"]:
        print(f"   ambiguity: {intent['ambiguity']}")

    print("[4a/4] task-graph.build")
    t = time.perf_counter()
    graph = post("/api/task-graph/build", json={"intent_id": intent["intent_id"]})
    print(f"   graph_id={graph['graph_id'][:8]}...  nodes={len(graph['nodes'])}  +{(time.perf_counter()-t)*1000:.0f}ms")
    for node in graph["nodes"]:
        deps = " <- " + ",".join(d[:6] for d in node["depends_on"]) if node["depends_on"] else ""
        print(f"     - {node['task_type']:24s} {node['required_agent']:20s} {deps}")

    print("[4b/4] reports.generate")
    t = time.perf_counter()
    report = post("/api/reports/generate", json={"graph_id": graph["graph_id"]})
    print(f"   report_id={report['report_id'][:8]}...  +{(time.perf_counter()-t)*1000:.0f}ms")
    print(f"   title: {report['title']}")
    print(f"   model: {report['model_used']}  draft_latency_ms={report['latency_ms']}")
    print()
    print("=" * 72)
    print(report["markdown"])
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
