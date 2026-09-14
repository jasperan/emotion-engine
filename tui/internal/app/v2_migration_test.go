package app

import (
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"
	"github.com/jasperan/emotion-engine/tui/internal/api"
)

// spacePress is what a terminal actually delivers for the space bar in v2:
// Key.Code is ' ' and Key.Text is " ". msg.String() then reports "space".
//
// This matters because v1 reported " " for the same keystroke. Any handler
// matching only " " compiles, runs, and silently never fires.
func spacePress() tea.KeyPressMsg {
	return tea.KeyPressMsg{Code: ' ', Text: " "}
}

// TestSpaceKeyReportsAsSpace pins the premise every space-to-toggle test below
// depends on. If a future Bubble Tea changed this back to " ", the tests below
// would start passing for the wrong reason, so assert it directly.
func TestSpaceKeyReportsAsSpace(t *testing.T) {
	if got := spacePress().String(); got != "space" {
		t.Fatalf("space press reports %q, want %q; the space-key tests below assume %q",
			got, "space", "space")
	}
}

// TestAppViewDeclaresAltScreen guards the v2 migration's least visible risk.
//
// v2 removed the alt-screen program option, so the alternate screen is now
// declared on the tea.View returned by View(). Deleting the declaration
// compiles cleanly and ships an app that renders over the user's scrollback.
//
// The SSH entry point depends on this too: internal/ssh hands the model to a
// Wish middleware and returns no program options, so this declaration is the
// only thing that gives a remote session an alternate screen.
func TestAppViewDeclaresAltScreen(t *testing.T) {
	a := NewApp("http://127.0.0.1:1", true, "test")

	v := a.View()
	if !v.AltScreen {
		t.Error("App.View() does not set AltScreen; v2 removed the program option, " +
			"so without this neither the local nor the SSH entry point enters the alternate screen")
	}
	// Non-vacuity: an empty view would also satisfy the assertion above, and it
	// would be a rendering regression the alt-screen check must not mask.
	if strings.TrimSpace(v.Content) == "" {
		t.Error("App.View() returned empty content; the migration must not have removed the frame")
	}
}

// TestTheaterSpaceTogglesPause covers the space-to-pause binding. It used to
// match " ", which v2 no longer produces, so the binding was dead until it was
// widened to accept "space" too.
func TestTheaterSpaceTogglesPause(t *testing.T) {
	m := NewTheaterModel(nil, "run-1", nil)
	if m.paused {
		t.Fatal("precondition: model should start unpaused")
	}

	m, _ = m.handleKey(spacePress())
	if !m.paused {
		t.Error("space did not pause the theater view")
	}

	m, _ = m.handleKey(spacePress())
	if m.paused {
		t.Error("space did not resume the theater view")
	}
}

// TestReplaySpaceStartsAndStopsPlayback covers the same binding on replay.
func TestReplaySpaceStartsAndStopsPlayback(t *testing.T) {
	m := NewReplayModel(nil, "run-1")
	if m.playing {
		t.Fatal("precondition: replay should start paused")
	}

	m, cmd := m.handleKey(spacePress())
	if !m.playing {
		t.Error("space did not start replay playback")
	}
	if cmd == nil {
		t.Error("starting playback should schedule a tick")
	}

	m, _ = m.handleKey(spacePress())
	if m.playing {
		t.Error("space did not stop replay playback")
	}
}

// TestDashboardSpaceDispatchesControl covers the third space binding, on the
// dashboard. The action runs against a live client, so assert that the key
// DISPATCHED rather than invoking the command.
func TestDashboardSpaceDispatchesControl(t *testing.T) {
	m := NewDashboardModel(nil, nil, false, "test-run")
	m.run = &api.RunResponse{Status: "running"}

	if _, cmd := m.handleKey(spacePress()); cmd == nil {
		t.Error("space did not dispatch a control command on the dashboard")
	}

	// Control: an unbound key must not dispatch anything. Without this the
	// assertion above could be satisfied by a handler that always returns a cmd.
	if _, cmd := m.handleKey(tea.KeyPressMsg{Code: 'z', Text: "z"}); cmd != nil {
		t.Error("an unbound key dispatched a command; the space assertion above proves nothing")
	}
}
