from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.intent.classifier import IntentClassifier
from app.schemas.intent import IntentResult
from app.services import sqlite_store

router = APIRouter(prefix="/api/intent", tags=["intent"])


class ClassifyRequest(BaseModel):
    observation_id: str
    user_prompt: str = ""


_classifier: IntentClassifier | None = None


def get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


@router.post("/classify", response_model=IntentResult)
def classify(req: ClassifyRequest) -> IntentResult:
    observation = sqlite_store.get_observation(req.observation_id)
    if not observation:
        raise HTTPException(404, f"Observation not found: {req.observation_id}")

    result = get_classifier().classify(observation, req.user_prompt)

    intent = IntentResult(
        intent_id=str(uuid.uuid4()),
        asset_id=observation.asset_id,
        observation_id=observation.observation_id,
        primary_intent=result["primary_intent"],
        confidence=result["confidence"],
        reasoning=result["reasoning"],
        ambiguity=result["ambiguity"],
        suggested_next_step=result["suggested_next_step"],
        user_prompt=req.user_prompt,
        model_used=result["model_used"],
        latency_ms=result["latency_ms"],
    )
    sqlite_store.save_intent(intent)
    return intent


@router.get("/{intent_id}", response_model=IntentResult)
def get_intent(intent_id: str) -> IntentResult:
    intent = sqlite_store.get_intent(intent_id)
    if not intent:
        raise HTTPException(404, f"Intent not found: {intent_id}")
    return intent
