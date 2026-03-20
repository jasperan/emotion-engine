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
	if !strings.Contains(result, "Nurse") {
		t.Error("expected occupation in output")
	}
}

func TestRenderAgentPane_NoEnrichment(t *testing.T) {
	d := AgentPaneData{Name: "Agent", Step: 1}
	result := RenderAgentPane(d, 40, 8)
	if result == "" {
		t.Error("expected non-empty pane")
	}
}
