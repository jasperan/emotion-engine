package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// WorldStateData holds data for rendering the world state panel.
type WorldStateData struct {
	HazardLevel float64
	Locations   []LocationInfo
	Width       int
}

// LocationInfo describes a location and the agents present.
type LocationInfo struct {
	Name       string
	AgentNames []string
}

// RenderWorldState renders the hazard gauge and location list.
func RenderWorldState(d WorldStateData) string {
	var sections []string

	// Hazard gauge
	sections = append(sections, renderHazardGauge(d.HazardLevel, d.Width-4))

	// Location list
	sections = append(sections, "")
	sections = append(sections, theme.Subtitle.Render("Locations"))

	for _, loc := range d.Locations {
		agentCount := len(loc.AgentNames)
		header := fmt.Sprintf("  %s (%d)",
			theme.Title.Render(loc.Name),
			agentCount,
		)
		sections = append(sections, header)

		if agentCount > 0 {
			names := theme.MutedText.Render("    " + strings.Join(loc.AgentNames, ", "))
			sections = append(sections, names)
		}
	}

	return strings.Join(sections, "\n")
}

// renderHazardGauge renders a horizontal bar gauge for hazard level.
func renderHazardGauge(level float64, width int) string {
	if width < 10 {
		width = 10
	}

	// Backend sends hazard_level on 0-10 scale; normalize to 0.0-1.0
	normalized := level / 10.0
	if normalized > 1.0 {
		normalized = 1.0
	}
	if normalized < 0 {
		normalized = 0
	}

	label := fmt.Sprintf("Hazard %.0f%%", normalized*100)
	barWidth := width - len(label) - 3 // space + brackets
	if barWidth < 5 {
		barWidth = 5
	}

	filled := int(normalized * float64(barWidth))
	if filled > barWidth {
		filled = barWidth
	}
	empty := barWidth - filled

	color := theme.HazardColor(normalized)
	gaugeStyle := lipgloss.NewStyle().Foreground(color)

	bar := gaugeStyle.Render(strings.Repeat("\u2588", filled)) +
		theme.MutedText.Render(strings.Repeat("\u2591", empty))

	return fmt.Sprintf("%s [%s]", theme.Title.Render(label), bar)
}
