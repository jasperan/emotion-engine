import pytest
from app.simulation.message_bus import MessageBus


class TestAliasRouting:
    def test_alias_registered_on_agent_registration(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        assert bus.alias_registry.resolve("dr. chen") == "a1"

    def test_alias_resolves_in_routing(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        bus.register_agent("a2", "Robert 'Bobby' Williams #6")
        assert bus.alias_registry.resolve("bobby") == "a2"
        assert bus.alias_registry.resolve("Bobby Williams") == "a2"

    def test_alias_unregistered_on_agent_unregister(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        bus.unregister_agent("a1")
        assert bus.alias_registry.resolve("dr. chen") is None
