"""Topic extraction + stance estimation from real message content (Step 5).

Opinion dynamics previously shifted only pre-seeded persona topics on every
interaction. This module grounds topics in what agents actually *say*:
- ``extract_topics`` finds which topics a message discusses via a keyword lexicon
- ``estimate_stance`` estimates the speaker's stance from polarity words
"""

from __future__ import annotations

# topic -> trigger keywords (substring match, case-insensitive)
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "evacuation": ["evacuat", "leave now", "flee", "abandon the", "get out", "escape"],
    "rescue": ["rescue", "save the", "pull them out", "search and rescue", "retrieve"],
    "bridge": ["bridge", "crossing", "cross the river"],
    "shelter": ["shelter", "safe house", "take cover", "high ground", "hill", "rooftop"],
    "supplies": ["food", "water", "medicine", "med kit", "supplies", "first aid", "rations"],
    "medical": ["medical", "injured", "wound", "doctor", "nurse", "triage", "hospital"],
    "cooperation": ["help", "together", "cooperate", "assist", "team", "share", "unite"],
    "leadership": ["follow me", "take charge", "lead", "organize", "command", "in charge"],
    "communication": ["radio", "signal", "call for", "message", "contact", "reach them"],
    "danger": ["danger", "risk", "unsafe", "collapse", "rising water", "flood", "trapped"],
    "hope": ["hope", "survive", "we will make it", "stay strong", "better"],
}

POSITIVE_WORDS = {
    "help", "hope", "safe", "together", "good", "great", "rescue", "saved",
    "trust", "support", "survive", "strong", "better", "yes", "win",
}
NEGATIVE_WORDS = {
    "danger", "risk", "unsafe", "collapse", "trapped", "fear", "panic",
    "dead", "drown", "flood", "bad", "no", "lose", "fail", "abandon", "worse",
}


def extract_topics(text: str, max_topics: int = 3) -> list[str]:
    """Find which topics a message discusses (deduplicated, capped).

    Returns an empty list when no topic keywords match.
    """
    if not text:
        return []
    lowered = text.lower()
    found: list[str] = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found.append(topic)
    return found[:max_topics]


def estimate_stance(text: str) -> float | None:
    """Estimate a stance (-1.0..1.0) from the message's polarity words.

    Returns None when the message carries no polarity signal.
    """
    if not text:
        return None
    words = [w.strip(".,!?;:'\"()[]") for w in text.lower().split()]
    positive = sum(1 for w in words if w in POSITIVE_WORDS)
    negative = sum(1 for w in words if w in NEGATIVE_WORDS)
    if positive == 0 and negative == 0:
        return None
    total = positive + negative
    return (positive - negative) / total
