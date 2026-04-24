"""OpenAI-compatible LLM client for remote endpoints (OCA / litellm / OpenAI).

Reads default configuration from ~/.codex/config.toml when available,
falling back to environment variables and Settings defaults.

Uses httpx directly (consistent with vllm.py and ollama.py) rather than
the openai SDK, so there's no extra dependency to manage.
"""
import asyncio
import json
import logging
import os
import tomllib
from pathlib import Path
from typing import Any, Callable, Awaitable

import httpx

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse
from emotionsim.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Codex config.toml parser
# ---------------------------------------------------------------------------

_codex_cache: dict[str, Any] | None = None


def _load_codex_config() -> dict[str, Any]:
    """Parse ~/.codex/config.toml once and cache the result."""
    global _codex_cache
    if _codex_cache is not None:
        return _codex_cache

    path = Path.home() / ".codex" / "config.toml"
    if not path.exists():
        _codex_cache = {}
        return _codex_cache

    try:
        with open(path, "rb") as f:
            _codex_cache = tomllib.load(f)
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        _codex_cache = {}
    return _codex_cache


def _load_codex_auth() -> str:
    """Read the API key from ~/.codex/auth.json (JWT for OCA endpoints)."""
    path = Path.home() / ".codex" / "auth.json"
    if not path.exists():
        return ""
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("OPENAI_API_KEY", "")
    except Exception as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return ""


def get_codex_defaults() -> dict[str, str]:
    """Extract base_url, model, api_key, and extra headers from codex config.

    Returns a dict with keys: base_url, model, api_key, headers_json.
    Missing keys are omitted.
    """
    cfg = _load_codex_config()
    result: dict[str, str] = {}

    # Resolve active provider
    provider_name = cfg.get("model_provider", "")
    provider = cfg.get("model_providers", {}).get(provider_name, {})

    if provider.get("base_url"):
        result["base_url"] = provider["base_url"]

    # Model: top-level "model" takes precedence (it's the active profile's model)
    if cfg.get("model"):
        result["model"] = cfg["model"]
    elif provider.get("model"):
        result["model"] = provider["model"]

    # Extra HTTP headers (e.g. {"client": "codex-cli", "client-version": "0"})
    if provider.get("http_headers"):
        result["headers_json"] = json.dumps(provider["http_headers"])

    # API key from codex auth.json (JWT for OCA, separate from env OPENAI_API_KEY)
    codex_key = _load_codex_auth()
    if codex_key:
        result["api_key"] = codex_key

    return result


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

async def _noop_callback(chunk: str) -> None:
    """No-op stream callback for when caller doesn't need streaming."""
    pass


def _is_retryable_error(exc: Exception) -> bool:
    """Check if an error is retryable (transient failures)."""
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.RemoteProtocolError, ConnectionError)):
        return True
    # Rate limits are retryable
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return True
    return False


class OpenAIClient(LLMClient):
    """LLM client for OpenAI-compatible remote endpoints.

    Works with any endpoint that speaks the /v1/chat/completions protocol:
    Oracle Code Assist (OCA), litellm proxies, OpenAI itself, etc.

    Always uses streaming mode because some endpoints (OCA/litellm) reject
    stream=false. When the caller doesn't provide a stream_callback, chunks
    are collected silently via a no-op callback.

    Configuration priority:
    1. Constructor arguments
    2. Settings (env vars / .env)
    3. ~/.codex/config.toml defaults
    """

    MAX_RETRIES = 3
    BASE_RETRY_DELAY = 2.0
    WALL_TIMEOUT = 300  # 5 minutes (remote endpoints can be slower)

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        settings = get_settings()
        codex = get_codex_defaults()

        self.base_url = (
            base_url
            or settings.openai_base_url
            or codex.get("base_url", "https://api.openai.com")
        ).rstrip("/")

        self.default_model = (
            default_model
            or settings.openai_model
            or codex.get("model", "gpt-4o")
        )

        # API key priority: constructor > codex auth.json > env var
        # codex auth.json has the OCA JWT token; the OPENAI_API_KEY env var
        # is often a separate real-OpenAI key. When a codex base_url is
        # configured (non-OpenAI), prefer the codex JWT.
        if api_key:
            self.api_key = api_key
        elif codex.get("api_key") and codex.get("base_url"):
            # Codex has both a custom endpoint and its own auth token
            self.api_key = codex["api_key"]
        else:
            self.api_key = (
                settings.openai_api_key
                or os.environ.get("OPENAI_API_KEY", "")
            )

        # Merge extra headers from codex config + constructor
        self.extra_headers: dict[str, str] = {}
        codex_headers_json = codex.get("headers_json")
        if codex_headers_json:
            try:
                self.extra_headers.update(json.loads(codex_headers_json))
            except json.JSONDecodeError:
                pass
        if extra_headers:
            self.extra_headers.update(extra_headers)

        headers = {"Authorization": f"Bearer {self.api_key}"}
        headers.update(self.extra_headers)

        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=180.0,  # remote endpoints need more time
                connect=15.0,
            ),
            headers=headers,
        )

        logger.info(
            "OpenAI client configured: base_url=%s model=%s",
            self.base_url, self.default_model,
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
        """Generate response with retry and watchdog."""
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
                        messages, model, temperature, max_tokens,
                        system, json_mode, stream_callback
                    ),
                    timeout=self.WALL_TIMEOUT,
                )
                return result

            except asyncio.TimeoutError:
                last_error = asyncio.TimeoutError(
                    f"Watchdog timeout: OpenAI request hung for {self.WALL_TIMEOUT}s "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                )
                logger.warning(str(last_error))

            except Exception as exc:
                last_error = exc

                if not _is_retryable_error(exc):
                    logger.error(f"Non-retryable OpenAI error: {exc}")
                    raise

                logger.warning(
                    f"Retryable OpenAI error (attempt {attempt + 1}/{self.MAX_RETRIES}): {exc}"
                )

            if attempt < self.MAX_RETRIES - 1:
                delay = self.BASE_RETRY_DELAY * (2 ** attempt)
                logger.info(f"Retrying OpenAI in {delay:.1f}s...")
                await asyncio.sleep(delay)

        raise last_error or RuntimeError("All OpenAI retries exhausted")

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
        """Generate via OpenAI-compatible /v1/chat/completions."""
        model = model or self.default_model

        # Build OpenAI-format messages
        oai_messages: list[dict[str, str]] = []
        if system:
            oai_messages.append({"role": "system", "content": system})
        for msg in messages:
            oai_messages.append({"role": msg.role, "content": msg.content})

        if json_mode and oai_messages:
            last = oai_messages[-1]
            if last["role"] == "user" and "JSON" not in last["content"][:100]:
                last["content"] = last["content"] + "\n\nRespond with valid JSON only."

        payload: dict[str, Any] = {
            "model": model,
            "messages": oai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Always stream: some endpoints (OCA/litellm) reject stream=false
            "stream": True,
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/v1/chat/completions"

        # When caller didn't request streaming, collect chunks silently
        callback = stream_callback or _noop_callback
        return await self._stream_generate(url, payload, callback)

    async def _stream_generate(
        self,
        url: str,
        payload: dict[str, Any],
        stream_callback: Callable[[str], Awaitable[None]],
    ) -> LLMResponse:
        """Streaming generation via SSE."""
        collected: list[str] = []
        usage: dict[str, int] = {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        }

        async with self.http_client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
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

    async def health_check(self) -> bool:
        """Check if the OpenAI-compatible endpoint is available."""
        try:
            response = await self.http_client.get(
                f"{self.base_url}/v1/models", timeout=10.0
            )
            return response.status_code == 200
        except Exception:
            return False
