package components

import (
	"strings"
	"testing"
)

func TestRenderMindView_Basic(t *testing.T) {
	d := MindViewData{
		Name:       "Alice",
		Occupation: "Doctor",
		Age:        34,
		Location:   "Hospital",
		Health:     75,
		Stress:     40,
		Width:      120,
		Height:     40,
	}

	out := RenderMindView(d)

	if !strings.Contains(out, "ALICE") {
		t.Errorf("expected uppercase name ALICE, got:\n%s", out)
	}
	if !strings.Contains(out, "Doctor") {
		t.Errorf("expected occupation Doctor")
	}
	if !strings.Contains(out, "34") {
		t.Errorf("expected age 34")
	}
	if !strings.Contains(out, "Hospital") {
		t.Errorf("expected location Hospital")
	}
	if !strings.Contains(out, "HP") {
		t.Errorf("expected HP stat label")
	}
	if !strings.Contains(out, "Stress") {
		t.Errorf("expected Stress stat label")
	}
}

func TestRenderMindView_Full(t *testing.T) {
	d := MindViewData{
		Name:          "Marcus",
		Occupation:    "Engineer",
		Age:           42,
		Location:      "Control Room",
		Health:        20,
		Stress:        90,
		Emotion:       "fear",
		Width:         140,
		Height:        50,
		Openness:      7,
		Conscientiousness: 8,
		Extraversion:  4,
		Agreeableness: 6,
		Neuroticism:   9,
		RiskTolerance: 3,
		Empathy:       5,
		Leadership:    7,
		Inventory: []string{"radio", "first aid kit", "map"},
		PlanGoal:      "Restore power to the eastern grid",
		PlanStep:      "Find backup generator",
		PlanProgress:  "2/5",
		PlanDeadline:  25,
		LastReasoning: "The flood is rising faster than expected. We need to prioritize evacuation routes before attempting repair.",
		Relationships: []MindRelationship{
			{AgentName: "Elena", Trust: 0.8, Label: "ally", Description: "Helped carry equipment"},
			{AgentName: "Director Chen", Trust: 0.3, Label: "suspicious", Description: "Withheld information"},
		},
		RecentActions: []MindAction{
			{Step: 10, Action: "move", Target: "Control Room", Emotion: "determined"},
			{Step: 11, Action: "speak", Target: "Elena", Emotion: "anxious"},
			{Step: 12, Action: "pick_up", Target: "radio", Emotion: "relieved"},
		},
	}

	out := RenderMindView(d)

	// Header
	if !strings.Contains(out, "MARCUS") {
		t.Errorf("expected uppercase name MARCUS")
	}
	if !strings.Contains(out, "Engineer") {
		t.Errorf("expected occupation Engineer")
	}
	if !strings.Contains(out, "Control Room") {
		t.Errorf("expected location Control Room")
	}
	if !strings.Contains(out, "fear") {
		t.Errorf("expected emotion fear")
	}

	// Personality section
	if !strings.Contains(out, "PERSONALITY") {
		t.Errorf("expected PERSONALITY section")
	}
	if !strings.Contains(out, "Openness") {
		t.Errorf("expected Openness trait")
	}
	if !strings.Contains(out, "Neuroticism") {
		t.Errorf("expected Neuroticism trait")
	}

	// Plan section
	if !strings.Contains(out, "PLAN") {
		t.Errorf("expected PLAN section")
	}
	if !strings.Contains(out, "eastern grid") {
		t.Errorf("expected plan goal text")
	}
	if !strings.Contains(out, "2/5") {
		t.Errorf("expected plan progress 2/5")
	}
	if !strings.Contains(out, "25") {
		t.Errorf("expected deadline step 25")
	}

	// Inventory
	if !strings.Contains(out, "INVENTORY") {
		t.Errorf("expected INVENTORY section")
	}
	if !strings.Contains(out, "radio") {
		t.Errorf("expected inventory item radio")
	}

	// Relationships
	if !strings.Contains(out, "RELATIONSHIPS") {
		t.Errorf("expected RELATIONSHIPS section")
	}
	if !strings.Contains(out, "Elena") {
		t.Errorf("expected relationship with Elena")
	}
	if !strings.Contains(out, "ally") {
		t.Errorf("expected label ally")
	}

	// Reasoning
	if !strings.Contains(out, "LAST REASONING") {
		t.Errorf("expected LAST REASONING section")
	}
	if !strings.Contains(out, "evacuation") {
		t.Errorf("expected reasoning text")
	}

	// Recent actions
	if !strings.Contains(out, "RECENT ACTIONS") {
		t.Errorf("expected RECENT ACTIONS section")
	}
	if !strings.Contains(out, "move") {
		t.Errorf("expected action move")
	}
	if !strings.Contains(out, "Elena") {
		t.Errorf("expected action target Elena")
	}
	if !strings.Contains(out, "determined") {
		t.Errorf("expected emotion determined in actions")
	}
}
