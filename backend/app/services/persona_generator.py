"""Persona generator: converts graph entities into Big Five + MBTI agent personas via LLM."""

import json
import logging
import random
from dataclasses import dataclass, field

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.schemas.persona import Persona

logger = logging.getLogger(__name__)

_GENERATION_PROMPT = """\
You are a character designer for a multi-agent disaster simulation.
Given an entity description (and optional scenario context), generate a rich persona with personality traits.

Return ONLY valid JSON with these fields:
{
  "name": "string",
  "age": int (1-120),
  "sex": "male" | "female" | "non-binary",
  "occupation": "string",
  "openness": int (1-10),
  "conscientiousness": int (1-10),
  "extraversion": int (1-10),
  "agreeableness": int (1-10),
  "neuroticism": int (1-10),
  "risk_tolerance": int (1-10),
  "empathy_level": int (1-10),
  "leadership": int (1-10),
  "mbti": "string (4 letters, e.g. INTJ)",
  "backstory": "string (2-3 sentences)",
  "skills": ["string", ...],
  "opinion_biases": {"topic": float (-1.0 to 1.0), ...},
  "influence_level": float (0.0-1.0),
  "reaction_speed": float (0.0-1.0)
}

Make the persona feel like a real person. Traits should be internally consistent with the
occupation, backstory, and MBTI type. Avoid generic defaults; give them edges and quirks.
"""


def _clamp_int(value: int | float | str, lo: int, hi: int, default: int) -> int:
    """Clamp a value to [lo, hi], returning default on failure."""
    try:
        return max(lo, min(hi, int(value)))
    except (ValueError, TypeError):
        return default


def _clamp_float(value: float | str, lo: float, hi: float, default: float) -> float:
    """Clamp a float to [lo, hi], returning default on failure."""
    try:
        return max(lo, min(hi, float(value)))
    except (ValueError, TypeError):
        return default


@dataclass
class GeneratedPersona:
    """Intermediate representation of a generated persona before conversion to Pydantic model."""

    name: str
    entity_id: str = ""
    age: int = 30
    sex: str = "non-binary"
    occupation: str = "Civilian"

    # Big Five (1-10)
    openness: int = 5
    conscientiousness: int = 5
    extraversion: int = 5
    agreeableness: int = 5
    neuroticism: int = 5

    # Behavioral modifiers (1-10)
    risk_tolerance: int = 5
    empathy_level: int = 5
    leadership: int = 5

    # MBTI
    mbti: str | None = None

    # Background
    backstory: str = ""
    skills: list[str] = field(default_factory=list)
    opinion_biases: dict[str, float] = field(default_factory=dict)
    influence_level: float = 0.5
    reaction_speed: float = 0.5

    def to_persona(self) -> Persona:
        """Convert to the existing Pydantic Persona model."""
        # Clamp opinion_biases values to [-1.0, 1.0] for opinion_vectors
        opinion_vectors = {
            k: _clamp_float(v, -1.0, 1.0, 0.0) for k, v in self.opinion_biases.items()
        }
        return Persona(
            name=self.name,
            age=self.age,
            sex=self.sex if self.sex in ("male", "female", "non-binary") else "non-binary",
            occupation=self.occupation,
            openness=_clamp_int(self.openness, 1, 10, 5),
            conscientiousness=_clamp_int(self.conscientiousness, 1, 10, 5),
            extraversion=_clamp_int(self.extraversion, 1, 10, 5),
            agreeableness=_clamp_int(self.agreeableness, 1, 10, 5),
            neuroticism=_clamp_int(self.neuroticism, 1, 10, 5),
            risk_tolerance=_clamp_int(self.risk_tolerance, 1, 10, 5),
            empathy_level=_clamp_int(self.empathy_level, 1, 10, 5),
            leadership=_clamp_int(self.leadership, 1, 10, 5),
            backstory=self.backstory,
            skills=list(self.skills),
            opinion_vectors=opinion_vectors,
            opinion_bias=_clamp_float(
                1.0 - (self.openness / 10.0 + self.agreeableness / 10.0) / 2.0,
                0.0, 1.0, 0.5,
            ),
            reaction_speed=_clamp_float(self.reaction_speed, 0.0, 1.0, 0.5),
            influence_level=_clamp_float(self.influence_level, 0.0, 1.0, 0.5),
        )

    @classmethod
    def fallback(cls, name: str, entity_type: str = "person") -> "GeneratedPersona":
        """Create a persona with randomized Big Five traits in the 3-8 range."""
        return cls(
            name=name,
            entity_id="",
            age=random.randint(20, 60),
            sex=random.choice(["male", "female", "non-binary"]),
            occupation=entity_type.capitalize() if entity_type != "person" else "Civilian",
            openness=random.randint(3, 8),
            conscientiousness=random.randint(3, 8),
            extraversion=random.randint(3, 8),
            agreeableness=random.randint(3, 8),
            neuroticism=random.randint(3, 8),
            risk_tolerance=random.randint(3, 8),
            empathy_level=random.randint(3, 8),
            leadership=random.randint(3, 8),
            backstory=f"A {entity_type} with an unremarkable past, now caught up in events beyond their control.",
            skills=[],
            opinion_biases={},
            influence_level=round(random.uniform(0.2, 0.8), 2),
            reaction_speed=round(random.uniform(0.2, 0.8), 2),
        )


class PersonaGenerator:
    """Generates rich personas from entity data using an LLM."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client

    async def generate_from_entity(
        self,
        entity: dict,
        scenario_context: str = "",
    ) -> GeneratedPersona:
        """Generate a persona from an entity dict via LLM, falling back on error.

        Args:
            entity: Dict with at least a "name" key. May contain "type", "description", etc.
            scenario_context: Optional scenario description for richer generation.

        Returns:
            GeneratedPersona populated from LLM output or fallback defaults.
        """
        entity_name = entity.get("name", "Unknown")

        if self.llm_client is None:
            logger.warning("No LLM client configured; using fallback persona for %s", entity_name)
            return GeneratedPersona.fallback(entity_name, entity.get("type", "person"))

        user_content = f"Entity data: {json.dumps(entity, default=str)}"
        if scenario_context:
            user_content += f"\n\nScenario context: {scenario_context}"

        messages = [
            LLMMessage(role="system", content=_GENERATION_PROMPT),
            LLMMessage(role="user", content=user_content),
        ]

        try:
            response: LLMResponse = await self.llm_client.generate(
                messages=messages,
                temperature=0.8,
                max_tokens=1024,
                json_mode=True,
            )
            data = json.loads(response.content)
            return self._parse_response(data, entity_name)
        except Exception:
            logger.exception("LLM persona generation failed for %s; using fallback", entity_name)
            return GeneratedPersona.fallback(entity_name, entity.get("type", "person"))

    def _parse_response(self, data: dict, fallback_name: str) -> GeneratedPersona:
        """Parse LLM JSON response into a GeneratedPersona, clamping all values."""
        sex_raw = str(data.get("sex", "non-binary")).lower()
        sex = sex_raw if sex_raw in ("male", "female", "non-binary") else "non-binary"

        skills_raw = data.get("skills", [])
        skills = [str(s) for s in skills_raw] if isinstance(skills_raw, list) else []

        biases_raw = data.get("opinion_biases", {})
        opinion_biases: dict[str, float] = {}
        if isinstance(biases_raw, dict):
            for k, v in biases_raw.items():
                opinion_biases[str(k)] = _clamp_float(v, -1.0, 1.0, 0.0)

        mbti_raw = data.get("mbti")
        mbti = str(mbti_raw).upper() if mbti_raw and len(str(mbti_raw)) == 4 else None

        return GeneratedPersona(
            name=str(data.get("name", fallback_name)),
            age=_clamp_int(data.get("age", 30), 1, 120, 30),
            sex=sex,
            occupation=str(data.get("occupation", "Civilian")),
            openness=_clamp_int(data.get("openness", 5), 1, 10, 5),
            conscientiousness=_clamp_int(data.get("conscientiousness", 5), 1, 10, 5),
            extraversion=_clamp_int(data.get("extraversion", 5), 1, 10, 5),
            agreeableness=_clamp_int(data.get("agreeableness", 5), 1, 10, 5),
            neuroticism=_clamp_int(data.get("neuroticism", 5), 1, 10, 5),
            risk_tolerance=_clamp_int(data.get("risk_tolerance", 5), 1, 10, 5),
            empathy_level=_clamp_int(data.get("empathy_level", 5), 1, 10, 5),
            leadership=_clamp_int(data.get("leadership", 5), 1, 10, 5),
            mbti=mbti,
            backstory=str(data.get("backstory", "")),
            skills=skills,
            opinion_biases=opinion_biases,
            influence_level=_clamp_float(data.get("influence_level", 0.5), 0.0, 1.0, 0.5),
            reaction_speed=_clamp_float(data.get("reaction_speed", 0.5), 0.0, 1.0, 0.5),
        )
