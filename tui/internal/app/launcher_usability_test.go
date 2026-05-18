package app

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
)

func TestLauncherRejectsInvalidMaxSteps(t *testing.T) {
	m := NewLauncherModel(nil, "scenario-1")
	m.maxStepsInput.SetValue("abc")

	updated, cmd := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated

	if cmd != nil {
		t.Fatal("invalid max steps should not create a run command")
	}
	if m.launching {
		t.Fatal("launcher should not enter launching state with invalid max steps")
	}
	if !strings.Contains(m.validationErr, "Max steps") {
		t.Fatalf("expected max steps validation error, got %q", m.validationErr)
	}
}

func TestLauncherRejectsInvalidSeed(t *testing.T) {
	m := NewLauncherModel(nil, "scenario-1")
	m.seedInput.SetValue("not-a-number")

	updated, cmd := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated

	if cmd != nil {
		t.Fatal("invalid seed should not create a run command")
	}
	if !strings.Contains(m.validationErr, "Seed") {
		t.Fatalf("expected seed validation error, got %q", m.validationErr)
	}
}

func TestLauncherQReturnsToScenarios(t *testing.T) {
	m := NewLauncherModel(nil, "scenario-1")

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'q'}})
	if cmd == nil {
		t.Fatal("q should produce a screen switch command")
	}

	msg := cmd()
	sw, ok := msg.(SwitchScreenMsg)
	if !ok {
		t.Fatalf("expected SwitchScreenMsg, got %T", msg)
	}
	if sw.Screen != ScreenScenarios {
		t.Fatalf("expected ScreenScenarios, got %v", sw.Screen)
	}
}

func TestLauncherCompactViewFits80Columns(t *testing.T) {
	m := NewLauncherModel(nil, "scenario-1")
	m.scenario = &api.ScenarioResponse{
		Name:        "Rising Flood With A Long Name",
		Description: strings.Repeat("Flood waters are rising and every team member needs clear launch settings. ", 3),
	}

	out := m.View(80, 24)
	for _, line := range strings.Split(out, "\n") {
		if got := lipgloss.Width(line); got > 80 {
			t.Fatalf("line width %d exceeds 80 columns: %q", got, line)
		}
	}
}
