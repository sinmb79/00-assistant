# src/assistant_22b/agents/administrative/agent.py
from __future__ import annotations

from pathlib import Path

from gongmun_doctor.engine import correct_text
from gongmun_doctor.rules.loader import load_rules

from assistant_22b.agents.base import BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext


class AdministrativeAgent(BaseAgent):
    """Wraps P1 공문닥터 engine as a BaseAgent.

    rules_dir=None  → use P1 bundled rules (L1/L2/L3, default)
    rules_dir=Path  → use custom rules directory (for testing or overrides)
    """

    def __init__(self, manifest_dir: Path, rules_dir: Path | None = None) -> None:
        super().__init__(manifest_dir)
        self._rules_dir = rules_dir

    def process(self, context: PipelineContext) -> AgentResult:
        rules = load_rules(self._rules_dir)
        items = correct_text(context.input_text, rules)
        return AgentResult(
            agent_id=self.agent_id,
            output=self._format_output(items),
            citations=[item.rule_id for item in items],
            raw=items,
        )

    def _format_output(self, items: list) -> str:
        if not items:
            return "교정 사항이 없습니다."
        lines = ["## 교정 결과\n"]
        for item in items:
            lines.append(
                f"- **[{item.rule_id}]** {item.rule_desc}\n"
                f"  - 원문: `{item.original_text}`\n"
                f"  - 교정: `{item.corrected_text}`\n"
                f"  - 근거: {item.rule_source}"
            )
        return "\n".join(lines)
