# tests/test_base_agent.py
import json
import pytest
from pathlib import Path
from assistant_22b.agents.base import AgentManifest, BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext


class ConcreteAgent(BaseAgent):
    """Minimal concrete implementation for testing the ABC."""
    def process(self, context: PipelineContext) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            output="test output",
            citations=[],
            raw=[],
        )


def test_agent_manifest_loads_from_json(tmp_manifest_dir):
    manifest = AgentManifest.from_json(tmp_manifest_dir / "manifest.json")
    assert manifest.id == "test-agent"
    assert manifest.name == "테스트 에이전트"
    assert "테스트" in manifest.triggers
    assert manifest.fallback is False


def test_base_agent_exposes_agent_id(tmp_manifest_dir):
    agent = ConcreteAgent(tmp_manifest_dir)
    assert agent.agent_id == "test-agent"


def test_base_agent_exposes_triggers(tmp_manifest_dir):
    agent = ConcreteAgent(tmp_manifest_dir)
    assert "테스트" in agent.triggers


def test_base_agent_from_manifest_dir(tmp_manifest_dir):
    agent = ConcreteAgent.from_manifest_dir(tmp_manifest_dir)
    assert agent.agent_id == "test-agent"


def test_base_agent_cannot_instantiate_without_process():
    """BaseAgent is abstract — instantiating it directly must fail."""
    with pytest.raises(TypeError):
        BaseAgent(Path("."))  # type: ignore
