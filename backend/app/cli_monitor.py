"""Rich console event renderer for CLI monitoring"""
import json
from datetime import datetime
from typing import Any

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
        self.run_status = "idle"
        
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
    
    def _update_state(self, event_type: str, data: dict[str, Any]) -> None:
        """Update internal state from events"""
        if event_type == "step_completed":
            self.current_step = data.get("step", self.current_step)
            self.world_state = data.get("world_state", self.world_state)
            self.conversations = data.get("conversations", self.conversations)
            self.agents = self.world_state.get("agents", self.agents)
        elif event_type == "initialized":
            self.run_status = "ready"
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
        
        # Progress bar
        progress = self.current_step / max(self.max_steps, 1)
        bar_width = 20
        filled = int(progress * bar_width)
        bar = f"[green]{'█' * filled}[/green][dim]{'░' * (bar_width - filled)}[/dim]"
        
        header_text = Text()
        header_text.append("EmotionSim Monitor", style="bold cyan")
        header_text.append("  │  ", style="dim")
        header_text.append(f"Status: ", style="dim")
        header_text.append(f"{self.run_status.upper()}", style=status_color)
        header_text.append("  │  ", style="dim")
        header_text.append(f"Step: {self.current_step}/{self.max_steps}", style="white")
        header_text.append(f"  {bar}", style="white")
        
        return Panel(header_text, box=box.ROUNDED, style="cyan")
    
    def render_world_state(self) -> Panel:
        """Render the world state panel"""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="dim")
        table.add_column("Value")
        
        # Hazard level with bar
        hazard = self.world_state.get("hazard_level", 0)
        hazard_bar = f"[red]{'█' * hazard}[/red][dim]{'░' * (10 - hazard)}[/dim]"
        table.add_row("Hazard", f"{hazard}/10 {hazard_bar}")
        
        # Weather
        weather = self.world_state.get("weather", "unknown")
        weather_icons = {"heavy_rain": "🌧", "storm": "⛈", "clear": "☀", "cloudy": "☁"}
        table.add_row("Weather", f"{weather_icons.get(weather, '?')} {weather}")
        
        # Time
        time_of_day = self.world_state.get("time_of_day", "unknown")
        table.add_row("Time", time_of_day)
        
        # Agent count
        agent_count = len(self.agents)
        table.add_row("Agents", str(agent_count))
        
        return Panel(table, title="[bold]World State[/bold]", box=box.ROUNDED)
    
    def render_conversations(self) -> Panel:
        """Render active conversations panel"""
        if not self.conversations:
            content = Text("No active conversations", style="dim italic")
        else:
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("Location", style="cyan")
            table.add_column("Participants", style="white")
            
            for conv in self.conversations[:5]:  # Show top 5
                location = conv.get("location", "unknown")
                participants = conv.get("participants", [])
                if isinstance(participants, list):
                    names = ", ".join(str(p) for p in participants[:3])
                    if len(participants) > 3:
                        names += f" +{len(participants) - 3}"
                else:
                    names = str(participants)
                table.add_row(f"[{location}]", names)
            
            content = table
        
        return Panel(content, title="[bold]Active Conversations[/bold]", box=box.ROUNDED)
    
    def render_agents(self) -> Panel:
        """Render agents panel"""
        if not self.agents:
            content = Text("No agents loaded", style="dim italic")
        else:
            table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
            table.add_column("Agent", style="cyan")
            table.add_column("Location", style="magenta")
            table.add_column("Health", style="green")
            table.add_column("Stress", style="yellow")
            
            for agent_id, agent_data in list(self.agents.items())[:8]:
                name = agent_data.get("name", agent_id)[:15]
                location = agent_data.get("location", "?")[:10]
                health = agent_data.get("health", "?")
                stress = agent_data.get("stress_level", "?")
                
                # Health bar
                if isinstance(health, (int, float)):
                    health_bar = f"{'●' * int(health // 2)}{'○' * (5 - int(health // 2))}"
                else:
                    health_bar = str(health)
                
                table.add_row(name, location, health_bar, str(stress))
            
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
            content = data.get("content", "")[:200]  # Increased from 60 to show full messages
            
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
                to_loc = data.get("to", "?")
                reason = data.get("reason", "Unknown reason")
                text.append(f" {agent_name} ({agent_id[:8]}): {from_loc} → {to_loc} failed: {reason}", style="red")
            elif event_type == "location_created":
                agent_name = data.get("agent_name", data.get("agent_id", "?"))
                agent_id = data.get("agent_id", "?")
                location = data.get("location", "?")
                connected_to = data.get("connected_to", "?")
                text.append(f" {agent_name} ({agent_id[:8]}): discovered '{location}' (connected to {connected_to})", style="cyan")
            elif "step" in data:
                text.append(f" (step {data['step']})", style="dim")
        
        return text
    
    def render_layout(self) -> Layout:
        """Render the full layout"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="events", size=18),
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
        layout["events"].update(self.render_event_log())
        
        return layout


class SimpleEventLogger:
    """Simple streaming logger for non-interactive mode"""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    
    def log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Log an event to console"""
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
            f"[dim]{timestamp}[/dim] [{color}]{event_type:20}[/{color}] {self._summarize(data)}"
        )
    
    def log_message(self, message: dict[str, Any]) -> None:
        """Log a message to console"""
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
    
    def _summarize(self, data: dict[str, Any]) -> str:
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
            if "reason" in data:
                parts.append(f"reason: {data['reason']}")
            return " ".join(parts)
        if "agent_count" in data:
            return f"agents={data['agent_count']}"
        return ""

