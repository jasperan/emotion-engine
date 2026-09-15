package app

import (
	"strings"

	"charm.land/bubbles/v2/help"
	"charm.land/bubbles/v2/key"
	"charm.land/lipgloss/v2"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// kb builds a keybinding from the keys that trigger it, the text the interface
// shows for them, and a description.
//
// Keys are the strings a terminal actually delivers, i.e. what msg.String()
// returns for the same press: "esc" not "Escape", "space" not " ", "up" not "↑".
// The display text is deliberately separate, because several bindings are shown
// grouped ("q/Esc", "j/k", "1-9") and those are a rendering choice, not keys.
//
// A binding with no keys is NOT enabled (key.Binding.Enabled reports keys == nil
// as disabled) and bubbles/help skips disabled bindings, so every binding here
// carries at least one key.
func kb(display, desc string, keys ...string) key.Binding {
	return key.NewBinding(key.WithKeys(keys...), key.WithHelp(display, desc))
}

// HelpModel provides context-sensitive help overlay rendering.
type HelpModel struct{}

// Update is a no-op; help is stateless.
func (h HelpModel) Update(msg interface{}) (HelpModel, interface{}) {
	return h, nil
}

// Overlay renders a centered help box on top of the background string.
//
// The frame stays custom. bubbles/help renders a short or full help FOOTER, not
// a centred modal, so this view supplies the same key bindings and renders them
// itself. The bindings are the shared ones, so the modal and the footer describe
// the same keys.
func (h HelpModel) Overlay(bg string, w, h2 int, screen Screen) string {
	bindings := bindingsForScreen(screen)

	var b strings.Builder
	b.WriteString(theme.Title.Render("Keyboard Shortcuts") + "\n\n")

	for _, binding := range bindings {
		line := binding.Help()
		b.WriteString("  " + theme.KeyName.Render(padRight(line.Key, 10)) + theme.MutedText.Render(line.Desc) + "\n")
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
		lipgloss.WithWhitespaceStyle(lipgloss.NewStyle().Foreground(theme.Bg)),
	)
}

// hintBar renders a screen's terse key hints with the bubbles/help component.
//
// Two things about help are load-bearing here:
//
//   - Its width must be set. help only truncates when its width is greater than
//     zero, so an unset width disables truncation entirely and the row renders at
//     whatever length it wants.
//   - Even with a width set, help can emit an over-long row: when an item does
//     not fit and the ellipsis does not fit either, it appends the item anyway.
//     The result is therefore bounded here as well, so the caller gets a row that
//     cannot exceed the width it was given.
//
// A width of zero or less means "unconstrained": the hints render in full.
func hintBar(width int, bindings []key.Binding) string {
	if width < 1 {
		return hintBarText(0, bindings)
	}
	return lipgloss.NewStyle().MaxWidth(width).Render(hintBarText(width, bindings))
}

func hintBarText(width int, bindings []key.Binding) string {
	h := help.New()
	h.ShortSeparator = "  "
	h.Styles.ShortKey = theme.KeyName
	h.Styles.ShortDesc = theme.KeyHint
	h.Styles.ShortSeparator = lipgloss.NewStyle()
	h.SetWidth(width)
	return h.ShortHelpView(bindings)
}

// KeyMap adapts a screen's bindings to the help.KeyMap interface, so the same
// bindings can drive a bubbles/help view.
type KeyMap struct{ bindings []key.Binding }

// ShortHelp returns the bindings the short help should list.
func (k KeyMap) ShortHelp() []key.Binding { return k.bindings }

// FullHelp returns the bindings grouped into columns for the full help.
func (k KeyMap) FullHelp() [][]key.Binding { return [][]key.Binding{k.bindings} }

// ShortHelpFor returns a help.KeyMap for a screen's footer hints.
func ShortHelpFor(screen Screen) KeyMap { return KeyMap{bindings: footerBindingsForScreen(screen)} }

// bindingsForScreen returns the long-form bindings the help overlay lists.
func bindingsForScreen(screen Screen) []key.Binding {
	switch screen {
	case ScreenSplash:
		return []key.Binding{
			kb("Enter", "Continue", "enter"),
			kb("r", "Retry connection", "r"),
			kb("q", "Quit", "q"),
		}
	case ScreenScenarios:
		return []key.Binding{
			kb("Enter", "Launch scenario", "enter"),
			kb("↑/↓", "Navigate", "up", "down"),
			kb("/", "Filter", "/"),
			kb("h", "History", "h"),
			kb("a", "Analytics", "a"),
			kb("q/Esc", "Back", "q", "esc"),
		}
	case ScreenLauncher:
		return []key.Binding{
			kb("Enter", "Next field / start run", "enter"),
			kb("Tab", "Next field", "tab"),
			kb("Shift+Tab", "Prev field", "shift+tab"),
			kb("←/→", "Change provider", "left", "right"),
			kb("q/Esc", "Back", "q", "esc"),
		}
	case ScreenDashboard:
		return []key.Binding{
			kb("Tab", "Next panel", "tab"),
			kb("Shift+Tab", "Prev panel", "shift+tab"),
			kb("g", "Grid/Focus toggle", "g"),
			kb("t", "Theater view", "t"),
			kb("Enter", "Agent Mind View", "enter"),
			kb("f", "Filter messages (Feed)", "f"),
			kb("n", "Network mode (Network)", "n"),
			kb("Space", "Pause/Resume", "space"),
			kb("s", "Stop run", "s"),
			kb("1-9", "Select agent", "1", "2", "3", "4", "5", "6", "7", "8", "9"),
			kb("h/l", "Cycle agents", "h", "l"),
			kb("j/k", "Scroll", "j", "k"),
			kb("q/Esc", "Back", "q", "esc"),
		}
	case ScreenTheater:
		return []key.Binding{
			kb("Space", "Pause/Resume feed", "space"),
			kb("1-9", "Focus on agent", "1", "2", "3", "4", "5", "6", "7", "8", "9"),
			kb("0", "Show all agents", "0"),
			kb("j/k", "Scroll", "j", "k"),
			kb("q/Esc", "Back to dashboard", "q", "esc"),
		}
	case ScreenHistory:
		return []key.Binding{
			kb("Enter", "Open run (Replay/Dashboard)", "enter"),
			kb("r", "Replay selected run", "r"),
			kb("↑/↓", "Navigate", "up", "down"),
			kb("/", "Filter", "/"),
			kb("a", "Analytics", "a"),
			kb("q/Esc", "Back", "q", "esc"),
		}
	case ScreenAnalytics:
		return []key.Binding{
			kb("s", "Cycle scenario filter", "s"),
			kb("j/k", "Select run", "j", "k"),
			kb("Enter", "Open in Replay", "enter"),
			kb("q/Esc", "Back", "q", "esc"),
		}
	case ScreenReplay:
		return []key.Binding{
			kb("left/h", "Previous step", "left", "h"),
			kb("right/l", "Next step", "right", "l"),
			kb("H/L", "Back/forward 5 steps", "H", "L"),
			kb("Home/End", "First/last step", "home", "end"),
			kb("Space", "Play/pause", "space"),
			kb("+/-", "Speed up/slow down", "+", "-"),
			kb("d", "Toggle diff view", "d"),
			kb("e", "Jump to evaluation", "e"),
			kb("q/Esc", "Back to history", "q", "esc"),
		}
	}
	return nil
}

// footerBindingsForScreen returns the terse bindings the footer hint bar shows.
// They cover the same keys as bindingsForScreen for the same screen; a test
// asserts that, so the two views cannot drift apart.
func footerBindingsForScreen(screen Screen) []key.Binding {
	switch screen {
	case ScreenScenarios:
		return []key.Binding{
			kb("Enter", "launch", "enter"),
			kb("/", "filter", "/"),
			kb("q/Esc", "back", "q", "esc"),
		}
	case ScreenLauncher:
		return []key.Binding{
			kb("Enter", "next / start", "enter"),
			kb("Tab", "next field", "tab"),
			kb("q/Esc", "back", "q", "esc"),
		}
	case ScreenHistory:
		return []key.Binding{
			kb("Enter", "view", "enter"),
			kb("r", "replay", "r"),
			kb("↑/↓", "navigate", "up", "down"),
			kb("/", "filter", "/"),
			kb("q/Esc", "back", "q", "esc"),
		}
	case ScreenAnalytics:
		return []key.Binding{
			kb("s", "cycle filter", "s"),
			kb("j/k", "select", "j", "k"),
			kb("Enter", "replay", "enter"),
			kb("q/Esc", "back", "q", "esc"),
		}
	case ScreenTheater:
		return []key.Binding{
			kb("Space", "pause", "space"),
			kb("1-9", "focus", "1", "2", "3", "4", "5", "6", "7", "8", "9"),
			kb("0", "all", "0"),
			kb("q/Esc", "back", "q", "esc"),
		}
	case ScreenReplay:
		return []key.Binding{
			kb("←/h", "prev", "left", "h"),
			kb("→/l", "next", "right", "l"),
			kb("H/L", "±5", "H", "L"),
			kb("Home/End", "first/last", "home", "end"),
			kb("Space", "play", "space"),
			kb("+/-", "speed", "+", "-"),
			kb("d", "diff", "d"),
			kb("e", "eval", "e"),
			kb("q/Esc", "back", "q", "esc"),
		}
	}
	return nil
}

// SplashHintBindings returns the splash footer for the current connection state.
// The splash is the one screen whose hints change with state rather than only
// with the screen, which is why it is not covered by footerBindingsForScreen.
func SplashHintBindings(connected bool) []key.Binding {
	if connected {
		return []key.Binding{
			kb("Enter", "browse scenarios", "enter"),
			kb("q", "quit", "q"),
		}
	}
	return []key.Binding{
		kb("r", "retry", "r"),
		kb("q", "quit", "q"),
	}
}

// padRight pads a string with spaces to the given width.
func padRight(s string, n int) string {
	if len(s) >= n {
		return s
	}
	return s + strings.Repeat(" ", n-len(s))
}
