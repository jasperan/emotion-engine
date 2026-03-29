"""Scenario assembler: converts IngestedScenario graph entities into simulation-ready ScenarioCreate."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.agent import AgentConfig
from app.schemas.scenario import ScenarioCreate, WorldConfig
from app.services.document_ingestor import IngestedScenario
from app.services.persona_generator import GeneratedPersona, PersonaGenerator

logger = logging.getLogger(__name__)


def _to_snake_case(name: str) -> str:
    """Convert a location name to a snake_case key."""
    # Replace non-alphanumeric chars with underscores, collapse runs, strip edges
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip())
    # Insert underscores before uppercase runs (camelCase -> camel_Case)
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s)
    return s.lower().strip("_") or "unknown"


class ScenarioAssembler:
    """Transforms an IngestedScenario (graph entities) into a ScenarioCreate ready for simulation."""

    def __init__(self, persona_generator: PersonaGenerator | None = None) -> None:
        self._persona_gen = persona_generator or PersonaGenerator()

    async def assemble(
        self,
        ingested: IngestedScenario,
        scenario_name: str,
        scenario_description: str = "",
        max_steps: int = 100,
    ) -> ScenarioCreate:
        """Build a full ScenarioCreate from ingested graph entities.

        Steps:
            1. Extract locations, convert to location dicts.
            2. Fall back to "central_area" if none found.
            3. Wire up nearby connections (fully connected for small maps).
            4. Extract hazards, mark affected locations.
            5. Create environment agent.
            6. Generate personas from person entities, assign locations round-robin.
            7. Create human AgentConfigs with survival goals.
            8. Build WorldConfig and return ScenarioCreate.
        """
        # --- 1. Locations ---
        location_entities = ingested.get_location_entities()
        locations: dict[str, dict[str, Any]] = {}

        for loc_ent in location_entities:
            key = _to_snake_case(loc_ent.get("name", "unknown"))
            attrs = loc_ent.get("attributes", {})
            description = attrs.get("description", loc_ent.get("name", key))
            locations[key] = {
                "description": description,
                "nearby": [],
                "items": [],
                "hazard_affected": False,
                "observations": [],
            }

        # --- 2. Default location fallback ---
        if not locations:
            locations["central_area"] = {
                "description": "A central gathering area where survivors have congregated.",
                "nearby": [],
                "items": [],
                "hazard_affected": False,
                "observations": [],
            }

        # --- 3. Wire nearby connections (fully connected for small maps, <= 6) ---
        location_keys = list(locations.keys())
        if len(location_keys) <= 6:
            # Fully connected
            for key in location_keys:
                locations[key]["nearby"] = [k for k in location_keys if k != key]
        else:
            # Ring topology with next-2 neighbors for larger maps
            for i, key in enumerate(location_keys):
                neighbors = set()
                for offset in (1, 2):
                    neighbors.add(location_keys[(i + offset) % len(location_keys)])
                    neighbors.add(location_keys[(i - offset) % len(location_keys)])
                neighbors.discard(key)
                locations[key]["nearby"] = sorted(neighbors)

        # --- 4. Hazards ---
        hazard_entities = ingested.get_hazard_entities()
        hazard_names = [h.get("name", "") for h in hazard_entities]

        if hazard_entities and location_keys:
            # Mark roughly half the locations as hazard-affected (at least 1)
            num_affected = max(1, len(location_keys) // 2)
            for key in location_keys[:num_affected]:
                locations[key]["hazard_affected"] = True
                if hazard_names:
                    locations[key]["observations"].append(
                        f"Affected by: {hazard_names[0]}"
                    )

        # --- 5. Environment agent ---
        hazard_goals = [f"Simulate {h}" for h in hazard_names] if hazard_names else []
        env_agent = AgentConfig(
            name="Environment",
            role="environment",
            goals=[
                "Simulate realistic environmental progression",
                "Create meaningful survival challenges",
                "Generate events that force cooperation",
            ]
            + hazard_goals,
        )

        # --- 6. Generate personas from person entities ---
        person_entities = ingested.get_person_entities()
        human_agents: list[AgentConfig] = []

        for idx, person_ent in enumerate(person_entities):
            generated: GeneratedPersona = await self._persona_gen.generate_from_entity(
                person_ent, scenario_context=scenario_description
            )
            persona = generated.to_persona()

            # Assign location round-robin
            loc_key = location_keys[idx % len(location_keys)]
            persona.location = loc_key

            human_agents.append(
                AgentConfig(
                    name=persona.name,
                    role="human",
                    persona=persona,
                    goals=[
                        "Survive and help others survive",
                        "Coordinate with other survivors",
                        "Find and share resources",
                        "Reach safety",
                    ],
                )
            )

        # --- 7. Build agent list ---
        agent_templates = [env_agent] + human_agents

        # --- 8. WorldConfig + ScenarioCreate ---
        world_config = WorldConfig(
            name=scenario_name,
            description=scenario_description,
            initial_state={
                "hazard_level": 1 if hazard_entities else 0,
                "locations": locations,
                "hazards": hazard_names,
                "events": [],
            },
            dynamics={
                "intensity_growth": 0.15,
                "resource_spawn_rate": 0.1,
                "event_probability": 0.2,
            },
            max_steps=max_steps,
            tick_delay=1.0,
        )

        return ScenarioCreate(
            name=scenario_name,
            description=scenario_description,
            config=world_config,
            agent_templates=agent_templates,
        )
