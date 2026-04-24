"""Tests for document upload API Pydantic schemas"""
import pytest
from pydantic import ValidationError

from emotionsim.api.document import DocumentUploadRequest, DocumentUploadResponse


class TestDocumentUploadRequest:
    """Test DocumentUploadRequest schema validation"""

    def test_valid_request(self):
        req = DocumentUploadRequest(
            text="This is a sufficiently long document text for testing.",
            scenario_name="Test Scenario",
            scenario_description="A test scenario description",
            max_steps=50,
        )
        assert req.text == "This is a sufficiently long document text for testing."
        assert req.scenario_name == "Test Scenario"
        assert req.scenario_description == "A test scenario description"
        assert req.max_steps == 50

    def test_defaults(self):
        req = DocumentUploadRequest(
            text="This is a sufficiently long document text.",
            scenario_name="Minimal",
        )
        assert req.scenario_description == ""
        assert req.max_steps == 100

    def test_text_min_length(self):
        with pytest.raises(ValidationError) as exc_info:
            DocumentUploadRequest(
                text="short",
                scenario_name="Test",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("text",) for e in errors)

    def test_scenario_name_min_length(self):
        with pytest.raises(ValidationError) as exc_info:
            DocumentUploadRequest(
                text="This is a sufficiently long document text.",
                scenario_name="",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("scenario_name",) for e in errors)

    def test_max_steps_too_low(self):
        with pytest.raises(ValidationError) as exc_info:
            DocumentUploadRequest(
                text="This is a sufficiently long document text.",
                scenario_name="Test",
                max_steps=5,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("max_steps",) for e in errors)

    def test_max_steps_too_high(self):
        with pytest.raises(ValidationError) as exc_info:
            DocumentUploadRequest(
                text="This is a sufficiently long document text.",
                scenario_name="Test",
                max_steps=5000,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("max_steps",) for e in errors)

    def test_max_steps_boundary_low(self):
        req = DocumentUploadRequest(
            text="This is a sufficiently long document text.",
            scenario_name="Test",
            max_steps=10,
        )
        assert req.max_steps == 10

    def test_max_steps_boundary_high(self):
        req = DocumentUploadRequest(
            text="This is a sufficiently long document text.",
            scenario_name="Test",
            max_steps=1000,
        )
        assert req.max_steps == 1000


class TestDocumentUploadResponse:
    """Test DocumentUploadResponse schema validation"""

    def test_valid_response(self):
        resp = DocumentUploadResponse(
            graph_id="graph-abc-123",
            scenario_id="scenario-def-456",
            entity_count=15,
            relation_count=8,
            agent_count=5,
        )
        assert resp.graph_id == "graph-abc-123"
        assert resp.scenario_id == "scenario-def-456"
        assert resp.entity_count == 15
        assert resp.relation_count == 8
        assert resp.agent_count == 5

    def test_zero_counts(self):
        resp = DocumentUploadResponse(
            graph_id="g1",
            scenario_id="s1",
            entity_count=0,
            relation_count=0,
            agent_count=0,
        )
        assert resp.entity_count == 0
        assert resp.relation_count == 0
        assert resp.agent_count == 0

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            DocumentUploadResponse(
                graph_id="g1",
                # missing scenario_id
                entity_count=1,
                relation_count=1,
                agent_count=1,
            )

    def test_serialization_roundtrip(self):
        resp = DocumentUploadResponse(
            graph_id="g1",
            scenario_id="s1",
            entity_count=10,
            relation_count=5,
            agent_count=3,
        )
        data = resp.model_dump()
        assert data == {
            "graph_id": "g1",
            "scenario_id": "s1",
            "entity_count": 10,
            "relation_count": 5,
            "agent_count": 3,
        }
        # Reconstruct from dict
        resp2 = DocumentUploadResponse(**data)
        assert resp2 == resp
