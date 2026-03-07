import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    """Only max_concurrent_llm_calls requests should run at once."""
    from app.llm.ollama import get_llm_semaphore, reset_llm_semaphore
    reset_llm_semaphore()

    with patch("app.llm.ollama.get_settings") as mock_settings:
        mock_settings.return_value.max_concurrent_llm_calls = 1
        mock_settings.return_value.vram_aware_mode = False
        mock_settings.return_value.ollama_base_url = "http://localhost:11434/v1"
        mock_settings.return_value.ollama_api_key = "ollama"
        mock_settings.return_value.ollama_default_model = "test"

        sem = get_llm_semaphore()
        assert sem._value == 1

@pytest.mark.asyncio
async def test_semaphore_queues_concurrent_requests():
    """A second request waits while first holds semaphore."""
    from app.llm.ollama import get_llm_semaphore, reset_llm_semaphore
    reset_llm_semaphore()

    with patch("app.llm.ollama.get_settings") as mock_settings:
        mock_settings.return_value.max_concurrent_llm_calls = 1
        mock_settings.return_value.vram_aware_mode = False
        mock_settings.return_value.ollama_base_url = "http://localhost:11434/v1"
        mock_settings.return_value.ollama_api_key = "ollama"
        mock_settings.return_value.ollama_default_model = "test"

        sem = get_llm_semaphore()
        order = []

        async def hold_then_release():
            async with sem:
                order.append("first_in")
                await asyncio.sleep(0.05)
                order.append("first_out")

        async def wait_and_enter():
            await asyncio.sleep(0.01)
            async with sem:
                order.append("second_in")

        await asyncio.gather(hold_then_release(), wait_and_enter())
        assert order == ["first_in", "first_out", "second_in"]


@pytest.mark.asyncio
async def test_vram_check_warm_model():
    """check_model_warm returns True when model is in /api/ps response."""
    from app.llm.ollama import check_model_warm
    with patch("app.llm.ollama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"models": [{"name": "qwen3.5:9b"}]}
        ))
        result = await check_model_warm("qwen3.5:9b", "http://localhost:11434")
    assert result is True


@pytest.mark.asyncio
async def test_vram_check_cold_model():
    """check_model_warm returns False when model is NOT in /api/ps response."""
    from app.llm.ollama import check_model_warm
    with patch("app.llm.ollama.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"models": []}
        ))
        result = await check_model_warm("qwen3.5:9b", "http://localhost:11434")
    assert result is False
