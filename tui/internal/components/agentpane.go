package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// AgentPaneData holds data for rendering a single agent pane.
type AgentPaneData struct {
	ID        string
	Name      string
	Active    bool
	Tokens    string
	LatencyMs int
	Step      int
	Selected  bool
}

// RenderAgentPane renders a bordered pane showing an agent's token stream.
func RenderAgentPane(d AgentPaneData, width, height int) string {
	// Choose border style
	var panelStyle lipgloss.Style
	switch {
	case d.Active:
		panelStyle = theme.GeneratingPanel
	case d.Selected:
		panelStyle = theme.ActivePanel
	default:
		panelStyle = theme.Panel
	}
	panelStyle = panelStyle.Width(width - 2).Height(height - 2) // account for border

	// Header: status dot + name + step/latency
	var dot string
	if d.Active {
		dot = theme.StatusActive.Render(theme.StatusDot)
	} else {
		dot = theme.StatusIdle.Render(theme.StatusDot)
	}

	name := theme.AgentName.Render(d.Name)
	meta := theme.MutedText.Render(fmt.Sprintf("step %d | %dms", d.Step, d.LatencyMs))
	header := fmt.Sprintf("%s %s  %s", dot, name, meta)

	// Body: truncated token text with optional cursor
	bodyHeight := height - 4 // borders + header + separator
	if bodyHeight < 1 {
		bodyHeight = 1
	}
	bodyWidth := width - 6 // borders + padding
	if bodyWidth < 1 {
		bodyWidth = 1
	}

	body := truncateLines(d.Tokens, bodyWidth, bodyHeight)

	// Add blinking cursor for active agents
	if d.Active {
		body += theme.Cursor.Render(" ")
	}

	content := header + "\n" + theme.MutedText.Render(strings.Repeat("─", bodyWidth)) + "\n" + theme.TokenText.Render(body)

	return panelStyle.Render(content)
}

// truncateLines wraps and truncates text to fit within the given dimensions.
func truncateLines(text string, width, maxLines int) string {
	if width <= 0 || maxLines <= 0 {
		return ""
	}

	var lines []string
	for _, line := range strings.Split(text, "\n") {
		// Wrap long lines
		for len(line) > width {
			lines = append(lines, line[:width])
			line = line[width:]
		}
		lines = append(lines, line)
	}

	// Take only the last maxLines lines (tail)
	if len(lines) > maxLines {
		lines = lines[len(lines)-maxLines:]
	}

	return strings.Join(lines, "\n")
}
