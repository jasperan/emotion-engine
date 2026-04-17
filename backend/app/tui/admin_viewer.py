#!/usr/bin/env python3
"""
EmotionSim Admin Viewer: Rich Live real-time dashboard for agent monitoring.

Single-screen layout:
  Left 2/3:  Agent token stream panes (2x2 grid, up to 10 agents)
  Right 1/3: Stats panel (top) + Pipeline log (bottom)

Tails backend/logs/agent_{name}.jsonl files and logs/pipeline.log.

Launch:
    python -m app.tui.admin_viewer                     # defaults
    python -m app.tui.admin_viewer --log-dir logs      # custom log dir
    python -m app.tui.admin_viewer --max-agents 6      # show up to 6 panes
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import termios
import time
import tty
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Theme import
# ---------------------------------------------------------------------------
try:
    from app.tui.theme import PI_COLORS
except ImportError:
    # Fallback when running standalone outside package context
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
        "thinking_high": "#b294bb",
        "thinking_xhigh": "#d183e8",
    }

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_CYAN = PI_COLORS["cyan"]
_BLUE = PI_COLORS["blue"]
_GREEN = PI_COLORS["green"]
_RED = PI_COLORS["red"]
_YELLOW = PI_COLORS["yellow"]
_GRAY = PI_COLORS["gray"]
_DIM = PI_COLORS["dim_gray"]
_DARK = PI_COLORS["dark_gray"]
_ACCENT = PI_COLORS["accent"]
_HEADING = PI_COLORS["md_heading"]
_THINKING = PI_COLORS["thinking_high"]
_THINKING_X = PI_COLORS["thinking_xhigh"]

_BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# One color per agent slot (cycles if > len)
_AGENT_COLORS = [
    _CYAN, _GREEN, _THINKING, _HEADING, _BLUE,
    _ACCENT, _THINKING_X, _YELLOW, _RED, _GRAY,
]

# Pipeline log patterns -> emoji enrichment
_LOG_PATTERNS: list[tuple[str, str, str]] = [
    (r"\bERROR\b", "red", "  "),
    (r"\bWARN(?:ING)?\b", _YELLOW, "  "),
    (r"\bstep\b", _CYAN, " "),
    (r"\bcomplete|done|finish", _GREEN, " "),
    (r"\bstart|begin|init", _ACCENT, " "),
    (r"\bagent|spawn", _THINKING, " "),
    (r"\bllm|model|ollama|vllm", _BLUE, " "),
    (r"\bconversation|message", _HEADING, " "),
]

# Max lines to keep in each buffer
_MAX_LINES = 200
_PIPELINE_MAX_LINES = 100


# ===========================================================================
# Agent pane state
# ===========================================================================
class AgentPane:
    """State for a single agent's streaming pane."""

    __slots__ = (
        "agent_id", "name", "color", "lines", "status",
        "step", "prompt_tokens", "completion_tokens", "latency_ms",
        "token_buf", "active", "error_msg", "last_update",
    )

    def __init__(self, agent_id: str, name: str, color: str) -> None:
        self.agent_id = agent_id
        self.name = name
        self.color = color
        self.lines: list[Text] = []
        self.status: str = "idle"          # idle | active | error
        self.step: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.latency_ms: float = 0.0
        self.token_buf: list[tuple[str, str]] = []
        self.active: bool = False
        self.error_msg: str = ""
        self.last_update: float = time.monotonic()

    def flush_buf(self) -> None:
        """Flush token buffer into a styled line."""
        if not self.token_buf:
            return
        line = Text()
        for token, style in self.token_buf:
            line.append(token, style=style)
        self.lines.append(line)
        if len(self.lines) > _MAX_LINES:
            self.lines = self.lines[-_MAX_LINES:]
        self.token_buf = []

    @property
    def header(self) -> str:
        tag = self.agent_id.upper()
        step_str = f" (step {self.step})" if self.step else ""
        return f"[{tag}] {self.name}{step_str}"

    @property
    def spinner(self) -> str:
        if self.status == "active":
            idx = int(time.monotonic() * 10) % len(_BRAILLE)
            return _BRAILLE[idx]
        if self.status == "error":
            return "✗"
        return "●"

    @property
    def footer_text(self) -> str:
        pt = f"{self.prompt_tokens:,}"
        ct = f"{self.completion_tokens:,}"
        total = f"{self.prompt_tokens + self.completion_tokens:,}"
        lat = f"{self.latency_ms:.0f}ms" if self.latency_ms else "--"
        return f"{pt} → {ct} = {total} | {lat}"


# ===========================================================================
# File tailers
# ===========================================================================
class JsonlTailer:
    """Incrementally reads new lines from a JSONL file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset: int = 0

    def read_new(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size <= self.offset:
            return []
        entries: list[dict] = []
        try:
            with open(self.path, "r") as f:
                f.seek(self.offset)
                raw = f.read()
                self.offset = f.tell()
        except OSError:
            return []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries


class LineTailer:
    """Incrementally reads new lines from a plain text file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset: int = 0

    def read_new(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            size = self.path.stat().st_size
        except OSError:
            return []
        if size <= self.offset:
            return []
        try:
            with open(self.path, "r") as f:
                f.seek(self.offset)
                raw = f.read()
                self.offset = f.tell()
        except OSError:
            return []
        return [ln for ln in raw.splitlines() if ln.strip()]


# ===========================================================================
# GPU status helper
# ===========================================================================
def _get_gpu_status() -> str:
    """Query nvidia-smi for GPU utilization and memory."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return "GPU: unavailable"
        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            name, util, mem_used, mem_total, temp = parts[:5]
            return f"{name} | {util}% util | {mem_used}/{mem_total} MiB | {temp}C"
        return line
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "GPU: nvidia-smi not found"


# ===========================================================================
# Render helpers
# ===========================================================================
def _colorize_token(token: str) -> tuple[str, str]:
    """Return (token, style) for JSON token coloring."""
    if any(c in token for c in "{}[]:,"):
        return token, _DIM
    if '"' in token:
        return token, _CYAN
    return token, "white"


def _enrich_pipeline_line(line: str) -> Text:
    """Add emoji + color to a pipeline log line based on patterns."""
    ts = datetime.now().strftime("%H:%M:%S")
    t = Text()
    t.append(f"{ts} ", style=_DIM)

    for pattern, color, emoji in _LOG_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            t.append(f"{emoji} ", style=color)
            t.append(line, style=color)
            return t

    # Default style
    t.append(line, style=_GRAY)
    return t


def _render_agent_pane(pane: AgentPane, height: int) -> Panel:
    """Render a single agent pane as a Rich Panel."""
    # Status icon
    spinner = pane.spinner
    status_color = _GREEN if pane.status == "active" else (
        _RED if pane.status == "error" else _DIM
    )

    title = Text()
    title.append(f" {spinner} ", style=f"bold {status_color}")
    title.append(pane.header, style=f"bold {pane.color}")

    # Body: last N visible lines
    visible_count = max(height - 4, 2)
    visible_lines = pane.lines[-visible_count:]

    body = Text()
    for i, ln in enumerate(visible_lines):
        if i > 0:
            body.append("\n")
        body.append_text(ln)

    if pane.error_msg:
        body.append(f"\n✗ {pane.error_msg}", style=f"bold {_RED}")

    # Footer with token stats
    subtitle = Text()
    subtitle.append(f" {pane.footer_text} ", style=_DIM)

    return Panel(
        body,
        title=title,
        subtitle=subtitle,
        border_style=pane.color if pane.active else _DARK,
        padding=(0, 1),
    )


def _render_stats_panel(
    panes: dict[str, AgentPane],
    start_time: float,
    current_step: int,
    max_steps: int,
    backend: str,
    gpu_status: str,
    backend_detail: str = "",
) -> Panel:
    """Render the stats panel."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {_ACCENT}", justify="right")
    table.add_column(style="white")

    active = sum(1 for p in panes.values() if p.active)
    total_agents = len(panes)
    total_tokens = sum(p.prompt_tokens + p.completion_tokens for p in panes.values())
    elapsed = time.monotonic() - start_time
    elapsed_str = time.strftime("%H:%M:%S", time.gmtime(elapsed))
    tps = total_tokens / elapsed if elapsed > 0 else 0.0

    table.add_row("Workers", f"{active}/{total_agents} active")
    table.add_row("Tokens", f"{total_tokens:,}")
    table.add_row("Step", f"{current_step}/{max_steps}" if max_steps else str(current_step))
    table.add_row("Elapsed", elapsed_str)
    table.add_row("Throughput", f"{tps:,.1f} tok/s")

    # Backend with color-coded status
    backend_text = Text()
    if "vLLM" in backend or "vllm" in backend:
        backend_text.append(backend, style=f"bold {_GREEN}")
        backend_text.append(" (parallel)", style=_DIM)
    elif "Ollama" in backend:
        backend_text.append(backend, style=f"bold {_YELLOW}")
        backend_text.append(" (sequential)", style=_DIM)
    elif "No backend" in backend:
        backend_text.append(backend, style=f"bold {_RED}")
    else:
        backend_text.append(backend, style="white")
    table.add_row("Backend", backend_text)

    if backend_detail:
        table.add_row("Model", backend_detail)

    table.add_row("", "")
    # GPU info (may be multi-line)
    for i, line in enumerate(gpu_status.split("|")):
        label = "GPU" if i == 0 else ""
        table.add_row(label, line.strip())

    return Panel(
        table,
        title=Text(" Stats ", style=f"bold {_HEADING}"),
        border_style=_BLUE,
        padding=(1, 1),
    )


def _render_pipeline_panel(lines: list[Text]) -> Panel:
    """Render the pipeline log panel."""
    body = Text()
    for i, ln in enumerate(lines):
        if i > 0:
            body.append("\n")
        body.append_text(ln)

    return Panel(
        body,
        title=Text(" Pipeline Log ", style=f"bold {_ACCENT}"),
        border_style=_BLUE,
        padding=(0, 1),
    )


# ===========================================================================
# Main dashboard
# ===========================================================================
class AdminViewer:
    """Rich Live dashboard that polls JSONL agent logs."""

    def __init__(
        self,
        log_dir: str = "logs",
        max_agents: int = 10,
        max_steps: int = 0,
        backend: str = "auto",
    ) -> None:
        self.log_dir = Path(log_dir)
        self.max_agents = max_agents
        self.max_steps = max_steps
        self.backend = backend  # "auto" triggers live detection
        self._backend_detail: str = ""  # model/url detail line

        # Agent panes keyed by sanitized agent name
        self.panes: dict[str, AgentPane] = {}
        self.tailers: dict[str, JsonlTailer] = {}

        # Pipeline log
        self.pipeline_tailer = LineTailer(self.log_dir / "pipeline.log")
        self.pipeline_lines: list[Text] = []

        # Timers
        self.start_time = time.monotonic()
        self._last_stats_poll: float = 0.0
        self._last_token_poll: float = 0.0
        self._gpu_status: str = "GPU: querying..."
        self._current_step: int = 0

        # Controls
        self.follow: bool = True
        self.running: bool = True

        # Color assignment counter
        self._color_idx: int = 0

    # -- Discovery ----------------------------------------------------------

    def _discover_agents(self) -> None:
        """Scan log_dir for new agent_*.jsonl files."""
        if not self.log_dir.exists():
            return
        for path in sorted(self.log_dir.glob("agent_*.jsonl")):
            stem = path.stem  # e.g. agent_bob
            if stem in self.tailers:
                continue
            if len(self.panes) >= self.max_agents:
                break
            agent_name = stem.replace("agent_", "").replace("_", " ")
            agent_id = f"A{len(self.panes) + 1}"
            color = _AGENT_COLORS[self._color_idx % len(_AGENT_COLORS)]
            self._color_idx += 1
            self.panes[stem] = AgentPane(agent_id, agent_name, color)
            self.tailers[stem] = JsonlTailer(path)

    # -- Polling ------------------------------------------------------------

    def _poll_tokens(self) -> None:
        """Read new JSONL entries for each agent (200ms cadence)."""
        now = time.monotonic()
        if now - self._last_token_poll < 0.2:
            return
        self._last_token_poll = now

        self._discover_agents()

        for stem, tailer in self.tailers.items():
            pane = self.panes[stem]
            entries = tailer.read_new()
            for entry in entries:
                event = entry.get("event", "")
                pane.last_update = now

                if event == "start":
                    pane.flush_buf()
                    pane.active = True
                    pane.status = "active"
                    pane.step = entry.get("step", pane.step + 1)
                    pane.error_msg = ""
                    if pane.step > self._current_step:
                        self._current_step = pane.step
                    label = entry.get("label", pane.name)
                    pane.lines.append(
                        Text(f"── step {pane.step}: {label} ──", style=f"bold {pane.color}")
                    )

                elif event == "token":
                    token = entry.get("t", "")
                    if token:
                        tok_text, tok_style = _colorize_token(token)
                        pane.token_buf.append((tok_text, tok_style))
                        pane.completion_tokens += 1
                        # Flush on newlines or buffer overflow
                        buf_len = sum(len(t) for t, _ in pane.token_buf)
                        if "\n" in token or buf_len > 120:
                            pane.flush_buf()

                elif event == "done":
                    pane.flush_buf()
                    pane.active = False
                    pane.status = "idle"
                    pt = entry.get("prompt_tokens", 0)
                    ct = entry.get("completion_tokens", 0)
                    lat = entry.get("latency_ms", 0)
                    pane.prompt_tokens += pt
                    pane.completion_tokens += ct
                    pane.latency_ms = lat
                    total = pt + ct
                    pane.lines.append(Text(
                        f"  Done  {pt:,} prompt + {ct:,} completion = {total:,} | {lat:.0f}ms",
                        style=f"bold {_GREEN}",
                    ))

                elif event == "error":
                    pane.flush_buf()
                    pane.active = False
                    pane.status = "error"
                    msg = entry.get("msg", entry.get("error", "unknown"))
                    pane.error_msg = msg
                    pane.lines.append(Text(f"  Error: {msg}", style=f"bold {_RED}"))

            # Flush any remaining buffer
            if pane.token_buf:
                pane.flush_buf()

    def _poll_stats(self) -> None:
        """Poll GPU, backend status, and pipeline log (2s cadence)."""
        now = time.monotonic()
        if now - self._last_stats_poll < 2.0:
            return
        self._last_stats_poll = now

        # GPU
        self._gpu_status = _get_gpu_status()

        # Backend auto-detection (runs synchronously, fast HTTP with 1s timeout)
        if self.backend == "auto":
            self._detect_backend()

        # Pipeline log
        new_lines = self.pipeline_tailer.read_new()
        for line in new_lines:
            self.pipeline_lines.append(_enrich_pipeline_line(line))
        if len(self.pipeline_lines) > _PIPELINE_MAX_LINES:
            self.pipeline_lines = self.pipeline_lines[-_PIPELINE_MAX_LINES:]

    def _detect_backend(self) -> None:
        """Synchronously probe vLLM and Ollama to determine active backend."""
        import urllib.request
        import urllib.error

        # Try vLLM first (default port 8010)
        for port in (8010, 8000):
            try:
                req = urllib.request.Request(
                    f"http://localhost:{port}/v1/models",
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        import json as _json
                        data = _json.loads(resp.read())
                        models = [m["id"] for m in data.get("data", [])]
                        if models:
                            self.backend = f"vLLM :{port}"
                            self._backend_detail = ", ".join(models)
                            return
            except Exception:
                pass

        # Try Ollama
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(resp.read())
                    models = [m["name"] for m in data.get("models", [])]
                    if models:
                        self.backend = "Ollama"
                        self._backend_detail = ", ".join(models[:3])
                        return
        except Exception:
            pass

        self.backend = "No backend"
        self._backend_detail = ""

    # -- Layout builder -----------------------------------------------------

    def _build_layout(self, console: Console) -> Layout:
        """Build the full dashboard layout."""
        term_height = console.height or 40

        root = Layout(name="root")

        # Title bar
        title_bar = self._build_title_bar()
        root.split_column(
            Layout(title_bar, name="header", size=3),
            Layout(name="body"),
        )

        # Body: left (agents) + right (stats + pipeline)
        root["body"].split_row(
            Layout(name="agents", ratio=2),
            Layout(name="sidebar", ratio=1),
        )

        # Sidebar: stats top, pipeline bottom
        root["sidebar"].split_column(
            Layout(name="stats", ratio=2),
            Layout(name="pipeline", ratio=3),
        )

        # Build agent grid
        pane_list = list(self.panes.values())
        if not pane_list:
            root["agents"].update(Panel(
                Text("Waiting for agent logs...\n\n"
                     f"Watching: {self.log_dir.resolve()}/agent_*.jsonl",
                     style=_DIM),
                title=Text(" Agents ", style=f"bold {_CYAN}"),
                border_style=_DARK,
            ))
        else:
            agent_height = max((term_height - 5) // max(math.ceil(len(pane_list) / 2), 1), 8)
            self._build_agent_grid(root["agents"], pane_list, agent_height)

        # Stats panel
        root["stats"].update(_render_stats_panel(
            self.panes, self.start_time,
            self._current_step, self.max_steps,
            self.backend, self._gpu_status,
            backend_detail=self._backend_detail,
        ))

        # Pipeline panel: show last lines that fit
        pipeline_visible = self.pipeline_lines[-(term_height // 3):]
        root["pipeline"].update(_render_pipeline_panel(pipeline_visible))

        return root

    def _build_title_bar(self) -> Panel:
        """Build the top title/status bar."""
        active = sum(1 for p in self.panes.values() if p.active)
        total = len(self.panes)
        total_tokens = sum(p.prompt_tokens + p.completion_tokens for p in self.panes.values())
        elapsed = time.monotonic() - self.start_time
        tps = total_tokens / elapsed if elapsed > 0 else 0.0

        # Spinner
        if active > 0:
            idx = int(time.monotonic() * 10) % len(_BRAILLE)
            spin = _BRAILLE[idx]
        else:
            spin = "●"

        t = Text()
        t.append(f" {spin} ", style=f"bold {_CYAN}")
        t.append("EmotionSim Admin Viewer", style=f"bold {_CYAN}")
        t.append(f"   Workers: {active}/{total}", style="white")
        t.append(f"   Tokens: {total_tokens:,}", style="white")
        t.append(f"   {tps:,.1f} tok/s", style=_ACCENT)

        # Backend indicator in title bar
        if "vLLM" in self.backend or "vllm" in self.backend:
            t.append(f"   {self.backend}", style=f"bold {_GREEN}")
        elif "Ollama" in self.backend:
            t.append(f"   {self.backend}", style=f"bold {_YELLOW}")
        elif "No backend" in self.backend:
            t.append(f"   {self.backend}", style=f"bold {_RED}")

        follow_str = "FOLLOW" if self.follow else "follow off"
        follow_style = f"bold {_GREEN}" if self.follow else _DIM
        t.append(f"   [{follow_str}]", style=follow_style)

        ts = datetime.now().strftime("%H:%M:%S")
        t.append(f"   {ts}", style=_DIM)
        t.append("   q=quit  f=follow", style=_DARK)

        return Panel(t, style=_DARK, padding=(0, 0))

    def _build_agent_grid(self, layout: Layout, pane_list: list[AgentPane], pane_height: int) -> None:
        """Arrange agent panes in a 2-column grid."""
        cols = 2
        rows = math.ceil(len(pane_list) / cols)

        row_layouts: list[Layout] = []
        for r in range(rows):
            row_layout = Layout(name=f"row_{r}")
            col_layouts: list[Layout] = []
            for c in range(cols):
                idx = r * cols + c
                name = f"pane_{idx}"
                if idx < len(pane_list):
                    pane_panel = _render_agent_pane(pane_list[idx], pane_height)
                    col_layouts.append(Layout(pane_panel, name=name))
                else:
                    col_layouts.append(Layout(
                        Panel("", border_style=_DARK, padding=(0, 1)),
                        name=name,
                    ))
            row_layout.split_row(*col_layouts)
            row_layouts.append(row_layout)

        if row_layouts:
            layout.split_column(*row_layouts)

    # -- Input handling -----------------------------------------------------

    def _check_input(self) -> None:
        """Non-blocking stdin check for q/f keys."""
        import select
        if select.select([sys.stdin], [], [], 0.0)[0]:
            ch = sys.stdin.read(1)
            if ch == "q":
                self.running = False
            elif ch == "f":
                self.follow = not self.follow

    # -- Main loop ----------------------------------------------------------

    def run(self) -> None:
        """Run the live dashboard until 'q' is pressed."""
        console = Console()

        # Set terminal to raw mode for key detection
        old_settings = None
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except (termios.error, ValueError, OSError):
            old_settings = None

        try:
            with Live(
                console=console,
                refresh_per_second=5,
                screen=True,
            ) as live:
                while self.running:
                    self._poll_tokens()
                    self._poll_stats()
                    self._check_input()

                    layout = self._build_layout(console)
                    live.update(layout)

                    # ~200ms sleep between frames (Live handles refresh rate)
                    time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            # Restore terminal
            if old_settings is not None:
                try:
                    fd = sys.stdin.fileno()
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except (termios.error, ValueError, OSError):
                    pass


# ===========================================================================
# CLI entry point
# ===========================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="EmotionSim Admin Viewer - Rich Live real-time agent dashboard",
    )
    parser.add_argument(
        "--log-dir", type=str, default="logs",
        help="Directory containing agent JSONL logs (default: logs)",
    )
    parser.add_argument(
        "--max-agents", type=int, default=10,
        help="Maximum number of agent panes to display (default: 10)",
    )
    parser.add_argument(
        "--max-steps", type=int, default=0,
        help="Total simulation steps (for progress display, 0=unknown)",
    )
    parser.add_argument(
        "--backend", type=str, default="auto",
        help="LLM backend name: auto (detect), vLLM, Ollama (default: auto)",
    )
    parser.add_argument(
        "--force-vllm", type=str, nargs="?", const="http://localhost:8010", default=None,
        metavar="URL",
        help="Force vLLM backend display, optionally with URL (default: http://localhost:8010)",
    )
    args = parser.parse_args()

    backend = args.backend
    if args.force_vllm:
        backend = f"vLLM (forced)"

    viewer = AdminViewer(
        log_dir=args.log_dir,
        max_agents=args.max_agents,
        max_steps=args.max_steps,
        backend=backend,
    )
    if args.force_vllm:
        viewer._backend_detail = args.force_vllm
    viewer.run()


if __name__ == "__main__":
    main()
