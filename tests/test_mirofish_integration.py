"""Full MiroFish integration tests: document -> scenario -> memory -> report pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from emotionsim.storage.embedding_service import EmbeddingService
from emotionsim.storage.ner_extractor import NERExtractor, Extraction
from emotionsim.storage.oracle_graph_storage import OracleGraphStorage
from emotionsim.storage.graph_storage import Entity
from emotionsim.services.document_ingestor import DocumentIngestor
from emotionsim.services.persona_generator import PersonaGenerator, GeneratedPersona
from emotionsim.services.scenario_assembler import ScenarioAssembler
from emotionsim.agents.graph_memory import GraphMemory
from emotionsim.services.report_agent import ReportAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_embedding():
    """Mock embedding service returning deterministic 768-d vectors."""
    emb = MagicMock(spec=EmbeddingService)
    emb.dimension = 768
    emb.embed_text = AsyncMock(return_value=[0.1] * 768)
    emb.embed_batch = AsyncMock(return_value=[[0.1] * 768])
    return emb


@pytest.fixture
def mock_ner():
    """Mock NER extractor returning 4 entities (2 persons, 1 location, 1 hazard) and 2 relations."""
    ner = MagicMock(spec=NERExtractor)
    ner.extract = AsyncMock(
        return_value=Extraction(
            entities=[
                {"name": "Maria Gonzalez", "type": "person", "attributes": {"occupation": "nurse"}},
                {"name": "James Chen", "type": "person", "attributes": {"occupation": "engineer"}},
                {"name": "Riverside District", "type": "location", "attributes": {"description": "Low-lying residential area"}},
                {"name": "Flash Flood", "type": "hazard", "attributes": {"severity": "high"}},
            ],
            relations=[
                {"source": "Maria Gonzalez", "target": "Riverside District", "type": "located_at", "fact": "Maria Gonzalez lives in Riverside District"},
                {"source": "Flash Flood", "target": "Riverside District", "type": "affects", "fact": "Flash flood threatens Riverside District"},
            ],
        )
    )
    return ner


@pytest.fixture
def mock_persona_gen():
    """Mock persona generator returning a GeneratedPersona with entity name and reasonable Big Five traits."""
    gen = MagicMock(spec=PersonaGenerator)

    async def _generate(entity, scenario_context=""):
        name = entity.get("name", "Unknown")
        return GeneratedPersona(
            name=name,
            age=35,
            sex="female",
            occupation=entity.get("attributes", {}).get("occupation", "Civilian"),
            openness=7,
            conscientiousness=6,
            extraversion=5,
            agreeableness=8,
            neuroticism=4,
            risk_tolerance=6,
            empathy_level=8,
            leadership=5,
            backstory=f"{name} has been through tough times and knows how to keep calm under pressure.",
            skills=["first_aid", "navigation"],
        )

    gen.generate_from_entity = AsyncMock(side_effect=_generate)
    return gen


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Integration tests for the full MiroFish pipeline end-to-end."""

    @pytest.mark.asyncio
    async def test_document_to_scenario_pipeline(
        self, db_session, mock_embedding, mock_ner, mock_persona_gen
    ):
        """Ingest a document about a flash flood, verify graph entities, then assemble a scenario."""
        # 1. Create storage and ingestor
        storage = OracleGraphStorage(session=db_session, embedding_service=mock_embedding)
        ingestor = DocumentIngestor(
            storage=storage,
            ner_extractor=mock_ner,
            embedding_service=mock_embedding,
        )

        # 2. Ingest a document about a flash flood
        document = (
            "A flash flood struck the Riverside District at dawn. "
            "Maria Gonzalez, a nurse at the local clinic, was among the first to respond. "
            "James Chen, a structural engineer, assessed building damage in the area. "
            "Water levels rose rapidly, threatening the low-lying residential neighborhoods."
        )
        ingested = await ingestor.ingest(document, scenario_name="Flash Flood Crisis")

        # 3. Verify graph_id exists and entity count matches
        assert ingested.graph_id is not None
        assert len(ingested.graph_id) > 0
        assert len(ingested.entities) == 4  # 2 persons + 1 location + 1 hazard

        # Verify entity types
        person_entities = ingested.get_person_entities()
        location_entities = ingested.get_location_entities()
        hazard_entities = ingested.get_hazard_entities()
        assert len(person_entities) == 2
        assert len(location_entities) == 1
        assert len(hazard_entities) == 1

        # 4. Assemble scenario
        assembler = ScenarioAssembler(persona_generator=mock_persona_gen)
        scenario = await assembler.assemble(
            ingested,
            scenario_name="Flash Flood Crisis",
            scenario_description="A flash flood threatens Riverside District survivors.",
        )

        # 5. Verify scenario
        assert scenario.name == "Flash Flood Crisis"
        # Human agent count should match person entity count (2 persons -> 2 human agents)
        human_agents = [a for a in scenario.agent_templates if a.role == "human"]
        assert len(human_agents) == len(person_entities)
        # There should also be 1 environment agent
        env_agents = [a for a in scenario.agent_templates if a.role == "environment"]
        assert len(env_agents) == 1

    @pytest.mark.asyncio
    async def test_graph_memory_store_and_recall(self, db_session, mock_embedding):
        """Store 3 memories at different steps, then recall with a query and verify results."""
        # 1. Create storage and a graph
        storage = OracleGraphStorage(session=db_session, embedding_service=mock_embedding)
        graph_id = await storage.create_graph("Memory Test Graph")

        # 2. Create GraphMemory
        memory = GraphMemory(
            agent_id="agent-001",
            agent_name="Test Agent",
            run_id="run-001",
            graph_id=graph_id,
            storage=storage,
            embedding_service=mock_embedding,
        )

        # 3. Store 3 different memories at different steps
        mem_id_1 = await memory.store(
            content="Found clean water near the bridge",
            memory_type="observation",
            importance=7,
            emotional_valence=0.3,
            step_number=1,
        )
        mem_id_2 = await memory.store(
            content="Met Maria who offered medical supplies",
            memory_type="interaction",
            importance=8,
            emotional_valence=0.6,
            step_number=3,
        )
        mem_id_3 = await memory.store(
            content="Flood water is rising dangerously near camp",
            memory_type="observation",
            importance=9,
            emotional_valence=-0.5,
            step_number=5,
        )

        assert mem_id_1 is not None
        assert mem_id_2 is not None
        assert mem_id_3 is not None

        # 4. Recall with a query
        results = await memory.recall("water level danger", limit=5)

        # 5. Verify at least 1 result returned
        assert len(results) >= 1
        # All results should have the expected fields
        for r in results:
            assert "memory_id" in r
            assert "content" in r
            assert "memory_type" in r
            assert "importance" in r
            assert "step_number" in r

    @pytest.mark.asyncio
    async def test_report_generation(self, db_session, mock_embedding):
        """Create a graph with an entity, generate a report, verify non-empty string."""
        # 1. Create storage
        storage = OracleGraphStorage(session=db_session, embedding_service=mock_embedding)

        # 2. Create a graph and add an entity
        graph_id = await storage.create_graph("Report Test Graph")
        entity = Entity(
            name="Maria Gonzalez",
            type="person",
            summary="A nurse who led rescue operations during the flood.",
            attributes={"occupation": "nurse", "role": "first_responder"},
        )
        await storage.add_entity(graph_id, entity)

        # 3. Create ReportAgent with mock LLM
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=MagicMock(
                content="# Simulation Report\n\nMaria Gonzalez played a key role in coordinating rescue efforts."
            )
        )

        report_agent = ReportAgent(
            storage=storage,
            embedding_service=mock_embedding,
            llm_client=mock_llm,
        )

        # 4. Generate report
        report = await report_agent.generate_report(
            run_id="run-001",
            graph_id=graph_id,
            scenario_name="Flash Flood Crisis",
        )

        # 5. Verify non-empty string returned
        assert isinstance(report, str)
        assert len(report) > 0
