import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    """Only max_concurrent_llm_calls requests should run at once."""
    from app.llm.ollama import get_llm_semaphore, reset_llm_semaphore
    reset_llm_semaphore()

    with patch("app.core.config.get_settings") as mock_settings:
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

    with patch("app.core.config.get_settings") as mock_settings:
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
