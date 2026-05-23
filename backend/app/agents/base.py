"""Common agent protocol.

Every agent in the runtime takes an AgentContext (the slice of the world it
needs) and returns an AgentResult. The Executor passes context to whichever
agent owns the current TaskNode and feeds each agent's output_summary into
downstream agents as upstream_results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field

from app.schemas.intent import IntentResult
from app.schemas.observation import VisualObservation
from app.schemas.task_graph import TaskGraph, TaskNode


class AgentContext(BaseModel):
    task_node: TaskNode
    observation: VisualObservation
    intent: IntentResult
    graph: TaskGraph
    upstream_results: dict[str, str] = Field(default_factory=dict)
    user_prompt: str = ""


class AgentResult(BaseModel):
    output_summary: str = ""
    detail_markdown: str = ""
    warnings: list[str] = Field(default_factory=list)
    model_used: str = ""
    latency_ms: int = 0
    skipped: bool = False


class AgentBase(ABC):
    name: ClassVar[str]

    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult: ...
