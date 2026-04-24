"""Tests for GraphStorage ABC, Entity, Edge, and SearchResult data classes."""
import uuid

import pytest

from emotionsim.storage.graph_storage import Edge, Entity, GraphStorage, SearchResult


# ---------------------------------------------------------------------------
# Entity tests
# ---------------------------------------------------------------------------

class TestEntity:
    def test_defaults(self):
        e = Entity(name="Alice", type="person")
        assert e.name == "Alice"
        assert e.type == "person"
        assert e.summary == ""
        assert e.attributes == {}
        assert e.embedding == []
        # auto-generated UUID
        uuid.UUID(e.entity_id)  # raises if invalid

    def test_custom_fields(self):
        e = Entity(
            name="Shelter",
            type="location",
            summary="A safe place",
            attributes={"capacity": 20},
            embedding=[0.1, 0.2],
            entity_id="custom-id",
        )
        assert e.entity_id == "custom-id"
        assert e.attributes["capacity"] == 20
        assert e.embedding == [0.1, 0.2]

    def test_to_dict(self):
        e = Entity(name="Bob", type="person", entity_id="e-1")
        d = e.to_dict()
        assert d["entity_id"] == "e-1"
        assert d["name"] == "Bob"
        assert d["type"] == "person"
        assert d["summary"] == ""
        assert d["attributes"] == {}
        assert d["embedding"] == []

    def test_mutable_defaults_independent(self):
        """Each Entity instance should have its own mutable containers."""
        e1 = Entity(name="A", type="x")
        e2 = Entity(name="B", type="y")
        e1.attributes["key"] = "val"
        assert "key" not in e2.attributes


# ---------------------------------------------------------------------------
# Edge tests
# ---------------------------------------------------------------------------

class TestEdge:
    def test_defaults(self):
        e = Edge(source_id="s1", target_id="t1", type="knows")
        assert e.source_id == "s1"
        assert e.target_id == "t1"
        assert e.type == "knows"
        assert e.fact == ""
        assert e.weight == 1.0
        assert e.embedding == []
        uuid.UUID(e.edge_id)

    def test_custom_fields(self):
        e = Edge(
            source_id="s1",
            target_id="t1",
            type="trusts",
            fact="Alice trusts Bob",
            weight=0.8,
            embedding=[0.5],
            edge_id="edge-custom",
        )
        assert e.edge_id == "edge-custom"
        assert e.fact == "Alice trusts Bob"
        assert e.weight == 0.8

    def test_to_dict(self):
        e = Edge(source_id="s1", target_id="t1", type="helps", edge_id="e-1")
        d = e.to_dict()
        assert d["edge_id"] == "e-1"
        assert d["source_id"] == "s1"
        assert d["target_id"] == "t1"
        assert d["type"] == "helps"
        assert d["fact"] == ""
        assert d["weight"] == 1.0


# ---------------------------------------------------------------------------
# SearchResult tests
# ---------------------------------------------------------------------------

class TestSearchResult:
    def _sample_result(self) -> SearchResult:
        entities = [
            Entity(name="Alice", type="person", summary="A brave soul", entity_id="e1"),
            Entity(name="Shelter", type="location", entity_id="e2"),
        ]
        edges = [
            Edge(source_id="e1", target_id="e2", type="located_at", fact="Alice is at the shelter", edge_id="ed1"),
        ]
        return SearchResult(
            facts=["Alice found the shelter", "Water level is rising"],
            entities=entities,
            edges=edges,
            query="Where is Alice?",
            total_count=3,
        )

    def test_creation(self):
        sr = self._sample_result()
        assert sr.query == "Where is Alice?"
        assert sr.total_count == 3
        assert len(sr.facts) == 2
        assert len(sr.entities) == 2
        assert len(sr.edges) == 1

    def test_to_text_contains_query(self):
        sr = self._sample_result()
        text = sr.to_text()
        assert "Where is Alice?" in text
        assert "3 results" in text

    def test_to_text_contains_facts(self):
        sr = self._sample_result()
        text = sr.to_text()
        assert "Alice found the shelter" in text
        assert "Water level is rising" in text

    def test_to_text_contains_entities(self):
        sr = self._sample_result()
        text = sr.to_text()
        assert "Alice (person): A brave soul" in text
        assert "Shelter (location)" in text

    def test_to_text_contains_edges(self):
        sr = self._sample_result()
        text = sr.to_text()
        assert "[located_at]" in text
        assert "Alice is at the shelter" in text

    def test_to_text_empty(self):
        sr = SearchResult(facts=[], entities=[], edges=[], query="nothing", total_count=0)
        text = sr.to_text()
        assert "nothing" in text
        assert "0 results" in text
        # Should not contain section headers when empty
        assert "Facts:" not in text
        assert "Entities:" not in text
        assert "Relationships:" not in text

    def test_to_dict(self):
        sr = self._sample_result()
        d = sr.to_dict()
        assert d["query"] == "Where is Alice?"
        assert d["total_count"] == 3
        assert len(d["entities"]) == 2
        assert len(d["edges"]) == 1
        assert d["entities"][0]["name"] == "Alice"


# ---------------------------------------------------------------------------
# GraphStorage ABC tests
# ---------------------------------------------------------------------------

class TestGraphStorageABC:
    def test_cannot_instantiate(self):
        """GraphStorage is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            GraphStorage()

    def test_subclass_must_implement_all(self):
        """A subclass missing any abstract method still can't be instantiated."""

        class Partial(GraphStorage):
            async def create_graph(self, name, ontology=None):
                return "g1"

        with pytest.raises(TypeError):
            Partial()

    def test_complete_subclass_works(self):
        """A subclass that implements every abstract method can be instantiated."""

        class Complete(GraphStorage):
            async def create_graph(self, name, ontology=None):
                return "g1"

            async def delete_graph(self, graph_id):
                pass

            async def add_entity(self, graph_id, entity):
                return entity.entity_id

            async def add_edge(self, graph_id, edge):
                return edge.edge_id

            async def get_entity(self, entity_id):
                return None

            async def get_neighbors(self, entity_id, depth=1, edge_types=None):
                return ([], [])

            async def search(self, graph_id, query, limit=10, query_embedding=None):
                return SearchResult([], [], [], query, 0)

            async def add_memory(self, run_id, agent_id, content, memory_type, importance, emotional_valence, step_number, embedding=None, linked_entity_ids=None):
                return "m1"

            async def search_memories(self, run_id, agent_id, query, limit=5, query_embedding=None):
                return []

        instance = Complete()
        assert instance is not None
