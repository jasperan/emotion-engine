#!/usr/bin/env python3
"""Generate scenarios using the ScenarioGenerator

This tool provides multiple modes for generating scenarios:
- Interactive mode: Prompt user for scenario description
- Direct mode: Generate from command-line prompt
- Batch mode: Generate multiple scenarios from preset prompts
"""
import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scenarios.generator import ScenarioGenerator
from app.scenarios.storage import save_scenario, SCENARIOS_DIR

console = Console()

# Preset scenario prompts for batch generation
PRESET_PROMPTS = [
    {
        "name": "Earthquake Rescue",
        "prompt": "A magnitude 7.8 earthquake has struck a major city. Buildings have collapsed, power is out, and rescue teams must coordinate to save trapped civilians while dealing with aftershocks and limited resources.",
        "persona_count": 40,
    },
    {
        "name": "Zombie Outbreak",
        "prompt": "A zombie virus has broken out in a shopping mall. Survivors must work together to barricade entrances, find supplies, and plan an escape while dealing with the infected and dwindling resources.",
        "persona_count": 30,
    },
    {
        "name": "Hostage Negotiation",
        "prompt": "Armed robbers have taken hostages at a downtown bank. Police negotiators, SWAT team members, and the criminals must navigate a tense standoff with lives hanging in the balance.",
        "persona_count": 25,
    },
    {
        "name": "Space Station Emergency",
        "prompt": "A critical oxygen leak has occurred on an international space station. The crew must work together to repair the damage, manage limited oxygen supplies, and maintain morale while waiting for a rescue mission.",
        "persona_count": 15,
    },
    {
        "name": "Wildfire Evacuation",
        "prompt": "A rapidly spreading wildfire is approaching a small mountain town. Residents, firefighters, and emergency services must coordinate evacuation efforts while dealing with blocked roads, communication failures, and vulnerable populations.",
        "persona_count": 50,
    },
    {
        "name": "Corporate Merger Negotiation",
        "prompt": "Two tech companies are negotiating a multi-billion dollar merger. Executives, lawyers, and board members from both sides must navigate complex financial terms, cultural differences, and competing interests.",
        "persona_count": 20,
    },
    {
        "name": "Submarine Crisis",
        "prompt": "A military submarine has suffered a catastrophic failure and is stranded on the ocean floor. The crew must manage oxygen, repair critical systems, and maintain discipline while rescue operations are coordinated above.",
        "persona_count": 35,
    },
    {
        "name": "Political Summit",
        "prompt": "World leaders have gathered for an emergency climate summit. Diplomats must negotiate binding agreements while balancing national interests, economic concerns, and the urgent need for global action.",
        "persona_count": 45,
    },
    {
        "name": "Hospital Outbreak",
        "prompt": "A highly contagious disease has broken out in a major hospital. Medical staff must treat patients, contain the outbreak, manage limited supplies, and prevent panic while protecting themselves.",
        "persona_count": 40,
    },
    {
        "name": "Plane Hijacking",
        "prompt": "Terrorists have hijacked a commercial airliner mid-flight. Passengers, crew, air marshals, and ground control must work to resolve the situation peacefully while the plane is running low on fuel.",
        "persona_count": 60,
    },
    {
        "name": "Arctic Research Station",
        "prompt": "An Arctic research station has lost contact with the outside world during a severe blizzard. Scientists must survive extreme cold, manage dwindling supplies, and repair communication equipment while tensions rise.",
        "persona_count": 12,
    },
    {
        "name": "Prison Riot",
        "prompt": "A violent riot has erupted in a maximum-security prison. Guards, inmates, negotiators, and prison administrators must navigate the chaos, prevent casualties, and restore order.",
        "persona_count": 55,
    },
]


@click.command()
@click.option(
    "--interactive", "-i",
    is_flag=True,
    help="Interactive mode: prompt for scenario details"
)
@click.option(
    "--prompt", "-p",
    type=str,
    help="Direct mode: generate scenario from this prompt"
)
@click.option(
    "--batch", "-b",
    is_flag=True,
    help="Batch mode: generate multiple scenarios from presets"
)
@click.option(
    "--count", "-c",
    type=int,
    default=5,
    help="Number of scenarios to generate in batch mode (default: 5)"
)
@click.option(
    "--persona-count", "-n",
    type=int,
    default=50,
    help="Number of personas to generate (default: 50)"
)
@click.option(
    "--list-presets",
    is_flag=True,
    help="List available preset prompts"
)
@click.option(
    "--preset",
    type=int,
    help="Generate from a specific preset number (see --list-presets)"
)
def main(interactive, prompt, batch, count, persona_count, list_presets, preset):
    """Generate scenarios using AI-powered scenario generation.
    
    Examples:
        # Interactive mode
        python generate_scenario.py --interactive
        
        # Direct generation
        python generate_scenario.py --prompt "Tornado hits a small town"
        
        # Batch generation
        python generate_scenario.py --batch --count 3
        
        # List presets
        python generate_scenario.py --list-presets
        
        # Generate from preset
        python generate_scenario.py --preset 1
    """
    if list_presets:
        show_presets()
        return
    
    if preset is not None:
        if 1 <= preset <= len(PRESET_PROMPTS):
            preset_data = PRESET_PROMPTS[preset - 1]
            asyncio.run(generate_single(
                preset_data["prompt"],
                preset_data["persona_count"],
                preset_data["name"]
            ))
        else:
            console.print(f"[red]Invalid preset number. Use --list-presets to see available options.[/red]")
            sys.exit(1)
        return
    
    if interactive:
        asyncio.run(interactive_mode())
    elif prompt:
        asyncio.run(generate_single(prompt, persona_count))
    elif batch:
        asyncio.run(batch_mode(count))
    else:
        console.print("[yellow]No mode specified. Use --help for options.[/yellow]")
        console.print("\nQuick start:")
        console.print("  [cyan]python generate_scenario.py --interactive[/cyan]")
        console.print("  [cyan]python generate_scenario.py --prompt 'Your scenario idea'[/cyan]")
        console.print("  [cyan]python generate_scenario.py --batch --count 3[/cyan]")


def show_presets():
    """Display available preset prompts"""
    console.print("\n[bold cyan]Available Preset Scenarios[/bold cyan]\n")
    
    table = Table(box=box.ROUNDED)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Personas", style="yellow", width=8)
    table.add_column("Description", style="white")
    
    for i, preset in enumerate(PRESET_PROMPTS, 1):
        table.add_row(
            str(i),
            preset["name"],
            str(preset["persona_count"]),
            preset["prompt"][:80] + "..." if len(preset["prompt"]) > 80 else preset["prompt"]
        )
    
    console.print(table)
    console.print("\n[dim]Use --preset <number> to generate a specific preset[/dim]")


async def interactive_mode():
    """Interactive scenario generation"""
    console.print("\n[bold cyan]╔══════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║   Scenario Generator - Interactive   ║[/bold cyan]")
    console.print("[bold cyan]╚══════════════════════════════════════╝[/bold cyan]\n")
    
    # Show some examples
    console.print("[dim]Examples:[/dim]")
    console.print("  • A tornado hits a small farming community")
    console.print("  • Alien first contact at the United Nations")
    console.print("  • A heist at a high-security museum")
    console.print()
    
    prompt = Prompt.ask("[bold]Describe your scenario[/bold]")
    
    if not prompt or len(prompt) < 10:
        console.print("[red]Prompt too short. Please provide more detail.[/red]")
        return
    
    persona_count_str = Prompt.ask(
        "Number of personas",
        default="50"
    )
    persona_count = int(persona_count_str)
    
    if persona_count < 2 or persona_count > 100:
        console.print("[red]Persona count must be between 2 and 100.[/red]")
        return
    
    console.print()
    await generate_single(prompt, persona_count)


async def generate_single(prompt: str, persona_count: int, suggested_name: str = None):
    """Generate a single scenario"""
    console.print(f"[cyan]Generating scenario...[/cyan]")
    console.print(f"  Prompt: [dim]{prompt}[/dim]")
    console.print(f"  Personas: [dim]{persona_count}[/dim]\n")
    
    try:
        generator = ScenarioGenerator()
        
        with console.status("[cyan]Calling AI to generate scenario...[/cyan]"):
            scenario = await generator.generate(
                prompt=prompt,
                persona_count=persona_count,
            )
        
        # Save to file
        filepath = save_scenario(scenario)
        
        console.print(f"[green]✓[/green] Generated: [bold]{scenario.name}[/bold]")
        console.print(f"[green]✓[/green] Saved to: [dim]{filepath}[/dim]")
        console.print(f"[green]✓[/green] Agents: {len(scenario.agent_templates)}")
        console.print(f"[green]✓[/green] Max steps: {scenario.config.max_steps}")
        console.print()
        
        # Show brief summary
        console.print("[bold]Description:[/bold]")
        console.print(f"  {scenario.description}\n")
        
    except Exception as e:
        console.print(f"[red]✗ Generation failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def batch_mode(count: int):
    """Generate multiple scenarios from presets"""
    console.print(f"\n[bold cyan]Batch Generation Mode[/bold cyan]")
    console.print(f"Generating {count} scenarios from presets...\n")
    
    # Select random presets
    import random
    selected_presets = random.sample(PRESET_PROMPTS, min(count, len(PRESET_PROMPTS)))
    
    for i, preset in enumerate(selected_presets, 1):
        console.print(f"[bold]Scenario {i}/{len(selected_presets)}[/bold]")
        await generate_single(
            preset["prompt"],
            preset["persona_count"],
            preset["name"]
        )
        
        if i < len(selected_presets):
            console.print("[dim]" + "─" * 60 + "[/dim]\n")
    
    console.print(f"[green]✓ Batch generation complete![/green]")
    console.print(f"[green]✓ Generated {len(selected_presets)} scenarios in {SCENARIOS_DIR}[/green]")


if __name__ == "__main__":
    main()
