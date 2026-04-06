package components

import (
	"strings"
	"testing"
)

func TestRenderStepDiff_Empty(t *testing.T) {
	out := RenderStepDiff(StepDiffData{Width: 80, Height: 40})
	if !strings.Contains(out, "Waiting for state changes") {
		t.Error("expected empty-state message")
	}
	if !strings.Contains(out, "STEP DIFF") {
		t.Error("expected title")
	}
}

func TestRenderStepDiff_WithDiffs(t *testing.T) {
	data := StepDiffData{
		CurrentStep: 5,
		Diffs: [][]DiffEntry{
			{
				{Category: "hazard", Key: "level", ChangeType: DiffChanged, OldValue: "3", NewValue: "5"},
				{Category: "movement", Key: "Alice", ChangeType: DiffChanged, NewValue: "moved to Bridge"},
				{Category: "proposal", Key: "new proposals", ChangeType: DiffAdded, NewValue: "2"},
				{Category: "health", Key: "Bob", ChangeType: DiffChanged, OldValue: "8", NewValue: "6"},
			},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderStepDiff(data)

	if !strings.Contains(out, "HAZARD") {
		t.Error("expected hazard category")
	}
	if !strings.Contains(out, "MOVEMENT") {
		t.Error("expected movement category")
	}
	if !strings.Contains(out, "HEALTH") {
		t.Error("expected health category")
	}
}

func TestRenderStepDiff_RollingHistory(t *testing.T) {
	data := StepDiffData{
		CurrentStep: 5,
		Diffs: [][]DiffEntry{
			{{Category: "event", Key: "flood", ChangeType: DiffAdded}},
			{{Category: "event", Key: "wind", ChangeType: DiffAdded}},
			{{Category: "hazard", Key: "level", ChangeType: DiffChanged, NewValue: "7"}},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderStepDiff(data)

	// Should show the latest diff (hazard)
	if !strings.Contains(out, "HAZARD") {
		t.Error("expected latest diff to show")
	}
	// Should show sparkline for history
	if !strings.Contains(out, "changes:") {
		t.Error("expected changes sparkline")
	}
}

func TestRenderStepDiff_EmptyDiffStep(t *testing.T) {
	data := StepDiffData{
		CurrentStep: 3,
		Diffs:       [][]DiffEntry{{}}, // empty step
		Width:       80,
		Height:      40,
	}
	out := RenderStepDiff(data)
	if !strings.Contains(out, "No changes this step") {
		t.Error("expected no-changes message for empty diff")
	}
}

func TestRenderStepDiff_ContagionEvents(t *testing.T) {
	data := StepDiffData{
		CurrentStep: 5,
		Diffs:       [][]DiffEntry{{}},
		Contagion: []ContagionEvent{
			{
				SourceName: "Alice", TargetName: "Bob",
				StressDelta: 1.5, StressBefore: 3, StressAfter: 4.5,
				Mechanism: "panic_spread", Location: "Bridge", Step: 5,
			},
			{
				SourceName: "Carol", TargetName: "Alice",
				StressDelta: -0.8, StressBefore: 5, StressAfter: 4.2,
				Mechanism: "calm_anchor", Location: "Shelter", Step: 5,
			},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderStepDiff(data)

	if !strings.Contains(out, "EMOTION CONTAGION") {
		t.Error("expected contagion section")
	}
	if !strings.Contains(out, "Alice") {
		t.Error("expected Alice in contagion")
	}
	if !strings.Contains(out, "Bob") {
		t.Error("expected Bob in contagion")
	}
}

func TestDiffIcon_AllTypes(t *testing.T) {
	for _, ct := range []DiffChangeType{DiffAdded, DiffChanged, DiffRemoved} {
		icon := diffIcon(ct)
		if icon == "" {
			t.Errorf("diffIcon(%d) returned empty", ct)
		}
	}
}
