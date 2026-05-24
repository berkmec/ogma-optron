"""Workflow synthesis tests.

The Qwen call inside workflow_service.synthesise_workflow() is mocked so
pytest stays offline. We verify ordering, schema persistence, and the
prompt's structural rules (system prompt + per-observation block) by
inspecting the mock's recorded args.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from app.api import workflows as workflows_api
from app.schemas.observation import ImageType, VisualObservation
from app.schemas.workflow import WorkflowSession
from app.services import sqlite_store, workflow_service


def _make_observation(text: str, image_type: ImageType = ImageType.ERROR_SCREEN) -> VisualObservation:
    return VisualObservation(
        observation_id=str(uuid.uuid4()),
        asset_id=str(uuid.uuid4()),
        image_type=image_type,
        ocr_text=text,
        vision_description=f"description of: {text[:40]}",
        confidence=0.8,
        warnings=[],
        model_used="mock-model",
        latency_ms=10,
        created_at=datetime.now(timezone.utc),
    )


class _FakeChatChoiceMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChatChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeChatChoiceMessage(content)


class _FakeChatResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChatChoice(content)]


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeChatResponse:
        self.calls.append(kwargs)
        return _FakeChatResponse("## What this flow is\nmocked synthesis\n")


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self, *_, **__) -> None:
        self.chat = _FakeChat()


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> _FakeClient:
    instances: list[_FakeClient] = []

    def factory(*args: Any, **kwargs: Any) -> _FakeClient:
        client = _FakeClient(*args, **kwargs)
        instances.append(client)
        return client

    monkeypatch.setattr("app.services.workflow_service.OpenAI", factory)
    # Force the settings to look configured so synthesise_workflow doesn't bail.
    monkeypatch.setattr("app.services.workflow_service.settings.hf_token", "hf_test_token", raising=False)

    yield instances  # type: ignore[misc]


def test_synthesise_workflow_empty_returns_empty() -> None:
    result = workflow_service.synthesise_workflow([])
    assert result["markdown"] == ""
    assert result["latency_ms"] == 0


def test_synthesise_workflow_calls_model_with_ordered_blocks(
    fake_openai: list[_FakeClient],
) -> None:
    obs = [
        _make_observation("ERROR: NullPointerException"),
        _make_observation("Retry button visible", ImageType.UI_DASHBOARD),
        _make_observation("Stack trace at main.py:42"),
    ]
    result = workflow_service.synthesise_workflow(obs, user_prompt="bug report")

    assert "mocked synthesis" in result["markdown"]
    assert len(fake_openai) == 1
    call = fake_openai[0].chat.completions.calls[0]
    user_message = call["messages"][-1]["content"]
    # observations appear in order
    assert "Step 1" in user_message and "Step 2" in user_message and "Step 3" in user_message
    assert "NullPointerException" in user_message
    assert "Retry button visible" in user_message
    assert "Stack trace at main.py:42" in user_message
    # system prompt structure is enforced
    system = call["messages"][0]["content"]
    assert "## What this flow is" in system
    assert "## Where it broke or what's missing" in system


def test_workflow_api_create_persists_session(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    fake_openai: list[_FakeClient],
) -> None:
    # Isolate the test DB to tmp_path.
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr("app.services.sqlite_store.DB_PATH", db_path)
    sqlite_store.init_db()

    obs_one = _make_observation("first screen")
    obs_two = _make_observation("second screen")
    sqlite_store.save_observation(obs_one)
    sqlite_store.save_observation(obs_two)

    request = workflows_api.CreateWorkflowRequest(
        observation_ids=[obs_one.observation_id, obs_two.observation_id],
        title="bug-2026-05",
        user_prompt="track the failure",
        synthesise=True,
    )
    session = workflows_api.create(request)
    assert isinstance(session, WorkflowSession)
    assert session.title == "bug-2026-05"
    assert session.synthesis_markdown.startswith("## What this flow is")

    # Reload from disk to confirm persistence
    loaded = sqlite_store.get_workflow_session(session.session_id)
    assert loaded is not None
    assert loaded.observation_ids == [obs_one.observation_id, obs_two.observation_id]
    # And it appears in the listing
    assert any(s.session_id == session.session_id for s in sqlite_store.list_workflow_sessions())


def test_workflow_api_missing_observation_returns_404(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    fake_openai: list[_FakeClient],
) -> None:
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr("app.services.sqlite_store.DB_PATH", db_path)
    sqlite_store.init_db()

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        workflows_api.create(
            workflows_api.CreateWorkflowRequest(
                observation_ids=["does-not-exist"], synthesise=False
            )
        )
    assert excinfo.value.status_code == 404


def test_workflow_api_empty_observation_ids_returns_400(
    fake_openai: list[_FakeClient],
) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        workflows_api.create(
            workflows_api.CreateWorkflowRequest(observation_ids=[], synthesise=False)
        )
    assert excinfo.value.status_code == 400


def test_workflow_session_pydantic_round_trip() -> None:
    session = WorkflowSession(
        session_id="abc",
        title="t",
        observation_ids=["a", "b"],
        synthesis_markdown="## md",
        user_prompt="q",
        model_used="m",
        latency_ms=42,
    )
    payload = session.model_dump_json()
    parsed = json.loads(payload)
    assert parsed["observation_ids"] == ["a", "b"]
    assert WorkflowSession.model_validate_json(payload).latency_ms == 42
