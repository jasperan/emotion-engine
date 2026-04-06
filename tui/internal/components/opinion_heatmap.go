package components

import (
	"fmt"
	"sort"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// OpinionStance tracks one agent's stance on one topic.
type OpinionStance struct {
	AgentName string
	Topic     string
	Value     float64 // -1.0 to 1.0
}

// TippingPointInfo marks a convergence or divergence event.
type TippingPointInfo struct {
	Step       int
	Topic      string
	Type       string  // "convergence" or "divergence"
	MeanBefore float64
	MeanAfter  float64
}

// InfluenceProfile summarizes an agent's influence footprint.
type InfluenceProfile struct {
	AgentName      string
	Exerted        float64
	Received       float64
	IsSuperSpreader bool
	IsAnchor       bool
}

// OpinionHeatmapData holds everything for the social dynamics panel.
type OpinionHeatmapData struct {
	Stances         []OpinionStance
	TippingPoints   []TippingPointInfo
	Profiles        []InfluenceProfile
	ConvergenceByTopic map[string]float64 // topic -> 0.0-1.0
	Width           int
	Height          int
}

// stanceColor returns a color interpolated from red (-1) through yellow (0) to green (+1).
func stanceColor(v float64) lipgloss.Color {
	if v < -0.6 {
		return lipgloss.Color("#FF453A") // strong negative
	} else if v < -0.2 {
		return lipgloss.Color("#FF8C3A") // moderate negative
	} else if v < 0.2 {
		return lipgloss.Color("#FFD60A") // neutral
	} else if v < 0.6 {
		return lipgloss.Color("#7CD15E") // moderate positive
	}
	return lipgloss.Color("#30D158") // strong positive
}

// stanceBlock renders a colored block for a stance value.
func stanceBlock(v float64) string {
	bg := stanceColor(v)
	// Use block chars with intensity based on absolute value
	abs := v
	if abs < 0 {
		abs = -abs
	}
	var ch string
	switch {
	case abs >= 0.8:
		ch = "\u2588" // █ full
	case abs >= 0.5:
		ch = "\u2593" // ▓ dark
	case abs >= 0.2:
		ch = "\u2592" // ▒ medium
	default:
		ch = "\u2591" // ░ light
	}
	return lipgloss.NewStyle().Foreground(bg).Render(ch + ch)
}

// convergenceSparkline renders a tiny sparkline for convergence score.
func convergenceSparkline(score float64) string {
	blocks := []string{"▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"}
	idx := int(score * 7)
	if idx > 7 {
		idx = 7
	}
	if idx < 0 {
		idx = 0
	}
	color := theme.Accent
	if score < 0.3 {
		color = theme.Danger
	} else if score < 0.6 {
		color = theme.Warning
	}
	return lipgloss.NewStyle().Foreground(color).Render(blocks[idx])
}

// RenderOpinionHeatmap renders the social dynamics panel with opinion heatmap.
func RenderOpinionHeatmap(d OpinionHeatmapData) string {
	var lines []string
	lines = append(lines, theme.Subtitle.Render("SOCIAL DYNAMICS"))
	lines = append(lines, "")

	// Collect unique agents and topics
	agentSet := make(map[string]bool)
	topicSet := make(map[string]bool)
	stanceMap := make(map[string]map[string]float64) // agent -> topic -> value

	for _, s := range d.Stances {
		agentSet[s.AgentName] = true
		topicSet[s.Topic] = true
		if stanceMap[s.AgentName] == nil {
			stanceMap[s.AgentName] = make(map[string]float64)
		}
		stanceMap[s.AgentName][s.Topic] = s.Value
	}

	if len(agentSet) == 0 || len(topicSet) == 0 {
		lines = append(lines, theme.MutedText.Render("No opinion data yet..."))
		lines = append(lines, "")
		lines = append(lines, theme.MutedText.Render("Agents need conversations for"))
		lines = append(lines, theme.MutedText.Render("opinion dynamics to emerge."))
		return strings.Join(lines, "\n")
	}

	var agents []string
	for a := range agentSet {
		agents = append(agents, a)
	}
	sort.Strings(agents)

	var topics []string
	for t := range topicSet {
		topics = append(topics, t)
	}
	sort.Strings(topics)

	// Build profile lookup
	profileMap := make(map[string]*InfluenceProfile)
	for i := range d.Profiles {
		profileMap[d.Profiles[i].AgentName] = &d.Profiles[i]
	}

	// Header row: topic names (truncated)
	maxNameLen := 12
	nameColWidth := maxNameLen + 2
	topicWidth := 8 // topic label + block chars + spacing

	header := strings.Repeat(" ", nameColWidth)
	for _, t := range topics {
		label := t
		if len(label) > topicWidth-1 {
			label = label[:topicWidth-1]
		}
		header += lipgloss.NewStyle().Foreground(theme.Primary).Bold(true).
			Width(topicWidth).Render(label)
	}

	// Convergence row
	convRow := lipgloss.NewStyle().Width(nameColWidth).Foreground(theme.Muted).Render("  convg:")
	for _, t := range topics {
		score := 0.0
		if d.ConvergenceByTopic != nil {
			if s, ok := d.ConvergenceByTopic[t]; ok {
				score = s
			}
		}
		convRow += lipgloss.NewStyle().Width(topicWidth).Render(" " + convergenceSparkline(score))
	}

	lines = append(lines, header)
	lines = append(lines, convRow)
	lines = append(lines, "")

	// Data rows: one per agent
	for _, agent := range agents {
		name := agent
		if len(name) > maxNameLen {
			name = name[:maxNameLen]
		}

		// Badge for influence profile
		badge := ""
		if p, ok := profileMap[agent]; ok {
			if p.IsSuperSpreader {
				badge = lipgloss.NewStyle().Foreground(theme.Warning).Bold(true).Render("\u26a1") // ⚡
			} else if p.IsAnchor {
				badge = lipgloss.NewStyle().Foreground(theme.Primary).Bold(true).Render("\u2693") // ⚓
			}
		}

		row := lipgloss.NewStyle().Width(nameColWidth).Foreground(theme.Text).
			Render(name + badge)

		for _, topic := range topics {
			if val, ok := stanceMap[agent][topic]; ok {
				row += lipgloss.NewStyle().Width(topicWidth).Render(stanceBlock(val))
			} else {
				row += lipgloss.NewStyle().Width(topicWidth).Foreground(theme.Dim).Render(" \u00b7") // ·
			}
		}
		lines = append(lines, row)
	}

	// Tipping points
	if len(d.TippingPoints) > 0 {
		lines = append(lines, "")
		lines = append(lines, theme.Subtitle.Render("TIPPING POINTS"))
		// Show last 3
		start := 0
		if len(d.TippingPoints) > 3 {
			start = len(d.TippingPoints) - 3
		}
		for _, tp := range d.TippingPoints[start:] {
			icon := lipgloss.NewStyle().Foreground(theme.Accent).Render("\u25b2") // ▲ convergence
			if tp.Type == "divergence" {
				icon = lipgloss.NewStyle().Foreground(theme.Danger).Render("\u25bc") // ▼
			}
			line := fmt.Sprintf("  %s step %d: %s %.2f\u2192%.2f",
				icon, tp.Step,
				lipgloss.NewStyle().Foreground(theme.Primary).Render(tp.Topic),
				tp.MeanBefore, tp.MeanAfter)
			lines = append(lines, line)
		}
	}

	// Legend
	lines = append(lines, "")
	lines = append(lines, theme.MutedText.Render("  ")+
		lipgloss.NewStyle().Foreground(lipgloss.Color("#FF453A")).Render("\u2588\u2588")+
		theme.MutedText.Render(" oppose  ")+
		lipgloss.NewStyle().Foreground(lipgloss.Color("#FFD60A")).Render("\u2592\u2592")+
		theme.MutedText.Render(" neutral  ")+
		lipgloss.NewStyle().Foreground(lipgloss.Color("#30D158")).Render("\u2588\u2588")+
		theme.MutedText.Render(" support"))
	lines = append(lines, theme.MutedText.Render("  ")+
		lipgloss.NewStyle().Foreground(theme.Warning).Bold(true).Render("\u26a1")+
		theme.MutedText.Render(" spreader  ")+
		lipgloss.NewStyle().Foreground(theme.Primary).Bold(true).Render("\u2693")+
		theme.MutedText.Render(" anchor"))

	return strings.Join(lines, "\n")
}
