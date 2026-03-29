"""Tests for EmbeddingService (mocked, no live Ollama required)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage.embedding_service import EmbeddingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_embedding(dim: int = 768) -> list[float]:
    """Return a deterministic non-zero vector for assertions."""
    return [float(i) / dim for i in range(dim)]


def _make_mock_response(embeddings: list[list[float]], status: int = 200):
    """Build an async-context-manager mock that mimics aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value={"embeddings": embeddings})
    return resp


def _make_mock_session(mock_response):
    """Build a mock aiohttp.ClientSession whose .post() returns *mock_response*."""
    post_cm = AsyncMock()
    post_cm.__aenter__ = AsyncMock(return_value=mock_response)
    post_cm.__aexit__ = AsyncMock(return_value=False)

    session = AsyncMock()
    session.post = MagicMock(return_value=post_cm)

    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    return session_cm, session


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestEmbeddingServiceInit:
    def test_defaults(self):
        """Service picks up defaults from settings when no args given."""
        svc = EmbeddingService()
        assert svc.model == "nomic-embed-text"
        assert svc.dimension == 768
        # base_url should have /v1 stripped
        assert not svc.base_url.endswith("/v1")

    def test_custom_config(self):
        svc = EmbeddingService(
            model="mxbai-embed-large",
            base_url="http://myhost:9999",
            dimension=1024,
        )
        assert svc.model == "mxbai-embed-large"
        assert svc.base_url == "http://myhost:9999"
        assert svc.dimension == 1024

    def test_v1_suffix_stripped(self):
        svc = EmbeddingService(base_url="http://localhost:11434/v1")
        assert svc.base_url == "http://localhost:11434"

    def test_v1_slash_suffix_stripped(self):
        svc = EmbeddingService(base_url="http://localhost:11434/v1/")
        assert svc.base_url == "http://localhost:11434"


# ---------------------------------------------------------------------------
# embed_text
# ---------------------------------------------------------------------------

class TestEmbedText:
    @pytest.mark.asyncio
    async def test_returns_embedding(self):
        svc = EmbeddingService(base_url="http://localhost:11434")
        fake_emb = _fake_embedding(768)
        mock_resp = _make_mock_response([fake_emb])
        session_cm, session = _make_mock_session(mock_resp)

        with patch("app.storage.embedding_service.aiohttp.ClientSession", return_value=session_cm):
            result = await svc.embed_text("hello world")

        assert result == fake_emb
        session.post.assert_called_once()
        call_args = session.post.call_args
        assert "/api/embed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_empty_string_returns_zero_vector(self):
        svc = EmbeddingService(base_url="http://localhost:11434")
        result = await svc.embed_text("")
        assert result == [0.0] * 768
        assert len(result) == 768

    @pytest.mark.asyncio
    async def test_whitespace_returns_zero_vector(self):
        svc = EmbeddingService(base_url="http://localhost:11434")
        result = await svc.embed_text("   ")
        assert result == [0.0] * 768


# ---------------------------------------------------------------------------
# embed_batch
# ---------------------------------------------------------------------------

class TestEmbedBatch:
    @pytest.mark.asyncio
    async def test_batch_returns_embeddings(self):
        svc = EmbeddingService(base_url="http://localhost:11434")
        fake_emb_1 = _fake_embedding(768)
        fake_emb_2 = [x + 1.0 for x in _fake_embedding(768)]
        mock_resp = _make_mock_response([fake_emb_1, fake_emb_2])
        session_cm, session = _make_mock_session(mock_resp)

        with patch("app.storage.embedding_service.aiohttp.ClientSession", return_value=session_cm):
            results = await svc.embed_batch(["hello", "world"])

        assert len(results) == 2
        assert results[0] == fake_emb_1
        assert results[1] == fake_emb_2

    @pytest.mark.asyncio
    async def test_batch_handles_empty_strings(self):
        """Empty strings get zero vectors; non-empty go to the API."""
        svc = EmbeddingService(base_url="http://localhost:11434")
        fake_emb = _fake_embedding(768)
        mock_resp = _make_mock_response([fake_emb])
        session_cm, session = _make_mock_session(mock_resp)

        with patch("app.storage.embedding_service.aiohttp.ClientSession", return_value=session_cm):
            results = await svc.embed_batch(["", "hello", "  "])

        assert len(results) == 3
        assert results[0] == [0.0] * 768  # empty
        assert results[1] == fake_emb     # real
        assert results[2] == [0.0] * 768  # whitespace

        # Only one text should have been sent to the API.
        call_args = session.post.call_args
        payload = call_args[1]["json"]
        assert payload["input"] == ["hello"]

    @pytest.mark.asyncio
    async def test_batch_all_empty(self):
        """If every input is empty, no HTTP call should be made."""
        svc = EmbeddingService(base_url="http://localhost:11434")
        results = await svc.embed_batch(["", "  ", ""])
        assert len(results) == 3
        for vec in results:
            assert vec == [0.0] * 768

    @pytest.mark.asyncio
    async def test_batch_empty_list(self):
        svc = EmbeddingService(base_url="http://localhost:11434")
        results = await svc.embed_batch([])
        assert results == []
