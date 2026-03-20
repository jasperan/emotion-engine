package components

import (
	"strings"
	"testing"
)

func TestRenderRelationshipWeb_Empty(t *testing.T) {
	result := RenderRelationshipWeb(RelationshipWebData{
		Agents: nil,
		Edges:  nil,
		Width:  80,
		Height: 40,
	})
	if !strings.Contains(result, "No relationship data yet...") {
		t.Errorf("expected empty state message, got: %s", result)
	}
	if !strings.Contains(result, "RELATIONSHIPS") {
		t.Errorf("expected RELATIONSHIPS subtitle, got: %s", result)
	}
}

func TestRenderRelationshipWeb_WithEdges(t *testing.T) {
	agents := []RelAgent{
		{ID: "a1", Name: "Alice"},
		{ID: "a2", Name: "Bob"},
	}
	edges := []RelEdge{
		{AgentA: "Alice", AgentB: "Bob", Type: RelTrust, Strength: 0.7, Label: "vouched"},
	}
	result := RenderRelationshipWeb(RelationshipWebData{
		Agents: agents,
		Edges:  edges,
		Width:  80,
		Height: 40,
	})
	if !strings.Contains(result, "RELATIONSHIPS") {
		t.Errorf("expected RELATIONSHIPS subtitle")
	}
	if !strings.Contains(result, "Alice") {
		t.Errorf("expected Alice in output")
	}
	if !strings.Contains(result, "Bob") {
		t.Errorf("expected Bob in output")
	}
	if !strings.Contains(result, "vouched") {
		t.Errorf("expected edge label 'vouched' in output")
	}
	if !strings.Contains(result, "Legend") {
		t.Errorf("expected Legend in output")
	}
}

func TestEdgesFor(t *testing.T) {
	edges := []RelEdge{
		{AgentA: "Alice", AgentB: "Bob", Type: RelTrust, Strength: 0.8},
		{AgentA: "Alice", AgentB: "Carol", Type: RelConflict, Strength: 0.6},
		{AgentA: "Bob", AgentB: "Carol", Type: RelAlliance, Strength: 0.9},
	}

	aliceEdges := edgesFor(edges, "Alice")
	if len(aliceEdges) != 2 {
		t.Errorf("expected 2 edges for Alice, got %d", len(aliceEdges))
	}

	bobEdges := edgesFor(edges, "Bob")
	if len(bobEdges) != 2 {
		t.Errorf("expected 2 edges for Bob, got %d", len(bobEdges))
	}

	carolEdges := edgesFor(edges, "Carol")
	if len(carolEdges) != 2 {
		t.Errorf("expected 2 edges for Carol, got %d", len(carolEdges))
	}

	noneEdges := edgesFor(edges, "Dave")
	if len(noneEdges) != 0 {
		t.Errorf("expected 0 edges for Dave, got %d", len(noneEdges))
	}
}
