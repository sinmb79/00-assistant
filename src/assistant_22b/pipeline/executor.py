# src/assistant_22b/pipeline/executor.py
from __future__ import annotations

import uuid
from datetime import datetime

from assistant_22b.agents.registry import AgentRegistry
from assistant_22b.pipeline.context import AgentResult, PipelineContext
from assistant_22b.security.auditor import SecurityAuditor


class PipelineExecutor:
    """Orchestrates the full request→response pipeline.

    Sequence: Gate1 → route → agent.process (×N) → Gate2 → Gate3 → Gate4
    All gates always run. Agent exceptions are caught and recorded.
    """

    def __init__(self, auditor: SecurityAuditor, registry: AgentRegistry) -> None:
        self._auditor = auditor
        self._registry = registry

    def run(self, text: str) -> PipelineContext:
        context = PipelineContext(
            request_id=str(uuid.uuid4()),
            input_text=text,
        )

        # Gate 1 — classify sensitivity
        self._auditor.gate1(context)

        # Route to agents
        agents = self._registry.route(text)

        # Execute agents (sequential in BMVP)
        for agent in agents:
            try:
                result = agent.process(context)
            except Exception as exc:
                result = AgentResult(
                    agent_id=agent.agent_id,
                    output="",
                    citations=[],
                    raw=[],
                    error=str(exc),
                )
            context.agent_results.append(result)

        # Gate 2 — PII mask check (BMVP: pass-through, no external LLM)
        self._auditor.gate2(context)

        # Gate 3 — verify results
        self._auditor.gate3(context)

        # Gate 4 — audit log
        self._auditor.gate4(context)

        context.completed_at = datetime.now()
        return context
