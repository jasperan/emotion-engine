"""Embedding service wrapping Ollama's embedding API (nomic-embed-text, 768d)."""

from __future__ import annotations

import aiohttp

from app.core.config import get_settings


class EmbeddingService:
    """Async wrapper around Ollama's /api/embed endpoint.

    Defaults to nomic-embed-text (768-dimensional embeddings).
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str | None = None,
        dimension: int = 768,
    ) -> None:
        self.model = model
        self.dimension = dimension
        # Ollama embedding endpoint lives at the raw base, not /v1.
        # Strip trailing /v1 (or /v1/) if present so callers can pass
        # the same ollama_base_url used for chat completions.
        if base_url is None:
            base_url = get_settings().ollama_base_url
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[: -len("/v1")]
        self.base_url = base_url

    def _zero_vector(self) -> list[float]:
        return [0.0] * self.dimension

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string via POST /api/embed.

        Returns a zero vector for empty/whitespace-only input.
        """
        if not text or not text.strip():
            return self._zero_vector()

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {"model": self.model, "input": text}
            async with session.post(
                f"{self.base_url}/api/embed", json=payload
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                # Ollama returns {"embeddings": [[...], ...]}
                return data["embeddings"][0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single call via POST /api/embed.

        Empty/whitespace-only strings are replaced with zero vectors
        without sending them to the model. Non-empty texts are batched
        into one request.
        """
        if not texts:
            return []

        # Track which indices are empty vs non-empty.
        non_empty_indices: list[int] = []
        non_empty_texts: list[str] = []
        for i, t in enumerate(texts):
            if t and t.strip():
                non_empty_indices.append(i)
                non_empty_texts.append(t)

        # Pre-fill results with zero vectors.
        results: list[list[float]] = [self._zero_vector() for _ in texts]

        if non_empty_texts:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {"model": self.model, "input": non_empty_texts}
                async with session.post(
                    f"{self.base_url}/api/embed", json=payload
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    embeddings = data["embeddings"]
                    for idx, emb in zip(non_empty_indices, embeddings):
                        results[idx] = emb

        return results
