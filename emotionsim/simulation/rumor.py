"""Message distortion / rumor spread.

When an agent retells another agent's message (direct or broadcast), the
retelling is a *relay*: the story loses fidelity per hop, exactly like real
rumor chains. The engine feeds every step's messages through
:class:`RumorTracker`; chains (content-similar relays by different agents)
accumulate hops. When a HumanAgent later renders its memories (key facts),
relayed messages are shown **distorted** by :func:`distort_text`, so the LLM
acts on degraded information — genuine rumor dynamics in agent behavior.

Determinism: distortion is a pure function of (original text, hop count,
chain seed) — no RNG state — so sequential mode stays reproducible. The whole
layer is off by default (``RUMOR_DISTORTION_ENABLED=false``).
"""
from __future__ import annotations

import hashlib
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tokens that carry little information and should not define "sameness".
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "then", "else", "of", "to", "in", "on", "at",
    "for", "with", "i", "you", "he", "she", "it", "we", "they", "my", "your",
    "his", "her", "its", "our", "their", "this", "that", "these", "those",
    "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "shall", "may", "might", "not", "no", "so", "as",
    "by", "from", "up", "down", "about", "into", "out", "over", "after",
    "before", "just", "very", "really", "also",
}

# Confusion pairs: plausible single-word mutations in retelling.
_CONFUSIONS: dict[str, str] = {
    "yes": "no",
    "north": "south",
    "east": "west",
    "bridge": "street",
    "street": "bridge",
    "flood": "water",
    "water": "rain",
    "roof": "door",
    "door": "window",
    "strong": "broken",
    "safe": "dangerous",
    "dangerous": "safe",
    "nearby": "far",
    "far": "nearby",
    "upstairs": "ground",
    "help": "wait",
    "helping": "ignoring",
    "careful": "quick",
    "slowly": "quickly",
    "morning": "evening",
    "evening": "morning",
    "two": "five",
    "three": "six",
    "many": "few",
    "few": "many",
    "children": "people",
    "injured": "missing",
    "alive": "safe",
    "trapped": "free",
    "still": "already",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def token_overlap(a: str, b: str) -> float:
    """Jaccard similarity of the content-bearing tokens of two texts."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def chain_id(text: str) -> str:
    """Stable id for a rumor chain from its origin content."""
    toks = sorted(_tokens(text))
    return hashlib.md5("|".join(toks).encode()).hexdigest()[:16]


def _rng_float(seed: str, index: int) -> float:
    """Deterministic pseudo-random float in [0,1) from (seed, index)."""
    h = int(hashlib.md5(f"{seed}:{index}".encode()).hexdigest()[:8], 16)
    return (h % 1_000_000) / 1_000_000


def distort_text(text: str, hops: int, seed: str, fidelity_drop: float = 0.15) -> str:
    """Deterministically degrade *text* by *hops* retellings.

    Each hop: fidelity = max(0.25, 1 - hops*fidelity_drop). A deterministic
    fraction of tokens (proportional to 1-fidelity) mutate: confusion-word
    substitution, neighbor swap, or (at low fidelity) outright drop. At least
    one mutation is always applied per hop so retold stories visibly drift.
    Identical inputs produce identical output (needed for determinism).
    """
    if hops <= 0:
        return text
    fidelity = max(0.25, 1.0 - hops * fidelity_drop)

    words = text.split()
    n = len(words)
    if n < 3:
        return text

    # Number of corrupted tokens this hop: at least 1, roughly (1-fidelity)*n.
    corrupt = max(1, int(n * (1.0 - fidelity)))
    indexes = sorted(
        {int(_rng_float(seed, i) * n) for i in range(1, corrupt + 3)}
    )[:corrupt]

    for idx in indexes:
        key = re.sub(r"[^a-z0-9']", "", words[idx].lower())
        if key in _CONFUSIONS:
            words[idx] = _CONFUSIONS[key]
        elif fidelity < 0.6 and _rng_float(seed + "d", idx) > 0.55:
            words[idx] = ""  # drop marker
        elif idx + 1 < n:
            # order corruption: swap with the next token
            words[idx], words[idx + 1] = words[idx + 1], words[idx]
        else:
            words[idx] = words[idx].upper() if idx % 2 else words[idx].lower()

    # Extra reorder at low fidelity (deterministic).
    if n >= 8 and fidelity < 0.6 and _rng_float(seed, n) > 0.5:
        a = int(_rng_float(seed, n + 1) * n)
        b = int(_rng_float(seed, n + 2) * n)
        words[a], words[b] = words[b], words[a]

    return " ".join(w for w in words if w != "")


class RumorTracker:
    """Tracks rumor chains across steps.

    ``feed_message`` detects relays: a message whose content-bearing tokens
    overlap heavily with the latest retelling of an existing chain, sent by a
    different agent. Chains start at hop 0 with the origin message; each relay
    by a new agent bumps the hop count once. Matching is overlap-based (a
    relay rarely reproduces the origin verbatim), so chain ids are an internal
    detail — readers match by :func:`find_chain`.
    """

    def __init__(self, overlap_threshold: float = 0.5) -> None:
        self.overlap_threshold = overlap_threshold
        self.chains: dict[str, dict[str, Any]] = {}  # chain_id -> info
        self._last_content_by_chain: dict[str, str] = {}
        self._seen_by: dict[str, set[str]] = {}
        self.rumor_events: list[dict[str, Any]] = []  # observability

    def _find_chain(self, content: str, sender: str) -> str | None:
        """Return the chain id this message relays, or None."""
        best: str | None = None
        best_overlap = self.overlap_threshold
        for cid, info in self.chains.items():
            if sender in self._seen_by.get(cid, set()):
                continue
            prev = self._last_content_by_chain.get(cid, info["origin_content"])
            ov = token_overlap(prev, content)
            if ov >= best_overlap:
                best_overlap = ov
                best = cid
        return best

    def feed_message(self, msg: dict[str, Any]) -> None:
        """Register one message; detect/hydrate a rumor chain."""
        content = (msg.get("content") or "").strip()
        sender = msg.get("from_agent") or msg.get("from_agent_name") or "?"
        if not content or len(_tokens(content)) < 3:
            return

        cid = self._find_chain(content, sender)
        if cid is None:
            # New origin (id derived from this content's canonical tokens).
            cid = chain_id(content)
            self.chains[cid] = {
                "origin": sender,
                "origin_content": content,
                "hops": 0,
                "last": sender,
            }
            self._last_content_by_chain[cid] = content
            self._seen_by[cid] = {sender}
            return

        info = self.chains[cid]
        info["hops"] += 1
        info["last"] = sender
        self._seen_by[cid].add(sender)
        self._last_content_by_chain[cid] = content
        self.rumor_events.append(
            {
                "chain": cid,
                "hops": info["hops"],
                "origin": info["origin"],
                "relayer": sender,
                "content": content,
            }
        )
        logger.info(
            "Rumor spread: %s retold %s's story (hop %d)",
            sender,
            info["origin"],
            info["hops"],
        )

    def feed_step(self, messages: list[dict[str, Any]]) -> None:
        for msg in messages:
            self.feed_message(msg)

    def state(self) -> dict[str, dict[str, Any]]:
        """Snapshot for injection into world_state (transient '_rumors')."""
        return {
            cid: {
                "hops": info["hops"],
                "origin": info["origin"],
                "last_content": self._last_content_by_chain.get(cid, info["origin_content"]),
            }
            for cid, info in self.chains.items()
            if info["hops"] >= 1
        }

    def distort_fn(self, fidelity_drop: float = 0.15):
        """Return a function: original content -> distorted content (or same)."""

        def distort_for(content: str, reader: str | None = None) -> str:
            cid = find_chain(self.state(), content, self.overlap_threshold, exclude_reader=reader)
            if cid is None:
                return content
            info = self.state()[cid]
            return distort_text(
                content, info["hops"], cid, fidelity_drop=fidelity_drop
            )

        return distort_for


def find_chain(
    rumor_state: dict[str, dict[str, Any]],
    content: str,
    threshold: float = 0.5,
    exclude_reader: str | None = None,
) -> str | None:
    """Find the rumor chain a piece of content relays (reader-side matching).

    Works on the same snapshot the engine injects into world_state so prompt
    rendering can degrade retold stories without touching the tracker.
    Returns the chain id or None. The origin agent's own retelling is exempt
    (they know exactly what they said).
    """
    best: str | None = None
    best_overlap = threshold
    for cid, info in rumor_state.items():
        if exclude_reader is not None and info.get("origin") == exclude_reader:
            continue
        prev = info.get("last_content", "")
        ov = token_overlap(prev, content)
        if ov >= best_overlap:
            best_overlap = ov
            best = cid
    return best