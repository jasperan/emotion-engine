package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// RelEdgeType categorizes the relationship between two agents.
type RelEdgeType int

const (
	RelTrust    RelEdgeType = iota // green solid
	RelConflict                    // red wavy
	RelAlliance                    // green double
	RelPending                     // yellow dotted
)

// RelAgent is a node in the relationship graph.
type RelAgent struct {
	ID   string
	Name string
}

// RelEdge is a directed (but rendered bidirectional) relationship between two agents.
type RelEdge struct {
	AgentA   string // name
	AgentB   string // name
	Type     RelEdgeType
	Strength float64 // 0.0 - 1.0
	Label    string
}

// RelationshipWebData holds everything needed to render the relationship web panel.
type RelationshipWebData struct {
	Agents []RelAgent
	Edges  []RelEdge
	Width  int
	Height int
}

// edgesFor returns all edges where agent (by name) appears as either AgentA or AgentB,
// deduped so each pair appears only once.
func edgesFor(edges []RelEdge, agent string) []RelEdge {
	var result []RelEdge
	for _, e := range edges {
		if e.AgentA == agent || e.AgentB == agent {
			result = append(result, e)
		}
	}
	return result
}

// edgeChars returns the connector string and lipgloss style for a given edge type.
func edgeChars(t RelEdgeType) (string, lipgloss.Style) {
	switch t {
	case RelTrust:
		return "\u2500\u2500", lipgloss.NewStyle().Foreground(theme.Accent)
	case RelConflict:
		return "~~", lipgloss.NewStyle().Foreground(theme.Danger)
	case RelAlliance:
		return "\u2550\u2550", lipgloss.NewStyle().Foreground(theme.Accent)
	default: // RelPending
		return "..", lipgloss.NewStyle().Foreground(theme.Warning)
	}
}

// strengthBar renders a 5-char progress bar using block chars.
func strengthBar(strength float64) string {
	const width = 5
	filled := int(strength * float64(width))
	if filled > width {
		filled = width
	}
	empty := width - filled
	return lipgloss.NewStyle().Foreground(theme.Primary).Render(strings.Repeat("\u2588", filled)) +
		theme.MutedText.Render(strings.Repeat("\u2591", empty))
}

// RenderRelationshipWeb renders the relationship web panel.
func RenderRelationshipWeb(d RelationshipWebData) string {
	var lines []string

	lines = append(lines, theme.Subtitle.Render("RELATIONSHIPS"))
	lines = append(lines, "")

	if len(d.Agents) == 0 {
		lines = append(lines, theme.MutedText.Render("No relationship data yet..."))
		return theme.Panel.Render(strings.Join(lines, "\n"))
	}

	for _, agent := range d.Agents {
		lines = append(lines, lipgloss.NewStyle().Foreground(theme.Accent).Bold(true).Render(agent.Name))

		agentEdges := edgesFor(d.Edges, agent.Name)
		if len(agentEdges) == 0 {
			lines = append(lines, theme.MutedText.Render("  (no connections)"))
		}

		for _, e := range agentEdges {
			// Determine the other agent
			other := e.AgentB
			if e.AgentA != agent.Name {
				other = e.AgentA
			}

			chars, style := edgeChars(e.Type)
			connector := style.Render(chars)
			bar := strengthBar(e.Strength)

			label := ""
			if e.Label != "" {
				label = " " + theme.MutedText.Render("["+e.Label+"]")
			}

			line := fmt.Sprintf("  %s %s %s%s",
				connector,
				lipgloss.NewStyle().Foreground(theme.Primary).Render(other),
				bar,
				label,
			)
			lines = append(lines, line)
		}
		lines = append(lines, "")
	}

	// Legend
	trustStyle := lipgloss.NewStyle().Foreground(theme.Accent)
	conflictStyle := lipgloss.NewStyle().Foreground(theme.Danger)
	pendingStyle := lipgloss.NewStyle().Foreground(theme.Warning)

	lines = append(lines, theme.MutedText.Render("  Legend: ")+
		trustStyle.Render("\u2500\u2500")+" trust  "+
		conflictStyle.Render("~~")+" conflict  "+
		trustStyle.Render("\u2550\u2550")+" alliance  "+
		pendingStyle.Render("..")+" pending")

	return theme.Panel.Render(strings.Join(lines, "\n"))
}
