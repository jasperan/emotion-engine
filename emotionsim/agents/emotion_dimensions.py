"""Continuous emotion dimensions: valence (pleasure↔displeasure) and arousal.

Agents carry two scalar emotion channels in [-1.0, 1.0]:
- **valence**  — how pleasant/positive the emotional state is
- **arousal**  — how activated/energized it is (calm ↔ excited/tense)

Sources of motion (all clamped to [-1, 1], gated behind
``EMOTION_DIMENSIONS_ENABLED`` so the default path is byte-identical):
1. **Personality baselines** — agreeableness lifts valence, extraversion
   lifts arousal, neuroticism raises arousal baseline reactivity.
2. **Events** — receiving help boosts valence; observing danger (high hazard)
   raises arousal and lowers valence; stress couples up to arousal.
3. **The LLM itself** — the dominant emotion in the act response (e.g.
   "panic", "relieved") pulls the dimensions toward its lexicon values.

Effects:
- Arousal raises response probability in ``should_respond`` (activated agents
  speak/move more).
- The emotional state is surfaced to the LLM in ``build_context`` so prose,
  decisions, and the next emotion reflect it.
- The current dimensions ride along ``dynamic_state`` and persist with the run.
"""
from __future__ import annotations

# emotion word/category → (valence, arousal) in [-1, 1]²
EMOTION_LEXICON: dict[str, tuple[float, float]] = {
    "panic": (-0.85, 0.95),
    "terrified": (-0.9, 0.95),
    "frightened": (-0.8, 0.85),
    "fear": (-0.8, 0.8),
    "despair": (-0.9, 0.3),
    "desperate": (-0.7, 0.75),
    "hopeless": (-0.85, 0.2),
    "angry": (-0.6, 0.75),
    "anger": (-0.6, 0.75),
    "furious": (-0.8, 0.9),
    "frustrated": (-0.45, 0.6),
    "anxious": (-0.5, 0.7),
    "worried": (-0.45, 0.55),
    "tense": (-0.4, 0.55),
    "stressed": (-0.5, 0.6),
    "nervous": (-0.4, 0.5),
    "uneasy": (-0.35, 0.4),
    "sad": (-0.5, -0.25),
    "grief": (-0.75, -0.3),
    "grieving": (-0.7, -0.35),
    "tired": (-0.2, -0.5),
    "fatigued": (-0.3, -0.5),
    "exhausted": (-0.4, -0.6),
    "calm": (0.45, -0.45),
    "peaceful": (0.6, -0.5),
    "relieved": (0.65, -0.45),
    "grateful": (0.8, 0.15),
    "thankful": (0.75, 0.1),
    "hopeful": (0.6, 0.25),
    "determined": (0.3, 0.4),
    "resolute": (0.35, 0.4),
    "focused": (0.2, 0.3),
    "confident": (0.55, 0.4),
    "brave": (0.4, 0.5),
    "happy": (0.8, 0.35),
    "hopeful": (0.6, 0.25),
    "optimistic": (0.65, 0.3),
    "joy": (0.9, 0.45),
    "excited": (0.6, 0.8),
    "cautious": (-0.1, 0.1),
    "neutral": (0.0, 0.0),
}

# Fallback for unseen words: infer from the word's sentiment-ish cues.
_POSITIVE_HINTS = ("hope", "calm", "relief", "grateful", "happy", "peace", "joy", "brave", "confident")
_NEGATIVE_HINTS = ("fear", "panic", "anger", "despair", "sad", "grief", "tense", "anxious", "worry", "stress", "hopeless")
_HIGH_AROUSAL_HINTS = ("panic", "terr", "fear", "angr", "furious", "excited", "anxious", "tense", "desperate", "nervous")
_LOW_AROUSAL_HINTS = ("calm", "peace", "tired", "fatigu", "exhaust", "relief", "sad", "grief")


def clamp(v: float) -> float:
    """Clamp to [-1, 1]."""
    return max(-1.0, min(1.0, v))


def emotion_to_vector(emotion: str) -> tuple[float, float] | None:
    """Map an emotion word to (valence, arousal), or None when unrecognized.

    Substring matching (singular/plural, -ed/-ing forms, "very panicked").
    """
    text = (emotion or "").strip().lower()
    if not text:
        return None
    for word, vec in EMOTION_LEXICON.items():
        if word in text:
            return vec
    signs: list[tuple[float, float]] = []
    if any(h in text for h in _POSITIVE_HINTS):
        signs.append((0.5, 0.2))
    if any(h in text for h in _NEGATIVE_HINTS):
        signs.append((-0.5, 0.3))
    if signs:
        v = sum(s[0] for s in signs) / len(signs)
        a = sum(s[1] for s in signs) / len(signs)
        return (clamp(v), clamp(a))
    return None


def personality_baselines(persona) -> tuple[float, float]:
    """(valence, arousal) baselines from Big Five traits."""
    valence = (persona.agreeableness - 5) * 0.04 + (5 - persona.neuroticism) * 0.03
    arousal = (persona.extraversion - 5) * 0.04 + (persona.neuroticism - 5) * 0.03
    return (clamp(valence), clamp(arousal))


def compute_emotion_update(
    valence: float,
    arousal: float,
    base_valence: float,
    base_arousal: float,
    stress: float,
    hazard: float,
    helped: bool,
    danger_observed: bool,
    decay: float = 0.3,
    stress_coupling: float = 0.06,
    help_boost: float = 0.2,
    danger_valence: float = -0.12,
    danger_arousal: float = 0.18,
) -> tuple[float, float]:
    """One tick of valence/arousal dynamics (pure function for testing).

    - Relax toward personality baselines (decay).
    - Stress couples into arousal and pulls valence down.
    - Receiving help raises valence.
    - Observing danger lowers valence and raises arousal.
    """
    v = valence + decay * (base_valence - valence)
    a = arousal + decay * (base_arousal - arousal)

    if stress > 5:
        a += (stress - 5) * stress_coupling
        v -= (stress - 5) * 0.02
    if helped:
        v += help_boost
    if danger_observed or hazard >= 7:
        v += danger_valence
        a += danger_arousal
    return (clamp(v), clamp(a))


def valence_label(v: float) -> str:
    if v >= 0.35:
        return "positive"
    if v <= -0.35:
        return "negative"
    return "neutral"


def arousal_label(a: float) -> str:
    if a >= 0.35:
        return "activated"
    if a <= -0.35:
        return "calm"
    return "moderate"


def emotion_line(valence: float, arousal: float) -> str:
    """Human-readable prompt line, e.g. 'You feel neutral-positive, moderate activation'."""
    return (
        f"You feel {valence_label(valence)}-leaning with {arousal_label(arousal)} "
        f"activation (valence {valence:+.2f}, arousal {arousal:+.2f})."
    )