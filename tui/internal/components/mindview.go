package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// MindViewData holds all data for the full-screen agent mind view.
type MindViewData struct {
	Name          string
	Occupation    string
	Location      string
	PlanGoal      string
	PlanStep      string
	PlanProgress  string
	LastReasoning string
	Emotion       string

	Age          int
	Health       int
	Stress       int
	PlanDeadline int

	Width  int
	Height int

	// Big Five + extra traits (1-10 scale)
	Openness          int
	Conscientiousness int
	Extraversion      int
	Agreeableness     int
	Neuroticism       int
	RiskTolerance     int
	Empathy           int
	Leadership        int

	Inventory     []string
	Relationships []MindRelationship
	RecentActions []MindAction
}

// MindRelationship describes one agent's relationship to another.
type MindRelationship struct {
	AgentName   string
	Trust       float64
	Label       string
	Description string
}

// MindAction records a single recent action by an agent.
type MindAction struct {
	Step    int
	Action  string
	Target  string
	Emotion string
}

// coloredStat returns a styled "Label: N" string with HP/Stress color coding.
func coloredStat(label string, value int, isStress bool) string {
	var color lipgloss.Color
	if isStress {
		switch {
		case value > 80:
			color = theme.Danger
		case value > 60:
			color = theme.Warning
		default:
			color = theme.Accent
		}
	} else {
		// HP
		switch {
		case value >= 50:
			color = theme.Accent
		case value >= 25:
			color = theme.Warning
		default:
			color = theme.Danger
		}
	}
	styled := lipgloss.NewStyle().Foreground(color).Render(fmt.Sprintf("%d", value))
	return fmt.Sprintf("%s: %s", label, styled)
}

// traitBar renders a named trait bar: "Name: ████░░░░░░ N"
func traitBar(name string, value int, barWidth int) string {
	if value < 0 {
		value = 0
	}
	if value > 10 {
		value = 10
	}
	filled := value * barWidth / 10
	empty := barWidth - filled
	bar := lipgloss.NewStyle().Foreground(theme.Accent).Render(strings.Repeat("█", filled)) +
		theme.MutedText.Render(strings.Repeat("░", empty))
	label := fmt.Sprintf("%-18s", name)
	return fmt.Sprintf("%s %s %2d", label, bar, value)
}

// trustBar renders a 5-char trust bar for relationships.
func trustBar(trust float64) string {
	if trust < 0 {
		trust = 0
	}
	if trust > 1 {
		trust = 1
	}
	filled := int(trust * 5)
	empty := 5 - filled
	return lipgloss.NewStyle().Foreground(theme.Accent).Render(strings.Repeat("█", filled)) +
		theme.MutedText.Render(strings.Repeat("░", empty))
}

// wrapText wraps text to the given width, returning joined lines.
func wrapText(text string, width int) string {
	if width <= 0 || text == "" {
		return text
	}
	words := strings.Fields(text)
	if len(words) == 0 {
		return ""
	}
	var lines []string
	current := ""
	for _, w := range words {
		if current == "" {
			current = w
		} else if len(current)+1+len(w) <= width {
			current += " " + w
		} else {
			lines = append(lines, current)
			current = w
		}
	}
	if current != "" {
		lines = append(lines, current)
	}
	return strings.Join(lines, "\n")
}

// truncate cuts s to maxLen, appending "…" if needed.
func truncateMind(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	if maxLen <= 1 {
		return "…"
	}
	return s[:maxLen-1] + "…"
}

// RenderMindView renders a full-screen agent mind view panel.
func RenderMindView(d MindViewData) string {
	innerWidth := d.Width - 6 // panel border (2) + padding (2*2)
	if innerWidth < 20 {
		innerWidth = 20
	}

	sep := theme.MutedText.Render(strings.Repeat("─", innerWidth))

	var lines []string

	// --- Header ---
	nameStr := lipgloss.NewStyle().Bold(true).Foreground(theme.Text).
		Render(strings.ToUpper(d.Name))
	meta := ""
	if d.Occupation != "" && d.Age > 0 {
		meta = fmt.Sprintf("%s, age %d", d.Occupation, d.Age)
	} else if d.Occupation != "" {
		meta = d.Occupation
	} else if d.Age > 0 {
		meta = fmt.Sprintf("age %d", d.Age)
	}

	lines = append(lines, nameStr)
	if meta != "" {
		lines = append(lines, theme.MutedText.Render(meta))
	}

	locStr := ""
	if d.Location != "" {
		locStr = fmt.Sprintf("  @ %s", d.Location)
	}
	emotStr := ""
	if d.Emotion != "" {
		emotStr = fmt.Sprintf("  ◆ %s", d.Emotion)
	}

	statLine := coloredStat("HP", d.Health, false) + "  " +
		coloredStat("Stress", d.Stress, true) +
		locStr + emotStr
	lines = append(lines, statLine)
	lines = append(lines, sep)

	// --- Two-column: Personality | Plan + Inventory ---
	colWidth := innerWidth / 2
	barWidth := 10

	// Build personality lines
	traits := []struct {
		name  string
		value int
	}{
		{"Openness", d.Openness},
		{"Conscientiousness", d.Conscientiousness},
		{"Extraversion", d.Extraversion},
		{"Agreeableness", d.Agreeableness},
		{"Neuroticism", d.Neuroticism},
		{"Risk Tolerance", d.RiskTolerance},
		{"Empathy", d.Empathy},
		{"Leadership", d.Leadership},
	}

	leftLines := []string{theme.Subtitle.Render("PERSONALITY")}
	for _, t := range traits {
		leftLines = append(leftLines, traitBar(t.name, t.value, barWidth))
	}

	// Build plan + inventory lines
	rightLines := []string{theme.Subtitle.Render("PLAN")}
	if d.PlanGoal != "" {
		rightLines = append(rightLines, theme.MutedText.Render("Goal:"))
		rightLines = append(rightLines, "  "+truncateMind(d.PlanGoal, colWidth-2))
	}
	if d.PlanStep != "" {
		rightLines = append(rightLines, theme.MutedText.Render("Step:"))
		rightLines = append(rightLines, "  "+truncateMind(d.PlanStep, colWidth-2))
	}
	if d.PlanProgress != "" {
		rightLines = append(rightLines, theme.MutedText.Render("Progress: ")+d.PlanProgress)
	}
	if d.PlanDeadline > 0 {
		rightLines = append(rightLines, theme.MutedText.Render(fmt.Sprintf("Deadline: step %d", d.PlanDeadline)))
	}
	rightLines = append(rightLines, "")
	rightLines = append(rightLines, theme.Subtitle.Render("INVENTORY"))
	if len(d.Inventory) == 0 {
		rightLines = append(rightLines, theme.MutedText.Render("  (empty)"))
	} else {
		for _, item := range d.Inventory {
			rightLines = append(rightLines, "  • "+truncateMind(item, colWidth-4))
		}
	}

	// Merge columns side by side
	maxRows := len(leftLines)
	if len(rightLines) > maxRows {
		maxRows = len(rightLines)
	}
	leftStyle := lipgloss.NewStyle().Width(colWidth)
	rightStyle := lipgloss.NewStyle().Width(innerWidth - colWidth)
	for i := 0; i < maxRows; i++ {
		l := ""
		r := ""
		if i < len(leftLines) {
			l = leftLines[i]
		}
		if i < len(rightLines) {
			r = rightLines[i]
		}
		lines = append(lines, leftStyle.Render(l)+rightStyle.Render(r))
	}
	lines = append(lines, sep)

	// --- Relationships ---
	lines = append(lines, theme.Subtitle.Render("RELATIONSHIPS"))
	if len(d.Relationships) == 0 {
		lines = append(lines, theme.MutedText.Render("  No relationships recorded"))
	} else {
		for _, rel := range d.Relationships {
			bar := trustBar(rel.Trust)
			label := ""
			if rel.Label != "" {
				label = " [" + rel.Label + "]"
			}
			desc := ""
			if rel.Description != "" {
				maxDesc := innerWidth - len(rel.AgentName) - 10
				if maxDesc < 10 {
					maxDesc = 10
				}
				desc = "  \"" + truncateMind(rel.Description, maxDesc) + "\""
			}
			line := fmt.Sprintf("  %-16s %s%s%s",
				truncateMind(rel.AgentName, 16),
				bar,
				theme.MutedText.Render(label),
				theme.MutedText.Render(desc),
			)
			lines = append(lines, line)
		}
	}
	lines = append(lines, sep)

	// --- Last Reasoning ---
	lines = append(lines, theme.Subtitle.Render("LAST REASONING"))
	if d.LastReasoning == "" {
		lines = append(lines, theme.MutedText.Render("  (none)"))
	} else {
		wrapped := wrapText(d.LastReasoning, innerWidth-2)
		for _, wl := range strings.Split(wrapped, "\n") {
			lines = append(lines, "  "+theme.TokenText.Render(wl))
		}
	}
	lines = append(lines, sep)

	// --- Recent Actions ---
	lines = append(lines, theme.Subtitle.Render("RECENT ACTIONS"))
	if len(d.RecentActions) == 0 {
		lines = append(lines, theme.MutedText.Render("  (none)"))
	} else {
		for _, act := range d.RecentActions {
			target := ""
			if act.Target != "" {
				target = " -> " + act.Target
			}
			emotion := ""
			if act.Emotion != "" {
				emotion = "  " + theme.MutedText.Render(act.Emotion)
			}
			line := fmt.Sprintf("  Step %3d: %s%s%s",
				act.Step,
				act.Action,
				target,
				emotion,
			)
			lines = append(lines, line)
		}
	}

	content := strings.Join(lines, "\n")
	return theme.Panel.Width(d.Width - 2).Render(content)
}
