"""Pre-built scenario configurations"""
from app.scenarios.rising_flood import create_rising_flood_scenario, get_rising_flood_config
from app.scenarios.airplane_crash import create_airplane_crash_scenario, get_airplane_crash_config
from app.scenarios.mass_casualty import create_mass_casualty_scenario, get_mass_casualty_config

__all__ = [
    "create_rising_flood_scenario",
    "get_rising_flood_config",
    "create_airplane_crash_scenario",
    "get_airplane_crash_config",
    "create_mass_casualty_scenario",
    "get_mass_casualty_config",
]

