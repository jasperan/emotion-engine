package app

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/jasperan/emotion-engine/tui/internal/api"
)

func newTestTheater() TheaterModel {
	return TheaterModel{
		runID:      "test-run",
		run:        &api.RunResponse{Status: "running", CurrentStep: 5, MaxSteps: 50},
		focusAgent: -1,
		maxEntries: 500,
	}
}

func TestTheaterModel_Init(t *testing.T) {
	m := newTestTheater()
	if m.Init() != nil {
		t.Error("Init should return nil")
	}
}

func TestTheaterModel_SceneTurnEvent(t *testing.T) {
	m := newTestTheater()

	evt := api.WSMessage{
		Event: "scene_turn",
		Data: map[string]interface{}{
			"agent_name": "Alice",
			"action":     "looks around nervously",
			"speech":     "We need to leave now!",
			"thought":    "I'm terrified but I can't show it",
			"emotion":    "fear",
			"location":   "Bridge",
			"step_index": float64(5),
		},
	}
	m.handleWSEvent(evt)

	if len(m.entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(m.entries))
	}
	e := m.entries[0]
	if e.AgentName != "Alice" {
		t.Errorf("expected Alice, got %s", e.AgentName)
	}
	if e.Speech != "We need to leave now!" {
		t.Errorf("unexpected speech: %s", e.Speech)
	}
	if e.Thought != "I'm terrified but I can't show it" {
		t.Errorf("unexpected thought: %s", e.Thought)
	}
	if e.Location != "Bridge" {
		t.Errorf("expected Bridge, got %s", e.Location)
	}
	// Agent name should be tracked
	if len(m.agentNames) != 1 || m.agentNames[0] != "Alice" {
		t.Error("expected Alice in agentNames")
	}
}

func TestTheaterModel_MessageEvent(t *testing.T) {
	m := newTestTheater()

	evt := api.WSMessage{
		Event: "message",
		Data: map[string]interface{}{
			"agent_name": "Bob",
			"content":    "I found supplies!",
			"location":   "Shelter",
			"step_index": float64(3),
		},
	}
	m.handleWSEvent(evt)

	if len(m.entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(m.entries))
	}
	if m.entries[0].Speech != "I found supplies!" {
		t.Error("expected message content in Speech field")
	}
}

func TestTheaterModel_MovementEvent(t *testing.T) {
	m := newTestTheater()

	evt := api.WSMessage{
		Event: "agent_moved",
		Data: map[string]interface{}{
			"agent_name": "Carol",
			"from":       "Bridge",
			"to":         "Shelter",
			"step":       float64(4),
		},
	}
	m.handleWSEvent(evt)

	if len(m.entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(m.entries))
	}
	if !m.entries[0].IsMovement {
		t.Error("expected IsMovement to be true")
	}
}

func TestTheaterModel_ContagionDirectorNote(t *testing.T) {
	m := newTestTheater()

	evt := api.WSMessage{
		Event: "emotion_contagion",
		Data: map[string]interface{}{
			"source_name": "Alice",
			"target_name": "Bob",
			"mechanism":   "panic_spread",
			"delta":       float64(1.5),
			"step":        float64(5),
		},
	}
	m.handleWSEvent(evt)

	if len(m.directorNotes) != 1 {
		t.Fatalf("expected 1 director note, got %d", len(m.directorNotes))
	}
	n := m.directorNotes[0]
	if n.Type != "contagion" {
		t.Errorf("expected contagion type, got %s", n.Type)
	}
	if !strings.Contains(n.Content, "Alice") || !strings.Contains(n.Content, "Bob") {
		t.Error("expected agent names in note content")
	}
}

func TestTheaterModel_Pause(t *testing.T) {
	m := newTestTheater()
	if m.paused {
		t.Error("should not start paused")
	}

	m, _ = m.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{' '}})
	if !m.paused {
		t.Error("should be paused after Space")
	}

	// Events should not be added when paused
	evt := api.WSMessage{
		Event: "scene_turn",
		Data: map[string]interface{}{
			"agent_name": "Alice",
			"speech":     "ignored",
		},
	}
	m.handleWSEvent(evt)
	if len(m.entries) != 0 {
		t.Error("should not add entries when paused")
	}

	m, _ = m.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{' '}})
	if m.paused {
		t.Error("should be unpaused after second Space")
	}
}

func TestTheaterModel_FocusAgent(t *testing.T) {
	m := newTestTheater()
	m.agentNames = []string{"Alice", "Bob", "Carol"}

	// Focus on agent 2 (Bob)
	m, _ = m.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'2'}})
	if m.focusAgent != 1 {
		t.Errorf("expected focus on index 1, got %d", m.focusAgent)
	}

	// Toggle off
	m, _ = m.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'2'}})
	if m.focusAgent != -1 {
		t.Errorf("expected focus off, got %d", m.focusAgent)
	}

	// Focus then reset to all
	m, _ = m.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'1'}})
	if m.focusAgent != 0 {
		t.Errorf("expected focus 0, got %d", m.focusAgent)
	}
	m, _ = m.handleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'0'}})
	if m.focusAgent != -1 {
		t.Error("expected focus reset to -1")
	}
}

func TestTheaterModel_ViewRenders(t *testing.T) {
	m := newTestTheater()
	// Add some entries
	m.entries = []TheaterEntry{
		{AgentName: "Alice", Location: "Bridge", Speech: "Help!", Thought: "I'm scared", Action: "waves arms", Emotion: "fear", Step: 1},
		{AgentName: "Bob", Location: "Bridge", Speech: "Coming!", Step: 2},
	}
	m.agentNames = []string{"Alice", "Bob"}
	m.directorNotes = []DirectorNote{
		{Step: 1, Type: "contagion", Content: "stress spreading"},
	}

	out := m.View(120, 40)
	if !strings.Contains(out, "THEATER") {
		t.Error("expected THEATER header")
	}
	if !strings.Contains(out, "STAGE") {
		t.Error("expected STAGE column")
	}
	if !strings.Contains(out, "BACKSTAGE") {
		t.Error("expected BACKSTAGE column")
	}
	if !strings.Contains(out, "All Agents") {
		t.Error("expected All Agents focus label")
	}
}

func TestTheaterModel_ViewWithFocus(t *testing.T) {
	m := newTestTheater()
	m.entries = []TheaterEntry{
		{AgentName: "Alice", Speech: "Hello", Step: 1},
		{AgentName: "Bob", Speech: "Hi there", Step: 1},
	}
	m.agentNames = []string{"Alice", "Bob"}
	m.focusAgent = 0

	out := m.View(120, 40)
	if !strings.Contains(out, "Alice") {
		t.Error("expected Alice in focused view")
	}
}

func TestTheaterModel_RunStatusUpdate(t *testing.T) {
	m := newTestTheater()

	evt := api.WSMessage{Event: "run_completed"}
	m.handleWSEvent(evt)
	if m.run.Status != "completed" {
		t.Errorf("expected completed, got %s", m.run.Status)
	}
}

func TestTheaterModel_EscReturns(t *testing.T) {
	m := newTestTheater()
	var cmd tea.Cmd
	m, cmd = m.handleKey(tea.KeyMsg{Type: tea.KeyEsc})
	if cmd == nil {
		t.Error("expected SwitchScreenMsg command on Esc")
	}
}

func TestTheaterModel_EntryCap(t *testing.T) {
	m := newTestTheater()
	m.maxEntries = 5

	for i := 0; i < 10; i++ {
		m.addEntry(TheaterEntry{AgentName: "Alice", Step: i})
	}

	if len(m.entries) != 5 {
		t.Errorf("expected cap at 5, got %d", len(m.entries))
	}
	// Should keep the latest
	if m.entries[0].Step != 5 {
		t.Errorf("expected oldest entry to be step 5, got %d", m.entries[0].Step)
	}
}
