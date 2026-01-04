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
import httpx

from app.cli_monitor import EventRenderer, SimpleEventLogger
from app.core.config import get_settings


async def check_model_selection():
    """Ensure a valid model is selected and available"""
    settings = get_settings()
    base_url = settings.ollama_base_url
    default_model = settings.ollama_default_model
    
    try:
        async with httpx.AsyncClient() as client:
            try:
                # List models
                response = await client.get(f"{base_url}/tags", timeout=2.0)
                if response.status_code != 200:
                    console.print(f"[yellow]Warning: Could not connect to Ollama at {base_url}[/yellow]")
                    console.print(f"Using configured default: [bold]{default_model}[/bold]")
                    return
                
                models_data = response.json()
                models = [m["name"] for m in models_data.get("models", [])]
                
                if not models:
                    console.print("[red]No models found in Ollama![/red]")
                    console.print("Please pull a model, e.g.: [bold]ollama pull gemma3[/bold]")
                    sys.exit(1)
                
                # Check if default model exists
                if default_model not in models and f"{default_model}:latest" not in models:
                    console.print(f"[yellow]Default model '{default_model}' not found in Ollama.[/yellow]")
                    console.print("\n[bold]Available Models:[/bold]")
                    for i, m in enumerate(models, 1):
                        console.print(f"  {i}. {m}")
                    
                    console.print()
                    choice = Prompt.ask(
                        "Select a model to use",
                        choices=[str(i) for i in range(1, len(models) + 1)],
                        default="1"
                    )
                    selected_model = models[int(choice) - 1]
                    
                    # Update settings (in memory for this session)
                    settings.ollama_default_model = selected_model
                    console.print(f"[green]Using model: {selected_model}[/green]\n")
                else:
                    # Model exists, all good
                    pass
                    
            except httpx.ConnectError:
                console.print(f"[yellow]Warning: Could not connect to Ollama at {base_url}[/yellow]")
                console.print(f"Using configured default: [bold]{default_model}[/bold]")
                
    except Exception as e:
        console.print(f"[dim]Model check failed: {e}[/dim]")


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
@click.option("--scenario", "-s", required=False, help="Scenario name or ID to run (optional, prompts if omitted)")
@click.option("--max-steps", "-m", type=int, default=None, help="Override max steps")
@click.option("--seed", type=int, default=None, help="Random seed for reproducibility")
@click.option("--tick-delay", "-d", type=float, default=None, help="Delay between steps (seconds)")
@click.option("--simple", is_flag=True, help="Use simple log output instead of rich UI")
def run(scenario: str | None, max_steps: int | None, seed: int | None, tick_delay: float | None, simple: bool):
    """Run a simulation in standalone mode (no server required).
    
    Example:
        emotionsim run --scenario "Rising Flood" --max-steps 50 --seed 42
    """
    asyncio.run(_run_standalone(scenario, max_steps, seed, tick_delay, simple))


async def _run_standalone(
    scenario_name: str | None,
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
    
    # Check model
    await check_model_selection()
    
    # Create database engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Initialize database
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session() as db:
        
        # If no scenario specified, show menu
        if not scenario_name:
            from app.scenarios.defaults import DEFAULT_SCENARIOS
            from app.scenarios.storage import load_generated_scenarios
            
            # Fetch DB scenarios
            db_scenarios = (await db.execute(select(Scenario))).scalars().all()
            
            # Load generated scenarios
            generated_scenarios = load_generated_scenarios()
            
            console.print("\n[bold]Select a Scenario:[/bold]")
            
            choices = []
            choice_sources = []  # Track where each choice comes from
            
            # Add DB scenarios
            if db_scenarios:
                console.print("\n[dim]Saved Scenarios:[/dim]")
                for idx, sc in enumerate(db_scenarios):
                    choices.append(sc.name)
                    choice_sources.append(("db", sc))
                    console.print(f"  [cyan]{len(choices)}.[/cyan] {sc.name} [dim]({len(sc.agent_templates)} agents)[/dim]")
            
            # Add Generated scenarios
            if generated_scenarios:
                console.print("\n[dim]Generated Scenarios:[/dim]")
                for gen_sc in generated_scenarios:
                    choices.append(gen_sc["name"])
                    choice_sources.append(("generated", gen_sc))
                    console.print(f"  [cyan]{len(choices)}.[/cyan] {gen_sc['name']} [dim]({gen_sc['agent_count']} agents)[/dim]")
            
            # Add Built-in scenarios
            console.print("\n[dim]Built-in Templates:[/dim]")
            for name in DEFAULT_SCENARIOS.keys():
                choices.append(name)
                choice_sources.append(("builtin", name))
                console.print(f"  [cyan]{len(choices)}.[/cyan] {name}")
                
            console.print()
            
            if not choices:
                console.print("[red]No scenarios found![/red]")
                return

            choice_idx = Prompt.ask("Enter number", default="1")
            try:
                idx = int(choice_idx) - 1
                if 0 <= idx < len(choices):
                    scenario_name = choices[idx]
                    selected_source, selected_data = choice_sources[idx]
                else:
                    console.print("[red]Invalid selection[/red]")
                    return
            except ValueError:
                console.print("[red]Invalid input[/red]")
                return
        else:
            selected_source = None
            selected_data = None

        # Find or create scenario
        scenario = None
        
        # Check if scenario_name is a simple numeric ID
        if scenario_name.isdigit():
            # Build scenario map
            db_scenarios_list = (await db.execute(select(Scenario).order_by(Scenario.name))).scalars().all()
            from app.scenarios.storage import load_generated_scenarios
            generated_scenarios = load_generated_scenarios()
            
            idx = int(scenario_name)
            
            # Check if it's a DB scenario
            if idx < len(db_scenarios_list):
                scenario = db_scenarios_list[idx]
            # Check if it's a generated scenario
            elif idx < len(db_scenarios_list) + len(generated_scenarios):
                gen_idx = idx - len(db_scenarios_list)
                gen_scenario = generated_scenarios[gen_idx]
                console.print(f"[yellow]Loading generated scenario: {gen_scenario['name']}[/yellow]")
                scenario = Scenario(
                    name=gen_scenario["name"],
                    description=gen_scenario["description"],
                    config=gen_scenario["config"],
                    agent_templates=gen_scenario["agent_templates"],
                )
                db.add(scenario)
                await db.commit()
                await db.refresh(scenario)
        else:
            # Try UUID lookup
            try:
                from uuid import UUID
                UUID(scenario_name)
                result = await db.execute(
                    select(Scenario).where(Scenario.id == scenario_name)
                )
                scenario = result.scalar_one_or_none()
            except (ValueError, AttributeError):
                # Try by name
                result = await db.execute(
                    select(Scenario).where(Scenario.name.ilike(f"%{scenario_name}%"))
                )
                scenario = result.scalar_one_or_none()
                
                # Try generated scenario filename
                if not scenario:
                    from app.scenarios.storage import load_generated_scenarios
                    generated_scenarios = load_generated_scenarios()
                    gen_scenario = next(
                        (s for s in generated_scenarios if scenario_name in s["filename"] or scenario_name.lower() in s["name"].lower()),
                        None
                    )
                    
                    if gen_scenario:
                        console.print(f"[yellow]Loading generated scenario: {gen_scenario['name']}[/yellow]")
                        scenario = Scenario(
                            name=gen_scenario["name"],
                            description=gen_scenario["description"],
                            config=gen_scenario["config"],
                            agent_templates=gen_scenario["agent_templates"],
                        )
                        db.add(scenario)
                        await db.commit()
                        await db.refresh(scenario)
        
        if not scenario:
            # Check if it's a generated scenario
            if selected_source == "generated":
                # Load from JSON file
                console.print(f"[yellow]Loading generated scenario: {selected_data['name']}[/yellow]")
                scenario = Scenario(
                    name=selected_data["name"],
                    description=selected_data["description"],
                    config=selected_data["config"],
                    agent_templates=selected_data["agent_templates"],
                )
                db.add(scenario)
                await db.commit()
                await db.refresh(scenario)
            else:
                # Try to create a built-in scenario
                from app.scenarios.defaults import DEFAULT_SCENARIOS
                from app.scenarios.storage import load_generated_scenarios
                
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
                    # Try to find in generated scenarios
                    generated_scenarios = load_generated_scenarios()
                    gen_scenario = next(
                        (s for s in generated_scenarios if scenario_name.lower() in s["name"].lower()),
                        None
                    )
                    
                    if gen_scenario:
                        console.print(f"[yellow]Loading generated scenario: {gen_scenario['name']}[/yellow]")
                        scenario = Scenario(
                            name=gen_scenario["name"],
                            description=gen_scenario["description"],
                            config=gen_scenario["config"],
                            agent_templates=gen_scenario["agent_templates"],
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
                if event_type == "message":
                     # Handle real-time message addition
                     renderer.add_message(data["data"])
                else:
                    renderer.add_event(event_type, data)
                
                # Note: We no longer add messages from step_completed to avoid duplicates
                # and ensure real-time logging via the 'message' event above.
        
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
            # Increase refresh rate for smooth streaming
            with Live(renderer.render_layout(), console=console, refresh_per_second=15) as live:
                
                async def stream_callback(agent_id: str, token: str):
                    renderer.update_stream(agent_id, token)
                    live.refresh()
                
                # Start simulation in background
                task = asyncio.create_task(engine_sim.start(stream_callback=stream_callback))
                
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
        
        if Confirm.ask("Backend server not reachable. Start it now?"):
            console.print("[yellow]Starting backend server...[/yellow]")
            import subprocess
            
            # Start backend in background
            # We assume we are in backend dir because cli runs from there?
            # Actually CLI might be run as `python -m app.cli` from backend dir.
            process = subprocess.Popen(
                [sys.executable, "-m", "app.main"],
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
            )
            
            # Wait for it to start
            connected = False
            with console.status("[cyan]Waiting for server to start...[/cyan]"):
                for _ in range(15):
                    await asyncio.sleep(1)
                    try:
                        import httpx
                        async with httpx.AsyncClient() as client:
                             # Check health endpoint instead of WS for startup
                             resp = await client.get(f"{base_url}/health", timeout=1.0)
                             if resp.status_code == 200:
                                 connected = True
                                 break
                    except:
                        pass
            
            if connected:
                console.print("[green]✓[/green] Server started. Retrying connection...")
                await _monitor_websocket(base_url, run_id, simple)
                return
            else:
                console.print("[red]✗[/red] Failed to start server or connect in time.")
                process.terminate()
                
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
        
        # List scenarios from DB
        result = await db.execute(select(Scenario).order_by(Scenario.name))
        db_scenarios = result.scalars().all()
        
        # Load generated scenarios
        from app.scenarios.storage import load_generated_scenarios
        generated_scenarios = load_generated_scenarios()
        
        # Combine all scenarios
        all_scenarios = []
        scenario_map = {}  # Map simple ID to actual scenario data
        
        # Add DB scenarios
        for idx, s in enumerate(db_scenarios):
            simple_id = str(idx)
            all_scenarios.append({
                "source": "DB",
                "name": s.name,
                "id": simple_id,
                "db_id": str(s.id),
                "agents": len(s.agent_templates) if s.agent_templates else 0,
                "max_steps": s.config.get("max_steps", "?") if s.config else "?",
                "description": s.description or "",
            })
            scenario_map[simple_id] = {"type": "db", "db_id": str(s.id), "name": s.name}
        
        # Add generated scenarios
        start_idx = len(db_scenarios)
        for idx, g in enumerate(generated_scenarios):
            simple_id = str(start_idx + idx)
            file_id = g["filename"].replace(".json", "")
            all_scenarios.append({
                "source": "Generated",
                "name": g["name"],
                "id": simple_id,
                "file_id": file_id,
                "agents": g["agent_count"],
                "max_steps": g["config"].get("max_steps", "?"),
                "description": g["description"],
            })
            scenario_map[simple_id] = {"type": "generated", "file_id": file_id, "name": g["name"]}
        
        if not all_scenarios:
            console.print("[yellow]No scenarios found.[/yellow]")
            console.print("Use 'emotionsim scenarios --create-builtin' to create built-in scenarios.")
            console.print("Or use 'python tools/generate_scenario.py' to generate new scenarios.")
            return
        
        table = Table(title="Available Scenarios", box=box.ROUNDED)
        table.add_column("ID", style="dim", width=4)
        table.add_column("Source", style="magenta", width=10)
        table.add_column("Name", style="cyan bold")
        table.add_column("Agents", style="green", width=7)
        table.add_column("Max Steps", style="yellow", width=10)
        table.add_column("Description", style="white", max_width=40)
        
        for s in all_scenarios:
            desc = s["description"][:40]
            if len(s["description"]) > 40:
                desc += "..."
            
            table.add_row(
                s["id"],
                s["source"],
                s["name"],
                str(s["agents"]),
                str(s["max_steps"]),
                desc,
            )
        
        console.print()
        console.print(table)
        console.print()
        console.print("[dim]Tip: Use 'emotionsim run --scenario \"<name or ID>\"' to run a simulation[/dim]")


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
        # Check model
        await check_model_selection()
        
        # Get DB scenarios
        result = await db.execute(select(Scenario).order_by(Scenario.name))
        db_scenarios = list(result.scalars().all())
        
        # Load generated scenarios
        from app.scenarios.storage import load_generated_scenarios
        generated_scenarios = load_generated_scenarios()
        
        # Create built-in if none exist
        if not db_scenarios and not generated_scenarios:
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
            db_scenarios = list(result.scalars().all())
            console.print(f"[green]✓[/green] Created {len(db_scenarios)} scenarios.\n")
        
        # Combine all scenarios for selection
        all_scenarios = []
        scenario_sources = []
        
        # Add DB scenarios
        console.print("[bold]Available Scenarios:[/bold]")
        if db_scenarios:
            console.print("\n[dim]Saved Scenarios:[/dim]")
            for s in db_scenarios:
                agent_count = len(s.agent_templates) if s.agent_templates else 0
                all_scenarios.append(s)
                scenario_sources.append(("db", s))
                console.print(f"  [cyan]{len(all_scenarios)}.[/cyan] {s.name} [dim]({agent_count} agents)[/dim]")
        
        # Add generated scenarios
        if generated_scenarios:
            console.print("\n[dim]Generated Scenarios:[/dim]")
            for g in generated_scenarios:
                all_scenarios.append(g)
                scenario_sources.append(("generated", g))
                console.print(f"  [cyan]{len(all_scenarios)}.[/cyan] {g['name']} [dim]({g['agent_count']} agents)[/dim]")
        
        console.print()
        
        # Select scenario
        choice = Prompt.ask(
            "Select scenario",
            choices=[str(i) for i in range(1, len(all_scenarios) + 1)],
            default="1"
        )
        choice_idx = int(choice) - 1
        source_type, selected_data = scenario_sources[choice_idx]
        
        # Load scenario into DB if it's a generated one
        if source_type == "generated":
            selected = Scenario(
                name=selected_data["name"],
                description=selected_data["description"],
                config=selected_data["config"],
                agent_templates=selected_data["agent_templates"],
            )
            db.add(selected)
            await db.commit()
            await db.refresh(selected)
        else:
            selected = selected_data
        
        console.print()
        
        # Configuration
        default_steps = selected.config.get("max_steps", 10)
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

    # Preset Selection Logic
    selected_preset = None
    
    # Get available presets
    preset_choices = list(DEFAULT_SCENARIOS.keys())
    preset_choices.sort()
    
    console.print("[bold]Select Auto-Run Source:[/bold]")
    console.print("  [cyan]0.[/cyan] [bold white]Random (Cycle through all)[/bold white]")
    for i, name in enumerate(preset_choices, 1):
        console.print(f"  [cyan]{i}.[/cyan] {name}")
    console.print()
    
    choice_idx = Prompt.ask("Enter number", default="0")
    try:
        idx = int(choice_idx)
        if idx > 0 and idx <= len(preset_choices):
            selected_preset = preset_choices[idx-1]
            console.print(f"[green]Selected preset:[/green] {selected_preset}")
        else:
            console.print("[yellow]Using Random selection[/yellow]")
    except ValueError:
        console.print("[yellow]Invalid input, using Random selection[/yellow]")

    console.print()
    
    # Setup DB
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Ensure DB exists
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # CLEANUP: End all pending and running simulations before starting
    async with async_session() as db:
        cleanup_query = select(Run).where(Run.status.in_([RunStatus.PENDING, RunStatus.RUNNING]))
        cleanup_result = await db.execute(cleanup_query)
        runs_to_cleanup = cleanup_result.scalars().all()
        
        if runs_to_cleanup:
            console.print(f"[yellow]Cleaning up {len(runs_to_cleanup)} pending/running simulation(s)...[/yellow]")
            for run in runs_to_cleanup:
                run.status = RunStatus.CANCELLED
                console.print(f"  [dim]Stopped run {str(run.id)[:8]}...[/dim]")
            await db.commit()
            console.print("[green]✓[/green] Cleanup complete\n")
        
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
                # Create a new run
                preset_name = selected_preset or random.choice(list(DEFAULT_SCENARIOS.keys()))
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
                await _execute_existing_run(target_run_id, simple=False)
                
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
    from app.cli_monitor import SimpleEventLogger, EventRenderer
    from rich.live import Live
    
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.run import Run, RunStatus
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        
        if simple:
            logger = SimpleEventLogger(console)
            def on_event(event_type: str, data: dict[str, Any]):
                if event_type == "message":
                    logger.log_message(data["data"])
                else:
                    logger.log_event(event_type, data)
        else:
            renderer = EventRenderer(console)
            def on_event(event_type: str, data: dict[str, Any]):
                if event_type == "message":
                     renderer.add_message(data["data"])
                else:
                    renderer.add_event(event_type, data)
        
        # Initialize Engine with existing run
        sim_engine = SimulationEngine(
            run_id=run_id,
            db_session=db,
            on_event=on_event
        )
        
        # Check run status to decide whether to load or initialize
        result = await db.execute(
            select(Run)
            .where(Run.id == run_id)
            .options(selectinload(Run.scenario))
        )
        run = result.scalar_one_or_none()
        
        if not run:
            console.print(f"[red]Run {run_id} not found![/red]")
            return

        if run.status == RunStatus.PENDING or (run.current_step == 0 and not run.agents):
             # Initialize fresh
             console.print(f"[cyan]Initializing new run from scenario: {run.scenario.name}[/cyan]")
             
             config = {
                "config": run.scenario.config,
                "agent_templates": run.scenario.agent_templates,
                "seed": run.seed,
            }
             
             # Apply max_steps override if present in run
             if run.max_steps:
                 config["config"]["max_steps"] = run.max_steps
                 
             await sim_engine.initialize(config)
             console.print(f"[green]✓[/green] Initialized {len(sim_engine.agents)} agents")
        else:
             # Load existing state
             await sim_engine.load_from_db()
             console.print(f"[green]✓[/green] Resumed run {run_id} (step {sim_engine.current_step})")
             
        # Set max steps for renderer if applicable
        if not simple and hasattr(sim_engine, 'max_steps'):
            renderer.max_steps = sim_engine.max_steps
        
        # Start Simulation
        if simple:
            console.print("[cyan]Starting simulation...[/cyan]\n")
            await sim_engine.start()
        else:
            console.print("[cyan]Starting simulation (auto-mode)...[/cyan]\n")
            # Rich Live Display Logic
            with Live(renderer.render_layout(), console=console, refresh_per_second=15) as live:
                
                async def stream_callback(agent_id: str, token: str):
                    renderer.update_stream(agent_id, token)
                    live.refresh()
                
                # Start simulation in background
                task = asyncio.create_task(sim_engine.start(stream_callback=stream_callback))
                
                # Update display while running
                while not task.done():
                    live.update(renderer.render_layout())
                    await asyncio.sleep(0.25)
                
                # Wait for task to complete and handle exceptions
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                # Final update
                live.update(renderer.render_layout())
        
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

