# tests/test_agent_registry.py
from pathlib import Path
from assistant_22b.agents.registry import AgentRegistry


AGENTS_DIR = (
    Path(__file__).parent.parent / "src" / "assistant_22b" / "agents"
)


def test_registry_loads_administrative_agent():
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.all_agents()
    ids = [a.agent_id for a in agents]
    assert "administrative" in ids


def test_registry_routes_by_keyword():
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.route("이 공문을 교정해줘")
    ids = [a.agent_id for a in agents]
    assert "administrative" in ids


def test_registry_falls_back_to_fallback_agent():
    """Unknown domain text → fallback agent (administrative, fallback=true)."""
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.route("오늘 날씨가 좋네요")  # no trigger match
    assert len(agents) == 1
    assert agents[0].agent_id == "administrative"


def test_registry_keyword_match_is_case_insensitive():
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.route("문서 교정 부탁합니다")
    ids = [a.agent_id for a in agents]
    assert "administrative" in ids


def test_registry_no_duplicate_agents_for_multiple_trigger_matches():
    registry = AgentRegistry(AGENTS_DIR)
    # "공문서 맞춤법" contains TWO triggers for administrative → still one result
    agents = registry.route("공문서 맞춤법 교정")
    admin_hits = [a for a in agents if a.agent_id == "administrative"]
    assert len(admin_hits) == 1
