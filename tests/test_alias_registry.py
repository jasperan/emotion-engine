"""Tests for the AliasRegistry"""
import pytest
from emotionsim.simulation.alias_registry import AliasRegistry


class TestAliasRegistry:
    """Test cases for AliasRegistry"""

    def test_register_generates_aliases(self):
        """Dr. Sarah Chen #1 resolves from multiple alias forms"""
        reg = AliasRegistry()
        reg.register("agent_1", "Dr. Sarah Chen #1")

        assert reg.resolve("dr. chen") == "agent_1"
        assert reg.resolve("sarah") == "agent_1"
        assert reg.resolve("chen") == "agent_1"
        assert reg.resolve("sarah chen") == "agent_1"
        assert reg.resolve("dr. sarah chen") == "agent_1"
        assert reg.resolve("dr. sarah chen #1") == "agent_1"

    def test_nickname_extraction(self):
        """Robert 'Bobby' Williams #6 resolves from nickname forms"""
        reg = AliasRegistry()
        reg.register("agent_6", "Robert 'Bobby' Williams #6")

        assert reg.resolve("bobby") == "agent_6"
        assert reg.resolve("bobby williams") == "agent_6"
        assert reg.resolve("robert") == "agent_6"
        assert reg.resolve("williams") == "agent_6"
        assert reg.resolve("robert williams") == "agent_6"

    def test_hyphenated_names(self):
        """Mei-Lin Wu #7 resolves from hyphenated and last name"""
        reg = AliasRegistry()
        reg.register("agent_7", "Mei-Lin Wu #7")

        assert reg.resolve("mei-lin") == "agent_7"
        assert reg.resolve("wu") == "agent_7"
        assert reg.resolve("mei-lin wu") == "agent_7"

    def test_case_insensitive(self):
        """All lookups are case-insensitive"""
        reg = AliasRegistry()
        reg.register("agent_1", "Dr. Sarah Chen #1")

        assert reg.resolve("DR. CHEN") == "agent_1"
        assert reg.resolve("SARAH CHEN") == "agent_1"
        assert reg.resolve("Dr. Sarah Chen #1") == "agent_1"

    def test_ambiguous_alias_returns_none(self):
        """Two agents sharing a first name make that alias ambiguous"""
        reg = AliasRegistry()
        reg.register("agent_1", "Sarah Chen #1")
        reg.register("agent_2", "Sarah Williams #2")

        # "sarah" is ambiguous — maps to both
        assert reg.resolve("sarah") is None
        # But full names still work
        assert reg.resolve("sarah chen") == "agent_1"
        assert reg.resolve("sarah williams") == "agent_2"

    def test_ambiguous_resolve_or_fallback(self):
        """resolve_or_fallback indicates ambiguity"""
        reg = AliasRegistry()
        reg.register("agent_1", "Sarah Chen #1")
        reg.register("agent_2", "Sarah Williams #2")

        agent_id, ambiguous = reg.resolve_or_fallback("sarah")
        assert agent_id is None
        assert ambiguous is True

        agent_id, ambiguous = reg.resolve_or_fallback("sarah chen")
        assert agent_id == "agent_1"
        assert ambiguous is False

    def test_unknown_name_returns_none(self):
        """Unknown names resolve to None"""
        reg = AliasRegistry()
        reg.register("agent_1", "Dr. Sarah Chen #1")

        assert reg.resolve("unknown person") is None

    def test_unknown_resolve_or_fallback(self):
        """resolve_or_fallback returns (None, False) for unknown names"""
        reg = AliasRegistry()
        agent_id, ambiguous = reg.resolve_or_fallback("nobody")
        assert agent_id is None
        assert ambiguous is False

    def test_exact_match_wins(self):
        """An agent whose full name matches exactly wins over partial alias collisions"""
        reg = AliasRegistry()
        # Agent whose actual name part is "Chen"
        reg.register("agent_a", "Chen #3")
        # Another agent who has "chen" as a last name alias
        reg.register("agent_b", "Dr. Sarah Chen #1")

        # "chen" is ambiguous between both agents
        # But the full display name "chen #3" still resolves
        assert reg.resolve("chen #3") == "agent_a"
        assert reg.resolve("dr. sarah chen") == "agent_b"
        assert reg.resolve("sarah chen") == "agent_b"

    def test_unregister(self):
        """Unregistering removes all aliases for that agent"""
        reg = AliasRegistry()
        reg.register("agent_1", "Dr. Sarah Chen #1")

        # Verify it works before unregister
        assert reg.resolve("sarah chen") == "agent_1"

        reg.unregister("agent_1")

        assert reg.resolve("sarah chen") is None
        assert reg.resolve("dr. chen") is None
        assert reg.resolve("sarah") is None

    def test_title_prefix_prof(self):
        """Prof. title is extracted and used for alias"""
        reg = AliasRegistry()
        reg.register("agent_10", "Prof. James Wright #10")

        assert reg.resolve("prof. wright") == "agent_10"
        assert reg.resolve("james wright") == "agent_10"

    def test_title_prefix_officer(self):
        """Officer title is extracted and used for alias"""
        reg = AliasRegistry()
        reg.register("agent_11", "Officer Maria Lopez #11")

        assert reg.resolve("officer lopez") == "agent_11"
        assert reg.resolve("maria lopez") == "agent_11"

    def test_double_quoted_nickname(self):
        """Double-quoted nicknames are also extracted"""
        reg = AliasRegistry()
        reg.register("agent_12", 'Thomas "Tommy" Garcia #12')

        assert reg.resolve("tommy") == "agent_12"
        assert reg.resolve("tommy garcia") == "agent_12"
        assert reg.resolve("thomas garcia") == "agent_12"
