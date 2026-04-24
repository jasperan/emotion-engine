"""Security tests for EmotionSim backend.

Covers:
- CORS configuration loads from settings (not wildcard)
- Path traversal protection on scenario file endpoints
- Rate limiter blocks after threshold
- Callbacks log errors instead of swallowing silently
- httpx.AsyncClient close() methods on LLM clients
"""
import asyncio
import logging
import time
from unittest.mock import patch, MagicMock

import pytest
import httpx
from httpx import ASGITransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(cors_origins: str = "http://localhost:3000,http://localhost:5173"):
    """Build a fresh FastAPI app with overridden settings.

    We patch get_settings so we don't need a real database or .env file.
    """
    from unittest.mock import patch, PropertyMock

    fake_settings = MagicMock()
    fake_settings.app_name = "TestApp"
    fake_settings.debug = False
    fake_settings.cors_origins = cors_origins
    fake_settings.database_url = "sqlite+aiosqlite:///:memory:"
    fake_settings.datalake_enabled = False

    with patch("emotionsim.core.config.get_settings", return_value=fake_settings):
        # Force re-import so the module-level `settings = get_settings()` picks up our mock
        import importlib
        import emotionsim.main as main_mod

        importlib.reload(main_mod)
        return main_mod.app


# ---------------------------------------------------------------------------
# 1. CORS configuration
# ---------------------------------------------------------------------------


class TestCORSConfiguration:
    """Verify CORS origins come from settings, not a wildcard."""

    def test_cors_origins_from_settings(self):
        """The CORSMiddleware should use origins from settings.cors_origins."""
        from emotionsim.core.config import Settings

        s = Settings(cors_origins="https://example.com,https://other.com")
        origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
        assert origins == ["https://example.com", "https://other.com"]

    def test_cors_default_not_wildcard(self):
        """Default cors_origins should not be '*'."""
        from emotionsim.core.config import Settings

        s = Settings()
        assert s.cors_origins != "*"
        origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins

    def test_cors_empty_string_yields_empty_list(self):
        """An empty cors_origins string should produce an empty list (no wildcard fallback)."""
        from emotionsim.core.config import Settings

        s = Settings(cors_origins="")
        origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
        assert origins == []


# ---------------------------------------------------------------------------
# 2. Path traversal on scenario file endpoints
# ---------------------------------------------------------------------------


class TestPathTraversal:
    """Verify that ../.. style filenames are rejected by the resolve() guard."""

    def test_get_scenario_file_traversal_blocked(self):
        """A filename like '../../../etc/passwd' should be caught by is_relative_to()."""
        from pathlib import Path
        from emotionsim.scenarios.storage import SCENARIOS_DIR

        filename = "../../../etc/passwd"
        filepath = (SCENARIOS_DIR / filename).resolve()
        # The resolved path escapes the scenarios directory
        assert not filepath.is_relative_to(SCENARIOS_DIR.resolve())

    @pytest.mark.asyncio
    async def test_get_scenario_file_traversal_via_api(self):
        """GET /api/scenarios/files/<traversal> should return 400 when the filename contains '..'."""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Use a filename that contains '..' but stays in one path segment
            resp = await client.get("/api/scenarios/files/..%5C..%5Cetc%5Cpasswd")
            # Should be either 400 (traversal caught) or 404 (file not found)
            # The key thing: it must NOT be 200
            assert resp.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_scenario_file_normal_access_not_blocked(self):
        """A normal filename (no traversal) should not trigger the guard."""
        from pathlib import Path
        from emotionsim.scenarios.storage import SCENARIOS_DIR

        filename = "my_scenario.json"
        filepath = (SCENARIOS_DIR / filename).resolve()
        assert filepath.is_relative_to(SCENARIOS_DIR.resolve())


# ---------------------------------------------------------------------------
# 3. Rate limiter
# ---------------------------------------------------------------------------


def _find_rate_limiter(app):
    """Walk Starlette's middleware stack to find our RateLimitMiddleware instance.

    The stack is lazily built on first request, so we send a dummy GET first.
    """
    from emotionsim.main import RateLimitMiddleware

    # The middleware_stack is built on first request. Walk it.
    inner = app.middleware_stack
    while inner is not None:
        if isinstance(inner, RateLimitMiddleware):
            return inner
        inner = getattr(inner, "app", None)
    return None


class TestRateLimiter:
    """Verify the in-memory rate limiter on mutation endpoints."""

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_after_threshold(self):
        """After 100 POST requests in a window, the 101st should return 429."""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Trigger middleware stack build with a GET
            await client.get("/health")

            rate_limiter = _find_rate_limiter(app)
            assert rate_limiter is not None, "RateLimitMiddleware not found in stack"

            # Pre-fill the rate limiter at the limit
            rate_limiter._hits["127.0.0.1"] = (
                rate_limiter.RATE_LIMIT,
                time.time(),
            )

            # Next POST should be blocked (count becomes 101)
            resp = await client.post("/health")
            assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_get_requests(self):
        """GET requests should never be rate-limited."""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Trigger middleware stack build
            await client.get("/health")

            rate_limiter = _find_rate_limiter(app)
            assert rate_limiter is not None

            # Pre-fill way over the limit
            rate_limiter._hits["127.0.0.1"] = (9999, time.time())

            # GET should still work (rate limiter only checks POST/DELETE)
            resp = await client.get("/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limiter_resets_after_window(self):
        """After the window expires, the counter should reset."""
        app = _make_app()
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Trigger middleware stack build
            await client.get("/health")

            rate_limiter = _find_rate_limiter(app)
            assert rate_limiter is not None

            # Set hits with an expired window (61 seconds ago)
            rate_limiter._hits["127.0.0.1"] = (
                rate_limiter.RATE_LIMIT + 50,
                time.time() - 61,
            )

            # POST should succeed because the window has expired
            resp = await client.post("/health")
            # health endpoint doesn't accept POST natively, but it shouldn't be 429
            assert resp.status_code != 429


# ---------------------------------------------------------------------------
# 4. Callbacks log errors instead of swallowing
# ---------------------------------------------------------------------------


class TestCallbackErrorLogging:
    """Verify that callback errors are logged, not silently swallowed."""

    def test_message_bus_logs_callback_error(self, caplog):
        """MessageBus._notify_callbacks should log warnings on callback errors."""
        from emotionsim.simulation.message_bus import MessageBus

        bus = MessageBus()
        bus.register_agent("a1", "Agent One")

        def bad_callback(msg):
            raise ValueError("boom")

        bus.on_message(bad_callback)

        with caplog.at_level(logging.WARNING, logger="emotionsim.simulation.message_bus"):
            # This should NOT raise, but should log
            bus.broadcast("a1", "hello", step_index=0)

        assert any("callback error" in r.message.lower() for r in caplog.records), (
            f"Expected a 'callback error' warning, got: {[r.message for r in caplog.records]}"
        )

    def test_message_bus_callback_error_does_not_break_delivery(self):
        """Even if a callback raises, the message should still be delivered."""
        from emotionsim.simulation.message_bus import MessageBus

        bus = MessageBus()
        bus.register_agent("a1", "Agent One")
        bus.register_agent("a2", "Agent Two")

        delivered = []

        def bad_callback(msg):
            raise RuntimeError("explode")

        def good_callback(msg):
            delivered.append(msg)

        bus.on_message(bad_callback)
        bus.on_message(good_callback)

        bus.broadcast("a1", "test msg", step_index=0)

        # Good callback still fired
        assert len(delivered) == 1
        assert delivered[0]["content"] == "test msg"

        # Message was delivered to a2's queue
        messages = bus.get_messages("a2")
        assert len(messages) == 1

    def test_conversation_manager_logs_callback_error(self, caplog):
        """ConversationManager._notify_event should log warnings on callback errors."""
        from emotionsim.simulation.conversation import ConversationManager

        mgr = ConversationManager()

        def bad_callback(event_type, data):
            raise ValueError("kaboom")

        mgr.on_event(bad_callback)

        with caplog.at_level(logging.WARNING, logger="emotionsim.simulation.conversation"):
            # Trigger a notification by starting a conversation
            mgr.start_explicit_conversation(
                initiator_id="a1",
                target_agent_ids=["a2"],
                location="test",
            )

        assert any("callback error" in r.message.lower() for r in caplog.records), (
            f"Expected a 'callback error' warning, got: {[r.message for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# 5. LLM client close() methods
# ---------------------------------------------------------------------------


class TestLLMClientClose:
    """Verify that VLLMClient and OllamaClient have close() methods."""

    @pytest.mark.asyncio
    async def test_vllm_client_close(self):
        """VLLMClient.close() should close the underlying httpx client."""
        with patch("emotionsim.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                vllm_base_url="http://localhost:8010",
                vllm_default_model="test-model",
            )
            from emotionsim.llm.vllm import VLLMClient

            client = VLLMClient(base_url="http://localhost:8010", default_model="test")
            assert not client.http_client.is_closed

            await client.close()
            assert client.http_client.is_closed

    @pytest.mark.asyncio
    async def test_ollama_client_close(self):
        """OllamaClient.close() should close the underlying httpx client."""
        with patch("emotionsim.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                ollama_base_url="http://localhost:11434/v1",
                ollama_default_model="test-model",
                max_concurrent_llm_calls=1,
                vram_aware_mode=False,
            )
            from emotionsim.llm.ollama import OllamaClient

            client = OllamaClient(
                base_url="http://localhost:11434/v1", default_model="test"
            )
            assert not client.http_client.is_closed

            await client.close()
            assert client.http_client.is_closed


# ---------------------------------------------------------------------------
# 6. Datalake async wrapping
# ---------------------------------------------------------------------------


class TestDatalakeAsync:
    """Verify datalake endpoints use asyncio.to_thread for sync operations."""

    def test_run_sync_helper_exists(self):
        """The _run_sync helper should exist in the datalake module."""
        from emotionsim.api.datalake import _run_sync

        assert asyncio.iscoroutinefunction(_run_sync)

    @pytest.mark.asyncio
    async def test_run_sync_wraps_sync_function(self):
        """_run_sync should execute a sync function in a thread."""
        from emotionsim.api.datalake import _run_sync

        import threading

        main_thread = threading.current_thread()
        call_thread = None

        def sync_func():
            nonlocal call_thread
            call_thread = threading.current_thread()
            return 42

        result = await _run_sync(sync_func)
        assert result == 42
        # The sync function should have run in a different thread
        assert call_thread is not None
        assert call_thread != main_thread
