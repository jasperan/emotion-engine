"""Tests for the scenario configurations"""
import pytest

from emotionsim.scenarios.rising_flood import create_rising_flood_scenario, get_rising_flood_config
from emotionsim.scenarios.airplane_crash import create_airplane_crash_scenario, get_airplane_crash_config
from emotionsim.scenarios.mass_casualty import create_mass_casualty_scenario, get_mass_casualty_config
from emotionsim.scenarios.philippines_tsunami import create_philippines_tsunami_scenario, get_philippines_tsunami_config
from emotionsim.scenarios.alien_signal import create_alien_signal_scenario, get_alien_signal_config
from emotionsim.scenarios.sinking_ship import create_sinking_ship_scenario, get_sinking_ship_config
from emotionsim.scenarios.iceland_volcano import create_iceland_volcano_scenario, get_iceland_volcano_config
from emotionsim.scenarios.space_station import create_space_station_scenario, get_space_station_config
from emotionsim.scenarios.bushfire import create_bushfire_scenario, get_bushfire_config


class TestRisingFloodScenario:
    """Tests for the Rising Flood scenario"""

    def test_create_scenario(self):
        """Test creating the Rising Flood scenario"""
        scenario = create_rising_flood_scenario(num_agents=8)

        assert scenario.name.startswith("Rising Flood")
        assert len(scenario.agent_templates) == 9  # 8 humans + 1 environment

    def test_scenario_config(self):
        """Test getting the scenario configuration as dict"""
        config = get_rising_flood_config()

        assert "name" in config
        assert "description" in config
        assert "config" in config
        assert "agent_templates" in config

        assert config["name"].startswith("Rising Flood")

    def test_locations(self):
        """Test that locations are properly configured"""
        scenario = create_rising_flood_scenario(num_agents=8)
        locations = scenario.config.initial_state["locations"]

        assert "shelter" in locations
        assert "street" in locations
        assert "rooftop" in locations
        assert "bridge" in locations

        # Check location connections
        shelter = locations["shelter"]
        assert "nearby" in shelter
        assert "street" in shelter["nearby"]

    def test_personas(self):
        """Test that personas are properly configured"""
        scenario = create_rising_flood_scenario(num_agents=8)

        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        assert len(human_templates) == 8

        # Check each has a persona
        for template in human_templates:
            assert template.persona is not None
            assert template.persona.name is not None
            assert template.persona.location is not None

    def test_goals(self):
        """Test that agents have goals focused on saving lives"""
        scenario = create_rising_flood_scenario(num_agents=8)

        human_templates = [t for t in scenario.agent_templates if t.role == "human"]

        for template in human_templates:
            assert len(template.goals) > 0
            # At least one goal should mention saving/helping
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["save", "help", "rescue", "safety"])


class TestAirplaneCrashScenario:
    """Tests for the Airplane Crash scenario"""

    def test_create_scenario(self):
        """Test creating the Airplane Crash scenario"""
        scenario = create_airplane_crash_scenario(num_agents=8)

        assert scenario.name.startswith("Airplane Crash Investigation")
        assert len(scenario.agent_templates) == 9  # 8 humans + 1 environment

    def test_scenario_config(self):
        """Test getting the scenario configuration as dict"""
        config = get_airplane_crash_config()

        assert config["name"].startswith("Airplane Crash Investigation")
        assert "crash" in config["description"].lower()

    def test_locations(self):
        """Test that locations are properly configured"""
        scenario = create_airplane_crash_scenario(num_agents=8)
        locations = scenario.config.initial_state["locations"]

        assert "crash_site" in locations
        assert "hilltop" in locations
        assert "community_center" in locations
        assert "perimeter" in locations

        # Check for observations/clues
        crash_site = locations["crash_site"]
        assert "observations" in crash_site
        assert len(crash_site["observations"]) > 0

    def test_diverse_personas(self):
        """Test that personas have diverse expertise"""
        scenario = create_airplane_crash_scenario(num_agents=8)

        human_templates = [t for t in scenario.agent_templates if t.role == "human"]

        occupations = [t.persona.occupation for t in human_templates]

        # Should have diverse occupations
        assert len(set(occupations)) > 1

        # Should have some relevant expertise
        occupation_text = " ".join(occupations).lower()
        assert "pilot" in occupation_text or "aviation" in occupation_text
        assert "doctor" in occupation_text or "physician" in occupation_text

    def test_investigation_focus(self):
        """Test that scenario has investigation elements"""
        scenario = create_airplane_crash_scenario(num_agents=8)
        initial_state = scenario.config.initial_state

        # Should have clues
        assert "clues" in initial_state
        assert "witness_reports" in initial_state["clues"]

        # Goals should include investigation
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        for template in human_templates:
            goal_text = " ".join(template.goals).lower()
            assert "investigate" in goal_text or "information" in goal_text or "save" in goal_text


class TestMassCasualtyScenario:
    """Tests for the Mass Casualty scenario"""

    def test_create_scenario(self):
        """Test creating the Mass Casualty scenario"""
        scenario = create_mass_casualty_scenario(num_agents=10)

        assert "Mass Casualty" in scenario.name
        assert len(scenario.agent_templates) == 11  # 10 humans + 1 environment

    def test_scenario_config(self):
        """Test getting the scenario configuration as dict"""
        config = get_mass_casualty_config()

        assert "Mass Casualty" in config["name"]
        assert "collapse" in config["description"].lower() or "building" in config["description"].lower()

    def test_locations(self):
        """Test that locations are properly configured for mass casualty"""
        scenario = create_mass_casualty_scenario(num_agents=10)
        locations = scenario.config.initial_state["locations"]

        assert "collapse_zone" in locations
        assert "triage_area" in locations
        assert "command_post" in locations
        assert "safe_zone" in locations

    def test_first_responders(self):
        """Test that scenario includes first responders"""
        scenario = create_mass_casualty_scenario(num_agents=10)

        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        occupations = [t.persona.occupation.lower() for t in human_templates]

        # Should have first responders
        occupation_text = " ".join(occupations)
        assert any(word in occupation_text for word in ["fire", "paramedic", "doctor", "nurse"])

    def test_triage_elements(self):
        """Test that scenario has triage elements"""
        scenario = create_mass_casualty_scenario(num_agents=10)
        initial_state = scenario.config.initial_state

        # Should have triage status
        assert "triage_status" in initial_state
        assert "red_critical" in initial_state["triage_status"]

        # Should track survivors
        assert "trapped_survivors" in initial_state

    def test_goals_focus_on_saving_lives(self):
        """Test that goals are focused on saving lives"""
        scenario = create_mass_casualty_scenario(num_agents=10)

        human_templates = [t for t in scenario.agent_templates if t.role == "human"]

        for template in human_templates:
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["save", "rescue", "triage", "lives", "coordinate"])


class TestPhilippinesTsunamiScenario:
    """Tests for the Philippines Mega-Tsunami scenario"""

    def test_create_scenario(self):
        scenario = create_philippines_tsunami_scenario(num_agents=10)
        assert "Philippines" in scenario.name or "Tsunami" in scenario.name
        assert len(scenario.agent_templates) == 11  # 10 humans + 1 environment

    def test_scenario_config(self):
        config = get_philippines_tsunami_config()
        assert "name" in config
        assert "description" in config
        assert "config" in config
        assert "agent_templates" in config

    def test_locations(self):
        scenario = create_philippines_tsunami_scenario(num_agents=10)
        locations = scenario.config.initial_state["locations"]
        assert "coastal_village" in locations
        assert "hilltop_evacuation" in locations
        assert "church_plaza" in locations
        assert "school_rooftop" in locations

    def test_personas(self):
        scenario = create_philippines_tsunami_scenario(num_agents=10)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        assert len(human_templates) == 10
        for template in human_templates:
            assert template.persona is not None
            assert template.persona.location is not None

    def test_goals(self):
        scenario = create_philippines_tsunami_scenario(num_agents=10)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        for template in human_templates:
            assert len(template.goals) > 0
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["save", "help", "rescue", "supplies", "communicate"])


class TestAlienSignalScenario:
    """Tests for the Alien Signal scenario"""

    def test_create_scenario(self):
        scenario = create_alien_signal_scenario(num_agents=10)
        assert "Alien" in scenario.name or "Signal" in scenario.name
        assert len(scenario.agent_templates) == 11

    def test_scenario_config(self):
        config = get_alien_signal_config()
        assert "name" in config
        assert "signal" in config["description"].lower() or "alien" in config["description"].lower()

    def test_locations(self):
        scenario = create_alien_signal_scenario(num_agents=10)
        locations = scenario.config.initial_state["locations"]
        assert "control_room" in locations
        assert "antenna_array" in locations
        assert "military_checkpoint" in locations
        assert "indigenous_village" in locations

    def test_diverse_personas(self):
        scenario = create_alien_signal_scenario(num_agents=10)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        occupations = [t.persona.occupation for t in human_templates]
        assert len(set(occupations)) > 3  # highly diverse cast

    def test_goals(self):
        scenario = create_alien_signal_scenario(num_agents=10)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        for template in human_templates:
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["signal", "decode", "consensus", "respond", "balance"])


class TestSinkingShipScenario:
    """Tests for the Sinking Cruise Ship scenario"""

    def test_create_scenario(self):
        scenario = create_sinking_ship_scenario(num_agents=10)
        assert "Sinking" in scenario.name or "Cruise" in scenario.name or "Ship" in scenario.name
        assert len(scenario.agent_templates) == 11

    def test_scenario_config(self):
        config = get_sinking_ship_config()
        assert "ship" in config["description"].lower() or "sink" in config["description"].lower()

    def test_locations(self):
        scenario = create_sinking_ship_scenario(num_agents=10)
        locations = scenario.config.initial_state["locations"]
        assert "bridge" in locations
        assert "engine_room" in locations
        assert "refugee_hold" in locations

    def test_moral_dilemma_elements(self):
        scenario = create_sinking_ship_scenario(num_agents=12)
        initial_state = scenario.config.initial_state
        assert "lifeboat_capacity" in initial_state
        assert "passengers_total" in initial_state
        # Lifeboats should be insufficient
        assert initial_state["lifeboat_capacity"] < initial_state["passengers_total"]

    def test_goals(self):
        scenario = create_sinking_ship_scenario(num_agents=10)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        for template in human_templates:
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["evacuate", "lifeboat", "rescue", "refugee", "pump"])


class TestIcelandVolcanoScenario:
    """Tests for the Iceland Volcano scenario"""

    def test_create_scenario(self):
        scenario = create_iceland_volcano_scenario(num_agents=9)
        assert "Volcan" in scenario.name or "Eruption" in scenario.name
        assert len(scenario.agent_templates) == 10  # 9 humans + 1 environment

    def test_scenario_config(self):
        config = get_iceland_volcano_config()
        assert "volcan" in config["description"].lower() or "erupt" in config["description"].lower()

    def test_locations(self):
        scenario = create_iceland_volcano_scenario(num_agents=9)
        locations = scenario.config.initial_state["locations"]
        assert "seismic_station" in locations
        assert "blue_lagoon_resort" in locations
        assert "town_hall" in locations
        assert "geothermal_plant" in locations

    def test_slow_burn_dynamics(self):
        scenario = create_iceland_volcano_scenario(num_agents=9)
        dynamics = scenario.config.dynamics
        assert "seismic_escalation_rate" in dynamics or "eruption_probability_growth" in dynamics
        # Hazard starts LOW — this is a slow-burn scenario
        assert scenario.config.initial_state["hazard_level"] <= 4

    def test_goals(self):
        scenario = create_iceland_volcano_scenario(num_agents=9)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        for template in human_templates:
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["assess", "evacuate", "data", "protect", "balance"])


class TestSpaceStationScenario:
    """Tests for the ISS Cascade Failure scenario"""

    def test_create_scenario(self):
        scenario = create_space_station_scenario(num_agents=9)
        assert "ISS" in scenario.name or "Station" in scenario.name
        assert len(scenario.agent_templates) == 10

    def test_scenario_config(self):
        config = get_space_station_config()
        assert "station" in config["description"].lower() or "ISS" in config["description"]

    def test_locations(self):
        scenario = create_space_station_scenario(num_agents=9)
        locations = scenario.config.initial_state["locations"]
        assert "us_lab_destiny" in locations
        assert "russian_module_zvezda" in locations
        assert "soyuz_capsule" in locations
        assert "crew_dragon" in locations

    def test_escape_capsules(self):
        scenario = create_space_station_scenario(num_agents=11)
        initial_state = scenario.config.initial_state
        assert "escape_capsule_seats" in initial_state or "crew_aboard" in initial_state

    def test_goals(self):
        scenario = create_space_station_scenario(num_agents=9)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        for template in human_templates:
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["stabilize", "repair", "evacuat", "seal", "resolve"])


class TestBushfireScenario:
    """Tests for the Australian Bushfire scenario"""

    def test_create_scenario(self):
        scenario = create_bushfire_scenario(num_agents=10)
        assert "Bushfire" in scenario.name or "Fire" in scenario.name
        assert len(scenario.agent_templates) == 11

    def test_scenario_config(self):
        config = get_bushfire_config()
        assert "bushfire" in config["description"].lower() or "fire" in config["description"].lower()

    def test_locations(self):
        scenario = create_bushfire_scenario(num_agents=10)
        locations = scenario.config.initial_state["locations"]
        assert "town_center" in locations
        assert "dharawal_trail_entrance" in locations
        assert "mountain_pass_trailhead" in locations
        assert "rfs_staging_area" in locations

    def test_dual_escape_routes(self):
        scenario = create_bushfire_scenario(num_agents=10)
        locations = scenario.config.initial_state["locations"]
        # Both escape routes should exist
        assert "mountain_pass_trailhead" in locations
        assert "dharawal_trail_entrance" in locations

    def test_goals(self):
        scenario = create_bushfire_scenario(num_agents=10)
        human_templates = [t for t in scenario.agent_templates if t.role == "human"]
        for template in human_templates:
            goal_text = " ".join(template.goals).lower()
            assert any(word in goal_text for word in ["evacuat", "route", "negotiate", "protect", "split"])


class TestScenarioCompatibility:
    """Tests to ensure scenarios work with the conversation system"""

    def _all_scenarios(self):
        return [
            create_rising_flood_scenario(num_agents=5),
            create_airplane_crash_scenario(num_agents=5),
            create_mass_casualty_scenario(num_agents=5),
            create_philippines_tsunami_scenario(num_agents=5),
            create_alien_signal_scenario(num_agents=5),
            create_sinking_ship_scenario(num_agents=5),
            create_iceland_volcano_scenario(num_agents=5),
            create_space_station_scenario(num_agents=5),
            create_bushfire_scenario(num_agents=5),
        ]

    def test_all_scenarios_have_locations(self):
        """Test that all scenarios have location-based setup"""
        for scenario in self._all_scenarios():
            locations = scenario.config.initial_state.get("locations", {})
            assert len(locations) >= 3, f"{scenario.name} should have at least 3 locations"

            # Each location should have nearby
            for loc_name, loc_data in locations.items():
                assert "nearby" in loc_data, f"{loc_name} in {scenario.name} should have nearby"

    def test_all_personas_have_locations(self):
        """Test that all personas have starting locations"""
        for scenario in self._all_scenarios():
            human_templates = [t for t in scenario.agent_templates if t.role == "human"]
            locations = set(scenario.config.initial_state.get("locations", {}).keys())

            for template in human_templates:
                assert template.persona.location is not None
                assert template.persona.location in locations, \
                    f"{template.name}'s location {template.persona.location} not in {scenario.name} locations"

    def test_movement_possible(self):
        """Test that agents can move between locations"""
        for scenario in self._all_scenarios():
            locations = scenario.config.initial_state.get("locations", {})

            # Check that locations form a connected graph
            all_locations = set(locations.keys())
            reachable = set()

            # Start from first location
            if not all_locations:
                continue

            to_visit = [list(all_locations)[0]]

            while to_visit:
                current = to_visit.pop()
                if current in reachable:
                    continue
                reachable.add(current)

                nearby = locations.get(current, {}).get("nearby", [])
                for neighbor in nearby:
                    if neighbor in all_locations and neighbor not in reachable:
                        to_visit.append(neighbor)

            assert reachable == all_locations, \
                f"Not all locations reachable in {scenario.name}: {all_locations - reachable}"
