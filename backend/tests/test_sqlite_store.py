"""SQLite store: schema initialization + roundtrip for each entity.

Uses tmp_path to redirect DB_PATH so we don't touch the dev sessions.db.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.schemas.agent import AgentRun, AgentRunStatus, AgentTrace
from app.schemas.asset import VisualAsset
from app.schemas.chat import ChatMessage, ChatRole
from app.schemas.clawbridge import ClawPermissionProfile, ClawRun, ClawRunStatus
from app.schemas.intent import IntentKind, IntentResult
from app.schemas.observation import ImageType, VisualObservation
from app.schemas.report import Report
from app.schemas.task_graph import TaskGraph, TaskNode


@pytest.fixture
def store(tmp_path: Path, monkeypatch):
    from app.services import sqlite_store

    monkeypatch.setattr(sqlite_store, "DB_PATH", tmp_path / "test_sessions.db")
    sqlite_store.init_db()
    return sqlite_store


def _id() -> str:
    return str(uuid.uuid4())


def test_asset_roundtrip(store) -> None:
    asset = VisualAsset(
        asset_id=_id(),
        filename="x.png",
        mime_type="image/png",
        width=10,
        height=10,
        size_bytes=100,
        storage_path="uploads/x.png",
    )
    store.save_asset(asset)
    fetched = store.get_asset(asset.asset_id)
    assert fetched is not None
    assert fetched.asset_id == asset.asset_id


def test_observation_and_listing(store) -> None:
    asset_id = _id()
    obs1 = VisualObservation(
        observation_id=_id(),
        asset_id=asset_id,
        image_type=ImageType.ERROR_SCREEN,
    )
    obs2 = VisualObservation(
        observation_id=_id(),
        asset_id=asset_id,
        image_type=ImageType.OTHER,
    )
    store.save_observation(obs1)
    store.save_observation(obs2)
    listed = store.list_observations_for_asset(asset_id)
    assert {o.observation_id for o in listed} == {obs1.observation_id, obs2.observation_id}


def test_intent_and_report_chain(store) -> None:
    obs_id = _id()
    intent = IntentResult(
        intent_id=_id(),
        asset_id=_id(),
        observation_id=obs_id,
        primary_intent=IntentKind.ERROR_DEBUG,
    )
    store.save_intent(intent)
    assert store.get_intent(intent.intent_id) is not None

    report = Report(
        report_id=_id(),
        asset_id=intent.asset_id,
        observation_id=obs_id,
        intent_id=intent.intent_id,
        graph_id=_id(),
        intent_kind=intent.primary_intent,
        title="Debug Report",
        markdown="# x",
    )
    store.save_report(report)
    assert store.get_latest_report_for_observation(obs_id) is not None


def test_task_graph_and_agent_run(store) -> None:
    node = TaskNode(
        task_id=_id(),
        task_type="extract",
        description="x",
        required_agent="VisualAnalyzerAgent",
    )
    graph = TaskGraph(
        graph_id=_id(),
        intent_id=_id(),
        asset_id=_id(),
        observation_id=_id(),
        intent_kind=IntentKind.ERROR_DEBUG,
        nodes=[node],
    )
    store.save_task_graph(graph)
    assert store.get_task_graph(graph.graph_id) is not None

    run = AgentRun(
        run_id=_id(),
        graph_id=graph.graph_id,
        intent_id=graph.intent_id,
        observation_id=graph.observation_id,
        asset_id=graph.asset_id,
        intent_kind=IntentKind.ERROR_DEBUG,
        status=AgentRunStatus.DONE,
        traces=[
            AgentTrace(
                task_id=node.task_id,
                task_type=node.task_type,
                agent_name=node.required_agent,
                status="done",
                output_summary="ok",
            ),
        ],
    )
    store.save_agent_run(run)
    assert store.get_agent_run(run.run_id) is not None


def test_chat_history_order(store) -> None:
    obs_id = _id()
    msgs = [
        ChatMessage(
            message_id=_id(),
            observation_id=obs_id,
            role=ChatRole.USER,
            content="q1",
        ),
        ChatMessage(
            message_id=_id(),
            observation_id=obs_id,
            role=ChatRole.ASSISTANT,
            content="a1",
        ),
    ]
    for m in msgs:
        store.save_chat_message(m)
    history = store.list_chat_messages(obs_id)
    assert [m.content for m in history] == ["q1", "a1"]


def test_claw_run_roundtrip(store) -> None:
    run = ClawRun(
        run_id=_id(),
        workspace_path="C:/tmp/x",
        prompt="review",
        permission_profile=ClawPermissionProfile.READ_ONLY,
        status=ClawRunStatus.DONE,
        output="md",
    )
    store.save_claw_run(run)
    fetched = store.get_claw_run(run.run_id)
    assert fetched is not None
    assert fetched.permission_profile is ClawPermissionProfile.READ_ONLY
