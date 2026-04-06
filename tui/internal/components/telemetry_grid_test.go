package components

import (
	"strings"
	"testing"
)

func TestRenderTelemetryGrid_Empty(t *testing.T) {
	out := RenderTelemetryGrid(TelemetryGridData{Width: 80, Height: 40})
	if !strings.Contains(out, "No telemetry data yet") {
		t.Error("expected empty-state message")
	}
	if !strings.Contains(out, "AGENT TELEMETRY") {
		t.Error("expected title")
	}
}

func TestRenderTelemetryGrid_WithAgents(t *testing.T) {
	data := TelemetryGridData{
		Agents: []AgentTelemetryInfo{
			{Name: "Alice", Status: "healthy", AvgTickMs: 1200, TokensUsed: 5000, ActionCount: 15, MessagesSent: 8, MessagesReceived: 12, StaleScore: 0.1},
			{Name: "Bob", Status: "degraded", AvgTickMs: 8000, TokensUsed: 15000, ActionCount: 5, MessagesSent: 2, MessagesReceived: 3, StaleScore: 0.8},
			{Name: "Carol", Status: "failed", AvgTickMs: 0, TokensUsed: 200, ActionCount: 1, MessagesSent: 0, MessagesReceived: 1, StaleScore: 0.95},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderTelemetryGrid(data)

	if !strings.Contains(out, "Alice") {
		t.Error("expected Alice in grid")
	}
	if !strings.Contains(out, "Bob") {
		t.Error("expected Bob in grid")
	}
	if !strings.Contains(out, "Carol") {
		t.Error("expected Carol in grid")
	}
	// Header should be present
	if !strings.Contains(out, "Agent") {
		t.Error("expected header")
	}
	if !strings.Contains(out, "Tick") {
		t.Error("expected Tick column header")
	}
}

func TestRenderTelemetryGrid_HighTokenCount(t *testing.T) {
	data := TelemetryGridData{
		Agents: []AgentTelemetryInfo{
			{Name: "Alice", Status: "healthy", TokensUsed: 25000, ActionCount: 10},
		},
		Width:  80,
		Height: 40,
	}
	out := RenderTelemetryGrid(data)

	// Should format as "25.0k" style
	if !strings.Contains(out, "k") {
		t.Error("expected k-formatted token count for 25000")
	}
}

func TestTelemetryStatusDot_AllStatuses(t *testing.T) {
	statuses := []string{"healthy", "recovering", "degraded", "failed", "unknown"}
	for _, s := range statuses {
		dot := telemetryStatusDot(s)
		if dot == "" {
			t.Errorf("telemetryStatusDot(%q) returned empty", s)
		}
	}
}

func TestActionMiniBar(t *testing.T) {
	// Zero max
	b := actionMiniBar(0, 0)
	if b == "" {
		t.Error("actionMiniBar(0,0) returned empty")
	}

	// Normal
	b = actionMiniBar(5, 10)
	if b == "" {
		t.Error("actionMiniBar(5,10) returned empty")
	}

	// Max
	b = actionMiniBar(10, 10)
	if b == "" {
		t.Error("actionMiniBar(10,10) returned empty")
	}
}
