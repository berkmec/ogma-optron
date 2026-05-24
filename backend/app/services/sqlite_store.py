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
from app.schemas.chat import ChatMessage
from app.schemas.clawbridge import ClawRun
from app.schemas.intent import IntentResult
from app.schemas.observation import VisualObservation
from app.schemas.report import Report
from app.schemas.repo_index import RepoIndexInfo
from app.schemas.task_graph import TaskGraph
from app.schemas.workflow import WorkflowSession

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
CREATE TABLE IF NOT EXISTS claw_runs (
    run_id         TEXT PRIMARY KEY,
    workspace_path TEXT NOT NULL,
    status         TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claw_runs_status ON claw_runs(status);
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id     TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL,
    role           TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (observation_id) REFERENCES observations(observation_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_observation ON chat_messages(observation_id, created_at);
CREATE TABLE IF NOT EXISTS repo_indexes (
    index_id       TEXT PRIMARY KEY,
    workspace_path TEXT NOT NULL,
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_repo_indexes_workspace ON repo_indexes(workspace_path, created_at);
CREATE TABLE IF NOT EXISTS workflow_sessions (
    session_id     TEXT PRIMARY KEY,
    title          TEXT NOT NULL DEFAULT '',
    data           TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workflows_created ON workflow_sessions(created_at);
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


def save_claw_run(run: ClawRun) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO claw_runs"
            "(run_id, workspace_path, status, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.workspace_path,
                run.status.value,
                run.model_dump_json(),
                run.started_at.isoformat(),
            ),
        )


def get_claw_run(run_id: str) -> ClawRun | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM claw_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    return ClawRun.model_validate_json(row["data"]) if row else None


def save_chat_message(message: ChatMessage) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO chat_messages"
            "(message_id, observation_id, role, data, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                message.message_id,
                message.observation_id,
                message.role.value,
                message.model_dump_json(),
                message.created_at.isoformat(),
            ),
        )


def list_chat_messages(observation_id: str) -> list[ChatMessage]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT data FROM chat_messages WHERE observation_id = ? ORDER BY created_at ASC",
            (observation_id,),
        ).fetchall()
    return [ChatMessage.model_validate_json(r["data"]) for r in rows]


def list_recent_assets(limit: int = 30) -> list[VisualAsset]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT data FROM assets ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [VisualAsset.model_validate_json(r["data"]) for r in rows]


def get_latest_report_for_observation(observation_id: str) -> Report | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM reports WHERE observation_id = ?"
            " ORDER BY created_at DESC LIMIT 1",
            (observation_id,),
        ).fetchone()
    return Report.model_validate_json(row["data"]) if row else None


def save_repo_index(info: RepoIndexInfo) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO repo_indexes"
            "(index_id, workspace_path, data, created_at) VALUES (?, ?, ?, ?)",
            (
                info.index_id,
                info.workspace_path,
                info.model_dump_json(),
                info.created_at.isoformat(),
            ),
        )


def get_repo_index(index_id: str) -> RepoIndexInfo | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM repo_indexes WHERE index_id = ?", (index_id,)
        ).fetchone()
    return RepoIndexInfo.model_validate_json(row["data"]) if row else None


def save_workflow_session(session: WorkflowSession) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO workflow_sessions"
            "(session_id, title, data, created_at) VALUES (?, ?, ?, ?)",
            (
                session.session_id,
                session.title,
                session.model_dump_json(),
                session.created_at.isoformat(),
            ),
        )


def get_workflow_session(session_id: str) -> WorkflowSession | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM workflow_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return WorkflowSession.model_validate_json(row["data"]) if row else None


def list_workflow_sessions(limit: int = 30) -> list[WorkflowSession]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT data FROM workflow_sessions ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [WorkflowSession.model_validate_json(r["data"]) for r in rows]


def list_repo_indexes(workspace_path: str | None = None) -> list[RepoIndexInfo]:
    with connect() as conn:
        if workspace_path:
            rows = conn.execute(
                "SELECT data FROM repo_indexes WHERE workspace_path = ?"
                " ORDER BY created_at DESC",
                (workspace_path,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT data FROM repo_indexes ORDER BY created_at DESC"
            ).fetchall()
    return [RepoIndexInfo.model_validate_json(r["data"]) for r in rows]


def get_latest_observation_for_asset(asset_id: str) -> VisualObservation | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM observations WHERE asset_id = ?"
            " ORDER BY created_at DESC LIMIT 1",
            (asset_id,),
        ).fetchone()
    return VisualObservation.model_validate_json(row["data"]) if row else None
