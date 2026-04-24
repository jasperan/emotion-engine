"""Tests for the document ingestion pipeline."""

from __future__ import annotations

import pytest

from unittest.mock import AsyncMock, MagicMock

from emotionsim.services.document_ingestor import (
    DEFAULT_ONTOLOGY,
    DocumentIngestor,
    IngestedScenario,
    _chunk_text,
)
from emotionsim.storage.graph_storage import Entity, Edge
from emotionsim.storage.ner_extractor import Extraction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_storage():
    """Return an AsyncMock that quacks like GraphStorage."""
    storage = AsyncMock()
    storage.create_graph.return_value = "graph-001"
    storage.add_entity.return_value = "ent-id"
    storage.add_edge.return_value = "edge-id"
    return storage


@pytest.fixture
def mock_ner():
    """Return an AsyncMock that quacks like NERExtractor."""
    ner = AsyncMock()
    ner.extract.return_value = Extraction(
        entities=[
            {"name": "Alice", "type": "person", "attributes": {"age": 30}},
            {"name": "Downtown", "type": "location", "attributes": {}},
            {"name": "Flood", "type": "hazard", "attributes": {"severity": "high"}},
        ],
        relations=[
            {
                "source": "Alice",
                "target": "Downtown",
                "type": "located_at",
                "fact": "Alice is in downtown.",
            },
            {
                "source": "Flood",
                "target": "Downtown",
                "type": "affects",
                "fact": "The flood affects downtown.",
            },
        ],
    )
    return ner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_document(mock_storage, mock_ner):
    """Verify that ingest creates a graph, stores entities, and stores edges."""
    ingestor = DocumentIngestor(storage=mock_storage, ner_extractor=mock_ner)

    result = await ingestor.ingest(
        text="Alice lives in Downtown. The flood hit Downtown hard.",
        scenario_name="Rising Flood",
    )

    # Graph was created
    mock_storage.create_graph.assert_called_once_with("Rising Flood", DEFAULT_ONTOLOGY)
    assert result.graph_id == "graph-001"

    # 3 unique entities stored
    assert mock_storage.add_entity.call_count == 3
    assert len(result.entities) == 3

    entity_names = {e["name"] for e in result.entities}
    assert entity_names == {"Alice", "Downtown", "Flood"}

    # 2 edges stored (both source and target exist)
    assert mock_storage.add_edge.call_count == 2
    assert len(result.relations) == 2

    rel_types = {r["type"] for r in result.relations}
    assert "located_at" in rel_types
    assert "affects" in rel_types


@pytest.mark.asyncio
async def test_ingest_generates_ontology(mock_storage, mock_ner):
    """Verify that ontology is passed through to create_graph."""
    custom_ontology = {
        "entity_types": ["person", "animal"],
        "relation_types": ["feeds"],
    }
    ingestor = DocumentIngestor(storage=mock_storage, ner_extractor=mock_ner)

    await ingestor.ingest(
        text="Bob feeds the cat.",
        scenario_name="Pet Care",
        ontology=custom_ontology,
    )

    mock_storage.create_graph.assert_called_once_with("Pet Care", custom_ontology)


@pytest.mark.asyncio
async def test_ingest_skips_edges_with_missing_entities(mock_storage):
    """Edges referencing unknown entities should be silently skipped."""
    ner = AsyncMock()
    ner.extract.return_value = Extraction(
        entities=[
            {"name": "Alice", "type": "person", "attributes": {}},
        ],
        relations=[
            {
                "source": "Alice",
                "target": "UnknownPlace",
                "type": "located_at",
                "fact": "Alice is somewhere unknown.",
            },
        ],
    )

    ingestor = DocumentIngestor(storage=mock_storage, ner_extractor=ner)
    result = await ingestor.ingest(text="Alice went somewhere.", scenario_name="test")

    # Entity stored, but edge skipped
    assert mock_storage.add_entity.call_count == 1
    assert mock_storage.add_edge.call_count == 0
    assert len(result.relations) == 0


@pytest.mark.asyncio
async def test_ingest_deduplicates_entities(mock_storage):
    """Duplicate entity names across chunks should be deduplicated."""
    ner = AsyncMock()
    # Simulate two chunks returning the same entity name
    ner.extract.side_effect = [
        Extraction(
            entities=[{"name": "Alice", "type": "person", "attributes": {"age": 30}}],
            relations=[],
        ),
        Extraction(
            entities=[{"name": "Alice", "type": "person", "attributes": {"age": 31}}],
            relations=[],
        ),
    ]

    ingestor = DocumentIngestor(storage=mock_storage, ner_extractor=ner)
    # Two paragraphs = two chunks
    result = await ingestor.ingest(
        text="Alice is brave.\n\nAlice is strong.",
        scenario_name="dedup-test",
    )

    # Only one entity stored
    assert len(result.entities) == 1
    assert result.entities[0]["name"] == "Alice"
    assert mock_storage.add_entity.call_count == 1


def test_ingested_scenario_filtering():
    """Test get_person_entities, get_location_entities, get_hazard_entities."""
    scenario = IngestedScenario(
        graph_id="g1",
        entities=[
            {"name": "Alice", "type": "person", "entity_id": "e1", "attributes": {}},
            {"name": "Bob", "type": "person", "entity_id": "e2", "attributes": {}},
            {"name": "Downtown", "type": "location", "entity_id": "e3", "attributes": {}},
            {"name": "Hospital", "type": "location", "entity_id": "e4", "attributes": {}},
            {"name": "Flood", "type": "hazard", "entity_id": "e5", "attributes": {}},
            {"name": "Red Cross", "type": "organization", "entity_id": "e6", "attributes": {}},
        ],
    )

    persons = scenario.get_person_entities()
    assert len(persons) == 2
    assert {p["name"] for p in persons} == {"Alice", "Bob"}

    locations = scenario.get_location_entities()
    assert len(locations) == 2
    assert {loc["name"] for loc in locations} == {"Downtown", "Hospital"}

    hazards = scenario.get_hazard_entities()
    assert len(hazards) == 1
    assert hazards[0]["name"] == "Flood"


def test_chunk_text_single_paragraph():
    """A short text should produce a single chunk."""
    chunks = _chunk_text("Hello world.")
    assert len(chunks) == 1
    assert chunks[0] == "Hello world."


def test_chunk_text_multiple_paragraphs():
    """Paragraphs separated by double newlines should be preserved."""
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = _chunk_text(text)
    # All three fit in one chunk (well under 2000 chars)
    assert len(chunks) == 1
    assert "First paragraph." in chunks[0]
    assert "Third paragraph." in chunks[0]


def test_chunk_text_long_paragraph():
    """A paragraph exceeding 2000 chars should be hard-split."""
    long_text = "A" * 3000
    chunks = _chunk_text(long_text)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2000
    assert len(chunks[1]) == 1000


@pytest.mark.asyncio
async def test_ingest_without_ner(mock_storage):
    """Ingestor with no NER extractor should return an empty scenario."""
    ingestor = DocumentIngestor(storage=mock_storage, ner_extractor=None)
    result = await ingestor.ingest(text="Some text.", scenario_name="empty")

    assert result.graph_id == "graph-001"
    assert len(result.entities) == 0
    assert len(result.relations) == 0
