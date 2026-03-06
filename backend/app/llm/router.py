"""LLM Router for selecting providers"""
from typing import Literal, Callable, Awaitable

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.llm.ollama import OllamaClient


class LLMRouter:
    """Routes LLM requests to appropriate providers"""

    _clients: dict[str, LLMClient] = {}

    @classmethod
    def get_client(cls, provider: Literal["ollama", "anthropic"] = "ollama") -> LLMClient:
        """
        Get an LLM client for the specified provider.

        Args:
            provider: The LLM provider to use

        Returns:
            LLMClient instance for the provider
        """
        if provider not in cls._clients:
            if provider == "ollama":
                cls._clients[provider] = OllamaClient()
            elif provider == "anthropic":
                # Placeholder for future Claude integration
                raise NotImplementedError(
                    "Anthropic/Claude provider not yet implemented. "
                    "Use 'ollama' provider for now."
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
    ) -> LLMResponse:
        """
        Generate a response with automatic fallback to a smaller model.

        Tries the primary model first, then falls back to a smaller model
        if the primary fails and auto_fallback is enabled.

        Args:
            messages: Conversation history
            system: System prompt
            json_mode: Whether to request JSON output
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            stream_callback: Optional streaming callback
            model_override: Override the primary model

        Returns:
            LLMResponse from whichever model succeeds

        Raises:
            The original primary error if both models fail or fallback is disabled
        """
        from app.core.config import get_settings

        settings = get_settings()
        client = LLMRouter.get_client("ollama")
        primary_model = model_override or settings.ollama_default_model

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

            try:
                return await client.generate(
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

