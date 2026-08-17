"""LLM Router for selecting providers with per-agent-type model routing.

Supports three backends:
- **vllm**: True parallel inference via continuous batching (preferred)
- **ollama**: Single-slot inference with semaphore gating (fallback)
- **openai**: Remote OpenAI-compatible endpoint (OCA / litellm / OpenAI)

Enhanced with retry-at-fallback level: tries primary model, then fallback,
with logging of which model/attempt succeeded or failed.
"""
import logging
from typing import Literal, Callable, Awaitable

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)

# Per-agent-type model routing (Pi-inspired: different models for different agent roles)
# Maps agent role -> model override. None means use default.
_AGENT_MODEL_ROUTING: dict[str, str | None] = {
    "human": None,           # Uses primary model (complex persona reasoning)
    "environment": None,     # Will be set to fallback model
    "designer": None,        # Uses primary model (narrative guidance)
    "evaluator": None,       # Uses primary model (analysis)
    "reactive": None,        # Will be set to fallback model (quick reactions)
}


def get_model_for_role(role: str) -> str | None:
    """Get the model override for a given agent role. Returns None to use default."""
    return _AGENT_MODEL_ROUTING.get(role)


def configure_model_routing(routing: dict[str, str | None]) -> None:
    """Update model routing configuration at runtime"""
    _AGENT_MODEL_ROUTING.update(routing)


class LLMRouter:
    """Routes LLM requests to appropriate providers.

    Supports 'ollama', 'vllm', and 'openai' backends. The active backend is
    determined by settings.llm_backend.
    """

    _clients: dict[str, LLMClient] = {}

    @classmethod
    def get_client(cls, provider: Literal["ollama", "vllm", "openai", "anthropic", "stub"] | None = None) -> LLMClient:
        """Get an LLM client for the specified provider.

        If provider is None, uses settings.llm_backend. The special value
        "auto" probes vLLM → Ollama → stub and caches the result (pi/local
        compatibility: the same code runs with or without external services).
        """
        if provider is None:
            from emotionsim.core.config import get_settings
            provider = get_settings().llm_backend  # type: ignore

        if provider == "auto":
            from emotionsim.core.runtime import detect_llm_backend

            provider = detect_llm_backend()  # type: ignore

        if provider not in cls._clients:
            if provider == "ollama":
                from emotionsim.llm.ollama import OllamaClient
                from emotionsim.core.config import get_settings

                # Pick the best available Ollama model (qwen parity on machines
                # whose local model tag differs from the configured default).
                settings = get_settings()
                if settings.llm_backend == "auto":
                    from emotionsim.core.runtime import pick_ollama_model

                    model = pick_ollama_model(
                        settings.ollama_default_model, settings.ollama_base_url
                    )
                else:
                    model = settings.ollama_default_model
                cls._clients[provider] = OllamaClient(default_model=model)
            elif provider == "vllm":
                from emotionsim.llm.vllm import VLLMClient
                cls._clients[provider] = VLLMClient()
            elif provider == "openai":
                from emotionsim.llm.openai_client import OpenAIClient
                cls._clients[provider] = OpenAIClient()
            elif provider == "stub":
                # Deterministic offline client for the eval harness (no network)
                from emotionsim.llm.stub import StubLLMClient
                cls._clients[provider] = StubLLMClient()
            elif provider == "anthropic":
                raise NotImplementedError(
                    "Anthropic/Claude provider not yet implemented. "
                    "Use 'ollama', 'vllm', or 'openai' provider."
                )
            else:
                raise ValueError(f"Unknown provider: {provider}")

        return cls._clients[provider]

    @classmethod
    def reset(cls) -> None:
        """Reset cached clients (useful for testing)"""
        cls._clients.clear()

    @staticmethod
    async def generate_with_fallback(
        messages: list[LLMMessage],
        system: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
        model_override: str | None = None,
        agent_role: str | None = None,
    ) -> LLMResponse:
        """Generate a response with automatic fallback.

        Both OllamaClient and VLLMClient handle retries internally.
        This method adds model-level fallback on top.

        For vLLM: primary and fallback use the same model (single vLLM
        server), so fallback means retrying the same model after the
        internal retries are exhausted (effectively a last-chance attempt).

        For Ollama: tries primary, then falls back to the configured
        fallback model (e.g., smaller model on OOM).
        """
        from emotionsim.core.config import get_settings

        settings = get_settings()
        client = LLMRouter.get_client()  # auto-selects based on settings.llm_backend

        # Semantic response cache (opt-in via LLM_CACHE_ENABLED). On a hit the
        # cached content is replayed through the stream callback so UI token
        # streaming still renders (instant tokens).
        cache = None
        if settings.llm_cache_enabled is True:
            # Identity check: real Settings use a bool; MagicMock settings in
            # unit tests are truthy-but-not-True and must stay off the cache.
            from emotionsim.llm.cache import get_semantic_cache

            cache = get_semantic_cache()

        # Per-agent-type model routing
        role_model = get_model_for_role(agent_role) if agent_role else None

        # Choose primary model based on backend
        if settings.llm_backend == "openai":
            from emotionsim.llm.openai_client import get_codex_defaults
            codex = get_codex_defaults()
            # Ignore model_override if it looks like a local model name
            # (contains ":" for Ollama like qwen3.5:27b, or "/" for vLLM
            # like Qwen/Qwen3.5-4B). These don't exist on remote endpoints.
            effective_override = model_override
            if effective_override and (":" in effective_override or "/" in effective_override):
                logger.debug(
                    "Ignoring local model_override %r for OpenAI backend",
                    effective_override,
                )
                effective_override = None
            primary_model = (
                effective_override or role_model
                or settings.openai_model
                or codex.get("model", "gpt-4o")
            )
        elif settings.llm_backend == "vllm":
            primary_model = model_override or role_model or settings.vllm_default_model
        else:
            primary_model = model_override or role_model or settings.ollama_default_model

        if cache is not None:
            hit = await cache.get(messages, system, json_mode, primary_model)
            if hit is not None:
                if stream_callback is not None:
                    content = hit.content or ""
                    for i in range(0, len(content), 32):
                        await stream_callback(content[i : i + 32])
                return hit

        try:
            result = await client.generate(
                messages=messages,
                model=primary_model,
                system=system,
                json_mode=json_mode,
                temperature=temperature,
                max_tokens=max_tokens,
                stream_callback=stream_callback,
            )
            if cache is not None:
                await cache.put(messages, system, json_mode, primary_model, result)
            return result
        except Exception as primary_error:
            if not settings.ollama_auto_fallback:
                raise

            # For vLLM or OpenAI, try Ollama as fallback backend
            if settings.llm_backend in ("vllm", "openai"):
                logger.warning(
                    f"{settings.llm_backend} failed after retries, falling back to Ollama: {primary_error}"
                )
                try:
                    fallback_client = LLMRouter.get_client("ollama")
                    result = await fallback_client.generate(
                        messages=messages,
                        model=settings.ollama_fallback_model,
                        system=system,
                        json_mode=json_mode,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream_callback=stream_callback,
                    )
                    if cache is not None:
                        await cache.put(messages, system, json_mode, settings.ollama_fallback_model, result)
                    return result
                except Exception:
                    raise primary_error

            # For Ollama, try the fallback model
            fallback_model = settings.ollama_fallback_model
            if fallback_model == primary_model:
                raise

            logger.warning(
                f"Primary model {primary_model} failed, "
                f"falling back to {fallback_model}: {primary_error}"
            )

            try:
                result = await client.generate(
                    messages=messages,
                    model=fallback_model,
                    system=system,
                    json_mode=json_mode,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream_callback=stream_callback,
                )
                if cache is not None:
                    await cache.put(messages, system, json_mode, fallback_model, result)
                return result
            except Exception:
                raise primary_error
