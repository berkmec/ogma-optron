from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.providers.hf_qwen_vl import HFQwenVLProvider
from app.schemas.observation import ImageType, VisualObservation
from app.services import file_store, sqlite_store
from app.vision.ocr import extract_text

router = APIRouter(prefix="/api/vision", tags=["vision"])


class AnalyzeRequest(BaseModel):
    asset_id: str
    prompt: str = ""


_provider: HFQwenVLProvider | None = None


def get_provider() -> HFQwenVLProvider:
    global _provider
    if _provider is None:
        _provider = HFQwenVLProvider()
    return _provider


@router.post("/analyze", response_model=VisualObservation)
def analyze(req: AnalyzeRequest) -> VisualObservation:
    asset = sqlite_store.get_asset(req.asset_id)
    if not asset:
        raise HTTPException(404, f"Asset not found: {req.asset_id}")

    image_path = file_store.asset_full_path(asset.storage_path)

    start = time.perf_counter()
    ocr_text = extract_text(image_path)
    provider = get_provider()
    result = provider.analyze(image_path, req.prompt)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    observation = VisualObservation(
        observation_id=str(uuid.uuid4()),
        asset_id=asset.asset_id,
        image_type=ImageType(result.image_type),
        ocr_text=ocr_text,
        vision_description=result.description,
        confidence=result.confidence,
        warnings=result.warnings,
        model_used=result.model_used,
        latency_ms=elapsed_ms,
    )
    sqlite_store.save_observation(observation)
    return observation


@router.get("/observations/{observation_id}", response_model=VisualObservation)
def get_observation(observation_id: str) -> VisualObservation:
    obs = sqlite_store.get_observation(observation_id)
    if not obs:
        raise HTTPException(404, f"Observation not found: {observation_id}")
    return obs
