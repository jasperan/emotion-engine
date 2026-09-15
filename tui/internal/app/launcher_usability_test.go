package app

import (
	"strings"
	"testing"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"charm.land/lipgloss/v2"
	"github.com/jasperan/emotion-engine/tui/internal/api"
)

// --- form drivers ---
//
// An embedded huh form needs the message traffic a standalone one gets from the
// bubbletea runtime. The command huh returns alongside a keystroke also carries
// time-based animations (cursor blinks, spinner ticks) that sleep when executed,
// so these drivers deliver the advance message directly through the exported
// huh.NextField instead of running the command. Executing it would add minutes
// to the suite for no extra coverage.

func enterKey() tea.KeyPressMsg { return tea.KeyPressMsg{Code: tea.KeyEnter} }

// typeInto sends the characters of s to the focused field.
func typeInto(m LauncherModel, s string) LauncherModel {
	for _, r := range s {
		updated, _ := m.Update(tea.KeyPressMsg{Code: r, Text: string(r)})
		m = updated
	}
	return m
}

// advance submits the focused field and moves the form on. huh returns a nil
// command when validation rejects the value, in which case focus stays put.
func advance(m LauncherModel) LauncherModel {
	updated, cmd := m.Update(enterKey())
	m = updated
	if cmd == nil {
		return m
	}
	m, _ = m.Update(huh.NextField())
	return m
}

// completeForm submits the last field's group. huh completes the form on the
// message that follows the final field's submit, which Form.NextGroup delivers.
func completeForm(m LauncherModel) LauncherModel {
	m.form.NextGroup()
	return m
}

// size reports the terminal size the way the runtime does before the first
// frame, so a screen lays its form out at the right width and height.
func size(m LauncherModel, w, h int) LauncherModel {
	updated, _ := m.Update(tea.WindowSizeMsg{Width: w, Height: h})
	return updated
}

// focusFirstField runs the form's Init, which focuses the first field and
// builds its content. Init also returns cursor-blink commands; nothing here
// executes them.
func focusFirstField(m LauncherModel) LauncherModel {
	_ = m.form.Init()
	return m
}

// newFocusedLauncher builds a launcher and focuses the first field, which
// Form.Init does in the running program.
func newFocusedLauncher() LauncherModel {
	m := NewLauncherModel(api.NewClient("http://127.0.0.1:1"), "scenario-1")
	return focusFirstField(m)
}

// --- validator units ---

func TestValidateMaxStepsAcceptsBlankAndBounds(t *testing.T) {
	for _, tc := range []struct {
		name    string
		value   string
		wantErr bool
	}{
		{"blank means the backend default", "", false},
		{"whitespace means the backend default", "   ", false},
		{"lower bound is allowed", "1", false},
		{"upper bound is allowed", "10000", false},
		{"zero is rejected", "0", true},
		{"above the upper bound is rejected", "10001", true},
		{"negative is rejected", "-3", true},
		{"non-numeric is rejected", "abc", true},
		{"fractional is rejected", "1.5", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			err := validateMaxSteps(tc.value)
			if tc.wantErr && err == nil {
				t.Fatalf("validateMaxSteps(%q) accepted a value it should reject", tc.value)
			}
			if !tc.wantErr && err != nil {
				t.Fatalf("validateMaxSteps(%q) rejected a valid value: %v", tc.value, err)
			}
			if err != nil && !strings.Contains(err.Error(), "Max steps") {
				t.Fatalf("error %q does not name the field", err)
			}
		})
	}
}

func TestValidateSeedAcceptsBlankOrWholeNumbers(t *testing.T) {
	for _, tc := range []struct {
		name    string
		value   string
		wantErr bool
	}{
		{"blank means a random seed", "", false},
		{"zero is a valid seed", "0", false},
		{"negative seeds are accepted", "-42", false},
		{"large seeds are accepted", "4294967296", false},
		{"non-numeric is rejected", "not-a-number", true},
		{"fractional is rejected", "1.5", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			err := validateSeed(tc.value)
			if tc.wantErr && err == nil {
				t.Fatalf("validateSeed(%q) accepted a value it should reject", tc.value)
			}
			if !tc.wantErr && err != nil {
				t.Fatalf("validateSeed(%q) rejected a valid value: %v", tc.value, err)
			}
			if err != nil && !strings.Contains(err.Error(), "Seed") {
				t.Fatalf("error %q does not name the field", err)
			}
		})
	}
}

// --- form-level behaviour ---

// TestLauncherRejectsInvalidMaxSteps pins that huh validates before the run is
// created: the model used to validate on Enter itself and stash the message in
// validationErr, which the field validator replaces.
func TestLauncherRejectsInvalidMaxSteps(t *testing.T) {
	m := newFocusedLauncher()
	m = typeInto(m, "abc")

	updated, cmd := m.Update(enterKey())
	m = updated

	if cmd != nil {
		t.Fatal("invalid max steps should not produce a command")
	}
	if m.launching {
		t.Fatal("launcher should not enter launching state with invalid max steps")
	}
	errs := m.form.Errors()
	if len(errs) == 0 {
		t.Fatal("expected the form to report a Max Steps validation error")
	}
	if !strings.Contains(errs[0].Error(), "Max steps") {
		t.Fatalf("expected a max steps validation error, got %q", errs[0])
	}
	if m.form.State == huh.StateCompleted {
		t.Fatal("form completed despite an invalid max steps value")
	}
}

// TestLauncherRejectsInvalidSeed covers the second validator: get past Max
// Steps (left blank = backend default), then type garbage into Seed.
func TestLauncherRejectsInvalidSeed(t *testing.T) {
	m := newFocusedLauncher()
	m = advance(m)
	m = typeInto(m, "not-a-number")

	updated, cmd := m.Update(enterKey())
	m = updated

	if cmd != nil {
		t.Fatal("invalid seed should not produce a command")
	}
	if m.launching {
		t.Fatal("launcher should not enter launching state with an invalid seed")
	}
	errs := m.form.Errors()
	if len(errs) == 0 {
		t.Fatal("expected the form to report a Seed validation error")
	}
	if !strings.Contains(errs[0].Error(), "Seed") {
		t.Fatalf("expected a seed validation error, got %q", errs[0])
	}
}

// TestLauncherSubmitsValidForm covers the happy path end to end: fill both
// inputs, walk to the provider field and submit. The run cannot be created
// (there is no server), so the assertion is that the submit path fired and
// surfaced the failure instead of silently doing nothing.
func TestLauncherSubmitsValidForm(t *testing.T) {
	m := newFocusedLauncher()

	m = typeInto(m, "10")
	m = advance(m)
	m = typeInto(m, "7")
	m = advance(m)
	m = advance(m)
	m = completeForm(m)

	if m.form.State != huh.StateCompleted {
		t.Fatalf("form state = %v, want StateCompleted after submitting every field", m.form.State)
	}
	if m.answers.maxSteps != "10" {
		t.Errorf("max steps bound value = %q, want %q", m.answers.maxSteps, "10")
	}
	if m.answers.seed != "7" {
		t.Errorf("seed bound value = %q, want %q", m.answers.seed, "7")
	}
	if m.answers.provider != "vllm" {
		t.Errorf("provider bound value = %q, want the vllm default", m.answers.provider)
	}

	// The screen dispatches the run on the next message it processes; hand it
	// the resize it would receive anyway and capture what it emits.
	m, cmd := m.Update(tea.WindowSizeMsg{Width: 120, Height: 36})
	if cmd == nil {
		t.Fatal("completing the form did not dispatch a run creation")
	}
	if !m.launching {
		t.Fatal("launcher did not enter the launching state on submit")
	}

	// The run cannot be created (there is no server), so the failure must be
	// surfaced and the launcher left usable.
	m, _ = m.Update(cmd())
	if m.launching {
		t.Error("launcher stayed in the launching state after the run request failed")
	}
	if m.err == nil {
		t.Fatal("expected the failed run request to surface an error")
	}
}

// TestLauncherAnswersSurviveValueCopies guards the pointer indirection the
// bound fields rely on: models are copied by value on every Update, so the
// storage the fields write into must be shared, not copied.
func TestLauncherAnswersSurviveValueCopies(t *testing.T) {
	m := newFocusedLauncher()
	copied := m // simulate the Elm-architecture copy
	copied.answers.maxSteps = "42"

	if m.answers.maxSteps != "42" {
		t.Fatal("answers are not shared between model copies; typed values would be lost")
	}
}

func TestLauncherQReturnsToScenarios(t *testing.T) {
	m := NewLauncherModel(nil, "scenario-1")

	_, cmd := m.Update(tea.KeyPressMsg{Code: 'q', Text: "q"})
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

func TestLauncherEscReturnsToScenarios(t *testing.T) {
	m := NewLauncherModel(nil, "scenario-1")

	_, cmd := m.Update(tea.KeyPressMsg{Code: tea.KeyEscape})
	if cmd == nil {
		t.Fatal("esc should produce a screen switch command")
	}
	sw, ok := cmd().(SwitchScreenMsg)
	if !ok {
		t.Fatalf("expected SwitchScreenMsg, got %T", cmd())
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
	m = size(m, 80, 24)

	out := m.View(80, 24)
	for _, line := range strings.Split(out, "\n") {
		if got := lipgloss.Width(line); got > 80 {
			t.Fatalf("line width %d exceeds 80 columns: %q", got, line)
		}
	}
}

// TestLauncherRendersProviderChoices pins that the inline Select shows every
// provider, so the picker is not silently reduced to the selected one.
func TestLauncherRendersProviderChoices(t *testing.T) {
	m := NewLauncherModel(nil, "scenario-1")
	m = size(m, 100, 30)
	m = focusFirstField(m)

	out := m.View(100, 30)
	for _, want := range []string{"vLLM (default)", "Ollama", "OpenAI/OCA"} {
		if !strings.Contains(out, want) {
			t.Errorf("provider picker is missing %q: %q", want, out)
		}
	}
}
