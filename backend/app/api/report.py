"""Report generation API endpoint for post-simulation analysis."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs/{run_id}", tags=["report"])


class ReportResponse(BaseModel):
    """Response payload for report generation."""
    run_id: str
    report: str


@router.post("/report", response_model=ReportResponse)
async def generate_report(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a post-simulation analysis report for a completed run.

    Combines InsightForge deep search, PanoramaSearch breadth view,
    and agent memory highlights into a structured markdown report.
    """
    try:
        from app.storage.oracle_graph_storage import OracleGraphStorage
        from app.storage.embedding_service import EmbeddingService
        from app.llm.router import LLMRouter
        from app.services.report_agent import ReportAgent
        from app.models.run import Run

        from sqlalchemy import select

        # Fetch the run
        result = await db.execute(select(Run).where(Run.id == run_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Extract graph_id and scenario name from run
        graph_id = getattr(run, "graph_id", None)
        if graph_id is None:
            raise HTTPException(
                status_code=400,
                detail="Run has no associated knowledge graph",
            )

        scenario_name = getattr(run, "scenario_name", "Simulation")

        # Collect agent IDs from the run
        agent_ids: list[str] = []
        if hasattr(run, "agents") and run.agents:
            agent_ids = [str(a.id) for a in run.agents]

        # Set up services
        graph_storage = OracleGraphStorage(db)
        embedding_service = EmbeddingService()
        llm_client = LLMRouter.get_client()

        agent = ReportAgent(
            storage=graph_storage,
            embedding_service=embedding_service,
            llm_client=llm_client,
        )

        report = await agent.generate_report(
            run_id=run_id,
            graph_id=graph_id,
            scenario_name=scenario_name,
            agent_ids=agent_ids,
        )

        return ReportResponse(run_id=run_id, report=report)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Report generation failed")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")
