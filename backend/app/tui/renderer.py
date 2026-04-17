"""Pi-style renderers for EmotionSim CLI.

PiStyleRenderer: Replaces EventRenderer (rich live dashboard mode).
    Uses scrolling console.print() with a Rich Live footer.

PiStyleLogger: Replaces SimpleEventLogger (simple streaming mode).
    Uses scrolling console.print() with pi-styled components.
"""

import time
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.text import Text

from app.tui.theme import PI_THEME
from app.tui.components import (
    step_border,
    event_panel,
    message_panel,
    world_state_panel,
    scene_border,
    scene_turn as render_scene_turn,
    scene_end,
    render_footer,
)


# ============================================================================
# PiStyleRenderer (replaces EventRenderer)
# ============================================================================

class PiStyleRenderer:
    """Pi-style scrolling renderer with Live footer.

    Unlike the old EventRenderer which used a fixed Rich Layout dashboard,
    this renderer prints events as they arrive (scrolling output) and maintains
    a sticky footer via Rich Live for status information.
    """

    def __init__(self, console: Console | None = None):
        self.console = console or Console(theme=PI_THEME)
        self.events: list[dict[str, Any]] = []
        self.max_events = 100

        # State
        self.current_step = 0
        self.max_steps = 100
        self.world_state: dict[str, Any] = {}
        self.agents: dict[str, dict[str, Any]] = {}
        self.conversations: list[dict[str, Any]] = []
        self.run_status = "idle"
        self.scenario_name = ""
        self.model_name = ""
        self.start_time = time.time()

        # Streaming state
        self.current_stream_agent: str | None = None
        self.current_stream_text: str = ""
        self._last_step_rendered: int = -1

    def add_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Process and render an event."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        self._update_state(event_type, data)

        # Render the event
        if event_type == "step_completed":
            step = data.get("step", self.current_step)
            # Only render world state periodically (every 5 steps or step 1)
            if step == 1 or step % 5 == 0:
                world = data.get("world_state", self.world_state)
                if world:
                    world_state_panel(self.console, world)
            step_border(self.console, step, self.max_steps)
        elif event_type == "message":
            # Render message from the data payload
            msg_data = data.get("data", data)
            message_panel(self.console, msg_data, event["timestamp"])
        elif event_type in ("scene_turn", "scene_completed"):
            pass  # Handled separately
        else:
            event_panel(self.console, event_type, data, event["timestamp"])

    def add_message(self, message: dict[str, Any]) -> None:
        """Render a message event."""
        ts = datetime.now().strftime("%H:%M:%S")
        event = {"type": "message", "data": message, "timestamp": ts}
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        message_panel(self.console, message, ts)

    def update_stream(self, agent_id: str, token: str) -> None:
        """Update streaming state (for Live refresh)."""
        if self.current_stream_agent != agent_id:
            self.current_stream_agent = agent_id
            self.current_stream_text = ""

        self.current_stream_text += token
        if len(self.current_stream_text) > 1000:
            self.current_stream_text = "..." + self.current_stream_text[-997:]

    def _update_state(self, event_type: str, data: dict[str, Any]) -> None:
        """Update internal state from events."""
        if event_type == "step_completed":
            self.current_step = data.get("step", self.current_step)
            self.world_state = data.get("world_state", self.world_state)
            self.conversations = data.get("conversations", self.conversations)
            self.agents = self.world_state.get("agents", self.agents)
        elif event_type == "initialized":
            self.run_status = "ready"
            self.world_state = data.get("world_state", self.world_state)
            self.agents = self.world_state.get("agents", self.agents)
            self.conversations = data.get("conversations", [])
        elif event_type == "run_started":
            self.run_status = "running"
            self.current_step = data.get("step", 0)
            self.start_time = time.time()
        elif event_type == "run_paused":
            self.run_status = "paused"
        elif event_type == "run_stopped":
            self.run_status = "stopped"
        elif event_type == "run_completed":
            self.run_status = "completed"
        elif event_type == "connected":
            self.run_status = data.get("status", self.run_status)
            self.current_step = data.get("current_step", self.current_step)
            self.max_steps = data.get("max_steps", self.max_steps)
            self.world_state = data.get("world_state", self.world_state)

    def get_footer(self) -> Text:
        """Build the Live footer renderable."""
        return render_footer(
            scenario=self.scenario_name,
            step=self.current_step,
            max_steps=self.max_steps,
            agent_count=len(self.agents),
            event_count=len(self.events),
            model=self.model_name,
            elapsed_seconds=time.time() - self.start_time,
            width=self.console.width,
        )

    # Backward compat: old code calls render_layout()
    def render_layout(self):
        """Return footer for Rich Live (backward compat)."""
        return self.get_footer()


# ============================================================================
# PiStyleLogger (replaces SimpleEventLogger)
# ============================================================================

class PiStyleLogger:
    """Pi-style streaming logger for non-interactive (simple) mode.

    Drop-in replacement for SimpleEventLogger with pi-styled output.
    """

    def __init__(self, console: Console | None = None):
        self.console = console or Console(theme=PI_THEME)
        self.last_stream_agent: str | None = None
        self._current_scene_location: str | None = None
        self._step_count: int = 0
        self._max_steps: int = 0

    def log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log an event with pi styling."""
        # Flush streaming state
        if self.last_stream_agent:
            self.console.print()
            self.last_stream_agent = None

        if event_type == "step_completed":
            self._step_count = data.get("step", self._step_count)
            step_border(self.console, self._step_count, self._max_steps)

            # Show world state on first step and every 5 steps
            if self._step_count == 1 or self._step_count % 5 == 0:
                ws = data.get("world_state", {})
                if ws:
                    world_state_panel(self.console, ws)
            return

        # All other events
        event_panel(self.console, event_type, data)

    def log_message(self, message: dict[str, Any]) -> None:
        """Log a message with pi styling."""
        if self.last_stream_agent:
            self.console.print()
            self.last_stream_agent = None

        message_panel(self.console, message)

    def log_scene_boundary(self, location: str, participant_names: list[str]) -> None:
        """Print scene header separator."""
        scene_border(self.console, location, participant_names)

    def log_scene_turn(self, data: dict[str, Any]) -> None:
        """Render a cinematic scene turn."""
        location = data.get("location", "")
        if location and location != self._current_scene_location:
            participants = data.get("participants", [location])
            self.log_scene_boundary(location, participants)
            self._current_scene_location = location

        render_scene_turn(self.console, data)

    def log_scene_end(self) -> None:
        """Print scene footer."""
        scene_end(self.console)
        self._current_scene_location = None

    def log_token(self, agent_id: str, token: str, agent_name: str | None = None) -> None:
        """Log a streaming token."""
        if self.last_stream_agent != agent_id:
            if self.last_stream_agent is not None:
                self.console.print()

            name = agent_name or agent_id
            self.console.print(
                f"\n[pi.stream.agent]🤖 {escape(name)}:[/pi.stream.agent] ",
                end="",
            )
            self.last_stream_agent = agent_id

        self.console.print(token, end="")
