"""Run the synthetic eval set and emit a JSON + markdown benchmark report.

For each case in scripts/eval_cases.py, drive upload -> analyze ->
intent.classify. Aggregates:
- image_type accuracy (observation.image_type vs expected)
- intent accuracy (intent.primary_intent vs expected)
- latency percentiles (p50, p95, p99) per step
- per-case rows

Writes benchmarks/eval_<UTC-date>.json and .md under the repo root.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Make scripts/ importable when run from repo root or from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_cases import CASES, EvalCase  # noqa: E402

API = "http://127.0.0.1:8000"
REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "benchmarks"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def _summary(name: str, vals: list[float]) -> dict:
    return {
        "step": name,
        "n": len(vals),
        "p50_ms": round(_percentile(vals, 0.50), 1),
        "p95_ms": round(_percentile(vals, 0.95), 1),
        "p99_ms": round(_percentile(vals, 0.99), 1),
        "mean_ms": round(statistics.fmean(vals), 1) if vals else 0.0,
    }


def run_case(client: httpx.Client, case: EvalCase) -> dict:
    row: dict = {
        "case_id": case.case_id,
        "expected_image_type": case.expected_image_type,
        "expected_intent": case.expected_intent,
        "user_prompt": case.user_prompt,
        "actual_image_type": None,
        "actual_intent": None,
        "intent_confidence": None,
        "image_type_ok": False,
        "intent_ok": False,
        "latency_ms": {},
        "error": None,
    }

    try:
        t = time.perf_counter()
        r = client.post(
            f"{API}/api/assets/upload",
            files={"file": (case.case_id + ".png", case.png, "image/png")},
            timeout=30,
        )
        r.raise_for_status()
        asset = r.json()
        row["latency_ms"]["upload"] = int((time.perf_counter() - t) * 1000)

        t = time.perf_counter()
        r = client.post(
            f"{API}/api/vision/analyze",
            json={"asset_id": asset["asset_id"]},
            timeout=180,
        )
        r.raise_for_status()
        obs = r.json()
        row["latency_ms"]["analyze"] = int((time.perf_counter() - t) * 1000)
        row["actual_image_type"] = obs["image_type"]
        row["image_type_ok"] = obs["image_type"] == case.expected_image_type

        t = time.perf_counter()
        r = client.post(
            f"{API}/api/intent/classify",
            json={"observation_id": obs["observation_id"], "user_prompt": case.user_prompt},
            timeout=120,
        )
        r.raise_for_status()
        intent = r.json()
        row["latency_ms"]["intent"] = int((time.perf_counter() - t) * 1000)
        row["actual_intent"] = intent["primary_intent"]
        row["intent_confidence"] = intent["confidence"]
        row["intent_ok"] = intent["primary_intent"] == case.expected_intent
    except Exception as exc:
        row["error"] = str(exc)[:300]

    return row


def render_markdown(rows: list[dict], summaries: dict, started: datetime, finished: datetime) -> str:
    n = len(rows)
    img_ok = sum(1 for r in rows if r["image_type_ok"])
    int_ok = sum(1 for r in rows if r["intent_ok"])
    err = sum(1 for r in rows if r["error"])

    out = [
        f"# ogma-optron eval — {started.date()}",
        "",
        f"- Cases: **{n}**",
        f"- image_type accuracy: **{img_ok}/{n} = {100*img_ok/n:.0f}%**",
        f"- intent accuracy:     **{int_ok}/{n} = {100*int_ok/n:.0f}%**",
        f"- errored cases:       **{err}**",
        f"- wall: {(finished - started).total_seconds():.1f}s",
        "",
        "## Latency percentiles (ms)",
        "",
        "| step | n | p50 | p95 | p99 | mean |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in summaries["per_step"]:
        out.append(
            f"| {s['step']} | {s['n']} | {s['p50_ms']} | {s['p95_ms']} | {s['p99_ms']} | {s['mean_ms']} |"
        )

    out += [
        "",
        "## Per-case results",
        "",
        "| case | expected_image | got_image | expected_intent | got_intent | conf | upload | analyze | intent |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        lm = r["latency_ms"]
        out.append(
            f"| {r['case_id']} | {r['expected_image_type']} | "
            f"{r['actual_image_type']} {_check(r['image_type_ok'])} | "
            f"{r['expected_intent']} | "
            f"{r['actual_intent']} {_check(r['intent_ok'])} | "
            f"{r['intent_confidence'] if r['intent_confidence'] is not None else ''} | "
            f"{lm.get('upload', '')} | {lm.get('analyze', '')} | {lm.get('intent', '')} |"
        )
    return "\n".join(out) + "\n"


def _check(ok: bool) -> str:
    return "OK" if ok else "MISS"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    rows: list[dict] = []
    with httpx.Client() as client:
        try:
            client.get(f"{API}/api/health", timeout=5).raise_for_status()
        except Exception as exc:
            sys.exit(f"backend not reachable at {API}: {exc}")
        for case in CASES:
            print(f"  - {case.case_id} ... ", end="", flush=True)
            row = run_case(client, case)
            ok_marker = (
                "OK" if row["image_type_ok"] and row["intent_ok"]
                else ("PARTIAL" if (row["image_type_ok"] or row["intent_ok"]) else "MISS")
            )
            if row["error"]:
                ok_marker = "ERR"
            print(f"{ok_marker}  ({row['latency_ms']})")
            rows.append(row)
    finished = datetime.now(timezone.utc)

    per_step = []
    for step in ["upload", "analyze", "intent"]:
        vals = [r["latency_ms"][step] for r in rows if step in r["latency_ms"]]
        per_step.append(_summary(step, vals))

    img_ok = sum(1 for r in rows if r["image_type_ok"])
    int_ok = sum(1 for r in rows if r["intent_ok"])
    n = len(rows)
    summaries = {
        "n_cases": n,
        "image_type_correct": img_ok,
        "image_type_accuracy": round(img_ok / n, 3) if n else 0.0,
        "intent_correct": int_ok,
        "intent_accuracy": round(int_ok / n, 3) if n else 0.0,
        "errored": sum(1 for r in rows if r["error"]),
        "per_step": per_step,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "wall_seconds": round((finished - started).total_seconds(), 1),
    }

    date_tag = started.strftime("%Y-%m-%d")
    json_path = OUT_DIR / f"eval_{date_tag}.json"
    md_path = OUT_DIR / f"eval_{date_tag}.md"
    json_path.write_text(
        json.dumps({"summary": summaries, "cases": rows}, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(rows, summaries, started, finished), encoding="utf-8")

    print()
    print(f"  image_type accuracy: {img_ok}/{n}")
    print(f"  intent accuracy:     {int_ok}/{n}")
    print(f"  wrote {json_path.relative_to(REPO_ROOT)}")
    print(f"  wrote {md_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
