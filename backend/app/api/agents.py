from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.manager import default_manager
from app.runtime import executor
from app.schemas.agent import AgentRun
from app.services import sqlite_store

router = APIRouter(prefix="/api/agents", tags=["agents"])


class RunRequest(BaseModel):
    graph_id: str
    workspace_path: str = ""


@router.post("/run", response_model=AgentRun)
def run(req: RunRequest) -> AgentRun:
    graph = sqlite_store.get_task_graph(req.graph_id)
    if not graph:
        raise HTTPException(404, f"TaskGraph not found: {req.graph_id}")
    intent = sqlite_store.get_intent(graph.intent_id)
    if not intent:
        raise HTTPException(404, f"Intent not found: {graph.intent_id}")
    observation = sqlite_store.get_observation(graph.observation_id)
    if not observation:
        raise HTTPException(404, f"Observation not found: {graph.observation_id}")

    agent_run = executor.execute(
        manager=default_manager(),
        graph=graph,
        observation=observation,
        intent=intent,
        user_prompt=intent.user_prompt,
        workspace_path=req.workspace_path,
    )
    sqlite_store.save_agent_run(agent_run)
    return agent_run


@router.get("/runs/{run_id}", response_model=AgentRun)
def get_run(run_id: str) -> AgentRun:
    run = sqlite_store.get_agent_run(run_id)
    if not run:
        raise HTTPException(404, f"AgentRun not found: {run_id}")
    return run
