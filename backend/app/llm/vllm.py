"""vLLM LLM client using OpenAI-compatible /v1/chat/completions endpoint.

vLLM supports true parallel inference via continuous batching, making it
ideal for concurrent agent ticks. Unlike Ollama's single-slot architecture,
vLLM can handle N simultaneous requests efficiently on a single GPU.

Fail-safe mechanisms (ORBR-inspired):
- Retry with exponential backoff (3 attempts)
- OOM / CUDA error detection
- Watchdog timeout via asyncio.wait_for
"""
import asyncio
import json
import logging
import httpx
from typing import Any, Callable, Awaitable

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an error is retryable (transient failures)."""
    err_str = str(exc).lower()

    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.RemoteProtocolError, ConnectionError)):
        return True
    if "cuda" in err_str and ("out of memory" in err_str or "oom" in err_str):
        return True
    return False


class VLLMClient(LLMClient):
    """LLM client for vLLM via OpenAI-compatible API.

    Uses /v1/chat/completions endpoint. vLLM handles batching internally,
    so multiple concurrent requests are efficiently served.
    """

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2.0
    WALL_TIMEOUT = 180  # 3 minutes

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self.default_model = default_model or settings.vllm_default_model
        self.api_key = api_key or "EMPTY"  # vLLM doesn't require a real key

        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=120.0,
                connect=10.0,
            ),
            headers={"Authorization": f"Bearer {self.api_key}"},
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
        """Generate response with retry and watchdog (no semaphore needed).

        vLLM handles concurrency internally via continuous batching,
        so we don't gate with a semaphore like Ollama.
        """
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
        """Retry wrapper with exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = await asyncio.wait_for(
                    self._generate_inner(
                        messages, model, temperature, max_tokens, system, json_mode, stream_callback
                    ),
                    timeout=self.WALL_TIMEOUT,
                )
                return result

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Watchdog timeout: vLLM request hung for {self.WALL_TIMEOUT}s "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                logger.warning(str(last_error))

            except Exception as exc:
                last_error = exc

                if not _is_retryable_error(exc):
                    logger.error(f"Non-retryable vLLM error: {exc}")
                    raise

                logger.warning(
                    f"Retryable vLLM error (attempt {attempt + 1}/{self.MAX_RETRIES}): {exc}"
                )

            if attempt < self.MAX_RETRIES - 1:
                delay = self.BASE_RETRY_DELAY * (2 ** attempt)
                logger.info(f"Retrying vLLM in {delay:.1f}s...")
                await asyncio.sleep(delay)

        raise last_error or RuntimeError("All vLLM retries exhausted")

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
        """Generate via vLLM OpenAI-compatible /v1/chat/completions."""
        # Always use the vLLM server's loaded model; ignore Ollama-style model names
        model = self.default_model

        # Build OpenAI-format messages
        oai_messages: list[dict[str, str]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for msg in messages:
            oai_messages.append({"role": msg.role, "content": msg.content})

        # Reinforce JSON in last user message if needed
        if json_mode and oai_messages:
            last = oai_messages[-1]
            if last["role"] == "user" and "JSON" not in last["content"][:100]:
                last["content"] = last["content"] + "\n\nRespond with valid JSON only."

        payload: dict[str, Any] = {
            "model": model,
            "messages": oai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": bool(stream_callback),
        }

        # Disable thinking for qwen3.5 models
        if "qwen3" in model.lower():
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        url = f"{self.base_url}/v1/chat/completions"

        if stream_callback:
            return await self._stream_generate(url, payload, stream_callback)
        else:
            return await self._batch_generate(url, payload)

    async def _batch_generate(
        self, url: str, payload: dict[str, Any]
    ) -> LLMResponse:
        """Non-streaming generation."""
        resp = await self.http_client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            raw_response=data,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
        )

    async def _stream_generate(
        self,
        url: str,
        payload: dict[str, Any],
        stream_callback: Callable[[str], Awaitable[None]],
    ) -> LLMResponse:
        """Streaming generation via SSE."""
        collected: list[str] = []
        usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        async with self.http_client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]  # strip "data: " prefix
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    collected.append(content)
                    await stream_callback(content)
                # vLLM may include usage in the last chunk
                if "usage" in chunk:
                    u = chunk["usage"]
                    usage = {
                        "prompt_tokens": u.get("prompt_tokens", 0),
                        "completion_tokens": u.get("completion_tokens", 0),
                        "total_tokens": u.get("total_tokens", 0),
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
            logger.warning("VLLMClient was garbage-collected without calling close()")

    async def health_check(self) -> bool:
        """Check if vLLM server is available."""
        try:
            response = await self.http_client.get(
                f"{self.base_url}/v1/models", timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False
