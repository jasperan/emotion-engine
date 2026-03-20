package app

import (
	"testing"
	"time"

	"github.com/jasperan/emotion-engine/tui/internal/api"
)

func TestReplayModel_NewDefaults(t *testing.T) {
	m := NewReplayModel(nil, "test-id")
	if m.runID != "test-id" {
		t.Error("wrong runID")
	}
	if m.playSpeed != time.Second {
		t.Error("default speed should be 1s")
	}
	if m.playing {
		t.Error("should not be playing initially")
	}
	if m.steps == nil {
		t.Error("steps map should be initialized")
	}
}

func TestComputeDiff(t *testing.T) {
	prev := map[string]interface{}{"a": 1, "b": "old", "c": "removed"}
	curr := map[string]interface{}{"a": 1, "b": "new", "d": "added"}
	lines := computeDiff(prev, curr, 60)
	if len(lines) != 3 {
		t.Errorf("expected 3 diff lines, got %d", len(lines))
	}
}

func TestComputeDiff_NoDiff(t *testing.T) {
	same := map[string]interface{}{"a": 1}
	lines := computeDiff(same, same, 60)
	if len(lines) != 1 {
		t.Errorf("expected 1 no-changes line, got %d", len(lines))
	}
}

func TestReplayMessagesAtStep(t *testing.T) {
	m := ReplayModel{
		messages: []api.MessageResponse{
			{StepIndex: 1, Content: "hello"},
			{StepIndex: 2, Content: "world"},
			{StepIndex: 1, Content: "again"},
		},
	}
	msgs := m.messagesAtStep(1)
	if len(msgs) != 2 {
		t.Errorf("expected 2 messages at step 1, got %d", len(msgs))
	}
}
