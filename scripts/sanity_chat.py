"""Sanity for chat-over-observation + sessions list.

Upload a synthetic error screenshot, analyze it, send two chat questions
on the same observation, then call /api/sessions to confirm it's listed.
"""

from __future__ import annotations

import sys
import time
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

API = "http://127.0.0.1:8000"


def error_png() -> bytes:
    img = Image.new("RGB", (700, 360), color=(20, 22, 30))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "ERROR: ConnectionRefusedError", fill=(255, 90, 90))
    d.text((30, 90), "Could not connect to api.example.com:443", fill=(220, 220, 220))
    d.text((30, 180), "ConnectionError: [Errno 111] refused", fill=(255, 110, 110))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def post(path: str, **kwargs) -> dict:
    r = httpx.post(f"{API}{path}", timeout=300, **kwargs)
    r.raise_for_status()
    return r.json()


def get(path: str) -> object:
    r = httpx.get(f"{API}{path}", timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> None:
    print("[1] upload + analyze")
    asset = post("/api/assets/upload", files={"file": ("e.png", error_png(), "image/png")})
    obs = post("/api/vision/analyze", json={"asset_id": asset["asset_id"]})
    print(f"   asset {asset['asset_id'][:8]}, obs {obs['observation_id'][:8]}, type={obs['image_type']}")

    print("[2] chat: 'What does this error mean?'")
    t = time.perf_counter()
    turn1 = post(
        "/api/chat",
        json={"observation_id": obs["observation_id"], "question": "What does this error mean?"},
    )
    print(f"   +{(time.perf_counter()-t)*1000:.0f}ms")
    print(f"   user: {turn1['user_message']['content']}")
    print(f"   asst: {turn1['assistant_message']['content'][:400]}")

    print("[3] chat: 'List the 3 most likely fixes.'")
    t = time.perf_counter()
    turn2 = post(
        "/api/chat",
        json={"observation_id": obs["observation_id"], "question": "List the 3 most likely fixes."},
    )
    print(f"   +{(time.perf_counter()-t)*1000:.0f}ms")
    print(f"   asst: {turn2['assistant_message']['content'][:400]}")

    print("[4] GET /api/chat/{observation_id}")
    history = get(f"/api/chat/{obs['observation_id']}")
    print(f"   {len(history)} messages in history")

    print("[5] GET /api/sessions")
    sessions = get("/api/sessions?limit=5")
    print(f"   {len(sessions)} recent sessions")
    for s in sessions[:3]:
        obs_type = s["observation"]["image_type"] if s["observation"] else "(no obs)"
        report_title = s["latest_report"]["title"] if s["latest_report"] else "(no report)"
        print(f"     - {s['asset']['asset_id'][:8]}  type={obs_type:20s}  report={report_title}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
