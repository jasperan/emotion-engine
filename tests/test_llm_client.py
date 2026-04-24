"""Tests for LLM client abstraction"""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from emotionsim.llm.base import LLMClient, LLMMessage, LLMResponse
from emotionsim.llm.ollama import OllamaClient, reset_llm_semaphore, reset_vram_cache
from emotionsim.llm.router import LLMRouter


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
    """Test OllamaClient (native /api/chat endpoint)"""

    def test_client_initialization(self):
        """Test client initializes with defaults"""
        client = OllamaClient()

        assert client.default_model is not None
        assert "localhost" in client.native_url

    @pytest.mark.asyncio
    async def test_generate_with_mock(self):
        """Test generate method with mocked httpx response"""
        reset_llm_semaphore()
        reset_vram_cache()

        client = OllamaClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Test response"},
            "prompt_eval_count": 10,
            "eval_count": 20,
            "done": True,
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client.http_client, "post", new=AsyncMock(return_value=mock_response)), \
             patch("emotionsim.llm.ollama.is_model_warm_cached", new=AsyncMock(return_value=True)):
            messages = [LLMMessage(role="user", content="Hello")]
            response = await client.generate(messages)

        assert response.content == "Test response"
        assert response.usage["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when Ollama is available"""
        client = OllamaClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client.http_client, "get", new=AsyncMock(return_value=mock_response)):
            is_healthy = await client.health_check()

        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test that OllamaClient retries on timeout errors."""
        reset_llm_semaphore()
        reset_vram_cache()

        client = OllamaClient()
        # Speed up retries for testing
        client.MAX_RETRIES = 2
        client.BASE_RETRY_DELAY = 0.01
        client.WALL_TIMEOUT = 5

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "message": {"content": "recovered"},
            "prompt_eval_count": 5,
            "eval_count": 10,
            "done": True,
        }
        success_response.raise_for_status = MagicMock()

        call_count = 0
        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("simulated timeout")
            return success_response

        with patch.object(client.http_client, "post", side_effect=mock_post), \
             patch("emotionsim.llm.ollama.is_model_warm_cached", new=AsyncMock(return_value=True)):
            messages = [LLMMessage(role="user", content="Hello")]
            response = await client.generate(messages)

        assert response.content == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises(self):
        """Test that exhausting all retries raises the last error."""
        reset_llm_semaphore()
        reset_vram_cache()

        client = OllamaClient()
        client.MAX_RETRIES = 2
        client.BASE_RETRY_DELAY = 0.01
        client.WALL_TIMEOUT = 5

        async def mock_post(*args, **kwargs):
            raise ConnectionError("connection refused")

        with patch.object(client.http_client, "post", side_effect=mock_post), \
             patch("emotionsim.llm.ollama.is_model_warm_cached", new=AsyncMock(return_value=True)):
            messages = [LLMMessage(role="user", content="Hello")]
            with pytest.raises(ConnectionError, match="connection refused"):
                await client.generate(messages)


class TestLLMRouter:
    """Test LLMRouter"""

    def test_get_ollama_client(self):
        """Test getting Ollama client"""
        LLMRouter.reset()
        client = LLMRouter.get_client("ollama")
        assert isinstance(client, OllamaClient)

    def test_get_cached_client(self):
        """Test client caching"""
        LLMRouter.reset()
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
        client1 = LLMRouter.get_client("ollama")
        LLMRouter.reset()
        client2 = LLMRouter.get_client("ollama")
        assert client1 is not client2
