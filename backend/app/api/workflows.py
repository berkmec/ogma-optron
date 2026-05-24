from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.workflow import WorkflowSession
from app.services import sqlite_store
from app.services.workflow_service import synthesise_workflow

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class CreateWorkflowRequest(BaseModel):
    observation_ids: list[str]
    title: str = ""
    user_prompt: str = ""
    synthesise: bool = True


@router.post("", response_model=WorkflowSession)
def create(req: CreateWorkflowRequest) -> WorkflowSession:
    if not req.observation_ids:
        raise HTTPException(400, "observation_ids must not be empty")

    observations = []
    for obs_id in req.observation_ids:
        obs = sqlite_store.get_observation(obs_id)
        if obs is None:
            raise HTTPException(404, f"observation not found: {obs_id}")
        observations.append(obs)

    session = WorkflowSession(
        session_id=str(uuid.uuid4()),
        title=req.title,
        observation_ids=req.observation_ids,
        user_prompt=req.user_prompt,
    )

    if req.synthesise:
        result = synthesise_workflow(observations, req.user_prompt)
        session.synthesis_markdown = result["markdown"]
        session.model_used = result["model_used"]
        session.latency_ms = result["latency_ms"]

    sqlite_store.save_workflow_session(session)
    return session


class SynthesiseRequest(BaseModel):
    user_prompt: str = ""


@router.post("/{session_id}/synthesise", response_model=WorkflowSession)
def synthesise(session_id: str, req: SynthesiseRequest) -> WorkflowSession:
    session = sqlite_store.get_workflow_session(session_id)
    if session is None:
        raise HTTPException(404, f"workflow not found: {session_id}")

    observations = []
    for obs_id in session.observation_ids:
        obs = sqlite_store.get_observation(obs_id)
        if obs is None:
            raise HTTPException(
                404, f"observation referenced by workflow no longer exists: {obs_id}"
            )
        observations.append(obs)

    result = synthesise_workflow(observations, req.user_prompt or session.user_prompt)
    session.synthesis_markdown = result["markdown"]
    session.model_used = result["model_used"]
    session.latency_ms = result["latency_ms"]
    if req.user_prompt:
        session.user_prompt = req.user_prompt
    sqlite_store.save_workflow_session(session)
    return session


@router.get("/{session_id}", response_model=WorkflowSession)
def get(session_id: str) -> WorkflowSession:
    session = sqlite_store.get_workflow_session(session_id)
    if session is None:
        raise HTTPException(404, f"workflow not found: {session_id}")
    return session


@router.get("", response_model=list[WorkflowSession])
def list_workflows(limit: int = 30) -> list[WorkflowSession]:
    return sqlite_store.list_workflow_sessions(limit=limit)
