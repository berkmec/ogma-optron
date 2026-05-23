from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="ogma-optron", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "vision_model": settings.vision_model,
        "openai_base_url": settings.openai_base_url,
        "hf_token_configured": bool(settings.hf_token),
        "agent_code_bin_set": bool(settings.agent_code_bin),
        "agent_code_model": settings.agent_code_model,
    }
