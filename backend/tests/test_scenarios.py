"""Tests for the scenario configurations"""
import pytest

from app.scenarios.rising_flood import create_rising_flood_scenario, get_rising_flood_config
from app.scenarios.airplane_crash import create_airplane_crash_scenario, get_airplane_crash_config
from app.scenarios.mass_casualty import create_mass_casualty_scenario, get_mass_casualty_config


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


class TestScenarioCompatibility:
    """Tests to ensure scenarios work with the conversation system"""
    
    def test_all_scenarios_have_locations(self):
        """Test that all scenarios have location-based setup"""
        scenarios = [
            create_rising_flood_scenario(num_agents=5),
            create_airplane_crash_scenario(num_agents=5),
            create_mass_casualty_scenario(num_agents=5),
        ]
        
        for scenario in scenarios:
            locations = scenario.config.initial_state.get("locations", {})
            assert len(locations) >= 3, f"{scenario.name} should have at least 3 locations"
            
            # Each location should have nearby
            for loc_name, loc_data in locations.items():
                assert "nearby" in loc_data, f"{loc_name} in {scenario.name} should have nearby"
    
    def test_all_personas_have_locations(self):
        """Test that all personas have starting locations"""
        scenarios = [
            create_rising_flood_scenario(num_agents=5),
            create_airplane_crash_scenario(num_agents=5),
            create_mass_casualty_scenario(num_agents=5),
        ]
        
        for scenario in scenarios:
            human_templates = [t for t in scenario.agent_templates if t.role == "human"]
            locations = set(scenario.config.initial_state.get("locations", {}).keys())
            
            for template in human_templates:
                assert template.persona.location is not None
                assert template.persona.location in locations, \
                    f"{template.name}'s location {template.persona.location} not in {scenario.name} locations"
    
    def test_movement_possible(self):
        """Test that agents can move between locations"""
        scenarios = [
            create_rising_flood_scenario(num_agents=5),
            create_airplane_crash_scenario(num_agents=5),
            create_mass_casualty_scenario(num_agents=5),
        ]
        
        for scenario in scenarios:
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


