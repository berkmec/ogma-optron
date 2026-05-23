"""CodeAgent: placeholder for week 5 ClawBridge wiring.

Week 4 ships this as a no-op that marks its task SKIPPED with a clear
warning. Week 5 will subclass or replace this with a real subprocess call
into `agent.exe` (claw upstream) in read-only mode.
"""

from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentBase, AgentContext, AgentResult


class CodeAgent(AgentBase):
    name: ClassVar[str] = "CodeAgent"

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            output_summary=(
                "CodeAgent is a placeholder in week 4. "
                "Week 5 wires this to agent.exe (claw upstream) in read-only mode."
            ),
            detail_markdown=(
                "_CodeAgent has not yet been wired to ClawBridge. "
                "This step is skipped intentionally; week 5 will replace this "
                "stub with a real subprocess call._"
            ),
            warnings=["CodeAgent skipped — ClawBridge wiring pending (week 5)"],
            skipped=True,
        )
