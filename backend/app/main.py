from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyze as analyze_api
from app.api import upload as upload_api
from app.config import settings
from app.services.sqlite_store import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="ogma-optron", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_api.router)
app.include_router(analyze_api.router)


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
