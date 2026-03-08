"""Pi-style TUI components for EmotionSim.

All components use console.print() for scrolling output (not Rich Live layouts).
Inspired by pi-coding-agent's dynamic borders, colored panels, and footer.
"""

import os
import re
from datetime import datetime
from typing import Any

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from app.tui.theme import (
    PI_COLORS,
    PI_BACKGROUNDS,
    EVENT_ICONS,
    MESSAGE_ICONS,
)


# ============================================================================
# Dynamic Border
# ============================================================================

def dynamic_border(console: Console, label: str = "", style: str = "pi.border") -> None:
    """Print a ─ line spanning terminal width, optionally with a label.

    Like pi-coding-agent's DynamicBorder component.
    """
    width = console.width
    if label:
        # ── label ──────────────────
        prefix = f"── {label} "
        remaining = max(1, width - len(prefix))
        line = f"[{style}]{prefix}{'─' * remaining}[/{style}]"
    else:
        line = f"[{style}]{'─' * width}[/{style}]"
    console.print(line)


def step_border(console: Console, step: int, max_steps: int = 0) -> None:
    """Print a step separator border."""
    if max_steps:
        label = f"step {step}/{max_steps}"
    else:
        label = f"step {step}"
    dynamic_border(console, label, "pi.event.step")


# ============================================================================
# Startup Banner
# ============================================================================

def startup_banner(
    console: Console,
    version: str = "0.1.0",
    scenario: str | None = None,
    agents: int = 0,
    seed: int | None = None,
    model: str | None = None,
) -> None:
    """Print the pi-style startup banner with session info."""
    console.print()
    dynamic_border(console, style="pi.border.accent")

    # Title line
    title = Text()
    title.append("EmotionSim Engine", style="bold #00d7ff")
    title.append(f" v{version}", style="pi.dim")
    console.print(title)

    # Info lines
    if scenario:
        info = Text()
        info.append("Scenario: ", style="pi.muted")
        info.append(scenario, style="pi.heading")
        if agents:
            info.append(f"  |  Agents: ", style="pi.muted")
            info.append(str(agents), style="pi.accent")
        if seed is not None:
            info.append(f"  |  Seed: ", style="pi.muted")
            info.append(str(seed), style="pi.accent")
        console.print(info)

    if model:
        model_line = Text()
        model_line.append("Model: ", style="pi.muted")
        model_line.append(model, style="pi.accent")
        console.print(model_line)

    dynamic_border(console, style="pi.border.accent")
    console.print()


# ============================================================================
# Event Panel
# ============================================================================

def event_panel(
    console: Console,
    event_type: str,
    data: dict[str, Any],
    timestamp: str | None = None,
) -> None:
    """Render a system event as a bordered panel with pi styling."""
    ts = timestamp or datetime.now().strftime("%H:%M:%S")
    style_name, icon = EVENT_ICONS.get(event_type, ("pi.muted", "•"))

    # Build content text
    content = _format_event_content(event_type, data)

    # Title with icon and event type
    title = f"{icon} {event_type.upper()}"

    # Choose panel border style based on event type
    if "error" in event_type or "failed" in event_type:
        border_style = "pi.error"
    elif event_type in ("run_started", "run_completed", "consensus_reached"):
        border_style = "pi.success"
    elif event_type == "step_completed":
        # Step completions use border separators, not panels
        step_border(console, data.get("step", "?"), data.get("max_steps", 0))
        return
    else:
        border_style = style_name

    # Timestamp prefix
    header = Text()
    header.append(f"{ts} ", style="pi.dim")
    header.append(f"{icon} ", style=style_name)
    header.append(event_type.upper(), style=style_name)

    if content:
        header.append("  ", style="pi.dim")
        header.append(content)

    console.print(header)


def _format_event_content(event_type: str, data: dict[str, Any]) -> str:
    """Format event data into a readable string."""
    if event_type == "agent_moved":
        name = data.get("agent_name", data.get("agent_id", "?"))
        from_loc = data.get("from", "?")
        to_loc = data.get("to", "?")
        return f"{name}: {from_loc} → {to_loc}"

    if event_type == "travel_started":
        name = data.get("agent_name", data.get("agent_id", "?"))
        from_loc = data.get("from", "?")
        to_loc = data.get("to", "?")
        dist = data.get("distance", "?")
        return f"{name}: {from_loc} → {to_loc} (dist: {dist})"

    if event_type == "agent_travelling":
        name = data.get("agent_name", data.get("agent_id", "?"))
        target = data.get("target", "?")
        progress = data.get("progress", "?")
        dist = data.get("distance", "?")
        return f"{name}: travelling to {target} ({progress}/{dist})"

    if event_type == "agent_error":
        name = data.get("agent_name", data.get("agent_id", "?"))
        error = str(data.get("error", ""))[:80]
        ctx = data.get("context", "")
        result = f"{name}: {error}"
        if ctx:
            result += f" [{ctx}]"
        return result

    if event_type == "movement_failed":
        name = data.get("agent_name", data.get("agent_id", "?"))
        from_loc = data.get("from", "?")
        to_loc = data.get("to", "?")
        return f"{name}: {from_loc} ⊘ {to_loc} (unreachable)"

    if event_type in ("location_created", "location_discovered"):
        name = data.get("agent_name", data.get("agent_id", "?"))
        loc = data.get("location", "?")
        return f"{name}: discovered '{loc}'"

    if event_type == "initialized":
        count = data.get("agent_count", "?")
        return f"agents={count}"

    if event_type in ("run_started", "run_completed", "run_paused", "run_stopped"):
        step = data.get("step")
        if step is not None:
            return f"step {step}"
        return ""

    if event_type == "consensus_reached":
        return data.get("description", "All agents in agreement")

    # Fallback: show step if present
    step = data.get("step")
    if step is not None:
        return f"step {step}"
    return ""


# ============================================================================
# Message Panel
# ============================================================================

def message_panel(
    console: Console,
    message: dict[str, Any],
    timestamp: str | None = None,
) -> None:
    """Render an agent message as a pi-style bordered panel."""
    ts = timestamp or datetime.now().strftime("%H:%M:%S")
    msg_type = message.get("message_type", "direct")
    style_name, icon = MESSAGE_ICONS.get(msg_type, ("pi.muted", "?"))

    from_name = message.get("from_agent_name", message.get("from_agent", "?"))
    content = message.get("content", "")

    # Strip metadata suffixes
    content = re.sub(r'\s*\[ctx:\d+\]\s*$', '', content)

    # Build the panel content
    body = Text()
    body.append(f'"{content}"', style="white")

    # Build title
    if msg_type == "conversation":
        location = message.get("location", "?")
        title_text = f"{icon} {from_name} [{location}]"
    else:
        to_target = message.get("to_agent_name", message.get("to_target", "all"))
        title_text = f"{icon} {from_name} → {to_target}"

    # Render as panel with colored border
    panel = Panel(
        body,
        title=f"[{style_name}]{escape(title_text)}[/{style_name}]",
        title_align="left",
        subtitle=f"[pi.dim]{ts}[/pi.dim]",
        subtitle_align="right",
        border_style=style_name,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)


# ============================================================================
# World State Panel
# ============================================================================

def world_state_panel(console: Console, world_state: dict[str, Any]) -> None:
    """Render world state as a compact pi-style panel."""
    if not world_state:
        return

    parts = []

    # Hazard level with bar
    hazard = int(world_state.get("hazard_level", 0))
    hazard_bar = f"[pi.error]{'█' * hazard}[/pi.error][pi.dark]{'░' * (10 - hazard)}[/pi.dark]"
    parts.append(f"Hazard: {hazard}/10 {hazard_bar}")

    # Weather
    weather = world_state.get("weather", "")
    weather_icons = {
        "heavy_rain": "🌧", "storm": "⛈", "clear": "☀",
        "cloudy": "☁", "rain": "🌧", "fog": "🌫",
    }
    if weather:
        w_icon = weather_icons.get(weather, "🌍")
        parts.append(f"Weather: {w_icon} {weather}")

    # Time
    time_of_day = world_state.get("time_of_day", "")
    if time_of_day:
        parts.append(f"Time: {time_of_day}")

    # Optional fields
    temp = world_state.get("temperature")
    if temp:
        parts.append(f"Temp: {temp}")

    city = world_state.get("city")
    country = world_state.get("country")
    if city and country:
        parts.append(f"Location: {city}, {country}")
    elif city:
        parts.append(f"City: {city}")

    content = "  [pi.dim]|[/pi.dim]  ".join(parts)

    panel = Panel(
        content,
        title="[pi.heading]World State[/pi.heading]",
        title_align="left",
        border_style="pi.border",
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)


# ============================================================================
# Stream Panel (for LLM token streaming)
# ============================================================================

def stream_panel(
    console: Console,
    agent_name: str,
    text: str,
    is_active: bool = True,
) -> None:
    """Render a streaming LLM response panel."""
    body = Text()
    body.append(text, style="white")
    if is_active:
        body.append(" █", style="pi.stream.cursor")

    border = "pi.success" if is_active else "pi.dim"

    panel = Panel(
        body,
        title=f"[pi.stream.agent]🤖 {escape(agent_name)}[/pi.stream.agent]"
              + (" [pi.dim](streaming)[/pi.dim]" if is_active else ""),
        title_align="left",
        border_style=border,
        box=box.ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)


# ============================================================================
# Scene Rendering
# ============================================================================

def scene_border(console: Console, location: str, participants: list[str]) -> None:
    """Print a cinematic scene header."""
    names = ", ".join(participants)
    label = f"SCENE: {location} — {names}"
    console.print()
    dynamic_border(console, label, "pi.border.accent")


def scene_turn(console: Console, data: dict[str, Any]) -> None:
    """Render a cinematic scene turn."""
    name = escape(data.get("agent_name", "?"))
    action = data.get("action", "")
    speech = data.get("speech")
    emotion = data.get("emotion", "")

    if action:
        console.print(f"  [italic pi.dim]{escape(action)}[/italic pi.dim]")
    if speech:
        console.print(
            f"  [pi.agent.name]{name.upper():<12}[/pi.agent.name] "
            f'[white]"{escape(speech)}"[/white]  [pi.dim][{escape(emotion)}][/pi.dim]'
        )
    elif action:
        console.print(
            f"  [pi.agent.name]{name.upper():<12}[/pi.agent.name] "
            f"[pi.dim]...[/pi.dim]  [pi.dim][{escape(emotion)}][/pi.dim]"
        )


def scene_end(console: Console) -> None:
    """Print scene footer."""
    dynamic_border(console, style="pi.dim")
    console.print()


# ============================================================================
# Footer (for Rich Live sticky display)
# ============================================================================

def render_footer(
    scenario: str = "",
    step: int = 0,
    max_steps: int = 0,
    agent_count: int = 0,
    event_count: int = 0,
    model: str = "",
    elapsed_seconds: float = 0,
) -> Text:
    """Build the 2-line footer renderable for Rich Live.

    Line 1: path (branch) • scenario
    Line 2: step stats | model
    """
    # Line 1: working dir + scenario
    cwd = os.getcwd()
    home = os.environ.get("HOME", "")
    if home and cwd.startswith(home):
        cwd = f"~{cwd[len(home):]}"

    line1 = Text()
    line1.append(cwd, style="pi.dim")
    if scenario:
        line1.append(f" • {scenario}", style="pi.dim")

    # Line 2: stats left, model right
    stats_parts = []
    if max_steps:
        stats_parts.append(f"Step {step}/{max_steps}")
    else:
        stats_parts.append(f"Step {step}")

    if agent_count:
        stats_parts.append(f"Agents: {agent_count}")

    if event_count:
        stats_parts.append(f"Events: {event_count}")

    if elapsed_seconds > 0:
        mins, secs = divmod(int(elapsed_seconds), 60)
        if mins:
            stats_parts.append(f"Elapsed: {mins}m{secs}s")
        else:
            stats_parts.append(f"Elapsed: {secs}s")

    stats_left = "  ".join(stats_parts)

    line2 = Text()
    line2.append(stats_left, style="pi.dim")

    if model:
        # Right-align model name
        padding = max(2, 80 - len(stats_left) - len(model))
        line2.append(" " * padding, style="pi.dim")
        line2.append(model, style="pi.dim")

    result = Text()
    result.append_text(line1)
    result.append("\n")
    result.append_text(line2)
    return result
