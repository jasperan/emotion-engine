package components

import (
	"strings"
	"testing"
)

func TestRenderAgentPane_Basic(t *testing.T) {
	d := AgentPaneData{
		Name:   "Maria",
		Active: true,
		Tokens: "Hello world",
		Step:   5,
	}
	result := RenderAgentPane(d, 40, 10)
	if result == "" {
		t.Error("expected non-empty pane")
	}
}

func TestRenderAgentPane_Enriched(t *testing.T) {
	d := AgentPaneData{
		Name:         "Maria",
		Occupation:   "Nurse",
		Age:          34,
		Health:       85,
		Stress:       42,
		Location:     "Shelter",
		PlanGoal:     "Triage wounded",
		PlanProgress: "60%",
		Step:         12,
	}
	result := RenderAgentPane(d, 50, 14)
	if result == "" {
		t.Error("expected non-empty enriched pane")
	}
	for _, want := range []string{"Nurse", "HP:85", "ST:42", "@Shelter", "Triage wounded"} {
		if !strings.Contains(result, want) {
			t.Errorf("expected %q in enriched output", want)
		}
	}
}

func TestRenderAgentPane_ZeroHealth(t *testing.T) {
	d := AgentPaneData{
		Name:     "Dead Agent",
		Location: "River",
		Health:   0,
		Stress:   0,
		Step:     5,
	}
	result := RenderAgentPane(d, 50, 12)
	if !strings.Contains(result, "HP:0") {
		t.Error("HP:0 should be visible for dead agent")
	}
	if !strings.Contains(result, "ST:0") {
		t.Error("ST:0 should be visible when enrichment data present")
	}
}

func TestRenderAgentPane_NoEnrichment(t *testing.T) {
	d := AgentPaneData{Name: "Agent", Step: 1}
	result := RenderAgentPane(d, 40, 8)
	if result == "" {
		t.Error("expected non-empty pane")
	}
	// No enrichment fields set, so HP/ST lines should NOT appear
	if strings.Contains(result, "HP:") {
		t.Error("HP should not appear when no enrichment data")
	}
}
