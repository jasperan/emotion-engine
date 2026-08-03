package components

import (
	"fmt"
	"sort"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// NetworkMode selects which network to visualize.
type NetworkMode int

const (
	NetworkTrust     NetworkMode = iota // trust/conflict/alliance edges
	NetworkInfluence                    // influence flow edges
)

var networkModeNames = [...]string{"Trust", "Influence"}

func (n NetworkMode) String() string { return networkModeNames[n] }

// CoalitionInfo describes an emergent group.
type CoalitionInfo struct {
	Name     string
	Members  []string
	Strength float64
	Leader   string
}

// InfluenceEdgeInfo tracks directed influence between agents.
type InfluenceEdgeInfo struct {
	Source          string
	Target          string
	Topic           string
	TotalDelta      float64
	InteractionCount int
}

// NetworkMatrixData holds everything for the network matrix panel.
type NetworkMatrixData struct {
	Agents     []RelAgent
	Edges      []RelEdge
	Coalitions []CoalitionInfo
	Influence  []InfluenceEdgeInfo
	Mode       NetworkMode
	Width      int
	Height     int
}

// cellColor returns a colored block based on relationship type and strength.
func cellColor(edgeType RelEdgeType, strength float64) string {
	var fg lipgloss.Color
	switch edgeType {
	case RelTrust:
		fg = theme.Accent
	case RelConflict:
		fg = theme.Danger
	case RelAlliance:
		fg = theme.Secondary // mauve for double/alliance
	default:
		fg = theme.Warning
	}

	var ch string
	switch {
	case strength >= 0.8:
		ch = "\u2588" // █
	case strength >= 0.5:
		ch = "\u2593" // ▓
	case strength >= 0.2:
		ch = "\u2592" // ▒
	default:
		ch = "\u2591" // ░
	}
	return lipgloss.NewStyle().Foreground(fg).Render(ch)
}

// influenceCellColor returns a colored block for influence magnitude.
func influenceCellColor(delta float64) string {
	abs := delta
	if abs < 0 {
		abs = -abs
	}

	var fg lipgloss.Color
	if delta > 0 {
		fg = theme.Accent // positive influence
	} else if delta < 0 {
		fg = theme.Danger // negative influence
	} else {
		return theme.MutedText.Render("\u00b7") // · no interaction
	}

	var ch string
	switch {
	case abs >= 0.5:
		ch = "\u2588"
	case abs >= 0.2:
		ch = "\u2593"
	case abs >= 0.05:
		ch = "\u2592"
	default:
		ch = "\u2591"
	}
	return lipgloss.NewStyle().Foreground(fg).Render(ch)
}

// RenderNetworkMatrix renders an adjacency matrix of agent relationships.
func RenderNetworkMatrix(d NetworkMatrixData) string {
	var lines []string

	modeLabel := d.Mode.String()
	lines = append(lines, theme.Subtitle.Render("NETWORK: "+modeLabel))
	lines = append(lines, "")

	if len(d.Agents) == 0 {
		lines = append(lines, theme.MutedText.Render("No agents yet..."))
		return strings.Join(lines, "\n")
	}

	// Sort agents for consistent ordering
	agents := make([]RelAgent, len(d.Agents))
	copy(agents, d.Agents)
	sort.Slice(agents, func(i, j int) bool { return agents[i].Name < agents[j].Name })

	// Determine coalition membership for grouping
	coalitionOf := make(map[string]int) // agent name -> coalition index
	for i, c := range d.Coalitions {
		for _, m := range c.Members {
			coalitionOf[m] = i + 1
		}
	}

	// Build edge lookup
	edgeLookup := make(map[string]RelEdge) // "a|b" -> edge
	for _, e := range d.Edges {
		edgeLookup[e.AgentA+"|"+e.AgentB] = e
		edgeLookup[e.AgentB+"|"+e.AgentA] = e
	}

	// Build influence lookup
	influenceLookup := make(map[string]float64) // "source|target" -> delta
	for _, e := range d.Influence {
		influenceLookup[e.Source+"|"+e.Target] = e.TotalDelta
	}

	// Truncated name width
	nameW := 8
	cellW := 2

	// Header row with column labels (first char of each name)
	header := strings.Repeat(" ", nameW+1)
	for _, a := range agents {
		label := a.Name
		if len(label) > cellW {
			label = label[:cellW]
		}
		header += lipgloss.NewStyle().Foreground(theme.Primary).Width(cellW).Render(label)
	}
	lines = append(lines, header)

	// Matrix rows
	for _, rowAgent := range agents {
		name := rowAgent.Name
		if len(name) > nameW {
			name = name[:nameW]
		}

		// Coalition marker
		marker := " "
		if ci, ok := coalitionOf[rowAgent.Name]; ok {
			colors := []lipgloss.Color{theme.Primary, theme.Accent, theme.Warning, theme.Danger}
			c := colors[ci%len(colors)]
			marker = lipgloss.NewStyle().Foreground(c).Render("\u2502") // │
		}

		row := lipgloss.NewStyle().Width(nameW).Foreground(theme.Text).Render(name) + marker

		for _, colAgent := range agents {
			if rowAgent.Name == colAgent.Name {
				// Diagonal: show stress-colored dot
				row += lipgloss.NewStyle().Foreground(theme.Dim).Render("\u25c7 ") // ◇
				continue
			}

			if d.Mode == NetworkTrust {
				key := rowAgent.Name + "|" + colAgent.Name
				if e, ok := edgeLookup[key]; ok {
					row += cellColor(e.Type, e.Strength) + " "
				} else {
					row += theme.MutedText.Render("\u00b7 ") // ·
				}
			} else {
				key := rowAgent.Name + "|" + colAgent.Name
				if delta, ok := influenceLookup[key]; ok {
					row += influenceCellColor(delta) + " "
				} else {
					row += theme.MutedText.Render("\u00b7 ") // ·
				}
			}
		}
		lines = append(lines, row)
	}

	// Coalitions section
	if len(d.Coalitions) > 0 {
		lines = append(lines, "")
		lines = append(lines, theme.Subtitle.Render("COALITIONS"))
		for _, c := range d.Coalitions {
			leader := ""
			if c.Leader != "" {
				leader = fmt.Sprintf(" [%s]", c.Leader)
			}
			members := strings.Join(c.Members, ", ")
			if len(members) > d.Width-20 {
				members = members[:d.Width-20] + "..."
			}
			strength := fmt.Sprintf("%.0f%%", c.Strength*100)
			line := fmt.Sprintf("  %s %s%s %s",
				lipgloss.NewStyle().Foreground(theme.Accent).Render(strength),
				theme.MutedText.Render(members),
				lipgloss.NewStyle().Foreground(theme.Primary).Render(leader),
				"")
			lines = append(lines, line)
		}
	}

	// Legend
	lines = append(lines, "")
	if d.Mode == NetworkTrust {
		lines = append(lines, theme.MutedText.Render("  ")+
			lipgloss.NewStyle().Foreground(theme.Accent).Render("\u2588")+
			theme.MutedText.Render(" trust  ")+
			lipgloss.NewStyle().Foreground(theme.Danger).Render("\u2588")+
			theme.MutedText.Render(" conflict  ")+
			lipgloss.NewStyle().Foreground(theme.Secondary).Render("\u2588")+
			theme.MutedText.Render(" alliance  ")+
			theme.MutedText.Render("\u00b7")+
			theme.MutedText.Render(" none"))
	} else {
		lines = append(lines, theme.MutedText.Render("  ")+
			lipgloss.NewStyle().Foreground(theme.Accent).Render("\u2588")+
			theme.MutedText.Render(" positive  ")+
			lipgloss.NewStyle().Foreground(theme.Danger).Render("\u2588")+
			theme.MutedText.Render(" negative  ")+
			theme.MutedText.Render("intensity = block density"))
	}

	return strings.Join(lines, "\n")
}
