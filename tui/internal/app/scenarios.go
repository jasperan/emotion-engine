package app

import (
	"fmt"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"charm.land/lipgloss/v2"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/huhstyle"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// --- Messages ---

type scenariosLoadedMsg struct {
	scenarios []api.ScenarioResponse
	err       error
}

const keyScenario = "scenario"

// scenarioSelection is the storage the scenario Select is bound to. It is a
// pointer for the same reason launcherAnswers is: the Elm architecture copies
// models by value, so a bound field must live where every copy can see it.
type scenarioSelection struct {
	id string
}

// scenarioOptionLabel is the option text for a scenario. The old list delegate
// drew the name, the agent count and the description on three lines; a Select
// option is a single line, so the count joins the label and the description is
// rendered beneath the form for the option under the cursor.
func scenarioOptionLabel(s api.ScenarioResponse) string {
	return fmt.Sprintf("%s (%d agents)", s.Name, len(s.AgentTemplates))
}

// buildScenarioForm builds the scenario browser as a huh form.
func buildScenarioForm(scenarios []api.ScenarioResponse, sel *scenarioSelection) (*huh.Form, *huh.Select[string]) {
	opts := make([]huh.Option[string], 0, len(scenarios))
	for _, s := range scenarios {
		opts = append(opts, huh.NewOption(scenarioOptionLabel(s), s.ID))
	}

	selectField := huh.NewSelect[string]().
		Key(keyScenario).
		Title("Scenarios").
		Description("Pick a scenario to configure and launch.").
		Options(opts...).
		Value(&sel.id)

	form := huh.NewForm(huh.NewGroup(selectField)).
		WithTheme(huh.ThemeFunc(huhstyle.Theme)).
		WithAccessible(huhstyle.Accessible()).
		// The screen draws its own hint bar from footerBindingsForScreen, and
		// the F1 overlay documents the same keys. huh's footer would be a
		// second, differently-worded copy of the same hints.
		WithShowHelp(false)

	return form, selectField
}

// --- ScenarioModel ---

// ScenarioModel is the scenario browser screen.
type ScenarioModel struct {
	client    *api.Client
	scenarios []api.ScenarioResponse
	selection *scenarioSelection
	form      *huh.Form
	selectF   *huh.Select[string]
	loaded    bool
	err       error

	// width and height are the last size reported by tea.WindowSizeMsg. The
	// form is sized from these in Update, because huh rebuilds a form's content
	// on Update and a width applied during View would land a frame too late.
	width  int
	height int
}

// NewScenarioModel creates a new scenario browser.
func NewScenarioModel(client *api.Client) ScenarioModel {
	return ScenarioModel{
		client:    client,
		selection: &scenarioSelection{},
	}
}

// Init fetches scenarios from the backend.
func (m ScenarioModel) Init() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		scenarios, err := client.ListScenarios()
		return scenariosLoadedMsg{scenarios: scenarios, err: err}
	}
}

// Update handles list navigation and key input.
func (m ScenarioModel) Update(msg tea.Msg) (ScenarioModel, tea.Cmd) {
	switch msg := msg.(type) {
	case scenariosLoadedMsg:
		if msg.err != nil {
			m.err = msg.err
			return m, nil
		}
		// The options only exist once the scenarios are known, so the form is
		// built here rather than in the constructor.
		m.scenarios = msg.scenarios
		m.form, m.selectF = buildScenarioForm(msg.scenarios, m.selection)
		m.loaded = true
		m.resizeForm()
		return m, m.form.Init()

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.resizeForm()
		// Still delegated to the form below, which is what rebuilds its content.

	case tea.KeyPressMsg:
		// The Select owns every key while its "/" filter is capturing input, so
		// the screen bindings only apply once filtering has stopped.
		if m.selectF != nil && !m.selectF.GetFiltering() {
			switch msg.String() {
			case "h":
				return m, switchTo(ScreenHistory)
			case "a":
				return m, switchTo(ScreenAnalytics)
			case "q", "esc":
				return m, switchTo(ScreenSplash)
			}
		}
	}

	if m.form == nil {
		return m, nil
	}

	model, cmd := m.form.Update(msg)
	if form, ok := model.(*huh.Form); ok {
		m.form = form
	}
	if m.form.State == huh.StateCompleted {
		return m, switchToData(ScreenLauncher, m.selection.id)
	}
	return m, cmd
}

// resizeForm applies the last reported terminal size to the form. It is a
// no-op until the form exists, so a size that arrives before the scenarios load
// is applied when the form is built.
func (m *ScenarioModel) resizeForm() {
	if m.form == nil {
		return
	}
	m.form.WithWidth(formContentWidth(m.width))
	m.form.WithHeight(formHeight(m.height))
	m.selectF.Height(selectHeight(m.height, len(m.scenarios)))
}

// hoveredScenario returns the scenario under the cursor.
func (m ScenarioModel) hoveredScenario() (api.ScenarioResponse, bool) {
	if m.selectF == nil {
		return api.ScenarioResponse{}, false
	}
	id, ok := m.selectF.Hovered()
	if !ok {
		return api.ScenarioResponse{}, false
	}
	for _, s := range m.scenarios {
		if s.ID == id {
			return s, true
		}
	}
	return api.ScenarioResponse{}, false
}

// View renders the scenario browser.
func (m ScenarioModel) View(width, height int) string {
	if m.err != nil {
		errView := theme.ErrorText.Render("Failed to load scenarios: "+m.err.Error()) +
			"\n\n" + theme.KeyName.Render("q/Esc") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, errView)
	}
	if !m.loaded {
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
			theme.MutedText.Render("Loading scenarios..."))
	}

	contentWidth := formContentWidth(width)

	body := trimFormPad(m.form.View())
	if s, ok := m.hoveredScenario(); ok && s.Description != "" {
		body += "\n\n" + theme.MutedText.Width(contentWidth).Render(s.Description)
	}

	hints := hintBar(width, footerBindingsForScreen(ScreenScenarios))

	return lipgloss.Place(width, height-2, lipgloss.Center, lipgloss.Center, body) + "\n" + hints
}
