"""Backward compatibility shim - use app.tui.renderer instead.

This module re-exports the new pi-style renderers under the old names
so any existing code that imports EventRenderer or SimpleEventLogger
continues to work.
"""

from app.tui.renderer import PiStyleRenderer as EventRenderer
from app.tui.renderer import PiStyleLogger as SimpleEventLogger

__all__ = ["EventRenderer", "SimpleEventLogger"]
