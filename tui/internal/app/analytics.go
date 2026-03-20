package app

import (
	"fmt"
	"sort"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// analyticsLoadedMsg carries the result of fetching datalake data.
type analyticsLoadedMsg struct {
	runs  []map[string]interface{}
	stats map[string]interface{}
	err   error
}

// analyticsRunsReloadedMsg carries a refreshed run list after scenario filter change.
type analyticsRunsReloadedMsg struct {
	runs []map[string]interface{}
	err  error
}

// AnalyticsModel is the cross-run analysis screen.
type AnalyticsModel struct {
	client      *api.Client
	runs        []map[string]interface{}
	stats       map[string]interface{}
	scenarios   []string
	selScenario int
	available   bool
	err         error
	selectedRun int
}

// NewAnalyticsModel creates a fresh analytics screen.
func NewAnalyticsModel(client *api.Client) AnalyticsModel {
	return AnalyticsModel{client: client}
}

// Init fetches datalake stats and runs.
func (m AnalyticsModel) Init() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		stats, err := client.DatalakeStats()
		if err != nil {
			return analyticsLoadedMsg{err: err}
		}
		runs, _ := client.DatalakeRuns("", 100)
		return analyticsLoadedMsg{stats: stats, runs: runs}
	}
}

// Update handles messages and key input.
func (m AnalyticsModel) Update(msg tea.Msg) (AnalyticsModel, tea.Cmd) {
	switch msg := msg.(type) {
	case analyticsLoadedMsg:
		if msg.err != nil {
			m.available = false
			m.err = msg.err
			return m, nil
		}
		m.available = true
		m.stats = msg.stats
		m.runs = msg.runs
		m.scenarios = buildScenarioList(msg.runs)
		m.selScenario = 0
		m.selectedRun = 0
		return m, nil

	case analyticsRunsReloadedMsg:
		if msg.err == nil {
			m.runs = msg.runs
			m.selectedRun = 0
		}
		return m, nil

	case tea.KeyMsg:
		if !m.available {
			switch msg.String() {
			case "q", "esc":
				return m, func() tea.Msg { return SwitchScreenMsg{Screen: ScreenScenarios} }
			}
			return m, nil
		}
		switch msg.String() {
		case "s":
			m.selScenario = (m.selScenario + 1) % len(m.scenarios)
			m.selectedRun = 0
			return m, m.reloadRuns()
		case "j", "down":
			if m.selectedRun < len(m.runs)-1 {
				m.selectedRun++
			}
		case "k", "up":
			if m.selectedRun > 0 {
				m.selectedRun--
			}
		case "enter":
			if len(m.runs) > 0 && m.selectedRun < len(m.runs) {
				run := m.runs[m.selectedRun]
				runID, _ := run["id"].(string)
				if runID != "" {
					return m, func() tea.Msg {
						return SwitchScreenMsg{Screen: ScreenReplay, Data: runID}
					}
				}
			}
		case "q", "esc":
			return m, func() tea.Msg { return SwitchScreenMsg{Screen: ScreenScenarios} }
		}
	}
	return m, nil
}

// reloadRuns fetches runs for the currently selected scenario filter.
func (m AnalyticsModel) reloadRuns() tea.Cmd {
	client := m.client
	scenarioFilter := ""
	if m.selScenario > 0 && m.selScenario < len(m.scenarios) {
		scenarioFilter = m.scenarios[m.selScenario]
	}
	return func() tea.Msg {
		runs, err := client.DatalakeRuns(scenarioFilter, 100)
		return analyticsRunsReloadedMsg{runs: runs, err: err}
	}
}

// View renders the analytics screen.
func (m AnalyticsModel) View(width, height int) string {
	if !m.available {
		return m.unavailableView(width, height)
	}

	// Status bar.
	scenarioLabel := "All"
	if m.selScenario > 0 && m.selScenario < len(m.scenarios) {
		scenarioLabel = m.scenarios[m.selScenario]
	}
	statusBar := theme.StatusBar.Width(width).Render(
		"  " + theme.KeyName.Render("Filter:") + " " + scenarioLabel +
			"  " + theme.MutedText.Render(fmt.Sprintf("%d runs", len(m.runs))),
	)

	// Hint bar.
	hints := theme.KeyName.Render("s") + theme.KeyHint.Render(" cycle filter") +
		"  " + theme.KeyName.Render("j/k") + theme.KeyHint.Render(" select") +
		"  " + theme.KeyName.Render("Enter") + theme.KeyHint.Render(" replay") +
		"  " + theme.KeyName.Render("q") + theme.KeyHint.Render(" back")

	bodyHeight := height - 2 // status + hints
	leftWidth := width / 2
	rightWidth := width - leftWidth

	leftPanel := m.renderRunList(leftWidth, bodyHeight)
	rightPanel := m.renderStats(rightWidth, bodyHeight)

	body := lipgloss.JoinHorizontal(lipgloss.Top, leftPanel, rightPanel)

	return statusBar + "\n" + body + "\n" + hints
}

// renderRunList draws the scrollable run list with cursor.
func (m AnalyticsModel) renderRunList(width, height int) string {
	title := theme.Title.Render("Runs") + "\n"

	if len(m.runs) == 0 {
		content := title + theme.MutedText.Render("  No runs found")
		return lipgloss.NewStyle().Width(width).Height(height).Render(content)
	}

	// Visible window.
	visible := height - 2 // title + possible scroll indicator
	if visible < 1 {
		visible = 1
	}

	start := 0
	if m.selectedRun >= visible {
		start = m.selectedRun - visible + 1
	}
	end := start + visible
	if end > len(m.runs) {
		end = len(m.runs)
	}

	var sb strings.Builder
	sb.WriteString(title)

	for i := start; i < end; i++ {
		run := m.runs[i]
		id, _ := run["id"].(string)
		if len(id) > 8 {
			id = id[:8]
		}
		status, _ := run["status"].(string)
		if status == "" {
			status = "unknown"
		}

		statusStyle := lipgloss.NewStyle().Foreground(theme.StatusColor(status))
		cursor := "  "
		if i == m.selectedRun {
			cursor = theme.Subtitle.Render("> ")
		}

		line := cursor + theme.Title.Render("#"+id) + "  " + statusStyle.Render(status)
		sb.WriteString(line + "\n")
	}

	return lipgloss.NewStyle().Width(width).Height(height).Render(sb.String())
}

// renderStats draws the key/value stats summary.
func (m AnalyticsModel) renderStats(width, height int) string {
	title := theme.Title.Render("Datalake Stats") + "\n"

	if len(m.stats) == 0 {
		content := title + theme.MutedText.Render("  No stats available")
		return lipgloss.NewStyle().Width(width).Height(height).Render(content)
	}

	// Stable key order.
	keys := make([]string, 0, len(m.stats))
	for k := range m.stats {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	var sb strings.Builder
	sb.WriteString(title)

	for _, k := range keys {
		v := m.stats[k]
		valStr := fmt.Sprintf("%v", v)
		row := "  " + theme.KeyName.Render(k+":") + " " + theme.MutedText.Render(valStr)
		sb.WriteString(row + "\n")
	}

	return lipgloss.NewStyle().Width(width).Height(height).Render(sb.String())
}

// unavailableView shows a centered explanation panel.
func (m AnalyticsModel) unavailableView(width, height int) string {
	msg := theme.Title.Render("Datalake not available") + "\n\n" +
		theme.MutedText.Render("The datalake API is disabled on this backend.") + "\n" +
		theme.MutedText.Render("Enable it by setting the environment variable:") + "\n\n" +
		theme.KeyName.Render("  DATALAKE_ENABLED=true") + "\n\n" +
		theme.KeyHint.Render("q / esc") + theme.MutedText.Render("  back")

	panel := lipgloss.NewStyle().
		Padding(2, 4).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Muted).
		Render(msg)

	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, panel)
}

// buildScenarioList extracts unique scenario names and prepends "All".
func buildScenarioList(runs []map[string]interface{}) []string {
	seen := map[string]struct{}{}
	var names []string
	for _, r := range runs {
		name, _ := r["scenario_name"].(string)
		if name == "" {
			continue
		}
		if _, ok := seen[name]; !ok {
			seen[name] = struct{}{}
			names = append(names, name)
		}
	}
	sort.Strings(names)
	return append([]string{"All"}, names...)
}
