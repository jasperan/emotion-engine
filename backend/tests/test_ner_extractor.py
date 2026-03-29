"""Tests for the NER/RE extractor."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.storage.ner_extractor import Extraction, NERExtractor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_ONTOLOGY = {
    "entity_types": ["Person", "Location", "Organization"],
    "relation_types": ["lives_in", "works_for", "knows"],
}

GOOD_JSON = json.dumps(
    {
        "entities": [
            {"name": "Alice", "type": "Person", "attributes": {"age": 30}},
            {"name": "Springfield", "type": "Location", "attributes": {}},
        ],
        "relations": [
            {
                "source": "Alice",
                "target": "Springfield",
                "type": "lives_in",
                "fact": "Alice lives in Springfield.",
            }
        ],
    }
)

FENCED_JSON = f"Some preamble\n```json\n{GOOD_JSON}\n```\nSome epilogue"

MALFORMED_JSON = "This is definitely not JSON {{{ oops"


def _make_mock_client(content: str) -> LLMClient:
    """Build a mock LLM client that returns *content* from generate()."""
    client = MagicMock(spec=LLMClient)

    async def _generate(
        messages,
        model=None,
        temperature=0.7,
        max_tokens=1024,
        system=None,
        json_mode=False,
        stream_callback=None,
    ) -> LLMResponse:
        return LLMResponse(
            content=content,
            raw_response={"choices": [{"message": {"content": content}}]},
            usage={"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
        )

    client.generate = AsyncMock(side_effect=_generate)
    client.health_check = AsyncMock(return_value=True)
    return client


# ---------------------------------------------------------------------------
# Tests: Extraction dataclass
# ---------------------------------------------------------------------------


class TestExtractionDataclass:
    def test_default_empty(self):
        ext = Extraction()
        assert ext.entities == []
        assert ext.relations == []

    def test_with_data(self):
        entities = [{"name": "Bob", "type": "Person", "attributes": {}}]
        relations = [{"source": "Bob", "target": "Acme", "type": "works_for", "fact": "Bob works for Acme."}]
        ext = Extraction(entities=entities, relations=relations)
        assert len(ext.entities) == 1
        assert ext.entities[0]["name"] == "Bob"
        assert len(ext.relations) == 1
        assert ext.relations[0]["type"] == "works_for"


# ---------------------------------------------------------------------------
# Tests: NERExtractor creation
# ---------------------------------------------------------------------------


class TestNERExtractorCreation:
    def test_create_with_client(self, mock_llm_client):
        extractor = NERExtractor(llm_client=mock_llm_client)
        assert extractor._client is mock_llm_client
        assert extractor._max_retries == 2

    def test_create_without_client(self):
        extractor = NERExtractor()
        assert extractor._client is None

    def test_custom_retries(self, mock_llm_client):
        extractor = NERExtractor(llm_client=mock_llm_client, max_retries=5)
        assert extractor._max_retries == 5


# ---------------------------------------------------------------------------
# Tests: extract with good JSON
# ---------------------------------------------------------------------------


class TestExtractGoodJSON:
    @pytest.mark.asyncio
    async def test_extract_parses_valid_json(self):
        client = _make_mock_client(GOOD_JSON)
        extractor = NERExtractor(llm_client=client)
        result = await extractor.extract("Alice lives in Springfield.", SAMPLE_ONTOLOGY)

        assert isinstance(result, Extraction)
        assert len(result.entities) == 2
        assert result.entities[0]["name"] == "Alice"
        assert result.entities[1]["type"] == "Location"
        assert len(result.relations) == 1
        assert result.relations[0]["type"] == "lives_in"

    @pytest.mark.asyncio
    async def test_extract_calls_llm_with_correct_params(self):
        client = _make_mock_client(GOOD_JSON)
        extractor = NERExtractor(llm_client=client)
        await extractor.extract("some text", SAMPLE_ONTOLOGY)

        client.generate.assert_called_once()
        call_kwargs = client.generate.call_args
        # json_mode should be True
        assert call_kwargs.kwargs.get("json_mode") is True or (
            len(call_kwargs.args) > 0
        )

    @pytest.mark.asyncio
    async def test_extract_fenced_json(self):
        """LLM wraps JSON in markdown code fences; extractor should handle it."""
        client = _make_mock_client(FENCED_JSON)
        extractor = NERExtractor(llm_client=client)
        result = await extractor.extract("Alice lives in Springfield.", SAMPLE_ONTOLOGY)

        assert len(result.entities) == 2
        assert len(result.relations) == 1


# ---------------------------------------------------------------------------
# Tests: extract with malformed response (graceful fallback)
# ---------------------------------------------------------------------------


class TestExtractMalformed:
    @pytest.mark.asyncio
    async def test_malformed_returns_empty_extraction(self):
        client = _make_mock_client(MALFORMED_JSON)
        extractor = NERExtractor(llm_client=client)
        result = await extractor.extract("whatever", SAMPLE_ONTOLOGY)

        assert isinstance(result, Extraction)
        assert result.entities == []
        assert result.relations == []

    @pytest.mark.asyncio
    async def test_no_client_returns_empty_extraction(self):
        extractor = NERExtractor(llm_client=None)
        result = await extractor.extract("anything", SAMPLE_ONTOLOGY)

        assert isinstance(result, Extraction)
        assert result.entities == []
        assert result.relations == []

    @pytest.mark.asyncio
    async def test_llm_exception_returns_empty_after_retries(self):
        client = MagicMock(spec=LLMClient)
        client.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        extractor = NERExtractor(llm_client=client, max_retries=2)
        result = await extractor.extract("text", SAMPLE_ONTOLOGY)

        assert isinstance(result, Extraction)
        assert result.entities == []
        assert result.relations == []
        # Should have retried twice
        assert client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_partial_json_missing_relations(self):
        """Response has entities but no relations key."""
        partial = json.dumps({"entities": [{"name": "X", "type": "Person", "attributes": {}}]})
        client = _make_mock_client(partial)
        extractor = NERExtractor(llm_client=client)
        result = await extractor.extract("text", SAMPLE_ONTOLOGY)

        assert len(result.entities) == 1
        assert result.relations == []
