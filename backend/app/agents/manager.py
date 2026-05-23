"""AgentManager: registry that maps required_agent (string) to AgentBase.

Use AgentManager.default() to get a singleton wired with all four built-in
agents (VisualAnalyzerAgent, PlannerAgent, ReportAgent, CodeAgent stub).
"""

from __future__ import annotations

from threading import Lock

from app.agents.base import AgentBase
from app.agents.code_agent import CodeAgent
from app.agents.planner import PlannerAgent
from app.agents.report_agent import ReportAgent
from app.agents.visual_analyzer import VisualAnalyzerAgent


class AgentManager:
    def __init__(self) -> None:
        self._agents: dict[str, AgentBase] = {}

    def register(self, agent: AgentBase) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> AgentBase | None:
        return self._agents.get(name)

    def known(self) -> list[str]:
        return list(self._agents.keys())


_default: AgentManager | None = None
_lock = Lock()


def default_manager() -> AgentManager:
    global _default
    if _default is not None:
        return _default
    with _lock:
        if _default is None:
            mgr = AgentManager()
            mgr.register(VisualAnalyzerAgent())
            mgr.register(PlannerAgent())
            mgr.register(ReportAgent())
            mgr.register(CodeAgent())
            _default = mgr
    return _default
