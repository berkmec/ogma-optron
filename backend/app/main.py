from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agents as agents_api
from app.api import analyze as analyze_api
from app.api import chat as chat_api
from app.api import clawbridge as clawbridge_api
from app.api import intent as intent_api
from app.api import reports as reports_api
from app.api import repo_index as repo_index_api
from app.api import sessions as sessions_api
from app.api import task_graph as task_graph_api
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
app.include_router(intent_api.router)
app.include_router(task_graph_api.router)
app.include_router(reports_api.router)
app.include_router(agents_api.router)
app.include_router(clawbridge_api.router)
app.include_router(chat_api.router)
app.include_router(sessions_api.router)
app.include_router(repo_index_api.router)


def _health_payload() -> dict:
    return {
        "status": "ok",
        "vision_model": settings.vision_model,
        "openai_base_url": settings.openai_base_url,
        "hf_token_configured": bool(settings.hf_token),
        "agent_code_bin_set": bool(settings.agent_code_bin),
        "agent_code_model": settings.agent_code_model,
    }


@app.get("/health")
def health() -> dict:
    return _health_payload()


@app.get("/api/health")
def api_health() -> dict:
    return _health_payload()
