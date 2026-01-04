"""Default, built-in scenarios"""

from app.scenarios.airplane_crash import create_airplane_crash_scenario
from app.scenarios.mass_casualty import create_mass_casualty_scenario
from app.scenarios.rising_flood import create_rising_flood_scenario

# A list of all default scenarios that can be created automatically
DEFAULT_SCENARIOS = {
    "Airplane Crash Investigation (10 agents)": lambda: create_airplane_crash_scenario(10),
    "Airplane Crash Investigation (50 agents)": lambda: create_airplane_crash_scenario(50),
    "Airplane Crash Investigation (100 agents)": lambda: create_airplane_crash_scenario(100),
    "Mass Casualty: Building Collapse (10 agents)": lambda: create_mass_casualty_scenario(10),
    "Mass Casualty: Building Collapse (50 agents)": lambda: create_mass_casualty_scenario(50),
    "Mass Casualty: Building Collapse (100 agents)": lambda: create_mass_casualty_scenario(100),
    "Rising Flood (10 agents)": lambda: create_rising_flood_scenario(10),
    "Rising Flood (50 agents)": lambda: create_rising_flood_scenario(50),
    "Rising Flood (100 agents)": lambda: create_rising_flood_scenario(100),
}
