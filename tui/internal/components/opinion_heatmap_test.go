package components

import (
	"strings"
	"testing"
)

func TestRenderOpinionHeatmap_Empty(t *testing.T) {
	out := RenderOpinionHeatmap(OpinionHeatmapData{Width: 80, Height: 40})
	if !strings.Contains(out, "No opinion data yet") {
		t.Error("expected empty-state message for no stances")
	}
	if !strings.Contains(out, "SOCIAL DYNAMICS") {
		t.Error("expected title")
	}
}

func TestRenderOpinionHeatmap_WithStances(t *testing.T) {
	data := OpinionHeatmapData{
		Stances: []OpinionStance{
			{AgentName: "Alice", Topic: "evac", Value: 0.8},
			{AgentName: "Alice", Topic: "coop", Value: -0.5},
			{AgentName: "Bob", Topic: "evac", Value: -0.3},
			{AgentName: "Bob", Topic: "coop", Value: 0.9},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderOpinionHeatmap(data)

	if !strings.Contains(out, "SOCIAL DYNAMICS") {
		t.Error("expected title")
	}
	// Should contain agent names
	if !strings.Contains(out, "Alice") {
		t.Error("expected Alice in output")
	}
	if !strings.Contains(out, "Bob") {
		t.Error("expected Bob in output")
	}
	// Should contain topic headers
	if !strings.Contains(out, "coop") {
		t.Error("expected topic 'coop' in header")
	}
	// Should contain legend
	if !strings.Contains(out, "oppose") {
		t.Error("expected legend")
	}
}

func TestRenderOpinionHeatmap_TippingPoints(t *testing.T) {
	data := OpinionHeatmapData{
		Stances: []OpinionStance{
			{AgentName: "Alice", Topic: "evac", Value: 0.5},
		},
		TippingPoints: []TippingPointInfo{
			{Step: 10, Topic: "evac", Type: "convergence", MeanBefore: 0.2, MeanAfter: 0.7},
			{Step: 15, Topic: "evac", Type: "divergence", MeanBefore: 0.7, MeanAfter: 0.3},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderOpinionHeatmap(data)

	if !strings.Contains(out, "TIPPING POINTS") {
		t.Error("expected tipping points section")
	}
	if !strings.Contains(out, "evac") {
		t.Error("expected topic name in tipping points")
	}
}

func TestRenderOpinionHeatmap_InfluenceProfiles(t *testing.T) {
	data := OpinionHeatmapData{
		Stances: []OpinionStance{
			{AgentName: "Alice", Topic: "evac", Value: 0.8},
			{AgentName: "Bob", Topic: "evac", Value: -0.3},
		},
		Profiles: []InfluenceProfile{
			{AgentName: "Alice", IsSuperSpreader: true},
			{AgentName: "Bob", IsAnchor: true},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderOpinionHeatmap(data)

	if !strings.Contains(out, "spreader") {
		t.Error("expected spreader in legend")
	}
	if !strings.Contains(out, "anchor") {
		t.Error("expected anchor in legend")
	}
}

func TestRenderOpinionHeatmap_Convergence(t *testing.T) {
	data := OpinionHeatmapData{
		Stances: []OpinionStance{
			{AgentName: "Alice", Topic: "evac", Value: 0.5},
		},
		ConvergenceByTopic: map[string]float64{"evac": 0.85},
		Width:              80,
		Height:             40,
	}
	out := RenderOpinionHeatmap(data)

	if !strings.Contains(out, "convg") {
		t.Error("expected convergence row")
	}
}

func TestStanceColor_Range(t *testing.T) {
	// Verify stanceColor doesn't panic across range
	for v := -1.0; v <= 1.0; v += 0.1 {
		c := stanceColor(v)
		if c == "" {
			t.Errorf("stanceColor(%f) returned empty", v)
		}
	}
}

func TestStanceBlock_Range(t *testing.T) {
	for v := -1.0; v <= 1.0; v += 0.2 {
		b := stanceBlock(v)
		if b == "" {
			t.Errorf("stanceBlock(%f) returned empty", v)
		}
	}
}
