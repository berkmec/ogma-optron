# Security model

This is a personal-portfolio MVP that runs on localhost. It does not target production deployment, multi-tenancy, or hostile networks. Within that scope, the surface is small and the guard rails are explicit.

## Trust boundaries

| boundary | who is trusted | what crosses it |
|---|---|---|
| browser ↔ Vite | the local user | screenshots, prompts |
| Vite ↔ FastAPI | proxied, localhost only | HTTP JSON / multipart |
| FastAPI ↔ HF router | HF token over HTTPS | image data, OCR text, intent prompts |
| FastAPI ↔ agent.exe | subprocess only, no network in either direction | rendered prompt over stdin args |

The backend binds to `127.0.0.1`. Do not expose it to the network without adding auth.

## Upload guard rails

`backend/app/services/file_store.py`:

- MIME type whitelist: png / jpeg / webp / gif. Anything else → 415.
- Extension whitelist: `.png .jpg .jpeg .webp .gif`.
- Size cap: 10 MB. Bigger → 413.
- Empty uploads → 400.
- `PIL.Image.verify()` is called on the bytes; broken / non-image content → 400.
- Filenames are sanitized to `[A-Za-z0-9._-]` and capped at 128 chars. Path separators are dropped.
- Asset id is a server-side UUID; the on-disk filename uses `{asset_id}{ext}`, not the user's filename.
- `asset_full_path` resolves a stored path inside `uploads/` and refuses any path that escapes `UPLOAD_DIR` (path traversal → 403).

## Token handling

- `HF_TOKEN` lives in `.env` only. `.env` is gitignored (line 16).
- The token is never echoed in responses; `/health` only reports whether it is configured.
- The same token is passed to agent.exe over command-line args (`--api-key`). That is in-process; nobody else on the box sees the argv unless they own the same user.

## Prompt injection

OCR text and the user prompt both feed into Qwen prompts. We cannot prevent prompt injection from a hostile screenshot, but:

- The system prompts are explicit ("do not invent files / errors / line numbers that are not present in the context").
- After a real regression in week 6 (the model substituted a generic `Cannot read property of undefined` for the actual `ConnectionRefusedError`), the chat system prompt was hardened to demand verbatim quoting. See [chat_service.py](../backend/app/services/chat_service.py).
- Reports and chat turns are persisted; if a malicious screenshot ever produces bad output, the prompt + response are still on disk for inspection.

## Code agent (agent.exe)

See [`clawbridge.md`](clawbridge.md). Summary:

- `--permission-mode deny` blocks every tool call.
- Workspace contents are scanned in Python and injected into the prompt; the subprocess cannot read your filesystem on its own.
- Workspace path is validated and refused for system directories (`C:\Windows`, `C:\Program Files`, …).
- Output is truncated to 20 000 chars; the run is capped at 120 s; everything is persisted under `runs/claw/{run_id}/`.

The path-block was a real bug (raise was being swallowed) — caught and fixed in week 7 with a regression test (`tests/test_clawbridge_safety.py`).

## What this doesn't protect against

- A malicious local user — they have the file system, the .env, and the cargo binary anyway.
- A compromised HF account — token revocation is the answer, not extra guarding here.
- A truly adversarial screenshot that exploits Qwen-VL behavior — we surface warnings when the model is uncertain, but we don't sandbox the model itself.
- DoS — rate limiting and concurrency caps are out of scope for the MVP.

## Reporting

This is a personal project. Open an issue or DM the author. Do not file CVEs.
