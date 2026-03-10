package app

import (
	"fmt"
	"strconv"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
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

// --- LauncherModel ---

// LauncherModel is the run configuration/launch screen.
type LauncherModel struct {
	client     *api.Client
	scenarioID string
	scenario   *api.ScenarioResponse
	err        error

	maxStepsInput textinput.Model
	seedInput     textinput.Model
	focusIndex    int
	launching     bool
}

// NewLauncherModel creates a launcher for the given scenario.
func NewLauncherModel(client *api.Client, scenarioID string) LauncherModel {
	maxSteps := textinput.New()
	maxSteps.Placeholder = "50"
	maxSteps.CharLimit = 5
	maxSteps.Width = 20
	maxSteps.Prompt = "Max Steps: "
	maxSteps.Focus()

	seed := textinput.New()
	seed.Placeholder = "random"
	seed.CharLimit = 10
	seed.Width = 20
	seed.Prompt = "Seed:      "

	return LauncherModel{
		client:        client,
		scenarioID:    scenarioID,
		maxStepsInput: maxSteps,
		seedInput:     seed,
		focusIndex:    0,
	}
}

// Init fetches the scenario detail.
func (m LauncherModel) Init() tea.Cmd {
	client := m.client
	id := m.scenarioID
	return func() tea.Msg {
		s, err := client.GetScenario(id)
		return scenarioDetailMsg{scenario: s, err: err}
	}
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

	case tea.KeyMsg:
		switch msg.String() {
		case "tab", "shift+tab":
			if msg.String() == "tab" {
				m.focusIndex = (m.focusIndex + 1) % 2
			} else {
				m.focusIndex = (m.focusIndex - 1 + 2) % 2
			}
			if m.focusIndex == 0 {
				m.maxStepsInput.Focus()
				m.seedInput.Blur()
			} else {
				m.maxStepsInput.Blur()
				m.seedInput.Focus()
			}
			return m, nil

		case "enter":
			if m.launching {
				return m, nil
			}
			m.launching = true
			return m, m.createRun()

		case "esc":
			return m, func() tea.Msg {
				return SwitchScreenMsg{Screen: ScreenScenarios}
			}
		}
	}

	// Update focused input
	var cmd tea.Cmd
	if m.focusIndex == 0 {
		m.maxStepsInput, cmd = m.maxStepsInput.Update(msg)
	} else {
		m.seedInput, cmd = m.seedInput.Update(msg)
	}
	return m, cmd
}

// View renders the launcher form.
func (m LauncherModel) View(width, height int) string {
	if m.err != nil && m.scenario == nil {
		errView := theme.ErrorText.Render("Error: "+m.err.Error()) +
			"\n\n" + theme.KeyName.Render("Esc") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, errView)
	}

	var title string
	if m.scenario != nil {
		title = theme.Title.Render("Launch: "+m.scenario.Name) + "\n" +
			theme.MutedText.Render(m.scenario.Description) + "\n" +
			theme.MutedText.Render(fmt.Sprintf("%d agent templates", len(m.scenario.AgentTemplates)))
	} else {
		title = theme.MutedText.Render("Loading scenario...")
	}

	form := lipgloss.JoinVertical(lipgloss.Left,
		title,
		"",
		m.maxStepsInput.View(),
		"",
		m.seedInput.View(),
	)

	if m.launching {
		form += "\n\n" + theme.MutedText.Render("Creating run...")
	} else if m.err != nil {
		form += "\n\n" + theme.ErrorText.Render("Error: "+m.err.Error())
	}

	hints := "\n\n" +
		theme.KeyName.Render("Tab") + theme.KeyHint.Render(" switch field") +
		"  " + theme.KeyName.Render("Enter") + theme.KeyHint.Render(" launch") +
		"  " + theme.KeyName.Render("Esc") + theme.KeyHint.Render(" back")
	form += hints

	box := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Primary).
		Padding(2, 4).
		Render(form)

	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, box)
}

// createRun builds the RunCreate request and posts it.
func (m LauncherModel) createRun() tea.Cmd {
	client := m.client
	scenarioID := m.scenarioID
	maxStepsStr := m.maxStepsInput.Value()
	seedStr := m.seedInput.Value()

	return func() tea.Msg {
		req := api.RunCreate{
			ScenarioID: scenarioID,
		}

		if maxStepsStr != "" {
			if v, err := strconv.Atoi(maxStepsStr); err == nil {
				req.MaxSteps = &v
			}
		}
		if seedStr != "" {
			if v, err := strconv.Atoi(seedStr); err == nil {
				req.Seed = &v
			}
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
