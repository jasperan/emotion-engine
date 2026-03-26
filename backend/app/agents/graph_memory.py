"""Graph-backed agent memory combining episodic recall with knowledge graph context."""

from __future__ import annotations

from typing import Optional

from app.storage.embedding_service import EmbeddingService
from app.storage.graph_storage import GraphStorage


class GraphMemory:
    """Hybrid memory layer for a single agent.

    Stores episodic memories (observations, reflections, decisions) as
    embedding-indexed nodes and retrieves them alongside knowledge graph
    facts for richer LLM context.
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        run_id: str,
        graph_id: str,
        storage: GraphStorage,
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.run_id = run_id
        self.graph_id = graph_id
        self.storage = storage
        self.embedding_service = embedding_service

    async def _embed(self, text: str) -> Optional[list[float]]:
        """Embed text if an embedding service is available."""
        if self.embedding_service is None:
            return None
        return await self.embedding_service.embed_text(text)

    async def store(
        self,
        content: str,
        memory_type: str = "observation",
        importance: int = 5,
        emotional_valence: float = 0.0,
        step_number: int = 0,
        linked_entity_ids: Optional[list[str]] = None,
    ) -> str:
        """Embed content and persist it as an episodic memory node.

        Returns the memory_id assigned by the storage backend.
        """
        embedding = await self._embed(content)
        return await self.storage.add_memory(
            run_id=self.run_id,
            agent_id=self.agent_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            emotional_valence=emotional_valence,
            step_number=step_number,
            embedding=embedding,
            linked_entity_ids=linked_entity_ids,
        )

    async def recall(self, query: str, limit: int = 5) -> list[dict]:
        """Retrieve the most relevant memories for a query."""
        query_embedding = await self._embed(query)
        return await self.storage.search_memories(
            run_id=self.run_id,
            agent_id=self.agent_id,
            query=query,
            limit=limit,
            query_embedding=query_embedding,
        )

    async def recall_graph_context(self, entity_ids: list[str]) -> str:
        """Get knowledge graph context for a set of nearby entities.

        For each entity, fetches immediate neighbors (depth 1, limit 5)
        and collects edge facts and neighbor names.

        Returns a newline-joined string of facts.
        """
        facts: list[str] = []
        seen_facts: set[str] = set()

        for entity_id in entity_ids:
            neighbors, edges = await self.storage.get_neighbors(
                entity_id=entity_id,
                depth=1,
                edge_types=None,
            )
            for edge in edges:
                if edge.fact and edge.fact not in seen_facts:
                    seen_facts.add(edge.fact)
                    facts.append(edge.fact)
            for neighbor in neighbors:
                name_fact = f"{neighbor.name} ({neighbor.type})"
                if name_fact not in seen_facts:
                    seen_facts.add(name_fact)
                    facts.append(name_fact)

        return "\n".join(facts)

    async def build_context(
        self,
        current_situation: str,
        max_memories: int = 5,
        max_graph_facts: int = 3,
    ) -> str:
        """Build a formatted context string for LLM prompts.

        Combines recalled episodic memories with knowledge graph search
        results into a single block of text.
        """
        # Recall memories relevant to the current situation.
        memories = await self.recall(current_situation, limit=max_memories)

        # Search the knowledge graph for relevant facts.
        query_embedding = await self._embed(current_situation)
        graph_results = await self.storage.search(
            graph_id=self.graph_id,
            query=current_situation,
            limit=max_graph_facts,
            query_embedding=query_embedding,
        )

        # Format memories.
        memory_lines: list[str] = []
        for mem in memories:
            step = mem.get("step_number", "?")
            content = mem.get("content", "")
            importance = mem.get("importance", 0)
            prefix = "!" if importance >= 7 else ""
            memory_lines.append(f"- {prefix}[Step {step}] {content}")

        # Format graph facts.
        fact_lines: list[str] = []
        for fact in graph_results.facts:
            fact_lines.append(f"- {fact}")

        sections: list[str] = []
        if memory_lines:
            sections.append("Relevant memories:\n" + "\n".join(memory_lines))
        if fact_lines:
            sections.append("Known facts:\n" + "\n".join(fact_lines))

        return "\n\n".join(sections)
