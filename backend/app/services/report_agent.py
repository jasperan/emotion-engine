"""ReportAgent: generates post-simulation analysis reports using graph tools."""

from __future__ import annotations

import logging

from app.llm.base import LLMClient, LLMMessage
from app.services.graph_tools import GraphToolsService
from app.storage.embedding_service import EmbeddingService
from app.storage.graph_storage import GraphStorage

logger = logging.getLogger(__name__)


class ReportAgent:
    """Produces a structured markdown report for a completed simulation run.

    Combines InsightForge (deep search), PanoramaSearch (breadth view),
    and agent memory highlights into a single LLM-generated report.
    """

    def __init__(
        self,
        storage: GraphStorage,
        embedding_service: EmbeddingService | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._storage = storage
        self._embedding = embedding_service
        self._llm = llm_client
        self._graph_tools = GraphToolsService(
            storage=storage,
            embedding_service=embedding_service,
            llm_client=llm_client,
        )

    async def generate_report(
        self,
        run_id: str,
        graph_id: str,
        scenario_name: str = "Simulation",
        agent_ids: list[str] | None = None,
    ) -> str:
        """Generate a post-simulation analysis report as a markdown string.

        Steps:
        1. InsightForge deep search on key events/decisions
        2. PanoramaSearch for breadth view
        3. Gather agent memory highlights
        4. Build prompt, send to LLM, return report
        """

        # Step 1: InsightForge deep search
        insight_result = await self._graph_tools.insight_forge(
            graph_id,
            "What were the most significant events and decisions?",
        )

        # Step 2: PanoramaSearch breadth view
        panorama_result = await self._graph_tools.panorama_search(graph_id)

        # Step 3: Gather agent memory highlights
        memory_sections: list[str] = []
        if agent_ids:
            for agent_id in agent_ids:
                try:
                    memories = await self._storage.search_memories(
                        run_id=run_id,
                        agent_id=agent_id,
                        query="important decision action",
                        limit=3,
                    )
                    if memories:
                        lines = [f"Agent {agent_id}:"]
                        for mem in memories:
                            content = mem.get("content", str(mem))
                            lines.append(f"  - {content}")
                        memory_sections.append("\n".join(lines))
                except Exception:
                    logger.debug("Failed to fetch memories for agent %s", agent_id)

        # Step 4: Build prompt and generate report
        prompt_parts: list[str] = [
            f"# Post-Simulation Analysis: {scenario_name}",
            f"\nRun ID: {run_id}",
            "\n## Deep Analysis (InsightForge)",
            insight_result.to_text(),
            "\n## Breadth View (PanoramaSearch)",
            panorama_result.to_text(),
        ]

        if memory_sections:
            prompt_parts.append("\n## Agent Memory Highlights")
            prompt_parts.extend(memory_sections)

        context = "\n".join(prompt_parts)

        if self._llm is None:
            # No LLM available; return the raw gathered context as the report.
            return context

        system_prompt = (
            "You are a simulation analyst. Given the following data from a multi-agent "
            "simulation, write a clear, structured markdown report covering: "
            "1) Key events and turning points, 2) Agent behaviors and decisions, "
            "3) Cooperation patterns, 4) Overall outcomes. "
            "Be specific and reference evidence from the data."
        )

        try:
            response = await self._llm.generate(
                messages=[LLMMessage(role="user", content=context)],
                system=system_prompt,
                temperature=0.5,
                max_tokens=2048,
            )
            return response.content
        except Exception:
            logger.exception("LLM report generation failed, returning raw context")
            return context
