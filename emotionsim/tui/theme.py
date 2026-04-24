"""Theme system ported from pi-coding-agent dark.json color palette."""

from rich.theme import Theme
from rich.style import Style


# ============================================================================
# Pi dark.json color palette
# ============================================================================

PI_COLORS = {
    "cyan": "#00d7ff",
    "blue": "#5f87ff",
    "green": "#b5bd68",
    "red": "#cc6666",
    "yellow": "#ffff00",
    "gray": "#808080",
    "dim_gray": "#666666",
    "dark_gray": "#505050",
    "accent": "#8abeb7",
    "md_heading": "#f0c674",
    "md_link": "#81a2be",
    "custom_label": "#9575cd",
    "thinking_high": "#b294bb",
    "thinking_xhigh": "#d183e8",
}

# Background colors for event panels
PI_BACKGROUNDS = {
    "pending": "#282832",
    "success": "#283228",
    "error": "#3c2828",
    "user_msg": "#343541",
    "custom_msg": "#2d2838",
}


# ============================================================================
# Rich Theme definition
# ============================================================================

PI_THEME = Theme({
    # Core UI
    "pi.border": Style(color=PI_COLORS["blue"]),
    "pi.border.accent": Style(color=PI_COLORS["cyan"]),
    "pi.accent": Style(color=PI_COLORS["accent"]),
    "pi.success": Style(color=PI_COLORS["green"]),
    "pi.error": Style(color=PI_COLORS["red"]),
    "pi.warning": Style(color=PI_COLORS["yellow"]),
    "pi.muted": Style(color=PI_COLORS["gray"]),
    "pi.dim": Style(color=PI_COLORS["dim_gray"]),
    "pi.dark": Style(color=PI_COLORS["dark_gray"]),

    # Headings & labels
    "pi.heading": Style(color=PI_COLORS["md_heading"], bold=True),
    "pi.label": Style(color=PI_COLORS["custom_label"]),

    # Agent & message styles
    "pi.agent.name": Style(color=PI_COLORS["cyan"], bold=True),
    "pi.agent.action": Style(color=PI_COLORS["accent"]),
    "pi.msg.direct": Style(color=PI_COLORS["blue"]),
    "pi.msg.broadcast": Style(color=PI_COLORS["yellow"]),
    "pi.msg.room": Style(color=PI_COLORS["green"]),
    "pi.msg.conversation": Style(color=PI_COLORS["cyan"]),

    # Event styles
    "pi.event.system": Style(color=PI_COLORS["blue"]),
    "pi.event.move": Style(color=PI_COLORS["thinking_high"]),
    "pi.event.error": Style(color=PI_COLORS["red"], bold=True),
    "pi.event.step": Style(color=PI_COLORS["cyan"]),

    # Footer
    "pi.footer.path": Style(color=PI_COLORS["dim_gray"]),
    "pi.footer.stats": Style(color=PI_COLORS["dim_gray"]),
    "pi.footer.model": Style(color=PI_COLORS["dim_gray"]),

    # Streaming
    "pi.stream.cursor": Style(color=PI_COLORS["green"], bold=True),
    "pi.stream.agent": Style(color=PI_COLORS["cyan"], bold=True),
})


# ============================================================================
# Event type -> (style_name, icon) mappings
# ============================================================================

EVENT_ICONS = {
    "step_completed": ("pi.event.step", "⏱"),
    "run_started": ("pi.success", "▶"),
    "run_paused": ("pi.warning", "⏸"),
    "run_stopped": ("pi.error", "⏹"),
    "run_completed": ("pi.success", "✓"),
    "agent_error": ("pi.event.error", "✗"),
    "agent_moved": ("pi.event.move", "→"),
    "travel_started": ("pi.event.move", "🚶"),
    "agent_travelling": ("pi.event.move", "⋯"),
    "movement_failed": ("pi.error", "⊘"),
    "location_created": ("pi.accent", "📍"),
    "location_discovered": ("pi.accent", "📍"),
    "initialized": ("pi.event.system", "⚡"),
    "connected": ("pi.event.system", "🔌"),
    "proposal_created": ("pi.accent", "📋"),
    "proposal_accepted": ("pi.success", "✅"),
    "proposal_rejected": ("pi.error", "❌"),
    "consensus_reached": ("pi.success", "🤝"),
    "plan_shared": ("pi.accent", "📝"),
    "task_delegated": ("pi.accent", "📤"),
    "conversation_outcome": ("pi.accent", "💡"),
    "scene_turn": ("pi.agent.action", "🎬"),
    "scene_completed": ("pi.muted", "🎬"),
    "resumed": ("pi.event.system", "↻"),
}

MESSAGE_ICONS = {
    "direct": ("pi.msg.direct", "✉"),
    "broadcast": ("pi.msg.broadcast", "📢"),
    "room": ("pi.msg.room", "🏠"),
    "conversation": ("pi.msg.conversation", "💬"),
}
