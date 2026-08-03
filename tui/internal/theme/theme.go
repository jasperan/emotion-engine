package theme

import "github.com/charmbracelet/lipgloss"

// Catppuccin Mocha palette (see docs/tui-design-tokens.md).
// 14 approved tokens — single source of truth for the whole TUI.
var (
	Bg       = lipgloss.Color("#1e1e2e")
	Surface  = lipgloss.Color("#181825")
	Elevated = lipgloss.Color("#313244")
	Highest  = lipgloss.Color("#45475a")
	Text     = lipgloss.Color("#cdd6f4")
	Subtext  = lipgloss.Color("#a6adc8")
	Muted    = lipgloss.Color("#6c7086")
	Dim      = lipgloss.Color("#585b70")
	Primary  = lipgloss.Color("#89b4fa")
	Secondary = lipgloss.Color("#cba6f7")
	Info     = lipgloss.Color("#89dceb")
	Accent   = lipgloss.Color("#a6e3a1") // success
	Warning  = lipgloss.Color("#f9e2af")
	Danger   = lipgloss.Color("#f38ba8")
)

// Panel styles.
var (
	Panel = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(Dim).
		Padding(1, 2)

	ActivePanel = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(Primary).
			Padding(1, 2)

	GeneratingPanel = lipgloss.NewStyle().
				Border(lipgloss.RoundedBorder()).
				BorderForeground(Accent).
				Padding(1, 2)
)

// Text styles.
var (
	Title = lipgloss.NewStyle().
		Bold(true).
		Foreground(Text)

	Subtitle = lipgloss.NewStyle().
			Bold(true).
			Foreground(Primary)

	MutedText = lipgloss.NewStyle().
			Foreground(Muted)

	ErrorText = lipgloss.NewStyle().
			Bold(true).
			Foreground(Danger)

	AgentName = lipgloss.NewStyle().
			Bold(true).
			Foreground(Text)

	TokenText = lipgloss.NewStyle().
			Foreground(Subtext)

	Throughput = lipgloss.NewStyle().
			Bold(true).
			Foreground(Accent)
)

// Status indicators.
var (
	StatusActive = lipgloss.NewStyle().Foreground(Accent)
	StatusIdle   = lipgloss.NewStyle().Foreground(Muted)
	StatusError  = lipgloss.NewStyle().Foreground(Danger)
)

const StatusDot = "\u25cf" // ●

// Hazard level styles.
var (
	HazardLow    = lipgloss.NewStyle().Foreground(Accent)
	HazardMedium = lipgloss.NewStyle().Foreground(Warning)
	HazardHigh   = lipgloss.NewStyle().Foreground(Danger)
)

// StatusBar style.
var StatusBar = lipgloss.NewStyle().
	Background(Surface).
	Foreground(Text)

// Key hint styles.
var (
	KeyHint = lipgloss.NewStyle().Foreground(Dim)
	KeyName = lipgloss.NewStyle().Bold(true).Foreground(Primary)
)

// Cursor style.
var Cursor = lipgloss.NewStyle().Background(Primary)

// HazardColor returns a lipgloss.Color based on a 0.0-1.0 hazard level.
func HazardColor(level float64) lipgloss.Color {
	switch {
	case level >= 0.7:
		return Danger
	case level >= 0.4:
		return Warning
	default:
		return Accent
	}
}

// StatusColor returns a lipgloss.Color based on a status string.
func StatusColor(status string) lipgloss.Color {
	switch status {
	case "active", "generating", "running", "completed":
		return Accent
	case "error", "failed":
		return Danger
	case "idle", "paused", "stopped":
		return Muted
	default:
		return Muted
	}
}