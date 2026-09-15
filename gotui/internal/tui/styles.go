package tui

import "charm.land/lipgloss/v2"

// The approved design tokens (docs/tui-design-tokens.md). Only these 14 values
// appear anywhere in this module, so check_palette.py stays green. The form
// itself is styled by huhstyle; these cover the surrounding furniture.
var (
	colBG      = lipgloss.Color("#1e1e2e") // bg
	colSurface = lipgloss.Color("#181825") // surface
	colHighest = lipgloss.Color("#45475a") // highest
	colText    = lipgloss.Color("#cdd6f4") // text
	colSubtext = lipgloss.Color("#a6adc8") // subtext
	colMuted   = lipgloss.Color("#6c7086") // muted
	colDim     = lipgloss.Color("#585b70") // dim
	colPrimary = lipgloss.Color("#89b4fa") // primary
	colError   = lipgloss.Color("#f38ba8") // error
)

var (
	titleStyle = lipgloss.NewStyle().Bold(true).Foreground(colPrimary)
	bodyStyle  = lipgloss.NewStyle().Foreground(colText)
	metaStyle  = lipgloss.NewStyle().Foreground(colSubtext)
	mutedStyle = lipgloss.NewStyle().Foreground(colMuted)
	errStyle   = lipgloss.NewStyle().Foreground(colError)
	paneStyle  = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colHighest).
			Padding(0, 1)
	barStyle = lipgloss.NewStyle().
			Background(colSurface).
			Foreground(colSubtext).
			Padding(0, 1)
)
