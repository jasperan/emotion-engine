"""Document upload API endpoint for NER-based scenario generation"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.scenario import Scenario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


class DocumentUploadRequest(BaseModel):
    """Request body for document upload and entity extraction"""
    text: str = Field(..., min_length=10, description="Document text to process")
    scenario_name: str = Field(..., min_length=1, description="Name for the generated scenario")
    scenario_description: str = Field("", description="Optional scenario description")
    max_steps: int = Field(100, ge=10, le=1000, description="Maximum simulation steps")


class DocumentUploadResponse(BaseModel):
    """Response from document upload processing"""
    graph_id: str
    scenario_id: str
    entity_count: int
    relation_count: int
    agent_count: int


@router.post("/", response_model=DocumentUploadResponse)
async def upload_document(
    request: DocumentUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document, extract entities via NER, generate personas,
    and create a scenario.

    Steps:
    1. Extract named entities and relationships from the text
    2. Store entity graph in Oracle graph storage
    3. Generate agent personas from extracted entities
    4. Assemble and save a complete scenario
    """
    try:
        from app.storage.oracle_graph_storage import OracleGraphStorage
        from app.storage.embedding_service import EmbeddingService
        from app.storage.ner_extractor import NERExtractor
        from app.services.document_ingestor import DocumentIngestor
        from app.services.persona_generator import PersonaGenerator
        from app.services.scenario_assembler import ScenarioAssembler

        # Step 1: Set up services
        embedding_service = EmbeddingService()
        graph_storage = OracleGraphStorage(db)
        ner_extractor = NERExtractor()

        # Step 2: Ingest document (extract entities + relationships)
        ingestor = DocumentIngestor(
            embedding_service=embedding_service,
            graph_storage=graph_storage,
            ner_extractor=ner_extractor,
        )
        ingested = await ingestor.ingest(request.text)

        # Step 3: Generate personas and assemble scenario
        persona_generator = PersonaGenerator()
        assembler = ScenarioAssembler(persona_generator=persona_generator)
        assembled = await assembler.assemble(
            ingested=ingested,
            scenario_name=request.scenario_name,
            scenario_description=request.scenario_description,
            max_steps=request.max_steps,
        )

        # Step 4: Save scenario to DB
        scenario = Scenario(
            name=request.scenario_name,
            description=request.scenario_description,
            config=assembled.config if isinstance(assembled.config, dict) else assembled.config,
            agent_templates=assembled.agent_templates if isinstance(assembled.agent_templates, list) else assembled.agent_templates,
        )

        # graph_id column is added in Task 12; set it safely
        try:
            setattr(scenario, 'graph_id', ingested.graph_id)
        except Exception:
            logger.debug("graph_id column not yet available on Scenario model")

        db.add(scenario)
        await db.flush()
        await db.refresh(scenario)

        return DocumentUploadResponse(
            graph_id=ingested.graph_id,
            scenario_id=scenario.id,
            entity_count=ingested.entity_count,
            relation_count=ingested.relation_count,
            agent_count=len(assembled.agent_templates) if isinstance(assembled.agent_templates, list) else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")
