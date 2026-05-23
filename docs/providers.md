# Providers: HF Inference Providers (router) + Qwen3-VL

ogma-optron talks to exactly one external service: the HuggingFace Inference Providers router (`https://router.huggingface.co/v1`). Same endpoint for the Python pipeline (vision, intent, planner, report, chat) and for the spawned `agent.exe` (claw).

## Why this provider

- **OpenAI-compatible.** Both the Python `openai` SDK and the upstream `agent-code` crate accept the router URL with a Bearer header.
- **Multi-backend.** The router transparently picks a serverless backend (Together / Hyperbolic / Nebius / Fireworks / …) for whichever model you call. We don't depend on any one provider.
- **One token.** A single fine-grained `HF_TOKEN` covers every call. The same token in `.env` powers the FastAPI backend and is forwarded to `agent.exe` as `AGENT_CODE_API_KEY`.

## Token requirements

A standard "Read" token does **not** work — the router refuses with:

```
This authentication method does not have sufficient permissions to call
Inference Providers on behalf of user <name>
```

You need a *fine-grained* token (https://huggingface.co/settings/tokens) with **"Make calls to Inference Providers"** permission checked. Plus your account needs Inference Providers enabled in billing (free credit is usually enough for development).

## Why this model

`Qwen/Qwen3-VL-30B-A3B-Instruct`. The history:

| candidate | outcome |
|---|---|
| `Qwen/Qwen2-VL-7B-Instruct` | Not present in the router catalog. (Was in the original plan; reality disagreed.) |
| `Qwen/Qwen3-VL-8B-Instruct` | Worked for a day, then Together moved it to non-serverless and demanded a dedicated endpoint. HTTP 500 with `model_not_available`. |
| `Qwen/Qwen2.5-VL-72B-Instruct` | Works, but misnamed a red square as "pink" in our probe. |
| `Qwen/Qwen3-VL-30B-A3B-Instruct` | **Chosen.** MoE (30 B total, ~3 B active) so latency stays similar to the 8 B; correctly identifies the test color where the 72 B does not. |
| `Qwen/Qwen3-VL-235B-A22B-Instruct` | `invalid_request_error`. |

If the chosen model also goes non-serverless someday, swap a single line:

```
# .env
VISION_MODEL=Qwen/Qwen2.5-VL-72B-Instruct   # fallback that has been observed working
AGENT_CODE_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```

Restart uvicorn, re-run `scripts/run_eval.py` to confirm intent + image_type accuracy stayed acceptable, commit the swap.

## Environment variables

```
HF_TOKEN=hf_...                           # used by Python SDK
VISION_MODEL=Qwen/Qwen3-VL-30B-A3B-Instruct

OPENAI_BASE_URL=https://router.huggingface.co/v1
                                          # used by Python SDK as `base_url`

AGENT_CODE_BIN=C:\Users\<you>\.cargo\bin\agent.exe
AGENT_CODE_API_BASE_URL=https://router.huggingface.co/v1
AGENT_CODE_API_KEY=hf_...                 # same value as HF_TOKEN, just a different env name
AGENT_CODE_MODEL=Qwen/Qwen3-VL-30B-A3B-Instruct
```

**Important:** `agent.exe` does not pick up `OPENAI_BASE_URL` / `OPENAI_API_KEY`. It has its own env names (`AGENT_CODE_API_BASE_URL`, etc.). The wrapper injects them per subprocess in `backend/app/clawbridge/wrapper.py`.

## Adding another provider

The current `VisionProvider` abstraction is in `backend/app/providers/base.py`. A new implementation needs:

```python
class MyProvider(VisionProvider):
    def analyze(self, image_path: Path, prompt: str = "") -> VisionAnalysisResult:
        ...
```

…and a registration site (currently the provider is hard-wired in `backend/app/api/analyze.py`'s `get_provider()`). Future work, not in the 2-month MVP.
