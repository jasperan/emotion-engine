package app

import (
	"fmt"
	"strconv"
	"strings"

	"charm.land/bubbles/v2/key"
	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"charm.land/lipgloss/v2"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/huhstyle"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// --- Messages ---

type scenarioDetailMsg struct {
	scenario *api.ScenarioResponse
	err      error
}

type runCreatedMsg struct {
	run *api.RunResponse
	err error
}

// --- Inference providers ---

var inferenceProviders = []string{"vllm", "ollama", "openai"}

// providerLabels are the labels for the inline provider picker. They are kept
// short because the picker lays its options out horizontally: the old screen
// carried a second short-label map plus a width branch to choose between the
// two, which a compact label set and the field description replaces.
var providerLabels = map[string]string{
	"vllm":   "vLLM (default)",
	"ollama": "Ollama",
	"openai": "OpenAI/OCA",
}

const providerDescription = "vLLM runs locally by default. Ollama is a local alternative; OpenAI/OCA is remote."

// Form keys. The values are read back off the form on completion (and by tests)
// rather than off model fields, because LauncherModel is copied by value on
// every Update and bound field pointers would follow the copy, not the model.
const (
	keyMaxSteps = "maxsteps"
	keySeed     = "seed"
	keyProvider = "provider"
)

// launcherAnswers holds the storage the huh fields are bound to.
//
// It is a pointer for the same reason App holds *ProgramRef: the Elm
// architecture copies models by value, so a bound field must live somewhere all
// copies share or the entered values would be written to a discarded copy.
type launcherAnswers struct {
	maxSteps string
	seed     string
	provider string
}

// validateMaxSteps accepts a blank value (use the backend default) or a whole
// number of steps in 1..10000.
func validateMaxSteps(s string) error {
	v := strings.TrimSpace(s)
	if v == "" {
		return nil
	}
	n, err := strconv.Atoi(v)
	if err != nil || n < 1 || n > 10000 {
		return fmt.Errorf("Max steps must be a whole number from 1 to 10000.")
	}
	return nil
}

// validateSeed accepts a blank value (random seed) or a whole number.
func validateSeed(s string) error {
	v := strings.TrimSpace(s)
	if v == "" {
		return nil
	}
	if _, err := strconv.Atoi(v); err != nil {
		return fmt.Errorf("Seed must be a whole number, or blank for random.")
	}
	return nil
}

// buildLauncherForm builds the run configuration form.
//
// huh owns what the screen used to hand-roll: a focusIndex cycled by Tab, manual
// Blur/Focus calls per input, a validationErr string rendered under the fields,
// and a provider pill row driven by a providerIndex. Field validators now report
// inline, and the inline Select reproduces the pill row.
func buildLauncherForm(a *launcherAnswers) *huh.Form {
	opts := make([]huh.Option[string], 0, len(inferenceProviders))
	for _, p := range inferenceProviders {
		opts = append(opts, huh.NewOption(providerLabels[p], p))
	}

	return huh.NewForm(
		huh.NewGroup(
			huh.NewInput().
				Key(keyMaxSteps).
				Title("Max Steps").
				Placeholder("50").
				CharLimit(5).
				Validate(validateMaxSteps).
				Value(&a.maxSteps),
			huh.NewInput().
				Key(keySeed).
				Title("Seed").
				Placeholder("random").
				CharLimit(10).
				Validate(validateSeed).
				Value(&a.seed),
			huh.NewSelect[string]().
				Key(keyProvider).
				Title("Inference").
				Description(providerDescription).
				Inline(true).
				Options(opts...).
				Value(&a.provider),
		),
	).
		WithTheme(huh.ThemeFunc(huhstyle.Theme)).
		WithAccessible(huhstyle.Accessible()).
		// The screen draws its own hint bar from footerBindingsForScreen, and
		// the F1 overlay documents the same keys. huh's footer would be a
		// second, differently-worded copy of the same hints.
		WithShowHelp(false)
}

// --- LauncherModel ---

// LauncherModel is the run configuration/launch screen.
type LauncherModel struct {
	client     *api.Client
	scenarioID string
	scenario   *api.ScenarioResponse
	err        error

	answers *launcherAnswers
	form    *huh.Form

	launching bool
}

// NewLauncherModel creates a launcher for the given scenario.
func NewLauncherModel(client *api.Client, scenarioID string) LauncherModel {
	answers := &launcherAnswers{provider: inferenceProviders[0]} // vllm default
	return LauncherModel{
		client:     client,
		scenarioID: scenarioID,
		answers:    answers,
		form:       buildLauncherForm(answers),
	}
}

// Init fetches the scenario detail and starts the form.
//
// Form.Init is what focuses the first field. A standalone form gets it from
// tea.Program; an embedded one has to schedule it itself, so it is batched with
// the scenario fetch rather than left to the caller.
func (m LauncherModel) Init() tea.Cmd {
	client := m.client
	id := m.scenarioID
	return tea.Batch(
		func() tea.Msg {
			s, err := client.GetScenario(id)
			return scenarioDetailMsg{scenario: s, err: err}
		},
		m.form.Init(),
	)
}

// Update handles form navigation, input, and launch.
func (m LauncherModel) Update(msg tea.Msg) (LauncherModel, tea.Cmd) {
	switch msg := msg.(type) {
	case scenarioDetailMsg:
		if msg.err != nil {
			m.err = msg.err
		} else {
			m.scenario = msg.scenario
		}
		return m, nil

	case runCreatedMsg:
		m.launching = false
		if msg.err != nil {
			m.err = msg.err
			return m, nil
		}
		return m, func() tea.Msg {
			return SwitchScreenMsg{
				Screen: ScreenDashboard,
				Data:   msg.run.ID,
			}
		}

	case tea.WindowSizeMsg:
		// Sized here rather than in View: huh rebuilds a form's content on
		// Update, so a width applied while rendering would not take effect until
		// the next keystroke. Deliberately no return -- the form below still
		// needs the message to rebuild its content at the new size.
		m.form.WithWidth(formContentWidth(msg.Width))
		m.form.WithHeight(formHeight(msg.Height))

	case tea.KeyPressMsg:
		// Back stays outside the form so the documented q/Esc binding keeps
		// working. Both launcher inputs are numeric, so reserving q here cannot
		// swallow a character the user needs to type.
		switch msg.String() {
		case "q", "esc":
			return m, func() tea.Msg {
				return SwitchScreenMsg{Screen: ScreenScenarios}
			}
		}
	}

	if m.launching {
		return m, nil
	}

	model, cmd := m.form.Update(msg)
	if form, ok := model.(*huh.Form); ok {
		m.form = form
	}

	// huh completes the form on the message that follows the last field's
	// submit, so this fires on the update after Enter on the provider field.
	if m.form.State == huh.StateCompleted {
		m.launching = true
		return m, m.createRun()
	}
	return m, cmd
}

// View renders the launcher form.
func (m LauncherModel) View(width, height int) string {
	if m.err != nil && m.scenario == nil {
		errView := theme.ErrorText.Render("Error: "+m.err.Error()) +
			"\n\n" + theme.KeyName.Render("q/Esc") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, errView)
	}

	contentWidth := formContentWidth(width)

	var title string
	if m.scenario != nil {
		title = theme.Title.Render("Launch: "+m.scenario.Name) + "\n" +
			theme.MutedText.Width(contentWidth).Render(m.scenario.Description) + "\n" +
			theme.MutedText.Render(fmt.Sprintf("%d agent templates", len(m.scenario.AgentTemplates)))
	} else {
		title = theme.MutedText.Render("Loading scenario...")
	}

	form := lipgloss.JoinVertical(lipgloss.Left,
		title,
		"",
		trimFormPad(m.form.View()),
	)

	if m.launching {
		form += "\n\n" + theme.MutedText.Render("Creating run...")
	} else if m.err != nil {
		form += "\n\n" + theme.ErrorText.Render("Error: "+m.err.Error())
	}

	form += "\n\n" + m.renderHints(contentWidth)

	// No outer frame: every huh field already renders a rounded focus ring, and
	// nesting those inside a second border reads as double framing.
	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, form)
}

// renderHints builds the launcher footer.
//
// It keeps its own width branches: below 62 columns it falls back to fewer
// hints rather than relying on the help component to elide them. The footer's
// keys are a subset of the ones the F1 overlay documents, which help_test
// asserts.
func (m LauncherModel) renderHints(width int) string {
	back := kb("q/Esc", "back", "q", "esc")
	if width > 0 && width < 62 {
		return hintBar(width, []key.Binding{
			kb("Enter", "launch", "enter"),
			back,
		})
	}
	return hintBar(width, []key.Binding{
		kb("Tab", "next field", "tab"),
		kb("←/→", "provider", "left", "right"),
		kb("Enter", "launch", "enter"),
		back,
	})
}

// createRun builds the RunCreate request and posts it.
func (m LauncherModel) createRun() tea.Cmd {
	client := m.client
	scenarioID := m.scenarioID
	answers := m.answers

	return func() tea.Msg {
		req := api.RunCreate{
			ScenarioID: scenarioID,
		}

		if v := strings.TrimSpace(answers.maxSteps); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				req.MaxSteps = &n
			}
		}
		if v := strings.TrimSpace(answers.seed); v != "" {
			if n, err := strconv.Atoi(v); err == nil {
				req.Seed = &n
			}
		}

		// Only send llm_backend if not the default (vllm)
		if answers.provider != "vllm" {
			provider := answers.provider
			req.LLMBackend = &provider
		}

		run, err := client.CreateRun(req)
		if err != nil {
			return runCreatedMsg{err: err}
		}

		// Start the run
		if err := client.ControlRun(run.ID, "start"); err != nil {
			return runCreatedMsg{err: fmt.Errorf("created but failed to start: %w", err)}
		}

		return runCreatedMsg{run: run}
	}
}
