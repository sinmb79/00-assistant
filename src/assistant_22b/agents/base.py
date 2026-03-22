# src/assistant_22b/agents/base.py
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from assistant_22b.pipeline.context import AgentResult, PipelineContext


@dataclass
class AgentManifest:
    id: str
    name: str
    icon: str
    version: str
    triggers: list[str]
    llm_preference: str  # "local" | "hybrid" | "external"
    sensitivity: str     # "public" | "internal" | "confidential" | "secret"
    fallback: bool = False

    @classmethod
    def from_json(cls, path: Path) -> AgentManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            id=data["id"],
            name=data["name"],
            icon=data.get("icon", ""),
            version=data["version"],
            triggers=data.get("triggers", []),
            llm_preference=data.get("llm_preference", "local"),
            sensitivity=data.get("sensitivity", "internal"),
            fallback=data.get("fallback", False),
        )


class BaseAgent(ABC):
    def __init__(self, manifest_dir: Path) -> None:
        self.manifest = AgentManifest.from_json(manifest_dir / "manifest.json")
        self._manifest_dir = manifest_dir

    @classmethod
    def from_manifest_dir(cls, path: Path) -> Self:
        return cls(path)

    @property
    def agent_id(self) -> str:
        return self.manifest.id

    @property
    def triggers(self) -> list[str]:
        return self.manifest.triggers

    @abstractmethod
    def process(self, context: PipelineContext) -> AgentResult: ...
