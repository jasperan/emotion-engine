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

// --- Inference providers ---

var inferenceProviders = []string{"vllm", "ollama", "openai"}

var providerLabels = map[string]string{
	"vllm":   "vLLM (local, default)",
	"ollama": "Ollama (local)",
	"openai": "OpenAI / OCA (remote)",
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
	providerIndex int // index into inferenceProviders
	focusIndex    int // 0=maxSteps, 1=seed, 2=provider
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
		providerIndex: 0, // vllm default
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
			numFields := 3
			if msg.String() == "tab" {
				m.focusIndex = (m.focusIndex + 1) % numFields
			} else {
				m.focusIndex = (m.focusIndex - 1 + numFields) % numFields
			}
			// Update focus states
			m.maxStepsInput.Blur()
			m.seedInput.Blur()
			switch m.focusIndex {
			case 0:
				m.maxStepsInput.Focus()
			case 1:
				m.seedInput.Focus()
			// case 2: provider selector (no text input focus needed)
			}
			return m, nil

		case "left", "h":
			if m.focusIndex == 2 {
				m.providerIndex = (m.providerIndex - 1 + len(inferenceProviders)) % len(inferenceProviders)
				return m, nil
			}

		case "right", "l":
			if m.focusIndex == 2 {
				m.providerIndex = (m.providerIndex + 1) % len(inferenceProviders)
				return m, nil
			}

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

	// Update focused text input
	var cmd tea.Cmd
	switch m.focusIndex {
	case 0:
		m.maxStepsInput, cmd = m.maxStepsInput.Update(msg)
	case 1:
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

	// Build provider selector
	providerView := m.renderProviderSelector()

	form := lipgloss.JoinVertical(lipgloss.Left,
		title,
		"",
		m.maxStepsInput.View(),
		"",
		m.seedInput.View(),
		"",
		providerView,
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
	if m.focusIndex == 2 {
		hints = "\n\n" +
			theme.KeyName.Render("←/→") + theme.KeyHint.Render(" change provider") +
			"  " + theme.KeyName.Render("Tab") + theme.KeyHint.Render(" switch field") +
			"  " + theme.KeyName.Render("Enter") + theme.KeyHint.Render(" launch") +
			"  " + theme.KeyName.Render("Esc") + theme.KeyHint.Render(" back")
	}
	form += hints

	box := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Primary).
		Padding(2, 4).
		Render(form)

	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, box)
}

// renderProviderSelector builds the inline provider picker.
func (m LauncherModel) renderProviderSelector() string {
	focused := m.focusIndex == 2

	label := "Inference: "
	if focused {
		label = lipgloss.NewStyle().Foreground(theme.Primary).Render(label)
	} else {
		label = theme.MutedText.Render(label)
	}

	var pills []string
	for i, p := range inferenceProviders {
		text := providerLabels[p]
		if i == m.providerIndex {
			// Selected pill
			style := lipgloss.NewStyle().
				Bold(true).
				Foreground(lipgloss.Color("#000000")).
				Background(theme.Primary).
				Padding(0, 1)
			if focused {
				pills = append(pills, style.Render(text))
			} else {
				// Selected but field not focused: dimmer highlight
				style = style.Background(theme.Secondary)
				pills = append(pills, style.Render(text))
			}
		} else {
			// Unselected pill
			style := lipgloss.NewStyle().
				Foreground(theme.Muted).
				Padding(0, 1)
			pills = append(pills, style.Render(text))
		}
	}

	return label + lipgloss.JoinHorizontal(lipgloss.Center, pills...)
}

// createRun builds the RunCreate request and posts it.
func (m LauncherModel) createRun() tea.Cmd {
	client := m.client
	scenarioID := m.scenarioID
	maxStepsStr := m.maxStepsInput.Value()
	seedStr := m.seedInput.Value()
	selectedProvider := inferenceProviders[m.providerIndex]

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

		// Only send llm_backend if not the default (vllm)
		if selectedProvider != "vllm" {
			req.LLMBackend = &selectedProvider
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
