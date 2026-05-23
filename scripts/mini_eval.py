"""Mini eval: 5 synthetic screenshots, check image_type accuracy.

This is not a real evaluation. Synthetic PIL drawings are easier than real
screenshots — treat the pass rate as a smoke gate, not a benchmark.
"""

from __future__ import annotations

import sys
import time
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

API = "http://127.0.0.1:8000"


def err() -> bytes:
    img = Image.new("RGB", (700, 360), color=(20, 22, 30))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "FATAL: NullPointerException", fill=(255, 80, 80))
    d.text((30, 80), "Traceback (most recent call last):", fill=(220, 220, 220))
    d.text((30, 120), '  File "main.py", line 42', fill=(220, 220, 220))
    d.text((30, 160), '  AttributeError: NoneType has no attribute', fill=(255, 110, 110))
    d.text((30, 220), "Process exited with code 1", fill=(200, 200, 200))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def github() -> bytes:
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


def dashboard() -> bytes:
    img = Image.new("RGB", (900, 540), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (900, 60)], fill=(30, 80, 200))
    d.text((20, 20), "Analytics Dashboard", fill=(255, 255, 255))
    for i, (label, value) in enumerate([
        ("Users", "12,304"),
        ("Revenue", "$48.2K"),
        ("Sessions", "9,812"),
    ]):
        x = 30 + i * 280
        d.rectangle([(x, 100), (x + 250, 220)], fill=(255, 255, 255), outline=(220, 220, 220))
        d.text((x + 16, 120), label, fill=(110, 110, 110))
        d.text((x + 16, 160), value, fill=(20, 20, 20))
    d.text((30, 270), "Recent activity:", fill=(20, 20, 20))
    for i, txt in enumerate(["+ new signup", "+ payment received", "- subscription canceled"]):
        d.text((30, 310 + i * 30), txt, fill=(60, 60, 60))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def code_editor() -> bytes:
    img = Image.new("RGB", (820, 500), color=(30, 30, 36))
    d = ImageDraw.Draw(img)
    for i in range(20):
        d.text((10, 20 + i * 22), f"{i + 1:>3}", fill=(110, 110, 130))
    lines = [
        "def fetch_user(user_id: int) -> User | None:",
        '    """Return a user by id, or None if absent."""',
        "    with sessionmaker() as session:",
        "        result = session.query(User)",
        "        result = result.filter(User.id == user_id)",
        "        return result.one_or_none()",
        "",
        "class UserService:",
        "    def __init__(self, repo: UserRepo) -> None:",
        "        self.repo = repo",
        "",
        "    def get(self, user_id: int) -> User:",
        "        user = self.repo.find(user_id)",
        "        if user is None:",
        "            raise NotFoundError(user_id)",
        "        return user",
    ]
    for i, line in enumerate(lines):
        d.text((50, 20 + i * 22), line, fill=(220, 220, 220))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def document_page() -> bytes:
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((60, 60), "Chapter 3: Attention Is All You Need", fill=(0, 0, 0))
    d.text((60, 110), "Abstract", fill=(60, 60, 60))
    body = (
        "The dominant sequence transduction models are based on complex recurrent or convolutional"
        " neural networks that include an encoder and a decoder. The best performing models also"
        " connect the encoder and decoder through an attention mechanism. We propose a new simple"
        " network architecture, the Transformer, based solely on attention mechanisms, dispensing"
        " with recurrence and convolutions entirely."
    )
    # naive wrap
    words = body.split()
    line, y = "", 150
    for w in words:
        if len(line) + len(w) + 1 > 90:
            d.text((60, y), line, fill=(30, 30, 30))
            y += 22
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        d.text((60, y), line, fill=(30, 30, 30))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


CASES = [
    ("error_synth.png", "error_screen", err),
    ("github_synth.png", "github_repo", github),
    ("dashboard_synth.png", "ui_dashboard", dashboard),
    ("code_synth.png", "code_editor", code_editor),
    ("doc_synth.png", "document_page", document_page),
]


def run_one(name: str, png: bytes) -> dict:
    up = httpx.post(
        f"{API}/api/assets/upload",
        files={"file": (name, png, "image/png")},
        timeout=30,
    )
    up.raise_for_status()
    asset_id = up.json()["asset_id"]
    an = httpx.post(
        f"{API}/api/vision/analyze",
        json={"asset_id": asset_id},
        timeout=180,
    )
    an.raise_for_status()
    return an.json()


def main() -> None:
    print(f"running {len(CASES)} mini-eval cases against {API}")
    correct = 0
    rows: list[tuple[str, str, str, int]] = []
    for name, expected, fn in CASES:
        t0 = time.perf_counter()
        try:
            obs = run_one(name, fn())
            got = obs["image_type"]
            ok = got == expected
            correct += int(ok)
            rows.append((name, expected, got, int((time.perf_counter() - t0) * 1000)))
            print(f"  {name:24s} expected={expected:18s} got={got:18s} {'OK' if ok else 'MISS'}")
        except Exception as e:
            rows.append((name, expected, f"ERROR:{e}", int((time.perf_counter() - t0) * 1000)))
            print(f"  {name:24s} expected={expected:18s} ERROR: {e}")

    print()
    print(f"accuracy: {correct}/{len(CASES)} = {100 * correct / len(CASES):.0f}%")
    print()
    print("| case | expected | got | latency_ms |")
    print("|---|---|---|---|")
    for name, exp, got, ms in rows:
        print(f"| {name} | {exp} | {got} | {ms} |")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPStatusError as e:
        print(f"HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
