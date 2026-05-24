# `optron` CLI

A thin terminal layer over the same handlers the HTTP routers use. No uvicorn required — the CLI runs the full pipeline in-process. Useful for shell scripting, CI smoke tests, and quickly trying a screenshot without booting the React frontend.

## Install

The CLI is shipped inside the `backend/` package as a console script.

```bash
# From the repo root
pip install -e backend
optron --version          # optron 0.2.0
```

After install, `optron` is on PATH for the active Python environment. To use it without installing, you can always run `python -m app.cli <subcommand>` from `backend/` instead — the entry points are identical.

## Subcommands

```text
optron health
optron analyze <image>      [-p PROMPT] [-w WORKSPACE] [--json]
optron review  -w WORKSPACE [-p PROMPT] [--timeout SECONDS] [--json]
optron chat    <observation_id> "your question"  [--json]
optron eval    [-- extra args passed to scripts/run_eval.py]
```

### `optron health`

Print the resolved configuration as JSON. Confirms `HF_TOKEN` is loaded, which model is selected, and whether the `agent.exe` binary is on disk.

```bash
$ optron health
{
  "vision_model": "Qwen/Qwen3-VL-30B-A3B-Instruct",
  "openai_base_url": "https://router.huggingface.co/v1",
  "hf_token_configured": true,
  "agent_code_bin_set": true,
  "agent_code_bin": "C:\\Users\\pc\\.cargo\\bin\\agent.exe",
  "agent_code_model": "Qwen/Qwen3-VL-30B-A3B-Instruct"
}
```

### `optron analyze <image>`

Run the full pipeline on a single image: **upload → vision → intent → task graph → agents → report**. The asset, observation, intent, graph, and agent run are persisted to SQLite, so you can chain a `chat` call against the resulting `observation_id`.

```bash
optron analyze ./error.png -p "What does this error mean?"
```

Human-readable output (default):

```
asset:       48728ac3...  720x360  6051B  (error.png)
image_type:  error_screen
intent:      error_debug  (conf 0.95)
reasoning:   The user provides an error screen ...
graph:       4 nodes
  - extract_error_text        VisualAnalyzerAgent
  - classify_error_cause      PlannerAgent
  - suggest_debug_steps       PlannerAgent
  - draft_report              ReportAgent

agent run:   done  total 37948ms  failed=0  skipped=0
  [done   ]  extract_error_text        VisualAnalyzerAgent     1748ms
  [done   ]  classify_error_cause      PlannerAgent            1747ms
  [done   ]  suggest_debug_steps       PlannerAgent            2521ms
  [done   ]  draft_report              ReportAgent            31931ms

========================================================================
## Summary
...
========================================================================
```

JSON output (`--json`) returns every step's full pydantic dump in one document, suitable for piping into `jq`.

`--workspace PATH` enables `CodeAgent` (the read-only `agent.exe` subprocess) when the intent classifier picks `repo_review`. Without it, `CodeAgent` is skipped with an explanatory note.

### `optron review -w PATH`

Direct entry to ClawBridge — skip the screenshot, just review a local repository:

```bash
optron review -w ./my-project -p "Focus on test coverage and CI."
```

Runs `agent.exe` with `--permission-mode deny` (no tool calls); workspace files are scanned in Python and injected into the prompt instead. Exit code is `0` on success, `1` on `failed`/`timeout`, `2` on validation errors.

### `optron chat <observation_id> "question"`

Follow up on a previous `analyze` run. The chat service loads the observation, the most recent report, and prior chat turns from SQLite.

```bash
optron chat 48728ac3-... "What was the actual hostname in that error?"
```

### `optron eval`

Run the 10-case synthetic eval suite (`scripts/run_eval.py`). Anything after a literal `--` is forwarded as extra args to the eval script.

```bash
optron eval
optron eval -- --json
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Pipeline / runtime failure (HF error, agent.exe failed, etc.) |
| 2 | Validation error (missing image, missing workspace) |
| 130 | Interrupted (Ctrl-C) |

## SQLite location

All commands share the project's `sessions.db` (see `app.config.REPO_ROOT`). Running the CLI initializes the schema if needed; running uvicorn alongside is fine — they read the same database.
