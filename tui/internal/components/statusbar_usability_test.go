package components

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestRenderStatusBarFits80Columns(t *testing.T) {
	out := RenderStatusBar(StatusBarData{
		Connected:  true,
		RunStatus:  "running",
		Step:       12,
		MaxSteps:   100,
		TokPerSec:  42.5,
		PanelName:  "Relationships",
		FilterName: "Negotiations",
		Hints: []KeyHint{
			{Key: "Tab", Desc: "panel"},
			{Key: "Shift+Tab", Desc: "previous"},
			{Key: "Enter", Desc: "mind"},
			{Key: "q", Desc: "back"},
		},
	}, 80)

	if out == "" {
		t.Fatal("expected non-empty status bar")
	}
	for _, line := range strings.Split(out, "\n") {
		if got := lipgloss.Width(line); got > 80 {
			t.Fatalf("line width %d exceeds 80 columns: %q", got, line)
		}
	}
}

func TestRenderStatusBarKeepsFittingHints(t *testing.T) {
	data := StatusBarData{
		Connected: true,
		RunStatus: "running",
		Step:      12,
		MaxSteps:  100,
		TokPerSec: 42.5,
		PanelName: "Overview",
		Hints: []KeyHint{
			{Key: "Tab", Desc: "panel"},
			{Key: "Shift+Tab", Desc: "prev"},
			{Key: "Enter", Desc: "mind"},
			{Key: "g", Desc: "grid"},
			{Key: "t", Desc: "theater"},
			{Key: "F1", Desc: "help"},
			{Key: "q/Esc", Desc: "back"},
		},
	}

	for _, width := range []int{100, 120} {
		out := RenderStatusBar(data, width)
		if !strings.Contains(out, "back") {
			t.Fatalf("expected fitting back hint at width %d, got %q", width, out)
		}
		for _, line := range strings.Split(out, "\n") {
			if got := lipgloss.Width(line); got > width {
				t.Fatalf("line width %d exceeds %d columns: %q", got, width, line)
			}
		}
	}
}
