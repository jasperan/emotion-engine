import pytest


def test_simulation_engine_has_acp_attributes():
    """Verify SimulationEngine class can accept ACP components."""
    from emotionsim.acp.registry import AgentRegistry
    from emotionsim.acp.coordination import CoordinationController
    from emotionsim.agents.voting_mixin import GroupDecisionMixin

    # Verify the classes can be instantiated
    registry = AgentRegistry()
    coord = CoordinationController(level="moderate")
    voting = GroupDecisionMixin()

    assert registry is not None
    assert coord.level == "moderate"
    assert voting is not None
