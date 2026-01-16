#!/usr/bin/env python3
"""Emotion Engine CLI Interface"""
import os
import sys
import asyncio
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import print as rprint

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scenarios.generator import ScenarioGenerator
from app.scenarios.storage import save_scenario, SCENARIOS_DIR

console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear_screen()
    title = """
    ╔════════════════════════════════════════════════════════════════╗
    ║                 EMOTION ENGINE CLI                             ║
    ║             Autonomous Agent Scenario Generator                ║
    ╚════════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(title, style="bold magenta", border_style="magenta"))

async def generate_scenario_interactive():
    print_header()
    console.print("[bold yellow]Generate New Scenario[/bold yellow]")
    
    console.print("[dim]Examples: 'A tornado hits a small town', 'Alien first contact', 'Heist at a museum'[/dim]\n")
    
    prompt = Prompt.ask("[bold]Describe your scenario[/bold]")
    if not prompt:
        return

    persona_count = IntPrompt.ask("Number of personas", default=10)
    
    console.print(f"\n[cyan]Generating scenario with {persona_count} agents...[/cyan]")
    
    try:
        generator = ScenarioGenerator()
        with console.status("[cyan]Calling AI to generate scenario...[/cyan]"):
            scenario = await generator.generate(
                prompt=prompt,
                persona_count=persona_count,
            )
        
        filepath = save_scenario(scenario)
        
        console.print(f"\n[green]✓[/green] Generated: [bold]{scenario.name}[/bold]")
        console.print(f"[green]✓[/green] Saved to: [dim]{filepath}[/dim]")
        
        console.print("\n[bold]Description:[/bold]")
        console.print(f"  {scenario.description}\n")
        
    except Exception as e:
        console.print(f"[red]Generation failed: {e}[/red]")

def list_scenarios():
    print_header()
    console.print("[bold yellow]Browse Scenarios[/bold yellow]")
    
    if not os.path.exists(SCENARIOS_DIR):
        console.print("[yellow]No scenarios directory found.[/yellow]")
        return
        
    files = sorted([f for f in os.listdir(SCENARIOS_DIR) if f.endswith('.json')], reverse=True)
    
    if not files:
        console.print("[yellow]No scenarios found.[/yellow]")
        return
        
    table = Table(title=f"Scenarios in {SCENARIOS_DIR}")
    table.add_column("Filename", style="cyan")
    table.add_column("Size (KB)", justify="right")
    
    for f in files:
        size = os.path.getsize(os.path.join(SCENARIOS_DIR, f)) / 1024
        table.add_row(f, f"{size:.2f}")
        
    console.print(table)

def main_menu():
    while True:
        print_header()
        console.print("[bold]Select a Task:[/bold]")
        
        table = Table(show_header=False, box=None)
        table.add_row("[1]", "Generate New Scenario", style="magenta")
        table.add_row("[2]", "Browse Scenarios", style="cyan")
        table.add_row("[0]", "Exit", style="red")
        
        console.print(table)
        
        choice = Prompt.ask("\nEnter choice", choices=["1", "2", "0"], default="1")
        
        if choice == "1":
            asyncio.run(generate_scenario_interactive())
            input("\nPress Enter to continue...")
        elif choice == "2":
            list_scenarios()
            input("\nPress Enter to continue...")
        elif choice == "0":
            console.print("[bold]Goodbye![/bold]")
            sys.exit(0)

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted. Exiting...[/bold red]")
        sys.exit(0)
