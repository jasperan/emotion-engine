"""Tests for proximity-based communication: hop distance and zone calculation."""

import pytest
from app.simulation.engine import SimulationEngine


def _make_engine():
    """Create a minimal SimulationEngine without full init for testing."""
    engine = SimulationEngine.__new__(SimulationEngine)
    engine.world_state = {
        "locations": {
            "shelter": {"nearby": ["street", "rooftop"]},
            "street": {"nearby": ["shelter", "bridge"]},
            "bridge": {"nearby": ["street", "safe_hill"]},
            "safe_hill": {"nearby": ["bridge"]},
            "rooftop": {"nearby": ["shelter"]},
        }
    }
    engine._agent_locations = {
        "a1": "shelter",
        "a2": "shelter",
        "a3": "street",
        "a4": "bridge",
        "a5": "safe_hill",
    }
    engine._hop_cache = {}
    engine.current_step = 1
    return engine


class TestHopDistance:
    def test_same_location_zero_hops(self):
        engine = _make_engine()
        assert engine._calculate_hop_distance("a1", "a2") == 0

    def test_adjacent_one_hop(self):
        engine = _make_engine()
        assert engine._calculate_hop_distance("a1", "a3") == 1

    def test_two_hops(self):
        engine = _make_engine()
        assert engine._calculate_hop_distance("a1", "a4") == 2

    def test_three_hops(self):
        engine = _make_engine()
        assert engine._calculate_hop_distance("a1", "a5") == 3

    def test_hop_cache_works(self):
        engine = _make_engine()
        # First call computes
        result1 = engine._calculate_hop_distance("a1", "a5")
        assert result1 == 3
        # Verify cache entry exists (sorted tuple key)
        cache_key = ("a1", "a5")
        assert cache_key in engine._hop_cache
        # Second call uses cache (same result)
        result2 = engine._calculate_hop_distance("a1", "a5")
        assert result2 == 3
        # Also test reverse order hits the same cache
        result3 = engine._calculate_hop_distance("a5", "a1")
        assert result3 == 3

    def test_unreachable_returns_99(self):
        engine = _make_engine()
        # Add an isolated location
        engine.world_state["locations"]["island"] = {"nearby": []}
        engine._agent_locations["a6"] = "island"
        assert engine._calculate_hop_distance("a1", "a6") == 99


class TestCommZone:
    def test_same_zone(self):
        engine = _make_engine()
        assert engine._get_comm_zone("a1", "a2") == "same"

    def test_adjacent_zone(self):
        engine = _make_engine()
        assert engine._get_comm_zone("a1", "a3") == "adjacent"

    def test_distant_zone_two_hops(self):
        engine = _make_engine()
        assert engine._get_comm_zone("a1", "a4") == "distant"

    def test_distant_zone_three_hops(self):
        engine = _make_engine()
        assert engine._get_comm_zone("a1", "a5") == "distant"
