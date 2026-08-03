package app

import (
	"fmt"
	"strconv"
	"strings"

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

var providerShortLabels = map[string]string{
	"vllm":   "vLLM",
	"ollama": "Ollama",
	"openai": "OpenAI",
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
	validationErr string
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
			if err := m.validateInputs(); err != nil {
				m.validationErr = err.Error()
				return m, nil
			}
			m.validationErr = ""
			m.launching = true
			return m, m.createRun()

		case "q", "esc":
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
		m.validationErr = ""
	case 1:
		m.seedInput, cmd = m.seedInput.Update(msg)
		m.validationErr = ""
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

	contentWidth := launcherContentWidth(width)
	var title string
	if m.scenario != nil {
		title = theme.Title.Render("Launch: "+m.scenario.Name) + "\n" +
			theme.MutedText.Width(contentWidth).Render(m.scenario.Description) + "\n" +
			theme.MutedText.Render(fmt.Sprintf("%d agent templates", len(m.scenario.AgentTemplates)))
	} else {
		title = theme.MutedText.Render("Loading scenario...")
	}

	providerView := m.renderProviderSelector(contentWidth)

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
	} else if m.validationErr != "" {
		form += "\n\n" + theme.ErrorText.Render(m.validationErr)
	} else if m.err != nil {
		form += "\n\n" + theme.ErrorText.Render("Error: "+m.err.Error())
	}

	form += "\n\n" + m.renderHints(contentWidth)

	padY, padX := 2, 4
	if width > 0 && width < 72 || height > 0 && height < 24 {
		padY, padX = 1, 2
	}

	box := lipgloss.NewStyle().
		Width(contentWidth).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Primary).
		Padding(padY, padX).
		Render(form)

	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, box)
}

// renderProviderSelector builds the inline provider picker.
func (m LauncherModel) renderProviderSelector(width int) string {
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
		if width > 0 && width < 72 {
			text = providerShortLabels[p]
		}
		if i == m.providerIndex {
			// Selected pill
			style := lipgloss.NewStyle().
				Bold(true).
				Foreground(theme.Bg).
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

func (m LauncherModel) renderHints(width int) string {
	back := renderLauncherHint("q/Esc", "back")
	if width > 0 && width < 62 {
		if m.focusIndex == 2 {
			return strings.Join([]string{
				renderLauncherHint("left/right", "provider"),
				renderLauncherHint("Enter", "launch"),
				back,
			}, "  ")
		}
		return strings.Join([]string{
			renderLauncherHint("Tab", "field"),
			renderLauncherHint("Enter", "launch"),
			back,
		}, "  ")
	}
	if m.focusIndex == 2 {
		return strings.Join([]string{
			renderLauncherHint("left/right", "change provider"),
			renderLauncherHint("Tab", "switch field"),
			renderLauncherHint("Enter", "launch"),
			back,
		}, "  ")
	}
	return strings.Join([]string{
		renderLauncherHint("Tab", "switch field"),
		renderLauncherHint("Enter", "launch"),
		back,
	}, "  ")
}

func renderLauncherHint(key, desc string) string {
	return theme.KeyName.Render(key) + theme.KeyHint.Render(" "+desc)
}

func launcherContentWidth(width int) int {
	if width <= 0 {
		return 64
	}
	contentWidth := width - 10
	if contentWidth < 36 {
		contentWidth = 36
	}
	if contentWidth > 84 {
		contentWidth = 84
	}
	return contentWidth
}

func (m LauncherModel) validateInputs() error {
	maxStepsStr := strings.TrimSpace(m.maxStepsInput.Value())
	if maxStepsStr != "" {
		v, err := strconv.Atoi(maxStepsStr)
		if err != nil || v < 1 || v > 10000 {
			return fmt.Errorf("Max steps must be a whole number from 1 to 10000.")
		}
	}

	seedStr := strings.TrimSpace(m.seedInput.Value())
	if seedStr != "" {
		if _, err := strconv.Atoi(seedStr); err != nil {
			return fmt.Errorf("Seed must be a whole number, or blank for random.")
		}
	}
	return nil
}

// createRun builds the RunCreate request and posts it.
func (m LauncherModel) createRun() tea.Cmd {
	client := m.client
	scenarioID := m.scenarioID
	maxStepsStr := strings.TrimSpace(m.maxStepsInput.Value())
	seedStr := strings.TrimSpace(m.seedInput.Value())
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
