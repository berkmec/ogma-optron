"""End-to-end smoke test: synthetic error screenshot -> upload -> analyze.

Builds a fake error screenshot in-memory, POSTs it to /api/assets/upload, then
POSTs the returned asset_id to /api/vision/analyze and prints the observation.

First run will be slow because RapidOCR downloads ~80MB of ONNX models.
"""

from __future__ import annotations

import sys
import time
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

API = "http://127.0.0.1:8000"


def make_error_screenshot() -> bytes:
    img = Image.new("RGB", (760, 420), color=(20, 22, 30))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "ERROR: ConnectionRefusedError", fill=(255, 90, 90))
    d.text((30, 80), "Could not connect to host api.example.com:443", fill=(220, 220, 220))
    d.text((30, 140), "Traceback (most recent call last):", fill=(180, 180, 180))
    d.text((30, 180), '  File "main.py", line 42, in <module>', fill=(180, 180, 180))
    d.text((30, 220), "    response = client.get(url, timeout=5)", fill=(180, 180, 180))
    d.text((30, 280), "ConnectionError: [Errno 111] Connection refused", fill=(255, 120, 120))
    d.text((30, 350), "Suggestion: check firewall and DNS", fill=(120, 180, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> None:
    png = make_error_screenshot()

    print("step 1: POST /api/assets/upload")
    r = httpx.post(
        f"{API}/api/assets/upload",
        files={"file": ("synth_error.png", png, "image/png")},
        timeout=30,
    )
    r.raise_for_status()
    asset = r.json()
    print(f"  asset_id={asset['asset_id']}  {asset['width']}x{asset['height']}  {asset['size_bytes']}B")

    print("step 2: POST /api/vision/analyze (RapidOCR cold start may be slow)")
    t0 = time.perf_counter()
    r = httpx.post(
        f"{API}/api/vision/analyze",
        json={"asset_id": asset["asset_id"]},
        timeout=300,
    )
    r.raise_for_status()
    obs = r.json()
    wall = time.perf_counter() - t0
    print(f"  observation_id={obs['observation_id']}")
    print(f"  image_type     ={obs['image_type']}")
    print(f"  model_used     ={obs['model_used']}")
    print(f"  latency_ms     ={obs['latency_ms']}  (wall {wall*1000:.0f}ms)")
    print(f"  confidence     ={obs['confidence']}")
    print(f"  warnings       ={obs['warnings']}")
    print("  --- ocr_text ---")
    print(f"  {obs['ocr_text'].replace(chr(10), chr(10) + '  ')}")
    print("  --- vision_description ---")
    print(f"  {obs['vision_description']}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
