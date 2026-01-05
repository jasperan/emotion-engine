"""Rich console event renderer for CLI monitoring"""
import json
from datetime import datetime
from typing import Any

from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text
from rich import box


class EventRenderer:
    """Renders simulation events to a Rich console with live updates"""
    
    # Event type colors and icons
    EVENT_STYLES = {
        "step_completed": ("cyan", "⏱"),
        "run_started": ("green", "▶"),
        "run_paused": ("yellow", "⏸"),
        "run_stopped": ("red", "⏹"),
        "run_completed": ("green bold", "✓"),
        "agent_error": ("red bold", "✗"),
        "agent_moved": ("magenta", "→"),
        "movement_failed": ("red", "⊘"),
        "initialized": ("blue", "⚡"),
    }
    
    MESSAGE_STYLES = {
        "direct": ("blue", "✉"),
        "broadcast": ("yellow", "📢"),
        "room": ("green", "🏠"),
        "conversation": ("cyan", "💬"),
    }
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.events: list[dict[str, Any]] = []
        self.max_events = 50  # Keep last N events
        
        # Current state
        self.current_step = 0
        self.max_steps = 100
        self.world_state: dict[str, Any] = {}
        self.conversations: list[dict[str, Any]] = []
        self.agents: dict[str, dict[str, Any]] = {}
        self.conversations: list[dict[str, Any]] = []
        self.agents: dict[str, dict[str, Any]] = {}
        self.run_status = "idle"
        
        # Streaming state
        self.current_stream_agent: str | None = None
        self.current_stream_text: str = ""
        self.current_stream_token_count: int = 0
        self._stream_cycler_index: int = 0
        self._last_cycle_time: float = 0

        
    def add_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Add an event to the log"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self.events.append(event)
        
        # Trim old events
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        # Update state from events
        self._update_state(event_type, data)
    
    def add_message(self, message: dict[str, Any]) -> None:
        """Add a message event"""
        event = {
            "type": "message",
            "data": message,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self.events.append(event)
        
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def update_stream(self, agent_id: str, token: str) -> None:
        """Update the current stream with a new token"""
        # If agent changed, reset
        if self.current_stream_agent != agent_id:
            self.current_stream_agent = agent_id
            self.current_stream_text = ""
            self.current_stream_token_count = 0
            
        self.current_stream_text += token
        self.current_stream_token_count += 1
        
        # Keep text length reasonable
        if len(self.current_stream_text) > 1000:
            self.current_stream_text = "..." + self.current_stream_text[-997:]

    def _update_state(self, event_type: str, data: dict[str, Any]) -> None:
        """Update internal state from events"""
        if event_type == "step_completed":
            self.current_step = data.get("step", self.current_step)
            self.world_state = data.get("world_state", self.world_state)
            self.conversations = data.get("conversations", self.conversations)
            self.agents = self.world_state.get("agents", self.agents)
        elif event_type == "initialized":
            self.run_status = "ready"
            # Update world state and agents from initialization
            self.world_state = data.get("world_state", self.world_state)
            self.agents = self.world_state.get("agents", self.agents)
            self.conversations = data.get("conversations", [])
        elif event_type == "run_started":
            self.run_status = "running"
            self.current_step = data.get("step", 0)
        elif event_type == "run_paused":
            self.run_status = "paused"
        elif event_type == "run_stopped":
            self.run_status = "stopped"
        elif event_type == "run_completed":
            self.run_status = "completed"
        elif event_type == "connected":
            # WebSocket initial status
            status_data = data
            self.run_status = status_data.get("status", self.run_status)
            self.current_step = status_data.get("current_step", self.current_step)
            self.max_steps = status_data.get("max_steps", self.max_steps)
            self.world_state = status_data.get("world_state", self.world_state)
    
    def render_header(self) -> Panel:
        """Render the header panel with status"""
        # Status indicator
        status_colors = {
            "idle": "dim",
            "ready": "blue",
            "running": "green",
            "paused": "yellow",
            "stopped": "red",
            "completed": "green bold",
        }
        status_color = status_colors.get(self.run_status, "white")
        
        # Progress bar - use Text.from_markup to ensure tags are parsed
        progress = self.current_step / max(self.max_steps, 1)
        bar_width = 20
        filled = int(progress * bar_width)
        bar_markup = f"[green]{'█' * filled}[/green][dim]{'░' * (bar_width - filled)}[/dim]"
        
        header_text = Text()
        header_text.append("EmotionSim Monitor", style="bold cyan")
        header_text.append("  │  ", style="dim")
        header_text.append(f"Status: ", style="dim")
        header_text.append(f"{self.run_status.upper()}", style=status_color)
        header_text.append("  │  ", style="dim")
        header_text.append(f"Step: {self.current_step}/{self.max_steps}", style="white")
        header_text.append("  ", style="white")
        header_text.append_text(Text.from_markup(bar_markup))
        
        return Panel(header_text, box=box.ROUNDED, style="cyan")
    
    def render_world_state(self) -> Panel:
        """Render the world state panel"""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="dim")
        table.add_column("Value")
        
        # System Time
        table.add_row("Sys Time", datetime.now().strftime("%H:%M:%S"))
        
        # Hazard level with bar
        hazard = int(self.world_state.get("hazard_level", 0))
        hazard_bar = f"[red]{'█' * hazard}[/red][dim]{'░' * (10 - hazard)}[/dim]"
        table.add_row("Hazard", f"{hazard}/10 {hazard_bar}")
        
        # Weather
        weather = self.world_state.get("weather", "unknown")
        weather_icons = {"heavy_rain": "🌧", "storm": "⛈", "clear": "☀", "cloudy": "☁"}
        table.add_row("Weather", f"{weather_icons.get(weather, '?')} {weather}")
        
        # Time
        time_of_day = self.world_state.get("time_of_day", "unknown")
        table.add_row("Time", time_of_day)
        
        # New Fields: Temp, City, Country
        temp = self.world_state.get("temperature", "?")
        city = self.world_state.get("city", "?")
        country = self.world_state.get("country", "?")
        
        if temp != "?": table.add_row("Temp", f"{temp}")
        if city != "?": table.add_row("City", f"{city}")
        if country != "?": table.add_row("Country", f"{country}")
        
        # Agent count
        agent_count = len(self.agents)
        table.add_row("Agents", str(agent_count))
        
        return Panel(table, title="[bold]World State[/bold]", box=box.ROUNDED)
    
    def render_conversations(self) -> Panel:
        """Render active conversations panel with columns"""
        if not self.conversations:
            content = Text("No active conversations", style="dim italic")
        else:
            # Create a card for each conversation
            conv_panels = []
            
            for idx, conv in enumerate(self.conversations, 1):
                location = conv.get("location", "unknown")
                participants = conv.get("participants", [])
                count = len(participants) if isinstance(participants, list) else 0
                
                # Participants list (truncated)
                p_list = ", ".join([str(p)[:10] for p in participants])
                if len(p_list) > 30:
                    p_list = p_list[:27] + "..."
                
                # Mini panel for this conversation
                conv_text = Text()
                conv_text.append(f"loc: {location}\n", style="cyan")
                conv_text.append(f"👥 {count}: ", style="dim")
                conv_text.append(p_list, style="white")
                
                conv_panels.append(
                    Panel(conv_text, title=f"Conv #{idx}", style="dim", box=box.SQUARE)
                )
            
            # Use Columns to layout side-by-side
            content = Columns(conv_panels, expand=True, equal=True)
        
        return Panel(content, title="[bold]Active Conversations[/bold]", box=box.ROUNDED)
    
    def render_agents(self) -> Panel:
        """Render agents panel with status and intent"""
        if not self.agents:
            content = Text("No agents loaded", style="dim italic")
        else:
            table = Table(
                show_header=True, 
                box=box.SIMPLE, 
                padding=(0, 1),
                header_style="bold cyan", 
                expand=True
            )
            table.add_column("Agent", style="cyan", ratio=2)
            table.add_column("Location", style="magenta", ratio=2)
            table.add_column("State", style="green", ratio=1)
            table.add_column("Last Action", style="dim white", ratio=3)
            
            # Find last action for each agent
            last_actions = {}
            for event in self.events:
                evt_type = event.get("type")
                data = event.get("data", {})
                
                # Check different event types for action info
                agent_id = None
                action_desc = None
                
                if evt_type == "agent_moved":
                    agent_id = data.get("agent_id")
                    if agent_id:
                        to_loc = data.get("to", "?")
                        action_desc = f"Moved to {to_loc}"
                        
                elif evt_type == "message":
                    agent_id = data.get("from_agent_id", data.get("from_agent")) # from_agent is ID often
                    # Need to verify if from_agent is ID or Name. Usually ID in backend data.
                    # Looking at add_message, it takes message dict.
                    if agent_id:
                        msg_type = data.get("message_type", "direct")
                        action_desc = f"Msg ({msg_type})"
                    
                # Store if found (overwriting older ones since we iterate forward? No events are appended, so last is newest? 
                # events list is appended to. So iterating forward gives latest at end.
                if agent_id and action_desc:
                    last_actions[agent_id] = action_desc
            
            for agent_id, agent_data in list(self.agents.items())[:8]:
                name = agent_data.get("name", agent_id)[:15]
                location = agent_data.get("location", "?")[:12]
                health = agent_data.get("health", "?")
                stress = agent_data.get("stress_level", "?")
                
                # Health bar
                if isinstance(health, (int, float)):
                    health_val = int(health)
                    health_bar = f"{'●' * (health_val // 2)}{'○' * (5 - (health_val // 2))}"
                else:
                    health_bar = str(health)
                
                # Format state (Health + Stress)
                state_str = f"{health_bar} S:{stress}"
                
                # Last action
                last_act = last_actions.get(agent_id, "-")
                
                table.add_row(name, location, state_str, last_act)
            
            content = table
        
        return Panel(content, title="[bold]Agents[/bold]", box=box.ROUNDED)
    
    def render_event_log(self) -> Panel:
        """Render the event log panel"""
        if not self.events:
            content = Text("Waiting for events...", style="dim italic")
        else:
            lines = []
            for event in reversed(self.events[-15:]):  # Show last 15
                line = self._format_event(event)
                lines.append(line)
            content = Group(*lines)
        
        return Panel(content, title="[bold]Event Log[/bold]", box=box.ROUNDED)
    
    def _format_event(self, event: dict[str, Any]) -> Text:
        """Format a single event for display"""
        timestamp = event.get("timestamp", "")
        event_type = event.get("type", "unknown")
        data = event.get("data", {})
        
        text = Text()
        text.append(f"{timestamp} ", style="dim")
        
        if event_type == "message":
            # Format message event
            msg_type = data.get("message_type", "direct")
            style, icon = self.MESSAGE_STYLES.get(msg_type, ("white", "?"))
            
            from_name = data.get("from_agent_name", data.get("from_agent", "?"))
            content = data.get("content", "")
            
            # Strip context metadata suffix like [ctx:1234]
            import re
            content = re.sub(r'\s*\[ctx:\d+\]\s*$', '', content)
            content = content[:200]  # Limit length
            
            if msg_type == "conversation":
                location = data.get("location", "?")
                text.append(f"{icon} ", style=style)
                text.append(f"[{location}] ", style="cyan")
                text.append(f"{from_name}: ", style="bold")
                text.append(f'"{content}"', style="white")
            else:
                to_name = data.get("to_agent_name", data.get("to_target", "all"))
                text.append(f"{icon} ", style=style)
                text.append(f"{from_name}", style="bold")
                text.append(f" → ", style="dim")
                text.append(f"{to_name}: ", style="bold")
                text.append(f'"{content}"', style="white")
            
            # Context size
            if "metadata" in data and "context_size" in data["metadata"]:
                ctx_size = data["metadata"]["context_size"]
                text.append(f" [ctx:{ctx_size}]", style="dim italic")
        else:
            # Format system event
            style, icon = self.EVENT_STYLES.get(event_type, ("white", "•"))
            text.append(f"[{icon}] ", style=style)
            text.append(f"{event_type.upper()}", style=style)
            
            # Add relevant details
            if event_type == "step_completed":
                step = data.get("step", "?")
                text.append(f" Step {step}", style="dim")
            elif event_type == "agent_moved":
                agent_name = data.get("agent_name", data.get("agent_id", "?"))
                agent_id = data.get("agent_id", "?")
                from_loc = data.get("from", "?")
                to_loc = data.get("to", "?")
                text.append(f" {agent_name} ({agent_id[:8]}): {from_loc} → {to_loc}", style="magenta")
            elif event_type == "agent_error":
                agent_name = data.get("agent_name", data.get("agent_id", "?"))
                agent_id = data.get("agent_id", "?")
                error = data.get("error", "")[:60]
                context = data.get("context", "")
                text.append(f" {agent_name} ({agent_id[:8]}): {error}", style="red")
                if context:
                    text.append(f" [{context}]", style="dim")
            elif event_type == "movement_failed":
                agent_name = data.get("agent_name", data.get("agent_id", "?"))
                agent_id = data.get("agent_id", "?")
                from_loc = data.get("from", "?")
                to_loc = data.get("to", u"?")
                # reason = data.get("reason", "Unknown reason") # Unused in graceful mode
                
                # Graceful format
                text.append(f" {agent_name} ({agent_id[:8]}): Checked path to {to_loc}", style="dim")
                text.append(" → Unreachable. Staying at ", style="dim")
                text.append(f"{from_loc}", style="dim underline")
                text.append(".", style="dim")
            elif event_type == "location_created":
                agent_name = data.get("agent_name", data.get("agent_id", "?"))
                agent_id = data.get("agent_id", "?")
                location = data.get("location", "?")
                connected_to = data.get("connected_to", "?")
                dist = data.get("distance", 1)
                text.append(f" {agent_name} ({agent_id[:8]}): discovered '{location}' (dist: {dist}, connected to {connected_to})", style="cyan")
            elif event_type == "travel_started":
                agent_name = data.get("agent_name", data.get("agent_id", "?"))
                agent_id = data.get("agent_id", "?")
                from_loc = data.get("from", "?")
                to_loc = data.get("to", "?")
                distance = data.get("distance", "?")
                text.append(f" {agent_name} ({agent_id[:8]}): started travel {from_loc} → {to_loc} (dist: {distance})", style="magenta")
            elif event_type == "agent_travelling":
                agent_name = data.get("agent_name", data.get("agent_id", "?"))
                agent_id = data.get("agent_id", "?")
                target = data.get("target", "?")
                progress = data.get("progress", "?")
                distance = data.get("distance", "?")
                text.append(f" {agent_name} ({agent_id[:8]}): travelling to {target} ({progress}/{distance})", style="magenta dim")
            elif "step" in data:
                text.append(f" (step {data['step']})", style="dim")
        
        return text
    
        return text
    
    def render_active_stream(self) -> Panel:
        """Render the active streaming agent response in 3 columns"""
        # We need to track the last 3 active agents
        # This requires tracking state beyond just the single current stream
        # Implementation:
        # 1. Maintain a list of (agent_id, content, timestamp) tuples
        # 2. When update_stream is called, update the entry for that agent or move to top
        
        # NOTE: This method assumes self._active_streams exists. 
        # Since we can't easily add __init__ attributes in a patch without replacing the whole class,
        # we'll initialize it safely here if missing.
        if not hasattr(self, "_active_streams"):
            self._active_streams = [] # List of dicts: {id, name, text, time}

        # Sync current stream to _active_streams
        if self.current_stream_agent:
            agent_name = self.agents.get(self.current_stream_agent, {}).get("name", self.current_stream_agent)
            
            # Check if already in list
            found = False
            for s in self._active_streams:
                if s["id"] == self.current_stream_agent:
                    s["text"] = self.current_stream_text
                    s["time"] = datetime.now()
                    # Move to front
                    self._active_streams.remove(s)
                    self._active_streams.insert(0, s)
                    found = True
                    break
            
            if not found:
                self._active_streams.insert(0, {
                    "id": self.current_stream_agent,
                    "name": agent_name,
                    "text": self.current_stream_text,
                    "time": datetime.now()
                })
                
            # Keep only 3
            self._active_streams = self._active_streams[:3]

        # If no streams at all, show placeholdler
        if not self._active_streams:
             return Panel(
                Text("Waiting for agent activity...", style="dim italic"),
                title="[bold]Live Stream[/bold]",
                box=box.ROUNDED,
                height=10
            )

        # Create panels for top 3 streams
        panels = []
        for i in range(3):
            if i < len(self._active_streams):
                stream = self._active_streams[i]
                
                # Format content
                content = Text()
                content.append(f"{stream['name']}\n", style="bold cyan")
                
                # Show raw text (full JSON)
                text_preview = stream['text']
                # show last N chars if too long
                if len(text_preview) > 300:
                    text_preview = "..." + text_preview[-297:]
                    
                content.append(text_preview, style="white")
                
                # Active indicator
                if stream["id"] == self.current_stream_agent:
                     if int(datetime.now().timestamp() * 2) % 2 == 0:
                        content.append(" █", style="green")
                
                # Dim if old (> 10 seconds)
                time_diff = (datetime.now() - stream["time"]).total_seconds()
                border_style = "green" if time_diff < 5 else "dim"
                
                panels.append(
                    Panel(content, style=border_style, height=8, box=box.ROUNDED)
                )
            else:
                # Empty slot
                panels.append(Panel("", box=box.ROUNDED, height=8, style="dim"))

        return Panel(
            Columns(panels, equal=True, expand=True),
            title="[bold]Live Streams (Active & Recent)[/bold]",
            box=box.ROUNDED
        )

    def render_layout(self) -> Layout:
        """Render the full layout"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="stream", size=10),
            Layout(name="events", size=12),
        )
        
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        
        layout["left"].split_column(
            Layout(name="world", ratio=1),
            Layout(name="conversations", ratio=1),
        )
        
        layout["right"].update(self.render_agents())
        
        layout["header"].update(self.render_header())
        layout["world"].update(self.render_world_state())
        layout["conversations"].update(self.render_conversations())
        layout["conversations"].update(self.render_conversations())
        layout["stream"].update(self.render_active_stream())
        layout["events"].update(self.render_event_log())
        
        return layout


class SimpleEventLogger:
    """Simple streaming logger for non-interactive mode"""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.last_stream_agent: str | None = None
    
    def log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log an event to console"""
        # If we were streaming, print newline
        if self.last_stream_agent:
            self.console.print()
            self.last_stream_agent = None

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Color based on event type
        colors = {
            "step_completed": "cyan",
            "run_started": "green",
            "run_completed": "green bold",
            "run_paused": "yellow",
            "run_stopped": "red",
            "agent_error": "red bold",
            "agent_moved": "magenta",
            "movement_failed": "red",
            "initialized": "blue",
        }
        color = colors.get(event_type, "white")
        
        self.console.print(
            f"[dim]{timestamp}[/dim] [{color}]{event_type:20}[/{color}] {self._summarize(event_type, data)}"
        )
    
    def log_message(self, message: dict[str, Any]) -> None:
        """Log a message to console"""
        # If we were streaming, print newline
        if self.last_stream_agent:
            self.console.print()
            self.last_stream_agent = None
            
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        msg_type = message.get("message_type", "direct")
        from_name = message.get("from_agent_name", message.get("from_agent", "?"))
        content = message.get("content", "")[:200]  # Increased from 80 to show full messages
        
        type_colors = {
            "direct": "blue",
            "broadcast": "yellow",
            "room": "green",
            "conversation": "cyan",
        }
        color = type_colors.get(msg_type, "white")
        
        if msg_type == "conversation":
            location = message.get("location", "?")
            self.console.print(
                f"[dim]{timestamp}[/dim] [{color}]💬 [{location}][/{color}] "
                f"[bold]{from_name}:[/bold] \"{content}\""
            )
        else:
            to_target = message.get("to_agent_name", message.get("to_target", "all"))
            self.console.print(
                f"[dim]{timestamp}[/dim] [{color}]MSG[/{color}] "
                f"[bold]{from_name}[/bold] → {to_target}: \"{content}\""
            )
        
        # Log context size if available
        if "metadata" in message and "context_size" in message["metadata"]:
            self.console.print(f"    [dim]Context size: {message['metadata']['context_size']} chars[/dim]")
            
    def log_token(self, agent_id: str, token: str, agent_name: str | None = None) -> None:
        """Log a streaming token"""
        if self.last_stream_agent != agent_id:
            if self.last_stream_agent is not None:
                self.console.print()  # Newline after previous agent
            
            name = agent_name or agent_id
            self.console.print(f"\n[bold cyan]{name}:[/bold cyan] ", end="")
            self.last_stream_agent = agent_id
            
        self.console.print(token, end="")
    
    def _summarize(self, event_type: str, data: dict[str, Any]) -> str:
        """Create a summary string from event data"""
        if "error" in data:
            agent_name = data.get("agent_name", data.get("agent_id", "?"))
            agent_id = data.get("agent_id", "?")[:12]
            error = data['error'][:80]
            context = data.get("context", "")
            if context:
                return f"agent={agent_name} ({agent_id}) error: {error} [{context}]"
            return f"agent={agent_name} ({agent_id}) error: {error}"
        if "step" in data:
            return f"step={data['step']}"
        if "agent_id" in data:
            agent_name = data.get("agent_name", data.get("agent_id", "?"))
            agent_id = data.get("agent_id", "?")[:12]
            parts = [f"agent={agent_name} ({agent_id})"]
            if "from" in data and "to" in data:
                parts.append(f"{data['from']} → {data['to']}")
            if event_type == "travel_started":
                parts.append(f"(dist: {data.get('distance')})")
            if event_type == "agent_travelling":
                 parts.append(f"travelling to {data.get('target')} ({data.get('progress')}/{data.get('distance')})")
            if "reason" in data:
                parts.append(f"reason: {data['reason']}")
            return " ".join(parts)
        if "agent_count" in data:
            return f"agents={data['agent_count']}"
        return ""

