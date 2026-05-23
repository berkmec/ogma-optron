"""Task graph templates: every intent yields a non-empty, acyclic DAG that
ends in a draft_report node."""

from __future__ import annotations

import pytest

from app.runtime.task_graph_templates import build_nodes_for
from app.schemas.intent import IntentKind


@pytest.mark.parametrize(
    "intent",
    [IntentKind.ERROR_DEBUG, IntentKind.REPO_REVIEW, IntentKind.UI_HELP, IntentKind.UNKNOWN],
)
def test_each_template_ends_in_report(intent: IntentKind) -> None:
    nodes = build_nodes_for(intent)
    assert nodes, f"{intent} has no nodes"
    assert nodes[-1].task_type == "draft_report"
    assert nodes[-1].required_agent == "ReportAgent"


@pytest.mark.parametrize(
    "intent",
    [IntentKind.ERROR_DEBUG, IntentKind.REPO_REVIEW, IntentKind.UI_HELP, IntentKind.UNKNOWN],
)
def test_dependencies_reference_existing_nodes(intent: IntentKind) -> None:
    nodes = build_nodes_for(intent)
    ids = {n.task_id for n in nodes}
    for node in nodes:
        for dep in node.depends_on:
            assert dep in ids, f"node {node.task_type} depends on unknown {dep}"


def _has_cycle(nodes) -> bool:
    in_degree = {n.task_id: len(n.depends_on) for n in nodes}
    queue = [n.task_id for n in nodes if not n.depends_on]
    seen = 0
    while queue:
        tid = queue.pop(0)
        seen += 1
        for n in nodes:
            if tid in n.depends_on:
                in_degree[n.task_id] -= 1
                if in_degree[n.task_id] == 0:
                    queue.append(n.task_id)
    return seen != len(nodes)


@pytest.mark.parametrize(
    "intent",
    [IntentKind.ERROR_DEBUG, IntentKind.REPO_REVIEW, IntentKind.UI_HELP, IntentKind.UNKNOWN],
)
def test_template_is_acyclic(intent: IntentKind) -> None:
    nodes = build_nodes_for(intent)
    assert not _has_cycle(nodes)


def test_repo_review_includes_code_agent() -> None:
    nodes = build_nodes_for(IntentKind.REPO_REVIEW)
    agents = {n.required_agent for n in nodes}
    assert "CodeAgent" in agents


def test_error_debug_includes_planner() -> None:
    nodes = build_nodes_for(IntentKind.ERROR_DEBUG)
    agents = {n.required_agent for n in nodes}
    assert "PlannerAgent" in agents
    assert "VisualAnalyzerAgent" in agents
