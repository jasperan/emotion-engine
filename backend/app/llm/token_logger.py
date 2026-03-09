"""
Per-agent JSONL token logger.

Writes one JSONL file per agent under logs/agent_{sanitized_name}.jsonl,
tracking token-level events and aggregate statistics. Thread-safe via
asyncio locks for concurrent multi-agent logging.
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BACKEND_ROOT / "logs"

_instance: Optional["TokenLogger"] = None
_instance_lock = asyncio.Lock()


def _sanitize_name(name: str) -> str:
    """Convert an agent name to a safe filename component."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_").lower()


class TokenLogger:
    """Singleton JSONL token logger with per-agent files and statistics."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self._stats: dict[str, dict] = {}
        self._log_dir = LOG_DIR
        self._init_log_dir()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_log_dir(self) -> None:
        """Create the log directory and remove stale agent log files."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        for old_file in self._log_dir.glob("agent_*.jsonl"):
            try:
                old_file.unlink()
            except OSError:
                logger.warning("Failed to remove old log file: %s", old_file)

    def _log_path(self, agent_name: str) -> Path:
        return self._log_dir / f"agent_{_sanitize_name(agent_name)}.jsonl"

    async def _get_lock(self, agent_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if agent_id not in self._locks:
                self._locks[agent_id] = asyncio.Lock()
            return self._locks[agent_id]

    # ------------------------------------------------------------------
    # Internal write
    # ------------------------------------------------------------------

    async def _write(self, agent_id: str, agent_name: str, record: dict) -> None:
        lock = await self._get_lock(agent_id)
        async with lock:
            path = self._log_path(agent_name)
            try:
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                logger.exception("Failed to write token log for agent %s", agent_name)

    # ------------------------------------------------------------------
    # Public logging methods
    # ------------------------------------------------------------------

    async def log_start(
        self, agent_id: str, agent_name: str, step: int
    ) -> None:
        await self._write(agent_id, agent_name, {
            "ts": time.time(),
            "event": "start",
            "agent": agent_name,
            "agent_id": agent_id,
            "step": step,
        })

    async def log_token(
        self, agent_id: str, agent_name: str, token: str
    ) -> None:
        await self._write(agent_id, agent_name, {
            "ts": time.time(),
            "event": "token",
            "agent": agent_name,
            "t": token,
        })

    async def log_done(
        self,
        agent_id: str,
        agent_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> None:
        await self._write(agent_id, agent_name, {
            "ts": time.time(),
            "event": "done",
            "agent": agent_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms,
        })
        # Update aggregate stats
        async with self._global_lock:
            s = self._stats.setdefault(agent_id, {
                "agent_name": agent_name,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_latency_ms": 0.0,
                "call_count": 0,
            })
            s["prompt_tokens"] += prompt_tokens
            s["completion_tokens"] += completion_tokens
            s["total_latency_ms"] += latency_ms
            s["call_count"] += 1

    async def log_error(
        self, agent_id: str, agent_name: str, error: str
    ) -> None:
        await self._write(agent_id, agent_name, {
            "ts": time.time(),
            "event": "error",
            "agent": agent_name,
            "error": error,
        })

    # ------------------------------------------------------------------
    # Stats & utilities
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return a snapshot of per-agent aggregate statistics."""
        return {
            agent_id: {**s} for agent_id, s in self._stats.items()
        }

    def get_log_dir(self) -> Path:
        return self._log_dir

    def reset(self) -> None:
        """Clear all state and remove log files. Intended for testing."""
        self._stats.clear()
        self._locks.clear()
        self._init_log_dir()


async def get_token_logger() -> "TokenLogger":
    """Return the singleton TokenLogger, creating it on first call."""
    global _instance
    if _instance is None:
        async with _instance_lock:
            if _instance is None:
                _instance = TokenLogger()
    return _instance
