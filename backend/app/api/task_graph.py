from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime.task_graph_templates import build_nodes_for
from app.schemas.task_graph import TaskGraph
from app.services import sqlite_store

router = APIRouter(prefix="/api/task-graph", tags=["task-graph"])


class BuildRequest(BaseModel):
    intent_id: str


@router.post("/build", response_model=TaskGraph)
def build(req: BuildRequest) -> TaskGraph:
    intent = sqlite_store.get_intent(req.intent_id)
    if not intent:
        raise HTTPException(404, f"Intent not found: {req.intent_id}")

    nodes = build_nodes_for(intent.primary_intent)
    graph = TaskGraph(
        graph_id=str(uuid.uuid4()),
        intent_id=intent.intent_id,
        asset_id=intent.asset_id,
        observation_id=intent.observation_id,
        intent_kind=intent.primary_intent,
        nodes=nodes,
    )
    sqlite_store.save_task_graph(graph)
    return graph


@router.get("/{graph_id}", response_model=TaskGraph)
def get_graph(graph_id: str) -> TaskGraph:
    graph = sqlite_store.get_task_graph(graph_id)
    if not graph:
        raise HTTPException(404, f"TaskGraph not found: {graph_id}")
    return graph
