package components

import (
	"strings"
	"testing"
)

func TestRenderSpatialMap_Empty(t *testing.T) {
	out := RenderSpatialMap(SpatialMapData{})
	if out == "" {
		t.Fatal("expected non-empty output for empty data")
	}
	if !strings.Contains(out, "No locations") {
		t.Errorf("expected empty-state message, got: %q", out)
	}
}

func TestRenderSpatialMap_WithLocations(t *testing.T) {
	data := SpatialMapData{
		Locations: []MapLocation{
			{
				Name:        "Town Square",
				Agents:      []string{"Alice", "Bob"},
				ConnectedTo: []string{"Riverside"},
			},
			{
				Name:   "Riverside",
				Agents: []string{"Charlie"},
				Hazard: true,
			},
		},
	}

	out := RenderSpatialMap(data)

	if out == "" {
		t.Fatal("expected non-empty output")
	}
	if !strings.Contains(out, "Town Square") {
		t.Errorf("expected 'Town Square' in output")
	}
	if !strings.Contains(out, "Riverside") {
		t.Errorf("expected 'Riverside' in output")
	}
	if !strings.Contains(out, "Alice") {
		t.Errorf("expected agent 'Alice' in output")
	}
	if !strings.Contains(out, "Charlie") {
		t.Errorf("expected agent 'Charlie' in output")
	}
	if !strings.Contains(out, "SPATIAL MAP") {
		t.Errorf("expected 'SPATIAL MAP' header in output")
	}
}

func TestRenderSpatialMap_WithTravels(t *testing.T) {
	data := SpatialMapData{
		Locations: []MapLocation{
			{Name: "Alpha Base", Agents: []string{"Eve"}},
			{Name: "Beta Camp", Agents: []string{}},
		},
		Travels: []MapTravel{
			{
				AgentName: "Dave",
				From:      "Alpha Base",
				To:        "Beta Camp",
				Progress:  0.6,
			},
		},
	}

	out := RenderSpatialMap(data)

	if !strings.Contains(out, "IN TRANSIT") {
		t.Errorf("expected 'IN TRANSIT' section in output")
	}
	if !strings.Contains(out, "Dave") {
		t.Errorf("expected travelling agent 'Dave' in output")
	}
	if !strings.Contains(out, "Alpha Base") {
		t.Errorf("expected 'Alpha Base' in output")
	}
	if !strings.Contains(out, "Beta Camp") {
		t.Errorf("expected 'Beta Camp' in output")
	}
	if !strings.Contains(out, "60%") {
		t.Errorf("expected '60%%' progress in output")
	}
}
