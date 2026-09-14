package components

import (
	"fmt"
	"strings"

	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// BarChartEntry is a single row in the bar chart.
type BarChartEntry struct {
	Label string
	Value float64
	Max   float64
}

// RenderBarChart renders a horizontal bar chart for the given entries.
// Each row: "  Label_padded  ████████░░░░  N%"
func RenderBarChart(entries []BarChartEntry, width int) string {
	if len(entries) == 0 {
		return theme.MutedText.Render("No data")
	}

	// Compute label column width (longest label, capped at 20).
	maxLabel := 0
	for _, e := range entries {
		if len(e.Label) > maxLabel {
			maxLabel = len(e.Label)
		}
	}
	if maxLabel > 20 {
		maxLabel = 20
	}

	// Layout: 2 indent + maxLabel + 2 gap + barWidth + 2 gap + 5 pct
	const indent = 2
	const gap = 2
	const pctWidth = 5 // " 100%"
	barWidth := width - indent - maxLabel - gap - gap - pctWidth
	if barWidth < 4 {
		barWidth = 4
	}

	pctStyle := theme.MutedText

	var sb strings.Builder
	for i, e := range entries {
		label := e.Label
		if len(label) > 20 {
			label = label[:20]
		}
		// Pad label.
		label = label + strings.Repeat(" ", maxLabel-len(label))

		// Compute fill ratio.
		ratio := 0.0
		if e.Max > 0 {
			ratio = e.Value / e.Max
			if ratio > 1 {
				ratio = 1
			}
			if ratio < 0 {
				ratio = 0
			}
		}
		bar := NewProgressBar(barWidth, theme.Accent, theme.Muted).ViewAs(ratio)

		pct := fmt.Sprintf("%3.0f%%", ratio*100)

		row := strings.Repeat(" ", indent) + label +
			strings.Repeat(" ", gap) + bar +
			strings.Repeat(" ", gap) + pctStyle.Render(pct)

		sb.WriteString(row)
		if i < len(entries)-1 {
			sb.WriteByte('\n')
		}
	}
	return sb.String()
}
