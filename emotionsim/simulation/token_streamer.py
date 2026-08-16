"""TokenStreamer: batched WebSocket token streaming for agent ticks (Step 7).

Extracts the token buffering/flushing closure from the engine monolith so
``_tick_single_agent`` stays focused on orchestration. Behavior is identical:
tokens are logged per-agent, forwarded to an optional stream callback, and
broadcast to WebSocket clients in 50ms batches.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable


class TokenStreamer:
    """Buffers and flushes streamed LLM tokens for one agent tick."""

    FLUSH_INTERVAL = 0.05  # 50ms batching to avoid flooding WebSocket

    def __init__(self, on_event: Callable[[str, dict[str, Any]], None]) -> None:
        self.on_event = on_event
        self._buffer: list[str] = []
        self._last_flush = time.time()

    async def _flush(self, agent_id: str, agent_name: str, step: int) -> None:
        if self._buffer:
            chunk = "".join(self._buffer)
            self._buffer.clear()
            self.on_event("token_stream", {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "tokens": chunk,
                "step": step,
            })

    def make_callback(
        self,
        agent_id: str,
        agent_name: str,
        step: int,
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
        token_logger: Any | None = None,
        counter: list[int] | None = None,
    ) -> Callable[[str], Awaitable[None]]:
        """Build the per-tick token callback.

        ``counter`` is a mutable 1-list used to accumulate a char count for
        the tick (the engine's token budget accounting).
        """
        streamer = self
        local_step = step

        async def _cb(token: str, _aid: str = agent_id, _aname: str = agent_name) -> None:
            if stream_callback:
                await stream_callback(_aid, token)
            if token_logger is not None:
                await token_logger.log_token(_aid, _aname, token)
            if counter is not None:
                counter[0] += len(token)
            # Buffer tokens for batched WebSocket broadcast
            streamer._buffer.append(token)
            now = time.time()
            if now - streamer._last_flush >= streamer.FLUSH_INTERVAL:
                streamer._last_flush = now
                await streamer._flush(_aid, _aname, local_step)

        return _cb

    async def flush(self, agent_id: str, agent_name: str, step: int) -> None:
        """Flush any remaining buffered tokens."""
        await self._flush(agent_id, agent_name, step)
