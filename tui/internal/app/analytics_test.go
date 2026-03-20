package app

import "testing"

func TestAnalyticsScenarioCycling(t *testing.T) {
	m := AnalyticsModel{
		scenarios:   []string{"All", "Rising Flood", "Tsunami"},
		selScenario: 0,
	}
	m.selScenario = (m.selScenario + 1) % len(m.scenarios)
	if m.scenarios[m.selScenario] != "Rising Flood" {
		t.Errorf("expected Rising Flood, got %q", m.scenarios[m.selScenario])
	}
	m.selScenario = (m.selScenario + 1) % len(m.scenarios)
	if m.scenarios[m.selScenario] != "Tsunami" {
		t.Errorf("expected Tsunami, got %q", m.scenarios[m.selScenario])
	}
	m.selScenario = (m.selScenario + 1) % len(m.scenarios)
	if m.scenarios[m.selScenario] != "All" {
		t.Errorf("expected All wrap, got %q", m.scenarios[m.selScenario])
	}
}

func TestAnalyticsUnavailable(t *testing.T) {
	m := AnalyticsModel{available: false}
	view := m.View(80, 40)
	if view == "" {
		t.Error("expected non-empty view when unavailable")
	}
}
