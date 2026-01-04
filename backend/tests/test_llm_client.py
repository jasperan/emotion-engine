"""Tests for LLM client abstraction"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.llm.ollama import OllamaClient
from app.llm.router import LLMRouter


class TestLLMResponse:
    """Test LLMResponse model"""
    
    def test_create_response(self):
        """Test creating an LLM response"""
        response = LLMResponse(
            content="Hello, world!",
            raw_response={"test": "data"},
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )
        
        assert response.content == "Hello, world!"
        assert response.usage["total_tokens"] == 15


class TestLLMMessage:
    """Test LLMMessage model"""
    
    def test_create_message(self):
        """Test creating an LLM message"""
        msg = LLMMessage(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestOllamaClient:
    """Test OllamaClient"""
    
    def test_client_initialization(self):
        """Test client initializes with defaults"""
        with patch("app.llm.ollama.AsyncOpenAI"):
            client = OllamaClient()
            
            assert client.default_model is not None
            assert "localhost" in client.base_url
    
    @pytest.mark.asyncio
    async def test_generate_with_mock(self):
        """Test generate method with mocked OpenAI client"""
        with patch("app.llm.ollama.AsyncOpenAI") as mock_openai:
            # Setup mock
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 20
            mock_response.usage.total_tokens = 30
            mock_response.model_dump.return_value = {}
            
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client
            
            client = OllamaClient()
            
            messages = [LLMMessage(role="user", content="Hello")]
            response = await client.generate(messages)
            
            assert response.content == "Test response"
            assert response.usage["total_tokens"] == 30
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when Ollama is available"""
        with patch("app.llm.ollama.AsyncOpenAI"):
            with patch("app.llm.ollama.httpx.AsyncClient") as mock_httpx:
                mock_response = MagicMock()
                mock_response.status_code = 200
                
                mock_client = MagicMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.get = AsyncMock(return_value=mock_response)
                
                mock_httpx.return_value = mock_client
                
                client = OllamaClient()
                is_healthy = await client.health_check()
                
                assert is_healthy is True


class TestLLMRouter:
    """Test LLMRouter"""
    
    def test_get_ollama_client(self):
        """Test getting Ollama client"""
        LLMRouter.reset()
        
        with patch("app.llm.ollama.AsyncOpenAI"):
            client = LLMRouter.get_client("ollama")
            
            assert isinstance(client, OllamaClient)
    
    def test_get_cached_client(self):
        """Test client caching"""
        LLMRouter.reset()
        
        with patch("app.llm.ollama.AsyncOpenAI"):
            client1 = LLMRouter.get_client("ollama")
            client2 = LLMRouter.get_client("ollama")
            
            assert client1 is client2
    
    def test_anthropic_not_implemented(self):
        """Test Anthropic provider raises NotImplementedError"""
        LLMRouter.reset()
        
        with pytest.raises(NotImplementedError):
            LLMRouter.get_client("anthropic")
    
    def test_unknown_provider(self):
        """Test unknown provider raises ValueError"""
        LLMRouter.reset()
        
        with pytest.raises(ValueError):
            LLMRouter.get_client("unknown")  # type: ignore
    
    def test_reset(self):
        """Test resetting cached clients"""
        LLMRouter.reset()
        
        with patch("app.llm.ollama.AsyncOpenAI"):
            client1 = LLMRouter.get_client("ollama")
            LLMRouter.reset()
            client2 = LLMRouter.get_client("ollama")
            
            assert client1 is not client2

