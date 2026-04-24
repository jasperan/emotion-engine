"""Tests for GraphMemory: graph-backed agent memory with hybrid search recall."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from emotionsim.agents.graph_memory import GraphMemory
from emotionsim.storage.graph_storage import Edge, Entity, SearchResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_embedding_service():
    svc = AsyncMock()
    svc.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return svc


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.add_memory = AsyncMock(return_value="mem-001")
    storage.search_memories = AsyncMock(return_value=[])
    storage.search = AsyncMock(
        return_value=SearchResult(
            facts=[], entities=[], edges=[], query="", total_count=0
        )
    )
    storage.get_neighbors = AsyncMock(return_value=([], []))
    return storage


@pytest.fixture
def graph_memory(mock_storage, mock_embedding_service):
    return GraphMemory(
        agent_id="agent-1",
        agent_name="Dr. Chen",
        run_id="run-42",
        graph_id="graph-99",
        storage=mock_storage,
        embedding_service=mock_embedding_service,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_memory(graph_memory, mock_storage, mock_embedding_service):
    """store() should embed content and call storage.add_memory with correct args."""
    memory_id = await graph_memory.store(
        content="The bridge is collapsing",
        memory_type="observation",
        importance=8,
        emotional_valence=-0.7,
        step_number=5,
        linked_entity_ids=["entity-a", "entity-b"],
    )

    assert memory_id == "mem-001"
    mock_embedding_service.embed_text.assert_awaited_once_with(
        "The bridge is collapsing"
    )
    mock_storage.add_memory.assert_awaited_once_with(
        run_id="run-42",
        agent_id="agent-1",
        content="The bridge is collapsing",
        memory_type="observation",
        importance=8,
        emotional_valence=-0.7,
        step_number=5,
        embedding=[0.1, 0.2, 0.3],
        linked_entity_ids=["entity-a", "entity-b"],
    )


@pytest.mark.asyncio
async def test_store_memory_defaults(graph_memory, mock_storage):
    """store() with default params should pass sensible defaults to storage."""
    await graph_memory.store(content="Found medical supplies")

    mock_storage.add_memory.assert_awaited_once()
    call_kwargs = mock_storage.add_memory.call_args.kwargs
    assert call_kwargs["memory_type"] == "observation"
    assert call_kwargs["importance"] == 5
    assert call_kwargs["emotional_valence"] == 0.0
    assert call_kwargs["step_number"] == 0
    assert call_kwargs["linked_entity_ids"] is None


@pytest.mark.asyncio
async def test_recall(graph_memory, mock_storage, mock_embedding_service):
    """recall() should embed the query and call storage.search_memories."""
    mock_storage.search_memories = AsyncMock(
        return_value=[
            {"content": "The bridge is collapsing", "step_number": 5, "importance": 8},
            {"content": "Found medical supplies", "step_number": 3, "importance": 4},
        ]
    )

    results = await graph_memory.recall("bridge", limit=3)

    assert len(results) == 2
    assert results[0]["content"] == "The bridge is collapsing"
    mock_embedding_service.embed_text.assert_awaited_with("bridge")
    mock_storage.search_memories.assert_awaited_once_with(
        run_id="run-42",
        agent_id="agent-1",
        query="bridge",
        limit=3,
        query_embedding=[0.1, 0.2, 0.3],
    )


@pytest.mark.asyncio
async def test_recall_no_embedding_service(mock_storage):
    """recall() without an embedding service should pass None for query_embedding."""
    gm = GraphMemory(
        agent_id="agent-1",
        agent_name="Dr. Chen",
        run_id="run-42",
        graph_id="graph-99",
        storage=mock_storage,
        embedding_service=None,
    )
    mock_storage.search_memories = AsyncMock(return_value=[])

    results = await gm.recall("bridge")

    assert results == []
    mock_storage.search_memories.assert_awaited_once_with(
        run_id="run-42",
        agent_id="agent-1",
        query="bridge",
        limit=5,
        query_embedding=None,
    )


@pytest.mark.asyncio
async def test_recall_graph_context(graph_memory, mock_storage):
    """recall_graph_context() should collect edge facts and neighbor names."""
    mock_storage.get_neighbors = AsyncMock(
        return_value=(
            [
                Entity(name="Hospital", type="location"),
                Entity(name="Dr. Chen", type="person"),
            ],
            [
                Edge(
                    source_id="e1",
                    target_id="e2",
                    type="works_at",
                    fact="Dr. Chen works at the hospital",
                ),
            ],
        )
    )

    result = await graph_memory.recall_graph_context(["entity-x"])

    assert "Dr. Chen works at the hospital" in result
    assert "Hospital (location)" in result
    assert "Dr. Chen (person)" in result
    mock_storage.get_neighbors.assert_awaited_once_with(
        entity_id="entity-x",
        depth=1,
        edge_types=None,
    )


@pytest.mark.asyncio
async def test_recall_graph_context_deduplicates(graph_memory, mock_storage):
    """recall_graph_context() should not repeat the same fact or neighbor."""
    entity = Entity(name="Hospital", type="location")
    edge = Edge(
        source_id="e1",
        target_id="e2",
        type="near",
        fact="Hospital is near the river",
    )
    # Both entity IDs return the same neighbor/edge.
    mock_storage.get_neighbors = AsyncMock(return_value=([entity], [edge]))

    result = await graph_memory.recall_graph_context(["id-a", "id-b"])

    # Should appear only once despite two entity lookups returning identical data.
    assert result.count("Hospital is near the river") == 1
    assert result.count("Hospital (location)") == 1


@pytest.mark.asyncio
async def test_build_context(graph_memory, mock_storage, mock_embedding_service):
    """build_context() should produce formatted string with memories and facts."""
    mock_storage.search_memories = AsyncMock(
        return_value=[
            {
                "content": "The bridge is collapsing",
                "step_number": 5,
                "importance": 8,
            },
            {
                "content": "Found medical supplies",
                "step_number": 3,
                "importance": 4,
            },
        ]
    )
    mock_storage.search = AsyncMock(
        return_value=SearchResult(
            facts=["Dr. Chen works at the hospital"],
            entities=[],
            edges=[],
            query="flood rising",
            total_count=1,
        )
    )

    context = await graph_memory.build_context("flood rising", max_memories=5, max_graph_facts=3)

    # Memory section: high importance gets "!" prefix.
    assert "Relevant memories:" in context
    assert "![Step 5] The bridge is collapsing" in context
    # Normal importance: no "!" prefix.
    assert "- [Step 3] Found medical supplies" in context
    # Graph facts section.
    assert "Known facts:" in context
    assert "Dr. Chen works at the hospital" in context


@pytest.mark.asyncio
async def test_build_context_empty(graph_memory, mock_storage):
    """build_context() with no memories or facts returns an empty string."""
    mock_storage.search_memories = AsyncMock(return_value=[])
    mock_storage.search = AsyncMock(
        return_value=SearchResult(
            facts=[], entities=[], edges=[], query="nothing", total_count=0
        )
    )

    context = await graph_memory.build_context("nothing here")
    assert context == ""


@pytest.mark.asyncio
async def test_build_context_memories_only(graph_memory, mock_storage):
    """build_context() with memories but no graph facts omits Known facts section."""
    mock_storage.search_memories = AsyncMock(
        return_value=[
            {"content": "Water level rising", "step_number": 1, "importance": 6},
        ]
    )
    mock_storage.search = AsyncMock(
        return_value=SearchResult(
            facts=[], entities=[], edges=[], query="water", total_count=0
        )
    )

    context = await graph_memory.build_context("water")
    assert "Relevant memories:" in context
    assert "Known facts:" not in context
