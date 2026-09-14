package components

import (
	"image/color"

	"charm.land/bubbles/v2/progress"
)

// The two fill characters every hand-rolled bar in this TUI used before the
// Bubbles progress component replaced them.
const (
	barFull  = '█'
	barEmpty = '░'
)

// NewProgressBar builds a Bubbles progress bar that reproduces the hand-rolled
// bar it replaces: the same two fill characters, a constant fill colour, and no
// percentage suffix, because every caller renders its own figure beside the bar.
//
// full and empty are applied directly. Each is a single colour rather than a
// threshold ramp, so the colour function ignores both arguments and returns the
// same value at every fill level. WithColorFunc is used in preference to
// WithColors because WithColors interpolates BETWEEN colours, which is a
// different operation from choosing one.
//
// The model is a value with no locking, and percent is applied through ViewAs,
// which renders without mutating state. Building one per call is therefore safe
// and keeps these render helpers free of shared mutable state.
func NewProgressBar(width int, full, empty color.Color) progress.Model {
	if width < 1 {
		width = 1
	}
	m := progress.New(
		progress.WithWidth(width),
		progress.WithFillCharacters(barFull, barEmpty),
		progress.WithoutPercentage(),
		progress.WithColorFunc(func(_, _ float64) color.Color { return full }),
	)
	m.EmptyColor = empty
	return m
}
