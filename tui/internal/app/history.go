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

type runsLoadedMsg struct {
	runs []api.RunResponse
	err  error
}

// --- runItem implements list.Item ---

type runItem struct {
	run api.RunResponse
}

func (i runItem) FilterValue() string { return i.run.ID }

// --- Custom delegate ---

type runDelegate struct{}

func (d runDelegate) Height() int                               { return 2 }
func (d runDelegate) Spacing() int                              { return 1 }
func (d runDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }

func (d runDelegate) Render(w io.Writer, m list.Model, index int, listItem list.Item) {
	item, ok := listItem.(runItem)
	if !ok {
		return
	}

	r := item.run
	isSelected := index == m.Index()

	// ID (first 8 chars)
	idStr := r.ID
	if len(idStr) > 8 {
		idStr = idStr[:8]
	}

	var nameStyle lipgloss.Style
	if isSelected {
		nameStyle = lipgloss.NewStyle().Bold(true).Foreground(theme.Primary)
	} else {
		nameStyle = theme.Title
	}

	statusStyle := lipgloss.NewStyle().Foreground(theme.StatusColor(r.Status))

	cursor := "  "
	if isSelected {
		cursor = theme.Subtitle.Render("> ")
	}

	line1 := fmt.Sprintf("%s%s  %s  Step %d/%d",
		cursor,
		nameStyle.Render("#"+idStr),
		statusStyle.Render(r.Status),
		r.CurrentStep,
		r.MaxSteps,
	)

	scenarioInfo := theme.MutedText.Render(fmt.Sprintf("    scenario: %s", r.ScenarioID))

	fmt.Fprintf(w, "%s\n%s", line1, scenarioInfo)
}

// --- HistoryModel ---

// HistoryModel is the run history browser screen.
type HistoryModel struct {
	client  *api.Client
	list    list.Model
	loading bool
	errMsg  string
}

// NewHistoryModel creates a new history browser.
func NewHistoryModel(client *api.Client) HistoryModel {
	delegate := runDelegate{}
	l := list.New([]list.Item{}, delegate, 0, 0)
	l.Title = "Run History"
	l.SetShowStatusBar(true)
	l.SetFilteringEnabled(true)
	l.Styles.Title = theme.Title
	l.SetShowHelp(false)

	return HistoryModel{
		client:  client,
		list:    l,
		loading: true,
	}
}

// Init fetches runs from the backend.
func (m HistoryModel) Init() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		runs, err := client.ListRuns("", 50)
		return runsLoadedMsg{runs: runs, err: err}
	}
}

// Update handles list navigation and key input.
func (m HistoryModel) Update(msg tea.Msg) (HistoryModel, tea.Cmd) {
	switch msg := msg.(type) {
	case runsLoadedMsg:
		m.loading = false
		if msg.err != nil {
			m.errMsg = msg.err.Error()
			return m, nil
		}
		items := make([]list.Item, len(msg.runs))
		for i, r := range msg.runs {
			items[i] = runItem{run: r}
		}
		m.list.SetItems(items)
		return m, nil

	case tea.WindowSizeMsg:
		m.list.SetSize(msg.Width, msg.Height-2)
		return m, nil

	case tea.KeyMsg:
		if m.list.FilterState() == list.Filtering {
			break
		}
		switch msg.String() {
		case "enter":
			if item, ok := m.list.SelectedItem().(runItem); ok {
				return m, func() tea.Msg {
					return SwitchScreenMsg{
						Screen: ScreenDashboard,
						Data:   item.run.ID,
					}
				}
			}
		case "q", "esc":
			return m, func() tea.Msg {
				return SwitchScreenMsg{Screen: ScreenScenarios}
			}
		}
	}

	var cmd tea.Cmd
	m.list, cmd = m.list.Update(msg)
	return m, cmd
}

// View renders the history list.
func (m HistoryModel) View(width, height int) string {
	if m.errMsg != "" {
		errView := theme.ErrorText.Render("Failed to load runs: "+m.errMsg) +
			"\n\n" + theme.KeyName.Render("q") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, errView)
	}

	if m.loading {
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
			theme.MutedText.Render("Loading run history..."))
	}

	m.list.SetSize(width, height-2)

	hints := theme.KeyName.Render("Enter") + theme.KeyHint.Render(" view") +
		"  " + theme.KeyName.Render("↑/↓") + theme.KeyHint.Render(" navigate") +
		"  " + theme.KeyName.Render("q") + theme.KeyHint.Render(" back")

	return m.list.View() + "\n" + hints
}
