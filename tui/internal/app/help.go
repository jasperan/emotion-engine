package app

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// HelpModel provides context-sensitive help overlay rendering.
type HelpModel struct{}

// Update is a no-op; help is stateless.
func (h HelpModel) Update(msg interface{}) (HelpModel, interface{}) {
	return h, nil
}

// Overlay renders a centered help box on top of the background string.
func (h HelpModel) Overlay(bg string, w, h2 int, screen Screen) string {
	bindings := h.bindingsForScreen(screen)

	var b strings.Builder
	b.WriteString(theme.Title.Render("Keyboard Shortcuts") + "\n\n")

	for _, kb := range bindings {
		b.WriteString("  " + theme.KeyName.Render(padRight(kb.key, 10)) + theme.MutedText.Render(kb.desc) + "\n")
	}

	b.WriteString("\n" + theme.MutedText.Render("── Global ──") + "\n")
	b.WriteString("  " + theme.KeyName.Render(padRight("F1", 10)) + theme.MutedText.Render("Toggle help") + "\n")
	b.WriteString("  " + theme.KeyName.Render(padRight("Ctrl+C", 10)) + theme.MutedText.Render("Quit") + "\n")

	helpContent := lipgloss.NewStyle().
		Width(50).
		Padding(1, 2).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Primary).
		Foreground(theme.Text).
		Render(b.String())

	return lipgloss.Place(
		w, h2,
		lipgloss.Center, lipgloss.Center,
		helpContent,
		lipgloss.WithWhitespaceChars(" "),
		lipgloss.WithWhitespaceForeground(lipgloss.Color("#000000")),
	)
}

type keyBinding struct {
	key  string
	desc string
}

func (h HelpModel) bindingsForScreen(screen Screen) []keyBinding {
	switch screen {
	case ScreenSplash:
		return []keyBinding{
			{"Enter", "Continue"},
			{"r", "Retry connection"},
			{"q", "Quit"},
		}
	case ScreenScenarios:
		return []keyBinding{
			{"Enter", "Launch scenario"},
			{"↑/↓", "Navigate"},
			{"/", "Filter"},
			{"h", "History"},
			{"q", "Back"},
		}
	case ScreenLauncher:
		return []keyBinding{
			{"Enter", "Launch run"},
			{"Tab", "Next field"},
			{"Esc", "Back"},
		}
	case ScreenDashboard:
		return []keyBinding{
			{"Tab", "Panel mode"},
			{"g", "Grid toggle"},
			{"Space", "Pause/Resume"},
			{"s", "Stop run"},
			{"1-9", "Select agent"},
			{"←/→", "Cycle agents"},
			{"↑/↓", "Scroll feed"},
			{"q", "Back"},
		}
	case ScreenHistory:
		return []keyBinding{
			{"Enter", "View run"},
			{"r", "Replay run"},
			{"↑/↓", "Navigate"},
			{"q", "Back"},
		}
	case ScreenReplay:
		return []keyBinding{
			{"left/h", "Previous step"},
			{"right/l", "Next step"},
			{"H/L", "Back/forward 5 steps"},
			{"Home/End", "First/last step"},
			{"Space", "Play/pause"},
			{"+/-", "Speed up/slow down"},
			{"d", "Toggle diff view"},
			{"e", "Jump to evaluation"},
			{"q", "Back to history"},
		}
	default:
		return nil
	}
}

// padRight pads a string with spaces to the given width.
func padRight(s string, n int) string {
	if len(s) >= n {
		return s
	}
	return s + strings.Repeat(" ", n-len(s))
}
