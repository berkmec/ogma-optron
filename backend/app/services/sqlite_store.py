"""SQLite persistence for assets and observations.

Tables store the full Pydantic model as a JSON blob to keep schema migration
costs near zero during week 2-3 churn.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import REPO_ROOT
from app.schemas.agent import AgentRun
from app.schemas.asset import VisualAsset
from app.schemas.intent import IntentResult
from app.schemas.observation import VisualObservation
from app.schemas.report import Report
from app.schemas.task_graph import TaskGraph

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
CREATE TABLE IF NOT EXISTS intents (
    intent_id      TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    asset_id       TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (observation_id) REFERENCES observations(observation_id),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);
CREATE INDEX IF NOT EXISTS idx_intents_observation ON intents(observation_id);
CREATE TABLE IF NOT EXISTS task_graphs (
    graph_id       TEXT PRIMARY KEY,
    intent_id      TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    asset_id       TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (intent_id) REFERENCES intents(intent_id)
);
CREATE INDEX IF NOT EXISTS idx_graphs_intent ON task_graphs(intent_id);
CREATE TABLE IF NOT EXISTS reports (
    report_id      TEXT PRIMARY KEY,
    graph_id       TEXT NOT NULL,
    intent_id      TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    asset_id       TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (graph_id) REFERENCES task_graphs(graph_id)
);
CREATE INDEX IF NOT EXISTS idx_reports_graph ON reports(graph_id);
CREATE TABLE IF NOT EXISTS agent_runs (
    run_id         TEXT PRIMARY KEY,
    graph_id       TEXT NOT NULL,
    intent_id      TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    asset_id       TEXT NOT NULL,
    status         TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (graph_id) REFERENCES task_graphs(graph_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_graph ON agent_runs(graph_id);
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


def save_intent(intent: IntentResult) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO intents(intent_id, observation_id, asset_id, data, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                intent.intent_id,
                intent.observation_id,
                intent.asset_id,
                intent.model_dump_json(),
                intent.created_at.isoformat(),
            ),
        )


def get_intent(intent_id: str) -> IntentResult | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM intents WHERE intent_id = ?", (intent_id,)
        ).fetchone()
    return IntentResult.model_validate_json(row["data"]) if row else None


def save_task_graph(graph: TaskGraph) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO task_graphs"
            "(graph_id, intent_id, observation_id, asset_id, data, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                graph.graph_id,
                graph.intent_id,
                graph.observation_id,
                graph.asset_id,
                graph.model_dump_json(),
                graph.created_at.isoformat(),
            ),
        )


def get_task_graph(graph_id: str) -> TaskGraph | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM task_graphs WHERE graph_id = ?", (graph_id,)
        ).fetchone()
    return TaskGraph.model_validate_json(row["data"]) if row else None


def save_report(report: Report) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO reports"
            "(report_id, graph_id, intent_id, observation_id, asset_id, data, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                report.report_id,
                report.graph_id,
                report.intent_id,
                report.observation_id,
                report.asset_id,
                report.model_dump_json(),
                report.created_at.isoformat(),
            ),
        )


def get_report(report_id: str) -> Report | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM reports WHERE report_id = ?", (report_id,)
        ).fetchone()
    return Report.model_validate_json(row["data"]) if row else None


def save_agent_run(run: AgentRun) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO agent_runs"
            "(run_id, graph_id, intent_id, observation_id, asset_id, status, data, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.graph_id,
                run.intent_id,
                run.observation_id,
                run.asset_id,
                run.status.value,
                run.model_dump_json(),
                run.created_at.isoformat(),
            ),
        )


def get_agent_run(run_id: str) -> AgentRun | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM agent_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    return AgentRun.model_validate_json(row["data"]) if row else None
