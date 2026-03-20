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

	// Enrichment fields
	Occupation   string
	Age          int
	Health       int
	Stress       int
	Location     string
	PlanGoal     string
	PlanProgress string // e.g. "60%"
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

	// Header: status dot + name (occupation, age) + step/latency
	var dot string
	if d.Active {
		dot = theme.StatusActive.Render(theme.StatusDot)
	} else {
		dot = theme.StatusIdle.Render(theme.StatusDot)
	}

	// Build name suffix with occupation and age if available
	nameSuffix := ""
	if d.Occupation != "" && d.Age > 0 {
		nameSuffix = fmt.Sprintf(" (%s, %d)", d.Occupation, d.Age)
	} else if d.Occupation != "" {
		nameSuffix = fmt.Sprintf(" (%s)", d.Occupation)
	} else if d.Age > 0 {
		nameSuffix = fmt.Sprintf(" (%d)", d.Age)
	}

	name := theme.AgentName.Render(d.Name + nameSuffix)
	meta := theme.MutedText.Render(fmt.Sprintf("step %d | %dms", d.Step, d.LatencyMs))
	header := fmt.Sprintf("%s %s  %s", dot, name, meta)

	// Build enrichment lines
	var extraLines []string

	// Line 2: HP / Stress / Location
	hasStats := d.Health > 0 || d.Stress > 0 || d.Location != ""
	if hasStats {
		var statParts []string
		if d.Health > 0 {
			var hpColor lipgloss.Color
			switch {
			case d.Health >= 50:
				hpColor = theme.Accent
			case d.Health >= 25:
				hpColor = theme.Warning
			default:
				hpColor = theme.Danger
			}
			statParts = append(statParts, lipgloss.NewStyle().Foreground(hpColor).Render(fmt.Sprintf("HP:%d", d.Health)))
		}
		if d.Stress > 0 {
			var stColor lipgloss.Color
			switch {
			case d.Stress <= 60:
				stColor = theme.Accent
			case d.Stress <= 80:
				stColor = theme.Warning
			default:
				stColor = theme.Danger
			}
			statParts = append(statParts, lipgloss.NewStyle().Foreground(stColor).Render(fmt.Sprintf("ST:%d", d.Stress)))
		}
		if d.Location != "" {
			statParts = append(statParts, theme.MutedText.Render("@"+d.Location))
		}
		extraLines = append(extraLines, strings.Join(statParts, "  "))
	}

	// Line 3: Plan goal
	if d.PlanGoal != "" {
		goal := d.PlanGoal
		maxGoalLen := width - 20
		if maxGoalLen < 10 {
			maxGoalLen = 10
		}
		if len(goal) > maxGoalLen {
			goal = goal[:maxGoalLen-1] + "…"
		}
		planLine := theme.MutedText.Render("Goal: ") + theme.TokenText.Render(fmt.Sprintf("%q", goal))
		if d.PlanProgress != "" {
			planLine += " " + theme.MutedText.Render(d.PlanProgress)
		}
		extraLines = append(extraLines, planLine)
	}

	// Body: truncated token text with optional cursor
	extraLineCount := len(extraLines)
	bodyHeight := height - 4 - extraLineCount // borders + header + separator + extra lines
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

	// Assemble content
	content := header
	for _, line := range extraLines {
		content += "\n" + line
	}
	content += "\n" + theme.MutedText.Render(strings.Repeat("─", bodyWidth)) + "\n" + theme.TokenText.Render(body)

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
