"""LLM Router for selecting providers"""
from typing import Literal

from app.llm.base import LLMClient
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

