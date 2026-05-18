package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// StatusBarData holds all data needed to render the status bar.
type StatusBarData struct {
	Connected  bool
	RunStatus  string
	Step       int
	MaxSteps   int
	TokPerSec  float64
	Hints      []KeyHint
	PanelName  string
	FilterName string
}

// KeyHint represents a keyboard shortcut hint.
type KeyHint struct {
	Key  string
	Desc string
}

// RenderStatusBar renders a full-width status bar with left, center, and right sections.
func RenderStatusBar(d StatusBarData, width int) string {
	if width <= 0 {
		return ""
	}

	left := renderStatusLeft(d, true)
	center := fmt.Sprintf("Step %d/%d", d.Step, d.MaxSteps)
	right := renderStatusRight(d, statusRightWidth(left, center, width))
	if !statusPartsFit(left, center, right, width) {
		left = renderStatusLeft(d, false)
		right = renderStatusRight(d, statusRightWidth(left, center, width))
	}
	if !statusPartsFit(left, center, right, width) {
		center = fmt.Sprintf("%d/%d", d.Step, d.MaxSteps)
		right = renderStatusRight(d, statusRightWidth(left, center, width))
	}
	if !statusPartsFit(left, center, right, width) {
		return renderCompactStatusBar(d, width)
	}

	leftW := lipgloss.Width(left)
	centerW := lipgloss.Width(center)
	rightW := lipgloss.Width(right)

	remaining := width - leftW - centerW - rightW
	if remaining < 2 {
		return renderCompactStatusBar(d, width)
	}

	gap1 := width/2 - leftW - centerW/2
	if gap1 < 1 {
		gap1 = 1
	}
	if gap1 > remaining-1 {
		gap1 = remaining - 1
	}
	gap2 := remaining - gap1

	bar := left + strings.Repeat(" ", gap1) + center + strings.Repeat(" ", gap2) + right
	if lipgloss.Width(bar) > width {
		return renderCompactStatusBar(d, width)
	}

	return theme.StatusBar.Width(width).Render(bar)
}

func renderStatusLeft(d StatusBarData, includeContext bool) string {
	var connDot string
	if d.Connected {
		connDot = theme.StatusActive.Render(theme.StatusDot)
	} else {
		connDot = theme.StatusError.Render(theme.StatusDot)
	}

	statusStyle := lipgloss.NewStyle().Foreground(theme.StatusColor(d.RunStatus))
	left := fmt.Sprintf(" %s %s", connDot, statusStyle.Render(d.RunStatus))
	if includeContext && d.PanelName != "" {
		left += "  " + theme.Subtitle.Render("["+d.PanelName+"]")
	}
	if includeContext && d.FilterName != "" && d.FilterName != "All" {
		left += "  " + lipgloss.NewStyle().Foreground(theme.Warning).Render("filter:"+d.FilterName)
	}
	return left
}

func renderStatusRight(d StatusBarData, width int) string {
	if width <= 0 {
		return ""
	}

	tokStr := theme.Throughput.Render(fmt.Sprintf("%.1f tok/s", d.TokPerSec))
	for hintCount := len(d.Hints); hintCount > 0; hintCount-- {
		right := renderStatusRightWithHints(tokStr, selectStatusHints(d.Hints, hintCount))
		if lipgloss.Width(right) <= width {
			return right
		}
	}
	for hintCount := len(d.Hints); hintCount > 0; hintCount-- {
		right := renderStatusRightWithHints("", selectStatusHints(d.Hints, hintCount))
		if lipgloss.Width(right) <= width {
			return right
		}
	}
	right := renderStatusRightWithHints(tokStr, nil)
	if lipgloss.Width(right) <= width {
		return right
	}

	return ""
}

func renderStatusRightWithHints(tokStr string, selected []KeyHint) string {
	hints := make([]string, 0, len(selected))
	for _, h := range selected {
		hints = append(hints, fmt.Sprintf("%s %s",
			theme.KeyName.Render(h.Key),
			theme.KeyHint.Render(h.Desc),
		))
	}
	var parts []string
	if tokStr != "" {
		parts = append(parts, tokStr)
	}
	if len(hints) > 0 {
		parts = append(parts, strings.Join(hints, "  "))
	}
	right := strings.Join(parts, "  ")
	if right != "" {
		right += " "
	}
	return right
}

func selectStatusHints(hints []KeyHint, count int) []KeyHint {
	if count <= 0 {
		return nil
	}
	if count >= len(hints) {
		return hints
	}

	backIndex := -1
	for i, h := range hints {
		if isBackHint(h) {
			backIndex = i
		}
	}
	if backIndex < 0 {
		return hints[:count]
	}

	selected := make([]KeyHint, 0, count)
	for i, h := range hints {
		if i == backIndex {
			continue
		}
		if len(selected) == count-1 {
			break
		}
		selected = append(selected, h)
	}
	return append(selected, hints[backIndex])
}

func isBackHint(h KeyHint) bool {
	return strings.EqualFold(h.Desc, "back") || strings.Contains(strings.ToLower(h.Key), "esc")
}

func statusRightWidth(left, center string, width int) int {
	return width - lipgloss.Width(left) - lipgloss.Width(center) - 2
}

func statusPartsFit(left, center, right string, width int) bool {
	return lipgloss.Width(left)+lipgloss.Width(center)+lipgloss.Width(right)+2 <= width
}

func renderCompactStatusBar(d StatusBarData, width int) string {
	status := d.RunStatus
	if status == "" {
		status = "idle"
	}
	bar := fmt.Sprintf(" %s %d/%d %.1f tok/s", status, d.Step, d.MaxSteps, d.TokPerSec)
	return theme.StatusBar.Width(width).Render(trimRunes(bar, width))
}

func trimRunes(s string, width int) string {
	if width <= 0 {
		return ""
	}
	runes := []rune(s)
	if len(runes) <= width {
		return s
	}
	if width <= 1 {
		return string(runes[:width])
	}
	return string(runes[:width-1]) + "~"
}
