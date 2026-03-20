package components

import "testing"

func TestRenderMessageFeed_Empty(t *testing.T) {
	d := MessageFeedData{Height: 10, Width: 40}
	result := RenderMessageFeed(d)
	if result == "" {
		t.Error("expected non-empty output")
	}
}

func TestRenderMessageFeed_FilterSpeech(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "Maria", Content: "Hello", MessageType: "room", Step: 1, Location: "Shelter"},
			{AgentName: "System", Content: "Proposed X", MessageType: "negotiation", Step: 1, Location: "Shelter"},
			{AgentName: "Kenji", Content: "Moving", MessageType: "movement", Step: 1, Location: "Bridge"},
		},
		Filter: FilterSpeech,
		Height: 20,
		Width:  40,
	}
	result := RenderMessageFeed(d)
	if result == "" {
		t.Error("expected non-empty output")
	}
}

func TestRenderMessageFeed_FilterNegotiations(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "Maria", Content: "Hello", MessageType: "room", Step: 1, Location: "Shelter"},
			{AgentName: "System", Content: "Proposed X", MessageType: "negotiation", Step: 1, Location: "Shelter"},
		},
		Filter: FilterNegotiations,
		Height: 20,
		Width:  40,
	}
	result := RenderMessageFeed(d)
	if result == "" {
		t.Error("expected non-empty output")
	}
}

func TestRenderMessageFeed_FilterMovement_Empty(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "Maria", Content: "Hello", MessageType: "room", Step: 1, Location: "Shelter"},
		},
		Filter: FilterMovement,
		Height: 20,
		Width:  40,
	}
	result := RenderMessageFeed(d)
	if result == "" {
		t.Error("expected non-empty output for no-match filter")
	}
}

func TestFeedFilterCycling(t *testing.T) {
	f := FilterAll
	f = (f + 1) % 4
	if f != FilterSpeech {
		t.Errorf("expected FilterSpeech, got %v", f)
	}
	f = (f + 1) % 4
	if f != FilterNegotiations {
		t.Errorf("expected FilterNegotiations, got %v", f)
	}
	f = (f + 1) % 4
	if f != FilterMovement {
		t.Errorf("expected FilterMovement, got %v", f)
	}
	f = (f + 1) % 4
	if f != FilterAll {
		t.Errorf("expected FilterAll wrap, got %v", f)
	}
}

func TestFeedFilterString(t *testing.T) {
	if FilterAll.String() != "All" {
		t.Error("FilterAll string")
	}
	if FilterSpeech.String() != "Speech" {
		t.Error("FilterSpeech string")
	}
	if FilterNegotiations.String() != "Negotiations" {
		t.Error("FilterNegotiations string")
	}
	if FilterMovement.String() != "Movement" {
		t.Error("FilterMovement string")
	}
}
