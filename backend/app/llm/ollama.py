"""Ollama LLM client using native /api/chat endpoint"""
import asyncio
import json
import time
import httpx
from typing import Any, Callable, Awaitable

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.core.config import get_settings

# Module-level semaphore — one per process, shared across all agents
_llm_semaphore: asyncio.Semaphore | None = None


def get_llm_semaphore() -> asyncio.Semaphore:
    """Get (or lazily create) the global LLM semaphore."""
    global _llm_semaphore
    if _llm_semaphore is None:
        size = get_settings().max_concurrent_llm_calls
        _llm_semaphore = asyncio.Semaphore(size)
    return _llm_semaphore


def reset_llm_semaphore() -> None:
    """Reset the semaphore (for testing only)."""
    global _llm_semaphore
    _llm_semaphore = None


_vram_cache: dict[str, tuple[bool, float]] = {}  # model -> (is_warm, timestamp)
_VRAM_CACHE_TTL = 5.0  # seconds
_vram_cache_lock: asyncio.Lock | None = None


def get_vram_cache_lock() -> asyncio.Lock:
    global _vram_cache_lock
    if _vram_cache_lock is None:
        _vram_cache_lock = asyncio.Lock()
    return _vram_cache_lock


def reset_vram_cache() -> None:
    """Reset the VRAM cache and lock (for testing only)."""
    global _vram_cache, _vram_cache_lock
    _vram_cache = {}
    _vram_cache_lock = None


async def check_model_warm(model: str, native_url: str) -> bool:
    """Return True if model is currently loaded in Ollama (warm = low cold-start risk)."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{native_url}/api/ps")
            if resp.status_code != 200:
                return True  # assume warm on error (fail-open)
            running = resp.json().get("models", [])
            return any(model in m.get("name", "") for m in running)
    except Exception:
        return True  # fail-open: assume warm, don't block agents


async def is_model_warm_cached(model: str, native_url: str) -> bool:
    """Cached version of check_model_warm with 5-second TTL."""
    now = time.monotonic()
    # Fast path: check without lock first
    if model in _vram_cache:
        warm, ts = _vram_cache[model]
        if now - ts < _VRAM_CACHE_TTL:
            return warm
    # Slow path: acquire lock, re-check, then fetch
    lock = get_vram_cache_lock()
    async with lock:
        now = time.monotonic()  # re-read after acquiring lock
        if model in _vram_cache:
            warm, ts = _vram_cache[model]
            if now - ts < _VRAM_CACHE_TTL:
                return warm
        warm = await check_model_warm(model, native_url)
        _vram_cache[model] = (warm, now)
        return warm


def _native_url(base_url: str) -> str:
    """Strip /v1 suffix from Ollama base URL to get the native API URL."""
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url


class OllamaClient(LLMClient):
    """LLM client for Ollama via native /api/chat endpoint.

    Uses the native API instead of OpenAI-compat because the compat layer
    strips qwen3.5 thinking tokens and returns empty content.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        settings = get_settings()
        raw_url = base_url or settings.ollama_base_url
        self.native_url = _native_url(raw_url)
        self.default_model = default_model or settings.ollama_default_model

        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=90.0,   # 90s for completion (prompt eval can take 30s+)
                connect=10.0,
            )
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        system: str | None = None,
        json_mode: bool = False,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Generate response — semaphore-gated, optionally VRAM-aware."""
        settings = get_settings()
        sem = get_llm_semaphore()

        if settings.vram_aware_mode:
            effective_model = model or self.default_model
            warm = await is_model_warm_cached(effective_model, self.native_url)
            if not warm:
                await asyncio.sleep(0.5)

        async with sem:
            return await self._generate_inner(
                messages, model, temperature, max_tokens, system, json_mode, stream_callback
            )

    async def _generate_inner(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        system: str | None = None,
        json_mode: bool = False,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Generate via native Ollama /api/chat endpoint."""
        model = model or self.default_model

        # Build native Ollama message list
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        for msg in messages:
            ollama_messages.append({"role": msg.role, "content": msg.content})

        payload: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "think": False,  # Disable qwen3.5 internal thinking
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        # NOTE: Do NOT use Ollama's native format:"json" — it hangs with think:false.
        # Instead, JSON enforcement is done via the system/user prompt.
        if json_mode and ollama_messages:
            # Reinforce JSON output in the last user message
            last = ollama_messages[-1]
            if last["role"] == "user" and "JSON" not in last["content"][:100]:
                last["content"] = last["content"] + "\n\nRespond with valid JSON only."

        url = f"{self.native_url}/api/chat"

        if stream_callback:
            payload["stream"] = True
            return await self._stream_generate(url, payload, stream_callback)
        else:
            payload["stream"] = False
            return await self._batch_generate(url, payload)

    async def _batch_generate(
        self, url: str, payload: dict[str, Any]
    ) -> LLMResponse:
        """Non-streaming generation via native API."""
        resp = await self.http_client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            raw_response=data,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": (
                    data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                ),
            },
        )

    async def _stream_generate(
        self,
        url: str,
        payload: dict[str, Any],
        stream_callback: Callable[[str], Awaitable[None]],
    ) -> LLMResponse:
        """Streaming generation via native API (NDJSON)."""
        collected: list[str] = []
        usage: dict[str, int] = {}

        async with self.http_client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    collected.append(content)
                    await stream_callback(content)
                if chunk.get("done"):
                    usage = {
                        "prompt_tokens": chunk.get("prompt_eval_count", 0),
                        "completion_tokens": chunk.get("eval_count", 0),
                        "total_tokens": (
                            chunk.get("prompt_eval_count", 0)
                            + chunk.get("eval_count", 0)
                        ),
                    }

        return LLMResponse(
            content="".join(collected),
            raw_response={},
            usage=usage,
        )

    async def health_check(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = await self.http_client.get(
                f"{self.native_url}/api/tags", timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False

