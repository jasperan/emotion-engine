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

from app.llm.base import LLMClient, LLMMessage, LLMResponse

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
    def get_client(cls, provider: Literal["ollama", "vllm", "openai", "anthropic"] | None = None) -> LLMClient:
        """Get an LLM client for the specified provider.

        If provider is None, uses settings.llm_backend to auto-select.
        """
        if provider is None:
            from app.core.config import get_settings
            provider = get_settings().llm_backend  # type: ignore

        if provider not in cls._clients:
            if provider == "ollama":
                from app.llm.ollama import OllamaClient
                cls._clients[provider] = OllamaClient()
            elif provider == "vllm":
                from app.llm.vllm import VLLMClient
                cls._clients[provider] = VLLMClient()
            elif provider == "openai":
                from app.llm.openai_client import OpenAIClient
                cls._clients[provider] = OpenAIClient()
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
        internal retries are exhausted — effectively a last-chance attempt.

        For Ollama: tries primary, then falls back to the configured
        fallback model (e.g., smaller model on OOM).
        """
        from app.core.config import get_settings

        settings = get_settings()
        client = LLMRouter.get_client()  # auto-selects based on settings.llm_backend

        # Per-agent-type model routing
        role_model = get_model_for_role(agent_role) if agent_role else None

        # Choose primary model based on backend
        if settings.llm_backend == "openai":
            from app.llm.openai_client import get_codex_defaults
            codex = get_codex_defaults()
            primary_model = (
                model_override or role_model
                or settings.openai_model
                or codex.get("model", "gpt-4o")
            )
        elif settings.llm_backend == "vllm":
            primary_model = model_override or role_model or settings.vllm_default_model
        else:
            primary_model = model_override or role_model or settings.ollama_default_model

        try:
            return await client.generate(
                messages=messages,
                model=primary_model,
                system=system,
                json_mode=json_mode,
                temperature=temperature,
                max_tokens=max_tokens,
                stream_callback=stream_callback,
            )
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
                    return await fallback_client.generate(
                        messages=messages,
                        model=settings.ollama_fallback_model,
                        system=system,
                        json_mode=json_mode,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream_callback=stream_callback,
                    )
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
                return await client.generate(
                    messages=messages,
                    model=fallback_model,
                    system=system,
                    json_mode=json_mode,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream_callback=stream_callback,
                )
            except Exception:
                raise primary_error
