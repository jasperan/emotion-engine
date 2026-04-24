"""Tests for the post-simulation agent chat schemas."""

from emotionsim.api.chat import AgentChatRequest, AgentChatResponse


def test_agent_chat_request_creation():
    """AgentChatRequest accepts a non-empty message."""
    req = AgentChatRequest(message="Hello, what did you do during the flood?")
    assert req.message == "Hello, what did you do during the flood?"


def test_agent_chat_request_min_length():
    """AgentChatRequest rejects an empty string."""
    import pytest

    with pytest.raises(Exception):
        AgentChatRequest(message="")


def test_agent_chat_response_all_fields():
    """AgentChatResponse populates every field."""
    resp = AgentChatResponse(
        agent_name="Maria",
        response="I helped build the barrier near the river.",
        personality_context="Openness: 0.8, Conscientiousness: 0.9",
        memories_referenced=[
            "Helped stack sandbags at step 3",
            "Argued with Jonas about evacuation at step 7",
        ],
    )
    assert resp.agent_name == "Maria"
    assert "barrier" in resp.response
    assert "Openness" in resp.personality_context
    assert len(resp.memories_referenced) == 2


def test_agent_chat_response_defaults():
    """AgentChatResponse works with only required fields (defaults kick in)."""
    resp = AgentChatResponse(
        agent_name="Jonas",
        response="I tried to keep everyone calm.",
    )
    assert resp.agent_name == "Jonas"
    assert resp.personality_context == ""
    assert resp.memories_referenced == []
