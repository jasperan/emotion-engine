package components

import (
	"strings"
	"testing"
)

// =============================================================================
// ThroughputTracker / RenderThroughput edge cases
// =============================================================================

func TestSparkline_Width0(t *testing.T) {
	tt := NewThroughputTracker()
	tt.Add(10)
	spark := tt.Sparkline(0)
	if spark != "" {
		t.Errorf("expected empty string for width=0, got %q", spark)
	}
}

func TestSparkline_NegativeWidth(t *testing.T) {
	tt := NewThroughputTracker()
	tt.Add(10)
	spark := tt.Sparkline(-5)
	if spark != "" {
		t.Errorf("expected empty string for negative width, got %q", spark)
	}
}

func TestSparkline_Width1(t *testing.T) {
	tt := NewThroughputTracker()
	tt.Add(10)
	spark := tt.Sparkline(1)
	if len([]rune(spark)) != 1 {
		t.Errorf("expected 1 rune for width=1, got %d runes", len([]rune(spark)))
	}
}

func TestSparkline_VeryLargeWidth(t *testing.T) {
	tt := NewThroughputTracker()
	tt.Add(10)
	spark := tt.Sparkline(10000)
	// Should clamp to bucketCount (60)
	runeCount := len([]rune(spark))
	if runeCount > 60 {
		t.Errorf("expected max 60 runes (bucketCount), got %d", runeCount)
	}
}

func TestSparkline_NoData(t *testing.T) {
	tt := NewThroughputTracker()
	spark := tt.Sparkline(20)
	// Should produce sparkline chars even with zero data (all lowest)
	if spark == "" {
		t.Error("expected non-empty sparkline even with no data")
	}
}

func TestCurrentRate_NoData(t *testing.T) {
	tt := NewThroughputTracker()
	rate := tt.CurrentRate()
	if rate != 0 {
		t.Errorf("expected rate 0 with no data, got %f", rate)
	}
}

func TestCurrentRate_WithData(t *testing.T) {
	tt := NewThroughputTracker()
	tt.Add(100)
	rate := tt.CurrentRate()
	// Should be > 0 since we just added tokens
	if rate <= 0 {
		t.Errorf("expected positive rate, got %f", rate)
	}
}

func TestRenderThroughput_Width0(t *testing.T) {
	tt := NewThroughputTracker()
	result := RenderThroughput(tt, 0)
	// Should not panic; sparkWidth clamps to 5 minimum
	if result == "" {
		t.Error("expected non-empty throughput render")
	}
}

func TestRenderThroughput_NarrowWidth(t *testing.T) {
	tt := NewThroughputTracker()
	result := RenderThroughput(tt, 10)
	if result == "" {
		t.Error("expected non-empty throughput render for narrow width")
	}
}

func TestRenderThroughput_WideWidth(t *testing.T) {
	tt := NewThroughputTracker()
	tt.Add(50)
	result := RenderThroughput(tt, 200)
	if !strings.Contains(result, "tok/s") {
		t.Error("expected 'tok/s' in throughput output")
	}
}

func TestThroughputTracker_ConcurrentAdd(t *testing.T) {
	tt := NewThroughputTracker()
	done := make(chan struct{})
	for i := 0; i < 10; i++ {
		go func() {
			for j := 0; j < 100; j++ {
				tt.Add(1)
			}
			done <- struct{}{}
		}()
	}
	for i := 0; i < 10; i++ {
		<-done
	}
	// Just verify no race condition crash
}

// =============================================================================
// RenderMessageFeed edge cases
// =============================================================================

func TestRenderMessageFeed_NegativeScrollPos(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "A", Content: "Hello", MessageType: "room", Step: 1, Location: "L"},
		},
		ScrollPos: -10,
		Height:    10,
		Width:     40,
	}
	result := RenderMessageFeed(d)
	if result == "" {
		t.Error("expected non-empty output for negative scroll")
	}
}

func TestRenderMessageFeed_ScrollBeyondEnd(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "A", Content: "Hello", Step: 1, Location: "L"},
		},
		ScrollPos: 99999,
		Height:    10,
		Width:     40,
	}
	result := RenderMessageFeed(d)
	// Should clamp to last line
	if result == "" {
		t.Error("expected non-empty output for scroll beyond end")
	}
}

func TestRenderMessageFeed_Width0(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "A", Content: "Hello", Step: 1, Location: "L"},
		},
		Height: 10,
		Width:  0,
	}
	result := RenderMessageFeed(d)
	// contentWidth clamps to 1
	if result == "" {
		t.Error("expected non-empty output for width=0")
	}
}

func TestRenderMessageFeed_Height0(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "A", Content: "Hello", Step: 1, Location: "L"},
		},
		Height: 0,
		Width:  40,
	}
	result := RenderMessageFeed(d)
	// With height 0, start:end slice is empty
	_ = result // no panic
}

func TestRenderMessageFeed_VeryLongContent(t *testing.T) {
	longContent := strings.Repeat("x", 10000)
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "A", Content: longContent, Step: 1, Location: "L"},
		},
		Height: 10,
		Width:  40,
	}
	result := RenderMessageFeed(d)
	// Content should be truncated (maxContentLen = contentWidth * 3)
	if result == "" {
		t.Error("expected non-empty output")
	}
}

func TestRenderMessageFeed_LocationGrouping(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "A", Content: "1", Step: 1, Location: "Shelter"},
			{AgentName: "B", Content: "2", Step: 1, Location: "Shelter"},
			{AgentName: "C", Content: "3", Step: 1, Location: "Bridge"},
		},
		Height: 30,
		Width:  80,
	}
	result := RenderMessageFeed(d)
	if !strings.Contains(result, "Shelter") {
		t.Error("expected Shelter location header")
	}
	if !strings.Contains(result, "Bridge") {
		t.Error("expected Bridge location header")
	}
}

func TestRenderMessageFeed_AllFilteredOut(t *testing.T) {
	d := MessageFeedData{
		Entries: []FeedEntry{
			{AgentName: "A", Content: "Hello", MessageType: "room", Step: 1, Location: "L"},
		},
		Filter: FilterMovement, // no movement messages
		Height: 10,
		Width:  40,
	}
	result := RenderMessageFeed(d)
	if !strings.Contains(result, "No messages matching filter") {
		t.Error("expected filter empty state message")
	}
}

// =============================================================================
// RenderAgentPane / truncateLines edge cases
// =============================================================================

func TestTruncateLines_Width0(t *testing.T) {
	result := truncateLines("hello world", 0, 5)
	if result != "" {
		t.Errorf("expected empty string for width=0, got %q", result)
	}
}

func TestTruncateLines_Width1(t *testing.T) {
	result := truncateLines("abc", 1, 10)
	// Each character becomes its own line
	lines := strings.Split(result, "\n")
	if len(lines) != 3 {
		t.Errorf("expected 3 lines for width=1, got %d: %q", len(lines), result)
	}
}

func TestTruncateLines_MaxLines0(t *testing.T) {
	result := truncateLines("hello", 10, 0)
	if result != "" {
		t.Errorf("expected empty string for maxLines=0, got %q", result)
	}
}

func TestTruncateLines_NegativeWidth(t *testing.T) {
	result := truncateLines("hello", -5, 5)
	if result != "" {
		t.Errorf("expected empty string for negative width, got %q", result)
	}
}

func TestTruncateLines_NegativeMaxLines(t *testing.T) {
	result := truncateLines("hello", 10, -1)
	if result != "" {
		t.Errorf("expected empty string for negative maxLines, got %q", result)
	}
}

func TestTruncateLines_EmptyText(t *testing.T) {
	result := truncateLines("", 10, 5)
	if result != "" {
		t.Errorf("expected empty string for empty text, got %q", result)
	}
}

func TestTruncateLines_ExactFit(t *testing.T) {
	result := truncateLines("hello", 5, 1)
	if result != "hello" {
		t.Errorf("expected 'hello', got %q", result)
	}
}

func TestTruncateLines_TailBehavior(t *testing.T) {
	// When text has more lines than maxLines, should show the tail
	result := truncateLines("line1\nline2\nline3\nline4", 20, 2)
	lines := strings.Split(result, "\n")
	if len(lines) != 2 {
		t.Fatalf("expected 2 lines, got %d", len(lines))
	}
	if lines[0] != "line3" || lines[1] != "line4" {
		t.Errorf("expected tail lines, got %v", lines)
	}
}

func TestTruncateLines_WrapAndTruncate(t *testing.T) {
	// Long single line gets wrapped, then truncated to maxLines
	text := strings.Repeat("x", 100)
	result := truncateLines(text, 10, 2)
	lines := strings.Split(result, "\n")
	if len(lines) != 2 {
		t.Errorf("expected 2 lines after wrap+truncate, got %d", len(lines))
	}
}

func TestRenderAgentPane_EmptyName(t *testing.T) {
	d := AgentPaneData{
		Name:   "",
		Active: false,
		Tokens: "some tokens",
		Step:   1,
	}
	result := RenderAgentPane(d, 40, 10)
	if result == "" {
		t.Error("expected non-empty pane even with empty name")
	}
}

func TestRenderAgentPane_VerySmallDimensions(t *testing.T) {
	d := AgentPaneData{
		Name:   "Maria",
		Active: true,
		Tokens: "Hello world this is a long token stream",
		Step:   5,
	}
	// Very small dimensions: bodyHeight and bodyWidth clamp to 1
	result := RenderAgentPane(d, 3, 3)
	if result == "" {
		t.Error("expected non-empty pane even at tiny size")
	}
}

func TestRenderAgentPane_Width0(t *testing.T) {
	d := AgentPaneData{Name: "A", Step: 1}
	result := RenderAgentPane(d, 0, 10)
	_ = result // no panic
}

func TestRenderAgentPane_VeryLongPlanGoal(t *testing.T) {
	d := AgentPaneData{
		Name:       "Maria",
		Occupation: "Nurse",
		PlanGoal:   strings.Repeat("Long goal text ", 50),
		Step:       1,
	}
	result := RenderAgentPane(d, 40, 15)
	if result == "" {
		t.Error("expected non-empty pane with long plan goal")
	}
}

// =============================================================================
// RenderBarChart edge cases
// =============================================================================

func TestRenderBarChart_NegativeValues(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "Neg", Value: -5, Max: 100},
	}
	result := RenderBarChart(entries, 80)
	// Negative value: ratio becomes negative, int() truncates to 0 filled
	if result == "" {
		t.Error("expected non-empty output for negative values")
	}
}

func TestRenderBarChart_ZeroMax(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "Zero", Value: 50, Max: 0},
	}
	result := RenderBarChart(entries, 80)
	// Max=0 guard: ratio stays 0
	if result == "" {
		t.Error("expected non-empty output for zero max")
	}
}

func TestRenderBarChart_ValueExceedsMax(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "Over", Value: 200, Max: 100},
	}
	result := RenderBarChart(entries, 80)
	// ratio clamps to 1
	if !strings.Contains(result, "100%") {
		t.Error("expected 100% for value exceeding max")
	}
}

func TestRenderBarChart_NarrowWidth(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "A", Value: 50, Max: 100},
	}
	result := RenderBarChart(entries, 5)
	// barWidth clamps to 4
	if result == "" {
		t.Error("expected non-empty output for narrow width")
	}
}

func TestRenderBarChart_Width0(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "A", Value: 50, Max: 100},
	}
	result := RenderBarChart(entries, 0)
	// barWidth clamps to 4
	if result == "" {
		t.Error("expected non-empty output for width=0")
	}
}

func TestRenderBarChart_NegativeWidth(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "A", Value: 50, Max: 100},
	}
	result := RenderBarChart(entries, -10)
	if result == "" {
		t.Error("expected non-empty output for negative width")
	}
}

func TestRenderBarChart_LongLabel(t *testing.T) {
	entries := []BarChartEntry{
		{Label: strings.Repeat("x", 50), Value: 50, Max: 100},
	}
	result := RenderBarChart(entries, 80)
	// Label should be truncated to 20 chars
	if result == "" {
		t.Error("expected non-empty output for long label")
	}
}

func TestRenderBarChart_ManyEntries(t *testing.T) {
	var entries []BarChartEntry
	for i := 0; i < 100; i++ {
		entries = append(entries, BarChartEntry{Label: "Item", Value: float64(i), Max: 100})
	}
	result := RenderBarChart(entries, 80)
	lines := strings.Split(strings.TrimRight(result, "\n"), "\n")
	if len(lines) != 100 {
		t.Errorf("expected 100 lines, got %d", len(lines))
	}
}

func TestRenderBarChart_AllZeroValues(t *testing.T) {
	entries := []BarChartEntry{
		{Label: "A", Value: 0, Max: 100},
		{Label: "B", Value: 0, Max: 100},
	}
	result := RenderBarChart(entries, 80)
	if result == "" {
		t.Error("expected non-empty output")
	}
}

// =============================================================================
// RenderSpatialMap edge cases
// =============================================================================

func TestRenderSpatialMap_EmptyLocations(t *testing.T) {
	data := SpatialMapData{Locations: []MapLocation{}}
	out := RenderSpatialMap(data)
	if !strings.Contains(out, "No locations") {
		t.Error("expected empty-state message for empty locations slice")
	}
}

func TestRenderSpatialMap_LocationNoAgents(t *testing.T) {
	data := SpatialMapData{
		Locations: []MapLocation{
			{Name: "Empty Place", Agents: nil},
		},
	}
	out := RenderSpatialMap(data)
	if !strings.Contains(out, "Empty Place") {
		t.Error("expected location name in output")
	}
	if !strings.Contains(out, "[0]") {
		t.Error("expected [0] agent count")
	}
}

func TestRenderSpatialMap_TravelProgressBounds(t *testing.T) {
	data := SpatialMapData{
		Locations: []MapLocation{{Name: "A"}, {Name: "B"}},
		Travels: []MapTravel{
			{AgentName: "X", From: "A", To: "B", Progress: -0.5},
			{AgentName: "Y", From: "A", To: "B", Progress: 1.5},
			{AgentName: "Z", From: "A", To: "B", Progress: 0.0},
		},
	}
	out := RenderSpatialMap(data)
	// Should not panic with out-of-range progress values
	if !strings.Contains(out, "IN TRANSIT") {
		t.Error("expected IN TRANSIT section")
	}
}

func TestRenderSpatialMap_SortedLocations(t *testing.T) {
	data := SpatialMapData{
		Locations: []MapLocation{
			{Name: "Zoo"},
			{Name: "Airport"},
			{Name: "Market"},
		},
	}
	out := RenderSpatialMap(data)
	airportIdx := strings.Index(out, "Airport")
	marketIdx := strings.Index(out, "Market")
	zooIdx := strings.Index(out, "Zoo")
	if airportIdx > marketIdx || marketIdx > zooIdx {
		t.Error("locations should be sorted alphabetically")
	}
}

// =============================================================================
// RenderHazardGauge edge cases
// =============================================================================

func TestRenderHazardGauge_ValueGreaterThan10(t *testing.T) {
	// level is on 0-10 scale, normalized to 0-1
	out := renderHazardGauge(15.0, 40)
	// Should clamp to 100%
	if !strings.Contains(out, "100%") {
		t.Error("expected 100% for hazard > 10")
	}
}

func TestRenderHazardGauge_NegativeValue(t *testing.T) {
	out := renderHazardGauge(-5.0, 40)
	// Should clamp to 0%
	if !strings.Contains(out, "0%") {
		t.Error("expected 0% for negative hazard")
	}
}

func TestRenderHazardGauge_Zero(t *testing.T) {
	out := renderHazardGauge(0.0, 40)
	if !strings.Contains(out, "0%") {
		t.Error("expected 0% for zero hazard")
	}
}

func TestRenderHazardGauge_MaxValue(t *testing.T) {
	out := renderHazardGauge(10.0, 40)
	if !strings.Contains(out, "100%") {
		t.Error("expected 100% for max hazard")
	}
}

func TestRenderHazardGauge_NarrowWidth(t *testing.T) {
	// Width < 10 gets clamped to 10
	out := renderHazardGauge(5.0, 3)
	if out == "" {
		t.Error("expected non-empty gauge for narrow width")
	}
}

func TestRenderHazardGauge_Width0(t *testing.T) {
	out := renderHazardGauge(5.0, 0)
	// Width gets clamped to 10
	if out == "" {
		t.Error("expected non-empty gauge for width=0")
	}
}

func TestRenderHazardGauge_NegativeWidth(t *testing.T) {
	out := renderHazardGauge(5.0, -10)
	// Width gets clamped to 10
	if out == "" {
		t.Error("expected non-empty gauge for negative width")
	}
}

func TestRenderWorldState_Full(t *testing.T) {
	data := WorldStateData{
		HazardLevel: 7.0,
		Locations: []LocationInfo{
			{Name: "Shelter", AgentNames: []string{"Maria", "Kenji"}},
			{Name: "Bridge", AgentNames: nil},
		},
		Width: 80,
	}
	out := RenderWorldState(data)
	if !strings.Contains(out, "Hazard") {
		t.Error("expected Hazard gauge")
	}
	if !strings.Contains(out, "Shelter") {
		t.Error("expected Shelter location")
	}
	if !strings.Contains(out, "Maria") {
		t.Error("expected Maria in agent list")
	}
}

func TestRenderWorldState_NoLocations(t *testing.T) {
	data := WorldStateData{HazardLevel: 0, Width: 80}
	out := RenderWorldState(data)
	if !strings.Contains(out, "Locations") {
		t.Error("expected Locations header")
	}
}

// =============================================================================
// RenderStatusBar edge cases
// =============================================================================

func TestRenderStatusBar_Width0(t *testing.T) {
	d := StatusBarData{
		Connected: true,
		RunStatus: "running",
		Step:      5,
		MaxSteps:  50,
	}
	result := RenderStatusBar(d, 0)
	_ = result // no panic
}

func TestRenderStatusBar_NarrowWidth(t *testing.T) {
	d := StatusBarData{
		Connected: true,
		RunStatus: "running",
		Step:      5,
		MaxSteps:  50,
		Hints:     []KeyHint{{Key: "q", Desc: "quit"}},
	}
	result := RenderStatusBar(d, 10)
	// gap1 and gap2 clamp to 1
	if result == "" {
		t.Error("expected non-empty status bar")
	}
}

func TestRenderStatusBar_Disconnected(t *testing.T) {
	d := StatusBarData{
		Connected: false,
		RunStatus: "error",
	}
	result := RenderStatusBar(d, 80)
	if result == "" {
		t.Error("expected non-empty status bar when disconnected")
	}
}

func TestRenderStatusBar_WithPanelAndFilter(t *testing.T) {
	d := StatusBarData{
		Connected:  true,
		RunStatus:  "running",
		PanelName:  "Map",
		FilterName: "Speech",
		Step:       3,
		MaxSteps:   20,
	}
	result := RenderStatusBar(d, 120)
	if !strings.Contains(result, "Map") {
		t.Error("expected panel name in status bar")
	}
	if !strings.Contains(result, "Speech") {
		t.Error("expected filter name in status bar")
	}
}

func TestRenderStatusBar_FilterAll_Hidden(t *testing.T) {
	d := StatusBarData{
		Connected:  true,
		RunStatus:  "running",
		FilterName: "All",
	}
	result := RenderStatusBar(d, 80)
	if strings.Contains(result, "filter:All") {
		t.Error("filter 'All' should be hidden")
	}
}

func TestRenderStatusBar_GapCalculation_WideEnough(t *testing.T) {
	d := StatusBarData{
		Connected: true,
		RunStatus: "running",
		Step:      10,
		MaxSteps:  100,
		TokPerSec: 42.5,
		Hints: []KeyHint{
			{Key: "Tab", Desc: "panel"},
			{Key: "q", Desc: "back"},
		},
	}
	result := RenderStatusBar(d, 200)
	// Should have proper spacing
	if result == "" {
		t.Error("expected non-empty status bar")
	}
}

func TestRenderStatusBar_EmptyHints(t *testing.T) {
	d := StatusBarData{
		Connected: true,
		RunStatus: "idle",
		Hints:     nil,
	}
	result := RenderStatusBar(d, 80)
	if result == "" {
		t.Error("expected non-empty status bar with no hints")
	}
}

func TestRenderStatusBar_AllStatuses(t *testing.T) {
	statuses := []string{"active", "generating", "running", "completed", "error", "failed", "idle", "paused", "stopped", "unknown", ""}
	for _, status := range statuses {
		d := StatusBarData{Connected: true, RunStatus: status}
		result := RenderStatusBar(d, 80)
		if result == "" {
			t.Errorf("expected non-empty status bar for status %q", status)
		}
	}
}
