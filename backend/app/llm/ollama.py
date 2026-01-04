"""Ollama LLM client using OpenAI-compatible API"""
import httpx
from typing import Any, Callable, Awaitable
from openai import AsyncOpenAI

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.core.config import get_settings


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
        """Generate response using Ollama"""
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

