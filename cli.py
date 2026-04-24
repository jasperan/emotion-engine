#!/usr/bin/env python3
"""EmotionSim CLI entry point.

Runs the installed `emotionsim` package. After `pip install -e .` at the repo
root, the `emotionsim` console script is also available directly.
"""

from emotionsim.cli import main


if __name__ == "__main__":
    main()
