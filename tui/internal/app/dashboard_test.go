package app

import "testing"

func TestPanelModeCycling(t *testing.T) {
	m := DashboardModel{panelMode: PanelFeed}
	m.panelMode = (m.panelMode + 1) % 4
	if m.panelMode != PanelMap {
		t.Errorf("expected PanelMap, got %v", m.panelMode)
	}
	m.panelMode = (m.panelMode + 1) % 4
	if m.panelMode != PanelRelationships {
		t.Errorf("expected PanelRelationships, got %v", m.panelMode)
	}
	m.panelMode = (m.panelMode + 1) % 4
	if m.panelMode != PanelNegotiations {
		t.Errorf("expected PanelNegotiations, got %v", m.panelMode)
	}
	m.panelMode = (m.panelMode + 1) % 4
	if m.panelMode != PanelFeed {
		t.Errorf("expected PanelFeed wrap, got %v", m.panelMode)
	}
}

func TestPanelModeString(t *testing.T) {
	tests := []struct {
		mode PanelMode
		want string
	}{
		{PanelFeed, "Feed"},
		{PanelMap, "Map"},
		{PanelRelationships, "Relationships"},
		{PanelNegotiations, "Negotiations"},
	}
	for _, tt := range tests {
		if got := tt.mode.String(); got != tt.want {
			t.Errorf("PanelMode(%d).String() = %q, want %q", tt.mode, got, tt.want)
		}
	}
}
