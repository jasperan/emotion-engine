"""Tests for GraphToolsService and ReportAgent with mocked storage, embedding, and LLM."""

from __future__ import annotations

import json
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse
from emotionsim.services.graph_tools import GraphToolsService, InsightForgeResult
from emotionsim.services.report_agent import ReportAgent
from emotionsim.storage.graph_storage import Edge, Entity, GraphStorage, SearchResult


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_search_result(query: str = "test", facts: list[str] | None = None) -> SearchResult:
    """Build a SearchResult with sensible defaults."""
    facts = facts or ["fact-1", "fact-2"]
    return SearchResult(
        facts=facts,
        entities=[Entity(name="Alice", type="person", summary="leader")],
        edges=[Edge(source_id="a", target_id="b", type="trusts", fact="trust fact")],
        query=query,
        total_count=len(facts) + 1 + 1,
    )


@pytest.fixture
def mock_storage() -> AsyncMock:
    storage = AsyncMock(spec=GraphStorage)
    storage.search = AsyncMock(return_value=_make_search_result())
    storage.search_memories = AsyncMock(
        return_value=[
            {"content": "Decided to share supplies", "importance": 8},
            {"content": "Built a raft", "importance": 7},
        ]
    )
    return storage


@pytest.fixture
def mock_embedding() -> AsyncMock:
    embedding = AsyncMock()
    embedding.embed_text = AsyncMock(return_value=[0.1] * 768)
    return embedding


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock(spec=LLMClient)
    # Default: return sub-questions JSON for insight_forge
    sub_q_json = json.dumps(["What events happened?", "What decisions were made?", "Who cooperated?"])
    llm.generate = AsyncMock(
        return_value=LLMResponse(content=sub_q_json, raw_response=None, usage=None)
    )
    return llm


# ---------------------------------------------------------------------------
# InsightForge tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insight_forge(mock_storage: AsyncMock, mock_embedding: AsyncMock, mock_llm: AsyncMock):
    """InsightForge should decompose the question, search graph, and return aggregated findings."""
    service = GraphToolsService(
        storage=mock_storage,
        embedding_service=mock_embedding,
        llm_client=mock_llm,
    )

    result = await service.insight_forge("graph-1", "What happened?")

    assert isinstance(result, InsightForgeResult)
    assert result.question == "What happened?"
    assert len(result.sub_questions) == 3
    assert len(result.findings) > 0
    assert len(result.evidence) > 0

    # Should have searched: original question + 3 sub-questions = 4 calls
    assert mock_storage.search.call_count == 4

    # to_text should produce readable output
    text = result.to_text()
    assert "InsightForge" in text
    assert "Findings" in text


@pytest.mark.asyncio
async def test_insight_forge_no_llm(mock_storage: AsyncMock):
    """Without an LLM client, InsightForge should still work (no sub-questions)."""
    service = GraphToolsService(storage=mock_storage, embedding_service=None, llm_client=None)

    result = await service.insight_forge("graph-1", "What happened?")

    assert result.question == "What happened?"
    assert result.sub_questions == []
    # Only the original question searched
    assert mock_storage.search.call_count == 1
    assert len(result.findings) > 0


# ---------------------------------------------------------------------------
# PanoramaSearch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_panorama_search(mock_storage: AsyncMock):
    """PanoramaSearch should return a SearchResult from a wildcard query."""
    service = GraphToolsService(storage=mock_storage)

    result = await service.panorama_search("graph-1", limit=20)

    assert isinstance(result, SearchResult)
    mock_storage.search.assert_called_once_with("graph-1", query="*", limit=20)


# ---------------------------------------------------------------------------
# ReportAgent tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_report(mock_storage: AsyncMock, mock_embedding: AsyncMock, mock_llm: AsyncMock):
    """ReportAgent should produce a non-empty string report."""
    # Make the LLM return sub-questions first, then a report.
    sub_q_json = json.dumps(["q1", "q2", "q3"])
    report_text = "# Simulation Report\n\nKey events occurred."

    mock_llm.generate = AsyncMock(
        side_effect=[
            # First call: sub-question generation (from InsightForge)
            LLMResponse(content=sub_q_json, raw_response=None, usage=None),
            # Second call: report generation
            LLMResponse(content=report_text, raw_response=None, usage=None),
        ]
    )

    agent = ReportAgent(
        storage=mock_storage,
        embedding_service=mock_embedding,
        llm_client=mock_llm,
    )

    result = await agent.generate_report(
        run_id="run-123",
        graph_id="graph-1",
        scenario_name="The Great Flood",
        agent_ids=["agent-1", "agent-2"],
    )

    assert isinstance(result, str)
    assert len(result) > 0
    assert "Simulation Report" in result

    # Verify agent memories were fetched
    assert mock_storage.search_memories.call_count == 2


@pytest.mark.asyncio
async def test_generate_report_no_llm(mock_storage: AsyncMock):
    """Without an LLM, ReportAgent should return raw context as the report."""
    agent = ReportAgent(storage=mock_storage, embedding_service=None, llm_client=None)

    result = await agent.generate_report(
        run_id="run-456",
        graph_id="graph-2",
        scenario_name="Test Scenario",
    )

    assert isinstance(result, str)
    assert len(result) > 0
    assert "Test Scenario" in result
    assert "InsightForge" in result
    assert "PanoramaSearch" not in result or "Breadth View" in result


@pytest.mark.asyncio
async def test_generate_report_no_agents(mock_storage: AsyncMock, mock_embedding: AsyncMock, mock_llm: AsyncMock):
    """ReportAgent should work fine without agent_ids."""
    sub_q_json = json.dumps(["q1", "q2", "q3"])
    report_text = "# Report\n\nNo agent memories available."

    mock_llm.generate = AsyncMock(
        side_effect=[
            LLMResponse(content=sub_q_json, raw_response=None, usage=None),
            LLMResponse(content=report_text, raw_response=None, usage=None),
        ]
    )

    agent = ReportAgent(
        storage=mock_storage,
        embedding_service=mock_embedding,
        llm_client=mock_llm,
    )

    result = await agent.generate_report(
        run_id="run-789",
        graph_id="graph-3",
    )

    assert isinstance(result, str)
    assert len(result) > 0
    # No agent memories should have been fetched
    assert mock_storage.search_memories.call_count == 0
