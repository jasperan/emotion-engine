"""Tests for OracleGraphStorage using SQLite in-memory backend."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.storage.oracle_graph_storage import OracleGraphStorage, _cosine_similarity
from app.storage.graph_storage import Entity, Edge
from app.storage.embedding_service import EmbeddingService


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service that returns deterministic vectors."""
    svc = MagicMock(spec=EmbeddingService)

    async def _embed(text: str) -> list[float]:
        # Produce a simple deterministic embedding based on text length
        # so different texts get different vectors but same text = same vector
        base = len(text) % 10
        return [float(base) / 10.0] * 8

    svc.embed_text = AsyncMock(side_effect=_embed)
    svc.embed_batch = AsyncMock(return_value=[[0.5] * 8])
    return svc


@pytest.fixture
def storage(db_session, mock_embedding_service):
    """Create an OracleGraphStorage instance with mock embedding service."""
    return OracleGraphStorage(session=db_session, embedding_service=mock_embedding_service)


@pytest.fixture
def storage_no_embed(db_session):
    """Create an OracleGraphStorage instance without embedding service."""
    return OracleGraphStorage(session=db_session, embedding_service=None)


# ------------------------------------------------------------------
# _cosine_similarity
# ------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-9

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_norm(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_none_input(self):
        assert _cosine_similarity([], [1.0]) == 0.0


# ------------------------------------------------------------------
# Graph CRUD
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_graph(storage):
    graph_id = await storage.create_graph("test-graph", {"types": ["person", "place"]})
    assert graph_id
    assert isinstance(graph_id, str)
    assert len(graph_id) == 36  # UUID format


@pytest.mark.asyncio
async def test_create_graph_no_ontology(storage):
    graph_id = await storage.create_graph("minimal-graph")
    assert graph_id


# ------------------------------------------------------------------
# Entity roundtrip
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_and_get_entity(storage):
    graph_id = await storage.create_graph("entity-test")

    entity = Entity(
        name="Alice",
        type="person",
        summary="A brave survivor",
        attributes={"age": 30},
    )
    eid = await storage.add_entity(graph_id, entity)
    assert eid == entity.entity_id

    fetched = await storage.get_entity(eid)
    assert fetched is not None
    assert fetched.name == "Alice"
    assert fetched.type == "person"
    assert fetched.summary == "A brave survivor"
    assert fetched.attributes == {"age": 30}


@pytest.mark.asyncio
async def test_get_entity_not_found(storage):
    result = await storage.get_entity("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_add_entity_auto_embeds(storage, mock_embedding_service):
    graph_id = await storage.create_graph("embed-test")
    entity = Entity(name="Bob", type="person", summary="A healer")
    await storage.add_entity(graph_id, entity)

    # The embedding service should have been called
    mock_embedding_service.embed_text.assert_called()


@pytest.mark.asyncio
async def test_add_entity_no_embed_service(storage_no_embed):
    graph_id = await storage_no_embed.create_graph("no-embed")
    entity = Entity(name="Carol", type="person", summary="Engineer")
    eid = await storage_no_embed.add_entity(graph_id, entity)

    fetched = await storage_no_embed.get_entity(eid)
    assert fetched is not None
    assert fetched.name == "Carol"
    # No embedding service, so embedding should be empty
    assert fetched.embedding == []


# ------------------------------------------------------------------
# Edge
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_edge(storage):
    graph_id = await storage.create_graph("edge-test")

    e1 = Entity(name="Alice", type="person", summary="Leader")
    e2 = Entity(name="Bob", type="person", summary="Healer")
    await storage.add_entity(graph_id, e1)
    await storage.add_entity(graph_id, e2)

    edge = Edge(
        source_id=e1.entity_id,
        target_id=e2.entity_id,
        type="trusts",
        fact="Alice trusts Bob after the flood rescue",
        weight=0.9,
    )
    edge_id = await storage.add_edge(graph_id, edge)
    assert edge_id == edge.edge_id


# ------------------------------------------------------------------
# Neighbors
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_neighbors(storage):
    graph_id = await storage.create_graph("neighbor-test")

    alice = Entity(name="Alice", type="person", summary="Leader")
    bob = Entity(name="Bob", type="person", summary="Healer")
    carol = Entity(name="Carol", type="person", summary="Engineer")
    await storage.add_entity(graph_id, alice)
    await storage.add_entity(graph_id, bob)
    await storage.add_entity(graph_id, carol)

    edge1 = Edge(
        source_id=alice.entity_id,
        target_id=bob.entity_id,
        type="trusts",
        fact="Alice trusts Bob",
    )
    edge2 = Edge(
        source_id=carol.entity_id,
        target_id=alice.entity_id,
        type="helps",
        fact="Carol helps Alice",
    )
    await storage.add_edge(graph_id, edge1)
    await storage.add_edge(graph_id, edge2)

    entities, edges = await storage.get_neighbors(alice.entity_id)
    assert len(entities) == 2  # Bob and Carol
    assert len(edges) == 2
    neighbor_names = {e.name for e in entities}
    assert "Bob" in neighbor_names
    assert "Carol" in neighbor_names


@pytest.mark.asyncio
async def test_get_neighbors_with_edge_type_filter(storage):
    graph_id = await storage.create_graph("filter-test")

    alice = Entity(name="Alice", type="person", summary="Leader")
    bob = Entity(name="Bob", type="person", summary="Healer")
    carol = Entity(name="Carol", type="person", summary="Engineer")
    await storage.add_entity(graph_id, alice)
    await storage.add_entity(graph_id, bob)
    await storage.add_entity(graph_id, carol)

    await storage.add_edge(
        graph_id,
        Edge(source_id=alice.entity_id, target_id=bob.entity_id, type="trusts", fact="trust"),
    )
    await storage.add_edge(
        graph_id,
        Edge(source_id=alice.entity_id, target_id=carol.entity_id, type="dislikes", fact="dislike"),
    )

    entities, edges = await storage.get_neighbors(alice.entity_id, edge_types=["trusts"])
    assert len(entities) == 1
    assert entities[0].name == "Bob"
    assert len(edges) == 1


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_results(storage):
    graph_id = await storage.create_graph("search-test")

    await storage.add_entity(
        graph_id,
        Entity(name="Flood Zone", type="location", summary="A dangerous flooded area"),
    )
    await storage.add_entity(
        graph_id,
        Entity(name="Alice", type="person", summary="Brave flood survivor"),
    )
    await storage.add_entity(
        graph_id,
        Entity(name="Shelter", type="location", summary="A safe high ground"),
    )

    result = await storage.search(graph_id, "flood", limit=10)

    assert result.query == "flood"
    assert result.total_count > 0
    # At least the entities mentioning "flood" should appear
    names = [e.name for e in result.entities]
    assert "Flood Zone" in names or "Alice" in names


@pytest.mark.asyncio
async def test_search_with_explicit_embedding(storage):
    graph_id = await storage.create_graph("embed-search")

    await storage.add_entity(
        graph_id,
        Entity(name="Test", type="thing", summary="Test entity", embedding=[0.5] * 8),
    )

    # Pass a query embedding directly
    result = await storage.search(
        graph_id, "test", limit=5, query_embedding=[0.5] * 8
    )
    assert result.total_count > 0


@pytest.mark.asyncio
async def test_search_empty_graph(storage):
    graph_id = await storage.create_graph("empty-graph")
    result = await storage.search(graph_id, "anything")
    assert result.total_count == 0
    assert result.entities == []
    assert result.edges == []


# ------------------------------------------------------------------
# Memory
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_and_search_memories(storage):
    run_id = "run-001"
    agent_id = "agent-001"

    mid = await storage.add_memory(
        run_id=run_id,
        agent_id=agent_id,
        content="I saw the water rising at the bridge",
        memory_type="observation",
        importance=7,
        emotional_valence=-0.5,
        step_number=3,
    )
    assert mid
    assert isinstance(mid, str)

    await storage.add_memory(
        run_id=run_id,
        agent_id=agent_id,
        content="Alice helped me carry supplies to higher ground",
        memory_type="interaction",
        importance=8,
        emotional_valence=0.6,
        step_number=5,
    )

    results = await storage.search_memories(run_id, agent_id, "water rising")
    assert len(results) > 0
    assert "memory_id" in results[0]
    assert "content" in results[0]
    assert "memory_type" in results[0]
    assert "importance" in results[0]
    assert "emotional_valence" in results[0]
    assert "step_number" in results[0]
    assert "relevance_score" in results[0]


@pytest.mark.asyncio
async def test_add_memory_with_linked_entities(storage):
    graph_id = await storage.create_graph("memory-link-test")
    entity = Entity(name="Bridge", type="location", summary="Old stone bridge")
    await storage.add_entity(graph_id, entity)

    mid = await storage.add_memory(
        run_id="run-002",
        agent_id="agent-002",
        content="The bridge collapsed under the flood waters",
        memory_type="observation",
        importance=9,
        emotional_valence=-0.8,
        step_number=7,
        linked_entity_ids=[entity.entity_id],
    )
    assert mid


@pytest.mark.asyncio
async def test_search_memories_empty(storage):
    results = await storage.search_memories("no-run", "no-agent", "anything")
    assert results == []


@pytest.mark.asyncio
async def test_search_memories_different_agents(storage):
    """Memories for one agent shouldn't appear in another agent's search."""
    run_id = "run-003"

    await storage.add_memory(
        run_id=run_id,
        agent_id="agent-A",
        content="Secret observation by agent A",
        memory_type="observation",
        importance=5,
        emotional_valence=0.0,
        step_number=1,
    )
    await storage.add_memory(
        run_id=run_id,
        agent_id="agent-B",
        content="Secret observation by agent B",
        memory_type="observation",
        importance=5,
        emotional_valence=0.0,
        step_number=1,
    )

    results_a = await storage.search_memories(run_id, "agent-A", "observation")
    results_b = await storage.search_memories(run_id, "agent-B", "observation")

    assert len(results_a) == 1
    assert len(results_b) == 1
    assert results_a[0]["content"] == "Secret observation by agent A"
    assert results_b[0]["content"] == "Secret observation by agent B"


# ------------------------------------------------------------------
# Delete graph cascading
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_graph_cleans_everything(storage):
    graph_id = await storage.create_graph("delete-test")

    e1 = Entity(name="Alice", type="person", summary="Leader")
    e2 = Entity(name="Bob", type="person", summary="Healer")
    await storage.add_entity(graph_id, e1)
    await storage.add_entity(graph_id, e2)

    edge = Edge(
        source_id=e1.entity_id,
        target_id=e2.entity_id,
        type="trusts",
        fact="Alice trusts Bob",
    )
    await storage.add_edge(graph_id, edge)

    # Verify they exist
    assert await storage.get_entity(e1.entity_id) is not None
    assert await storage.get_entity(e2.entity_id) is not None

    await storage.delete_graph(graph_id)

    # Everything should be gone
    assert await storage.get_entity(e1.entity_id) is None
    assert await storage.get_entity(e2.entity_id) is None

    # Search on deleted graph returns empty
    result = await storage.search(graph_id, "anything")
    assert result.total_count == 0
