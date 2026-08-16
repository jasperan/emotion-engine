"""Oracle-backed graph storage using SQLAlchemy async sessions.

Implements the GraphStorage ABC with hybrid vector+keyword search
and episodic agent memory backed by Oracle DB (or any SQLAlchemy-compatible store).
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Optional

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from emotionsim.models.graph import (
    EdgeModel,
    EntityModel,
    GraphModel,
    MemoryEdgeModel,
    MemoryNodeModel,
)
from emotionsim.storage.embedding_service import EmbeddingService
from emotionsim.storage.graph_storage import Edge, Entity, GraphStorage, SearchResult

logger = logging.getLogger(__name__)

# Hybrid search weights
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two float vectors.

    Returns 0.0 for empty, mismatched-length, or zero-norm inputs.
    """
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def _keyword_score(query: str, text: str) -> float:
    """Fraction of query terms found in text (case-insensitive)."""
    if not query or not text:
        return 0.0
    terms = query.lower().split()
    if not terms:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for t in terms if t in text_lower)
    return matches / len(terms)


class OracleGraphStorage(GraphStorage):
    """GraphStorage implementation backed by SQLAlchemy async sessions.

    Works with Oracle DB in production and SQLite for testing.
    Supports hybrid vector + keyword search with configurable weights.
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service

    async def _auto_embed(self, text: str) -> list[float]:
        """Embed text if an embedding service is available, otherwise return empty.

        Any failure (e.g. Ollama not running) degrades gracefully to an empty
        vector so hybrid search falls back to keyword scoring — the simulation
        must never crash because embeddings are unavailable.
        """
        if self.embedding_service is None:
            return []
        try:
            return await self.embedding_service.embed_text(text)
        except Exception:
            logger.debug("Embedding failed, continuing without vector", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Graph CRUD
    # ------------------------------------------------------------------

    async def create_graph(self, name: str, ontology: Optional[dict] = None) -> str:
        graph_id = str(uuid.uuid4())
        graph = GraphModel(
            graph_id=graph_id,
            name=name,
            ontology_json=ontology,
        )
        self.session.add(graph)
        await self.session.flush()
        return graph_id

    async def delete_graph(self, graph_id: str) -> None:
        # Delete in FK-safe order: edges -> entities -> graph
        await self.session.execute(
            delete(EdgeModel).where(EdgeModel.graph_id == graph_id)
        )
        await self.session.execute(
            delete(EntityModel).where(EntityModel.graph_id == graph_id)
        )
        await self.session.execute(
            delete(GraphModel).where(GraphModel.graph_id == graph_id)
        )
        await self.session.flush()

    # ------------------------------------------------------------------
    # Entity / Edge
    # ------------------------------------------------------------------

    async def add_entity(self, graph_id: str, entity: Entity) -> str:
        embedding = entity.embedding
        if not embedding:
            embed_text = f"{entity.name} ({entity.type}): {entity.summary}"
            embedding = await self._auto_embed(embed_text)

        model = EntityModel(
            entity_id=entity.entity_id,
            graph_id=graph_id,
            name=entity.name,
            type=entity.type,
            summary=entity.summary,
            attributes_json=entity.attributes or {},
            embedding_json=embedding,
        )
        self.session.add(model)
        await self.session.flush()
        return entity.entity_id

    async def add_edge(self, graph_id: str, edge: Edge) -> str:
        embedding = edge.embedding
        if not embedding:
            embedding = await self._auto_embed(edge.fact)

        model = EdgeModel(
            edge_id=edge.edge_id,
            graph_id=graph_id,
            source_id=edge.source_id,
            target_id=edge.target_id,
            type=edge.type,
            fact=edge.fact,
            weight=edge.weight,
            embedding_json=embedding,
        )
        self.session.add(model)
        await self.session.flush()
        return edge.edge_id

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        result = await self.session.execute(
            select(EntityModel).where(EntityModel.entity_id == entity_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return Entity(
            entity_id=row.entity_id,
            name=row.name,
            type=row.type,
            summary=row.summary or "",
            attributes=row.attributes_json or {},
            embedding=row.embedding_json or [],
        )

    async def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
        edge_types: Optional[list[str]] = None,
    ) -> tuple[list[Entity], list[Edge]]:
        visited_entities: set[str] = {entity_id}
        all_edges: list[Edge] = []
        frontier: set[str] = {entity_id}

        for _ in range(depth):
            if not frontier:
                break

            stmt = select(EdgeModel).where(
                or_(
                    EdgeModel.source_id.in_(frontier),
                    EdgeModel.target_id.in_(frontier),
                )
            )
            if edge_types:
                stmt = stmt.where(EdgeModel.type.in_(edge_types))

            result = await self.session.execute(stmt)
            edges = result.scalars().all()

            next_frontier: set[str] = set()
            for e in edges:
                edge = Edge(
                    edge_id=e.edge_id,
                    source_id=e.source_id,
                    target_id=e.target_id,
                    type=e.type,
                    fact=e.fact or "",
                    weight=e.weight,
                    embedding=e.embedding_json or [],
                )
                # Avoid duplicate edges
                if not any(ex.edge_id == edge.edge_id for ex in all_edges):
                    all_edges.append(edge)

                # Track neighbor IDs
                for nid in (e.source_id, e.target_id):
                    if nid not in visited_entities:
                        next_frontier.add(nid)
                        visited_entities.add(nid)

            frontier = next_frontier

        # Fetch all neighbor entities (exclude the starting entity)
        neighbor_ids = visited_entities - {entity_id}
        entities: list[Entity] = []
        if neighbor_ids:
            result = await self.session.execute(
                select(EntityModel).where(EntityModel.entity_id.in_(neighbor_ids))
            )
            for row in result.scalars().all():
                entities.append(
                    Entity(
                        entity_id=row.entity_id,
                        name=row.name,
                        type=row.type,
                        summary=row.summary or "",
                        attributes=row.attributes_json or {},
                        embedding=row.embedding_json or [],
                    )
                )

        return entities, all_edges

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        query_embedding: Optional[list[float]] = None,
    ) -> SearchResult:
        if query_embedding is None and self.embedding_service is not None:
            query_embedding = await self._auto_embed(query)

        # Fetch all entities in this graph
        ent_result = await self.session.execute(
            select(EntityModel).where(EntityModel.graph_id == graph_id)
        )
        entity_rows = ent_result.scalars().all()

        # Fetch all edges in this graph
        edge_result = await self.session.execute(
            select(EdgeModel).where(EdgeModel.graph_id == graph_id)
        )
        edge_rows = edge_result.scalars().all()

        # Score entities
        scored_entities: list[tuple[float, Entity]] = []
        for row in entity_rows:
            text = f"{row.name} ({row.type}): {row.summary or ''}"
            vec_score = 0.0
            if query_embedding and row.embedding_json:
                vec_score = _cosine_similarity(query_embedding, row.embedding_json)
            kw_score = _keyword_score(query, text)
            combined = VECTOR_WEIGHT * vec_score + KEYWORD_WEIGHT * kw_score

            entity = Entity(
                entity_id=row.entity_id,
                name=row.name,
                type=row.type,
                summary=row.summary or "",
                attributes=row.attributes_json or {},
                embedding=row.embedding_json or [],
            )
            scored_entities.append((combined, entity))

        # Score edges
        scored_edges: list[tuple[float, Edge]] = []
        for row in edge_rows:
            text = row.fact or ""
            vec_score = 0.0
            if query_embedding and row.embedding_json:
                vec_score = _cosine_similarity(query_embedding, row.embedding_json)
            kw_score = _keyword_score(query, text)
            combined = VECTOR_WEIGHT * vec_score + KEYWORD_WEIGHT * kw_score

            edge = Edge(
                edge_id=row.edge_id,
                source_id=row.source_id,
                target_id=row.target_id,
                type=row.type,
                fact=row.fact or "",
                weight=row.weight,
                embedding=row.embedding_json or [],
            )
            scored_edges.append((combined, edge))

        # Merge, sort, take top-K
        all_scored: list[tuple[float, str, Entity | Edge]] = []
        for score, ent in scored_entities:
            all_scored.append((score, "entity", ent))
        for score, edg in scored_edges:
            all_scored.append((score, "edge", edg))

        all_scored.sort(key=lambda x: x[0], reverse=True)
        top_k = all_scored[:limit]

        result_entities: list[Entity] = []
        result_edges: list[Edge] = []
        facts: list[str] = []

        for score, kind, item in top_k:
            if kind == "entity":
                result_entities.append(item)  # type: ignore[arg-type]
                ent_item: Entity = item  # type: ignore[assignment]
                if ent_item.summary:
                    facts.append(f"{ent_item.name}: {ent_item.summary}")
            else:
                result_edges.append(item)  # type: ignore[arg-type]
                edge_item: Edge = item  # type: ignore[assignment]
                if edge_item.fact:
                    facts.append(edge_item.fact)

        return SearchResult(
            facts=facts,
            entities=result_entities,
            edges=result_edges,
            query=query,
            total_count=len(top_k),
        )

    # ------------------------------------------------------------------
    # Agent Memory
    # ------------------------------------------------------------------

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
        if embedding is None:
            embedding = await self._auto_embed(content)

        memory_id = str(uuid.uuid4())
        memory = MemoryNodeModel(
            memory_id=memory_id,
            run_id=run_id,
            agent_id=agent_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            emotional_valence=emotional_valence,
            step_number=step_number,
            embedding_json=embedding or [],
        )
        self.session.add(memory)
        await self.session.flush()

        # Create links to entities
        if linked_entity_ids:
            for eid in linked_entity_ids:
                link = MemoryEdgeModel(
                    edge_id=str(uuid.uuid4()),
                    source_id=memory_id,
                    target_id=eid,
                    type="linked_entity",
                )
                self.session.add(link)
            await self.session.flush()

        return memory_id

    async def search_memories(
        self,
        run_id: str,
        agent_id: str,
        query: str,
        limit: int = 5,
        query_embedding: Optional[list[float]] = None,
    ) -> list[dict]:
        if query_embedding is None and self.embedding_service is not None:
            query_embedding = await self._auto_embed(query)

        result = await self.session.execute(
            select(MemoryNodeModel).where(
                MemoryNodeModel.run_id == run_id,
                MemoryNodeModel.agent_id == agent_id,
            )
        )
        rows = result.scalars().all()

        scored: list[tuple[float, MemoryNodeModel]] = []
        for row in rows:
            vec_score = 0.0
            if query_embedding and row.embedding_json:
                vec_score = _cosine_similarity(query_embedding, row.embedding_json)
            kw_score = _keyword_score(query, row.content)
            combined = VECTOR_WEIGHT * vec_score + KEYWORD_WEIGHT * kw_score
            scored.append((combined, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_k = scored[:limit]

        return [
            {
                "memory_id": row.memory_id,
                "content": row.content,
                "memory_type": row.memory_type,
                "importance": row.importance,
                "emotional_valence": row.emotional_valence,
                "step_number": row.step_number,
                "relevance_score": score,
            }
            for score, row in top_k
        ]
