package components

import (
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

const (
	bucketCount    = 60
	sparkChars     = "▁▂▃▄▅▆▇█"
	rateWindowSecs = 5
)

var sparkRunes = []rune(sparkChars)

// ThroughputTracker tracks token throughput using a ring buffer of 1-second buckets.
type ThroughputTracker struct {
	mu      sync.Mutex
	buckets [bucketCount]int
	times   [bucketCount]int64 // unix seconds
	head    int
}

// NewThroughputTracker creates a new throughput tracker.
func NewThroughputTracker() *ThroughputTracker {
	return &ThroughputTracker{}
}

// Add records token production.
func (t *ThroughputTracker) Add(tokenCount int) {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now().Unix()
	t.advance(now)
	t.buckets[t.head] += tokenCount
}

// advance moves the head forward to the current second, zeroing skipped buckets.
func (t *ThroughputTracker) advance(now int64) {
	if t.times[t.head] == now {
		return
	}

	if t.times[t.head] == 0 {
		// First use
		t.times[t.head] = now
		return
	}

	gap := now - t.times[t.head]
	if gap <= 0 {
		return
	}
	if gap > bucketCount {
		gap = bucketCount
	}

	for i := int64(0); i < gap; i++ {
		t.head = (t.head + 1) % bucketCount
		t.buckets[t.head] = 0
		t.times[t.head] = now - gap + i + 1
	}
}

// CurrentRate returns the average tokens per second over the last rateWindowSecs seconds.
func (t *ThroughputTracker) CurrentRate() float64 {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now().Unix()
	t.advance(now)

	var total int
	var count int
	for i := 0; i < rateWindowSecs; i++ {
		idx := (t.head - i + bucketCount) % bucketCount
		if t.times[idx] > 0 && now-t.times[idx] < rateWindowSecs {
			total += t.buckets[idx]
			count++
		}
	}

	if count == 0 {
		return 0
	}
	return float64(total) / float64(count)
}

// Sparkline renders a sparkline of the recent throughput history.
func (t *ThroughputTracker) Sparkline(width int) string {
	t.mu.Lock()
	defer t.mu.Unlock()

	now := time.Now().Unix()
	t.advance(now)

	if width <= 0 {
		return ""
	}
	if width > bucketCount {
		width = bucketCount
	}

	// Collect the last `width` values
	values := make([]int, width)
	maxVal := 1
	for i := 0; i < width; i++ {
		idx := (t.head - width + 1 + i + bucketCount) % bucketCount
		values[i] = t.buckets[idx]
		if values[i] > maxVal {
			maxVal = values[i]
		}
	}

	// Map to sparkline characters
	var sb strings.Builder
	numChars := len(sparkRunes)
	for _, v := range values {
		charIdx := v * (numChars - 1) / maxVal
		if charIdx >= numChars {
			charIdx = numChars - 1
		}
		sb.WriteRune(sparkRunes[charIdx])
	}

	return sb.String()
}

// RenderThroughput renders the throughput display with sparkline and rate.
func RenderThroughput(t *ThroughputTracker, width int) string {
	rate := t.CurrentRate()
	sparkWidth := width - 20
	if sparkWidth < 5 {
		sparkWidth = 5
	}

	spark := t.Sparkline(sparkWidth)
	rateStr := theme.Throughput.Render(fmt.Sprintf("%.1f tok/s", rate))

	return fmt.Sprintf("%s %s", spark, rateStr)
}
