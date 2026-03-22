"""Battle-hardening tests: edge cases, malformed inputs, and failure modes.

Targets the dark corners of JSON parsing, movement, messaging,
conversations, trust, emotion contagion, scene direction, negotiation,
and goal trees. Each test documents how the system handles (or should
handle) degenerate inputs.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.simulation.message_bus import MessageBus
from app.simulation.conversation import (
    Conversation,
    ConversationManager,
    ConversationState,
    ConversationType,
)
from app.simulation.scene_director import SceneDirector
from app.simulation.trust_network import TrustNetwork, TrustSignal
from app.simulation.negotiation import NegotiationManager, ProposalState
from app.simulation.emotion_contagion import EmotionContagion
from app.simulation.goal_tree import GoalTree, GoalNode, GoalLevel, GoalStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_base_agent():
    """Create a minimal concrete Agent for testing parse/extract methods."""
    from app.agents.base import Agent

    class _StubAgent(Agent):
        async def tick(self, *a, **kw):
            pass

        def get_system_prompt(self):
            return "stub"

        def build_context(self, *a, **kw):
            return "stub"

    with patch("app.agents.base.LLMRouter") as mock_router:
        mock_router.get_client.return_value = MagicMock()
        agent = _StubAgent(agent_id="stub-id", name="Stub")

    agent.dynamic_state = {"stress_level": 5}
    agent._last_cinematic = {}
    return agent


def _make_mock_agent(agent_id, name, location, stress=5, extraversion=5,
                     neuroticism=5, role="human"):
    """Create a lightweight mock agent for contagion / scene tests."""
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.role = role
    agent.dynamic_state = {"stress_level": stress, "location": location}
    agent.persona = MagicMock()
    agent.persona.extraversion = extraversion
    agent.persona.neuroticism = neuroticism
    return agent


def _make_engine_stub():
    """Create a minimal SimulationEngine-like object with just the methods we test.

    Avoids importing the real engine (which requires DB session) by
    pulling the pure-logic methods onto a lightweight stand-in.
    """
    import collections
    from app.simulation.engine import SimulationEngine

    class _Stub:
        pass

    stub = _Stub()
    # Bind the unbound methods we care about
    stub._fuzzy_match_location = SimulationEngine._fuzzy_match_location.__get__(stub)
    stub._find_path = SimulationEngine._find_path.__get__(stub)
    stub._hop_cache = {}
    return stub


# ===================================================================
# 1. JSON Parsing Edge Cases (BaseAgent)
# ===================================================================

class TestJsonParsingEdgeCases:
    """Exercises _extract_json, _parse_json_response, _clean_response_text."""

    def test_empty_string_response(self):
        """Empty LLM output should produce a fallback AgentResponse with no message."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        resp = LLMResponse(content="", raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.actions == []
        assert result.message is None

    def test_pure_whitespace_response(self):
        """Whitespace-only output should not crash and should fall back gracefully."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        resp = LLMResponse(content="   \n\t  \n  ", raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.actions == []
        # Whitespace-only becomes empty after strip, so no message
        assert result.message is None

    def test_json_inside_markdown_code_block(self):
        """JSON wrapped in ```json ... ``` should be extracted and parsed."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        payload = '```json\n{"actions": [], "message": {"content": "hi", "to_target": "broadcast", "message_type": "broadcast"}, "state_changes": {}, "reasoning": "ok"}\n```'
        resp = LLMResponse(content=payload, raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.message is not None
        assert result.message.content == "hi"

    def test_json_inside_bare_code_block(self):
        """JSON wrapped in ``` ... ``` (no language hint) should still be extracted."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        payload = '```\n{"actions": [], "message": null, "state_changes": {}, "reasoning": "bare block"}\n```'
        resp = LLMResponse(content=payload, raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.reasoning == "bare block"

    def test_multiple_json_objects_picks_first(self):
        """When text contains several JSON blobs, _extract_json grabs the first one."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        payload = 'Some text {"actions": [], "reasoning": "first"} and then {"actions": [], "reasoning": "second"}'
        resp = LLMResponse(content=payload, raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.reasoning == "first"

    def test_truncated_json_falls_back(self):
        """Incomplete JSON should not crash; should fall back to natural language."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        payload = '{"actions": [{"action_type": "move", "target": "shelter"'
        resp = LLMResponse(content=payload, raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        # Truncated JSON starts with '{', so _clean_response_text tries to
        # extract a "content" field. With none present, message should be None.
        assert result.actions == []

    def test_unicode_emoji_in_json_values(self):
        """Unicode and emoji in JSON values should parse fine."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "actions": [],
            "message": {
                "content": "Help! 🔥🌊 We need to evacuate — now!",
                "to_target": "broadcast",
                "message_type": "broadcast",
            },
            "state_changes": {},
            "reasoning": "日本語テスト",
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert "🔥" in result.message.content
        assert result.reasoning == "日本語テスト"

    def test_null_values_for_required_fields(self):
        """Null message, null actions list should not crash."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {"actions": None, "message": None, "state_changes": None, "reasoning": None}
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.actions == []
        assert result.message is None

    def test_extra_unexpected_fields_ignored(self):
        """Extra keys in the JSON should be silently ignored."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "actions": [],
            "message": None,
            "state_changes": {},
            "reasoning": "ok",
            "hallucinated_field": True,
            "random_number": 42,
            "nested_garbage": {"x": [1, 2, 3]},
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.reasoning == "ok"

    def test_action_target_as_integer(self):
        """LLM sometimes returns a number as target; should be coerced to string."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "actions": [{"action_type": "move", "target": 42, "parameters": {}}],
            "message": None,
            "state_changes": {},
            "reasoning": "",
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert len(result.actions) == 1
        assert result.actions[0].target == "42"

    def test_action_target_as_empty_string(self):
        """Empty string target should become None."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "actions": [{"action_type": "wait", "target": "  ", "parameters": {}}],
            "message": None,
            "state_changes": {},
            "reasoning": "",
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.actions[0].target is None

    def test_message_type_invalid_falls_back_to_broadcast(self):
        """Invalid message_type should be corrected to 'broadcast'."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "actions": [],
            "message": {
                "content": "Hello",
                "to_target": "broadcast",
                "message_type": "yell",
            },
            "state_changes": {},
            "reasoning": "",
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.message.message_type == "broadcast"

    def test_message_to_target_none_falls_back(self):
        """None to_target should be corrected to 'broadcast'."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "actions": [],
            "message": {
                "content": "Hello",
                "to_target": None,
                "message_type": "broadcast",
            },
            "state_changes": {},
            "reasoning": "",
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.message.to_target == "broadcast"

    def test_message_as_string_not_dict(self):
        """LLM sometimes returns message as a plain string."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "actions": [],
            "message": "Help me please!",
            "state_changes": {},
            "reasoning": "",
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert result.message is not None
        assert result.message.content == "Help me please!"
        assert result.message.message_type == "broadcast"

    def test_clean_response_text_strips_json_block(self):
        """_clean_response_text should strip markdown JSON blocks from natural text."""
        agent = _make_base_agent()
        text = 'Here is my response:\n```json\n{"key": "val"}\n```\nDone.'
        cleaned = agent._clean_response_text(text)
        assert "```" not in cleaned
        assert "Done." in cleaned

    def test_clean_response_text_extracts_content_from_partial_json(self):
        """If text looks like JSON, try to extract a content field."""
        agent = _make_base_agent()
        text = '{"content": "extracted message", "other": 123}'
        cleaned = agent._clean_response_text(text)
        assert cleaned == "extracted message"

    def test_cinematic_schema_normalization(self):
        """New cinematic schema with all fields should normalize correctly."""
        agent = _make_base_agent()
        from app.llm.base import LLMResponse
        import json
        data = {
            "action": "She dives under the table.",
            "speech": "Get down!",
            "thought": "This is bad.",
            "emotion": "terror",
            "move_to": "basement",
            "stress_level": 9,
        }
        resp = LLMResponse(content=json.dumps(data), raw_response={}, usage={})
        result = agent.parse_llm_response(resp)
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "move"
        assert result.actions[0].target == "basement"
        assert result.message.content == "Get down!"


# ===================================================================
# 2. Movement System Edge Cases (Engine)
# ===================================================================

class TestFuzzyMatchLocation:
    """Tests for SimulationEngine._fuzzy_match_location."""

    def test_empty_location_list(self):
        """Matching against an empty list should return None."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("shelter", []) is None

    def test_exact_match(self):
        """Exact match should return the location."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("shelter", ["shelter", "rooftop"]) == "shelter"

    def test_case_insensitive_match(self):
        """Matching should be case-insensitive."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("SHELTER", ["shelter", "rooftop"]) == "shelter"

    def test_the_prefix_stripped(self):
        """'the shelter' should match 'shelter'."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("the shelter", ["shelter", "rooftop"]) == "shelter"

    def test_a_prefix_stripped(self):
        """'a shelter' should match 'shelter'."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("a shelter", ["shelter"]) == "shelter"

    def test_underscore_space_equivalence(self):
        """'main hall' should match 'main_hall' and vice versa."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("main hall", ["main_hall"]) == "main_hall"
        assert eng._fuzzy_match_location("main_hall", ["main hall"]) == "main hall"

    def test_substring_match(self):
        """'hall' should match 'main_hall' via substring containment."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("hall", ["main_hall", "rooftop"]) == "main_hall"

    def test_no_match_returns_none(self):
        """Completely unrelated target should return None."""
        eng = _make_engine_stub()
        assert eng._fuzzy_match_location("atlantis", ["shelter", "rooftop"]) is None

    def test_exact_match_priority_over_substring(self):
        """If both exact and substring match exist, exact should win because it's checked first."""
        eng = _make_engine_stub()
        # 'hall' is exact match for first item, and substring of 'main_hall'
        result = eng._fuzzy_match_location("hall", ["hall", "main_hall"])
        assert result == "hall"


class TestFindPath:
    """Tests for SimulationEngine._find_path (BFS pathfinding)."""

    def test_source_equals_destination(self):
        """Path from A to A should be [A]."""
        eng = _make_engine_stub()
        locations = {"A": {"nearby": ["B"]}}
        assert eng._find_path("A", "A", locations) == ["A"]

    def test_direct_neighbor(self):
        """Direct neighbor should produce a 2-element path."""
        eng = _make_engine_stub()
        locations = {
            "A": {"nearby": ["B"]},
            "B": {"nearby": ["A"]},
        }
        path = eng._find_path("A", "B", locations)
        assert path == ["A", "B"]

    def test_multi_hop_path(self):
        """A -> B -> C should produce a 3-element path."""
        eng = _make_engine_stub()
        locations = {
            "A": {"nearby": ["B"]},
            "B": {"nearby": ["A", "C"]},
            "C": {"nearby": ["B"]},
        }
        path = eng._find_path("A", "C", locations)
        assert path == ["A", "B", "C"]

    def test_no_path_disconnected_graph(self):
        """Disconnected locations should return None."""
        eng = _make_engine_stub()
        locations = {
            "A": {"nearby": ["B"]},
            "B": {"nearby": ["A"]},
            "C": {"nearby": ["D"]},
            "D": {"nearby": ["C"]},
        }
        assert eng._find_path("A", "C", locations) is None

    def test_circular_connections(self):
        """Circular graph should not cause infinite loop."""
        eng = _make_engine_stub()
        locations = {
            "A": {"nearby": ["B"]},
            "B": {"nearby": ["C"]},
            "C": {"nearby": ["A"]},
        }
        path = eng._find_path("A", "C", locations)
        assert path is not None
        assert path[-1] == "C"

    def test_nonexistent_target(self):
        """Target not in locations dict should return None."""
        eng = _make_engine_stub()
        locations = {
            "A": {"nearby": ["B"]},
            "B": {"nearby": ["A"]},
        }
        assert eng._find_path("A", "Z", locations) is None

    def test_nonexistent_source(self):
        """Source not in locations dict should return None (empty neighbors)."""
        eng = _make_engine_stub()
        locations = {
            "A": {"nearby": ["B"]},
            "B": {"nearby": ["A"]},
        }
        assert eng._find_path("Z", "A", locations) is None

    def test_empty_locations_dict(self):
        """Empty locations dict; source != target should return None."""
        eng = _make_engine_stub()
        assert eng._find_path("A", "B", {}) is None

    def test_shortest_path_chosen(self):
        """BFS should find the shortest path, not just any path."""
        eng = _make_engine_stub()
        locations = {
            "A": {"nearby": ["B", "D"]},
            "B": {"nearby": ["A", "C"]},
            "C": {"nearby": ["B", "D"]},
            "D": {"nearby": ["A", "C"]},
        }
        path = eng._find_path("A", "C", locations)
        # Both A->B->C and A->D->C are length 3; BFS finds one of them
        assert len(path) == 3


# ===================================================================
# 3. Message Bus Edge Cases
# ===================================================================

class TestMessageBusEdgeCases:

    def test_send_to_empty_room(self):
        """Sending to a room with no members should not crash."""
        bus = MessageBus()
        bus.register_agent("sender")
        msg = bus.send_to_room("sender", "empty_room", "Hello?", step_index=1)
        assert msg["message_type"] == "room"
        # No one to receive, history still records it
        assert len(bus.get_history()) == 1

    def test_direct_message_to_unregistered_agent(self):
        """Sending to a non-existent agent should still record in history."""
        bus = MessageBus()
        bus.register_agent("sender")
        msg = bus.send_direct("sender", "ghost", "Hello?", step_index=1)
        assert msg is not None
        assert len(bus.get_history()) == 1
        # ghost has no queue entry, so message goes into the void
        messages = bus.get_messages("ghost")
        assert len(messages) == 0

    def test_broadcast_to_empty_agent_list(self):
        """Broadcasting when no agents are registered should not crash."""
        bus = MessageBus()
        msg = bus.broadcast("system", "Alert!", step_index=1)
        assert msg is not None
        assert len(bus.get_history()) == 1

    def test_callback_exception_does_not_break_delivery(self):
        """A failing callback should not prevent message delivery."""
        bus = MessageBus()
        bus.register_agent("a1")
        bus.register_agent("a2")

        def bad_callback(msg):
            raise RuntimeError("Callback exploded")

        bus.on_message(bad_callback)
        # Should not raise
        msg = bus.send_direct("a1", "a2", "Still works", step_index=1)
        assert msg is not None
        messages = bus.get_messages("a2")
        assert len(messages) == 1

    def test_very_long_message_content(self):
        """10,000+ character message should be handled without truncation or crash."""
        bus = MessageBus()
        bus.register_agent("a1")
        bus.register_agent("a2")
        long_content = "x" * 15000
        msg = bus.send_direct("a1", "a2", long_content, step_index=1)
        assert len(msg["content"]) == 15000
        received = bus.get_messages("a2")
        assert len(received[0]["content"]) == 15000

    def test_none_sender_broadcast(self):
        """Broadcast with None sender (system message) should work."""
        bus = MessageBus()
        bus.register_agent("a1")
        msg = bus.broadcast(None, "System reboot", step_index=1)
        assert msg["from_agent"] is None
        assert msg["from_agent_name"] == "System"
        messages = bus.get_messages("a1")
        assert len(messages) == 1

    def test_peek_does_not_clear_queue(self):
        """peek_messages should return messages without clearing them."""
        bus = MessageBus()
        bus.register_agent("a1")
        bus.register_agent("a2")
        bus.send_direct("a1", "a2", "peek test", step_index=1)
        peeked = bus.peek_messages("a2")
        assert len(peeked) == 1
        # Queue should still be intact
        actual = bus.get_messages("a2")
        assert len(actual) == 1

    def test_get_messages_for_unregistered_agent(self):
        """Getting messages for an agent that was never registered."""
        bus = MessageBus()
        messages = bus.get_messages("nobody")
        assert messages == []

    def test_conversation_message_routing(self):
        """Conversation messages should go to all participants except sender."""
        bus = MessageBus()
        bus.register_agent("a1")
        bus.register_agent("a2")
        bus.register_agent("a3")
        participants = {"a1", "a2", "a3"}
        msg = bus.send_to_conversation("a1", "conv-1", participants, "Group chat", step_index=1)
        assert msg["message_type"] == "conversation"
        # a2 and a3 get it, a1 does not
        assert len(bus.get_messages("a1")) == 0
        assert len(bus.get_messages("a2")) == 1
        assert len(bus.get_messages("a3")) == 1

    def test_clear_resets_everything(self):
        """clear() should wipe all state."""
        bus = MessageBus()
        bus.register_agent("a1")
        bus.join_room("a1", "room")
        bus.broadcast("a1", "msg", step_index=1)
        bus.clear()
        assert len(bus._all_agents) == 0
        assert len(bus._message_history) == 0
        assert len(bus._room_subscriptions) == 0


# ===================================================================
# 4. Conversation Edge Cases
# ===================================================================

class TestConversationEdgeCases:

    def test_add_same_participant_twice(self):
        """Adding the same participant twice should return False the second time."""
        conv = Conversation(location="shelter")
        assert conv.add_participant("a1") is True
        assert conv.add_participant("a1") is False
        assert len(conv.participants) == 1

    def test_conversation_at_max_participants(self):
        """Should not be able to exceed MAX_PARTICIPANTS."""
        mgr = ConversationManager()
        conv_id = mgr.start_explicit_conversation("a1", ["a2", "a3", "a4", "a5"])
        # Already at 5 participants (a1 + 4 targets)
        result = mgr.join_conversation(conv_id, "a6")
        assert result is False

    def test_add_message_after_conversation_ended(self):
        """Adding a message to an ended conversation still appends (no guard)."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        conv.add_participant("a2")
        conv.end()
        assert conv.state == ConversationState.ENDED
        # add_message has no state guard; it just appends
        conv.add_message({"content": "ghost message"})
        assert len(conv.message_history) == 1

    def test_should_continue_with_one_participant(self):
        """Conversation with < 2 participants should not continue."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        assert conv.should_continue() is False

    def test_should_continue_after_max_passes(self):
        """Conversation should end after too many consecutive passes."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        conv.add_participant("a2")
        # Simulate consecutive passes
        for _ in range(3):
            conv.advance_turn(spoke=False)
        assert conv.should_continue() is False

    def test_should_continue_after_max_turns(self):
        """Conversation should stop after max_turns_per_step."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        conv.add_participant("a2")
        conv.max_turns_per_step = 3
        for _ in range(3):
            conv.advance_turn(spoke=True)
        assert conv.should_continue() is False

    def test_get_next_speaker_after_end(self):
        """get_next_speaker should return None for ended conversation."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        conv.add_participant("a2")
        conv.end()
        assert conv.get_next_speaker() is None

    def test_get_next_speaker_empty_conversation(self):
        """get_next_speaker with no participants should return None."""
        conv = Conversation(location="shelter")
        assert conv.get_next_speaker() is None

    def test_remove_participant_ends_conversation(self):
        """Removing a participant from a 2-person conversation should end it."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        conv.add_participant("a2")
        conv.remove_participant("a2")
        assert conv.state == ConversationState.ENDED

    def test_remove_nonexistent_participant(self):
        """Removing someone who isn't in the conversation returns False."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        assert conv.remove_participant("ghost") is False

    def test_pause_and_resume(self):
        """Pausing and resuming should toggle state correctly."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        conv.add_participant("a2")
        conv.pause()
        assert conv.state == ConversationState.PAUSED
        assert conv.get_next_speaker() is None  # paused = no speaker
        conv.resume()
        assert conv.state == ConversationState.ACTIVE
        assert conv.get_next_speaker() is not None

    def test_resume_non_paused_is_noop(self):
        """Resuming an active conversation should be a no-op."""
        conv = Conversation(location="shelter")
        conv.add_participant("a1")
        conv.add_participant("a2")
        conv.resume()  # already active
        assert conv.state == ConversationState.ACTIVE

    def test_manager_location_limit(self):
        """ConversationManager should enforce MAX_PER_LOCATION."""
        mgr = ConversationManager()
        # Create MAX_PER_LOCATION conversations at same location
        for i in range(ConversationManager.MAX_PER_LOCATION):
            result = mgr.create_conversation(
                initiator_id=f"a{i}",
                participant_ids={f"a{i}", f"b{i}"},
                location="shelter",
            )
            assert result is not None
        # Next one should be rejected
        result = mgr.create_conversation(
            initiator_id="overflow",
            participant_ids={"overflow", "partner"},
            location="shelter",
        )
        assert result is None

    def test_cleanup_ended_conversations(self):
        """cleanup_ended_conversations should remove ended ones and return their IDs."""
        mgr = ConversationManager()
        conv = mgr.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
        )
        conv_id = conv.id
        mgr.end_conversation(conv_id)
        ended = mgr.cleanup_ended_conversations()
        assert conv_id in ended
        assert mgr.get_conversation(conv_id) is None


# ===================================================================
# 5. Trust Network Edge Cases
# ===================================================================

class TestTrustNetworkEdgeCases:

    def test_self_trust_record(self):
        """Recording trust change from an agent to itself should work without crashing."""
        tn = TrustNetwork()
        signal = tn.record_trust_change("a1", "a1", old_trust=5, new_trust=8, reason="self-reflection", step=1)
        # Delta is 3, which is >= SIGNIFICANT_DELTA, so a signal is emitted
        assert signal is not None
        assert signal.from_agent == "a1"
        assert signal.to_agent == "a1"

    def test_small_delta_no_signal(self):
        """Trust change < SIGNIFICANT_DELTA should not emit a signal."""
        tn = TrustNetwork()
        signal = tn.record_trust_change("a1", "a2", old_trust=5, new_trust=6, reason="minor", step=1)
        assert signal is None

    def test_exactly_significant_delta(self):
        """Trust change == SIGNIFICANT_DELTA should emit a signal."""
        tn = TrustNetwork()
        signal = tn.record_trust_change("a1", "a2", old_trust=5, new_trust=7, reason="threshold", step=1)
        assert signal is not None
        assert signal.signal_type == "warming"

    def test_trust_score_extreme_values(self):
        """Extremely high or low trust values should not crash."""
        tn = TrustNetwork()
        # Very negative trust
        signal = tn.record_trust_change("a1", "a2", old_trust=10, new_trust=-100, reason="extreme hate", step=1)
        assert signal is not None
        assert signal.signal_type == "cooling"
        assert signal.trust_level == -100  # The network doesn't clamp; it records what's given

    def test_trust_for_nonexistent_pair(self):
        """Getting pending signals for an agent that has none should return empty list."""
        tn = TrustNetwork()
        signals = tn.get_pending_signals("nobody")
        assert signals == []

    def test_context_empty_when_no_signals(self):
        """Trust context for an agent with no signals should be empty string."""
        tn = TrustNetwork()
        ctx = tn.get_trust_context("nobody")
        assert ctx == ""

    def test_betrayal_then_vouch_recovery(self):
        """Cooling signal followed by vouching signal should both appear."""
        tn = TrustNetwork()
        tn.record_trust_change("a1", "a2", old_trust=7, new_trust=2, reason="betrayal", step=1)
        tn.vouch_for("a3", "a1", ["a2"], step=2, reason="actually trustworthy")
        signals = tn.get_pending_signals("a2", clear=False)
        assert len(signals) == 2
        types = {s.signal_type for s in signals}
        assert "cooling" in types
        assert "vouching" in types

    def test_vouch_for_creates_signals_for_all_recipients(self):
        """Vouching should create a signal for each recipient."""
        tn = TrustNetwork()
        signals = tn.vouch_for("voucher", "subject", ["r1", "r2", "r3"], step=1)
        assert len(signals) == 3
        for sig in signals:
            assert sig.signal_type == "vouching"

    def test_get_pending_clears_by_default(self):
        """get_pending_signals should clear after retrieval by default."""
        tn = TrustNetwork()
        tn.record_trust_change("a1", "a2", old_trust=3, new_trust=8, reason="help", step=1)
        first = tn.get_pending_signals("a2")
        assert len(first) == 1
        second = tn.get_pending_signals("a2")
        assert len(second) == 0

    def test_signal_history_persists_after_clear(self):
        """Clearing pending signals should not affect the permanent history."""
        tn = TrustNetwork()
        tn.record_trust_change("a1", "a2", old_trust=3, new_trust=8, reason="help", step=1)
        tn.get_pending_signals("a2", clear=True)
        history = tn.get_signal_history(agent_id="a2")
        assert len(history) == 1


# ===================================================================
# 6. Emotion Contagion Edge Cases
# ===================================================================

class TestEmotionContagionEdgeCases:

    def test_zero_agents(self):
        """Propagate with empty list should return empty."""
        ec = EmotionContagion()
        events = ec.propagate([], {}, step=1, location="x")
        assert events == []

    def test_one_agent(self):
        """Single agent can't spread emotions."""
        ec = EmotionContagion()
        agents = {"a1": _make_mock_agent("a1", "Alice", "shelter", stress=10)}
        events = ec.propagate(["a1"], agents, step=1, location="shelter")
        assert events == []

    def test_all_agents_at_max_stress(self):
        """All agents at stress=10 should have no differential to spread."""
        ec = EmotionContagion(spread_rate=1.0, max_delta_per_step=5)
        agents = {
            "a1": _make_mock_agent("a1", "Alice", "shelter", stress=10, extraversion=10),
            "a2": _make_mock_agent("a2", "Bob", "shelter", stress=10, neuroticism=10),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        # No differential (both at 10), so no contagion
        assert events == []

    def test_all_agents_at_zero_stress(self):
        """All agents at stress=1 (minimum) should have no spread."""
        ec = EmotionContagion(spread_rate=1.0, max_delta_per_step=5)
        agents = {
            "a1": _make_mock_agent("a1", "Alice", "shelter", stress=1, extraversion=10),
            "a2": _make_mock_agent("a2", "Bob", "shelter", stress=1, neuroticism=10),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        assert events == []

    def test_agent_missing_from_dict(self):
        """Agent ID in scene list but missing from agents dict should be skipped."""
        ec = EmotionContagion()
        agents = {"a1": _make_mock_agent("a1", "Alice", "shelter", stress=9)}
        events = ec.propagate(["a1", "missing_agent"], agents, step=1, location="shelter")
        assert events == []

    def test_non_human_agent_filtered(self):
        """Non-human agents should be filtered out, potentially leaving < 2 humans."""
        ec = EmotionContagion()
        agents = {
            "h1": _make_mock_agent("h1", "Human", "shelter", stress=9, role="human"),
            "env": _make_mock_agent("env", "Environment", "shelter", stress=1, role="environment"),
        }
        events = ec.propagate(["h1", "env"], agents, step=1, location="shelter")
        assert events == []


# ===================================================================
# 7. Scene Director Edge Cases
# ===================================================================

class TestSceneDirectorEdgeCases:

    def test_zero_agents(self):
        """Grouping with no agents should return empty dict."""
        sd = SceneDirector()
        result = sd.group_agents_by_location({}, {})
        assert result == {}

    def test_all_agents_same_location(self):
        """All agents at one location should produce a single group."""
        sd = SceneDirector()
        agents = {
            "a1": _make_mock_agent("a1", "Alice", "shelter"),
            "a2": _make_mock_agent("a2", "Bob", "shelter"),
            "a3": _make_mock_agent("a3", "Carol", "shelter"),
        }
        locations = {"a1": "shelter", "a2": "shelter", "a3": "shelter"}
        result = sd.group_agents_by_location(agents, locations)
        assert len(result) == 1
        assert "shelter" in result
        assert len(result["shelter"]) == 3

    def test_agent_with_none_location_uses_dynamic_state(self):
        """Agent not in location dict should fall back to dynamic_state['location']."""
        sd = SceneDirector()
        agent = _make_mock_agent("a1", "Alice", "fallback_loc")
        agents = {"a1": agent}
        locations = {}  # a1 not in location map
        result = sd.group_agents_by_location(agents, locations)
        assert "fallback_loc" in result

    def test_non_human_agents_excluded(self):
        """Only human agents should be included in scene groups."""
        sd = SceneDirector()
        agents = {
            "h1": _make_mock_agent("h1", "Human", "shelter", role="human"),
            "env": _make_mock_agent("env", "Env", "shelter", role="environment"),
        }
        locations = {"h1": "shelter", "env": "shelter"}
        result = sd.group_agents_by_location(agents, locations)
        assert len(result.get("shelter", [])) == 1

    def test_pick_initiator_empty_list_raises(self):
        """pick_initiator with empty list should raise ValueError."""
        sd = SceneDirector()
        with pytest.raises(ValueError):
            sd.pick_initiator([], {})

    def test_pick_initiator_highest_extraversion(self):
        """Initiator should be the agent with highest extraversion."""
        sd = SceneDirector()
        a1 = _make_mock_agent("a1", "Alice", "shelter", extraversion=3)
        a2 = _make_mock_agent("a2", "Bob", "shelter", extraversion=9)
        agents = {"a1": a1, "a2": a2}
        initiator = sd.pick_initiator(["a1", "a2"], agents)
        assert initiator == "a2"

    def test_build_scene_participants_summary_alone(self):
        """Summary with only the excluded agent should say '(you are alone)'."""
        sd = SceneDirector()
        agents = {"a1": _make_mock_agent("a1", "Alice", "shelter")}
        summary = sd.build_scene_participants_summary(["a1"], agents, "a1")
        assert "you are alone" in summary

    def test_build_scene_participants_summary_with_others(self):
        """Summary should list other agents with their emotional state."""
        sd = SceneDirector()
        agents = {
            "a1": _make_mock_agent("a1", "Alice", "shelter", stress=3),
            "a2": _make_mock_agent("a2", "Bob", "shelter", stress=9),
        }
        summary = sd.build_scene_participants_summary(["a1", "a2"], agents, "a1")
        assert "Bob" in summary
        assert "desperate" in summary  # stress >= 8


# ===================================================================
# 8. Negotiation Edge Cases
# ===================================================================

class TestNegotiationEdgeCases:

    def test_empty_proposal_description(self):
        """Creating a proposal with empty description should still work."""
        nm = NegotiationManager()
        prop = nm.create_proposal(
            proposer_id="a1",
            target_id="a2",
            proposal_type="task",
            description="",
            parameters={},
            current_step=1,
        )
        assert prop.description == ""
        assert prop.state == ProposalState.PENDING

    def test_proposal_to_self(self):
        """Proposing to yourself is technically allowed (no guard against it)."""
        nm = NegotiationManager()
        prop = nm.create_proposal(
            proposer_id="a1",
            target_id="a1",
            proposal_type="task",
            description="self-task",
            parameters={},
            current_step=1,
        )
        assert prop.proposer_id == "a1"
        assert prop.target_id == "a1"
        # But get_pending_proposals_for_agent filters out proposals where proposer == agent
        pending = nm.get_pending_proposals_for_agent("a1")
        assert len(pending) == 0  # Self-proposals are excluded from pending

    def test_proposal_with_no_target(self):
        """Open proposal (target_id=None) should be visible to everyone."""
        nm = NegotiationManager()
        nm.create_proposal(
            proposer_id="a1",
            target_id=None,
            proposal_type="cooperation",
            description="Anyone want to help?",
            parameters={},
            current_step=1,
        )
        # Should be visible to a2 (target_id is None, matches all)
        pending = nm.get_pending_proposals_for_agent("a2")
        assert len(pending) == 1

    def test_accept_nonexistent_proposal(self):
        """Accepting a proposal that doesn't exist should return None."""
        nm = NegotiationManager()
        result = nm.accept_proposal("fake_id", "a1", current_step=1)
        assert result is None

    def test_reject_nonexistent_proposal(self):
        """Rejecting a non-existent proposal should return False."""
        nm = NegotiationManager()
        assert nm.reject_proposal("fake_id", "a1", current_step=1) is False

    def test_double_accept(self):
        """Accepting an already-accepted proposal should return None."""
        nm = NegotiationManager()
        prop = nm.create_proposal("a1", "a2", "task", "help", {}, current_step=1)
        agreement = nm.accept_proposal(prop.id, "a2", current_step=2)
        assert agreement is not None
        # Try accepting again
        result = nm.accept_proposal(prop.id, "a2", current_step=3)
        assert result is None

    def test_reject_after_accept(self):
        """Rejecting an already-accepted proposal should fail."""
        nm = NegotiationManager()
        prop = nm.create_proposal("a1", "a2", "task", "help", {}, current_step=1)
        nm.accept_proposal(prop.id, "a2", current_step=2)
        result = nm.reject_proposal(prop.id, "a2", current_step=3)
        assert result is False

    def test_counter_propose(self):
        """Counter-proposal should change state to COUNTER_PENDING."""
        nm = NegotiationManager()
        prop = nm.create_proposal("a1", "a2", "trade", "swap items", {}, current_step=1)
        result = nm.counter_propose(prop.id, "a2", {"terms": "better deal"}, current_step=2)
        assert result is True
        assert prop.state == ProposalState.COUNTER_PENDING

    def test_counter_propose_on_already_accepted(self):
        """Counter-proposing on an accepted proposal should fail."""
        nm = NegotiationManager()
        prop = nm.create_proposal("a1", "a2", "trade", "swap", {}, current_step=1)
        nm.accept_proposal(prop.id, "a2", current_step=2)
        result = nm.counter_propose(prop.id, "a2", {"terms": "nope"}, current_step=3)
        assert result is False

    def test_withdraw_by_non_proposer(self):
        """Only the proposer can withdraw their own proposal."""
        nm = NegotiationManager()
        prop = nm.create_proposal("a1", "a2", "task", "help", {}, current_step=1)
        result = nm.withdraw_proposal(prop.id, "a2", current_step=2)
        assert result is False

    def test_withdraw_by_proposer(self):
        """Proposer should be able to withdraw."""
        nm = NegotiationManager()
        prop = nm.create_proposal("a1", "a2", "task", "help", {}, current_step=1)
        result = nm.withdraw_proposal(prop.id, "a1", current_step=2)
        assert result is True
        assert prop.state == ProposalState.WITHDRAWN

    def test_expire_proposals(self):
        """Proposals past their expiry step should be expired."""
        nm = NegotiationManager(default_expiry_steps=3)
        prop = nm.create_proposal("a1", "a2", "task", "help", {}, current_step=1)
        expired = nm.expire_proposals(current_step=10)
        assert prop.id in expired
        assert prop.state == ProposalState.EXPIRED

    def test_fulfill_nonexistent_agreement(self):
        """Fulfilling a non-existent agreement should return False."""
        nm = NegotiationManager()
        assert nm.fulfill_agreement("fake_id", current_step=1) is False


# ===================================================================
# 9. Goal Tree Edge Cases
# ===================================================================

class TestGoalTreeEdgeCases:

    def test_empty_tree_operations(self):
        """Operations on empty tree should handle gracefully."""
        tree = GoalTree()
        assert tree.mission is None
        assert tree.get_agent_goals("nobody") == []
        assert tree.get_active_goals("nobody") == []
        assert tree.get_highest_priority_goal("nobody") is None
        assert tree.get_context_string("nobody") == "No goals assigned."

    def test_get_nonexistent_goal_raises(self):
        """get_goal for missing ID should raise KeyError."""
        tree = GoalTree()
        with pytest.raises(KeyError):
            tree.get_goal("nonexistent")

    def test_complete_nonexistent_goal_raises(self):
        """Completing a non-existent goal should raise KeyError."""
        tree = GoalTree()
        with pytest.raises(KeyError):
            tree.complete_goal("nonexistent", step=1)

    def test_add_group_goal_without_mission(self):
        """Adding a group goal without a mission should set parent_id to None."""
        tree = GoalTree()
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        goal = tree.get_goal(gid)
        assert goal.parent_id is None

    def test_deeply_nested_goals_ancestry(self):
        """Ancestry chain through many levels should work."""
        tree = GoalTree()
        mid = tree.set_mission("Survive", step=0)
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        aid1 = tree.add_agent_goal("Find rope", "a1", gid, step=2)
        # Agent goals can technically reference other agent goals as parent
        # (even though that's not the intended use)
        ancestry = tree.get_ancestry(aid1)
        assert len(ancestry) == 3  # mission -> group -> individual
        assert ancestry[0].level == GoalLevel.MISSION

    def test_ancestry_of_orphan_goal(self):
        """Goal with no parent should have ancestry of length 1."""
        tree = GoalTree()
        gid = tree.add_group_goal("Orphan", ["a1"], step=1)
        ancestry = tree.get_ancestry(gid)
        assert len(ancestry) == 1

    def test_add_conflict_bidirectional(self):
        """add_conflict should set conflict_with in both directions."""
        tree = GoalTree()
        tree.set_mission("Survive", step=0)
        gid = tree.add_group_goal("Evacuate", ["a1", "a2"], step=1)
        a1 = tree.add_agent_goal("Hoard", "a1", gid, step=2)
        a2 = tree.add_agent_goal("Share", "a2", gid, step=2)
        tree.add_conflict(a1, a2)
        assert a2 in tree.get_goal(a1).conflict_with
        assert a1 in tree.get_goal(a2).conflict_with

    def test_add_conflict_idempotent(self):
        """Adding the same conflict twice should not duplicate entries."""
        tree = GoalTree()
        tree.set_mission("Survive", step=0)
        gid = tree.add_group_goal("Evacuate", ["a1", "a2"], step=1)
        a1 = tree.add_agent_goal("Hoard", "a1", gid, step=2)
        a2 = tree.add_agent_goal("Share", "a2", gid, step=2)
        tree.add_conflict(a1, a2)
        tree.add_conflict(a1, a2)
        assert tree.get_goal(a1).conflict_with.count(a2) == 1
        assert tree.get_goal(a2).conflict_with.count(a1) == 1

    def test_propagate_completions_no_children(self):
        """Group goal with no children should NOT auto-complete."""
        tree = GoalTree()
        tree.set_mission("Survive", step=0)
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.propagate_completions(step=5)
        assert tree.get_goal(gid).status == GoalStatus.ACTIVE

    def test_serialization_roundtrip_with_mission(self):
        """Full tree should survive to_dict/from_dict roundtrip."""
        tree = GoalTree()
        tree.set_mission("Survive", step=0)
        gid = tree.add_group_goal("Evacuate", ["a1"], step=1)
        tree.add_agent_goal("Find rope", "a1", gid, step=2)
        data = tree.to_dict()
        restored = GoalTree.from_dict(data)
        assert restored.mission is not None
        assert restored.mission.description == "Survive"
        assert len(restored._goals) == 3

    def test_serialization_roundtrip_empty_tree(self):
        """Empty tree should survive serialization."""
        tree = GoalTree()
        data = tree.to_dict()
        restored = GoalTree.from_dict(data)
        assert restored.mission is None
        assert len(restored._goals) == 0


# ===================================================================
# 10. Cooperation Coordinator Edge Cases
# ===================================================================

class TestCooperationCoordinatorEdgeCases:

    def test_loop_detection_fresh_agent(self):
        """Agent with no history should not be stuck in a loop."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        assert coord.is_stuck_in_loop("new_agent") is False

    def test_loop_detection_repetitive_actions(self):
        """Agent repeating the same action 3+ times should trigger loop detection."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        for _ in range(5):
            coord.track_action("a1", "wait", None)
        assert coord.is_stuck_in_loop("a1") is True

    def test_suggestions_for_stuck_agent(self):
        """Stuck agent should get at least one suggestion."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        coord.add_shared_goal("Evacuate everyone")
        for _ in range(5):
            coord.track_action("a1", "wait", None)
        suggestions = coord.get_suggestions_for_agent("a1")
        assert len(suggestions) >= 1

    def test_suggestions_for_unstuck_agent(self):
        """Agent that isn't stuck should get no suggestions."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        suggestions = coord.get_suggestions_for_agent("a1")
        assert suggestions == []

    def test_assign_nonexistent_task(self):
        """Assigning a task that doesn't exist should return False."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        assert coord.assign_task("fake_task", "a1") is False

    def test_complete_nonexistent_task(self):
        """Completing a task that doesn't exist should return False."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        assert coord.complete_task("fake_task") is False

    def test_cooperation_score_no_tasks(self):
        """Cooperation score with no tasks should be 0.5 (default)."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        coord.update_cooperation_score()
        assert coord.cooperation_score == 0.5

    def test_cooperation_score_all_completed(self):
        """All tasks completed should produce high cooperation score."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        tid = coord.create_task("help someone", priority=5, assigned_to="a1")
        coord.complete_task(tid)
        coord.update_cooperation_score()
        # task_score = 1.0, goal_progress = 0.0, combined = 0.6
        assert coord.cooperation_score == pytest.approx(0.6)

    def test_goal_progress_clamped(self):
        """Goal progress should be clamped to [0.0, 1.0]."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        coord.add_shared_goal("Survive")
        coord.update_goal_progress("Survive", 2.5)
        assert coord.goal_progress["Survive"] == 1.0
        coord.update_goal_progress("Survive", -1.0)
        assert coord.goal_progress["Survive"] == 0.0

    def test_duplicate_shared_goal_ignored(self):
        """Adding the same goal twice should not duplicate it."""
        from app.agents.coordinator import CooperationCoordinator
        coord = CooperationCoordinator()
        coord.add_shared_goal("Survive")
        coord.add_shared_goal("Survive")
        assert coord.shared_goals.count("Survive") == 1
