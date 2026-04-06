package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// DiffChangeType categorizes a world state change.
type DiffChangeType int

const (
	DiffAdded   DiffChangeType = iota // new key/event
	DiffChanged                       // value modified
	DiffRemoved                       // key/event gone
)

// DiffEntry represents one change in the world state.
type DiffEntry struct {
	Category   string // "hazard", "movement", "proposal", "trust", "health", "stress", "event"
	Key        string // what changed (agent name, location, etc.)
	ChangeType DiffChangeType
	OldValue   string
	NewValue   string
}

// ContagionEvent represents a stress propagation event.
type ContagionEvent struct {
	SourceName  string
	TargetName  string
	StressDelta float64
	StressBefore float64
	StressAfter float64
	Mechanism   string // "panic_spread" or "calm_anchor"
	Location    string
	Step        int
}

// StepDiffData holds everything for the step diff + contagion panel.
type StepDiffData struct {
	CurrentStep int
	Diffs       [][]DiffEntry // rolling history, last entry is current step
	Contagion   []ContagionEvent
	Width       int
	Height      int
}

// diffIcon returns a colored icon for the change type.
func diffIcon(ct DiffChangeType) string {
	switch ct {
	case DiffAdded:
		return lipgloss.NewStyle().Foreground(theme.Accent).Render("+")
	case DiffChanged:
		return lipgloss.NewStyle().Foreground(theme.Warning).Render("~")
	case DiffRemoved:
		return lipgloss.NewStyle().Foreground(theme.Danger).Render("-")
	}
	return " "
}

// categoryIcon returns an icon for the diff category.
func categoryIcon(cat string) string {
	switch cat {
	case "hazard":
		return "\u26a0" // ⚠
	case "movement":
		return "\u2192" // →
	case "proposal":
		return "\u2696" // ⚖
	case "trust":
		return "\u2661" // ♡
	case "health":
		return "\u2764" // ❤
	case "stress":
		return "\u26a1" // ⚡
	case "event":
		return "\u25cf" // ●
	default:
		return "\u00b7" // ·
	}
}

// RenderStepDiff renders the world state diff panel.
func RenderStepDiff(d StepDiffData) string {
	var lines []string
	lines = append(lines, theme.Subtitle.Render("STEP DIFF"))
	lines = append(lines, "")

	if len(d.Diffs) == 0 {
		lines = append(lines, theme.MutedText.Render("Waiting for state changes..."))
		return strings.Join(lines, "\n")
	}

	// Show current step's diff (last entry)
	currentDiff := d.Diffs[len(d.Diffs)-1]

	if len(currentDiff) == 0 {
		lines = append(lines, theme.MutedText.Render("  No changes this step"))
	} else {
		// Group by category
		byCat := make(map[string][]DiffEntry)
		catOrder := []string{}
		for _, e := range currentDiff {
			if _, seen := byCat[e.Category]; !seen {
				catOrder = append(catOrder, e.Category)
			}
			byCat[e.Category] = append(byCat[e.Category], e)
		}

		for _, cat := range catOrder {
			entries := byCat[cat]
			catLabel := lipgloss.NewStyle().Foreground(theme.Primary).Bold(true).
				Render(categoryIcon(cat) + " " + strings.ToUpper(cat))
			lines = append(lines, "  "+catLabel)

			for _, e := range entries {
				icon := diffIcon(e.ChangeType)
				detail := e.Key
				if e.OldValue != "" && e.NewValue != "" {
					detail += fmt.Sprintf(": %s \u2192 %s",
						theme.MutedText.Render(e.OldValue),
						lipgloss.NewStyle().Foreground(theme.Text).Render(e.NewValue))
				} else if e.NewValue != "" {
					detail += ": " + lipgloss.NewStyle().Foreground(theme.Text).Render(e.NewValue)
				}
				lines = append(lines, fmt.Sprintf("    %s %s", icon, detail))
			}
		}
	}

	// Summary sparkline of recent diff sizes
	if len(d.Diffs) > 1 {
		lines = append(lines, "")
		spark := "  "
		blocks := []string{"\u2581", "\u2582", "\u2583", "\u2584", "\u2585", "\u2586", "\u2587", "\u2588"}
		maxSize := 1
		for _, diff := range d.Diffs {
			if len(diff) > maxSize {
				maxSize = len(diff)
			}
		}
		for _, diff := range d.Diffs {
			idx := len(diff) * 7 / maxSize
			if idx > 7 {
				idx = 7
			}
			spark += lipgloss.NewStyle().Foreground(theme.Primary).Render(blocks[idx])
		}
		lines = append(lines, theme.MutedText.Render("  changes:")+spark)
	}

	// Contagion events
	if len(d.Contagion) > 0 {
		lines = append(lines, "")
		lines = append(lines, theme.Subtitle.Render("EMOTION CONTAGION"))

		// Show last 5
		start := 0
		if len(d.Contagion) > 5 {
			start = len(d.Contagion) - 5
		}
		for _, c := range d.Contagion[start:] {
			var mechStyle lipgloss.Style
			var mechIcon string
			if c.Mechanism == "panic_spread" {
				mechStyle = lipgloss.NewStyle().Foreground(theme.Danger)
				mechIcon = "\u2191" // ↑ stress up
			} else {
				mechStyle = lipgloss.NewStyle().Foreground(theme.Accent)
				mechIcon = "\u2193" // ↓ stress down
			}

			arrow := mechStyle.Render(c.SourceName + " \u2192 " + c.TargetName)
			delta := mechStyle.Render(fmt.Sprintf("%s%+.1f", mechIcon, c.StressDelta))
			loc := theme.MutedText.Render("@" + c.Location)

			lines = append(lines, fmt.Sprintf("  %s %s %s", arrow, delta, loc))
		}
	}

	return strings.Join(lines, "\n")
}
