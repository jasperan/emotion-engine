package theme

import "github.com/charmbracelet/lipgloss"

// Pi-inspired color palette.
var (
	Primary = lipgloss.Color("#5E5CE6")
	Accent  = lipgloss.Color("#30D158")
	Danger  = lipgloss.Color("#FF453A")
	Warning = lipgloss.Color("#FFD60A")
	Muted   = lipgloss.Color("#636366")
	Surface = lipgloss.Color("#1C1C1E")
	Text    = lipgloss.Color("#E5E5EA")
	Dim     = lipgloss.Color("#48484A")
)

// Panel styles.
var (
	Panel = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(Muted).
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
			Foreground(lipgloss.Color("#AEAEB2"))

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
	case "active", "generating", "running":
		return Accent
	case "error", "failed":
		return Danger
	case "idle", "paused", "stopped":
		return Muted
	default:
		return Muted
	}
}
