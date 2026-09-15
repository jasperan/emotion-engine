package app

import (
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"charm.land/lipgloss/v2"
	"github.com/jasperan/emotion-engine/tui/internal/api"
)

// --- fixtures ---

func twoScenarios() []api.ScenarioResponse {
	return []api.ScenarioResponse{
		{
			ID:             "s1",
			Name:           "Flood",
			Description:    "Rising water in a coastal town.",
			AgentTemplates: []map[string]interface{}{{}, {}},
		},
		{
			ID:          "s2",
			Name:        "Blackout",
			Description: "The grid fails at dusk.",
		},
	}
}

func twoRuns() []api.RunResponse {
	return []api.RunResponse{
		{ID: "11111111-2222", ScenarioID: "s1", Status: "running", CurrentStep: 3, MaxSteps: 50},
		{ID: "33333333-4444", ScenarioID: "s2", Status: "completed", CurrentStep: 12, MaxSteps: 12},
	}
}

// --- drivers ---

// scenarioScreen builds a loaded, focused and sized scenario browser.
func scenarioScreen(scenarios []api.ScenarioResponse) ScenarioModel {
	m := NewScenarioModel(nil)
	updated, _ := m.Update(scenariosLoadedMsg{scenarios: scenarios})
	m = updated
	m, _ = m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	return m
}

// historyScreen builds a loaded, focused and sized history browser.
func historyScreen(runs []api.RunResponse) HistoryModel {
	m := NewHistoryModel(nil)
	updated, _ := m.Update(runsLoadedMsg{runs: runs})
	m = updated
	m, _ = m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	return m
}

// submitOption moves the cursor down n options and submits the Select. huh
// completes the form on the message that follows the submit, which NextGroup
// delivers, and the screen dispatches its transition on the update after that.
func submitScenario(m ScenarioModel, down int) (ScenarioModel, tea.Cmd) {
	for range down {
		m, _ = m.Update(tea.KeyPressMsg{Code: tea.KeyDown})
	}
	if _, cmd := m.Update(enterKey()); cmd != nil {
		m, _ = m.Update(huh.NextField())
	}
	m.form.NextGroup()
	_, cmd := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	return m, cmd
}

func submitRun(m HistoryModel, down int) (HistoryModel, tea.Cmd) {
	for range down {
		m, _ = m.Update(tea.KeyPressMsg{Code: tea.KeyDown})
	}
	if _, cmd := m.Update(enterKey()); cmd != nil {
		m, _ = m.Update(huh.NextField())
	}
	m.form.NextGroup()
	_, cmd := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	return m, cmd
}

// switchMsg extracts a screen transition from a command. A non-nil command
// alone proves nothing: a keystroke that only reaches a huh field still returns
// one (the field's own cursor blink).
func switchMsg(cmd tea.Cmd) (SwitchScreenMsg, bool) {
	if cmd == nil {
		return SwitchScreenMsg{}, false
	}
	sw, ok := cmd().(SwitchScreenMsg)
	return sw, ok
}

func requireSwitch(t *testing.T, cmd tea.Cmd) SwitchScreenMsg {
	t.Helper()
	sw, ok := switchMsg(cmd)
	if !ok {
		t.Fatalf("expected a SwitchScreenMsg command, got %v", cmd)
	}
	return sw
}

// --- option labels ---

func TestScenarioOptionLabelCarriesTheAgentCount(t *testing.T) {
	got := scenarioOptionLabel(twoScenarios()[0])
	if !strings.Contains(got, "Flood") {
		t.Errorf("label %q lost the scenario name", got)
	}
	if !strings.Contains(got, "(2 agents)") {
		t.Errorf("label %q lost the agent count the old delegate showed", got)
	}
}

func TestRunOptionLabelCarriesStatusAndProgress(t *testing.T) {
	got := runOptionLabel(twoRuns()[1])
	for _, want := range []string{"#33333333", "completed", "step 12/12"} {
		if !strings.Contains(got, want) {
			t.Errorf("label %q is missing %q", got, want)
		}
	}
}

func TestRunTargetScreen(t *testing.T) {
	for _, tc := range []struct {
		status string
		want   Screen
	}{
		{"completed", ScreenReplay},
		{"failed", ScreenReplay},
		{"cancelled", ScreenReplay},
		{"running", ScreenDashboard},
		{"paused", ScreenDashboard},
		{"", ScreenDashboard},
	} {
		if got := runTargetScreen(tc.status); got != tc.want {
			t.Errorf("runTargetScreen(%q) = %v, want %v", tc.status, got, tc.want)
		}
	}
}

// --- scenario screen ---

func TestScenarioScreenSubmitsTheHighlightedScenario(t *testing.T) {
	m := scenarioScreen(twoScenarios())

	m, cmd := submitScenario(m, 1) // move from the first option to the second

	if m.form.State != huh.StateCompleted {
		t.Fatalf("form state = %v, want StateCompleted", m.form.State)
	}
	if m.selection.id != "s2" {
		t.Fatalf("selected %q, want the highlighted scenario s2", m.selection.id)
	}
	sw := requireSwitch(t, cmd)
	if sw.Screen != ScreenLauncher {
		t.Errorf("opened %v, want ScreenLauncher", sw.Screen)
	}
	if sw.Data != "s2" {
		t.Errorf("carried %v, want the scenario id s2", sw.Data)
	}
}

// TestScenarioScreenKeysYieldToTheFilter guards the one real hazard of placing
// screen bindings next to a huh Select: while "/" is capturing input the
// characters belong to the filter, not to the screen's navigation keys.
func TestScenarioScreenKeysYieldToTheFilter(t *testing.T) {
	m := scenarioScreen(twoScenarios())

	// Off-filter, h opens history.
	_, cmd := m.Update(tea.KeyPressMsg{Code: 'h', Text: "h"})
	sw, ok := switchMsg(cmd)
	if !ok {
		t.Fatal("h should open history while the filter is idle")
	}
	if sw.Screen != ScreenHistory {
		t.Fatalf("h opened %v, want ScreenHistory", sw.Screen)
	}

	// "/" starts filtering; the same key must now belong to the filter.
	updated, _ := m.Update(tea.KeyPressMsg{Code: '/', Text: "/"})
	m = updated
	if m.selectF == nil || !m.selectF.GetFiltering() {
		t.Fatal("/ did not start the Select filter")
	}
	_, cmd = m.Update(tea.KeyPressMsg{Code: 'h', Text: "h"})
	if sw, ok := switchMsg(cmd); ok {
		t.Fatalf("h navigated to %v while the filter was capturing input", sw.Screen)
	}
}

func TestScenarioScreenQuitKeysReturnToSplash(t *testing.T) {
	for _, key := range []tea.KeyPressMsg{
		{Code: 'q', Text: "q"},
		{Code: tea.KeyEscape},
	} {
		m := scenarioScreen(twoScenarios())
		_, cmd := m.Update(key)
		sw := requireSwitch(t, cmd)
		if sw.Screen != ScreenSplash {
			t.Errorf("%q opened %v, want ScreenSplash", key.String(), sw.Screen)
		}
	}
}

func TestScenarioViewShowsTheHoveredDescription(t *testing.T) {
	m := scenarioScreen(twoScenarios())
	m, _ = m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})

	out := m.View(120, 36)
	if !strings.Contains(out, "Rising water in a coastal town.") {
		t.Errorf("hovered scenario description is missing from the view: %q", out)
	}
	for _, line := range strings.Split(out, "\n") {
		if lipgloss.Width(line) > 120 {
			t.Fatalf("line exceeds 120 columns: %q", line)
		}
	}
}

// --- history screen ---
func TestHistoryScreenSubmitsTheHighlightedRun(t *testing.T) {
	m := historyScreen(twoRuns())

	// The second run is completed, so it opens in Replay.
	m, cmd := submitRun(m, 1)

	if m.form.State != huh.StateCompleted {
		t.Fatalf("form state = %v, want StateCompleted", m.form.State)
	}
	if m.selection.id != "33333333-4444" {
		t.Fatalf("selected %q, want the highlighted run", m.selection.id)
	}
	sw := requireSwitch(t, cmd)
	if sw.Screen != ScreenReplay {
		t.Errorf("opened %v, want ScreenReplay for a completed run", sw.Screen)
	}
	if sw.Data != "33333333-4444" {
		t.Errorf("carried %v, want the run id", sw.Data)
	}
}

func TestHistoryScreenOpensLiveRunsOnTheDashboard(t *testing.T) {
	m := historyScreen(twoRuns())

	// Leave the cursor on the first run, which is still running.
	m, cmd := submitRun(m, 0)

	sw := requireSwitch(t, cmd)
	if sw.Screen != ScreenDashboard {
		t.Errorf("opened %v, want ScreenDashboard for a running run", sw.Screen)
	}
}

func TestHistoryRKeyOpensTheHighlightedRun(t *testing.T) {
	m := historyScreen(twoRuns())

	m, _ = m.Update(tea.KeyPressMsg{Code: tea.KeyDown})
	_, cmd := m.Update(tea.KeyPressMsg{Code: 'r', Text: "r"})

	sw := requireSwitch(t, cmd)
	if sw.Screen != ScreenReplay || sw.Data != "33333333-4444" {
		t.Errorf("r opened %v/%v, want ScreenReplay for the highlighted completed run", sw.Screen, sw.Data)
	}
}

func TestHistoryViewShowsRunStatusAndScenario(t *testing.T) {
	m := historyScreen(twoRuns())
	m, _ = m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})

	out := m.View(120, 36)
	if !strings.Contains(out, "scenario: s1") {
		t.Errorf("hovered run's scenario is missing from the view: %q", out)
	}
	if !strings.Contains(out, "running") {
		t.Errorf("hovered run's status is missing from the view: %q", out)
	}
}

func TestHistoryScreenReportsAnEmptyHistory(t *testing.T) {
	m := historyScreen(nil)

	out := m.View(80, 24)
	if !strings.Contains(out, "No runs yet") {
		t.Errorf("empty history should say so instead of rendering nothing: %q", out)
	}
}
