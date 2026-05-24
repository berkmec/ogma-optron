"""ClawBridge: safe subprocess wrapper for agent.exe (claw upstream).

Default profile is read-only: agent.exe runs with --permission-mode deny
(so it cannot read / write / shell on its own), and the relevant workspace
contents are scanned in Python and injected into the prompt instead. This
keeps the read-only guarantee enforceable here rather than relying on the
subprocess's internal permission model.

Plan profile (--permission-mode plan) is exposed but not selected by
default. Workspace-write, shell-enabled, and network-enabled modes are
intentionally NOT exposed in the MVP.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from pathlib import Path

from app.clawbridge.run_store import save_run_log
from app.clawbridge.workspace_scanner import (
    MAX_FILE_BYTES,
    WorkspaceScan,
    scan_workspace,
)
from app.config import settings
from app.gitctx.diff import collect_git_context, format_context_block
from app.repo_index import load_for_workspace, search as index_search
from app.schemas.asset import utcnow
from app.schemas.clawbridge import ClawPermissionProfile, ClawRun, ClawRunStatus

DEFAULT_TIMEOUT_S = 120
DEFAULT_MAX_OUTPUT_CHARS = 20_000

_BLOCKED_PATHS: tuple[str, ...] = (
    os.environ.get("WINDIR", r"C:\Windows"),
    r"C:\Program Files",
    r"C:\Program Files (x86)",
)

_REVIEW_PROMPT_TEMPLATE = """You are a code reviewer.

Workspace path: {workspace}
Listed files: {n_files} (truncated: {truncated})

Listing:
{file_list}

{git_block}{semantic_block}Key file contents (each truncated to {max_bytes} bytes):
{file_contents}

User question: {user_prompt}

Write a concise markdown review:
## What this repository appears to be
## Notable observations (structure, language(s), tests, docs)
## Concerns or open questions
## Suggested follow-ups

Stay grounded in the listing and any semantic-search excerpts above. Do not
invent files that are not present. If the evidence is thin for any heading,
say so briefly.
"""


def _validate_workspace(raw: str) -> Path:
    if not raw:
        raise ValueError("workspace_path is empty")
    p = Path(raw).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Workspace does not exist or is not a directory: {p}")
    for blocked in _BLOCKED_PATHS:
        try:
            b = Path(blocked).resolve()
        except OSError:
            continue
        try:
            p.relative_to(b)
        except ValueError:
            # p is NOT under this blocked root; move on.
            continue
        # p IS under a blocked root; refuse.
        raise ValueError(f"Blocked system directory: {p}")
    return p


def _build_file_contents_block(file_contents: dict[str, str]) -> str:
    if not file_contents:
        return "(no key files captured)"
    parts = []
    for name, content in file_contents.items():
        parts.append(f"### {name}\n```\n{content}\n```")
    return "\n\n".join(parts)


def _build_semantic_block(workspace: Path, user_prompt: str) -> str:
    """If a repo_index exists for this workspace, return a markdown block of
    the top-K semantic-search hits. Empty string when no index is available
    or the search yields nothing."""
    query = user_prompt.strip() or "What does this repository do? Architecture, key modules, risks."
    loaded = load_for_workspace(str(workspace))
    if loaded is None:
        return ""
    hits = index_search(loaded, query, k_files=10, chunks_per_file=2)
    if not hits:
        return ""
    parts = [
        "Semantic-search excerpts (most relevant chunks to the user's question):\n",
    ]
    for file_path, score, chunks in hits:
        parts.append(f"### {file_path}  (score {score:.3f})")
        for chunk in chunks:
            excerpt = chunk.text[:1500]
            parts.append(f"```\n{excerpt}\n```")
    parts.append("")  # trailing newline before "Key file contents" header
    return "\n".join(parts) + "\n"


def _build_git_block(workspace: Path, base_ref: str | None) -> str:
    """Snapshot of the repo's branch/diff/uncommitted state, or empty string
    if the workspace is not a git repo (or git isn't on PATH)."""
    ctx = collect_git_context(workspace, base_ref=base_ref)
    return format_context_block(ctx)


def _build_review_prompt(
    workspace: Path,
    scan: WorkspaceScan,
    user_prompt: str,
    git_base_ref: str | None = None,
) -> str:
    return _REVIEW_PROMPT_TEMPLATE.format(
        workspace=str(workspace),
        n_files=len(scan.files),
        truncated=scan.truncated,
        file_list="\n".join(scan.files[:80]),
        git_block=_build_git_block(workspace, git_base_ref),
        semantic_block=_build_semantic_block(workspace, user_prompt),
        max_bytes=MAX_FILE_BYTES,
        file_contents=_build_file_contents_block(scan.file_contents),
        user_prompt=user_prompt.strip() or "Review this repository.",
    )


def _permission_mode_for(profile: ClawPermissionProfile) -> str:
    return "plan" if profile == ClawPermissionProfile.PLAN else "deny"


def run_repo_review(
    workspace_path: str,
    user_prompt: str = "Review this repository.",
    profile: ClawPermissionProfile = ClawPermissionProfile.READ_ONLY,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    git_base_ref: str | None = None,
) -> ClawRun:
    run_id = str(uuid.uuid4())
    started = utcnow()

    if not settings.agent_code_bin or not Path(settings.agent_code_bin).exists():
        return ClawRun(
            run_id=run_id,
            workspace_path=workspace_path,
            prompt=user_prompt,
            permission_profile=profile,
            status=ClawRunStatus.FAILED,
            error="AGENT_CODE_BIN missing or not configured in .env",
            started_at=started,
            finished_at=utcnow(),
        )

    try:
        workspace = _validate_workspace(workspace_path)
    except ValueError as exc:
        return ClawRun(
            run_id=run_id,
            workspace_path=workspace_path,
            prompt=user_prompt,
            permission_profile=profile,
            status=ClawRunStatus.BLOCKED,
            error=str(exc),
            started_at=started,
            finished_at=utcnow(),
        )

    scan = scan_workspace(workspace)
    prompt = _build_review_prompt(workspace, scan, user_prompt, git_base_ref=git_base_ref)

    env = os.environ.copy()
    env["AGENT_CODE_API_BASE_URL"] = settings.agent_code_api_base_url
    env["AGENT_CODE_API_KEY"] = settings.agent_code_api_key
    env["AGENT_CODE_MODEL"] = settings.agent_code_model

    cmd = [
        settings.agent_code_bin,
        "--api-base-url", settings.agent_code_api_base_url,
        "--api-key", settings.agent_code_api_key,
        "--model", settings.agent_code_model,
        "--permission-mode", _permission_mode_for(profile),
        "--output-format", "text",
        "--cwd", str(workspace),
        "-p", prompt,
    ]

    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(workspace),
        )
    except subprocess.TimeoutExpired:
        finished = utcnow()
        run = ClawRun(
            run_id=run_id,
            workspace_path=str(workspace),
            prompt=user_prompt,
            permission_profile=profile,
            status=ClawRunStatus.TIMEOUT,
            files_scanned=scan.files,
            files_read=list(scan.file_contents.keys()),
            timeout_s=timeout_s,
            model_used=settings.agent_code_model,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            error=f"Timeout after {timeout_s}s",
            started_at=started,
            finished_at=finished,
        )
        save_run_log(run, prompt, "", "(timeout)")
        return run

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    raw_stdout = result.stdout or ""
    raw_stderr = result.stderr or ""
    output = raw_stdout[:max_output_chars]
    warnings: list[str] = []
    if len(raw_stdout) > max_output_chars:
        warnings.append(
            f"stdout truncated from {len(raw_stdout)} to {max_output_chars} chars"
        )
    if raw_stderr.strip():
        warnings.append(f"stderr: {raw_stderr.strip()[:300]}")
    if scan.truncated:
        warnings.append(
            f"workspace listing truncated at {len(scan.files)} files"
        )

    status = ClawRunStatus.DONE if result.returncode == 0 else ClawRunStatus.FAILED
    error = ""
    if result.returncode != 0:
        error = f"exit code {result.returncode}; stderr: {raw_stderr[:500]}"

    run = ClawRun(
        run_id=run_id,
        workspace_path=str(workspace),
        prompt=user_prompt,
        permission_profile=profile,
        status=status,
        output=output,
        files_scanned=scan.files,
        files_read=list(scan.file_contents.keys()),
        warnings=warnings,
        timeout_s=timeout_s,
        model_used=settings.agent_code_model,
        latency_ms=elapsed_ms,
        error=error,
        started_at=started,
        finished_at=utcnow(),
    )

    save_run_log(run, prompt, raw_stdout, raw_stderr)
    return run
