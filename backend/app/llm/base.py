"""LLM client base abstraction"""
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class LLMMessage(BaseModel):
    """Message format for LLM interactions"""
    role: str  # "system", "user", "assistant"
    content: str


class LLMResponse(BaseModel):
    """Structured response from LLM"""
    content: str
    raw_response: dict[str, Any] | None = None
    usage: dict[str, int] | None = None


class LLMClient(ABC):
    """Abstract base class for LLM clients"""
    
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system: str | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: Conversation history
            model: Model identifier (uses default if None)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            system: System prompt (prepended to messages)
            json_mode: Whether to request JSON output
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is available"""
        pass

