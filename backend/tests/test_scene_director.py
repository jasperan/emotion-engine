import pytest
from unittest.mock import MagicMock
from app.simulation.scene_director import SceneDirector


def make_agent(agent_id, name, location, extraversion=5):
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.role = "human"
    agent.dynamic_state = {"location": location}
    agent.persona = MagicMock()
    agent.persona.extraversion = extraversion
    return agent


def test_group_by_location_basic():
    sd = SceneDirector(max_turns=3)
    agents = {
        "a1": make_agent("a1", "Alice", "shelter"),
        "a2": make_agent("a2", "Bob", "shelter"),
        "a3": make_agent("a3", "Carol", "street"),
    }
    agent_locations = {"a1": "shelter", "a2": "shelter", "a3": "street"}
    groups = sd.group_agents_by_location(agents, agent_locations)
    assert set(groups["shelter"]) == {"a1", "a2"}
    assert groups["street"] == ["a3"]


def test_group_by_location_skips_non_human():
    sd = SceneDirector(max_turns=3)
    env_agent = MagicMock()
    env_agent.id = "env"
    env_agent.role = "environment"
    env_agent.dynamic_state = {"location": "shelter"}
    agents = {
        "a1": make_agent("a1", "Alice", "shelter"),
        "env": env_agent,
    }
    agent_locations = {"a1": "shelter", "env": "shelter"}
    groups = sd.group_agents_by_location(agents, agent_locations)
    assert "a1" in groups.get("shelter", [])
    assert "env" not in groups.get("shelter", [])


def test_pick_scene_initiator_highest_extraversion():
    sd = SceneDirector(max_turns=3)
    agents = {
        "a1": make_agent("a1", "Alice", "shelter", extraversion=3),
        "a2": make_agent("a2", "Bob", "shelter", extraversion=8),
    }
    initiator = sd.pick_initiator(["a1", "a2"], agents)
    assert initiator == "a2"  # highest extraversion wins


def test_pick_initiator_single_agent():
    sd = SceneDirector(max_turns=3)
    agents = {"a1": make_agent("a1", "Alice", "shelter", extraversion=5)}
    initiator = sd.pick_initiator(["a1"], agents)
    assert initiator == "a1"


def test_build_scene_participants_summary_excludes_self():
    sd = SceneDirector(max_turns=3)
    agents = {
        "a1": make_agent("a1", "Alice", "shelter"),
        "a2": make_agent("a2", "Bob", "shelter"),
    }
    agents["a1"].dynamic_state = {"location": "shelter", "stress_level": 8}
    agents["a2"].dynamic_state = {"location": "shelter", "stress_level": 3}
    summary = sd.build_scene_participants_summary(["a1", "a2"], agents, exclude_id="a1")
    assert "Bob" in summary
    assert "Alice" not in summary


def test_pick_initiator_empty_list_raises():
    sd = SceneDirector(max_turns=3)
    with pytest.raises(ValueError, match="empty"):
        sd.pick_initiator([], {})


def test_build_participants_summary_unknown_agent_id():
    sd = SceneDirector(max_turns=3)
    agents = {"a1": make_agent("a1", "Alice", "shelter")}
    agents["a1"].dynamic_state = {"location": "shelter", "stress_level": 5}
    # "a2" is not in agents dict — should not crash
    summary = sd.build_scene_participants_summary(["a1", "a2"], agents, exclude_id="none")
    assert "Alice" in summary


def test_group_by_location_empty_inputs():
    sd = SceneDirector(max_turns=3)
    groups = sd.group_agents_by_location({}, {})
    assert groups == {}


def test_group_by_location_agent_with_no_location_in_dict():
    sd = SceneDirector(max_turns=3)
    agent = make_agent("a1", "Alice", "shelter")
    # agent_locations is empty — falls back to dynamic_state
    groups = sd.group_agents_by_location({"a1": agent}, {})
    assert "shelter" in groups
    assert "a1" in groups["shelter"]
