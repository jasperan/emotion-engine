#!/usr/bin/env python3
"""EmotionSim CLI - Monitor and run simulations from the command line"""
import asyncio
import json
import signal
import sys
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

from app.cli_monitor import EventRenderer, SimpleEventLogger


console = Console()


# ============================================================================
# CLI Group
# ============================================================================

@click.group()
@click.version_option(version="0.1.0", prog_name="emotionsim")
def cli():
    """EmotionSim - Multi-Agent Simulation System
    
    Monitor simulations in real-time or run them directly from the CLI.
    """
    pass


# ============================================================================
# Run Command (Standalone Mode)
# ============================================================================

@cli.command()
@click.option("--scenario", "-s", required=True, help="Scenario name or ID to run")
@click.option("--max-steps", "-m", type=int, default=None, help="Override max steps")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility")
@click.option("--tick-delay", "-d", type=float, default=None, help="Delay between steps (seconds)")
@click.option("--simple", is_flag=True, help="Use simple log output instead of rich UI")
def run(scenario: str, max_steps: int | None, seed: int | None, tick_delay: float | None, simple: bool):
    """Run a simulation in standalone mode (no server required).
    
    Example:
        emotionsim run --scenario "Rising Flood" --max-steps 50 --seed 42
    """
    asyncio.run(_run_standalone(scenario, max_steps, seed, tick_delay, simple))


async def _run_standalone(
    scenario_name: str,
    max_steps: int | None,
    seed: int | None,
    tick_delay: float | None,
    simple: bool,
):
    """Run simulation in standalone mode"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    
    from app.core.config import get_settings
    from app.core.database import Base
    from app.models.scenario import Scenario
    from app.models.run import Run, RunStatus
    from app.simulation.engine import SimulationEngine

    
    settings = get_settings()
    
    console.print("\n[bold cyan]EmotionSim[/bold cyan] - Standalone Mode\n")
    
    # Create database engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Initialize database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as db:
        # Find or create scenario
        result = await db.execute(
            select(Scenario).where(Scenario.name.ilike(f"%{scenario_name}%"))
        )
        scenario = result.scalar_one_or_none()
        
        if not scenario:
            # Try to create a built-in scenario
            from app.scenarios.defaults import DEFAULT_SCENARIOS
            
            creator = next(
                (
                    func
                    for name, func in DEFAULT_SCENARIOS.items()
                    if scenario_name.lower() in name.lower()
                ),
                None,
            )
            
            if creator:
                scenario_create = creator()
                console.print(f"[yellow]Creating built-in scenario: {scenario_create.name}[/yellow]")
                scenario = Scenario(
                    name=scenario_create.name,
                    description=scenario_create.description,
                    config=scenario_create.config.model_dump(),
                    agent_templates=[t.model_dump() for t in scenario_create.agent_templates],
                )
                db.add(scenario)
                await db.commit()
                await db.refresh(scenario)
            else:
                console.print(f"[red]Scenario '{scenario_name}' not found.[/red]")
                console.print("Use 'emotionsim scenarios --create-builtin' to see available scenarios.")
                return
        
        console.print(f"[green]✓[/green] Loaded scenario: [bold]{scenario.name}[/bold]")
        
        # Create run
        run_record = Run(
            scenario_id=scenario.id,
            seed=seed,
            max_steps=max_steps or scenario.config.get("max_steps", 100),
            status=RunStatus.PENDING,
        )
        db.add(run_record)
        await db.commit()
        await db.refresh(run_record)
        
        console.print(f"[green]✓[/green] Created run: [dim]{run_record.id}[/dim]")
        
        # Setup renderer
        if simple:
            logger = SimpleEventLogger(console)
            
            def on_event(event_type: str, data: dict[str, Any]):
                logger.log_event(event_type, data)
                # Log messages from step events
                if event_type == "step_completed":
                    for msg in data.get("messages", []):
                        logger.log_message(msg)
        else:
            renderer = EventRenderer(console)
            renderer.max_steps = run_record.max_steps
            
            def on_event(event_type: str, data: dict[str, Any]):
                renderer.add_event(event_type, data)
                # Add messages from step events
                if event_type == "step_completed":
                    for msg in data.get("messages", []):
                        renderer.add_message(msg)
        
        # Create engine
        engine_sim = SimulationEngine(
            run_id=run_record.id,
            db_session=db,
            on_event=on_event,
        )
        
        # Build config
        config = {
            "config": scenario.config,
            "agent_templates": scenario.agent_templates,
            "seed": seed,
        }
        
        # Apply overrides
        if max_steps:
            config["config"]["max_steps"] = max_steps
        if tick_delay:
            config["config"]["tick_delay"] = tick_delay
        
        # Initialize
        await engine_sim.initialize(config)
        console.print(f"[green]✓[/green] Initialized {len(engine_sim.agents)} agents")
        console.print()
        
        # Handle Ctrl+C gracefully
        stop_requested = False
        
        def signal_handler(sig, frame):
            nonlocal stop_requested
            if stop_requested:
                console.print("\n[red]Force quit[/red]")
                sys.exit(1)
            stop_requested = True
            console.print("\n[yellow]Stopping simulation... (Ctrl+C again to force)[/yellow]")
            asyncio.create_task(engine_sim.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        
        # Run with live display or simple output
        if simple:
            console.print("[cyan]Starting simulation...[/cyan]\n")
            await engine_sim.start()
        else:
            console.print("[cyan]Starting simulation (press Ctrl+C to stop)...[/cyan]\n")
            with Live(renderer.render_layout(), console=console, refresh_per_second=4) as live:
                # Start simulation in background
                task = asyncio.create_task(engine_sim.start())
                
                # Update display while running
                while not task.done() and not stop_requested:
                    live.update(renderer.render_layout())
                    await asyncio.sleep(0.25)
                
                # Wait for task to complete
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                # Final update
                live.update(renderer.render_layout())
        
        console.print()
        console.print(f"[green]✓[/green] Simulation complete. Final step: {engine_sim.current_step}")
        
        # Show summary
        if engine_sim.world_state:
            console.print()
            table = Table(title="Final World State", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Hazard Level", str(engine_sim.world_state.get("hazard_level", "?")))
            table.add_row("Total Messages", str(len(engine_sim.message_bus._message_history)))
            table.add_row("Steps Completed", str(engine_sim.current_step))
            
            console.print(table)


# ============================================================================
# Monitor Command (Client Mode)
# ============================================================================

@cli.command()
@click.option("--url", "-u", default="ws://localhost:8000/api/ws", help="WebSocket base URL")
@click.option("--run-id", "-r", required=True, help="Run ID to monitor")
@click.option("--simple", is_flag=True, help="Use simple log output instead of rich UI")
def monitor(url: str, run_id: str, simple: bool):
    """Monitor a running simulation via WebSocket.
    
    Example:
        emotionsim monitor --run-id abc123
    """
    asyncio.run(_monitor_websocket(url, run_id, simple))


async def _monitor_websocket(base_url: str, run_id: str, simple: bool):
    """Connect to WebSocket and monitor events"""
    import websockets
    
    ws_url = f"{base_url}/{run_id}"
    
    console.print(f"\n[bold cyan]EmotionSim Monitor[/bold cyan] - Client Mode")
    console.print(f"Connecting to: [dim]{ws_url}[/dim]\n")
    
    if simple:
        logger = SimpleEventLogger(console)
    else:
        renderer = EventRenderer(console)
    
    try:
        async with websockets.connect(ws_url) as ws:
            console.print("[green]✓[/green] Connected to simulation\n")
            
            if simple:
                # Simple streaming mode
                async for message in ws:
                    try:
                        data = json.loads(message)
                        event_type = data.get("event", "unknown")
                        event_data = data.get("data", {})
                        
                        logger.log_event(event_type, event_data)
                        
                        # Log messages
                        if event_type == "step_completed":
                            for msg in event_data.get("messages", []):
                                logger.log_message(msg)
                        
                        # Exit on completion
                        if event_type in ("run_completed", "run_stopped"):
                            break
                            
                    except json.JSONDecodeError:
                        console.print(f"[red]Invalid JSON:[/red] {message[:100]}")
            else:
                # Rich live display mode
                with Live(renderer.render_layout(), console=console, refresh_per_second=4) as live:
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            event_type = data.get("event", "unknown")
                            event_data = data.get("data", {})
                            
                            renderer.add_event(event_type, event_data)
                            
                            # Add messages
                            if event_type == "step_completed":
                                for msg in event_data.get("messages", []):
                                    renderer.add_message(msg)
                            
                            live.update(renderer.render_layout())
                            
                            # Exit on completion
                            if event_type in ("run_completed", "run_stopped"):
                                await asyncio.sleep(1)  # Show final state briefly
                                break
                                
                        except json.JSONDecodeError:
                            pass
            
            console.print("\n[green]✓[/green] Monitoring complete")
            
    except ConnectionRefusedError:
        console.print(f"[red]✗[/red] Could not connect to {ws_url}")
        console.print("  Make sure the backend server is running.")
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")


# ============================================================================
# Scenarios Command
# ============================================================================

@cli.command()
@click.option("--create-builtin", is_flag=True, help="Create built-in scenarios in database")
def scenarios(create_builtin: bool):
    """List available scenarios.
    
    Example:
        emotionsim scenarios
        emotionsim scenarios --create-builtin
    """
    asyncio.run(_list_scenarios(create_builtin))


async def _list_scenarios(create_builtin: bool):
    """List scenarios from database"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    
    from app.core.config import get_settings
    from app.core.database import Base
    from app.models.scenario import Scenario
    from app.scenarios.defaults import DEFAULT_SCENARIOS
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as db:
        if create_builtin:
            console.print("[cyan]Creating built-in scenarios...[/cyan]")
            for name, creator in DEFAULT_SCENARIOS.items():
                result = await db.execute(select(Scenario).where(Scenario.name == name))
                if not result.scalar_one_or_none():
                    scenario_create = creator()
                    scenario = Scenario(
                        name=scenario_create.name,
                        description=scenario_create.description,
                        config=scenario_create.config.model_dump(),
                        agent_templates=[t.model_dump() for t in scenario_create.agent_templates],
                    )
                    db.add(scenario)
                    await db.commit()
                    console.print(f"  [green]✓[/green] Created: {name}")
                else:
                    console.print(f"  [dim]Already exists: {name}[/dim]")
            console.print()
        
        # List scenarios
        result = await db.execute(select(Scenario).order_by(Scenario.name))
        scenarios_list = result.scalars().all()
        
        if not scenarios_list:
            console.print("[yellow]No scenarios found.[/yellow]")
            console.print("Use 'emotionsim scenarios --create-builtin' to create built-in scenarios.")
            return
        
        table = Table(title="Available Scenarios", box=box.ROUNDED)
        table.add_column("Name", style="cyan bold")
        table.add_column("ID", style="dim")
        table.add_column("Agents", style="green")
        table.add_column("Max Steps", style="yellow")
        table.add_column("Description", style="white", max_width=40)
        
        for s in scenarios_list:
            agent_count = len(s.agent_templates) if s.agent_templates else 0
            max_steps = s.config.get("max_steps", "?") if s.config else "?"
            desc = (s.description or "")[:40]
            if len(s.description or "") > 40:
                desc += "..."
            
            table.add_row(
                s.name,
                str(s.id)[:8] + "...",
                str(agent_count),
                str(max_steps),
                desc,
            )
        
        console.print()
        console.print(table)
        console.print()
        console.print("[dim]Tip: Use 'emotionsim run --scenario \"<name>\"' to run a simulation[/dim]")


# ============================================================================
# Interactive Command
# ============================================================================

@cli.command()
def interactive():
    """Launch interactive simulation wizard.
    
    Example:
        emotionsim interactive
    """
    asyncio.run(_interactive_wizard())


async def _interactive_wizard():
    """Interactive simulation launcher"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select
    
    from app.core.config import get_settings
    from app.core.database import Base
    from app.models.scenario import Scenario
    from app.scenarios.defaults import DEFAULT_SCENARIOS
    
    console.print()
    console.print("[bold cyan]╔══════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║     EmotionSim Interactive Mode      ║[/bold cyan]")
    console.print("[bold cyan]╚══════════════════════════════════════╝[/bold cyan]")
    console.print()
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as db:
        # Get scenarios
        result = await db.execute(select(Scenario).order_by(Scenario.name))
        scenarios_list = list(result.scalars().all())
        
        # Create built-in if none exist
        if not scenarios_list:
            console.print("[yellow]No scenarios found. Creating built-in scenarios...[/yellow]")
            for name, creator in DEFAULT_SCENARIOS.items():
                scenario_create = creator()
                scenario = Scenario(
                    name=scenario_create.name,
                    description=scenario_create.description,
                    config=scenario_create.config.model_dump(),
                    agent_templates=[t.model_dump() for t in scenario_create.agent_templates],
                )
                db.add(scenario)
            await db.commit()
            
            result = await db.execute(select(Scenario).order_by(Scenario.name))
            scenarios_list = list(result.scalars().all())
            console.print(f"[green]✓[/green] Created {len(scenarios_list)} scenarios.\n")
        
        # Display scenarios
        console.print("[bold]Available Scenarios:[/bold]")
        for i, s in enumerate(scenarios_list, 1):
            agent_count = len(s.agent_templates) if s.agent_templates else 0
            console.print(f"  [cyan]{i}.[/cyan] {s.name} [dim]({agent_count} agents)[/dim]")
        console.print()
        
        # Select scenario
        choice = Prompt.ask(
            "Select scenario",
            choices=[str(i) for i in range(1, len(scenarios_list) + 1)],
            default="1"
        )
        selected = scenarios_list[int(choice) - 1]
        console.print()
        
        # Configuration
        default_steps = selected.config.get("max_steps", 50)
        max_steps_str = Prompt.ask(
            "Max steps",
            default=str(default_steps)
        )
        max_steps = int(max_steps_str)
        
        default_delay = selected.config.get("tick_delay", 1.0)
        tick_delay_str = Prompt.ask(
            "Tick delay (seconds)",
            default=str(default_delay)
        )
        tick_delay = float(tick_delay_str)
        
        seed_str = Prompt.ask(
            "Random seed (blank for random)",
            default=""
        )
        seed = int(seed_str) if seed_str else None
        
        use_rich = Confirm.ask("Use rich UI display?", default=True)
        
        console.print()
        console.print("[bold]Configuration:[/bold]")
        console.print(f"  Scenario: [cyan]{selected.name}[/cyan]")
        console.print(f"  Max Steps: [yellow]{max_steps}[/yellow]")
        console.print(f"  Tick Delay: [yellow]{tick_delay}s[/yellow]")
        console.print(f"  Seed: [yellow]{seed or 'random'}[/yellow]")
        console.print(f"  Display: [yellow]{'Rich UI' if use_rich else 'Simple logs'}[/yellow]")
        console.print()
        
        if not Confirm.ask("Start simulation?", default=True):
            console.print("[dim]Cancelled.[/dim]")
            return
        
        console.print()
    
    # Run the simulation (need to close db session first since _run_standalone creates its own)
    await _run_standalone(
        scenario_name=selected.name,
        max_steps=max_steps,
        seed=seed,
        tick_delay=tick_delay,
        simple=not use_rich,
    )


# ============================================================================
# Status Command
# ============================================================================

@cli.command()
@click.option("--url", "-u", default="http://localhost:8000", help="Backend API URL")
def status(url: str):
    """Check backend server status.
    
    Example:
        emotionsim status
    """
    asyncio.run(_check_status(url))


async def _check_status(base_url: str):
    """Check server status"""
    import httpx
    
    console.print(f"\n[bold cyan]EmotionSim[/bold cyan] - Status Check")
    console.print(f"Server: [dim]{base_url}[/dim]\n")
    
    try:
        async with httpx.AsyncClient() as client:
            # Health check
            response = await client.get(f"{base_url}/health", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                console.print(f"[green]✓[/green] Server is [green]healthy[/green]")
                console.print(f"  App: {data.get('app', 'unknown')}")
            else:
                console.print(f"[red]✗[/red] Server returned status {response.status_code}")
                return
            
            # Get runs
            response = await client.get(f"{base_url}/api/runs/", timeout=5.0)
            if response.status_code == 200:
                runs = response.json()
                console.print(f"\n[bold]Recent Runs:[/bold]")
                if not runs:
                    console.print("  [dim]No runs found[/dim]")
                else:
                    table = Table(box=box.SIMPLE)
                    table.add_column("ID", style="dim")
                    table.add_column("Status", style="cyan")
                    table.add_column("Steps", style="yellow")
                    
                    for run in runs[:5]:
                        table.add_row(
                            str(run.get("id", "?"))[:8] + "...",
                            run.get("status", "?"),
                            str(run.get("current_step", 0)),
                        )
                    console.print(table)
                    
    except httpx.ConnectError:
        console.print(f"[red]✗[/red] Could not connect to {base_url}")
        console.print("  Make sure the backend server is running:")
        console.print("  [dim]cd backend && python -m app.main[/dim]")
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")


# ============================================================================
# Best Runs Command
# ============================================================================

@cli.command()
@click.option("--limit", "-n", default=10, help="Number of runs to show")
def best(limit: int):
    """Show the best simulations based on agent health and stress.
    
    Example:
        emotionsim best
    """
    asyncio.run(_show_best_runs(limit))


async def _show_best_runs(limit: int):
    """Show best runs analysis"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, desc
    from sqlalchemy.orm import selectinload
    
    from app.core.config import get_settings
    from app.core.database import Base
    from app.models.run import Run, RunStatus
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    console.print(f"\n[bold cyan]EmotionSim[/bold cyan] - Best Simulations")
    
    async with async_session() as db:
        # Get completed runs logic
        # Since JSON metrics querying depends on DB type (SQLite vs PG), we'll fetch completed runs 
        # and sort in Python for simplicity and compatibility
        result = await db.execute(
            select(Run)
            .where(Run.status == RunStatus.COMPLETED)
            .order_by(desc(Run.completed_at))
            .options(selectinload(Run.scenario))
        )
        runs = result.scalars().all()
        
        if not runs:
            console.print("[yellow]No completed runs found.[/yellow]")
            return
            
        # Calculate scores and sort
        scored_runs = []
        for run in runs:
            metrics = run.metrics or {}
            avg_health = float(metrics.get("avg_health", 0))
            avg_stress = float(metrics.get("avg_stress", 10))
            
            # Simple score: Health - Stress (higher is better)
            # Normalize stress (lower is better, so negate)
            score = avg_health - avg_stress
            
            scored_runs.append({
                "run": run,
                "score": score,
                "health": avg_health,
                "stress": avg_stress,
                "steps": run.current_step
            })
            
        # Sort by score descending
        scored_runs.sort(key=lambda x: x["score"], reverse=True)
        
        # Display
        table = Table(title=f"Top {limit} Simulations", box=box.ROUNDED)
        table.add_column("Rank", style="dim")
        table.add_column("ID", style="dim")
        table.add_column("Scenario", style="cyan")
        table.add_column("Score", style="bold green")
        table.add_column("Avg Health", style="green")
        table.add_column("Avg Stress", style="red")
        table.add_column("Steps", style="yellow")
        
        for i, item in enumerate(scored_runs[:limit], 1):
            run = item["run"]
            table.add_row(
                str(i),
                str(run.id)[:8] + "...",
                run.scenario.name if run.scenario else "Unknown",
                f"{item['score']:.2f}",
                f"{item['health']:.1f}",
                f"{item['stress']:.1f}",
                str(item['steps'])
            )
            
        console.print(table)
        console.print()


# ============================================================================
# Auto Run Command
# ============================================================================

@cli.command()
@click.option("--count", "-n", default=None, type=int, help="Number of simulations to run (default: infinite)")
def auto(count: int | None):
    """Automatically run simulations sequentially.
    
    Checks for pending runs first, then generates new ones from presets.
    """
    asyncio.run(_run_auto_loop(count))


async def _run_auto_loop(count: int | None):
    """Run simulations sequentially"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import select, asc
    import random
    
    from app.core.config import get_settings
    from app.core.database import Base
    from app.models.scenario import Scenario
    from app.models.run import Run, RunStatus
    from app.scenarios.defaults import DEFAULT_SCENARIOS
    
    settings = get_settings()
    
    console.print("\n[bold cyan]EmotionSim[/bold cyan] - Auto Runner")
    console.print(f"Model: [bold green]{settings.ollama_default_model}[/bold green]")
    console.print(f"Max Context: [bold yellow]8192 tokens[/bold yellow]")
    console.print()
    
    # Display available presets
    console.print("[bold]Available Presets:[/bold]")
    for name in DEFAULT_SCENARIOS.keys():
        console.print(f"  - {name}")
    console.print()
    
    # Setup DB
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Ensure DB exists
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    runs_completed = 0
    
    while count is None or runs_completed < count:
        console.print(f"[bold]>>> Starting cycle {runs_completed + 1}[/bold]")
        
        # Check for pending runs
        target_run_id = None
        scenario_name = None
        
        async with async_session() as db:
            # Check for PENDING runs
            result = await db.execute(
                select(Run)
                .where(Run.status == RunStatus.PENDING)
                .order_by(asc(Run.created_at))
                .limit(1)
            )
            pending_run = result.scalar_one_or_none()
            
            if pending_run:
                target_run_id = pending_run.id
                # Eager load scenario to get name
                result = await db.execute(select(Scenario).where(Scenario.id == pending_run.scenario_id))
                scenario = result.scalar_one_or_none()
                scenario_name = scenario.name if scenario else "Unknown"
                console.print(f"[yellow]Found pending run:[/yellow] {scenario_name} ({target_run_id[:8]}...)")
            else:
                # Create a new run from random preset
                preset_name = random.choice(list(DEFAULT_SCENARIOS.keys()))
                console.print(f"[cyan]No pending runs. Creating new run:[/cyan] {preset_name}")
                
                # Check if scenario exists
                result = await db.execute(select(Scenario).where(Scenario.name.ilike(f"%{preset_name}%")))
                scenario = result.scalar_one_or_none()
                
                if not scenario:
                    # Create it
                    creator = DEFAULT_SCENARIOS[preset_name]
                    scenario_create = creator()
                    scenario = Scenario(
                        name=scenario_create.name,
                        description=scenario_create.description,
                        config=scenario_create.config.model_dump(),
                        agent_templates=[t.model_dump() for t in scenario_create.agent_templates],
                    )
                    db.add(scenario)
                    await db.commit()
                    await db.refresh(scenario)
                
                # Create Run
                new_run = Run(
                    scenario_id=scenario.id,
                    status=RunStatus.PENDING,
                    max_steps=scenario.config.get("max_steps", 50),
                    seed=random.randint(1, 10000)
                )
                db.add(new_run)
                await db.commit()
                await db.refresh(new_run)
                
                target_run_id = new_run.id
                scenario_name = scenario.name
        
        if target_run_id:
            # Run it using existing standalone runner
            # We use simple mode for auto runner to keep logs clean
            console.print(f"[green]Executing run {target_run_id} ({scenario_name})...[/green]")
            try:
                # We need to run this function. 
                # Note: passing specific run_id isn't supported by _run_standalone directly
                # _run_standalone takes scenario name and creates a NEW run.
                # We need to refactor _run_standalone or create a variant that takes a run_id.
                # But wait, looking at _run_standalone, it creates a run.
                
                # Let's modify _run_standalone to accept an optional run_id!
                # Or simply implement the execution logic here reusing the engine?
                
                # Reusing internal logic is better to avoid "creating" a run when we already have one.
                
                # Reuse logic from _run_standalone but for an existing run
                await _execute_existing_run(target_run_id, simple=True)
                
            except Exception as e:
                console.print(f"[red]Error executing run:[/red] {e}")
                import traceback
                traceback.print_exc()
            
            runs_completed += 1
            console.print(f"[bold green]✓ Cycle completed.[/bold green]")
            console.print("-" * 50)
            
            # Small delay between runs
            await asyncio.sleep(2)


async def _execute_existing_run(run_id: str, simple: bool = True):
    """Execute an existing PENDING run"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import get_settings
    from app.simulation.engine import SimulationEngine
    from app.cli_monitor import SimpleEventLogger
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Setup logging
        logger = SimpleEventLogger(console)
        
        def on_event(event_type: str, data: dict[str, Any]):
            logger.log_event(event_type, data)
            if event_type == "step_completed":
                for msg in data.get("messages", []):
                    logger.log_message(msg)
        
        # Initialize Engine with existing run
        sim_engine = SimulationEngine(
            run_id=run_id,
            db_session=db,
            on_event=on_event
        )
        
        # Load from DB (this method needs to exist on engine or we initialize manually)
        # The engine has load_from_db()!
        await sim_engine.load_from_db()
        
        console.print(f"[green]✓[/green] Loaded run {run_id}")
        
        # Start
        await sim_engine.start()
        
        console.print(f"[green]✓[/green] Simulation finished.")



# ============================================================================
# Status Command
# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point for CLI"""
    cli()


if __name__ == "__main__":
    main()

