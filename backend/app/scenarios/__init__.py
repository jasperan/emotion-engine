"""Pre-built scenario configurations"""
from app.scenarios.rising_flood import create_rising_flood_scenario, get_rising_flood_config
from app.scenarios.airplane_crash import create_airplane_crash_scenario, get_airplane_crash_config
from app.scenarios.mass_casualty import create_mass_casualty_scenario, get_mass_casualty_config
from app.scenarios.philippines_tsunami import create_philippines_tsunami_scenario, get_philippines_tsunami_config
from app.scenarios.alien_signal import create_alien_signal_scenario, get_alien_signal_config
from app.scenarios.sinking_ship import create_sinking_ship_scenario, get_sinking_ship_config
from app.scenarios.iceland_volcano import create_iceland_volcano_scenario, get_iceland_volcano_config
from app.scenarios.space_station import create_space_station_scenario, get_space_station_config
from app.scenarios.bushfire import create_bushfire_scenario, get_bushfire_config

__all__ = [
    "create_rising_flood_scenario",
    "get_rising_flood_config",
    "create_airplane_crash_scenario",
    "get_airplane_crash_config",
    "create_mass_casualty_scenario",
    "get_mass_casualty_config",
    "create_philippines_tsunami_scenario",
    "get_philippines_tsunami_config",
    "create_alien_signal_scenario",
    "get_alien_signal_config",
    "create_sinking_ship_scenario",
    "get_sinking_ship_config",
    "create_iceland_volcano_scenario",
    "get_iceland_volcano_config",
    "create_space_station_scenario",
    "get_space_station_config",
    "create_bushfire_scenario",
    "get_bushfire_config",
]
