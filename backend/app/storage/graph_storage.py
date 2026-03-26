"""Abstract GraphStorage interface and supporting data classes for graph-based agent memory."""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Entity:
    """A node in the knowledge graph representing a person, place, concept, etc."""

    name: str
    type: str
    summary: str = ""
    attributes: dict = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "type": self.type,
            "summary": self.summary,
            "attributes": self.attributes,
            "embedding": self.embedding,
        }


@dataclass
class Edge:
    """A directed relationship between two entities in the knowledge graph."""

    source_id: str
    target_id: str
    type: str
    fact: str = ""
    weight: float = 1.0
    embedding: list[float] = field(default_factory=list)
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type,
            "fact": self.fact,
            "weight": self.weight,
            "embedding": self.embedding,
        }


@dataclass
class SearchResult:
    """Results from a graph search query."""

    facts: list[str]
    entities: list[Entity]
    edges: list[Edge]
    query: str
    total_count: int

    def to_text(self) -> str:
        """Format search results as a readable string for LLM context injection."""
        lines: list[str] = []
        lines.append(f"Graph search: \"{self.query}\" ({self.total_count} results)")

        if self.facts:
            lines.append("\nFacts:")
            for fact in self.facts:
                lines.append(f"  - {fact}")

        if self.entities:
            lines.append("\nEntities:")
            for entity in self.entities:
                desc = f"  - {entity.name} ({entity.type})"
                if entity.summary:
                    desc += f": {entity.summary}"
                lines.append(desc)

        if self.edges:
            lines.append("\nRelationships:")
            for edge in self.edges:
                desc = f"  - [{edge.type}] {edge.source_id} -> {edge.target_id}"
                if edge.fact:
                    desc += f" ({edge.fact})"
                lines.append(desc)

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "facts": self.facts,
            "entities": [e.to_dict() for e in self.entities],
            "edges": [e.to_dict() for e in self.edges],
            "query": self.query,
            "total_count": self.total_count,
        }


class GraphStorage(ABC):
    """Abstract base class for graph-based storage backends.

    Implementations handle knowledge graphs (entities + edges) and
    episodic agent memory nodes, backed by Oracle DB or other stores.
    """

    @abstractmethod
    async def create_graph(self, name: str, ontology: Optional[dict] = None) -> str:
        """Create a new named graph. Returns the graph_id."""
        ...

    @abstractmethod
    async def delete_graph(self, graph_id: str) -> None:
        """Delete a graph and all its entities/edges."""
        ...

    @abstractmethod
    async def add_entity(self, graph_id: str, entity: Entity) -> str:
        """Add an entity to a graph. Returns the entity_id."""
        ...

    @abstractmethod
    async def add_edge(self, graph_id: str, edge: Edge) -> str:
        """Add an edge between two entities. Returns the edge_id."""
        ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Retrieve an entity by ID, or None if not found."""
        ...

    @abstractmethod
    async def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
        edge_types: Optional[list[str]] = None,
    ) -> tuple[list[Entity], list[Edge]]:
        """Get neighboring entities and connecting edges up to a given depth."""
        ...

    @abstractmethod
    async def search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        query_embedding: Optional[list[float]] = None,
    ) -> SearchResult:
        """Search for entities/edges matching a query string or embedding."""
        ...

    @abstractmethod
    async def add_memory(
        self,
        run_id: str,
        agent_id: str,
        content: str,
        memory_type: str,
        importance: int,
        emotional_valence: float,
        step_number: int,
        embedding: Optional[list[float]] = None,
        linked_entity_ids: Optional[list[str]] = None,
    ) -> str:
        """Store an episodic memory node for an agent. Returns the memory_id."""
        ...

    @abstractmethod
    async def search_memories(
        self,
        run_id: str,
        agent_id: str,
        query: str,
        limit: int = 5,
        query_embedding: Optional[list[float]] = None,
    ) -> list[dict]:
        """Search an agent's memories by query text or embedding."""
        ...
