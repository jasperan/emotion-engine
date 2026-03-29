"""Tests for the opinion dynamics engine and persona opinion fields."""

import pytest

from app.schemas.persona import Persona
from app.simulation.opinion_dynamics import OpinionDynamics, OpinionShift


def _make_persona(**overrides) -> Persona:
    """Helper to build a Persona with opinion dynamics fields."""
    defaults = dict(
        name="Test Agent",
        age=30,
        sex="male",
        occupation="Engineer",
        opinion_vectors={},
        opinion_bias=0.5,
        reaction_speed=0.5,
        influence_level=0.5,
    )
    defaults.update(overrides)
    return Persona(**defaults)


class TestComputeShift:
    """Unit tests for OpinionDynamics.compute_shift."""

    def test_compute_shift_toward_influencer(self):
        """Influencer at 0.8, receiver at -0.2 -> shift is positive (toward influencer)."""
        engine = OpinionDynamics()
        delta = engine.compute_shift(
            receiver_stance=-0.2,
            influencer_stance=0.8,
            receiver_bias=0.3,
            influencer_influence=0.7,
            receiver_reaction_speed=0.6,
            trust_level=0.5,
        )
        assert delta > 0, f"Expected positive shift toward influencer, got {delta}"

    def test_high_bias_resists_change(self):
        """Receiver with opinion_bias=0.95 should produce a very small shift."""
        engine = OpinionDynamics()
        delta_resistant = engine.compute_shift(
            receiver_stance=0.0,
            influencer_stance=0.8,
            receiver_bias=0.95,
            influencer_influence=0.8,
            receiver_reaction_speed=0.5,
            trust_level=0.7,
        )
        delta_open = engine.compute_shift(
            receiver_stance=0.0,
            influencer_stance=0.8,
            receiver_bias=0.1,
            influencer_influence=0.8,
            receiver_reaction_speed=0.5,
            trust_level=0.7,
        )
        assert abs(delta_resistant) < abs(delta_open), (
            f"Resistant agent shifted more ({delta_resistant}) than open agent ({delta_open})"
        )
        assert abs(delta_resistant) < 0.02, (
            f"High-bias agent shifted too much: {delta_resistant}"
        )

    def test_high_influence_bigger_shift(self):
        """Higher influence_level should produce a bigger shift."""
        engine = OpinionDynamics()
        kwargs = dict(
            receiver_stance=0.0,
            influencer_stance=0.7,
            receiver_bias=0.3,
            receiver_reaction_speed=0.5,
            trust_level=0.5,
        )
        delta_high = engine.compute_shift(influencer_influence=0.9, **kwargs)
        delta_low = engine.compute_shift(influencer_influence=0.1, **kwargs)
        assert abs(delta_high) > abs(delta_low), (
            f"High influence ({delta_high}) should exceed low influence ({delta_low})"
        )

    def test_trust_affects_persuasion(self):
        """Higher trust should produce a bigger shift."""
        engine = OpinionDynamics()
        kwargs = dict(
            receiver_stance=-0.3,
            influencer_stance=0.5,
            receiver_bias=0.3,
            influencer_influence=0.6,
            receiver_reaction_speed=0.5,
        )
        delta_trusted = engine.compute_shift(trust_level=8 / 9, **kwargs)  # trust=9 normalized
        delta_untrusted = engine.compute_shift(trust_level=0 / 9, **kwargs)  # trust=1 normalized
        assert abs(delta_trusted) > abs(delta_untrusted), (
            f"Trusted ({delta_trusted}) should exceed untrusted ({delta_untrusted})"
        )

    def test_no_shift_on_same_opinion(self):
        """Speaker and listener with the same stance -> no shift."""
        engine = OpinionDynamics()
        delta = engine.compute_shift(
            receiver_stance=0.5,
            influencer_stance=0.5,
            receiver_bias=0.3,
            influencer_influence=0.9,
            receiver_reaction_speed=0.8,
            trust_level=0.9,
        )
        assert abs(delta) < 0.001, f"Same stance should yield ~0 shift, got {delta}"

    def test_shift_clamped_to_range(self):
        """Resulting stance must stay within [-1.0, 1.0]."""
        engine = OpinionDynamics(base_shift_rate=10.0, max_shift_per_interaction=0.3)
        delta = engine.compute_shift(
            receiver_stance=0.9,
            influencer_stance=1.0,
            receiver_bias=0.0,
            influencer_influence=1.0,
            receiver_reaction_speed=1.0,
            trust_level=1.0,
        )
        new_stance = 0.9 + delta
        assert -1.0 <= new_stance <= 1.0 + 0.3, "Stance after shift should be within bounds"
        # Also verify the delta itself is clamped
        assert -0.3 <= delta <= 0.3, f"Delta {delta} exceeds max_shift"


class TestProcessInteraction:
    """Integration tests for OpinionDynamics.process_interaction."""

    def test_process_interaction_applies_shifts(self):
        """Two personas with different opinions; interaction should shift listener."""
        speaker = _make_persona(
            name="Speaker",
            opinion_vectors={"climate": 0.8, "economy": -0.5},
            influence_level=0.7,
        )
        listener = _make_persona(
            name="Listener",
            opinion_vectors={"climate": -0.2, "economy": 0.3},
            opinion_bias=0.3,
            reaction_speed=0.6,
        )

        engine = OpinionDynamics()
        shifts = engine.process_interaction(
            speaker_persona=speaker,
            listener_persona=listener,
            speaker_id="speaker-1",
            listener_id="listener-1",
            trust_level=7,
        )

        assert len(shifts) > 0, "Expected at least one opinion shift"
        for s in shifts:
            assert s.agent_id == "listener-1"
            assert s.influenced_by == "speaker-1"
            assert s.topic in ("climate", "economy")
            assert s.old_stance != s.new_stance

        # Verify opinions actually changed on the persona object
        assert listener.opinion_vectors["climate"] != -0.2
        assert listener.opinion_vectors["economy"] != 0.3

    def test_no_shift_on_same_opinion_interaction(self):
        """If both agents share the same stance, process_interaction yields no shifts."""
        speaker = _make_persona(
            name="Speaker",
            opinion_vectors={"topic_a": 0.5},
            influence_level=0.8,
        )
        listener = _make_persona(
            name="Listener",
            opinion_vectors={"topic_a": 0.5},
            opinion_bias=0.3,
            reaction_speed=0.5,
        )

        engine = OpinionDynamics()
        shifts = engine.process_interaction(
            speaker_persona=speaker,
            listener_persona=listener,
            speaker_id="s1",
            listener_id="l1",
            trust_level=5,
        )
        assert len(shifts) == 0, f"Expected no shifts for same stance, got {shifts}"

    def test_history_tracking(self):
        """Process interactions and verify get_history() records them."""
        speaker = _make_persona(
            name="Speaker",
            opinion_vectors={"rights": 0.9},
            influence_level=0.8,
        )
        listener = _make_persona(
            name="Listener",
            opinion_vectors={"rights": -0.5},
            opinion_bias=0.2,
            reaction_speed=0.7,
        )

        engine = OpinionDynamics()
        assert len(engine.get_history()) == 0

        engine.process_interaction(
            speaker_persona=speaker,
            listener_persona=listener,
            speaker_id="s1",
            listener_id="l1",
            trust_level=6,
        )

        history = engine.get_history()
        assert len(history) >= 1
        assert all(isinstance(h, OpinionShift) for h in history)

        engine.clear_history()
        assert len(engine.get_history()) == 0

    def test_shift_clamped_to_stance_range(self):
        """Verify resulting stance stays within [-1.0, 1.0] after interaction."""
        speaker = _make_persona(
            name="Extremist",
            opinion_vectors={"policy": 1.0},
            influence_level=1.0,
        )
        listener = _make_persona(
            name="Near-extreme",
            opinion_vectors={"policy": 0.95},
            opinion_bias=0.0,
            reaction_speed=1.0,
        )

        engine = OpinionDynamics(base_shift_rate=5.0)
        engine.process_interaction(
            speaker_persona=speaker,
            listener_persona=listener,
            speaker_id="s",
            listener_id="l",
            trust_level=10,
        )

        assert -1.0 <= listener.opinion_vectors["policy"] <= 1.0


class TestPersonaOpinionFields:
    """Verify the Persona model accepts and stores opinion dynamics fields."""

    def test_persona_has_opinion_fields(self):
        """Create Persona with opinion_vectors and verify all fields exist."""
        p = _make_persona(
            opinion_vectors={"environment": 0.6, "taxation": -0.3},
            opinion_bias=0.7,
            reaction_speed=0.4,
            influence_level=0.8,
        )
        assert p.opinion_vectors == {"environment": 0.6, "taxation": -0.3}
        assert p.opinion_bias == 0.7
        assert p.reaction_speed == 0.4
        assert p.influence_level == 0.8

    def test_persona_defaults(self):
        """Persona opinion fields should have sensible defaults."""
        p = Persona(name="Default", age=25, sex="female", occupation="Student")
        assert p.opinion_vectors == {}
        assert p.opinion_bias == 0.5
        assert p.reaction_speed == 0.5
        assert p.influence_level == 0.5

    def test_persona_opinion_bias_validation(self):
        """opinion_bias must be between 0.0 and 1.0."""
        with pytest.raises(Exception):
            _make_persona(opinion_bias=1.5)
        with pytest.raises(Exception):
            _make_persona(opinion_bias=-0.1)
