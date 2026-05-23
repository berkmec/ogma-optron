"""Hardcoded task-graph templates per intent.

A dynamic graph builder is out of scope for week 3. Each intent maps to a
fixed list of TaskNodes the runtime will execute in order. Week 4 wires
those nodes to real agents; this module is the contract between the two.
"""

from __future__ import annotations

import uuid

from app.schemas.intent import IntentKind
from app.schemas.task_graph import TaskNode

REPORT_AGENT = "ReportAgent"
PLANNER_AGENT = "PlannerAgent"
VISUAL_ANALYZER = "VisualAnalyzerAgent"
CODE_AGENT = "CodeAgent"  # ClawBridge surface, week 5


def _node(task_type: str, description: str, agent: str, depends_on: list[str]) -> TaskNode:
    return TaskNode(
        task_id=str(uuid.uuid4()),
        task_type=task_type,
        description=description,
        required_agent=agent,
        depends_on=depends_on,
    )


def error_debug_nodes() -> list[TaskNode]:
    extract = _node(
        "extract_error_text",
        "Pull the error message, stack frames, and any error code from OCR + observation.",
        VISUAL_ANALYZER,
        [],
    )
    classify = _node(
        "classify_error_cause",
        "Guess the likely root cause category (network, auth, null/undefined, type mismatch, dependency, etc.).",
        PLANNER_AGENT,
        [extract.task_id],
    )
    steps = _node(
        "suggest_debug_steps",
        "Produce 3-6 concrete next steps the user should try, ordered by leverage.",
        PLANNER_AGENT,
        [classify.task_id],
    )
    report = _node(
        "draft_report",
        "Compose a markdown debug report: summary, suspected cause, ordered steps, optional code snippets.",
        REPORT_AGENT,
        [steps.task_id],
    )
    return [extract, classify, steps, report]


def repo_review_nodes() -> list[TaskNode]:
    inspect = _node(
        "inspect_repo_view",
        "From the screenshot, identify the project name, primary language, visible files/dirs, and any signals about activity.",
        VISUAL_ANALYZER,
        [],
    )
    concerns = _node(
        "list_review_concerns",
        "List what a code reviewer would normally check: structure, tests, docs, dependencies, CI signals.",
        PLANNER_AGENT,
        [inspect.task_id],
    )
    code_agent = _node(
        "claw_repo_read",
        "OPTIONAL (week 5): hand the workspace to agent-code (claw) in read-only mode for deeper review.",
        CODE_AGENT,
        [concerns.task_id],
    )
    report = _node(
        "draft_report",
        "Compose a markdown repo review: high-level structure, observations, suggested follow-ups.",
        REPORT_AGENT,
        [concerns.task_id],
    )
    return [inspect, concerns, code_agent, report]


def ui_help_nodes() -> list[TaskNode]:
    identify = _node(
        "identify_screen",
        "Identify the screen's role (auth, form, dashboard, settings, listing) and the user's likely goal.",
        VISUAL_ANALYZER,
        [],
    )
    actions = _node(
        "list_visible_actions",
        "Enumerate the visible primary actions (buttons, links, inputs) and what each likely does.",
        PLANNER_AGENT,
        [identify.task_id],
    )
    guide = _node(
        "guide_steps",
        "Suggest the most likely next action(s) given the user's prompt or absence thereof.",
        PLANNER_AGENT,
        [actions.task_id],
    )
    report = _node(
        "draft_report",
        "Compose a markdown UI guide: what this screen is, what the user can do, recommended next step.",
        REPORT_AGENT,
        [guide.task_id],
    )
    return [identify, actions, guide, report]


def unknown_nodes() -> list[TaskNode]:
    clarify = _node(
        "request_clarification",
        "Ask the user one clarifying question. Do not invent a task plan from ambiguous evidence.",
        PLANNER_AGENT,
        [],
    )
    report = _node(
        "draft_report",
        "Compose a brief markdown note: what was observed, what is ambiguous, the clarifying question.",
        REPORT_AGENT,
        [clarify.task_id],
    )
    return [clarify, report]


TEMPLATES: dict[IntentKind, list] = {
    IntentKind.ERROR_DEBUG: error_debug_nodes,
    IntentKind.REPO_REVIEW: repo_review_nodes,
    IntentKind.UI_HELP: ui_help_nodes,
    IntentKind.UNKNOWN: unknown_nodes,
}


def build_nodes_for(intent: IntentKind) -> list[TaskNode]:
    factory = TEMPLATES.get(intent, unknown_nodes)
    return factory()
