#!/usr/bin/env python3
"""EmotionSim CLI - run from project root.

All CLI functionality accessible from the project root directory.

Usage:
    python cli.py                              # Interactive menu
    python cli.py run -s "Rising Flood" --simple
    python cli.py run -s "Rising Flood" --max-steps 50 --seed 42
    python cli.py scenarios                    # List scenarios
    python cli.py scenarios --create-builtin   # Create built-in scenarios
    python cli.py status                       # Check backend health
    python cli.py best                         # Show best simulation runs
    python cli.py auto --count 5               # Batch auto-run
    python cli.py interactive                  # Guided wizard
    python cli.py monitor --run-id <id>        # Monitor via WebSocket
"""

import os
import sys


def main():
    # Ensure backend is on sys.path
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Change to backend dir so relative imports, .env, and configs work
    os.chdir(backend_dir)

    from app.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
