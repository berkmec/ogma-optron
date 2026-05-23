from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.report_agent import ReportAgent
from app.schemas.report import Report
from app.services import sqlite_store

router = APIRouter(prefix="/api/reports", tags=["reports"])


class GenerateRequest(BaseModel):
    graph_id: str


_agent: ReportAgent | None = None


def get_agent() -> ReportAgent:
    global _agent
    if _agent is None:
        _agent = ReportAgent()
    return _agent


@router.post("/generate", response_model=Report)
def generate(req: GenerateRequest) -> Report:
    graph = sqlite_store.get_task_graph(req.graph_id)
    if not graph:
        raise HTTPException(404, f"TaskGraph not found: {req.graph_id}")
    intent = sqlite_store.get_intent(graph.intent_id)
    if not intent:
        raise HTTPException(404, f"Intent not found: {graph.intent_id}")
    observation = sqlite_store.get_observation(graph.observation_id)
    if not observation:
        raise HTTPException(404, f"Observation not found: {graph.observation_id}")

    result = get_agent().draft(observation, intent, graph)

    report = Report(
        report_id=str(uuid.uuid4()),
        asset_id=graph.asset_id,
        observation_id=graph.observation_id,
        intent_id=graph.intent_id,
        graph_id=graph.graph_id,
        intent_kind=graph.intent_kind,
        title=result["title"],
        markdown=result["markdown"],
        model_used=result["model_used"],
        latency_ms=result["latency_ms"],
    )
    sqlite_store.save_report(report)
    return report


@router.get("/{report_id}", response_model=Report)
def get_report(report_id: str) -> Report:
    report = sqlite_store.get_report(report_id)
    if not report:
        raise HTTPException(404, f"Report not found: {report_id}")
    return report
