"""Semantic caching of LLM responses.

Repeated or near-identical prompts (same situation text, same system
instructions) produce the same expensive LLM round-trip. The semantic cache
embeds the prompt (real embeddings via Ollama nomic-embed-text when available,
a deterministic offline n-gram embedder otherwise), stores the response, and
serves it back when the cosine similarity of a new prompt passes a threshold.

Determinism note: caching is **off by default** (`LLM_CACHE_ENABLED=false`) so
the default simulation path is byte-identical to before. When enabled, repeated
prompts resolve to the same stored response — deterministic, faster, cheaper
by design. A temperature knob lets users restrict caching to low-temperature
requests.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import time
from dataclasses import dataclass, field

from emotionsim.llm.base import LLMResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedders
# ---------------------------------------------------------------------------

class CharNgramEmbedder:
    """Deterministic, offline embedder: hashed character n-gram vector.

    Near-duplicate prompts share most n-grams (high cosine); unrelated prompts
    are dissimilar. Used when no embedding service is reachable, and always in
    hermetic tests. Deterministic across processes (md5-hashed buckets).
    """

    def __init__(self, n: int = 4, size: int = 2048) -> None:
        self.n = n
        self.size = size

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.size
        text = " ".join(text.split()).lower()
        if len(text) < self.n:
            return vec
        for i in range(len(text) - self.n + 1):
            gram = text[i : i + self.n]
            h = int(hashlib.md5(gram.encode()).hexdigest()[:8], 16)
            vec[h % self.size] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OllamaEmbedder:
    """Async adapter around EmbeddingService (nomic-embed-text, 768d)."""

    def __init__(self) -> None:
        from emotionsim.storage.embedding_service import EmbeddingService

        self._svc = EmbeddingService()

    async def embed(self, text: str) -> list[float]:
        return await self._svc.embed_text(text)


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two normalized vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

@dataclass
class _Entry:
    embedding: list[float]
    content: str
    model: str
    stored_at: float


class SemanticLLMCache:
    """Thread-safe (asyncio) semantic response cache with TTL + size cap."""

    def __init__(
        self,
        threshold: float = 0.95,
        max_entries: int = 1024,
        ttl: float = 3600.0,
        embedder=None,
        embedder_kind: str = "auto",
    ) -> None:
        # Coerce numerics defensively (mock/faulty settings shouldn't crash).
        try:
            self.threshold = float(threshold)
        except (TypeError, ValueError):
            self.threshold = 0.95
        try:
            self.max_entries = int(max_entries)
        except (TypeError, ValueError):
            self.max_entries = 1024
        try:
            self.ttl = float(ttl)
        except (TypeError, ValueError):
            self.ttl = 3600.0
        self._embedder = embedder
        self._embedder_kind = embedder_kind
        self._entries: list[_Entry] = []
        self._lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

    # -- embedding ----------------------------------------------------------

    async def _embed(self, text: str) -> list[float]:
        if self._embedder is None:
            self._embedder = await self._make_embedder()
        result = self._embedder.embed(text)
        if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
            return await result
        return result

    async def _make_embedder(self):
        if self._embedder_kind == "ngram":
            return CharNgramEmbedder()
        if self._embedder_kind == "ollama":
            return OllamaEmbedder()
        # "auto": use Ollama nomic-embed-text when reachable, else offline.
        from emotionsim.core.config import get_settings
        from emotionsim.core.runtime import probe_ollama

        if probe_ollama(get_settings().ollama_base_url):
            logger.info("Semantic cache: using Ollama nomic-embed-text embedder")
            return OllamaEmbedder()
        logger.info("Semantic cache: using offline n-gram embedder")
        return CharNgramEmbedder()

    # -- public API ---------------------------------------------------------

    def _build_prompt(self, messages, system: str | None, json_mode: bool) -> str:
        parts = []
        if system:
            parts.append("SYSTEM: " + system)
        for msg in messages:
            parts.append(f"{msg.role}: {msg.content}")
        if json_mode:
            parts.append("MODE: json")
        return "\n".join(parts)

    async def get(
        self,
        messages,
        system: str | None,
        json_mode: bool,
        model: str,
    ) -> LLMResponse | None:
        """Return a cached response for a semantically similar prompt, or None."""
        if not self._entries:
            self.misses += 1
            return None

        prompt = self._build_prompt(messages, system, json_mode)
        try:
            emb = await self._embed(prompt)
        except Exception as exc:  # embedding failure → treat as miss, never crash
            logger.debug("Semantic cache embed failed: %s", exc)
            self.misses += 1
            return None

        now = time.monotonic()
        best: _Entry | None = None
        best_sim = self.threshold
        async with self._lock:
            for e in self._entries:
                if e.model != model:
                    continue
                if now - e.stored_at > self.ttl:
                    continue
                sim = cosine(emb, e.embedding)
                if sim >= best_sim:
                    best_sim = sim
                    best = e
        if best is not None:
            self.hits += 1
            logger.info("Semantic cache HIT (sim=%.3f, model=%s)", best_sim, model)
            return LLMResponse(content=best.content)
        self.misses += 1
        return None

    async def put(
        self,
        messages,
        system: str | None,
        json_mode: bool,
        model: str,
        response: LLMResponse,
    ) -> None:
        content = (response.content or "").strip()
        if not content:
            return
        prompt = self._build_prompt(messages, system, json_mode)
        try:
            emb = await self._embed(prompt)
        except Exception as exc:
            logger.debug("Semantic cache embed failed (no store): %s", exc)
            return

        now = time.monotonic()
        async with self._lock:
            self._entries.append(_Entry(emb, content, model, now))
            # Evict expired entries, then cap size (oldest dropped).
            self._entries = [
                e for e in self._entries if now - e.stored_at <= self.ttl
            ]
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries :]

    @property
    def size(self) -> int:
        return len(self._entries)

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "entries": self.size}


# ---------------------------------------------------------------------------
# Process-wide singleton (config-driven)
# ---------------------------------------------------------------------------

_cache: SemanticLLMCache | None = None


def get_semantic_cache() -> SemanticLLMCache:
    """Return the process-wide semantic cache configured from settings."""
    global _cache
    if _cache is None:
        from emotionsim.core.config import get_settings

        s = get_settings()
        _cache = SemanticLLMCache(
            threshold=s.llm_cache_threshold,
            max_entries=s.llm_cache_max_entries,
            ttl=s.llm_cache_ttl_seconds,
            embedder_kind=s.llm_cache_embedding,
        )
    return _cache


def reset_semantic_cache() -> None:
    """Drop the singleton (tests)."""
    global _cache
    _cache = None