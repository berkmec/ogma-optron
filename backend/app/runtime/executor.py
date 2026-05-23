"""Executor: runs a TaskGraph through registered agents.

Topologically sorts nodes by depends_on, then dispatches each one to the
agent named in TaskNode.required_agent. Each agent's output_summary is fed
into downstream agents via AgentContext.upstream_results.

Sequential by design. Parallel branches would be safe (no shared state, no
side effects beyond the LLM calls), but the API surface and trace ordering
stay simpler when serial.
"""

from __future__ import annotations

import time
import uuid

from app.agents.base import AgentContext
from app.agents.manager import AgentManager
from app.schemas.agent import AgentRun, AgentRunStatus, AgentTrace
from app.schemas.asset import utcnow
from app.schemas.intent import IntentResult
from app.schemas.observation import VisualObservation
from app.schemas.task_graph import TaskGraph, TaskStatus


def _topological_order(graph: TaskGraph) -> list[str]:
    in_degree = {n.task_id: len(n.depends_on) for n in graph.nodes}
    queue = [n.task_id for n in graph.nodes if not n.depends_on]
    order: list[str] = []
    while queue:
        tid = queue.pop(0)
        order.append(tid)
        for n in graph.nodes:
            if tid in n.depends_on:
                in_degree[n.task_id] -= 1
                if in_degree[n.task_id] == 0:
                    queue.append(n.task_id)
    if len(order) != len(graph.nodes):
        raise ValueError("Task graph contains a cycle")
    return order


def execute(
    manager: AgentManager,
    graph: TaskGraph,
    observation: VisualObservation,
    intent: IntentResult,
    user_prompt: str = "",
    workspace_path: str = "",
) -> AgentRun:
    nodes_by_id = {n.task_id: n for n in graph.nodes}
    order = _topological_order(graph)

    upstream: dict[str, str] = {}
    traces: list[AgentTrace] = []
    failed = 0
    skipped = 0
    total_start = time.perf_counter()

    for tid in order:
        node = nodes_by_id[tid]
        started = utcnow()
        agent = manager.get(node.required_agent)

        if agent is None:
            traces.append(
                AgentTrace(
                    task_id=tid,
                    task_type=node.task_type,
                    agent_name=node.required_agent,
                    status=TaskStatus.FAILED,
                    started_at=started,
                    finished_at=utcnow(),
                    error=f"No agent registered with name {node.required_agent!r}",
                )
            )
            failed += 1
            continue

        ctx = AgentContext(
            task_node=node,
            observation=observation,
            intent=intent,
            graph=graph,
            upstream_results={
                dep_id: upstream[dep_id]
                for dep_id in node.depends_on
                if dep_id in upstream
            },
            user_prompt=user_prompt,
            workspace_path=workspace_path,
        )

        try:
            result = agent.run(ctx)
        except Exception as exc:
            traces.append(
                AgentTrace(
                    task_id=tid,
                    task_type=node.task_type,
                    agent_name=node.required_agent,
                    status=TaskStatus.FAILED,
                    started_at=started,
                    finished_at=utcnow(),
                    error=str(exc),
                )
            )
            failed += 1
            continue

        status = TaskStatus.SKIPPED if result.skipped else TaskStatus.DONE
        if result.skipped:
            skipped += 1
        upstream[tid] = result.output_summary
        traces.append(
            AgentTrace(
                task_id=tid,
                task_type=node.task_type,
                agent_name=node.required_agent,
                status=status,
                output_summary=result.output_summary,
                detail_markdown=result.detail_markdown,
                warnings=result.warnings,
                model_used=result.model_used,
                latency_ms=result.latency_ms,
                started_at=started,
                finished_at=utcnow(),
            )
        )

    total_ms = int((time.perf_counter() - total_start) * 1000)
    if failed == 0:
        status = AgentRunStatus.DONE
    elif failed < len(graph.nodes):
        status = AgentRunStatus.PARTIAL
    else:
        status = AgentRunStatus.FAILED

    return AgentRun(
        run_id=str(uuid.uuid4()),
        graph_id=graph.graph_id,
        intent_id=graph.intent_id,
        observation_id=graph.observation_id,
        asset_id=graph.asset_id,
        intent_kind=graph.intent_kind,
        status=status,
        traces=traces,
        total_latency_ms=total_ms,
        failed_count=failed,
        skipped_count=skipped,
    )
