# ClawBridge: safe subprocess wrapper for `agent.exe`

ogma-optron's `CodeAgent` does not import or embed the upstream `claw` codebase. It spawns the `agent.exe` binary (installed via `cargo install agent-code`) as a child process under a strict, Python-enforced read-only contract.

## The contract

| guarantee | how it is enforced |
|---|---|
| Agent cannot read files on its own. | Subprocess is launched with `--permission-mode deny`, which refuses every tool call. The relevant workspace contents are scanned in Python and injected into the prompt as context instead. |
| Agent cannot write / shell / network. | Same `--permission-mode deny` blocks `bash`, `write_file`, `edit_file`, and any network tool. |
| Agent cannot escape the workspace. | `--cwd <workspace>` is set, and the workspace path is validated (must exist, must be a directory, must not be inside `C:\Windows`, `C:\Program Files`, etc.). Path traversal in the listing is impossible because the listing is built by `os.walk` from a resolved absolute root. |
| Output cannot blow up. | `subprocess.run(timeout=120, capture_output=True)`; stdout truncated to 20 000 chars; stderr stamped into warnings; everything persisted to `runs/claw/{run_id}/`. |

The read-only guarantee is enforced **outside** the subprocess. We do not trust agent.exe's internal permission model in isolation; the Python wrapper is the load-bearing piece.

## Evidence the guarantee holds

During the week 5 sanity probe, agent.exe attempted to invoke its `Brief` tool. The wire response from agent.exe was:

```
Permission denied: Default mode denies Brief
```

Followed by the model falling back to context-only synthesis. This was logged into `runs/claw/<run_id>/stderr.txt` and surfaced as a warning on the `ClawRun`. Same probe at the start of week 7 still shows the deny path active.

The path-traversal guard is unit-tested in `backend/tests/test_clawbridge_safety.py`:

- empty / missing workspace → `ClawRunStatus.BLOCKED`
- workspace inside `C:\Program Files` → `_validate_workspace` raises (regression test added after a real bug where the raise was being swallowed by an outer `except ValueError`)
- missing `AGENT_CODE_BIN` → `ClawRunStatus.FAILED`

## Workspace scanner

`backend/app/clawbridge/workspace_scanner.py`. Bounded recursive listing:

- max 200 files, depth 4
- skips `.git`, `node_modules`, `.venv`/`venv`, `__pycache__`, `target`, `dist`, `build`, `.next`, `.cache`, IDE folders, and any other dot-prefixed dirs
- reads the content of *important* files only: `README*`, `pyproject.toml`, `package.json`, `Cargo.toml`, `Dockerfile`, `.gitignore`, etc.
- each captured file is truncated to 50 KB

Files larger than 50 KB are listed by name but not read. The truncation flag is surfaced on the `ClawRun` if the listing hit the file cap.

## Prompt that goes to agent.exe

```
You are a code reviewer.

Workspace path: <abs path>
Listed files: <N> (truncated: <bool>)

Listing:
<sorted, relative posix paths>

Key file contents (each truncated to 50000 bytes):
### README.md
```
…
```
### pyproject.toml
…

User question: <user_prompt>

Write a concise markdown review:
## What this repository appears to be
## Notable observations (structure, language(s), tests, docs)
## Concerns or open questions
## Suggested follow-ups

Stay grounded in the listing above. Do not invent files that are not
present. If the evidence is thin for any heading, say so briefly.
```

## Run artifacts

Every call to `run_repo_review` writes four files under `runs/claw/{run_id}/`:

- `prompt.txt` — the rendered prompt actually sent to agent.exe
- `stdout.txt` — raw stdout, untruncated
- `stderr.txt` — raw stderr
- `run.json` — the serialized `ClawRun` (status, latency, files_scanned, files_read, warnings, error)

`runs/` is gitignored (see `.gitignore` line 28).

## Permission profiles

Two profiles exist; only `READ_ONLY` is the default and used by the integrated `CodeAgent`:

| profile | flag | use |
|---|---|---|
| `READ_ONLY` (default) | `--permission-mode deny` | Standard repo review. Agent cannot call tools. |
| `PLAN` | `--permission-mode plan` | Planning-only mode; surfaces what the agent *would* do without doing it. Available via `POST /api/clawbridge/review` if explicitly selected. |

`workspace-write`, `shell-enabled`, and `network-enabled` are intentionally **not exposed in the MVP**. If you need them, call `agent.exe` directly in a real terminal.

## Calling it

Direct:

```
POST /api/clawbridge/review
{
  "workspace_path": "C:\\Users\\you\\some\\repo",
  "prompt": "Review this repo, focus on the FastAPI surface.",
  "permission_profile": "read_only",
  "timeout_s": 120
}
```

Through the agent runtime (preferred — engages it as a graph node):

```
POST /api/agents/run
{
  "graph_id": "<graph_id from /api/task-graph/build>",
  "workspace_path": "C:\\Users\\you\\some\\repo"
}
```

`CodeAgent` is only listed in the `repo_review` task graph template, so unless the intent classifier picked that intent, the agent will skip naturally and the rest of the pipeline runs without it.
