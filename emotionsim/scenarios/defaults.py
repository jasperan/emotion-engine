"""Default, built-in scenarios"""

from emotionsim.scenarios.airplane_crash import create_airplane_crash_scenario
from emotionsim.scenarios.mass_casualty import create_mass_casualty_scenario
from emotionsim.scenarios.rising_flood import create_rising_flood_scenario
from emotionsim.scenarios.philippines_tsunami import create_philippines_tsunami_scenario
from emotionsim.scenarios.alien_signal import create_alien_signal_scenario
from emotionsim.scenarios.sinking_ship import create_sinking_ship_scenario
from emotionsim.scenarios.iceland_volcano import create_iceland_volcano_scenario
from emotionsim.scenarios.space_station import create_space_station_scenario
from emotionsim.scenarios.bushfire import create_bushfire_scenario

# A list of all default scenarios that can be created automatically
DEFAULT_SCENARIOS = {
    "Airplane Crash Investigation (10 agents)": lambda: create_airplane_crash_scenario(10),
    "Mass Casualty: Building Collapse (10 agents)": lambda: create_mass_casualty_scenario(10),
    "Rising Flood (10 agents)": lambda: create_rising_flood_scenario(10),
    "Philippines Mega-Tsunami (12 agents)": lambda: create_philippines_tsunami_scenario(12),
    "First Contact: Alien Signal (12 agents)": lambda: create_alien_signal_scenario(12),
    "Sinking Cruise Ship (12 agents)": lambda: create_sinking_ship_scenario(12),
    "Volcanic Eruption Warning (11 agents)": lambda: create_iceland_volcano_scenario(11),
    "ISS Cascade Failure (11 agents)": lambda: create_space_station_scenario(11),
    "Australian Bushfire Encirclement (12 agents)": lambda: create_bushfire_scenario(12),
}
