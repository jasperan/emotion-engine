package app

import (
	"strings"
	"testing"

	"charm.land/bubbles/v2/key"
	"charm.land/lipgloss/v2"
)

// footerScreens pairs each screen that renders a footer hint bar with the
// bindings it draws. The splash is listed twice because its hints depend on the
// connection state rather than only on the screen.
var footerScreens = []struct {
	name     string
	bindings []key.Binding
}{
	{"splash-connected", SplashHintBindings(true)},
	{"splash-disconnected", SplashHintBindings(false)},
	{"scenarios", footerBindingsForScreen(ScreenScenarios)},
	{"launcher", footerBindingsForScreen(ScreenLauncher)},
	{"history", footerBindingsForScreen(ScreenHistory)},
	{"analytics", footerBindingsForScreen(ScreenAnalytics)},
	{"theater", footerBindingsForScreen(ScreenTheater)},
	{"replay", footerBindingsForScreen(ScreenReplay)},
}

// TestHintBarNeverExceedsItsWidth is the HZ-7 guard.
//
// bubbles/help can emit a row WIDER than the width it was given: when an item
// does not fit and the ellipsis does not fit either, it appends the item anyway
// rather than dropping it. So the contract asserted here is the one the footer
// actually needs - the rendered hint bar never exceeds the width it was handed -
// and hintBar has to bound the result itself to meet it.
func TestHintBarNeverExceedsItsWidth(t *testing.T) {
	for _, width := range []int{40, 60, 80, 120} {
		for _, fs := range footerScreens {
			if len(fs.bindings) == 0 {
				t.Errorf("%s has no footer bindings; the fit assertion would be vacuous", fs.name)
				continue
			}
			out := hintBar(width, fs.bindings)
			if got := lipgloss.Width(out); got > width {
				t.Errorf("%s: hint bar is %d cells wide against a %d-column row: %q",
					fs.name, got, width, out)
			}
		}
	}
}

// TestHintBarElidesWhenTheRowIsTooNarrow proves the width above is doing real
// work rather than the full hint bar simply happening to fit.
//
// The invariant is conditional on purpose: a bar that already fits must render
// unchanged, and only a bar wider than the row may be trimmed. Demanding elision
// from every screen would fail on the two-binding splash footer, which is
// shorter than 20 cells and has nothing to drop.
func TestHintBarElidesWhenTheRowIsTooNarrow(t *testing.T) {
	const narrow = 20
	for _, fs := range footerScreens {
		full := hintBar(0, fs.bindings)
		narrowed := hintBar(narrow, fs.bindings)

		if lipgloss.Width(narrowed) > narrow {
			t.Errorf("%s: narrow bar is %d cells wide, want <= %d: %q",
				fs.name, lipgloss.Width(narrowed), narrow, narrowed)
		}

		fullWidth := lipgloss.Width(full)
		if fullWidth <= narrow {
			// Fits already: the narrow rendering must be the same text.
			if stripANSITest(narrowed) != stripANSITest(full) {
				t.Errorf("%s: bar fits in %d cells (%d) but was altered anyway\n  full:   %q\n  narrow: %q",
					fs.name, narrow, fullWidth, full, narrowed)
			}
			continue
		}

		if stripANSITest(narrowed) == stripANSITest(full) {
			t.Errorf("%s: bar is %d cells wide, over the %d-cell row, yet rendered identically "+
				"at width 0 and width %d, so nothing was elided\n  full:   %q\n  narrow: %q",
				fs.name, fullWidth, narrow, narrow, full, narrowed)
		}
	}
}

// TestHintBarElidesWithAnEllipsisNotAHardCut pins that the help component's own
// truncation is still doing work, rather than every fit being achieved by the
// hard bound hintBar applies on top.
//
// Measured on bubbles v2.2.1, the component's truncation is not just incomplete
// but NON-MONOTONIC. For the replay bindings: width 40 and 45 elide to 28 cells,
// 50 and 55 elide to 49, and 60 renders the full 98-cell row. A wider row can
// therefore render NARROWER than a narrower one. The cause is in shouldAddItem
// (help.go:234-244): when an item does not fit and the 2-cell ellipsis does not
// fit either, it appends the item anyway, and from that point on every remaining
// item is appended too, so the row degrades to its full natural width.
//
// Width 40 is used here because it is a width where the component's own elision
// works, so this test fails if that path is lost.
func TestHintBarElidesWithAnEllipsisNotAHardCut(t *testing.T) {
	bindings := footerBindingsForScreen(ScreenReplay)
	if len(bindings) == 0 {
		t.Fatal("replay has no footer bindings; this assertion would be vacuous")
	}

	full := hintBar(0, bindings)
	if lipgloss.Width(full) <= 40 {
		t.Fatalf("precondition: replay's unconstrained bar is %d cells, so width 40 "+
			"would not constrain it", lipgloss.Width(full))
	}

	out := hintBar(40, bindings)
	if lipgloss.Width(out) > 40 {
		t.Errorf("constrained bar is %d cells wide, want <= 40: %q", lipgloss.Width(out), out)
	}
	if !strings.Contains(out, "\u2026") {
		t.Errorf("constrained bar dropped bindings without the component's ellipsis, "+
			"so it was cut rather than elided: %q", out)
	}
}

// TestHintBarUnconstrainedShowsEveryBinding pins the other end: with no width
// the bar is not truncated, so every binding still reaches the user.
func TestHintBarUnconstrainedShowsEveryBinding(t *testing.T) {
	for _, fs := range footerScreens {
		out := stripANSITest(hintBar(0, fs.bindings))
		for _, b := range fs.bindings {
			line := b.Help()
			if !strings.Contains(out, line.Desc) {
				t.Errorf("%s: unconstrained bar is missing binding %q (%q): %q",
					fs.name, line.Key, line.Desc, out)
			}
		}
	}
}

// TestFooterBindingsCoverTheModalKeys keeps the two views of the same keys from
// drifting apart: every key the footer advertises must also be documented by the
// help overlay for that screen.
func TestFooterBindingsCoverTheModalKeys(t *testing.T) {
	for _, fs := range footerScreens {
		screen, ok := screenForFooter(fs.name)
		if !ok {
			continue // splash: its modal keys are asserted separately below
		}
		// Compare the KEYS, not the display text: the footer writes "↑/h" where the
		// overlay writes "left/h", and both describe the same press.
		modal := map[string]bool{}
		for _, b := range bindingsForScreen(screen) {
			for _, k := range b.Keys() {
				modal[k] = true
			}
		}
		for _, b := range fs.bindings {
			for _, k := range b.Keys() {
				if !modal[k] {
					t.Errorf("%s: footer binds %q but the help overlay does not document it",
						fs.name, k)
				}
			}
		}
	}
}

func screenForFooter(name string) (Screen, bool) {
	switch name {
	case "scenarios":
		return ScreenScenarios, true
	case "launcher":
		return ScreenLauncher, true
	case "history":
		return ScreenHistory, true
	case "analytics":
		return ScreenAnalytics, true
	case "theater":
		return ScreenTheater, true
	case "replay":
		return ScreenReplay, true
	}
	return 0, false
}

// TestSplashFooterCoversTheModalKeys is the splash's version of the check above.
func TestSplashFooterCoversTheModalKeys(t *testing.T) {
	modal := map[string]bool{}
	for _, b := range bindingsForScreen(ScreenSplash) {
		for _, k := range b.Keys() {
			modal[k] = true
		}
	}
	for _, set := range [][]key.Binding{SplashHintBindings(true), SplashHintBindings(false)} {
		for _, b := range set {
			for _, k := range b.Keys() {
				if !modal[k] {
					t.Errorf("splash footer binds %q but the overlay does not document it", k)
				}
			}
		}
	}
}

// stripANSITest removes CSI escape sequences so assertions compare visible text.
func stripANSITest(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); {
		if s[i] == '\x1b' && i+1 < len(s) && s[i+1] == '[' {
			j := i + 2
			for j < len(s) && s[j] != 'm' {
				j++
			}
			if j < len(s) {
				j++
			}
			i = j
			continue
		}
		b.WriteByte(s[i])
		i++
	}
	return b.String()
}
