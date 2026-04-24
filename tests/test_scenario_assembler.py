"""Tests for the ScenarioAssembler service."""

import pytest

from emotionsim.schemas.scenario import ScenarioCreate
from emotionsim.services.document_ingestor import IngestedScenario
from emotionsim.services.persona_generator import GeneratedPersona, PersonaGenerator
from emotionsim.services.scenario_assembler import ScenarioAssembler, _to_snake_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockPersonaGenerator(PersonaGenerator):
    """PersonaGenerator that returns deterministic personas without an LLM."""

    def __init__(self) -> None:
        super().__init__(llm_client=None)

    async def generate_from_entity(
        self, entity: dict, scenario_context: str = ""
    ) -> GeneratedPersona:
        name = entity.get("name", "Unknown")
        return GeneratedPersona(
            name=name,
            age=30,
            sex="female",
            occupation="Survivor",
            openness=6,
            conscientiousness=7,
            extraversion=5,
            agreeableness=8,
            neuroticism=4,
            risk_tolerance=5,
            empathy_level=7,
            leadership=5,
            backstory=f"{name} is caught in an emergency.",
            skills=["adaptability"],
        )


def _make_ingested(
    persons: list[dict] | None = None,
    locations: list[dict] | None = None,
    hazards: list[dict] | None = None,
) -> IngestedScenario:
    """Build an IngestedScenario from entity lists."""
    entities: list[dict] = []
    if persons:
        entities.extend(persons)
    if locations:
        entities.extend(locations)
    if hazards:
        entities.extend(hazards)
    return IngestedScenario(graph_id="test-graph-1", entities=entities, relations=[])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToSnakeCase:
    def test_simple(self):
        assert _to_snake_case("Main Street") == "main_street"

    def test_camel(self):
        assert _to_snake_case("RoofTop") == "roof_top"

    def test_special_chars(self):
        assert _to_snake_case("Town Hall (East)") == "town_hall_east"

    def test_empty(self):
        assert _to_snake_case("") == "unknown"


class TestAssembleFromIngestedScenario:
    """Provide IngestedScenario with 1 person + 1 location + 1 hazard, verify ScenarioCreate."""

    @pytest.mark.asyncio
    async def test_assemble_from_ingested_scenario(self):
        ingested = _make_ingested(
            persons=[
                {
                    "name": "Alice",
                    "type": "person",
                    "entity_id": "p1",
                    "attributes": {"description": "A brave survivor"},
                }
            ],
            locations=[
                {
                    "name": "Town Square",
                    "type": "location",
                    "entity_id": "l1",
                    "attributes": {"description": "The central town square."},
                }
            ],
            hazards=[
                {
                    "name": "Wildfire",
                    "type": "hazard",
                    "entity_id": "h1",
                    "attributes": {"description": "A fast-moving wildfire."},
                }
            ],
        )

        assembler = ScenarioAssembler(persona_generator=MockPersonaGenerator())
        result = await assembler.assemble(
            ingested,
            scenario_name="Test Scenario",
            scenario_description="A test emergency.",
            max_steps=50,
        )

        # Basic type check
        assert isinstance(result, ScenarioCreate)
        assert result.name == "Test Scenario"
        assert result.description == "A test emergency."

        # WorldConfig
        assert result.config.max_steps == 50
        locations = result.config.initial_state["locations"]
        assert "town_square" in locations
        assert locations["town_square"]["hazard_affected"] is True
        assert locations["town_square"]["description"] == "The central town square."

        # Hazard propagated
        assert "Wildfire" in result.config.initial_state["hazards"]

        # Agents: 1 environment + 1 human
        assert len(result.agent_templates) == 2
        env_agent = result.agent_templates[0]
        assert env_agent.role == "environment"
        assert env_agent.name == "Environment"
        assert any("Wildfire" in g for g in env_agent.goals)

        human_agent = result.agent_templates[1]
        assert human_agent.role == "human"
        assert human_agent.name == "Alice"
        assert human_agent.persona is not None
        assert human_agent.persona.location == "town_square"
        assert len(human_agent.goals) > 0

    @pytest.mark.asyncio
    async def test_default_location_when_none_found(self):
        """If no location entities exist, assembler creates central_area."""
        ingested = _make_ingested(
            persons=[
                {"name": "Bob", "type": "person", "entity_id": "p2", "attributes": {}}
            ],
        )
        assembler = ScenarioAssembler(persona_generator=MockPersonaGenerator())
        result = await assembler.assemble(ingested, scenario_name="No Locations")

        locations = result.config.initial_state["locations"]
        assert "central_area" in locations
        # Human agent should be placed in central_area
        human = [a for a in result.agent_templates if a.role == "human"][0]
        assert human.persona is not None
        assert human.persona.location == "central_area"

    @pytest.mark.asyncio
    async def test_round_robin_location_assignment(self):
        """Multiple persons get locations assigned round-robin."""
        ingested = _make_ingested(
            persons=[
                {"name": "P1", "type": "person", "entity_id": "p1", "attributes": {}},
                {"name": "P2", "type": "person", "entity_id": "p2", "attributes": {}},
                {"name": "P3", "type": "person", "entity_id": "p3", "attributes": {}},
            ],
            locations=[
                {
                    "name": "Alpha",
                    "type": "location",
                    "entity_id": "l1",
                    "attributes": {"description": "Location A"},
                },
                {
                    "name": "Beta",
                    "type": "location",
                    "entity_id": "l2",
                    "attributes": {"description": "Location B"},
                },
            ],
        )
        assembler = ScenarioAssembler(persona_generator=MockPersonaGenerator())
        result = await assembler.assemble(ingested, scenario_name="Round Robin")

        humans = [a for a in result.agent_templates if a.role == "human"]
        assert len(humans) == 3
        # P1 -> alpha, P2 -> beta, P3 -> alpha (wrap)
        assert humans[0].persona.location == "alpha"
        assert humans[1].persona.location == "beta"
        assert humans[2].persona.location == "alpha"

        # Nearby should be fully connected (2 locations)
        locs = result.config.initial_state["locations"]
        assert "beta" in locs["alpha"]["nearby"]
        assert "alpha" in locs["beta"]["nearby"]

    @pytest.mark.asyncio
    async def test_no_persona_generator_uses_fallback(self):
        """Passing None for persona_generator still works (uses fallback internally)."""
        ingested = _make_ingested(
            persons=[
                {"name": "Cara", "type": "person", "entity_id": "p1", "attributes": {}}
            ],
        )
        # Default PersonaGenerator with no LLM client falls back to GeneratedPersona.fallback()
        assembler = ScenarioAssembler(persona_generator=None)
        result = await assembler.assemble(ingested, scenario_name="Fallback Test")

        humans = [a for a in result.agent_templates if a.role == "human"]
        assert len(humans) == 1
        assert humans[0].persona is not None
        assert humans[0].persona.name == "Cara"


class TestPresetScenariosWork:
    """Verify that existing preset scenarios still function correctly."""

    def test_preset_scenarios_work(self):
        from emotionsim.scenarios import create_rising_flood_scenario

        scenario = create_rising_flood_scenario(num_agents=3)
        assert isinstance(scenario, ScenarioCreate)
        assert scenario.name
        assert len(scenario.agent_templates) >= 2  # at least env + 1 human
        assert scenario.config.max_steps is not None
        assert scenario.config.initial_state.get("locations")
