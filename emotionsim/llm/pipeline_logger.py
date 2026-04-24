"""Pipeline event logger for the admin viewer.

Writes timestamped events to logs/pipeline.log for the admin viewer's
pipeline panel to tail. Thread-safe via asyncio lock.
"""

import asyncio
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BACKEND_ROOT / "logs"
PIPELINE_LOG = LOG_DIR / "pipeline.log"

_lock = asyncio.Lock()


async def log_pipeline_event(event: str) -> None:
    """Append a timestamped event line to the pipeline log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {event}\n"
    async with _lock:
        try:
            with PIPELINE_LOG.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            logger.warning("Failed to write pipeline event: %s", event)


def clear_pipeline_log() -> None:
    """Remove the pipeline log file (call at simulation start)."""
    try:
        if PIPELINE_LOG.exists():
            PIPELINE_LOG.unlink()
    except OSError:
        pass
