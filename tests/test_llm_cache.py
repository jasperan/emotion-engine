"""Tests for the semantic LLM response cache (emotionsim/llm/cache.py)."""
from unittest.mock import AsyncMock, patch

import pytest

from emotionsim.core.config import Settings
from emotionsim.llm.base import LLMMessage, LLMResponse
from emotionsim.llm.cache import (
    CharNgramEmbedder,
    SemanticLLMCache,
    cosine,
    reset_semantic_cache,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    reset_semantic_cache()
    yield
    reset_semantic_cache()


def _msg(text: str) -> list[LLMMessage]:
    return [LLMMessage(role="user", content=text)]


class TestEmbedders:
    def test_ngram_identical_high_similarity(self):
        e = CharNgramEmbedder()
        a = e.embed("The rising flood water covers the bridge deck")
        b = e.embed("The rising flood water covers the bridge deck")
        assert cosine(a, b) > 0.99

    def test_ngram_unrelated_low_similarity(self):
        e = CharNgramEmbedder()
        a = e.embed("flood water rising bridge deck evacuation")
        b = e.embed("birthday cake candles party balloons celebration")
        assert cosine(a, b) < 0.5

    def test_ngram_near_duplicate_high_similarity(self):
        e = CharNgramEmbedder()
        a = e.embed("The rising flood water covers the bridge deck completely")
        b = e.embed("The rising flood water covers the bridge deck")
        assert cosine(a, b) > 0.8

    def test_ngram_deterministic(self):
        e = CharNgramEmbedder()
        text = "deterministic across processes please"
        assert e.embed(text) == e.embed(text)


class TestCacheCore:
    async def test_miss_then_hit_returns_cached_content(self):
        c = SemanticLLMCache(embedder=CharNgramEmbedder(), embedder_kind="ngram")
        await c.put(_msg("help the stranded family on the roof"), None, False, "m1", LLMResponse(content="I will help them."))
        hit = await c.get(_msg("help the stranded family on the roof"), None, False, "m1")
        assert hit is not None
        assert hit.content == "I will help them."
        assert c.stats()["hits"] == 1
        assert c.stats()["misses"] == 0
        # near-duplicate prompt (one character difference) also hits
        hit2 = await c.get(_msg("help the stranded family on the roof!"), None, False, "m1")
        assert hit2 is not None and hit2.content == "I will help them."
        # unrelated prompt misses
        miss = await c.get(_msg("where is the nearest coffee shop in tokyo"), None, False, "m1")
        assert miss is None
        assert c.stats()["misses"] >= 1

    async def test_model_is_part_of_the_key(self):
        c = SemanticLLMCache(embedder=CharNgramEmbedder(), embedder_kind="ngram")
        await c.put(_msg("same prompt"), None, False, "model_a", LLMResponse(content="from A"))
        assert await c.get(_msg("same prompt"), None, False, "model_b") is None
        assert await c.get(_msg("same prompt"), None, False, "model_a") is not None

    async def test_ttl_evicts(self):
        import asyncio

        c = SemanticLLMCache(embedder=CharNgramEmbedder(), embedder_kind="ngram", ttl=0.1)
        await c.put(_msg("prompt"), None, False, "m", LLMResponse(content="x"))
        await asyncio.sleep(0.15)
        assert await c.get(_msg("prompt"), None, False, "m") is None  # stale → miss

    async def test_max_entries_caps_size(self):
        c = SemanticLLMCache(
            embedder=CharNgramEmbedder(), embedder_kind="ngram", max_entries=3
        )
        for i in range(5):
            await c.put(_msg(f"unique prompt number {i}"), None, False, "m", LLMResponse(content=f"r{i}"))
        assert c.size == 3  # oldest two evicted
        assert await c.get(_msg("unique prompt number 4"), None, False, "m") is not None
        assert await c.get(_msg("completely unrelated about geese migration"), None, False, "m") is None

    async def test_empty_response_not_cached(self):
        c = SemanticLLMCache(embedder=CharNgramEmbedder(), embedder_kind="ngram")
        await c.put(_msg("p"), None, False, "m", LLMResponse(content="   "))
        assert c.size == 0

    async def test_embedding_failure_degrades_to_miss(self):
        class _BadEmbedder:
            async def embed(self, text):
                raise RuntimeError("embedder down")

        c = SemanticLLMCache(embedder=_BadEmbedder(), embedder_kind="ngram")
        await c.put(_msg("p"), None, False, "m", LLMResponse(content="x"))
        assert await c.get(_msg("p"), None, False, "m") is None  # never crashes


class TestRouterIntegration:
    """generate_with_fallback must serve cache hits without calling the provider."""

    async def _run_pair(self, settings, first_prompt, second_prompt):
        from emotionsim.llm.router import LLMRouter

        calls = []

        async def counting_generate(**kwargs):
            calls.append(kwargs)
            return LLMResponse(content="the-cached-answer")

        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch.object(LLMRouter, "get_client") as mock_get:
                mock_client = AsyncMock()
                mock_client.generate.side_effect = counting_generate
                mock_get.return_value = mock_client
                r1 = await LLMRouter.generate_with_fallback(
                    _msg(first_prompt), system="persona x"
                )
                r2 = await LLMRouter.generate_with_fallback(
                    _msg(second_prompt), system="persona x"
                )
        return r1, r2, calls

    async def test_second_call_hits_cache(self):
        settings = Settings(
            llm_backend="stub",
            llm_cache_enabled=True,
            llm_cache_threshold=0.9,
            llm_cache_embedding="ngram",
        )
        r1, r2, calls = await self._run_pair(
            settings,
            "what should we do about the rising water",
            "what should we do about the rising water?",
        )
        assert r1.content == "the-cached-answer"
        assert r2.content == "the-cached-answer"  # served from cache
        assert len(calls) == 1, f"provider called {len(calls)} times"

    async def test_cache_disabled_by_default(self):
        from emotionsim.llm.router import LLMRouter

        settings = Settings(llm_backend="stub", llm_cache_enabled=False)
        calls = []

        async def counting_generate(**kwargs):
            calls.append(kwargs)
            return LLMResponse(content="fresh")

        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch.object(LLMRouter, "get_client") as mock_get:
                mock_client = AsyncMock()
                mock_client.generate.side_effect = counting_generate
                mock_get.return_value = mock_client
                for _ in range(2):
                    await LLMRouter.generate_with_fallback(_msg("identical prompt"), system="s")
        assert len(calls) == 2  # no caching when disabled

    async def test_cache_hit_replays_stream(self):
        from emotionsim.llm.router import LLMRouter

        settings = Settings(
            llm_backend="stub",
            llm_cache_enabled=True,
            llm_cache_threshold=0.9,
            llm_cache_embedding="ngram",
        )
        calls = []
        chunks: list[str] = []

        async def counting_generate(**kwargs):
            calls.append(kwargs)
            return LLMResponse(content="streamed-content!")

        async def cb(tok: str):
            chunks.append(tok)

        with patch("emotionsim.core.config.get_settings", return_value=settings):
            with patch.object(LLMRouter, "get_client") as mock_get:
                mock_client = AsyncMock()
                mock_client.generate.side_effect = counting_generate
                mock_get.return_value = mock_client
                await LLMRouter.generate_with_fallback(
                    _msg("identical prompt for stream replay"), system="s", stream_callback=cb
                )
                await LLMRouter.generate_with_fallback(
                    _msg("identical prompt for stream replay"), system="s", stream_callback=cb
                )
        assert len(calls) == 1
        # The cached content was replayed through the stream callback on the hit
        # (the provider mock doesn't stream, so every chunk came from the cache).
        assert "".join(chunks) == "streamed-content!"