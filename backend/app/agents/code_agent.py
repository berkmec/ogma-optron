"""CodeAgent: bridges to agent.exe (claw upstream) via ClawBridge.

Behavior:
- If context.workspace_path is empty, returns SKIPPED with a note. This lets
  the runtime gracefully run task graphs whose code task wasn't given a real
  workspace (e.g. error_debug intents on bare screenshots).
- Otherwise, runs ClawBridge.run_repo_review with the read-only profile.
  The resulting markdown becomes the agent's detail_markdown, and a short
  summary of findings becomes the output_summary downstream agents see.
"""

from __future__ import annotations

from typing import ClassVar

from app.agents.base import AgentBase, AgentContext, AgentResult
from app.clawbridge.wrapper import run_repo_review
from app.schemas.clawbridge import ClawPermissionProfile, ClawRunStatus


class CodeAgent(AgentBase):
    name: ClassVar[str] = "CodeAgent"

    def run(self, context: AgentContext) -> AgentResult:
        if not context.workspace_path:
            return AgentResult(
                output_summary=(
                    "CodeAgent skipped: no workspace_path provided for this run. "
                    "Pass workspace_path on /api/agents/run to enable code review."
                ),
                detail_markdown=(
                    "_CodeAgent was skipped because no workspace_path was provided. "
                    "Re-run with a workspace_path to engage the agent.exe subprocess._"
                ),
                warnings=["CodeAgent skipped — no workspace_path"],
                skipped=True,
            )

        prompt = context.user_prompt or context.task_node.description
        claw_run = run_repo_review(
            workspace_path=context.workspace_path,
            user_prompt=prompt,
            profile=ClawPermissionProfile.READ_ONLY,
        )

        if claw_run.status == ClawRunStatus.DONE:
            summary_lines = [
                f"Claw read-only review of {claw_run.workspace_path}",
                f"  files scanned: {len(claw_run.files_scanned)}, "
                f"key files read: {len(claw_run.files_read)}",
                f"  latency: {claw_run.latency_ms} ms",
            ]
            if claw_run.warnings:
                summary_lines.append("  warnings: " + "; ".join(claw_run.warnings))
            return AgentResult(
                output_summary="\n".join(summary_lines),
                detail_markdown=claw_run.output,
                warnings=claw_run.warnings,
                model_used=claw_run.model_used,
                latency_ms=claw_run.latency_ms,
            )

        # Failed / timeout / blocked → surface as warnings and an empty summary
        return AgentResult(
            output_summary=(
                f"ClawBridge {claw_run.status.value}: {claw_run.error or '(no detail)'}"
            ),
            detail_markdown=(
                f"_ClawBridge returned status `{claw_run.status.value}`._\n\n"
                f"```\n{claw_run.error}\n```"
            ),
            warnings=[*claw_run.warnings, f"ClawBridge {claw_run.status.value}"],
            model_used=claw_run.model_used,
            latency_ms=claw_run.latency_ms,
            skipped=True,
        )
