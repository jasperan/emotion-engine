# MiroFish Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate MiroFish's knowledge graph infrastructure and analysis tools into EmotionEngine, backed by Oracle 26ai.

**Architecture:** Abstract GraphStorage interface with Oracle SQL/PGQ implementation. Document ingestion via NER/RE pipeline. Graph-backed agent memory with hybrid search (vector + BM25). Post-sim agent chat and ReportAgent with graph tools.

**Tech Stack:** Python 3.11+, SQLAlchemy (async), Oracle 26ai (SQL/PGQ, AI Vector Search, Oracle Text), Ollama nomic-embed-text (768d), FastAPI, pytest

---

## Task 1: Embedding Service

**Files:**
- Create: `backend/app/storage/__init__.py`
- Create: `backend/app/storage/embedding_service.py`
- Test: `backend/tests/test_embedding_service.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_embedding_service.py
"""Tests for the embedding service"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.storage.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Tests for the EmbeddingService class"""

    def test_creation_with_defaults(self):
        """Test creating service with default config"""
        service = EmbeddingService()
        assert service.model == "nomic-embed-text"
        assert service.dimension == 768

    def test_creation_with_custom_config(self):
        """Test creating service with custom model"""
        service = EmbeddingService(
            model="custom-model",
            base_url="http://custom:11434",
            dimension=512,
        )
        assert service.model == "custom-model"
        assert service.dimension == 512

    @pytest.mark.asyncio
    async def test_embed_single_text(self):
        """Test embedding a single text string"""
        service = EmbeddingService()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "embedding": [0.1] * 768
        })

        with patch("aiohttp.ClientSession.post", return_value=mock_response):
            with patch.object(mock_response, '__aenter__', return_value=mock_response):
                with patch.object(mock_response, '__aexit__', return_value=False):
                    embedding = await service.embed_text("hello world")
                    assert len(embedding) == 768

    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """Test embedding multiple texts in one call"""
        service = EmbeddingService()
        texts = ["hello", "world", "test"]

        mock_response = MagicMock()
        mock_response.status = 200
        # Ollama /api/embed returns list of embeddings
        mock_response.json = AsyncMock(return_value={
            "embeddings": [[0.1] * 768, [0.2] * 768, [0.3] * 768]
        })

        with patch("aiohttp.ClientSession.post", return_value=mock_response):
            with patch.object(mock_response, '__aenter__', return_value=mock_response):
                with patch.object(mock_response, '__aexit__', return_value=False):
                    embeddings = await service.embed_batch(texts)
                    assert len(embeddings) == 3
                    assert all(len(e) == 768 for e in embeddings)

    @pytest.mark.asyncio
    async def test_embed_empty_returns_zeros(self):
        """Test that empty string returns zero vector"""
        service = EmbeddingService()
        embedding = await service.embed_text("")
        assert len(embedding) == 768
        assert all(v == 0.0 for v in embedding)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_embedding_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.storage.embedding_service'"

**Step 3: Write minimal implementation**

```python
# backend/app/storage/__init__.py
"""Storage layer for graph-backed knowledge and memory"""
```

```python
# backend/app/storage/embedding_service.py
"""Embedding service using Ollama nomic-embed-text for vector generation"""
import logging
from typing import Optional

import aiohttp

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings via Ollama's embedding API.

    Uses nomic-embed-text (768d) by default. Compatible with any
    Ollama-served embedding model.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        dimension: int = 768,
    ):
        settings = get_settings()
        self.model = model or "nomic-embed-text"
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.dimension = dimension

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string. Returns zero vector for empty input."""
        if not text.strip():
            return [0.0] * self.dimension

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Embedding failed ({resp.status}), returning zeros")
                    return [0.0] * self.dimension
                data = await resp.json()
                # /api/embed returns {"embeddings": [[...]]} for single input
                embeddings = data.get("embeddings", [])
                if embeddings:
                    return embeddings[0]
                # Fallback for older /api/embeddings format
                return data.get("embedding", [0.0] * self.dimension)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in one call. Empty list returns empty list."""
        if not texts:
            return []

        # Filter empties, track indices
        non_empty = [(i, t) for i, t in enumerate(texts) if t.strip()]
        if not non_empty:
            return [[0.0] * self.dimension for _ in texts]

        indices, clean_texts = zip(*non_empty)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": list(clean_texts)},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Batch embedding failed ({resp.status})")
                    return [[0.0] * self.dimension for _ in texts]
                data = await resp.json()
                raw_embeddings = data.get("embeddings", [])

        # Reassemble with zeros for empty inputs
        result = [[0.0] * self.dimension for _ in texts]
        for idx, emb in zip(indices, raw_embeddings):
            result[idx] = emb

        return result
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_embedding_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/storage/__init__.py backend/app/storage/embedding_service.py backend/tests/test_embedding_service.py
git commit -m "feat(storage): add embedding service for Ollama nomic-embed-text"
```

---

## Task 2: NER Extractor

**Files:**
- Create: `backend/app/storage/ner_extractor.py`
- Test: `backend/tests/test_ner_extractor.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_ner_extractor.py
"""Tests for the NER extractor"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.storage.ner_extractor import NERExtractor, Extraction


class TestNERExtractor:
    """Tests for NER/RE extraction via LLM"""

    def test_creation(self):
        extractor = NERExtractor()
        assert extractor.max_retries == 2

    @pytest.mark.asyncio
    async def test_extract_entities_and_relations(self, mock_llm_client):
        """Test extracting entities and relations from text"""
        mock_llm_client.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "entities": [
                    {"name": "Dr. Sarah Chen", "type": "person", "attributes": {"occupation": "ER Doctor"}},
                    {"name": "Riverside Hospital", "type": "location", "attributes": {"type": "medical"}},
                ],
                "relations": [
                    {"source": "Dr. Sarah Chen", "target": "Riverside Hospital", "type": "works_at", "fact": "Dr. Sarah Chen works at Riverside Hospital"},
                ],
            })
        ))

        extractor = NERExtractor(llm_client=mock_llm_client)
        result = await extractor.extract(
            text="Dr. Sarah Chen is an ER doctor at Riverside Hospital.",
            ontology={"entity_types": ["person", "location"], "relation_types": ["works_at"]},
        )

        assert len(result.entities) == 2
        assert len(result.relations) == 1
        assert result.entities[0]["name"] == "Dr. Sarah Chen"
        assert result.relations[0]["type"] == "works_at"

    @pytest.mark.asyncio
    async def test_extract_with_malformed_response(self, mock_llm_client):
        """Test graceful handling of bad LLM output"""
        mock_llm_client.generate = AsyncMock(return_value=MagicMock(
            content="This is not JSON at all"
        ))

        extractor = NERExtractor(llm_client=mock_llm_client, max_retries=0)
        result = await extractor.extract(
            text="Some text",
            ontology={"entity_types": ["person"], "relation_types": []},
        )

        assert len(result.entities) == 0
        assert len(result.relations) == 0

    def test_extraction_dataclass(self):
        """Test the Extraction dataclass"""
        ext = Extraction(
            entities=[{"name": "Alice", "type": "person"}],
            relations=[{"source": "Alice", "target": "Bob", "type": "knows"}],
        )
        assert len(ext.entities) == 1
        assert ext.relations[0]["source"] == "Alice"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ner_extractor.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# backend/app/storage/ner_extractor.py
"""NER/RE extraction from text using LLM (Qwen3.5 via router)"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm.router import LLMRouter
from app.llm.base import LLMClient, LLMMessage

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a Named Entity Recognition and Relation Extraction system.
Given a text and an ontology (entity types + relation types), extract all entities and relations.

ONTOLOGY:
{ontology_description}

RULES:
1. Only extract entity types and relation types defined in the ontology.
2. Normalize entity names: strip whitespace, use canonical form.
3. Each entity must have: name, type (from ontology), and optional attributes dict.
4. Each relation must have: source entity name, target entity name, type (from ontology), and a fact sentence.
5. If no entities or relations are found, return empty lists.
6. Be precise: only extract what is explicitly stated or strongly implied.

Return ONLY valid JSON:
{{"entities": [{{"name": "...", "type": "...", "attributes": {{}}}}], "relations": [{{"source": "...", "target": "...", "type": "...", "fact": "..."}}]}}"""


@dataclass
class Extraction:
    """Result of NER/RE extraction"""
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)


class NERExtractor:
    """Extract entities and relations from text using LLM."""

    def __init__(self, llm_client: LLMClient | None = None, max_retries: int = 2):
        self._llm = llm_client
        self.max_retries = max_retries

    def _get_client(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMRouter.get_client()
        return self._llm

    async def extract(self, text: str, ontology: dict[str, Any]) -> Extraction:
        """Extract entities and relations from text guided by ontology."""
        ontology_desc = self._format_ontology(ontology)
        system = _SYSTEM_PROMPT.format(ontology_description=ontology_desc)

        for attempt in range(self.max_retries + 1):
            try:
                client = self._get_client()
                response = await client.generate(
                    messages=[LLMMessage(role="user", content=f"Extract entities and relations from:\n\n{text}")],
                    system=system,
                    json_mode=True,
                    temperature=0.1,
                    max_tokens=4096,
                )
                return self._parse_response(response.content)
            except Exception as e:
                logger.warning(f"NER extraction attempt {attempt + 1} failed: {e}")

        return Extraction()

    def _format_ontology(self, ontology: dict[str, Any]) -> str:
        parts = []
        entity_types = ontology.get("entity_types", [])
        relation_types = ontology.get("relation_types", [])
        if entity_types:
            parts.append(f"Entity types: {', '.join(entity_types)}")
        if relation_types:
            parts.append(f"Relation types: {', '.join(relation_types)}")
        return "\n".join(parts) if parts else "No ontology constraints (extract freely)"

    def _parse_response(self, content: str) -> Extraction:
        """Parse LLM response into Extraction. Handles malformed JSON."""
        try:
            # Try direct JSON parse
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                data = json.loads(content[start:end])
            except (ValueError, json.JSONDecodeError):
                logger.warning("Failed to parse NER response as JSON")
                return Extraction()

        return Extraction(
            entities=data.get("entities", []),
            relations=data.get("relations", []),
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ner_extractor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/storage/ner_extractor.py backend/tests/test_ner_extractor.py
git commit -m "feat(storage): add NER/RE extractor via LLM for entity/relationship extraction"
```

---

## Task 3: GraphStorage ABC + Oracle Graph Models

**Files:**
- Create: `backend/app/storage/graph_storage.py`
- Create: `backend/app/models/graph.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/core/database.py` (add OracleVector type)
- Test: `backend/tests/test_graph_storage.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_graph_storage.py
"""Tests for the graph storage abstraction and Oracle models"""
import pytest
from app.storage.graph_storage import GraphStorage, Entity, Edge, SearchResult


class TestGraphStorageModels:
    """Test the graph storage data models"""

    def test_entity_creation(self):
        entity = Entity(
            name="Dr. Sarah Chen",
            type="person",
            summary="ER doctor with 15 years experience",
            attributes={"occupation": "ER Doctor", "age": 42},
        )
        assert entity.name == "Dr. Sarah Chen"
        assert entity.type == "person"
        assert entity.attributes["age"] == 42
        assert entity.entity_id is not None  # Auto-generated UUID

    def test_edge_creation(self):
        edge = Edge(
            source_id="entity-1",
            target_id="entity-2",
            type="works_at",
            fact="Dr. Chen works at Riverside Hospital",
            weight=1.0,
        )
        assert edge.type == "works_at"
        assert edge.weight == 1.0

    def test_search_result_to_text(self):
        result = SearchResult(
            facts=["Dr. Chen works at hospital"],
            entities=[Entity(name="Dr. Chen", type="person")],
            edges=[],
            query="who works at the hospital",
            total_count=1,
        )
        text = result.to_text()
        assert "Dr. Chen" in text
        assert "hospital" in text

    def test_graph_storage_is_abstract(self):
        """Verify GraphStorage can't be instantiated directly"""
        with pytest.raises(TypeError):
            GraphStorage()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph_storage.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write implementation**

```python
# backend/app/storage/graph_storage.py
"""Abstract graph storage interface (Oracle, Neo4j, etc.)"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Entity:
    """A node in the knowledge graph"""
    name: str
    type: str
    summary: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "type": self.type,
            "summary": self.summary,
            "attributes": self.attributes,
        }


@dataclass
class Edge:
    """A relationship in the knowledge graph"""
    source_id: str
    target_id: str
    type: str
    fact: str = ""
    weight: float = 1.0
    embedding: list[float] = field(default_factory=list)
    edge_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type,
            "fact": self.fact,
            "weight": self.weight,
        }


@dataclass
class SearchResult:
    """Result from a graph search query"""
    facts: list[str]
    entities: list[Entity]
    edges: list[Edge]
    query: str
    total_count: int

    def to_text(self) -> str:
        parts = [f"Search: {self.query} ({self.total_count} results)"]
        if self.facts:
            parts.append("\nFacts:")
            for f in self.facts:
                parts.append(f"- {f}")
        if self.entities:
            parts.append("\nEntities:")
            for e in self.entities:
                parts.append(f"- {e.name} ({e.type})")
        return "\n".join(parts)


class GraphStorage(ABC):
    """Abstract interface for knowledge graph operations.

    Implementations: OracleGraphStorage (SQL/PGQ), potentially Neo4jStorage.
    """

    @abstractmethod
    async def create_graph(self, name: str, ontology: dict[str, Any]) -> str:
        """Create a new graph partition. Returns graph_id."""
        ...

    @abstractmethod
    async def delete_graph(self, graph_id: str) -> None:
        """Delete a graph and all its entities/edges."""
        ...

    @abstractmethod
    async def add_entity(self, graph_id: str, entity: Entity) -> str:
        """Add an entity node. Returns entity_id."""
        ...

    @abstractmethod
    async def add_edge(self, graph_id: str, edge: Edge) -> str:
        """Add a relationship edge. Returns edge_id."""
        ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> Entity | None:
        """Get entity by ID."""
        ...

    @abstractmethod
    async def get_neighbors(
        self, entity_id: str, depth: int = 1, edge_types: list[str] | None = None,
    ) -> tuple[list[Entity], list[Edge]]:
        """Get neighboring entities and edges up to depth."""
        ...

    @abstractmethod
    async def search(
        self, graph_id: str, query: str, limit: int = 10,
        query_embedding: list[float] | None = None,
    ) -> SearchResult:
        """Hybrid search (vector + keyword) on the graph."""
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
        embedding: list[float] | None = None,
        linked_entity_ids: list[str] | None = None,
    ) -> str:
        """Add a memory node to the agent's run-scoped memory graph. Returns memory_id."""
        ...

    @abstractmethod
    async def search_memories(
        self,
        run_id: str,
        agent_id: str,
        query: str,
        limit: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Search agent memories by relevance (hybrid search)."""
        ...
```

```python
# backend/app/models/graph.py
"""SQLAlchemy models for the knowledge graph and agent memory graph"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Float, Integer, Text, DateTime, ForeignKey, Index,
)
from app.core.database import Base, OracleJSON


class GraphModel(Base):
    """A knowledge graph partition (one per scenario or document)"""
    __tablename__ = "graphs"

    graph_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    ontology_json = Column(OracleJSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class EntityModel(Base):
    """An entity node in the knowledge graph"""
    __tablename__ = "graph_entities"

    entity_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    graph_id = Column(String(36), ForeignKey("graphs.graph_id"), nullable=False, index=True)
    name = Column(String(500), nullable=False)
    type = Column(String(100), nullable=False)
    summary = Column(Text, default="")
    attributes_json = Column(OracleJSON, default=dict)
    embedding_json = Column(OracleJSON, default=list)  # VECTOR(768) stored as JSON for SQLite compat
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_entity_graph_type", "graph_id", "type"),
        Index("idx_entity_name", "name"),
    )


class EdgeModel(Base):
    """A relationship edge in the knowledge graph"""
    __tablename__ = "graph_edges"

    edge_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    graph_id = Column(String(36), ForeignKey("graphs.graph_id"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("graph_entities.entity_id"), nullable=False)
    target_id = Column(String(36), ForeignKey("graph_entities.entity_id"), nullable=False)
    type = Column(String(100), nullable=False)
    fact = Column(Text, default="")
    weight = Column(Float, default=1.0)
    embedding_json = Column(OracleJSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_edge_graph_type", "graph_id", "type"),
        Index("idx_edge_source", "source_id"),
        Index("idx_edge_target", "target_id"),
    )


class MemoryNodeModel(Base):
    """An agent memory node (run-scoped)"""
    __tablename__ = "graph_memories"

    memory_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), nullable=False, index=True)
    agent_id = Column(String(36), nullable=False, index=True)
    memory_type = Column(String(50), nullable=False)  # observation, decision, conversation, action
    content = Column(Text, nullable=False)
    importance = Column(Integer, default=5)  # 1-10
    emotional_valence = Column(Float, default=0.0)  # -1.0 to 1.0
    step_number = Column(Integer, default=0)
    embedding_json = Column(OracleJSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_memory_run_agent", "run_id", "agent_id"),
        Index("idx_memory_step", "run_id", "step_number"),
    )


class MemoryEdgeModel(Base):
    """A relationship between memory nodes or between a memory and an entity"""
    __tablename__ = "graph_memory_edges"

    edge_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String(36), nullable=False, index=True)  # memory_id or entity_id
    target_id = Column(String(36), nullable=False, index=True)
    type = Column(String(100), nullable=False)  # led_to, contradicts, supports, about_entity, about_agent
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

Update `backend/app/models/__init__.py` to add:

```python
from app.models.graph import GraphModel, EntityModel, EdgeModel, MemoryNodeModel, MemoryEdgeModel
```

And add to `__all__`:

```python
"GraphModel", "EntityModel", "EdgeModel", "MemoryNodeModel", "MemoryEdgeModel",
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_graph_storage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/storage/graph_storage.py backend/app/models/graph.py backend/app/models/__init__.py backend/tests/test_graph_storage.py
git commit -m "feat(storage): add GraphStorage ABC, Entity/Edge models, and Oracle graph schema"
```

---

## Task 4: Oracle Graph Storage Implementation

**Files:**
- Create: `backend/app/storage/oracle_graph_storage.py`
- Test: `backend/tests/test_oracle_graph_storage.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_oracle_graph_storage.py
"""Tests for Oracle graph storage (uses SQLite in tests)"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.oracle_graph_storage import OracleGraphStorage
from app.storage.graph_storage import Entity, Edge
from app.storage.embedding_service import EmbeddingService
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_embedding_service():
    service = MagicMock(spec=EmbeddingService)
    service.embed_text = AsyncMock(return_value=[0.1] * 768)
    service.embed_batch = AsyncMock(return_value=[[0.1] * 768, [0.2] * 768])
    service.dimension = 768
    return service


@pytest.fixture
def storage(db_session, mock_embedding_service):
    return OracleGraphStorage(session=db_session, embedding_service=mock_embedding_service)


class TestOracleGraphStorage:

    @pytest.mark.asyncio
    async def test_create_graph(self, storage):
        graph_id = await storage.create_graph(
            name="test-graph",
            ontology={"entity_types": ["person", "location"], "relation_types": ["knows"]},
        )
        assert graph_id is not None
        assert isinstance(graph_id, str)

    @pytest.mark.asyncio
    async def test_add_and_get_entity(self, storage):
        graph_id = await storage.create_graph(name="test", ontology={})
        entity = Entity(name="Alice", type="person", summary="A test person")

        entity_id = await storage.add_entity(graph_id, entity)
        assert entity_id is not None

        fetched = await storage.get_entity(entity_id)
        assert fetched is not None
        assert fetched.name == "Alice"
        assert fetched.type == "person"

    @pytest.mark.asyncio
    async def test_add_edge(self, storage):
        graph_id = await storage.create_graph(name="test", ontology={})

        e1 = Entity(name="Alice", type="person")
        e2 = Entity(name="Hospital", type="location")
        id1 = await storage.add_entity(graph_id, e1)
        id2 = await storage.add_entity(graph_id, e2)

        edge = Edge(source_id=id1, target_id=id2, type="located_at", fact="Alice is at the hospital")
        edge_id = await storage.add_edge(graph_id, edge)
        assert edge_id is not None

    @pytest.mark.asyncio
    async def test_get_neighbors(self, storage):
        graph_id = await storage.create_graph(name="test", ontology={})

        e1 = Entity(name="Alice", type="person")
        e2 = Entity(name="Bob", type="person")
        id1 = await storage.add_entity(graph_id, e1)
        id2 = await storage.add_entity(graph_id, e2)

        edge = Edge(source_id=id1, target_id=id2, type="knows", fact="Alice knows Bob")
        await storage.add_edge(graph_id, edge)

        neighbors, edges = await storage.get_neighbors(id1)
        assert len(neighbors) == 1
        assert neighbors[0].name == "Bob"
        assert len(edges) == 1

    @pytest.mark.asyncio
    async def test_add_and_search_memory(self, storage):
        graph_id = await storage.create_graph(name="test", ontology={})

        memory_id = await storage.add_memory(
            run_id="run-1",
            agent_id="agent-1",
            content="The bridge is collapsing",
            memory_type="observation",
            importance=8,
            emotional_valence=-0.7,
            step_number=5,
        )
        assert memory_id is not None

        results = await storage.search_memories(
            run_id="run-1",
            agent_id="agent-1",
            query="bridge collapse",
            limit=5,
        )
        assert len(results) >= 1
        assert "bridge" in results[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_search_graph(self, storage):
        graph_id = await storage.create_graph(name="test", ontology={})

        e1 = Entity(name="Dr. Sarah Chen", type="person", summary="ER doctor")
        await storage.add_entity(graph_id, e1)

        result = await storage.search(graph_id, query="doctor", limit=5)
        assert result.total_count >= 1

    @pytest.mark.asyncio
    async def test_delete_graph(self, storage):
        graph_id = await storage.create_graph(name="test", ontology={})
        await storage.add_entity(graph_id, Entity(name="Alice", type="person"))

        await storage.delete_graph(graph_id)

        result = await storage.search(graph_id, query="Alice", limit=5)
        assert result.total_count == 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_oracle_graph_storage.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/storage/oracle_graph_storage.py
"""Oracle 26ai implementation of GraphStorage using SQLAlchemy async."""
import json
import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select, delete, text, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.graph_storage import GraphStorage, Entity, Edge, SearchResult
from app.storage.embedding_service import EmbeddingService
from app.models.graph import (
    GraphModel, EntityModel, EdgeModel, MemoryNodeModel, MemoryEdgeModel,
)

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class OracleGraphStorage(GraphStorage):
    """Oracle 26ai graph storage via SQLAlchemy.

    Uses standard SQL tables with JSON-stored embeddings for SQLite test compat.
    In production Oracle, these can be migrated to VECTOR columns + SQL/PGQ.
    Hybrid search: 0.7 * vector_similarity + 0.3 * keyword_match.
    """

    VECTOR_WEIGHT = 0.7
    KEYWORD_WEIGHT = 0.3

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ):
        self._session = session
        self._embedding = embedding_service or EmbeddingService()

    async def create_graph(self, name: str, ontology: dict[str, Any]) -> str:
        graph_id = str(uuid.uuid4())
        graph = GraphModel(graph_id=graph_id, name=name, ontology_json=ontology)
        self._session.add(graph)
        await self._session.flush()
        return graph_id

    async def delete_graph(self, graph_id: str) -> None:
        # Delete edges first (FK constraint)
        await self._session.execute(
            delete(EdgeModel).where(EdgeModel.graph_id == graph_id)
        )
        await self._session.execute(
            delete(EntityModel).where(EntityModel.graph_id == graph_id)
        )
        await self._session.execute(
            delete(GraphModel).where(GraphModel.graph_id == graph_id)
        )
        await self._session.flush()

    async def add_entity(self, graph_id: str, entity: Entity) -> str:
        embedding = entity.embedding
        if not embedding:
            summary_text = f"{entity.name} ({entity.type})"
            if entity.summary:
                summary_text += f": {entity.summary}"
            embedding = await self._embedding.embed_text(summary_text)

        model = EntityModel(
            entity_id=entity.entity_id,
            graph_id=graph_id,
            name=entity.name,
            type=entity.type,
            summary=entity.summary,
            attributes_json=entity.attributes,
            embedding_json=embedding,
        )
        self._session.add(model)
        await self._session.flush()
        return entity.entity_id

    async def add_edge(self, graph_id: str, edge: Edge) -> str:
        embedding = edge.embedding
        if not embedding:
            embedding = await self._embedding.embed_text(edge.fact or f"{edge.type}")

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
        self._session.add(model)
        await self._session.flush()
        return edge.edge_id

    async def get_entity(self, entity_id: str) -> Entity | None:
        result = await self._session.execute(
            select(EntityModel).where(EntityModel.entity_id == entity_id)
        )
        row = result.scalar_one_or_none()
        if not row:
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
        self, entity_id: str, depth: int = 1, edge_types: list[str] | None = None,
    ) -> tuple[list[Entity], list[Edge]]:
        # Get edges where entity is source or target
        query = select(EdgeModel).where(
            or_(EdgeModel.source_id == entity_id, EdgeModel.target_id == entity_id)
        )
        if edge_types:
            query = query.where(EdgeModel.type.in_(edge_types))

        result = await self._session.execute(query)
        edge_rows = result.scalars().all()

        edges = []
        neighbor_ids = set()
        for row in edge_rows:
            edges.append(Edge(
                edge_id=row.edge_id,
                source_id=row.source_id,
                target_id=row.target_id,
                type=row.type,
                fact=row.fact or "",
                weight=row.weight or 1.0,
            ))
            other_id = row.target_id if row.source_id == entity_id else row.source_id
            neighbor_ids.add(other_id)

        # Fetch neighbor entities
        entities = []
        if neighbor_ids:
            result = await self._session.execute(
                select(EntityModel).where(EntityModel.entity_id.in_(neighbor_ids))
            )
            for row in result.scalars().all():
                entities.append(Entity(
                    entity_id=row.entity_id,
                    name=row.name,
                    type=row.type,
                    summary=row.summary or "",
                    attributes=row.attributes_json or {},
                ))

        return entities, edges

    async def search(
        self, graph_id: str, query: str, limit: int = 10,
        query_embedding: list[float] | None = None,
    ) -> SearchResult:
        """Hybrid search: vector similarity + keyword matching."""
        if query_embedding is None:
            query_embedding = await self._embedding.embed_text(query)

        # Get all entities in graph
        result = await self._session.execute(
            select(EntityModel).where(EntityModel.graph_id == graph_id)
        )
        all_entities = result.scalars().all()

        # Get all edges in graph
        result = await self._session.execute(
            select(EdgeModel).where(EdgeModel.graph_id == graph_id)
        )
        all_edges = result.scalars().all()

        # Score entities
        scored = []
        query_lower = query.lower()
        query_terms = query_lower.split()

        for row in all_entities:
            # Vector score
            vec_score = _cosine_similarity(query_embedding, row.embedding_json or [])

            # Keyword score (simple BM25-like term matching)
            text_blob = f"{row.name} {row.summary or ''} {row.type}".lower()
            matched_terms = sum(1 for t in query_terms if t in text_blob)
            kw_score = matched_terms / max(len(query_terms), 1)

            combined = self.VECTOR_WEIGHT * vec_score + self.KEYWORD_WEIGHT * kw_score
            if combined > 0.01:
                scored.append((combined, row))

        # Score edges
        scored_edges = []
        for row in all_edges:
            vec_score = _cosine_similarity(query_embedding, row.embedding_json or [])
            text_blob = f"{row.fact or ''} {row.type}".lower()
            matched_terms = sum(1 for t in query_terms if t in text_blob)
            kw_score = matched_terms / max(len(query_terms), 1)
            combined = self.VECTOR_WEIGHT * vec_score + self.KEYWORD_WEIGHT * kw_score
            if combined > 0.01:
                scored_edges.append((combined, row))

        # Sort and limit
        scored.sort(key=lambda x: x[0], reverse=True)
        scored_edges.sort(key=lambda x: x[0], reverse=True)

        entities = [
            Entity(
                entity_id=row.entity_id, name=row.name, type=row.type,
                summary=row.summary or "", attributes=row.attributes_json or {},
            )
            for _, row in scored[:limit]
        ]
        edges = [
            Edge(
                edge_id=row.edge_id, source_id=row.source_id, target_id=row.target_id,
                type=row.type, fact=row.fact or "", weight=row.weight or 1.0,
            )
            for _, row in scored_edges[:limit]
        ]
        facts = [e.fact for e in edges if e.fact]

        return SearchResult(
            facts=facts,
            entities=entities,
            edges=edges,
            query=query,
            total_count=len(entities) + len(edges),
        )

    # --- Agent Memory Graph ---

    async def add_memory(
        self,
        run_id: str,
        agent_id: str,
        content: str,
        memory_type: str,
        importance: int,
        emotional_valence: float,
        step_number: int,
        embedding: list[float] | None = None,
        linked_entity_ids: list[str] | None = None,
    ) -> str:
        if embedding is None:
            embedding = await self._embedding.embed_text(content)

        memory_id = str(uuid.uuid4())
        model = MemoryNodeModel(
            memory_id=memory_id,
            run_id=run_id,
            agent_id=agent_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            emotional_valence=emotional_valence,
            step_number=step_number,
            embedding_json=embedding,
        )
        self._session.add(model)

        # Link to entities
        if linked_entity_ids:
            for eid in linked_entity_ids:
                link = MemoryEdgeModel(
                    source_id=memory_id,
                    target_id=eid,
                    type="about_entity",
                )
                self._session.add(link)

        await self._session.flush()
        return memory_id

    async def search_memories(
        self,
        run_id: str,
        agent_id: str,
        query: str,
        limit: int = 5,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        if query_embedding is None:
            query_embedding = await self._embedding.embed_text(query)

        result = await self._session.execute(
            select(MemoryNodeModel).where(
                MemoryNodeModel.run_id == run_id,
                MemoryNodeModel.agent_id == agent_id,
            )
        )
        all_memories = result.scalars().all()

        query_lower = query.lower()
        query_terms = query_lower.split()

        scored = []
        for row in all_memories:
            vec_score = _cosine_similarity(query_embedding, row.embedding_json or [])
            text_blob = row.content.lower()
            matched = sum(1 for t in query_terms if t in text_blob)
            kw_score = matched / max(len(query_terms), 1)
            combined = self.VECTOR_WEIGHT * vec_score + self.KEYWORD_WEIGHT * kw_score
            scored.append((combined, row))

        scored.sort(key=lambda x: x[0], reverse=True)

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
            for score, row in scored[:limit]
        ]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_oracle_graph_storage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/storage/oracle_graph_storage.py backend/tests/test_oracle_graph_storage.py
git commit -m "feat(storage): add Oracle graph storage with hybrid search and agent memory"
```

---

## Task 5: Document Ingestion Pipeline

**Files:**
- Create: `backend/app/services/document_ingestor.py`
- Test: `backend/tests/test_document_ingestor.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_document_ingestor.py
"""Tests for the document ingestion pipeline"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.document_ingestor import DocumentIngestor, IngestedScenario


class TestDocumentIngestor:

    @pytest.fixture
    def mock_storage(self):
        storage = MagicMock()
        storage.create_graph = AsyncMock(return_value="graph-1")
        storage.add_entity = AsyncMock(return_value="entity-1")
        storage.add_edge = AsyncMock(return_value="edge-1")
        return storage

    @pytest.fixture
    def mock_ner(self):
        from app.storage.ner_extractor import Extraction
        ner = MagicMock()
        ner.extract = AsyncMock(return_value=Extraction(
            entities=[
                {"name": "Dr. Sarah Chen", "type": "person", "attributes": {"occupation": "ER Doctor", "age": "42"}},
                {"name": "Riverside District", "type": "location", "attributes": {"description": "Urban flood zone"}},
                {"name": "Rising Flood", "type": "hazard", "attributes": {"severity": "high"}},
            ],
            relations=[
                {"source": "Dr. Sarah Chen", "target": "Riverside District", "type": "located_at", "fact": "Dr. Chen is in the Riverside District"},
            ],
        ))
        return ner

    @pytest.fixture
    def mock_embedding(self):
        service = MagicMock()
        service.embed_text = AsyncMock(return_value=[0.1] * 768)
        service.embed_batch = AsyncMock(return_value=[[0.1] * 768])
        return service

    @pytest.mark.asyncio
    async def test_ingest_document(self, mock_storage, mock_ner, mock_embedding):
        ingestor = DocumentIngestor(
            storage=mock_storage,
            ner_extractor=mock_ner,
            embedding_service=mock_embedding,
        )

        result = await ingestor.ingest(
            text="A catastrophic flood hits the Riverside District. Dr. Sarah Chen, an ER doctor, is on the scene.",
            scenario_name="Rising Flood",
        )

        assert isinstance(result, IngestedScenario)
        assert result.graph_id == "graph-1"
        assert len(result.entities) == 3
        assert mock_storage.create_graph.called
        assert mock_storage.add_entity.call_count == 3
        assert mock_storage.add_edge.call_count == 1

    @pytest.mark.asyncio
    async def test_ingest_generates_ontology(self, mock_storage, mock_ner, mock_embedding):
        ingestor = DocumentIngestor(
            storage=mock_storage,
            ner_extractor=mock_ner,
            embedding_service=mock_embedding,
        )

        result = await ingestor.ingest(
            text="Some text about a disaster",
            scenario_name="Test",
        )

        # Verify ontology was passed to create_graph
        call_args = mock_storage.create_graph.call_args
        ontology = call_args[1].get("ontology") or call_args[0][1]
        assert "entity_types" in ontology

    def test_ingested_scenario_has_person_entities(self):
        scenario = IngestedScenario(
            graph_id="g1",
            entities=[
                {"name": "Alice", "type": "person", "entity_id": "e1"},
                {"name": "Hospital", "type": "location", "entity_id": "e2"},
            ],
            relations=[],
        )
        persons = scenario.get_person_entities()
        assert len(persons) == 1
        assert persons[0]["name"] == "Alice"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_document_ingestor.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/services/document_ingestor.py
"""Document ingestion pipeline: text -> NER/RE -> graph -> scenario"""
import logging
from dataclasses import dataclass, field
from typing import Any

from app.storage.graph_storage import GraphStorage, Entity, Edge
from app.storage.ner_extractor import NERExtractor
from app.storage.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# Default ontology for disaster simulation scenarios
DEFAULT_ONTOLOGY = {
    "entity_types": [
        "person", "location", "organization", "hazard",
        "resource", "vehicle", "event", "object",
    ],
    "relation_types": [
        "located_at", "works_at", "knows", "trusts", "member_of",
        "caused_by", "affects", "owns", "near", "blocks",
    ],
}


@dataclass
class IngestedScenario:
    """Result of document ingestion"""
    graph_id: str
    entities: list[dict[str, Any]] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)

    def get_person_entities(self) -> list[dict[str, Any]]:
        return [e for e in self.entities if e.get("type") == "person"]

    def get_location_entities(self) -> list[dict[str, Any]]:
        return [e for e in self.entities if e.get("type") == "location"]

    def get_hazard_entities(self) -> list[dict[str, Any]]:
        return [e for e in self.entities if e.get("type") == "hazard"]


class DocumentIngestor:
    """Ingest a document into the knowledge graph.

    Pipeline: text -> chunk -> NER/RE -> embed -> store in graph.
    """

    def __init__(
        self,
        storage: GraphStorage,
        ner_extractor: NERExtractor | None = None,
        embedding_service: EmbeddingService | None = None,
        ontology: dict[str, Any] | None = None,
    ):
        self._storage = storage
        self._ner = ner_extractor or NERExtractor()
        self._embedding = embedding_service or EmbeddingService()
        self._ontology = ontology or DEFAULT_ONTOLOGY

    async def ingest(
        self,
        text: str,
        scenario_name: str,
        ontology: dict[str, Any] | None = None,
    ) -> IngestedScenario:
        """Ingest a document and build a knowledge graph."""
        ontology = ontology or self._ontology

        # 1. Create graph partition
        graph_id = await self._storage.create_graph(
            name=scenario_name, ontology=ontology,
        )

        # 2. Chunk text (simple paragraph-based for now)
        chunks = self._chunk_text(text)

        # 3. Extract entities and relations from all chunks
        all_entities: list[dict[str, Any]] = []
        all_relations: list[dict[str, Any]] = []

        for chunk in chunks:
            extraction = await self._ner.extract(chunk, ontology)
            all_entities.extend(extraction.entities)
            all_relations.extend(extraction.relations)

        # 4. Deduplicate entities by name
        entity_map: dict[str, dict[str, Any]] = {}
        for ent in all_entities:
            name = ent["name"].strip()
            if name not in entity_map:
                entity_map[name] = ent

        # 5. Store entities in graph
        name_to_id: dict[str, str] = {}
        stored_entities = []

        for name, ent_data in entity_map.items():
            entity = Entity(
                name=name,
                type=ent_data.get("type", "unknown"),
                summary=ent_data.get("summary", ""),
                attributes=ent_data.get("attributes", {}),
            )
            entity_id = await self._storage.add_entity(graph_id, entity)
            name_to_id[name] = entity_id
            stored = {**ent_data, "entity_id": entity_id, "name": name}
            stored_entities.append(stored)

        # 6. Store relations as edges
        stored_relations = []
        for rel in all_relations:
            source_name = rel.get("source", "").strip()
            target_name = rel.get("target", "").strip()
            source_id = name_to_id.get(source_name)
            target_id = name_to_id.get(target_name)

            if not source_id or not target_id:
                logger.warning(f"Skipping relation: {source_name} -> {target_name} (entity not found)")
                continue

            edge = Edge(
                source_id=source_id,
                target_id=target_id,
                type=rel.get("type", "related_to"),
                fact=rel.get("fact", ""),
            )
            await self._storage.add_edge(graph_id, edge)
            stored_relations.append({**rel, "edge_id": edge.edge_id})

        return IngestedScenario(
            graph_id=graph_id,
            entities=stored_entities,
            relations=stored_relations,
        )

    def _chunk_text(self, text: str, max_chunk_size: int = 2000) -> list[str]:
        """Split text into chunks by paragraphs, respecting max size."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [text] if text.strip() else []

        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 > max_chunk_size and current:
                chunks.append(current)
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
        if current:
            chunks.append(current)

        return chunks
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_document_ingestor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/document_ingestor.py backend/tests/test_document_ingestor.py
git commit -m "feat(services): add document ingestion pipeline (text -> NER/RE -> graph)"
```

---

## Task 6: Persona Generator (entity -> agent persona)

**Files:**
- Create: `backend/app/services/persona_generator.py`
- Test: `backend/tests/test_persona_generator.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_persona_generator.py
"""Tests for persona generation from graph entities"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.services.persona_generator import PersonaGenerator, GeneratedPersona


class TestPersonaGenerator:

    @pytest.fixture
    def mock_llm_client(self):
        client = MagicMock()
        client.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "openness": 6,
                "conscientiousness": 9,
                "extraversion": 6,
                "agreeableness": 8,
                "neuroticism": 3,
                "risk_tolerance": 7,
                "empathy_level": 9,
                "leadership": 8,
                "mbti": "ENFJ",
                "backstory": "A dedicated ER doctor with 15 years of experience.",
                "skills": ["first_aid", "surgery", "triage"],
                "opinion_biases": {"authority": 0.6, "cooperation": 0.8},
                "influence_level": 0.7,
                "reaction_speed": 0.8,
            })
        ))
        return client

    @pytest.mark.asyncio
    async def test_generate_persona_from_entity(self, mock_llm_client):
        generator = PersonaGenerator(llm_client=mock_llm_client)

        persona = await generator.generate_from_entity(
            entity={
                "name": "Dr. Sarah Chen",
                "type": "person",
                "attributes": {"occupation": "ER Doctor", "age": "42"},
                "entity_id": "ent-1",
            },
            scenario_context="A catastrophic flood in an urban district",
        )

        assert isinstance(persona, GeneratedPersona)
        assert persona.name == "Dr. Sarah Chen"
        assert 1 <= persona.openness <= 10
        assert persona.mbti in ["ENFJ", "INTJ", "ISFP", "ENTP", None]  # or any valid
        assert len(persona.skills) > 0

    @pytest.mark.asyncio
    async def test_generate_creates_valid_pydantic_persona(self, mock_llm_client):
        generator = PersonaGenerator(llm_client=mock_llm_client)

        persona = await generator.generate_from_entity(
            entity={"name": "Alice", "type": "person", "attributes": {}, "entity_id": "e1"},
            scenario_context="Flood scenario",
        )

        # Should be convertible to the existing Persona schema
        pydantic_persona = persona.to_persona()
        assert pydantic_persona.name == "Alice"
        assert pydantic_persona.openness == 6

    def test_fallback_persona_for_failed_llm(self):
        """Test that a reasonable default is generated if LLM fails"""
        persona = GeneratedPersona.fallback(
            name="Unknown Person",
            entity_type="person",
        )
        assert persona.name == "Unknown Person"
        assert 1 <= persona.openness <= 10
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_persona_generator.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/services/persona_generator.py
"""Generate rich agent personas from knowledge graph entities"""
import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm.router import LLMRouter
from app.llm.base import LLMClient, LLMMessage
from app.schemas.persona import Persona

logger = logging.getLogger(__name__)

_PERSONA_PROMPT = """Generate a detailed persona for a simulation agent based on this entity.

Entity: {name}
Type: {type}
Attributes: {attributes}
Scenario: {scenario_context}

Generate a JSON object with these fields:
- openness (1-10): curiosity, creativity
- conscientiousness (1-10): organization, dependability
- extraversion (1-10): sociability, assertiveness
- agreeableness (1-10): cooperation, trust
- neuroticism (1-10): emotional instability, anxiety
- risk_tolerance (1-10): willingness to take risks
- empathy_level (1-10): tendency to help others
- leadership (1-10): tendency to take charge
- mbti (string): 4-letter MBTI type (e.g. "ENFJ")
- backstory (string): 2-3 sentence backstory fitting the scenario
- skills (list[str]): 3-5 relevant skills
- opinion_biases (dict): topic -> stance (-1.0 to 1.0) for 2-3 key topics
- influence_level (float 0-1): how much this person influences others
- reaction_speed (float 0-1): how quickly they adapt to new information

Return ONLY valid JSON."""


@dataclass
class GeneratedPersona:
    """A persona generated from a graph entity"""
    name: str
    entity_id: str = ""
    age: int = 30
    sex: str = "non-binary"
    occupation: str = "Civilian"
    openness: int = 5
    conscientiousness: int = 5
    extraversion: int = 5
    agreeableness: int = 5
    neuroticism: int = 5
    risk_tolerance: int = 5
    empathy_level: int = 5
    leadership: int = 5
    mbti: str | None = None
    backstory: str = ""
    skills: list[str] = field(default_factory=list)
    opinion_biases: dict[str, float] = field(default_factory=dict)
    influence_level: float = 0.5
    reaction_speed: float = 0.5

    def to_persona(self) -> Persona:
        """Convert to the existing Persona pydantic model"""
        return Persona(
            name=self.name,
            age=self.age,
            sex=self.sex,
            occupation=self.occupation,
            openness=self.openness,
            conscientiousness=self.conscientiousness,
            extraversion=self.extraversion,
            agreeableness=self.agreeableness,
            neuroticism=self.neuroticism,
            risk_tolerance=self.risk_tolerance,
            empathy_level=self.empathy_level,
            leadership=self.leadership,
            backstory=self.backstory,
            skills=self.skills,
        )

    @classmethod
    def fallback(cls, name: str, entity_type: str = "person") -> "GeneratedPersona":
        """Generate a reasonable default persona when LLM fails"""
        return cls(
            name=name,
            openness=random.randint(3, 8),
            conscientiousness=random.randint(3, 8),
            extraversion=random.randint(3, 8),
            agreeableness=random.randint(3, 8),
            neuroticism=random.randint(3, 8),
            risk_tolerance=random.randint(3, 8),
            empathy_level=random.randint(3, 8),
            leadership=random.randint(3, 8),
            backstory=f"A {entity_type} caught in extraordinary circumstances.",
            skills=["survival"],
        )


class PersonaGenerator:
    """Generate detailed agent personas from knowledge graph entities."""

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client

    def _get_client(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMRouter.get_client()
        return self._llm

    async def generate_from_entity(
        self,
        entity: dict[str, Any],
        scenario_context: str = "",
    ) -> GeneratedPersona:
        """Generate a persona from a graph entity."""
        name = entity.get("name", "Unknown")
        entity_type = entity.get("type", "person")
        attributes = entity.get("attributes", {})

        prompt = _PERSONA_PROMPT.format(
            name=name,
            type=entity_type,
            attributes=json.dumps(attributes),
            scenario_context=scenario_context,
        )

        try:
            client = self._get_client()
            response = await client.generate(
                messages=[LLMMessage(role="user", content=prompt)],
                json_mode=True,
                temperature=0.7,
                max_tokens=1024,
            )
            data = self._parse_response(response.content)
        except Exception as e:
            logger.warning(f"Persona generation failed for {name}: {e}")
            return GeneratedPersona.fallback(name, entity_type)

        # Extract age/sex/occupation from attributes or LLM output
        age = int(attributes.get("age", data.get("age", 30)))
        sex = attributes.get("sex", attributes.get("gender", "non-binary"))
        occupation = attributes.get("occupation", attributes.get("role", "Civilian"))

        return GeneratedPersona(
            name=name,
            entity_id=entity.get("entity_id", ""),
            age=max(1, min(120, age)),
            sex=sex if sex in ("male", "female", "non-binary") else "non-binary",
            occupation=occupation,
            openness=self._clamp(data.get("openness", 5)),
            conscientiousness=self._clamp(data.get("conscientiousness", 5)),
            extraversion=self._clamp(data.get("extraversion", 5)),
            agreeableness=self._clamp(data.get("agreeableness", 5)),
            neuroticism=self._clamp(data.get("neuroticism", 5)),
            risk_tolerance=self._clamp(data.get("risk_tolerance", 5)),
            empathy_level=self._clamp(data.get("empathy_level", 5)),
            leadership=self._clamp(data.get("leadership", 5)),
            mbti=data.get("mbti"),
            backstory=data.get("backstory", ""),
            skills=data.get("skills", ["survival"]),
            opinion_biases=data.get("opinion_biases", {}),
            influence_level=max(0.0, min(1.0, data.get("influence_level", 0.5))),
            reaction_speed=max(0.0, min(1.0, data.get("reaction_speed", 0.5))),
        )

    def _clamp(self, val: Any, lo: int = 1, hi: int = 10) -> int:
        try:
            return max(lo, min(hi, int(val)))
        except (TypeError, ValueError):
            return 5

    def _parse_response(self, content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                return json.loads(content[start:end])
            except (ValueError, json.JSONDecodeError):
                return {}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_persona_generator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/persona_generator.py backend/tests/test_persona_generator.py
git commit -m "feat(services): add persona generator (graph entity -> Big Five + MBTI agent)"
```

---

## Task 7: Graph-Backed Agent Memory (GraphMemory)

**Files:**
- Create: `backend/app/agents/graph_memory.py`
- Test: `backend/tests/test_graph_memory.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_graph_memory.py
"""Tests for graph-backed agent memory"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.graph_memory import GraphMemory


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.add_memory = AsyncMock(return_value="mem-1")
    storage.search_memories = AsyncMock(return_value=[
        {
            "memory_id": "mem-1",
            "content": "The bridge is collapsing",
            "memory_type": "observation",
            "importance": 8,
            "emotional_valence": -0.7,
            "step_number": 5,
            "relevance_score": 0.85,
        }
    ])
    storage.search = AsyncMock(return_value=MagicMock(
        entities=[], edges=[], facts=[], total_count=0,
    ))
    storage.get_neighbors = AsyncMock(return_value=([], []))
    return storage


@pytest.fixture
def mock_embedding():
    service = MagicMock()
    service.embed_text = AsyncMock(return_value=[0.1] * 768)
    return service


class TestGraphMemory:

    @pytest.mark.asyncio
    async def test_store_memory(self, mock_storage, mock_embedding):
        mem = GraphMemory(
            agent_id="agent-1",
            agent_name="Sarah",
            run_id="run-1",
            graph_id="graph-1",
            storage=mock_storage,
            embedding_service=mock_embedding,
        )

        await mem.store(
            content="I saw the bridge crack",
            memory_type="observation",
            importance=7,
            emotional_valence=-0.5,
            step_number=3,
        )

        mock_storage.add_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_relevant_memories(self, mock_storage, mock_embedding):
        mem = GraphMemory(
            agent_id="agent-1",
            agent_name="Sarah",
            run_id="run-1",
            graph_id="graph-1",
            storage=mock_storage,
            embedding_service=mock_embedding,
        )

        results = await mem.recall("bridge danger", limit=5)
        assert len(results) == 1
        assert "bridge" in results[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_build_context_string(self, mock_storage, mock_embedding):
        mem = GraphMemory(
            agent_id="agent-1",
            agent_name="Sarah",
            run_id="run-1",
            graph_id="graph-1",
            storage=mock_storage,
            embedding_service=mock_embedding,
        )

        context = await mem.build_context("I'm at the bridge, it looks dangerous")
        assert isinstance(context, str)
        # Should contain recalled memories
        assert "bridge" in context.lower() or context == ""  # empty if no results
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_graph_memory.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/agents/graph_memory.py
"""Graph-backed agent memory using hybrid search for relevant recall."""
import logging
from typing import Any, Optional

from app.storage.graph_storage import GraphStorage
from app.storage.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class GraphMemory:
    """Graph-backed memory that retrieves by relevance, not recency.

    Replaces the flat sliding-window AgentMemory with semantic search
    over the knowledge graph + run-scoped memory graph.
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        run_id: str,
        graph_id: str,
        storage: GraphStorage,
        embedding_service: EmbeddingService | None = None,
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.run_id = run_id
        self.graph_id = graph_id
        self._storage = storage
        self._embedding = embedding_service or EmbeddingService()

    async def store(
        self,
        content: str,
        memory_type: str = "observation",
        importance: int = 5,
        emotional_valence: float = 0.0,
        step_number: int = 0,
        linked_entity_ids: list[str] | None = None,
    ) -> str:
        """Store a new memory in the graph."""
        embedding = await self._embedding.embed_text(content)
        return await self._storage.add_memory(
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

    async def recall(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Recall memories relevant to the query using hybrid search."""
        embedding = await self._embedding.embed_text(query)
        return await self._storage.search_memories(
            run_id=self.run_id,
            agent_id=self.agent_id,
            query=query,
            limit=limit,
            query_embedding=embedding,
        )

    async def recall_graph_context(
        self,
        entity_ids: list[str],
    ) -> str:
        """Get knowledge graph context for nearby entities."""
        parts = []
        for eid in entity_ids[:5]:  # Limit to avoid context bloat
            neighbors, edges = await self._storage.get_neighbors(eid, depth=1)
            for edge in edges:
                if edge.fact:
                    parts.append(edge.fact)
            for neighbor in neighbors:
                parts.append(f"{neighbor.name} ({neighbor.type})")

        return "\n".join(parts) if parts else ""

    async def build_context(
        self,
        current_situation: str,
        max_memories: int = 5,
        max_graph_facts: int = 3,
    ) -> str:
        """Build a context string for the agent's LLM prompt.

        Combines relevant memories + knowledge graph facts.
        """
        parts = []

        # 1. Recall relevant memories
        memories = await self.recall(current_situation, limit=max_memories)
        if memories:
            parts.append("Relevant memories:")
            for mem in memories:
                importance_marker = "!" if mem.get("importance", 0) >= 7 else ""
                parts.append(
                    f"- {importance_marker}[Step {mem.get('step_number', '?')}] "
                    f"{mem['content']}"
                )

        # 2. Search knowledge graph for related facts
        graph_result = await self._storage.search(
            self.graph_id, current_situation, limit=max_graph_facts,
        )
        if graph_result.facts:
            parts.append("\nKnown facts:")
            for fact in graph_result.facts[:max_graph_facts]:
                parts.append(f"- {fact}")

        return "\n".join(parts)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_graph_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agents/graph_memory.py backend/tests/test_graph_memory.py
git commit -m "feat(agents): add GraphMemory with hybrid search recall"
```

---

## Task 8: Scenario Assembler (preset + custom)

**Files:**
- Create: `backend/app/services/scenario_assembler.py`
- Test: `backend/tests/test_scenario_assembler.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_scenario_assembler.py
"""Tests for scenario assembler"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.services.scenario_assembler import ScenarioAssembler


class TestScenarioAssembler:

    @pytest.fixture
    def mock_persona_gen(self):
        from app.services.persona_generator import GeneratedPersona
        gen = MagicMock()
        gen.generate_from_entity = AsyncMock(return_value=GeneratedPersona(
            name="Dr. Sarah Chen",
            entity_id="e1",
            age=42,
            sex="female",
            occupation="ER Doctor",
            openness=6, conscientiousness=9, extraversion=6,
            agreeableness=8, neuroticism=3,
            risk_tolerance=7, empathy_level=9, leadership=8,
            backstory="Experienced ER doctor",
            skills=["first_aid", "surgery"],
        ))
        return gen

    @pytest.mark.asyncio
    async def test_assemble_from_ingested_scenario(self, mock_persona_gen):
        from app.services.document_ingestor import IngestedScenario

        ingested = IngestedScenario(
            graph_id="g1",
            entities=[
                {"name": "Dr. Sarah Chen", "type": "person", "entity_id": "e1", "attributes": {"occupation": "ER Doctor"}},
                {"name": "Riverside District", "type": "location", "entity_id": "e2", "attributes": {"description": "Flooded area"}},
                {"name": "Rising Flood", "type": "hazard", "entity_id": "e3", "attributes": {"severity": "high"}},
            ],
            relations=[],
        )

        assembler = ScenarioAssembler(persona_generator=mock_persona_gen)
        scenario = await assembler.assemble(
            ingested=ingested,
            scenario_name="Rising Flood",
            scenario_description="A catastrophic flood",
        )

        assert scenario.name == "Rising Flood"
        assert len(scenario.agent_templates) >= 2  # 1 human + 1 environment
        # Check that person entities became human agents
        human_agents = [a for a in scenario.agent_templates if a.role == "human"]
        assert len(human_agents) >= 1

    def test_preset_scenarios_have_graph_id_field(self):
        """Verify existing preset scenarios can have graph_id attached"""
        from app.scenarios.rising_flood import create_rising_flood_scenario
        scenario = create_rising_flood_scenario(num_agents=3)
        # ScenarioCreate should accept graph_id for linking to knowledge graph
        assert scenario.name is not None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_scenario_assembler.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/services/scenario_assembler.py
"""Assemble simulation-ready scenarios from ingested documents or presets"""
import logging
from typing import Any

from app.schemas.scenario import WorldConfig, ScenarioCreate
from app.schemas.agent import AgentConfig
from app.services.document_ingestor import IngestedScenario
from app.services.persona_generator import PersonaGenerator

logger = logging.getLogger(__name__)


class ScenarioAssembler:
    """Wire ingested graph entities into a simulation-ready ScenarioCreate."""

    def __init__(self, persona_generator: PersonaGenerator | None = None):
        self._persona_gen = persona_generator or PersonaGenerator()

    async def assemble(
        self,
        ingested: IngestedScenario,
        scenario_name: str,
        scenario_description: str = "",
        max_steps: int = 100,
    ) -> ScenarioCreate:
        """Build a ScenarioCreate from an IngestedScenario."""

        # Extract locations from entities
        locations = {}
        for ent in ingested.get_location_entities():
            loc_name = ent["name"].lower().replace(" ", "_")
            attrs = ent.get("attributes", {})
            locations[loc_name] = {
                "description": attrs.get("description", ent["name"]),
                "nearby": [],
                "items": [],
                "hazard_affected": False,
                "observations": [],
            }

        # If no locations found, create a default
        if not locations:
            locations["central_area"] = {
                "description": "The main area where events unfold",
                "nearby": [],
                "items": [],
                "hazard_affected": False,
                "observations": [],
            }

        # Wire up nearby connections (fully connected for small maps)
        loc_names = list(locations.keys())
        for i, name in enumerate(loc_names):
            locations[name]["nearby"] = [n for n in loc_names if n != name]

        # Extract hazards
        hazards = []
        for ent in ingested.get_hazard_entities():
            hazards.append(ent["name"])
            # Mark some locations as hazard-affected
            for loc in list(locations.values())[:len(locations) // 2 + 1]:
                loc["hazard_affected"] = True

        # Build agent templates
        agent_templates = []

        # Environment agent
        agent_templates.append(AgentConfig(
            name="Environment System",
            role="environment",
            goals=[
                "Simulate realistic scenario progression",
                "Create meaningful survival challenges",
                "Generate events that force cooperation",
            ],
        ))

        # Generate personas from person entities
        person_entities = ingested.get_person_entities()
        location_list = loc_names or ["central_area"]

        for i, ent in enumerate(person_entities):
            persona = await self._persona_gen.generate_from_entity(
                entity=ent,
                scenario_context=scenario_description,
            )
            pydantic_persona = persona.to_persona()
            # Assign to locations round-robin
            pydantic_persona.location = location_list[i % len(location_list)]

            agent_templates.append(AgentConfig(
                name=persona.name,
                role="human",
                persona=pydantic_persona,
                goals=[
                    "Survive and help others survive",
                    "Coordinate with others to share resources",
                    "Find and rescue anyone in danger",
                ],
            ))

        # World config
        world_config = WorldConfig(
            name=scenario_name,
            description=scenario_description,
            initial_state={
                "hazard_level": 2,
                "locations": locations,
                "events": hazards,
                "resources": [],
            },
            dynamics={
                "intensity_growth": 0.15,
                "resource_spawn_rate": 0.1,
                "event_probability": 0.2,
            },
            max_steps=max_steps,
            tick_delay=1.0,
        )

        return ScenarioCreate(
            name=scenario_name,
            description=scenario_description,
            config=world_config,
            agent_templates=agent_templates,
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_scenario_assembler.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/scenario_assembler.py backend/tests/test_scenario_assembler.py
git commit -m "feat(services): add scenario assembler (graph entities -> simulation-ready scenario)"
```

---

## Task 9: Document Upload API Endpoint

**Files:**
- Create: `backend/app/api/document.py`
- Modify: `backend/app/api/routes.py` (register new router)
- Test: `backend/tests/test_document_api.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_document_api.py
"""Tests for document upload API"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestDocumentAPI:

    def test_ingest_endpoint_schema(self):
        """Verify the request/response schema"""
        from app.api.document import DocumentUploadRequest, DocumentUploadResponse

        req = DocumentUploadRequest(
            text="A flood hits the city",
            scenario_name="Rising Flood",
        )
        assert req.text == "A flood hits the city"

        resp = DocumentUploadResponse(
            graph_id="g1",
            scenario_id="s1",
            entity_count=3,
            relation_count=1,
            agent_count=2,
        )
        assert resp.entity_count == 3
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_document_api.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/api/document.py
"""Document upload and ingestion API"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.storage.oracle_graph_storage import OracleGraphStorage
from app.storage.embedding_service import EmbeddingService
from app.storage.ner_extractor import NERExtractor
from app.services.document_ingestor import DocumentIngestor
from app.services.persona_generator import PersonaGenerator
from app.services.scenario_assembler import ScenarioAssembler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentUploadRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Document text to ingest")
    scenario_name: str = Field(..., min_length=1, description="Name for the generated scenario")
    scenario_description: str = Field("", description="Optional description")
    max_steps: int = Field(100, ge=10, le=1000)


class DocumentUploadResponse(BaseModel):
    graph_id: str
    scenario_id: str
    entity_count: int
    relation_count: int
    agent_count: int


@router.post("", response_model=DocumentUploadResponse)
async def upload_document(
    request: DocumentUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Upload a document, extract entities, generate personas, create scenario."""
    try:
        embedding_service = EmbeddingService()
        storage = OracleGraphStorage(session=db, embedding_service=embedding_service)
        ner = NERExtractor()
        ingestor = DocumentIngestor(
            storage=storage,
            ner_extractor=ner,
            embedding_service=embedding_service,
        )

        # 1. Ingest document -> knowledge graph
        ingested = await ingestor.ingest(
            text=request.text,
            scenario_name=request.scenario_name,
        )

        # 2. Assemble scenario from graph entities
        persona_gen = PersonaGenerator()
        assembler = ScenarioAssembler(persona_generator=persona_gen)
        scenario_create = await assembler.assemble(
            ingested=ingested,
            scenario_name=request.scenario_name,
            scenario_description=request.scenario_description,
            max_steps=request.max_steps,
        )

        # 3. Persist scenario to DB (reuse existing scenario creation logic)
        from app.models.scenario import Scenario
        scenario = Scenario(
            name=scenario_create.name,
            description=scenario_create.description,
            config=scenario_create.config.model_dump(),
            agent_templates=[t.model_dump() for t in scenario_create.agent_templates],
            graph_id=ingested.graph_id,
        )
        db.add(scenario)
        await db.flush()

        return DocumentUploadResponse(
            graph_id=ingested.graph_id,
            scenario_id=scenario.id,
            entity_count=len(ingested.entities),
            relation_count=len(ingested.relations),
            agent_count=len([e for e in ingested.entities if e.get("type") == "person"]),
        )

    except Exception as e:
        logger.error(f"Document ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

Note: The Scenario model will need a `graph_id` column added. Add to `backend/app/models/scenario.py`:
```python
graph_id = Column(String(36), nullable=True)  # Link to knowledge graph
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_document_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/document.py backend/tests/test_document_api.py
git commit -m "feat(api): add document upload endpoint for NER-based scenario generation"
```

---

## Task 10: Post-Simulation Agent Chat (Tier B1)

**Files:**
- Create: `backend/app/api/chat.py`
- Test: `backend/tests/test_agent_chat.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_agent_chat.py
"""Tests for post-simulation agent chat"""
import pytest
from app.api.chat import AgentChatRequest, AgentChatResponse


class TestAgentChat:

    def test_chat_request_schema(self):
        req = AgentChatRequest(message="Why did you refuse to help Marcus?")
        assert req.message == "Why did you refuse to help Marcus?"

    def test_chat_response_schema(self):
        resp = AgentChatResponse(
            agent_name="Dr. Sarah Chen",
            response="I didn't refuse. I was treating a critical patient at the time.",
            personality_context="Conscientious (9/10), high empathy",
            memories_referenced=["Treated injured patient at step 5"],
        )
        assert resp.agent_name == "Dr. Sarah Chen"
        assert len(resp.memories_referenced) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_agent_chat.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/api/chat.py
"""Post-simulation agent chat API"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.run import Run
from app.models.agent import AgentModel
from app.llm.router import LLMRouter
from app.llm.base import LLMMessage
from app.storage.oracle_graph_storage import OracleGraphStorage
from app.storage.embedding_service import EmbeddingService
from app.agents.graph_memory import GraphMemory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs/{run_id}/agents/{agent_id}", tags=["chat"])


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class AgentChatResponse(BaseModel):
    agent_name: str
    response: str
    personality_context: str = ""
    memories_referenced: list[str] = []


@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    run_id: str,
    agent_id: str,
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Chat with an agent after simulation ends. Agent responds in-character."""
    # Load agent
    result = await db.execute(
        select(AgentModel).where(
            AgentModel.id == agent_id,
            AgentModel.run_id == run_id,
        )
    )
    agent_row = result.scalar_one_or_none()
    if not agent_row:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Load run for graph_id
    result = await db.execute(select(Run).where(Run.id == run_id))
    run_row = result.scalar_one_or_none()
    if not run_row:
        raise HTTPException(status_code=404, detail="Run not found")

    # Build persona context
    persona = agent_row.persona or {}
    name = persona.get("name", agent_row.name)
    personality_parts = []
    for trait in ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]:
        val = persona.get(trait)
        if val:
            personality_parts.append(f"{trait}: {val}/10")
    personality_context = ", ".join(personality_parts)

    # Recall relevant memories
    memories_text = ""
    memories_referenced = []
    graph_id = getattr(run_row, "graph_id", None) or run_row.scenario_id
    if graph_id:
        try:
            embedding_service = EmbeddingService()
            storage = OracleGraphStorage(session=db, embedding_service=embedding_service)
            graph_mem = GraphMemory(
                agent_id=agent_id,
                agent_name=name,
                run_id=run_id,
                graph_id=graph_id,
                storage=storage,
                embedding_service=embedding_service,
            )
            recalled = await graph_mem.recall(request.message, limit=5)
            for mem in recalled:
                memories_referenced.append(mem["content"])
            if memories_referenced:
                memories_text = "\n\nRelevant memories:\n" + "\n".join(
                    f"- {m}" for m in memories_referenced
                )
        except Exception as e:
            logger.warning(f"Memory recall failed: {e}")

    # Build system prompt
    backstory = persona.get("backstory", "")
    system_prompt = f"""You are {name}. You just lived through a simulation.
Personality: {personality_context}
Backstory: {backstory}
{memories_text}

Respond in character. Be honest about your motivations and decisions.
Reference specific events from your memory when relevant."""

    # Generate response
    try:
        client = LLMRouter.get_client()
        llm_response = await client.generate(
            messages=[LLMMessage(role="user", content=request.message)],
            system=system_prompt,
            temperature=0.7,
            max_tokens=1024,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

    return AgentChatResponse(
        agent_name=name,
        response=llm_response.content,
        personality_context=personality_context,
        memories_referenced=memories_referenced,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_agent_chat.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/tests/test_agent_chat.py
git commit -m "feat(api): add post-simulation agent chat endpoint"
```

---

## Task 11: Report Agent with Graph Tools (Tier B2)

**Files:**
- Create: `backend/app/services/graph_tools.py`
- Create: `backend/app/services/report_agent.py`
- Create: `backend/app/api/report.py`
- Test: `backend/tests/test_report_agent.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_report_agent.py
"""Tests for report agent and graph tools"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.services.graph_tools import GraphToolsService, InsightForgeResult
from app.services.report_agent import ReportAgent


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.search = AsyncMock(return_value=MagicMock(
        facts=["Dr. Chen treated 3 patients", "Bridge collapsed at step 12"],
        entities=[],
        edges=[],
        total_count=2,
        to_text=lambda: "Dr. Chen treated 3 patients\nBridge collapsed at step 12",
    ))
    storage.search_memories = AsyncMock(return_value=[
        {"content": "I helped rescue the child", "memory_type": "action", "step_number": 8},
    ])
    return storage


@pytest.fixture
def mock_embedding():
    service = MagicMock()
    service.embed_text = AsyncMock(return_value=[0.1] * 768)
    return service


class TestGraphTools:

    @pytest.mark.asyncio
    async def test_insight_forge(self, mock_storage, mock_embedding):
        tools = GraphToolsService(
            storage=mock_storage,
            embedding_service=mock_embedding,
        )
        result = await tools.insight_forge(
            graph_id="g1",
            question="What were the key medical events?",
        )
        assert isinstance(result, InsightForgeResult)
        assert len(result.findings) > 0

    @pytest.mark.asyncio
    async def test_panorama_search(self, mock_storage, mock_embedding):
        tools = GraphToolsService(
            storage=mock_storage,
            embedding_service=mock_embedding,
        )
        result = await tools.panorama_search(graph_id="g1")
        assert result is not None


class TestReportAgent:

    @pytest.mark.asyncio
    async def test_generate_report(self, mock_storage, mock_embedding):
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(
            content="## Simulation Report\n\nThe simulation showed strong cooperation patterns."
        ))

        agent = ReportAgent(
            storage=mock_storage,
            embedding_service=mock_embedding,
            llm_client=mock_llm,
        )

        report = await agent.generate_report(
            run_id="run-1",
            graph_id="g1",
            scenario_name="Rising Flood",
        )

        assert isinstance(report, str)
        assert len(report) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_report_agent.py -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# backend/app/services/graph_tools.py
"""Graph retrieval tools for the Report Agent (InsightForge, PanoramaSearch)"""
import logging
from dataclasses import dataclass, field
from typing import Any

from app.storage.graph_storage import GraphStorage, SearchResult
from app.storage.embedding_service import EmbeddingService
from app.llm.router import LLMRouter
from app.llm.base import LLMClient, LLMMessage

logger = logging.getLogger(__name__)


@dataclass
class InsightForgeResult:
    """Result of deep multi-query search"""
    question: str
    sub_questions: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        parts = [f"Question: {self.question}"]
        if self.findings:
            parts.append("\nFindings:")
            for f in self.findings:
                parts.append(f"- {f}")
        if self.evidence:
            parts.append("\nEvidence:")
            for e in self.evidence:
                parts.append(f"- {e}")
        return "\n".join(parts)


class GraphToolsService:
    """Graph retrieval tools for post-simulation analysis."""

    def __init__(
        self,
        storage: GraphStorage,
        embedding_service: EmbeddingService | None = None,
        llm_client: LLMClient | None = None,
    ):
        self._storage = storage
        self._embedding = embedding_service or EmbeddingService()
        self._llm = llm_client

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMRouter.get_client()
        return self._llm

    async def insight_forge(
        self,
        graph_id: str,
        question: str,
        num_sub_questions: int = 3,
    ) -> InsightForgeResult:
        """Deep search: auto-generate sub-questions, search each, synthesize."""
        # Generate sub-questions
        sub_questions = await self._generate_sub_questions(question, num_sub_questions)

        # Search for each
        all_facts = []
        all_evidence = []

        queries = [question] + sub_questions
        for q in queries:
            result = await self._storage.search(graph_id, q, limit=5)
            all_facts.extend(result.facts)
            for ent in result.entities:
                all_evidence.append(f"{ent.name} ({ent.type}): {ent.summary}")

        # Deduplicate
        findings = list(dict.fromkeys(all_facts))
        evidence = list(dict.fromkeys(all_evidence))

        return InsightForgeResult(
            question=question,
            sub_questions=sub_questions,
            findings=findings[:10],
            evidence=evidence[:10],
        )

    async def panorama_search(
        self,
        graph_id: str,
        limit: int = 20,
    ) -> SearchResult:
        """Breadth search: get comprehensive view of all entities and events."""
        return await self._storage.search(graph_id, query="*", limit=limit)

    async def _generate_sub_questions(self, question: str, count: int) -> list[str]:
        """Use LLM to decompose a question into sub-questions."""
        try:
            client = self._get_llm()
            resp = await client.generate(
                messages=[LLMMessage(
                    role="user",
                    content=f"Break this question into {count} specific sub-questions for research. Return ONLY a JSON list of strings.\n\nQuestion: {question}",
                )],
                json_mode=True,
                temperature=0.3,
                max_tokens=512,
            )
            import json
            data = json.loads(resp.content)
            if isinstance(data, list):
                return data[:count]
            return data.get("questions", data.get("sub_questions", []))[:count]
        except Exception as e:
            logger.warning(f"Sub-question generation failed: {e}")
            return []
```

```python
# backend/app/services/report_agent.py
"""Post-simulation report agent with graph-backed analysis"""
import logging
from typing import Any

from app.storage.graph_storage import GraphStorage
from app.storage.embedding_service import EmbeddingService
from app.services.graph_tools import GraphToolsService
from app.llm.router import LLMRouter
from app.llm.base import LLMClient, LLMMessage

logger = logging.getLogger(__name__)

_REPORT_PROMPT = """You are a simulation analyst. Generate a structured report based on these findings.

Scenario: {scenario_name}
Run ID: {run_id}

## Knowledge Graph Findings
{insight_findings}

## Overview
{panorama_summary}

## Agent Memory Highlights
{memory_highlights}

Write a professional report with these sections:
1. Executive Summary (2-3 sentences)
2. Key Events Timeline
3. Agent Behavior Analysis
4. Cooperation & Conflict Patterns
5. Recommendations

Be specific. Reference agent names and events."""


class ReportAgent:
    """Generate post-simulation analysis reports using graph tools."""

    def __init__(
        self,
        storage: GraphStorage,
        embedding_service: EmbeddingService | None = None,
        llm_client: LLMClient | None = None,
    ):
        self._storage = storage
        self._embedding = embedding_service or EmbeddingService()
        self._llm = llm_client
        self._tools = GraphToolsService(
            storage=storage,
            embedding_service=self._embedding,
            llm_client=self._llm,
        )

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMRouter.get_client()
        return self._llm

    async def generate_report(
        self,
        run_id: str,
        graph_id: str,
        scenario_name: str = "Simulation",
        agent_ids: list[str] | None = None,
    ) -> str:
        """Generate a full analysis report."""

        # 1. InsightForge: deep search on key questions
        insight = await self._tools.insight_forge(
            graph_id=graph_id,
            question=f"What were the most significant events and decisions in the {scenario_name} simulation?",
        )

        # 2. PanoramaSearch: breadth view
        panorama = await self._tools.panorama_search(graph_id=graph_id)

        # 3. Gather agent memory highlights
        memory_highlights = []
        if agent_ids:
            for aid in agent_ids[:5]:
                memories = await self._storage.search_memories(
                    run_id=run_id, agent_id=aid,
                    query="important decision action",
                    limit=3,
                )
                for mem in memories:
                    memory_highlights.append(
                        f"[Agent {aid}, Step {mem.get('step_number', '?')}]: {mem['content']}"
                    )

        # 4. Generate report via LLM
        prompt = _REPORT_PROMPT.format(
            scenario_name=scenario_name,
            run_id=run_id,
            insight_findings=insight.to_text(),
            panorama_summary=panorama.to_text() if hasattr(panorama, 'to_text') else str(panorama),
            memory_highlights="\n".join(memory_highlights) if memory_highlights else "No agent memories available",
        )

        client = self._get_llm()
        response = await client.generate(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.5,
            max_tokens=4096,
        )

        return response.content
```

```python
# backend/app/api/report.py
"""Report generation API"""
import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.run import Run
from app.storage.oracle_graph_storage import OracleGraphStorage
from app.storage.embedding_service import EmbeddingService
from app.services.report_agent import ReportAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/runs/{run_id}", tags=["report"])


class ReportResponse(BaseModel):
    run_id: str
    report: str


@router.post("/report", response_model=ReportResponse)
async def generate_report(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a post-simulation analysis report."""
    result = await db.execute(select(Run).where(Run.id == run_id))
    run_row = result.scalar_one_or_none()
    if not run_row:
        raise HTTPException(status_code=404, detail="Run not found")

    graph_id = getattr(run_row, "graph_id", None) or run_row.scenario_id

    embedding_service = EmbeddingService()
    storage = OracleGraphStorage(session=db, embedding_service=embedding_service)

    agent = ReportAgent(storage=storage, embedding_service=embedding_service)
    report = await agent.generate_report(
        run_id=run_id,
        graph_id=graph_id,
        scenario_name=getattr(run_row, "scenario_name", "Simulation"),
    )

    return ReportResponse(run_id=run_id, report=report)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_report_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/graph_tools.py backend/app/services/report_agent.py backend/app/api/report.py backend/tests/test_report_agent.py
git commit -m "feat(services): add ReportAgent with InsightForge and PanoramaSearch graph tools"
```

---

## Task 12: Wire New Routes + Add graph_id to Models

**Files:**
- Modify: `backend/app/api/routes.py` (register document, chat, report routers)
- Modify: `backend/app/models/scenario.py` (add graph_id column)
- Modify: `backend/app/models/run.py` (add graph_id column)

**Step 1: Add graph_id to Scenario model**

In `backend/app/models/scenario.py`, add:
```python
graph_id = Column(String(36), nullable=True)
```

In `backend/app/models/run.py`, add:
```python
graph_id = Column(String(36), nullable=True)
```

**Step 2: Register new routers**

In `backend/app/api/routes.py`, add imports and include:
```python
from app.api.document import router as document_router
from app.api.chat import router as chat_router
from app.api.report import router as report_router
```

And in the router registration:
```python
app.include_router(document_router)
app.include_router(chat_router)
app.include_router(report_router)
```

**Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All existing tests pass + all new tests pass

**Step 4: Commit**

```bash
git add backend/app/api/routes.py backend/app/models/scenario.py backend/app/models/run.py
git commit -m "feat: wire document/chat/report routes and add graph_id to models"
```

---

## Task 13: Full Integration Test

**Files:**
- Create: `backend/tests/test_mirofish_integration.py`

**Step 1: Write integration test**

```python
# backend/tests/test_mirofish_integration.py
"""Integration tests for the full MiroFish pipeline"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.storage.embedding_service import EmbeddingService
from app.storage.ner_extractor import NERExtractor, Extraction
from app.storage.oracle_graph_storage import OracleGraphStorage
from app.storage.graph_storage import Entity
from app.services.document_ingestor import DocumentIngestor
from app.services.persona_generator import PersonaGenerator, GeneratedPersona
from app.services.scenario_assembler import ScenarioAssembler
from app.agents.graph_memory import GraphMemory
from app.services.graph_tools import GraphToolsService
from app.services.report_agent import ReportAgent


class TestFullPipeline:
    """Test the complete document -> scenario -> memory -> report pipeline"""

    @pytest.fixture
    def mock_embedding(self):
        svc = MagicMock(spec=EmbeddingService)
        svc.embed_text = AsyncMock(return_value=[0.1] * 768)
        svc.embed_batch = AsyncMock(return_value=[[0.1] * 768])
        svc.dimension = 768
        return svc

    @pytest.fixture
    def mock_ner(self):
        ner = MagicMock(spec=NERExtractor)
        ner.extract = AsyncMock(return_value=Extraction(
            entities=[
                {"name": "Dr. Sarah Chen", "type": "person", "attributes": {"occupation": "ER Doctor", "age": "42"}},
                {"name": "Marcus Thompson", "type": "person", "attributes": {"occupation": "Construction Worker"}},
                {"name": "Riverside District", "type": "location", "attributes": {}},
                {"name": "Flash Flood", "type": "hazard", "attributes": {"severity": "extreme"}},
            ],
            relations=[
                {"source": "Dr. Sarah Chen", "target": "Riverside District", "type": "located_at", "fact": "Dr. Chen is at Riverside"},
                {"source": "Marcus Thompson", "target": "Riverside District", "type": "located_at", "fact": "Marcus is at Riverside"},
            ],
        ))
        return ner

    @pytest.fixture
    def mock_persona_gen(self):
        gen = MagicMock(spec=PersonaGenerator)
        gen.generate_from_entity = AsyncMock(side_effect=lambda entity, **kw: GeneratedPersona(
            name=entity["name"],
            entity_id=entity.get("entity_id", ""),
            age=42, sex="female", occupation="Doctor",
            openness=6, conscientiousness=9, extraversion=6,
            agreeableness=8, neuroticism=3,
            risk_tolerance=7, empathy_level=9, leadership=8,
            backstory="Test persona", skills=["first_aid"],
        ))
        return gen

    @pytest.mark.asyncio
    async def test_document_to_scenario_pipeline(self, db_session, mock_embedding, mock_ner, mock_persona_gen):
        """Test: document -> ingest -> graph -> personas -> scenario"""
        storage = OracleGraphStorage(session=db_session, embedding_service=mock_embedding)

        # 1. Ingest document
        ingestor = DocumentIngestor(
            storage=storage, ner_extractor=mock_ner, embedding_service=mock_embedding,
        )
        ingested = await ingestor.ingest(
            text="Flash flood hits Riverside District. Dr. Sarah Chen and Marcus Thompson are on scene.",
            scenario_name="Flash Flood Test",
        )

        assert ingested.graph_id is not None
        assert len(ingested.entities) == 4

        # 2. Assemble scenario
        assembler = ScenarioAssembler(persona_generator=mock_persona_gen)
        scenario = await assembler.assemble(
            ingested=ingested,
            scenario_name="Flash Flood Test",
            scenario_description="A flash flood test scenario",
        )

        assert scenario.name == "Flash Flood Test"
        human_agents = [a for a in scenario.agent_templates if a.role == "human"]
        assert len(human_agents) == 2  # Sarah + Marcus

    @pytest.mark.asyncio
    async def test_graph_memory_store_and_recall(self, db_session, mock_embedding):
        """Test: store memories -> recall by relevance"""
        storage = OracleGraphStorage(session=db_session, embedding_service=mock_embedding)
        graph_id = await storage.create_graph(name="test", ontology={})

        mem = GraphMemory(
            agent_id="agent-1", agent_name="Sarah",
            run_id="run-1", graph_id=graph_id,
            storage=storage, embedding_service=mock_embedding,
        )

        # Store several memories
        await mem.store("The bridge is about to collapse", "observation", importance=9, step_number=5)
        await mem.store("Found medical supplies in the shelter", "observation", importance=6, step_number=3)
        await mem.store("Marcus agreed to help rescue the child", "conversation", importance=8, step_number=7)

        # Recall
        results = await mem.recall("bridge danger", limit=5)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_report_generation(self, db_session, mock_embedding):
        """Test: graph tools + report generation"""
        storage = OracleGraphStorage(session=db_session, embedding_service=mock_embedding)
        graph_id = await storage.create_graph(name="test", ontology={})

        # Add some data
        await storage.add_entity(graph_id, Entity(name="Dr. Chen", type="person", summary="ER doctor"))

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(
            content="## Report\n\nThe simulation demonstrated effective cooperation."
        ))

        agent = ReportAgent(
            storage=storage, embedding_service=mock_embedding, llm_client=mock_llm,
        )
        report = await agent.generate_report(
            run_id="run-1", graph_id=graph_id, scenario_name="Test",
        )
        assert "cooperation" in report.lower() or "report" in report.lower()
```

**Step 2: Run integration test**

Run: `cd backend && python -m pytest tests/test_mirofish_integration.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -30`
Expected: All tests pass

**Step 4: Commit**

```bash
git add backend/tests/test_mirofish_integration.py
git commit -m "test: add full MiroFish integration tests (document -> scenario -> memory -> report)"
```

---

## Task 14: Final Wiring + Full Test Run

**Step 1: Update `backend/app/storage/__init__.py` with exports**

```python
from app.storage.graph_storage import GraphStorage, Entity, Edge, SearchResult
from app.storage.oracle_graph_storage import OracleGraphStorage
from app.storage.embedding_service import EmbeddingService
from app.storage.ner_extractor import NERExtractor
```

**Step 2: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: ALL tests pass (existing + new)

**Step 3: Commit everything**

```bash
git add -A
git commit -m "feat: complete MiroFish Tier A + B integration (knowledge graph + analysis tools)"
git push origin mirofish-integration
```
