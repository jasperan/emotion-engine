package components

import (
	"fmt"
	"sort"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// MapLocation represents a location node on the spatial map.
type MapLocation struct {
	Name        string
	Agents      []string
	Hazard      bool
	ConnectedTo []string
}

// MapTravel represents an agent currently mid-travel between locations.
type MapTravel struct {
	AgentName string
	From      string
	To        string
	Progress  float64 // 0.0 - 1.0
}

// SpatialMapData holds all data needed to render the spatial map panel.
type SpatialMapData struct {
	Locations []MapLocation
	Travels   []MapTravel
	Width     int
	Height    int
}

// RenderSpatialMap renders the spatial map panel with locations, agents, and travel progress.
func RenderSpatialMap(d SpatialMapData) string {
	var lines []string

	lines = append(lines, theme.Subtitle.Render("SPATIAL MAP"))
	lines = append(lines, "")

	if len(d.Locations) == 0 {
		lines = append(lines, theme.MutedText.Render("No locations discovered yet..."))
		return theme.Panel.Render(strings.Join(lines, "\n"))
	}

	// Sort locations alphabetically for stable rendering
	sorted := make([]MapLocation, len(d.Locations))
	copy(sorted, d.Locations)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Name < sorted[j].Name
	})

	agentStyle := lipgloss.NewStyle().Foreground(theme.Accent)

	for _, loc := range sorted {
		// Location name: red if hazard, bold white otherwise
		var nameStr string
		if loc.Hazard {
			nameStr = theme.ErrorText.Render(loc.Name)
		} else {
			nameStr = theme.Title.Render(loc.Name)
		}

		agentCount := fmt.Sprintf("[%d]", len(loc.Agents))
		header := fmt.Sprintf("  %s %s", nameStr, theme.MutedText.Render(agentCount))
		lines = append(lines, header)

		// Agent names in green
		if len(loc.Agents) > 0 {
			agentList := agentStyle.Render("    " + strings.Join(loc.Agents, ", "))
			lines = append(lines, agentList)
		}

		// Connected locations in muted text
		if len(loc.ConnectedTo) > 0 {
			connections := theme.MutedText.Render("    -> " + strings.Join(loc.ConnectedTo, ", "))
			lines = append(lines, connections)
		}
	}

	// IN TRANSIT section
	if len(d.Travels) > 0 {
		lines = append(lines, "")
		lines = append(lines, theme.Subtitle.Render("IN TRANSIT"))

		barWidth := 10
		for _, t := range d.Travels {
			filled := int(t.Progress * float64(barWidth))
			if filled > barWidth {
				filled = barWidth
			}
			empty := barWidth - filled

			bar := lipgloss.NewStyle().Foreground(theme.Primary).Render(strings.Repeat("\u2588", filled)) +
				theme.MutedText.Render(strings.Repeat("\u2591", empty))

			pct := int(t.Progress * 100)
			line := fmt.Sprintf("  %-16s %s -> %s [%s] %d%%",
				agentStyle.Render(t.AgentName),
				theme.MutedText.Render(t.From),
				theme.MutedText.Render(t.To),
				bar,
				pct,
			)
			lines = append(lines, line)
		}
	}

	// Legend
	lines = append(lines, "")
	lines = append(lines, theme.MutedText.Render("  "+agentStyle.Render("green")+" = agents  "+
		theme.ErrorText.Render("red name")+" = hazard  "+
		"[N] = agent count"))

	return theme.Panel.Render(strings.Join(lines, "\n"))
}
