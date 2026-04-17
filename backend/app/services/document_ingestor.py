"""Document ingestion pipeline: text -> NER/RE extraction -> graph storage."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.storage.embedding_service import EmbeddingService
from app.storage.graph_storage import Edge, Entity, GraphStorage
from app.storage.ner_extractor import Extraction, NERExtractor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default ontology
# ---------------------------------------------------------------------------

DEFAULT_ONTOLOGY: dict[str, Any] = {
    "entity_types": [
        "person",
        "location",
        "organization",
        "hazard",
        "resource",
        "vehicle",
        "event",
        "object",
    ],
    "relation_types": [
        "located_at",
        "works_at",
        "knows",
        "trusts",
        "member_of",
        "caused_by",
        "affects",
        "owns",
        "near",
        "blocks",
    ],
}

# ---------------------------------------------------------------------------
# IngestedScenario dataclass
# ---------------------------------------------------------------------------


@dataclass
class IngestedScenario:
    """Result of ingesting a document into a knowledge graph."""

    graph_id: str
    entities: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)

    def get_person_entities(self) -> list[dict]:
        """Return entities whose type is 'person'."""
        return [e for e in self.entities if e.get("type") == "person"]

    def get_location_entities(self) -> list[dict]:
        """Return entities whose type is 'location'."""
        return [e for e in self.entities if e.get("type") == "location"]

    def get_hazard_entities(self) -> list[dict]:
        """Return entities whose type is 'hazard'."""
        return [e for e in self.entities if e.get("type") == "hazard"]


# ---------------------------------------------------------------------------
# Text chunking helper
# ---------------------------------------------------------------------------

_MAX_CHUNK_CHARS = 2000


def _chunk_text(text: str) -> list[str]:
    """Split *text* into paragraph-based chunks, each at most _MAX_CHUNK_CHARS."""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If a single paragraph exceeds the limit, hard-split it.
        if len(para) > _MAX_CHUNK_CHARS:
            if current:
                chunks.append(current)
                current = ""
            # Split by sentences or just by char limit.
            while len(para) > _MAX_CHUNK_CHARS:
                chunks.append(para[:_MAX_CHUNK_CHARS])
                para = para[_MAX_CHUNK_CHARS:]
            if para:
                current = para
            continue

        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > _MAX_CHUNK_CHARS:
            chunks.append(current)
            current = para
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# DocumentIngestor
# ---------------------------------------------------------------------------


class DocumentIngestor:
    """Ingests free-text documents into a knowledge graph via NER/RE extraction.

    Pipeline:
      1. Create graph via storage.create_graph
      2. Chunk text into paragraphs (max 2000 chars per chunk)
      3. For each chunk, call NER extractor
      4. Deduplicate entities by name
      5. Store entities in graph (storage.add_entity)
      6. Store relations as edges (storage.add_edge), skip if source/target not found
      7. Return IngestedScenario
    """

    def __init__(
        self,
        storage: GraphStorage,
        ner_extractor: NERExtractor | None = None,
        embedding_service: EmbeddingService | None = None,
        ontology: dict | None = None,
    ) -> None:
        self._storage = storage
        self._ner = ner_extractor
        self._embedding = embedding_service
        self._ontology = ontology

    async def ingest(
        self,
        text: str,
        scenario_name: str,
        ontology: dict | None = None,
    ) -> IngestedScenario:
        """Run the full ingestion pipeline on *text* and return an IngestedScenario."""
        effective_ontology = ontology or self._ontology or DEFAULT_ONTOLOGY

        # Step 1: create graph
        graph_id = await self._storage.create_graph(scenario_name, effective_ontology)

        # Step 2: chunk text
        chunks = _chunk_text(text)

        # Step 3: extract entities and relations from each chunk
        all_raw_entities: list[dict] = []
        all_raw_relations: list[dict] = []

        for chunk in chunks:
            extraction = await self._extract_chunk(chunk, effective_ontology)
            all_raw_entities.extend(extraction.entities)
            all_raw_relations.extend(extraction.relations)

        # Step 4: deduplicate entities by name (keep first occurrence)
        seen_names: dict[str, dict] = {}
        unique_entities: list[dict] = []
        for raw in all_raw_entities:
            name = raw.get("name", "")
            if name and name not in seen_names:
                entity_id = str(uuid.uuid4())
                entity_dict = {
                    "name": name,
                    "type": raw.get("type", "object"),
                    "entity_id": entity_id,
                    "attributes": raw.get("attributes", {}),
                }
                seen_names[name] = entity_dict
                unique_entities.append(entity_dict)

        # Step 5: store entities in graph
        for ent in unique_entities:
            entity = Entity(
                name=ent["name"],
                type=ent["type"],
                entity_id=ent["entity_id"],
                attributes=ent.get("attributes", {}),
            )
            await self._storage.add_entity(graph_id, entity)

        # Step 6: store relations as edges (skip if source/target not found)
        stored_relations: list[dict] = []
        name_to_id = {e["name"]: e["entity_id"] for e in unique_entities}

        for rel in all_raw_relations:
            source_name = rel.get("source", "")
            target_name = rel.get("target", "")
            source_id = name_to_id.get(source_name)
            target_id = name_to_id.get(target_name)

            if source_id is None or target_id is None:
                logger.debug(
                    "Skipping relation %s -> %s: source or target entity not found",
                    source_name,
                    target_name,
                )
                continue

            edge = Edge(
                source_id=source_id,
                target_id=target_id,
                type=rel.get("type", "related_to"),
                fact=rel.get("fact", ""),
            )
            await self._storage.add_edge(graph_id, edge)
            stored_relations.append(
                {
                    "source": source_name,
                    "target": target_name,
                    "type": rel.get("type", "related_to"),
                    "fact": rel.get("fact", ""),
                    "source_id": source_id,
                    "target_id": target_id,
                    "edge_id": edge.edge_id,
                }
            )

        # Step 7: return IngestedScenario
        return IngestedScenario(
            graph_id=graph_id,
            entities=unique_entities,
            relations=stored_relations,
        )

    async def _extract_chunk(self, chunk: str, ontology: dict) -> Extraction:
        """Extract entities/relations from a single chunk via NER."""
        if self._ner is None:
            return Extraction()
        return await self._ner.extract(chunk, ontology)
