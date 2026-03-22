# src/assistant_22b/pipeline/context.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GateRecord:
    gate: int        # 1 | 2 | 3 | 4
    passed: bool
    timestamp: datetime
    notes: str = ""  # human-readable summary


@dataclass
class AgentResult:
    agent_id: str
    output: str                # formatted text shown to user
    citations: list[str]       # rule_ids cited
    raw: list                  # list[CorrectionItem] from P1, kept as list[Any]
    verified: bool = True      # set False by Gate 3 if issues found
    error: str | None = None   # set if agent.process() raised


@dataclass
class PipelineContext:
    request_id: str
    input_text: str
    sensitivity: str = "public"  # Gate 1 overwrites; public|internal|confidential|secret
    gate_log: list[GateRecord] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
