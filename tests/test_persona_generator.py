"""Tests for the PersonaGenerator service."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse
from emotionsim.schemas.persona import Persona
from emotionsim.services.persona_generator import GeneratedPersona, PersonaGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_LLM_JSON = {
    "name": "Dr. Elara Vasquez",
    "age": 42,
    "sex": "female",
    "occupation": "Marine Biologist",
    "openness": 8,
    "conscientiousness": 7,
    "extraversion": 4,
    "agreeableness": 6,
    "neuroticism": 3,
    "risk_tolerance": 7,
    "empathy_level": 8,
    "leadership": 6,
    "mbti": "INFJ",
    "backstory": "Spent 15 years studying coral reefs before the disaster struck. Knows how to stay calm under water.",
    "skills": ["swimming", "first aid", "marine navigation"],
    "opinion_biases": {"government": -0.3, "science": 0.8},
    "influence_level": 0.65,
    "reaction_speed": 0.7,
}


def _make_mock_client(response_json: dict) -> LLMClient:
    """Create a mock LLM client that returns the given JSON as content."""
    mock = AsyncMock(spec=LLMClient)
    mock.generate.return_value = LLMResponse(
        content=json.dumps(response_json),
        raw_response=None,
        usage={"prompt_tokens": 100, "completion_tokens": 200},
    )
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_persona_from_entity():
    """Mock LLM returns valid JSON; verify persona has correct traits."""
    client = _make_mock_client(VALID_LLM_JSON)
    gen = PersonaGenerator(llm_client=client)

    entity = {"name": "Dr. Elara Vasquez", "type": "scientist", "description": "A marine biologist"}
    persona = await gen.generate_from_entity(entity, scenario_context="Rising Flood")

    assert isinstance(persona, GeneratedPersona)
    assert persona.name == "Dr. Elara Vasquez"
    assert persona.age == 42
    assert persona.sex == "female"
    assert persona.occupation == "Marine Biologist"
    assert persona.openness == 8
    assert persona.conscientiousness == 7
    assert persona.extraversion == 4
    assert persona.agreeableness == 6
    assert persona.neuroticism == 3
    assert persona.risk_tolerance == 7
    assert persona.empathy_level == 8
    assert persona.leadership == 6
    assert persona.mbti == "INFJ"
    assert "swimming" in persona.skills
    assert persona.opinion_biases["science"] == pytest.approx(0.8)
    assert 0.0 <= persona.influence_level <= 1.0
    assert 0.0 <= persona.reaction_speed <= 1.0

    # Verify the LLM was called with json_mode=True
    client.generate.assert_awaited_once()
    call_kwargs = client.generate.call_args
    assert call_kwargs.kwargs.get("json_mode") is True


@pytest.mark.asyncio
async def test_generate_creates_valid_pydantic_persona():
    """Call to_persona() on a generated persona and verify it produces a valid Persona."""
    client = _make_mock_client(VALID_LLM_JSON)
    gen = PersonaGenerator(llm_client=client)

    entity = {"name": "Dr. Elara Vasquez", "type": "scientist"}
    generated = await gen.generate_from_entity(entity)
    pydantic_persona = generated.to_persona()

    assert isinstance(pydantic_persona, Persona)
    assert pydantic_persona.name == "Dr. Elara Vasquez"
    assert pydantic_persona.age == 42
    assert pydantic_persona.sex == "female"
    assert pydantic_persona.occupation == "Marine Biologist"
    assert pydantic_persona.openness == 8
    assert pydantic_persona.risk_tolerance == 7
    assert "first aid" in pydantic_persona.skills
    # Pydantic should validate all constraints without raising
    assert 1 <= pydantic_persona.neuroticism <= 10


def test_fallback_persona():
    """Verify fallback generates reasonable defaults with randomized traits."""
    persona = GeneratedPersona.fallback("Jane Doe", entity_type="rescuer")

    assert persona.name == "Jane Doe"
    assert persona.occupation == "Rescuer"
    assert 3 <= persona.openness <= 8
    assert 3 <= persona.conscientiousness <= 8
    assert 3 <= persona.extraversion <= 8
    assert 3 <= persona.agreeableness <= 8
    assert 3 <= persona.neuroticism <= 8
    assert 3 <= persona.risk_tolerance <= 8
    assert 3 <= persona.empathy_level <= 8
    assert 3 <= persona.leadership <= 8
    assert 0.2 <= persona.influence_level <= 0.8
    assert 0.2 <= persona.reaction_speed <= 0.8
    assert 20 <= persona.age <= 60
    assert persona.sex in ("male", "female", "non-binary")
    assert "rescuer" in persona.backstory.lower()

    # Fallback should also convert cleanly to Pydantic
    p = persona.to_persona()
    assert isinstance(p, Persona)


@pytest.mark.asyncio
async def test_fallback_on_llm_error():
    """When the LLM raises an exception, we should get a fallback persona."""
    client = AsyncMock(spec=LLMClient)
    client.generate.side_effect = RuntimeError("LLM is down")
    gen = PersonaGenerator(llm_client=client)

    entity = {"name": "Bob Smith", "type": "engineer"}
    persona = await gen.generate_from_entity(entity)

    assert isinstance(persona, GeneratedPersona)
    assert persona.name == "Bob Smith"
    assert persona.occupation == "Engineer"
    # Traits should be in fallback range
    assert 3 <= persona.openness <= 8


@pytest.mark.asyncio
async def test_fallback_when_no_client():
    """When no LLM client is provided, fallback is used directly."""
    gen = PersonaGenerator(llm_client=None)
    entity = {"name": "Alice", "type": "medic"}
    persona = await gen.generate_from_entity(entity)

    assert isinstance(persona, GeneratedPersona)
    assert persona.name == "Alice"
    assert persona.occupation == "Medic"


@pytest.mark.asyncio
async def test_clamping_out_of_range_values():
    """Values outside valid ranges should be clamped."""
    bad_json = {
        **VALID_LLM_JSON,
        "openness": 15,
        "neuroticism": -3,
        "age": 999,
        "influence_level": 5.0,
        "reaction_speed": -1.0,
    }
    client = _make_mock_client(bad_json)
    gen = PersonaGenerator(llm_client=client)

    entity = {"name": "Test"}
    persona = await gen.generate_from_entity(entity)

    assert persona.openness == 10
    assert persona.neuroticism == 1
    assert persona.age == 120
    assert persona.influence_level == 1.0
    assert persona.reaction_speed == 0.0
