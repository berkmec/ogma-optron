from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.asset import VisualAsset
from app.schemas.observation import VisualObservation
from app.schemas.report import Report
from app.services import sqlite_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionSummary(BaseModel):
    asset: VisualAsset
    observation: VisualObservation | None = None
    latest_report: Report | None = None


@router.get("", response_model=list[SessionSummary])
def list_sessions(limit: int = 30) -> list[SessionSummary]:
    assets = sqlite_store.list_recent_assets(limit=max(1, min(limit, 100)))
    out: list[SessionSummary] = []
    for asset in assets:
        obs = sqlite_store.get_latest_observation_for_asset(asset.asset_id)
        report = None
        if obs is not None:
            report = sqlite_store.get_latest_report_for_observation(obs.observation_id)
        out.append(SessionSummary(asset=asset, observation=obs, latest_report=report))
    return out


@router.get("/{asset_id}", response_model=SessionSummary)
def get_session(asset_id: str) -> SessionSummary:
    asset = sqlite_store.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, f"Asset not found: {asset_id}")
    obs = sqlite_store.get_latest_observation_for_asset(asset_id)
    report = None
    if obs is not None:
        report = sqlite_store.get_latest_report_for_observation(obs.observation_id)
    return SessionSummary(asset=asset, observation=obs, latest_report=report)
