package components

import (
	"strings"
	"testing"
)

func TestRenderBarChartEmpty(t *testing.T) {
	out := RenderBarChart([]BarChartEntry{}, 80)
	if out == "" {
		t.Error("expected non-empty output for empty entries")
	}
	if !strings.Contains(out, "No data") {
		t.Errorf("expected 'No data', got %q", out)
	}
}

func TestRenderBarChartThreeEntries(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "Alpha", Value: 100, Max: 100},
		{Label: "Beta", Value: 50, Max: 100},
		{Label: "Gamma", Value: 0, Max: 100},
	}
	out := RenderBarChart(entries, 80)
	if out == "" {
		t.Error("expected non-empty output")
	}
	lines := strings.Split(strings.TrimRight(out, "\n"), "\n")
	if len(lines) != 3 {
		t.Errorf("expected 3 lines, got %d: %q", len(lines), out)
	}
}
