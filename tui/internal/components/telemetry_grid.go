package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// AgentTelemetryInfo holds operational metrics for one agent.
type AgentTelemetryInfo struct {
	Name             string
	Status           string  // "healthy", "recovering", "degraded", "failed"
	AvgTickMs        float64
	TokensUsed       int
	ActionCount      int
	MessagesSent     int
	MessagesReceived int
	StaleScore       float64 // 0.0-1.0
}

// TelemetryGridData holds everything for the telemetry panel.
type TelemetryGridData struct {
	Agents []AgentTelemetryInfo
	Width  int
	Height int
}

// statusDot returns a colored dot for agent health status.
func telemetryStatusDot(status string) string {
	switch status {
	case "healthy":
		return lipgloss.NewStyle().Foreground(theme.Accent).Render(theme.StatusDot)
	case "recovering":
		return lipgloss.NewStyle().Foreground(theme.Warning).Render(theme.StatusDot)
	case "degraded":
		return lipgloss.NewStyle().Foreground(lipgloss.Color("#FF8C3A")).Render(theme.StatusDot)
	case "failed":
		return lipgloss.NewStyle().Foreground(theme.Danger).Render(theme.StatusDot)
	default:
		return lipgloss.NewStyle().Foreground(theme.Muted).Render(theme.StatusDot)
	}
}

// actionMiniBar renders a tiny bar for action count relative to max.
func actionMiniBar(count, maxCount int) string {
	if maxCount == 0 {
		return theme.MutedText.Render("\u2500\u2500\u2500\u2500\u2500") // ─────
	}
	width := 5
	filled := count * width / maxCount
	if filled > width {
		filled = width
	}
	return lipgloss.NewStyle().Foreground(theme.Primary).Render(strings.Repeat("\u2588", filled)) +
		theme.MutedText.Render(strings.Repeat("\u2591", width-filled))
}

// RenderTelemetryGrid renders the agent telemetry table.
func RenderTelemetryGrid(d TelemetryGridData) string {
	var lines []string
	lines = append(lines, theme.Subtitle.Render("AGENT TELEMETRY"))
	lines = append(lines, "")

	if len(d.Agents) == 0 {
		lines = append(lines, theme.MutedText.Render("No telemetry data yet..."))
		return strings.Join(lines, "\n")
	}

	// Find max action count for relative bar
	maxActions := 1
	for _, a := range d.Agents {
		if a.ActionCount > maxActions {
			maxActions = a.ActionCount
		}
	}

	// Header
	nameW := 12
	header := lipgloss.NewStyle().Width(nameW+3).Foreground(theme.Muted).Render("Agent") +
		lipgloss.NewStyle().Width(7).Foreground(theme.Muted).Render("Tick") +
		lipgloss.NewStyle().Width(7).Foreground(theme.Muted).Render("Tok") +
		lipgloss.NewStyle().Width(7).Foreground(theme.Muted).Render("Acts") +
		lipgloss.NewStyle().Width(5).Foreground(theme.Muted).Render("Msg") +
		lipgloss.NewStyle().Width(6).Foreground(theme.Muted).Render("Stale")
	lines = append(lines, "  "+header)
	lines = append(lines, "  "+theme.MutedText.Render(strings.Repeat("\u2500", d.Width-6)))

	for _, a := range d.Agents {
		dot := telemetryStatusDot(a.Status)
		name := a.Name
		if len(name) > nameW {
			name = name[:nameW]
		}

		// Tick time coloring
		tickStr := fmt.Sprintf("%4.0fms", a.AvgTickMs)
		tickStyle := theme.MutedText
		if a.AvgTickMs > 5000 {
			tickStyle = lipgloss.NewStyle().Foreground(theme.Danger)
		} else if a.AvgTickMs > 2000 {
			tickStyle = lipgloss.NewStyle().Foreground(theme.Warning)
		}

		// Token count
		tokStr := fmt.Sprintf("%5d", a.TokensUsed)
		if a.TokensUsed > 10000 {
			tokStr = fmt.Sprintf("%4.1fk", float64(a.TokensUsed)/1000)
		}

		// Actions mini bar
		actBar := actionMiniBar(a.ActionCount, maxActions)

		// Messages
		msgStr := fmt.Sprintf("%2d/%2d", a.MessagesSent, a.MessagesReceived)

		// Staleness indicator
		staleStr := theme.MutedText.Render("\u00b7") // · low
		if a.StaleScore > 0.7 {
			staleStr = lipgloss.NewStyle().Foreground(theme.Danger).Render("\u26a0") // ⚠
		} else if a.StaleScore > 0.4 {
			staleStr = lipgloss.NewStyle().Foreground(theme.Warning).Render("~")
		}

		row := fmt.Sprintf("  %s %s %s %s %s %s %s",
			dot,
			lipgloss.NewStyle().Width(nameW).Foreground(theme.Text).Render(name),
			tickStyle.Width(7).Render(tickStr),
			lipgloss.NewStyle().Width(7).Foreground(theme.Muted).Render(tokStr),
			actBar,
			theme.MutedText.Width(5).Render(msgStr),
			staleStr,
		)
		lines = append(lines, row)
	}

	return strings.Join(lines, "\n")
}
