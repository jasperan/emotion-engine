"""Ollama LLM client using native /api/chat endpoint.

Includes ORBR-inspired fail-safe mechanisms:
- Retry with exponential backoff
- OOM / CUDA error detection with model unloading
- Watchdog timeout for hung requests (asyncio.wait_for)
- Automatic model unloading on persistent failures
"""
import asyncio
import json
import logging
import subprocess
import time
import httpx
from typing import Any, Callable, Awaitable

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse
from emotionsim.core.config import get_settings

logger = logging.getLogger(__name__)

# Module-level semaphore: one per process, shared across all agents
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


_TAG_CACHE: dict[tuple[str, str], str] = {}
_TAG_CACHE_TS: dict[tuple[str, str], float] = {}
_TAG_TTL = 120.0  # seconds; model lists change rarely


def resolve_ollama_tag(native_url: str, model: str, timeout: float = 3.0) -> str:
    """Resolve a model name to an existing Ollama tag.

    Handles two local-run frictions:
    - Built-in scenarios reference bare names (``gemma3``) while Ollama
      requires the full tag (``gemma3:4b``).
    - Code defaults reference tags that may not exist on the machine
      (``qwen3.5:27b`` → any available ``qwen3.5:*``).

    Resolution order: exact tag → bare-name family match → same-family tag
    (wrong-version case) → the name as-is (let Ollama 404 rather than
    silently substituting a different family). Results are cached per
    (server, model) with a short TTL.
    """
    import time

    now = time.monotonic()
    key = (native_url, model)
    cached = _TAG_CACHE.get(key)
    ts = _TAG_CACHE_TS.get(key, 0.0)
    if cached is not None and now - ts < _TAG_TTL:
        return cached

    family = model.split(":", 1)[0] if ":" in model else model

    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            resp = client.get(native_url + "/api/tags")
            if resp.status_code >= 400:
                _TAG_CACHE[key] = model
                _TAG_CACHE_TS[key] = now
                return model
            tags = [m.get("name", "") for m in resp.json().get("models", [])]
        if model in tags:
            _TAG_CACHE[key] = model
            _TAG_CACHE_TS[key] = now
            return model
        for tag in tags:
            if tag.startswith(model + ":"):
                logger.info("Ollama tag resolve: %s → %s", model, tag)
                _TAG_CACHE[key] = tag
                _TAG_CACHE_TS[key] = now
                return tag
        for tag in tags:
            if tag.startswith(family + ":"):
                logger.info(
                    "Ollama tag resolve: %s not on server → family member %s",
                    model,
                    tag,
                )
                _TAG_CACHE[key] = tag
                _TAG_CACHE_TS[key] = now
                return tag
    except Exception:
        pass

    _TAG_CACHE[key] = model
    _TAG_CACHE_TS[key] = now
    return model


def clear_tag_cache() -> None:
    """Drop cached tag resolutions (tests)."""
    _TAG_CACHE.clear()
    _TAG_CACHE_TS.clear()


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an error is retryable (transient failures)."""
    err_str = str(exc).lower()

    # Timeout errors are always retryable
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return True

    # HTTP 5xx errors are retryable
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True

    # Connection errors are retryable
    if isinstance(exc, (httpx.ConnectError, httpx.RemoteProtocolError, ConnectionError)):
        return True

    # CUDA OOM is retryable (after unloading)
    if "cuda" in err_str and ("out of memory" in err_str or "oom" in err_str):
        return True

    # Ollama-specific retryable errors
    if "llama runner" in err_str or "model is loading" in err_str:
        return True

    return False


def _is_oom_error(exc: Exception) -> bool:
    """Check if the error indicates GPU out-of-memory."""
    err_str = str(exc).lower()
    if "cuda" in err_str and ("out of memory" in err_str or "oom" in err_str):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            body = exc.response.text.lower()
            if "cuda" in body and ("out of memory" in body or "oom" in body):
                return True
        except Exception:
            pass
    return False


class OllamaClient(LLMClient):
    """LLM client for Ollama via native /api/chat endpoint.

    Uses the native API instead of OpenAI-compat because the compat layer
    strips qwen3.5 thinking tokens and returns empty content.

    Fail-safe mechanisms (ORBR-inspired):
    - Retry with exponential backoff (3 attempts, 2s/4s/8s delays)
    - OOM detection: unloads model via keep_alive=0 and kills runners
    - Watchdog timeout: asyncio.wait_for with configurable wall-clock limit
    """

    # Retry configuration
    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2.0  # seconds
    WALL_TIMEOUT = 180  # 3 minutes hard wall-clock limit per request

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

        # Read timeout honors OLLAMA_TIMEOUT with a 120s floor: first-token
        # latency on a loaded model with a long system prompt can exceed 90s,
        # and a too-tight read timeout wastes the whole generation on retry.
        request_timeout = max(float(settings.ollama_timeout), 120.0)
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=request_timeout,  # completion (prompt eval can take 30s+)
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
        """Generate response (semaphore-gated, with retry and watchdog)."""
        settings = get_settings()
        sem = get_llm_semaphore()

        if settings.vram_aware_mode:
            effective_model = model or self.default_model
            warm = await is_model_warm_cached(effective_model, self.native_url)
            if not warm:
                await asyncio.sleep(0.5)

        async with sem:
            return await self._generate_with_retry(
                messages, model, temperature, max_tokens, system, json_mode, stream_callback
            )

    async def _generate_with_retry(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        system: str | None = None,
        json_mode: bool = False,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        """Retry wrapper with exponential backoff and OOM handling."""
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                # Wrap in watchdog timeout
                result = await asyncio.wait_for(
                    self._generate_inner(
                        messages, model, temperature, max_tokens, system, json_mode, stream_callback
                    ),
                    timeout=self.WALL_TIMEOUT,
                )
                return result

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Watchdog timeout: LLM request hung for {self.WALL_TIMEOUT}s "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                logger.warning(str(last_error))
                # Kill hung ollama runners on timeout
                await self._kill_hung_runners()

            except Exception as exc:
                last_error = exc

                # OOM: unload model and kill runners before retry
                if _is_oom_error(exc):
                    effective_model = model or self.default_model
                    logger.warning(
                        f"CUDA OOM on {effective_model} (attempt {attempt + 1}), "
                        f"unloading model and killing runners"
                    )
                    await self._unload_model(effective_model)
                    await self._kill_hung_runners()

                if not _is_retryable_error(exc):
                    logger.error(f"Non-retryable LLM error: {exc}")
                    raise

                logger.warning(
                    f"Retryable LLM error (attempt {attempt + 1}/{self.MAX_RETRIES}): "
                    f"{exc!r}"
                )

            # Exponential backoff before retry
            if attempt < self.MAX_RETRIES - 1:
                delay = self.BASE_RETRY_DELAY * (2 ** attempt)
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        # All retries exhausted
        raise last_error or RuntimeError("All LLM retries exhausted")

    async def _unload_model(self, model: str) -> None:
        """Unload model from Ollama VRAM via keep_alive=0."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.native_url}/api/generate",
                    json={"model": model, "keep_alive": 0},
                )
            logger.info(f"Requested unload of {model}")
            # Invalidate VRAM cache
            _vram_cache.pop(model, None)
        except Exception as e:
            logger.warning(f"Failed to unload model {model}: {e}")

    async def _kill_hung_runners(self) -> None:
        """Kill hung ollama runner processes to free GPU memory."""
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["pkill", "-f", "ollama runner"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info("Killed hung ollama runner processes")
            await asyncio.sleep(2)  # Give GPU time to free memory
        except Exception as e:
            logger.debug(f"pkill ollama runner: {e}")

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
        model = resolve_ollama_tag(self.native_url, model)

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
            "keep_alive": get_settings().ollama_keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        # NOTE: Do NOT use Ollama's native format:"json"; it hangs with think:false.
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

    async def close(self) -> None:
        """Close the underlying HTTP client to release connections."""
        if self.http_client:
            await self.http_client.aclose()

    def __del__(self) -> None:
        """Safety net: warn if client was not explicitly closed."""
        if hasattr(self, "http_client") and self.http_client and not self.http_client.is_closed:
            logger.warning("OllamaClient was garbage-collected without calling close()")

    async def health_check(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = await self.http_client.get(
                f"{self.native_url}/api/tags", timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
