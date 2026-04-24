"""NER/RE extractor that uses the LLM router to pull entities and relations from text."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Extraction:
    """Result of an NER/RE pass over a chunk of text."""

    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a precise Named Entity Recognition and Relationship Extraction engine.

Given a passage of text and an ontology specification, extract:
1. **Entities** -- each with keys: "name" (str), "type" (str from ontology entity_types), \
"attributes" (dict of any extra properties you can infer).
2. **Relations** -- each with keys: "source" (entity name), "target" (entity name), \
"type" (str from ontology relation_types), "fact" (one-sentence natural language statement).

Return ONLY valid JSON with the structure:
{{
  "entities": [ {{"name": "...", "type": "...", "attributes": {{...}}}} ],
  "relations": [ {{"source": "...", "target": "...", "type": "...", "fact": "..."}} ]
}}

Ontology
--------
Entity types: {entity_types}
Relation types: {relation_types}

Rules:
- Only use entity types and relation types from the ontology above.
- If no entities or relations are found, return empty lists.
- Do NOT wrap the JSON in markdown code fences.
"""


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class NERExtractor:
    """Uses an LLM client to extract entities and relations from free text."""

    def __init__(self, llm_client: LLMClient | None = None, max_retries: int = 2) -> None:
        self._client = llm_client
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract(self, text: str, ontology: dict[str, Any]) -> Extraction:
        """Send *text* through the LLM with an ontology-guided prompt and
        return an ``Extraction`` containing entities and relations.

        If the LLM client is ``None`` or all retries fail, an empty
        ``Extraction`` is returned.
        """
        if self._client is None:
            logger.warning("NERExtractor has no LLM client; returning empty extraction")
            return Extraction()

        entity_types = ontology.get("entity_types", [])
        relation_types = ontology.get("relation_types", [])

        system = _SYSTEM_PROMPT.format(
            entity_types=json.dumps(entity_types),
            relation_types=json.dumps(relation_types),
        )

        messages = [LLMMessage(role="user", content=text)]

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response: LLMResponse = await self._client.generate(
                    messages=messages,
                    system=system,
                    json_mode=True,
                    temperature=0.0,
                    max_tokens=2048,
                )
                return self._parse(response.content)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "NERExtractor attempt %d/%d failed: %s",
                    attempt,
                    self._max_retries,
                    exc,
                )

        logger.error("NERExtractor exhausted retries. Last error: %s", last_error)
        return Extraction()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(raw: str) -> Extraction:
        """Parse LLM output into an ``Extraction``.

        Tries direct JSON first, then looks for a fenced code block.
        Returns an empty ``Extraction`` on any parse failure.
        """
        # Attempt 1: direct parse
        data = _try_json(raw)
        if data is not None:
            return _extraction_from_dict(data)

        # Attempt 2: extract from markdown code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if match:
            data = _try_json(match.group(1).strip())
            if data is not None:
                return _extraction_from_dict(data)

        logger.warning("NERExtractor could not parse LLM response; returning empty extraction")
        return Extraction()


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------


def _try_json(text: str) -> dict[str, Any] | None:
    """Return parsed dict or None on failure."""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _extraction_from_dict(data: dict[str, Any]) -> Extraction:
    """Build an Extraction from a parsed dict, tolerating missing keys."""
    entities = data.get("entities", [])
    relations = data.get("relations", [])
    if not isinstance(entities, list):
        entities = []
    if not isinstance(relations, list):
        relations = []
    return Extraction(entities=entities, relations=relations)
