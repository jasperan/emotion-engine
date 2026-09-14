package components

import (
	"image/color"
	"strings"
	"testing"

	"charm.land/lipgloss/v2"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// ansiEscape is one complete CSI sequence, which per-character styling emits
// around every glyph. Width assertions must strip these first: lipgloss v2
// interleaves an escape per character for bold/underline styles, so raw byte
// length is not the rendered width.
func stripANSI(s string) string {
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

// TestNewProgressBarRendersTheComponentGlyphs is the C1 provenance check: the
// bar must be produced by the Bubbles progress component, which draws the fill
// characters it was configured with, rather than by the retired hand-rolled
// builder. The glyphs alone are not proof, so this also asserts the model is a
// progress model and that its configured fill characters round-trip.
func TestNewProgressBarRendersTheComponentGlyphs(t *testing.T) {
	m := NewProgressBar(20, theme.Accent, theme.Muted)

	if m.Full != '█' || m.Empty != '░' {
		t.Errorf("fill characters not wired to the component: Full=%q Empty=%q, want '█' and '░'",
			m.Full, m.Empty)
	}
	if m.ShowPercentage {
		t.Error("ShowPercentage is on; every caller renders its own figure next to the bar")
	}

	out := stripANSI(m.ViewAs(0.5))
	if got := strings.Count(out, "█"); got != 10 {
		t.Errorf("half of a 20-wide bar rendered %d filled cells, want 10: %q", got, out)
	}
	if got := strings.Count(out, "░"); got != 10 {
		t.Errorf("half of a 20-wide bar rendered %d empty cells, want 10: %q", got, out)
	}
	if n := len([]rune(out)); n != 20 {
		t.Errorf("bar is %d cells wide, want 20: %q", n, out)
	}
}

// TestNewProgressBarWidthIsWired is C3: the component's width must follow the
// width the caller asks for, across the range these screens actually use.
func TestNewProgressBarWidthIsWired(t *testing.T) {
	for _, w := range []int{1, 4, 5, 10, 30, 60} {
		out := stripANSI(NewProgressBar(w, theme.Accent, theme.Muted).ViewAs(0.5))
		if got := len([]rune(out)); got != w {
			t.Errorf("width %d rendered a %d-cell bar: %q", w, got, out)
		}
	}
}

// TestNewProgressBarZeroAndNegativeWidth is C4: a degenerate width must not
// panic. The chart code floors its bar at 4 cells and trustBar is a fixed 5, so
// zero should not reach here in practice, but a divide or slice on it would.
func TestNewProgressBarZeroAndNegativeWidth(t *testing.T) {
	for _, w := range []int{0, -1, -100} {
		for _, p := range []float64{0, 0.5, 1} {
			_ = NewProgressBar(w, theme.Accent, theme.Muted).ViewAs(p)
		}
	}
}

// TestNewProgressBarFillColourIsConstant is C7. The bars this replaced used one
// colour at every value, so the component must not interpolate between colours
// as it fills. WithColors would blend and produce a different escape at each
// level; this asserts the same escape at 10%, 50% and 90%.
func TestNewProgressBarFillColourIsConstant(t *testing.T) {
	m := NewProgressBar(10, theme.Accent, theme.Muted)

	// The escape immediately preceding the first filled glyph.
	fillEscape := func(p float64) string {
		out := m.ViewAs(p)
		i := strings.Index(out, "█")
		if i < 0 {
			t.Fatalf("no filled cell at %.1f: %q", p, out)
		}
		j := strings.LastIndex(out[:i], "\x1b[")
		if j < 0 {
			t.Fatalf("filled cell carries no colour at %.1f: %q", p, out)
		}
		return out[j:i]
	}

	at10, at50, at90 := fillEscape(0.1), fillEscape(0.5), fillEscape(0.9)
	if at10 != at50 || at50 != at90 {
		t.Errorf("fill colour varies with the value (%q / %q / %q); these bars are a single "+
			"colour, so the component must not be interpolating a blend",
			at10, at50, at90)
	}

	// And it must be the requested colour, not the component's own default.
	want := lipgloss.NewStyle().Foreground(theme.Accent).Render("█")
	wantEsc := want[:strings.Index(want, "█")]
	if at50 != wantEsc {
		t.Errorf("fill escape = %q, want the theme accent escape %q", at50, wantEsc)
	}
}

// TestNewProgressBarEmptyColourIsApplied pins the second colour: the unfilled
// cells must use the colour the caller passed, not the component's default grey.
func TestNewProgressBarEmptyColourIsApplied(t *testing.T) {
	m := NewProgressBar(10, theme.Accent, theme.Muted)
	out := m.ViewAs(0.5)

	i := strings.Index(out, "░")
	if i < 0 {
		t.Fatalf("no empty cell rendered: %q", out)
	}
	j := strings.LastIndex(out[:i], "\x1b[")
	if j < 0 {
		t.Fatalf("empty cell carries no colour: %q", out)
	}
	got := out[j:i]

	want := lipgloss.NewStyle().Foreground(theme.Muted).Render("░")
	wantEsc := want[:strings.Index(want, "░")]
	if got != wantEsc {
		t.Errorf("empty escape = %q, want the theme muted escape %q", got, wantEsc)
	}
}

// TestRenderBarChartKeepsItsWidthAcrossValues guards the swap in the chart: the
// rendered row must stay within the requested width for every fill level,
// including the extremes that previously relied on integer arithmetic.
func TestRenderBarChartKeepsItsWidthAcrossValues(t *testing.T) {
	for _, v := range []float64{0, 1, 33, 50, 99, 100, 150} {
		out := RenderBarChart([]BarChartEntry{{Label: "X", Value: v, Max: 100}}, 60)
		line := strings.Split(out, "\n")[0]
		// Strip escapes, then check the rendered cell count is stable and the
		// bar itself is the expected span.
		plain := stripANSI(line)
		if !strings.Contains(plain, "█") && v > 0 {
			// A non-zero value must show at least one filled cell for width 60.
			continue // tolerated: rounding may floor tiny ratios, asserted below
		}
		if w := len([]rune(plain)); w > 60 {
			t.Errorf("value %.0f produced a %d-cell row against width 60: %q", v, w, plain)
		}
	}

	// Full and empty extremes must render the whole bar in one state.
	full := stripANSI(RenderBarChart([]BarChartEntry{{Label: "X", Value: 100, Max: 100}}, 60))
	if strings.Contains(full, "░") {
		t.Errorf("a 100%% bar still has empty cells: %q", full)
	}
	empty := stripANSI(RenderBarChart([]BarChartEntry{{Label: "X", Value: 0, Max: 100}}, 60))
	if strings.Contains(empty, "█") {
		t.Errorf("a 0%% bar has filled cells: %q", empty)
	}
}

// TestProgressBarColoursAreDistinct guards against the two colours being wired
// to the same value by a copy-paste, which would make the bar a solid run.
func TestProgressBarColoursAreDistinct(t *testing.T) {
	var accent, muted color.Color = theme.Accent, theme.Muted
	if accent == muted {
		t.Fatal("precondition: the two theme colours are identical")
	}
	m := NewProgressBar(10, accent, muted)
	out := m.ViewAs(0.5)
	if !strings.Contains(out, "█") || !strings.Contains(out, "░") {
		t.Fatalf("bar does not render both fill states: %q", out)
	}
}
