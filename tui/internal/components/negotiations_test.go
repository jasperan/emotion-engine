package components

import (
	"strings"
	"testing"
)

func TestRenderNegotiationTheater_Empty(t *testing.T) {
	result := RenderNegotiationTheater(NegotiationTheaterData{
		Entries:   nil,
		ScrollPos: 0,
		Width:     80,
		Height:    40,
	})
	if !strings.Contains(result, "NEGOTIATIONS") {
		t.Errorf("expected NEGOTIATIONS subtitle, got: %s", result)
	}
	if !strings.Contains(result, "No negotiations yet...") {
		t.Errorf("expected empty state message, got: %s", result)
	}
}

func TestRenderNegotiationTheater_WithEntries(t *testing.T) {
	entries := []NegotiationEntry{
		{
			ProposalID: "p1",
			Proposer:   "Alice",
			Target:     "Bob",
			Terms:      "Share water supplies",
			Status:     NegAccepted,
			Step:       3,
			Responses: []NegotiationResponse{
				{AgentName: "Bob", Action: "accepted", Detail: "agreed", Step: 4},
				{AgentName: "Carol", Action: "countered", Detail: "only half", Step: 5},
				{AgentName: "Dave", Action: "rejected", Detail: "", Step: 6},
			},
		},
		{
			ProposalID: "p2",
			Proposer:   "Eve",
			Target:     "Frank",
			Terms:      "Evacuate together",
			Status:     NegPending,
			Step:       7,
			Responses:  nil,
		},
	}

	result := RenderNegotiationTheater(NegotiationTheaterData{
		Entries:   entries,
		ScrollPos: 0,
		Width:     80,
		Height:    40,
	})

	if !strings.Contains(result, "NEGOTIATIONS") {
		t.Errorf("expected NEGOTIATIONS subtitle")
	}
	if !strings.Contains(result, "Alice") {
		t.Errorf("expected proposer Alice in output")
	}
	if !strings.Contains(result, "Bob") {
		t.Errorf("expected target Bob in output")
	}
	if !strings.Contains(result, "Share water supplies") {
		t.Errorf("expected terms in output")
	}
	if !strings.Contains(result, "step 3") {
		t.Errorf("expected step 3 in output")
	}
	if !strings.Contains(result, "accepted") {
		t.Errorf("expected 'accepted' response action in output")
	}
	if !strings.Contains(result, "countered") {
		t.Errorf("expected 'countered' response action in output")
	}
	if !strings.Contains(result, "rejected") {
		t.Errorf("expected 'rejected' response action in output")
	}
	if !strings.Contains(result, "only half") {
		t.Errorf("expected counter detail 'only half' in output")
	}
	if !strings.Contains(result, "Eve") {
		t.Errorf("expected second proposer Eve in output")
	}
	if !strings.Contains(result, "Evacuate together") {
		t.Errorf("expected second proposal terms in output")
	}
}
