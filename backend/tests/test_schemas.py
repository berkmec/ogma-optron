"""Schema roundtrip tests. Pure model code, no network."""

from __future__ import annotations

import uuid

from app.schemas.agent import AgentRun, AgentRunStatus, AgentTrace
from app.schemas.asset import VisualAsset
from app.schemas.chat import ChatMessage, ChatRole
from app.schemas.clawbridge import ClawPermissionProfile, ClawRun, ClawRunStatus
from app.schemas.intent import IntentKind, IntentResult
from app.schemas.observation import ImageType, VisualObservation
from app.schemas.report import Report
from app.schemas.task_graph import TaskGraph, TaskNode, TaskStatus


def _new_id() -> str:
    return str(uuid.uuid4())


def test_visual_asset_roundtrip() -> None:
    asset = VisualAsset(
        asset_id=_new_id(),
        filename="x.png",
        mime_type="image/png",
        width=100,
        height=50,
        size_bytes=1024,
        storage_path="uploads/x.png",
    )
    decoded = VisualAsset.model_validate_json(asset.model_dump_json())
    assert decoded == asset


def test_observation_roundtrip() -> None:
    obs = VisualObservation(
        observation_id=_new_id(),
        asset_id=_new_id(),
        image_type=ImageType.ERROR_SCREEN,
        ocr_text="ERROR foo",
        vision_description="An error screen",
    )
    decoded = VisualObservation.model_validate_json(obs.model_dump_json())
    assert decoded.image_type is ImageType.ERROR_SCREEN


def test_intent_result_roundtrip() -> None:
    intent = IntentResult(
        intent_id=_new_id(),
        asset_id=_new_id(),
        observation_id=_new_id(),
        primary_intent=IntentKind.ERROR_DEBUG,
        confidence=0.9,
    )
    decoded = IntentResult.model_validate_json(intent.model_dump_json())
    assert decoded.primary_intent is IntentKind.ERROR_DEBUG


def test_task_graph_roundtrip() -> None:
    node_a = TaskNode(
        task_id=_new_id(),
        task_type="extract_error_text",
        description="...",
        required_agent="VisualAnalyzerAgent",
    )
    node_b = TaskNode(
        task_id=_new_id(),
        task_type="draft_report",
        description="...",
        required_agent="ReportAgent",
        depends_on=[node_a.task_id],
        status=TaskStatus.PENDING,
    )
    graph = TaskGraph(
        graph_id=_new_id(),
        intent_id=_new_id(),
        asset_id=_new_id(),
        observation_id=_new_id(),
        intent_kind=IntentKind.ERROR_DEBUG,
        nodes=[node_a, node_b],
    )
    decoded = TaskGraph.model_validate_json(graph.model_dump_json())
    assert len(decoded.nodes) == 2
    assert decoded.nodes[1].depends_on == [node_a.task_id]


def test_report_roundtrip() -> None:
    report = Report(
        report_id=_new_id(),
        asset_id=_new_id(),
        observation_id=_new_id(),
        intent_id=_new_id(),
        graph_id=_new_id(),
        intent_kind=IntentKind.UI_HELP,
        title="UI Walkthrough",
        markdown="## What this screen is",
    )
    decoded = Report.model_validate_json(report.model_dump_json())
    assert decoded.title == "UI Walkthrough"


def test_agent_run_with_trace() -> None:
    trace = AgentTrace(
        task_id=_new_id(),
        task_type="extract_error_text",
        agent_name="VisualAnalyzerAgent",
        status=TaskStatus.DONE,
        output_summary="ok",
    )
    run = AgentRun(
        run_id=_new_id(),
        graph_id=_new_id(),
        intent_id=_new_id(),
        observation_id=_new_id(),
        asset_id=_new_id(),
        intent_kind=IntentKind.ERROR_DEBUG,
        status=AgentRunStatus.DONE,
        traces=[trace],
    )
    decoded = AgentRun.model_validate_json(run.model_dump_json())
    assert decoded.status is AgentRunStatus.DONE
    assert decoded.traces[0].status is TaskStatus.DONE


def test_clawrun_roundtrip() -> None:
    run = ClawRun(
        run_id=_new_id(),
        workspace_path=r"C:\some\path",
        prompt="review this",
        permission_profile=ClawPermissionProfile.READ_ONLY,
        status=ClawRunStatus.DONE,
        output="md",
    )
    decoded = ClawRun.model_validate_json(run.model_dump_json())
    assert decoded.permission_profile is ClawPermissionProfile.READ_ONLY
    assert decoded.status is ClawRunStatus.DONE


def test_chat_message_roles() -> None:
    user = ChatMessage(
        message_id=_new_id(),
        observation_id=_new_id(),
        role=ChatRole.USER,
        content="hi",
    )
    assert ChatMessage.model_validate_json(user.model_dump_json()).role is ChatRole.USER
