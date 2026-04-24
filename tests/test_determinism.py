"""Tests for the simulation determinism verifier."""

import time

import pytest

from emotionsim.simulation.determinism import DeterminismTracker, DivergenceReport


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _make_tick(tracker: DeterminismTracker, agent_id: str, step: int, **kwargs):
    """Shortcut for recording a tick with sensible defaults."""
    tracker.record_tick(
        agent_id=agent_id,
        step=step,
        actions=kwargs.get("actions", [{"type": "speak"}]),
        message=kwargs.get("message", {"content": "hello", "to_target": "broadcast"}),
        state_changes=kwargs.get("state_changes", {"stress": 4}),
    )


def _populate_tracker(tracker: DeterminismTracker) -> None:
    """Feed a reproducible sequence of events into a tracker."""
    tracker.record_world_state(0, {"weather": "rain", "flood_level": 1})
    _make_tick(tracker, "agent-1", 0)
    _make_tick(tracker, "agent-2", 0)
    tracker.record_world_state(1, {"weather": "rain", "flood_level": 2})
    _make_tick(tracker, "agent-1", 1)
    _make_tick(tracker, "agent-2", 1)
    tracker.record_event("scenario_loaded", {"name": "The Great Flood"})


# ---------------------------------------------------------------
# Core identity tests
# ---------------------------------------------------------------

class TestFingerprints:
    """Two identical event streams must produce identical fingerprints."""

    def test_identical_sequences_produce_identical_fingerprints(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        _populate_tracker(a)
        _populate_tracker(b)
        assert a.fingerprint() == b.fingerprint()

    def test_different_sequences_produce_different_fingerprints(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        _populate_tracker(a)
        # b gets a slightly different event
        b.record_world_state(0, {"weather": "sunny", "flood_level": 0})
        _make_tick(b, "agent-1", 0)
        assert a.fingerprint() != b.fingerprint()

    def test_order_matters(self):
        """Same events fed in a different order must produce different fingerprints."""
        a, b = DeterminismTracker(), DeterminismTracker()

        a.record_tick("agent-1", 0, actions=[{"type": "move"}])
        a.record_tick("agent-2", 0, actions=[{"type": "speak"}])

        b.record_tick("agent-2", 0, actions=[{"type": "speak"}])
        b.record_tick("agent-1", 0, actions=[{"type": "move"}])

        assert a.fingerprint() != b.fingerprint()

    def test_empty_tracker_has_known_baseline(self):
        """An empty tracker always produces the same SHA-256 of zero bytes."""
        import hashlib
        expected = hashlib.sha256().hexdigest()
        tracker = DeterminismTracker()
        assert tracker.fingerprint() == expected

    def test_empty_tracker_event_count_is_zero(self):
        tracker = DeterminismTracker()
        assert tracker.event_count == 0


# ---------------------------------------------------------------
# Canonical JSON / key ordering
# ---------------------------------------------------------------

class TestCanonicalJSON:
    """World state with different key orderings should still produce the same hash."""

    def test_key_order_does_not_affect_hash(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_world_state(0, {"z_key": 1, "a_key": 2, "m_key": 3})
        b.record_world_state(0, {"a_key": 2, "m_key": 3, "z_key": 1})
        assert a.fingerprint() == b.fingerprint()

    def test_nested_dicts_hash_consistently(self):
        nested_a = {
            "locations": {"shelter": {"occupants": 3}, "bridge": {"occupants": 1}},
            "weather": "storm",
        }
        nested_b = {
            "weather": "storm",
            "locations": {"bridge": {"occupants": 1}, "shelter": {"occupants": 3}},
        }
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_world_state(0, nested_a)
        b.record_world_state(0, nested_b)
        assert a.fingerprint() == b.fingerprint()

    def test_deeply_nested_structures(self):
        deep = {"l1": {"l2": {"l3": {"l4": {"l5": "value"}}}}}
        deep_reversed = {"l1": {"l2": {"l3": {"l4": {"l5": "value"}}}}}
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_world_state(0, deep)
        b.record_world_state(0, deep_reversed)
        assert a.fingerprint() == b.fingerprint()


# ---------------------------------------------------------------
# Unicode and special characters
# ---------------------------------------------------------------

class TestUnicodeAndSpecialChars:
    def test_unicode_in_messages(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        msg = {"content": "Hilfe! Das Wasser steigt! \u00fc\u00f6\u00e4\u00df \U0001f30a", "to_target": "broadcast"}
        a.record_tick("agent-1", 0, message=msg)
        b.record_tick("agent-1", 0, message=msg)
        assert a.fingerprint() == b.fingerprint()

    def test_special_characters_in_event_data(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        data = {"note": "line1\nline2\ttab", "quote": 'he said "run!"', "backslash": "c:\\path"}
        a.record_event("test", data)
        b.record_event("test", data)
        assert a.fingerprint() == b.fingerprint()

    def test_emoji_in_world_state(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        state = {"status": "\U0001f525\U0001f30a", "label": "\u2603 snowman"}
        a.record_world_state(0, state)
        b.record_world_state(0, state)
        assert a.fingerprint() == b.fingerprint()


# ---------------------------------------------------------------
# Step-level fingerprints
# ---------------------------------------------------------------

class TestStepFingerprints:
    def test_step_fingerprint_returns_consistent_value(self):
        tracker = DeterminismTracker()
        _make_tick(tracker, "agent-1", 0)
        fp1 = tracker.step_fingerprint(0)
        fp2 = tracker.step_fingerprint(0)
        assert fp1 == fp2

    def test_step_fingerprint_raises_for_unknown_step(self):
        tracker = DeterminismTracker()
        with pytest.raises(KeyError, match="No events recorded for step 99"):
            tracker.step_fingerprint(99)

    def test_step_fingerprints_isolate_per_step(self):
        tracker = DeterminismTracker()
        _make_tick(tracker, "agent-1", 0, actions=[{"type": "move"}])
        _make_tick(tracker, "agent-1", 1, actions=[{"type": "speak"}])
        assert tracker.step_fingerprint(0) != tracker.step_fingerprint(1)

    def test_steps_recorded_preserves_insertion_order(self):
        tracker = DeterminismTracker()
        _make_tick(tracker, "a", 3)
        _make_tick(tracker, "a", 1)
        _make_tick(tracker, "a", 5)
        assert tracker.steps_recorded == [3, 1, 5]

    def test_same_step_events_from_different_trackers_match(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        _make_tick(a, "agent-1", 0)
        _make_tick(b, "agent-1", 0)
        assert a.step_fingerprint(0) == b.step_fingerprint(0)


# ---------------------------------------------------------------
# DivergenceReport / compare()
# ---------------------------------------------------------------

class TestCompare:
    def test_identical_runs_report_identical(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        _populate_tracker(a)
        _populate_tracker(b)
        report = a.compare(b)
        assert report.identical is True
        assert report.first_divergent_step is None
        assert "identical" in report.details.lower()

    def test_divergent_runs_report_first_mismatch(self):
        a, b = DeterminismTracker(), DeterminismTracker()

        # Step 0: identical
        a.record_world_state(0, {"flood": 1})
        b.record_world_state(0, {"flood": 1})

        # Step 1: different
        a.record_world_state(1, {"flood": 2})
        b.record_world_state(1, {"flood": 3})

        # Step 2: also different, but step 1 should be reported
        a.record_world_state(2, {"flood": 4})
        b.record_world_state(2, {"flood": 5})

        report = a.compare(b)
        assert report.identical is False
        assert report.first_divergent_step == 1

    def test_missing_step_in_second_tracker(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_world_state(0, {"flood": 1})
        a.record_world_state(1, {"flood": 2})
        b.record_world_state(0, {"flood": 1})
        # b is missing step 1
        report = a.compare(b)
        assert report.identical is False
        assert report.first_divergent_step == 1
        assert "second" in report.details.lower()

    def test_missing_step_in_first_tracker(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_world_state(0, {"flood": 1})
        b.record_world_state(0, {"flood": 1})
        b.record_world_state(1, {"flood": 2})
        report = a.compare(b)
        assert report.identical is False
        assert report.first_divergent_step == 1
        assert "first" in report.details.lower()

    def test_event_only_divergence(self):
        """Steps match, but non-step events differ."""
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_world_state(0, {"x": 1})
        b.record_world_state(0, {"x": 1})
        a.record_event("extra", {"foo": "bar"})
        report = a.compare(b)
        assert report.identical is False
        assert report.first_divergent_step is None
        assert "non-step" in report.details.lower()

    def test_compare_two_empty_trackers(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        report = a.compare(b)
        assert report.identical is True

    def test_divergence_report_total_steps(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        for s in range(5):
            a.record_world_state(s, {"step": s})
        for s in range(3):
            b.record_world_state(s, {"step": s})
        report = a.compare(b)
        assert report.total_steps == 5


# ---------------------------------------------------------------
# Performance
# ---------------------------------------------------------------

class TestPerformance:
    def test_large_event_sequence(self):
        """1000+ events should work without issues."""
        tracker = DeterminismTracker()
        for step in range(500):
            tracker.record_world_state(step, {"flood_level": step, "agents_alive": 10 - step // 100})
            tracker.record_tick(
                agent_id=f"agent-{step % 5}",
                step=step,
                actions=[{"type": "move", "target": f"location-{step % 10}"}],
                message={"content": f"Step {step} message", "to_target": "broadcast"},
                state_changes={"stress": step % 10},
            )
        assert tracker.event_count == 1000
        fp = tracker.fingerprint()
        assert isinstance(fp, str) and len(fp) == 64  # SHA-256 hex

    def test_large_sequence_reproducible(self):
        """Two identical large runs produce the same fingerprint."""
        def build():
            t = DeterminismTracker()
            for step in range(200):
                t.record_world_state(step, {"level": step})
                t.record_tick("a1", step, actions=[{"n": step}])
            return t

        a, b = build(), build()
        assert a.fingerprint() == b.fingerprint()
        report = a.compare(b)
        assert report.identical is True

    def test_performance_is_reasonable(self):
        """Recording 2000 events should complete in well under 2 seconds."""
        tracker = DeterminismTracker()
        start = time.monotonic()
        for step in range(1000):
            tracker.record_world_state(step, {"v": step})
            tracker.record_tick("a", step)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"Took {elapsed:.2f}s for 2000 events"


# ---------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------

class TestEdgeCases:
    def test_record_tick_with_none_message(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_tick("a1", 0, message=None)
        b.record_tick("a1", 0, message=None)
        assert a.fingerprint() == b.fingerprint()

    def test_record_tick_with_string_message(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_tick("a1", 0, message="just a string")
        b.record_tick("a1", 0, message="just a string")
        assert a.fingerprint() == b.fingerprint()

    def test_record_tick_empty_actions(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        a.record_tick("a1", 0, actions=[], state_changes={})
        b.record_tick("a1", 0, actions=None, state_changes=None)
        # Both should normalize to empty list/dict
        assert a.fingerprint() == b.fingerprint()

    def test_record_event_with_list_data(self):
        tracker = DeterminismTracker()
        tracker.record_event("test", [1, 2, 3])
        assert tracker.event_count == 1

    def test_record_event_with_nested_data(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        data = {"agents": [{"id": "a1", "alive": True}, {"id": "a2", "alive": False}]}
        a.record_event("snapshot", data)
        b.record_event("snapshot", data)
        assert a.fingerprint() == b.fingerprint()

    def test_multiple_ticks_same_step_accumulate(self):
        tracker = DeterminismTracker()
        _make_tick(tracker, "a1", 0)
        _make_tick(tracker, "a2", 0)
        _make_tick(tracker, "a3", 0)
        assert tracker.event_count == 3
        # Step 0 should exist and have a fingerprint
        fp = tracker.step_fingerprint(0)
        assert isinstance(fp, str) and len(fp) == 64

    def test_world_state_with_numeric_values(self):
        a, b = DeterminismTracker(), DeterminismTracker()
        state = {"flood_level": 3.14159, "survivors": 42, "active": True, "notes": None}
        a.record_world_state(0, state)
        b.record_world_state(0, state)
        assert a.fingerprint() == b.fingerprint()
