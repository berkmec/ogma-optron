# Git-aware code review

`optron review` and `/api/clawbridge/review` now inject the workspace's **branch / diff / recent commits / uncommitted files** into the review prompt. Without this, agent.exe could only see "the repo as a static snapshot"; with it, the model sees *what is actually changing on this branch*.

## How it works

```text
ClawBridge prompt
  ├── workspace listing (read-only scanner)
  ├── Git context block         ← NEW
  │     branch, head_sha, base_ref, ahead/behind,
  │     uncommitted files,
  │     recent commits (max 20),
  │     diff --stat,
  │     diff (max 30,000 chars, truncated flag if larger)
  ├── Semantic-search excerpts  (from repo_index, if built)
  └── Key file contents         (README, pyproject.toml, package.json, ...)
```

If the workspace is **not** a git repo, the Git context block is empty and the prompt looks exactly like the M1.2 version.

## Base ref resolution

| order | candidate |
|---|---|
| 1 | the value passed via `--base` / `git_base_ref` |
| 2 | `origin/main` |
| 3 | `origin/master` |
| 4 | `main` |
| 5 | `master` |
| 6 | `HEAD~5` (last-resort, so even an isolated checkout still produces a diff) |

The first one that resolves with `git rev-parse` wins.

## CLI

```bash
# Default: best-guess base (origin/main → main → HEAD~5)
optron review -w .

# Explicit base
optron review -w . --base origin/main
optron review -w . -b HEAD~10

# Combine with the semantic index built in M1.2
optron index  -w .
optron review -w . -b origin/main -p "Focus on the new error-handling logic."
```

## Bounds

| | value |
|---|---|
| max diff chars | 30,000 (truncation flag set in `warnings` if exceeded) |
| max log entries | 20 |
| `git` subprocess timeout | 15 s (30 s for `git diff`) |
| read-only? | yes — no `fetch`, no `checkout`, no `reset`, no `add` |

## Safety

`backend/app/gitctx/diff.py` only calls `git rev-parse`, `git status --porcelain`, `git log`, and `git diff`. It never mutates the repository. Every call is bounded by a timeout. If `git` is not on PATH, `is_git_repo()` returns `False` and the prompt block stays empty.
