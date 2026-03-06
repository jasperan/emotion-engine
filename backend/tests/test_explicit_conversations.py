import pytest
from app.simulation.conversation import ConversationManager, Conversation, ConversationType


class TestExplicitConversations:
    def test_create_explicit_conversation(self):
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
            topic="rescue plan",
            conversation_type=ConversationType.EXPLICIT,
        )
        assert conv is not None
        assert conv.topic == "rescue plan"
        assert conv.initiator_id == "a1"
        assert "a1" in conv.participants
        assert "a2" in conv.participants

    def test_join_conversation(self):
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
            topic="rescue plan",
        )
        result = cm.join_conversation(conv.id, "a3")
        assert result is True
        assert "a3" in conv.participants

    def test_join_rejects_over_max_participants(self):
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2", "a3", "a4", "a5"},
            location="shelter",
            topic="big meeting",
        )
        result = cm.join_conversation(conv.id, "a6")
        assert result is False
        assert "a6" not in conv.participants

    def test_leave_conversation(self):
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2", "a3"},
            location="shelter",
            topic="plan",
        )
        cm.leave_conversation(conv.id, "a3")
        assert "a3" not in conv.participants

    def test_conversation_ends_when_one_participant(self):
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
            topic="chat",
        )
        cm.leave_conversation(conv.id, "a2")
        assert not conv.should_continue()

    def test_max_conversations_per_location(self):
        cm = ConversationManager()
        cm.create_conversation(
            initiator_id="a1", participant_ids={"a1", "a2"},
            location="shelter", topic="plan A",
        )
        cm.create_conversation(
            initiator_id="a3", participant_ids={"a3", "a4"},
            location="shelter", topic="plan B",
        )
        conv3 = cm.create_conversation(
            initiator_id="a5", participant_ids={"a5", "a6"},
            location="shelter", topic="plan C",
        )
        assert conv3 is None

    def test_get_location_conversation_summaries(self):
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1", participant_ids={"a1", "a2"},
            location="shelter", topic="rescue plan",
        )
        summaries = cm.get_location_conversation_summaries("shelter", exclude_agent="a3")
        assert len(summaries) == 1
        assert "rescue plan" in summaries[0]["topic"]

    def test_update_agent_location_no_auto_join(self):
        """Moving to a location should NOT auto-join any conversation"""
        cm = ConversationManager()
        cm.create_conversation(
            initiator_id="a1", participant_ids={"a1", "a2"},
            location="shelter", topic="plan",
        )
        joined = cm.update_agent_location("a3", "shelter")
        assert len(joined) == 0
