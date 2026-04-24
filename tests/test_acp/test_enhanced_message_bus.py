import pytest
from emotionsim.simulation.message_bus import MessageBus
from emotionsim.acp.message import ACPMessage, AgentIdentity


def test_message_bus_accepts_acp_direct():
    """Verify send_acp_message routes direct messages correctly."""
    bus = MessageBus()
    bus.register_agent("Martha", "Martha")
    bus.register_agent("Bob", "Bob")

    sender = AgentIdentity(name="Martha", role="human_sim")
    acp_msg = ACPMessage(
        sender=sender,
        recipient="Bob",
        channel="direct",
        msg_type="chat",
        payload={"content": "We need to evacuate!"},
    )

    bus.send_acp_message(acp_msg, step_index=5)
    messages = bus.get_messages("Bob")
    assert len(messages) == 1
    assert messages[0]["content"] == "We need to evacuate!"
    assert messages[0]["from_agent"] == "Martha"


def test_message_bus_accepts_acp_broadcast():
    """Verify send_acp_message routes broadcast messages correctly."""
    bus = MessageBus()
    bus.register_agent("Martha", "Martha")
    bus.register_agent("Bob", "Bob")
    bus.register_agent("Eve", "Eve")

    sender = AgentIdentity(name="Martha", role="human_sim")
    acp_msg = ACPMessage(
        sender=sender,
        channel="broadcast",
        msg_type="alert",
        payload={"content": "Flood warning!"},
    )

    bus.send_acp_message(acp_msg, step_index=1)
    bob_msgs = bus.get_messages("Bob")
    eve_msgs = bus.get_messages("Eve")
    assert len(bob_msgs) == 1
    assert len(eve_msgs) == 1
    assert bob_msgs[0]["content"] == "Flood warning!"


def test_message_bus_accepts_acp_room():
    """Verify send_acp_message routes room messages correctly."""
    bus = MessageBus()
    bus.register_agent("Martha", "Martha")
    bus.register_agent("Bob", "Bob")
    bus.join_room("Martha", "shelter")
    bus.join_room("Bob", "shelter")

    sender = AgentIdentity(name="Martha", role="human_sim")
    acp_msg = ACPMessage(
        sender=sender,
        channel="room:shelter",
        msg_type="chat",
        payload={"content": "Is everyone safe?"},
    )

    bus.send_acp_message(acp_msg, step_index=3)
    bob_msgs = bus.get_messages("Bob")
    assert len(bob_msgs) == 1
    assert bob_msgs[0]["content"] == "Is everyone safe?"


def test_message_bus_acp_metadata():
    """Verify ACP metadata is passed through to the internal message."""
    bus = MessageBus()
    bus.register_agent("Martha", "Martha")
    bus.register_agent("Bob", "Bob")

    sender = AgentIdentity(name="Martha", role="human_sim")
    acp_msg = ACPMessage(
        sender=sender,
        recipient="Bob",
        channel="direct",
        msg_type="proposal",
        payload={"content": "Let's build a raft"},
    )

    bus.send_acp_message(acp_msg, step_index=2)
    messages = bus.get_messages("Bob")
    assert messages[0]["metadata"]["acp_msg_type"] == "proposal"
    assert messages[0]["metadata"]["acp_id"] == acp_msg.id
