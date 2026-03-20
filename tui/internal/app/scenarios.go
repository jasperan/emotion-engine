package app

import (
	"fmt"
	"io"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// --- Messages ---

type scenariosLoadedMsg struct {
	scenarios []api.ScenarioResponse
	err       error
}

// --- scenarioItem implements list.Item ---

type scenarioItem struct {
	scenario api.ScenarioResponse
}

func (i scenarioItem) FilterValue() string { return i.scenario.Name }
func (i scenarioItem) Title() string       { return i.scenario.Name }
func (i scenarioItem) Description() string { return i.scenario.Description }

// --- Custom delegate ---

type scenarioDelegate struct{}

func (d scenarioDelegate) Height() int                               { return 3 }
func (d scenarioDelegate) Spacing() int                              { return 1 }
func (d scenarioDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }

func (d scenarioDelegate) Render(w io.Writer, m list.Model, index int, listItem list.Item) {
	item, ok := listItem.(scenarioItem)
	if !ok {
		return
	}

	s := item.scenario
	agentCount := len(s.AgentTemplates)

	isSelected := index == m.Index()

	// Name line
	var nameStyle lipgloss.Style
	if isSelected {
		nameStyle = lipgloss.NewStyle().Bold(true).Foreground(theme.Primary)
	} else {
		nameStyle = theme.Title
	}
	name := nameStyle.Render(s.Name)
	agents := theme.MutedText.Render(fmt.Sprintf(" (%d agents)", agentCount))

	// Description
	desc := s.Description
	if len(desc) > 80 {
		desc = desc[:77] + "..."
	}
	descLine := theme.MutedText.Render("  " + desc)

	// Cursor
	cursor := "  "
	if isSelected {
		cursor = theme.Subtitle.Render("> ")
	}

	fmt.Fprintf(w, "%s%s%s\n%s", cursor, name, agents, descLine)
}

// --- ScenarioModel ---

// ScenarioModel is the scenario browser screen.
type ScenarioModel struct {
	client *api.Client
	list   list.Model
	loaded bool
	err    error
}

// NewScenarioModel creates a new scenario browser.
func NewScenarioModel(client *api.Client) ScenarioModel {
	delegate := scenarioDelegate{}
	l := list.New([]list.Item{}, delegate, 0, 0)
	l.Title = "Scenarios"
	l.SetShowStatusBar(true)
	l.SetFilteringEnabled(true)
	l.Styles.Title = theme.Title
	l.SetShowHelp(false)

	return ScenarioModel{
		client: client,
		list:   l,
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
		items := make([]list.Item, len(msg.scenarios))
		for i, s := range msg.scenarios {
			items[i] = scenarioItem{scenario: s}
		}
		m.list.SetItems(items)
		m.loaded = true
		return m, nil

	case tea.KeyMsg:
		// Don't intercept keys when filtering is active.
		if m.list.FilterState() == list.Filtering {
			break
		}
		switch msg.String() {
		case "enter":
			if item, ok := m.list.SelectedItem().(scenarioItem); ok {
				return m, func() tea.Msg {
					return SwitchScreenMsg{
						Screen: ScreenLauncher,
						Data:   item.scenario.ID,
					}
				}
			}
		case "h":
			return m, func() tea.Msg {
				return SwitchScreenMsg{Screen: ScreenHistory}
			}
		case "a":
			return m, func() tea.Msg {
				return SwitchScreenMsg{Screen: ScreenAnalytics}
			}
		case "q", "esc":
			return m, func() tea.Msg {
				return SwitchScreenMsg{Screen: ScreenSplash}
			}
		}
	}

	var cmd tea.Cmd
	m.list, cmd = m.list.Update(msg)
	return m, cmd
}

// View renders the scenario list.
func (m ScenarioModel) View(width, height int) string {
	if m.err != nil {
		errView := theme.ErrorText.Render("Failed to load scenarios: " + m.err.Error()) +
			"\n\n" + theme.KeyName.Render("q") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, errView)
	}

	m.list.SetSize(width, height-2)

	hints := theme.KeyName.Render("Enter") + theme.KeyHint.Render(" launch") +
		"  " + theme.KeyName.Render("/") + theme.KeyHint.Render(" filter") +
		"  " + theme.KeyName.Render("q") + theme.KeyHint.Render(" back")

	return m.list.View() + "\n" + hints
}
