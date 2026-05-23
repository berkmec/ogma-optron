"""SQLite persistence for assets and observations.

Tables store the full Pydantic model as a JSON blob to keep schema migration
costs near zero during week 2-3 churn.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import REPO_ROOT
from app.schemas.asset import VisualAsset
from app.schemas.observation import VisualObservation

DB_PATH = REPO_ROOT / "sessions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    asset_id   TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    asset_id       TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);
CREATE INDEX IF NOT EXISTS idx_observations_asset ON observations(asset_id);
"""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_asset(asset: VisualAsset) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO assets(asset_id, data, created_at) VALUES (?, ?, ?)",
            (asset.asset_id, asset.model_dump_json(), asset.created_at.isoformat()),
        )


def get_asset(asset_id: str) -> VisualAsset | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM assets WHERE asset_id = ?", (asset_id,)
        ).fetchone()
    return VisualAsset.model_validate_json(row["data"]) if row else None


def save_observation(observation: VisualObservation) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO observations(observation_id, asset_id, data, created_at)"
            " VALUES (?, ?, ?, ?)",
            (
                observation.observation_id,
                observation.asset_id,
                observation.model_dump_json(),
                observation.created_at.isoformat(),
            ),
        )


def get_observation(observation_id: str) -> VisualObservation | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM observations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()
    return VisualObservation.model_validate_json(row["data"]) if row else None


def list_observations_for_asset(asset_id: str) -> list[VisualObservation]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT data FROM observations WHERE asset_id = ? ORDER BY created_at DESC",
            (asset_id,),
        ).fetchall()
    return [VisualObservation.model_validate_json(r["data"]) for r in rows]
