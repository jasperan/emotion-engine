package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// StatusBarData holds all data needed to render the status bar.
type StatusBarData struct {
	Connected bool
	RunStatus string
	Step      int
	MaxSteps  int
	TokPerSec float64
	Hints     []KeyHint
}

// KeyHint represents a keyboard shortcut hint.
type KeyHint struct {
	Key  string
	Desc string
}

// RenderStatusBar renders a full-width status bar with left, center, and right sections.
func RenderStatusBar(d StatusBarData, width int) string {
	// Left: connection dot + status
	var connDot string
	if d.Connected {
		connDot = theme.StatusActive.Render(theme.StatusDot)
	} else {
		connDot = theme.StatusError.Render(theme.StatusDot)
	}

	statusStyle := lipgloss.NewStyle().Foreground(theme.StatusColor(d.RunStatus))
	left := fmt.Sprintf(" %s %s", connDot, statusStyle.Render(d.RunStatus))

	// Center: step counter
	center := fmt.Sprintf("Step %d/%d", d.Step, d.MaxSteps)

	// Right: tok/s + key hints
	tokStr := theme.Throughput.Render(fmt.Sprintf("%.1f tok/s", d.TokPerSec))
	var hints []string
	for _, h := range d.Hints {
		hints = append(hints, fmt.Sprintf("%s %s",
			theme.KeyName.Render(h.Key),
			theme.KeyHint.Render(h.Desc),
		))
	}
	right := tokStr
	if len(hints) > 0 {
		right += "  " + strings.Join(hints, "  ")
	}
	right += " "

	// Calculate padding
	leftW := lipgloss.Width(left)
	centerW := lipgloss.Width(center)
	rightW := lipgloss.Width(right)

	// Pad between sections
	gap1 := width/2 - leftW - centerW/2
	if gap1 < 1 {
		gap1 = 1
	}
	gap2 := width - leftW - gap1 - centerW - rightW
	if gap2 < 1 {
		gap2 = 1
	}

	bar := left + strings.Repeat(" ", gap1) + center + strings.Repeat(" ", gap2) + right

	return theme.StatusBar.Width(width).Render(bar)
}
