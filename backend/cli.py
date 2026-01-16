#!/usr/bin/env python3
"""Emotion Engine CLI Wrapper"""
import os
import sys
import asyncio

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.cli import main_menu_async
except ImportError:
    # Fallback if package structure is different
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app'))
    from app.cli import main_menu_async

if __name__ == "__main__":
    try:
        asyncio.run(main_menu_async())
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting...")
        sys.exit(0)
