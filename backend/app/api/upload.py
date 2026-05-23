from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.schemas.asset import VisualAsset
from app.services import file_store, sqlite_store

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/upload", response_model=VisualAsset)
async def upload_asset(file: Annotated[UploadFile, File()]) -> VisualAsset:
    asset = await file_store.save_upload(file)
    sqlite_store.save_asset(asset)
    return asset


@router.get("/{asset_id}", response_model=VisualAsset)
def get_asset(asset_id: str) -> VisualAsset:
    from fastapi import HTTPException

    asset = sqlite_store.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, f"Asset not found: {asset_id}")
    return asset
