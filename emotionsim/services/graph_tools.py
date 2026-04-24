"""Graph analysis tools: InsightForge (deep search) and PanoramaSearch (breadth view)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from emotionsim.llm.base import LLMClient, LLMMessage
from emotionsim.storage.embedding_service import EmbeddingService
from emotionsim.storage.graph_storage import GraphStorage, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class InsightForgeResult:
    """Aggregated results from a multi-question deep search over a knowledge graph."""

    question: str
    sub_questions: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines: list[str] = [f"InsightForge: \"{self.question}\""]

        if self.sub_questions:
            lines.append("\nSub-questions:")
            for sq in self.sub_questions:
                lines.append(f"  - {sq}")

        if self.findings:
            lines.append("\nFindings:")
            for f in self.findings:
                lines.append(f"  - {f}")

        if self.evidence:
            lines.append("\nEvidence:")
            for e in self.evidence:
                lines.append(f"  - {e}")

        return "\n".join(lines)


class GraphToolsService:
    """High-level graph analysis tools built on top of GraphStorage."""

    def __init__(
        self,
        storage: GraphStorage,
        embedding_service: EmbeddingService | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._storage = storage
        self._embedding = embedding_service
        self._llm = llm_client

    async def insight_forge(
        self,
        graph_id: str,
        question: str,
        num_sub_questions: int = 3,
    ) -> InsightForgeResult:
        """Deep search: decompose a question into sub-questions, search graph for each,
        and aggregate deduplicated findings and evidence."""

        sub_questions = await self._generate_sub_questions(question, num_sub_questions)

        all_queries = [question] + sub_questions
        findings: list[str] = []
        evidence: list[str] = []
        seen_findings: set[str] = set()
        seen_evidence: set[str] = set()

        for q in all_queries:
            embedding = None
            if self._embedding is not None:
                try:
                    embedding = await self._embedding.embed_text(q)
                except Exception:
                    logger.debug("Embedding failed for query: %s", q)

            result: SearchResult = await self._storage.search(
                graph_id, q, limit=10, query_embedding=embedding
            )

            for fact in result.facts:
                if fact not in seen_findings:
                    seen_findings.add(fact)
                    findings.append(fact)

            for entity in result.entities:
                ev = f"{entity.name} ({entity.type})"
                if entity.summary:
                    ev += f": {entity.summary}"
                if ev not in seen_evidence:
                    seen_evidence.add(ev)
                    evidence.append(ev)

            for edge in result.edges:
                ev = f"[{edge.type}] {edge.source_id} -> {edge.target_id}"
                if edge.fact:
                    ev += f" ({edge.fact})"
                if ev not in seen_evidence:
                    seen_evidence.add(ev)
                    evidence.append(ev)

        return InsightForgeResult(
            question=question,
            sub_questions=sub_questions,
            findings=findings,
            evidence=evidence,
        )

    async def panorama_search(
        self,
        graph_id: str,
        limit: int = 20,
    ) -> SearchResult:
        """Breadth search across the entire graph."""
        return await self._storage.search(graph_id, query="*", limit=limit)

    async def _generate_sub_questions(
        self,
        question: str,
        count: int,
    ) -> list[str]:
        """Use LLM to decompose a question into sub-questions. Returns empty list on failure."""
        if self._llm is None:
            return []

        prompt = (
            f"Break the following question into exactly {count} focused sub-questions "
            f"that would help answer it comprehensively. Return ONLY a JSON array of strings.\n\n"
            f"Question: {question}"
        )

        try:
            response = await self._llm.generate(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.3,
                max_tokens=512,
                json_mode=True,
            )
            parsed = json.loads(response.content)
            if isinstance(parsed, list):
                return [str(q) for q in parsed[:count]]
            if isinstance(parsed, dict):
                # Handle {"sub_questions": [...]} or {"questions": [...]}
                for key in ("sub_questions", "questions", "items"):
                    if key in parsed and isinstance(parsed[key], list):
                        return [str(q) for q in parsed[key][:count]]
            return []
        except Exception:
            logger.debug("Failed to generate sub-questions for: %s", question)
            return []
