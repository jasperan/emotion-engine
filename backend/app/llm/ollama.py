"""Ollama LLM client using OpenAI-compatible API"""
import asyncio
import time
import httpx
from typing import Any, Callable, Awaitable
from openai import AsyncOpenAI

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
    if model in _vram_cache:
        warm, ts = _vram_cache[model]
        if now - ts < _VRAM_CACHE_TTL:
            return warm
    warm = await check_model_warm(model, native_url)
    _vram_cache[model] = (warm, now)
    return warm


class OllamaClient(LLMClient):
    """LLM client for Ollama via OpenAI-compatible API"""
    
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.ollama_base_url
        self.api_key = api_key or settings.ollama_api_key
        self.default_model = default_model or settings.ollama_default_model
        
        # Create httpx client with longer timeout for GPU-bound operations
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=120.0,  # 2 minutes for completion
                connect=10.0,   # 10 seconds to connect
            )
        )
        
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=http_client,
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

        # VRAM-aware: if model is cold, add a small delay before queuing
        # so any in-flight request can finish loading the model first
        if settings.vram_aware_mode:
            effective_model = model or self.default_model
            native_url = self.base_url.rstrip("/")
            if native_url.endswith("/v1"):
                native_url = native_url[:-3]
            warm = await is_model_warm_cached(effective_model, native_url)
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
        """Generate response using Ollama (inner, unsemaphored)"""
        model = model or self.default_model
        
        # Build message list
        openai_messages = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})
        
        # Make API call
        response_format = {"type": "json_object"} if json_mode else None
        
        if stream_callback:
            try:
                stream = await self.client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    stream=True,
                )
                
                collected_content = []
                
                async for chunk in stream:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        collected_content.append(content)
                        await stream_callback(content)
                
                full_content = "".join(collected_content)
                
                return LLMResponse(
                    content=full_content,
                    raw_response={},
                    usage={}
                )
            except Exception as e:
                # If streaming fails (e.g. not supported), fall back to normal
                print(f"Streaming failed, falling back to normal: {e}")
                # Fall through to non-streaming logic below
        
        # Non-streaming implementation (default or fallback)
        response = await self.client.chat.completions.create(
            model=model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        
        return LLMResponse(
            content=response.choices[0].message.content or "",
            raw_response=response.model_dump(),
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
        )
    
    async def health_check(self) -> bool:
        """Check if Ollama is available"""
        try:
            # Use base URL without /v1 for Ollama-specific endpoint
            base = self.base_url.replace("/v1", "")
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base}/api/tags", timeout=5.0)
                return response.status_code == 200
        except Exception:
            return False

