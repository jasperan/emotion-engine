package components

import (
	"strings"
	"testing"
)

func TestRenderNetworkMatrix_Empty(t *testing.T) {
	out := RenderNetworkMatrix(NetworkMatrixData{Width: 80, Height: 40})
	if !strings.Contains(out, "No agents yet") {
		t.Error("expected empty-state message")
	}
}

func TestRenderNetworkMatrix_TrustMode(t *testing.T) {
	data := NetworkMatrixData{
		Agents: []RelAgent{
			{ID: "1", Name: "Alice"},
			{ID: "2", Name: "Bob"},
			{ID: "3", Name: "Carol"},
		},
		Edges: []RelEdge{
			{AgentA: "Alice", AgentB: "Bob", Type: RelTrust, Strength: 0.7, Label: "vouched"},
			{AgentA: "Bob", AgentB: "Carol", Type: RelConflict, Strength: 0.5},
			{AgentA: "Alice", AgentB: "Carol", Type: RelAlliance, Strength: 0.9},
		},
		Mode:   NetworkTrust,
		Width:  80,
		Height: 40,
	}
	out := RenderNetworkMatrix(data)

	if !strings.Contains(out, "NETWORK: Trust") {
		t.Error("expected trust mode title")
	}
	if !strings.Contains(out, "Alice") {
		t.Error("expected Alice row")
	}
	if !strings.Contains(out, "Bob") {
		t.Error("expected Bob row")
	}
	// Legend should mention trust/conflict/alliance
	if !strings.Contains(out, "trust") {
		t.Error("expected trust in legend")
	}
	if !strings.Contains(out, "conflict") {
		t.Error("expected conflict in legend")
	}
}

func TestRenderNetworkMatrix_InfluenceMode(t *testing.T) {
	data := NetworkMatrixData{
		Agents: []RelAgent{
			{ID: "1", Name: "Alice"},
			{ID: "2", Name: "Bob"},
		},
		Influence: []InfluenceEdgeInfo{
			{Source: "Alice", Target: "Bob", Topic: "evac", TotalDelta: 0.3, InteractionCount: 5},
			{Source: "Bob", Target: "Alice", Topic: "evac", TotalDelta: -0.1, InteractionCount: 2},
		},
		Mode:   NetworkInfluence,
		Width:  80,
		Height: 40,
	}
	out := RenderNetworkMatrix(data)

	if !strings.Contains(out, "NETWORK: Influence") {
		t.Error("expected influence mode title")
	}
	if !strings.Contains(out, "positive") {
		t.Error("expected positive in legend")
	}
}

func TestRenderNetworkMatrix_Coalitions(t *testing.T) {
	data := NetworkMatrixData{
		Agents: []RelAgent{
			{ID: "1", Name: "Alice"},
			{ID: "2", Name: "Bob"},
		},
		Coalitions: []CoalitionInfo{
			{Name: "Group A", Members: []string{"Alice", "Bob"}, Strength: 0.85, Leader: "Alice"},
		},
		Mode:   NetworkTrust,
		Width:  80,
		Height: 40,
	}
	out := RenderNetworkMatrix(data)

	if !strings.Contains(out, "COALITIONS") {
		t.Error("expected coalitions section")
	}
	if !strings.Contains(out, "85%") {
		t.Error("expected coalition strength percentage")
	}
}

func TestCellColor_AllTypes(t *testing.T) {
	types := []RelEdgeType{RelTrust, RelConflict, RelAlliance, RelPending}
	strengths := []float64{0.1, 0.3, 0.6, 0.9}
	for _, et := range types {
		for _, s := range strengths {
			c := cellColor(et, s)
			if c == "" {
				t.Errorf("cellColor(%d, %f) returned empty", et, s)
			}
		}
	}
}

func TestInfluenceCellColor_Range(t *testing.T) {
	for _, delta := range []float64{-0.8, -0.3, 0.0, 0.1, 0.5} {
		c := influenceCellColor(delta)
		if c == "" {
			t.Errorf("influenceCellColor(%f) returned empty", delta)
		}
	}
}
