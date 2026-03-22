# src/assistant_22b/agents/registry.py
from __future__ import annotations

import importlib
from pathlib import Path

from assistant_22b.agents.base import BaseAgent


class AgentRegistry:
    """Scans agents/*/manifest.json, loads agents, routes requests by trigger keyword."""

    def __init__(self, agents_dir: Path) -> None:
        self._agents: list[BaseAgent] = []
        self._fallback: BaseAgent | None = None
        self._load(agents_dir)

    def _load(self, agents_dir: Path) -> None:
        for manifest_path in sorted(agents_dir.glob("*/manifest.json")):
            agent_dir = manifest_path.parent
            subpackage = agent_dir.name  # e.g., "administrative"

            try:
                module = importlib.import_module(
                    f"assistant_22b.agents.{subpackage}.agent"
                )
            except ImportError:
                continue

            # Find the first BaseAgent subclass in the module
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseAgent)
                    and obj is not BaseAgent
                ):
                    agent = obj.from_manifest_dir(agent_dir)
                    self._agents.append(agent)
                    if agent.manifest.fallback:
                        self._fallback = agent
                    break

    def all_agents(self) -> list[BaseAgent]:
        return list(self._agents)

    def route(self, text: str) -> list[BaseAgent]:
        """Return agents whose triggers appear in text. Deduplicated, preserves order."""
        text_lower = text.lower()
        seen: set[str] = set()
        matched: list[BaseAgent] = []

        for agent in self._agents:
            if agent.agent_id in seen:
                continue
            if any(trigger.lower() in text_lower for trigger in agent.triggers):
                matched.append(agent)
                seen.add(agent.agent_id)

        if not matched and self._fallback:
            return [self._fallback]
        return matched
