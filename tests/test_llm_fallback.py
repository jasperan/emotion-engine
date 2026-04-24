"""Tests for LLM Router fallback functionality"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from emotionsim.llm.base import LLMMessage, LLMResponse
from emotionsim.llm.router import LLMRouter


@pytest.fixture
def sample_messages():
    return [LLMMessage(role="user", content="Hello")]


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.ollama_default_model = "qwen3.5:27b"
    settings.ollama_fallback_model = "qwen3.5:4b"
    settings.ollama_timeout = 60
    settings.ollama_auto_fallback = True
    return settings


@pytest.fixture
def success_response():
    return LLMResponse(content="test response", raw_response={}, usage={})


@pytest.mark.asyncio
async def test_primary_model_success(sample_messages, mock_settings, success_response):
    """Primary model succeeds on first try, generate called once."""
    mock_client = AsyncMock()
    mock_client.generate.return_value = success_response

    with patch("emotionsim.core.config.get_settings", return_value=mock_settings), \
         patch.object(LLMRouter, "get_client", return_value=mock_client):
        result = await LLMRouter.generate_with_fallback(messages=sample_messages)

    assert result == success_response
    mock_client.generate.assert_called_once()
    # Verify primary model was used
    call_kwargs = mock_client.generate.call_args
    assert call_kwargs.kwargs.get("model") == "qwen3.5:27b" or \
           call_kwargs[1].get("model") == "qwen3.5:27b"


@pytest.mark.asyncio
async def test_fallback_on_timeout(sample_messages, mock_settings, success_response):
    """Primary raises TimeoutError, fallback model succeeds."""
    mock_client = AsyncMock()
    mock_client.generate.side_effect = [TimeoutError("primary timed out"), success_response]

    with patch("emotionsim.core.config.get_settings", return_value=mock_settings), \
         patch.object(LLMRouter, "get_client", return_value=mock_client):
        result = await LLMRouter.generate_with_fallback(messages=sample_messages)

    assert result == success_response
    assert mock_client.generate.call_count == 2
    # Second call should use fallback model
    second_call = mock_client.generate.call_args_list[1]
    assert second_call.kwargs.get("model") == "qwen3.5:4b" or \
           second_call[1].get("model") == "qwen3.5:4b"


@pytest.mark.asyncio
async def test_fallback_disabled(sample_messages, mock_settings):
    """auto_fallback=False, timeout raises immediately without trying fallback."""
    mock_settings.ollama_auto_fallback = False
    mock_client = AsyncMock()
    mock_client.generate.side_effect = TimeoutError("primary timed out")

    with patch("emotionsim.core.config.get_settings", return_value=mock_settings), \
         patch.object(LLMRouter, "get_client", return_value=mock_client):
        with pytest.raises(TimeoutError, match="primary timed out"):
            await LLMRouter.generate_with_fallback(messages=sample_messages)

    mock_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_both_models_fail_raises(sample_messages, mock_settings):
    """Both primary and fallback fail; raises the original primary error."""
    primary_error = TimeoutError("primary timed out")
    fallback_error = ConnectionError("fallback also failed")

    mock_client = AsyncMock()
    mock_client.generate.side_effect = [primary_error, fallback_error]

    with patch("emotionsim.core.config.get_settings", return_value=mock_settings), \
         patch.object(LLMRouter, "get_client", return_value=mock_client):
        with pytest.raises(TimeoutError, match="primary timed out"):
            await LLMRouter.generate_with_fallback(messages=sample_messages)

    assert mock_client.generate.call_count == 2
