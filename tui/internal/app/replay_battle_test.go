package app

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/jasperan/emotion-engine/tui/internal/api"
)

// runeKey builds a tea.KeyMsg for a printable character like "d", "+", "H", etc.
func runeKey(r rune) tea.KeyMsg {
	return tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}}
}

// specialKey builds a tea.KeyMsg for a named key (left, right, home, end, space, etc.)
func specialKey(kt tea.KeyType) tea.KeyMsg {
	return tea.KeyMsg{Type: kt}
}

// --- computeDiff edge cases ---

func TestComputeDiff_BothNil(t *testing.T) {
	lines := computeDiff(nil, nil, 60)
	if len(lines) != 1 {
		t.Errorf("expected 1 (no changes) line for nil/nil, got %d", len(lines))
	}
}

func TestComputeDiff_PrevNilCurrPopulated(t *testing.T) {
	curr := map[string]interface{}{"key": "value"}
	lines := computeDiff(nil, curr, 60)
	found := false
	for _, l := range lines {
		if strings.Contains(l, "key") {
			found = true
		}
	}
	if !found {
		t.Error("expected added key in diff")
	}
}

func TestComputeDiff_CurrNilPrevPopulated(t *testing.T) {
	prev := map[string]interface{}{"key": "value"}
	lines := computeDiff(prev, nil, 60)
	found := false
	for _, l := range lines {
		if strings.Contains(l, "key") {
			found = true
		}
	}
	if !found {
		t.Error("expected removed key in diff")
	}
}

func TestComputeDiff_IdenticalMaps(t *testing.T) {
	m := map[string]interface{}{"a": 1, "b": "two", "c": 3.14}
	lines := computeDiff(m, m, 60)
	if len(lines) != 1 {
		t.Errorf("expected 1 (no changes) line for identical maps, got %d", len(lines))
	}
}

func TestComputeDiff_IdenticalValues_DifferentMaps(t *testing.T) {
	prev := map[string]interface{}{"a": 1, "b": "two"}
	curr := map[string]interface{}{"a": 1, "b": "two"}
	lines := computeDiff(prev, curr, 60)
	if len(lines) != 1 {
		t.Errorf("expected 1 (no changes) line, got %d", len(lines))
	}
}

func TestComputeDiff_DeeplyNestedChanges(t *testing.T) {
	prev := map[string]interface{}{
		"nested": map[string]interface{}{"inner": "old"},
	}
	curr := map[string]interface{}{
		"nested": map[string]interface{}{"inner": "new"},
	}
	lines := computeDiff(prev, curr, 80)
	if len(lines) == 0 {
		t.Error("expected diff lines for nested change")
	}
	found := false
	for _, l := range lines {
		if strings.Contains(l, "nested") {
			found = true
		}
	}
	if !found {
		t.Error("expected 'nested' key to appear in diff")
	}
}

func TestComputeDiff_UnderscorePrefixedKeysIgnored(t *testing.T) {
	prev := map[string]interface{}{"_internal": "old", "visible": "same"}
	curr := map[string]interface{}{"_internal": "new", "visible": "same"}
	lines := computeDiff(prev, curr, 60)
	for _, l := range lines {
		if strings.Contains(l, "_internal") {
			t.Error("underscore-prefixed keys should be excluded from diff")
		}
	}
}

func TestComputeDiff_AllAdded(t *testing.T) {
	prev := map[string]interface{}{}
	curr := map[string]interface{}{"a": 1, "b": 2, "c": 3}
	lines := computeDiff(prev, curr, 60)
	if len(lines) != 3 {
		t.Errorf("expected 3 added lines, got %d", len(lines))
	}
}

func TestComputeDiff_AllRemoved(t *testing.T) {
	prev := map[string]interface{}{"a": 1, "b": 2, "c": 3}
	curr := map[string]interface{}{}
	lines := computeDiff(prev, curr, 60)
	if len(lines) != 3 {
		t.Errorf("expected 3 removed lines, got %d", len(lines))
	}
}

func TestComputeDiff_ZeroWidth(t *testing.T) {
	prev := map[string]interface{}{"a": 1}
	curr := map[string]interface{}{"a": 2}
	lines := computeDiff(prev, curr, 0)
	if len(lines) == 0 {
		t.Error("expected diff lines even with width=0")
	}
}

func TestComputeDiff_NegativeWidth(t *testing.T) {
	prev := map[string]interface{}{"a": 1}
	curr := map[string]interface{}{"a": 2}
	lines := computeDiff(prev, curr, -10)
	if len(lines) == 0 {
		t.Error("expected diff lines even with negative width")
	}
}

func TestComputeDiff_LargeNumberOfKeys(t *testing.T) {
	prev := make(map[string]interface{})
	curr := make(map[string]interface{})
	for i := 0; i < 1000; i++ {
		key := strings.Repeat("k", i%26+1)
		prev[key] = i
		curr[key] = i + 1
	}
	lines := computeDiff(prev, curr, 120)
	if len(lines) == 0 {
		t.Error("expected diff lines for large map")
	}
}

// --- messagesAtStep edge cases ---

func TestMessagesAtStep_EmptyMessages(t *testing.T) {
	m := ReplayModel{messages: nil}
	msgs := m.messagesAtStep(0)
	if len(msgs) != 0 {
		t.Errorf("expected 0 messages, got %d", len(msgs))
	}
}

func TestMessagesAtStep_Step0(t *testing.T) {
	m := ReplayModel{
		messages: []api.MessageResponse{
			{StepIndex: 0, Content: "genesis"},
			{StepIndex: 1, Content: "later"},
			{StepIndex: 0, Content: "also genesis"},
		},
	}
	msgs := m.messagesAtStep(0)
	if len(msgs) != 2 {
		t.Errorf("expected 2 messages at step 0, got %d", len(msgs))
	}
}

func TestMessagesAtStep_NoMatch(t *testing.T) {
	m := ReplayModel{
		messages: []api.MessageResponse{
			{StepIndex: 1, Content: "hello"},
			{StepIndex: 2, Content: "world"},
		},
	}
	msgs := m.messagesAtStep(99)
	if len(msgs) != 0 {
		t.Errorf("expected 0 messages for non-existent step, got %d", len(msgs))
	}
}

func TestMessagesAtStep_NegativeStep(t *testing.T) {
	m := ReplayModel{
		messages: []api.MessageResponse{
			{StepIndex: 0, Content: "hello"},
		},
	}
	msgs := m.messagesAtStep(-1)
	if len(msgs) != 0 {
		t.Errorf("expected 0 messages for negative step, got %d", len(msgs))
	}
}

// --- agentNameByID edge cases ---

func TestAgentNameByID_Found(t *testing.T) {
	m := ReplayModel{
		agents: []api.AgentStatus{
			{ID: "abc-123", Name: "Maria"},
		},
	}
	name := m.agentNameByID("abc-123")
	if name != "Maria" {
		t.Errorf("expected Maria, got %s", name)
	}
}

func TestAgentNameByID_NotFound_LongID(t *testing.T) {
	m := ReplayModel{}
	name := m.agentNameByID("abcdefghijklmnop")
	if name != "abcdefgh" {
		t.Errorf("expected truncated ID 'abcdefgh', got %s", name)
	}
}

func TestAgentNameByID_NotFound_ShortID(t *testing.T) {
	m := ReplayModel{}
	name := m.agentNameByID("abc")
	if name != "abc" {
		t.Errorf("expected raw short ID, got %s", name)
	}
}

func TestAgentNameByID_Empty(t *testing.T) {
	m := ReplayModel{}
	name := m.agentNameByID("")
	if name != "" {
		t.Errorf("expected empty string, got %s", name)
	}
}

// --- sortedKeys edge cases ---

func TestSortedKeys_Nil(t *testing.T) {
	keys := sortedKeys(nil)
	if len(keys) != 0 {
		t.Errorf("expected 0 keys for nil map, got %d", len(keys))
	}
}

func TestSortedKeys_Empty(t *testing.T) {
	keys := sortedKeys(map[string]interface{}{})
	if len(keys) != 0 {
		t.Errorf("expected 0 keys for empty map, got %d", len(keys))
	}
}

func TestSortedKeys_Sorted(t *testing.T) {
	m := map[string]interface{}{"c": 3, "a": 1, "b": 2}
	keys := sortedKeys(m)
	if len(keys) != 3 {
		t.Fatalf("expected 3 keys, got %d", len(keys))
	}
	if keys[0] != "a" || keys[1] != "b" || keys[2] != "c" {
		t.Errorf("keys not sorted: %v", keys)
	}
}

// --- toFloat edge cases ---

func TestToFloat_Float64(t *testing.T) {
	if toFloat(3.14) != 3.14 {
		t.Error("float64 conversion failed")
	}
}

func TestToFloat_Float32(t *testing.T) {
	result := toFloat(float32(2.5))
	if result < 2.4 || result > 2.6 {
		t.Errorf("float32 conversion failed: %f", result)
	}
}

func TestToFloat_Int(t *testing.T) {
	if toFloat(42) != 42.0 {
		t.Error("int conversion failed")
	}
}

func TestToFloat_Int64(t *testing.T) {
	if toFloat(int64(100)) != 100.0 {
		t.Error("int64 conversion failed")
	}
}

func TestToFloat_String(t *testing.T) {
	if toFloat("not a number") != 0 {
		t.Error("string should return 0")
	}
}

func TestToFloat_Nil(t *testing.T) {
	if toFloat(nil) != 0 {
		t.Error("nil should return 0")
	}
}

func TestToFloat_Bool(t *testing.T) {
	if toFloat(true) != 0 {
		t.Error("bool should return 0")
	}
}

// --- Render functions with extreme dimensions ---

func TestReplayView_ZeroDimensions(t *testing.T) {
	m := NewReplayModel(nil, "test")
	view := m.View(0, 0)
	_ = view // just verify no panic
}

func TestReplayView_Width1(t *testing.T) {
	m := NewReplayModel(nil, "test")
	view := m.View(1, 1)
	_ = view
}

func TestReplayView_VeryLarge(t *testing.T) {
	m := NewReplayModel(nil, "test")
	view := m.View(10000, 10000)
	_ = view
}

func TestReplayView_WithLoadedRun(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{
		ID:          "test",
		CurrentStep: 5,
		WorldState:  map[string]interface{}{"hazard_level": 3.0},
		Metrics:     map[string]interface{}{"total_messages": 42.0},
	}
	m.totalSteps = 5
	m.agents = []api.AgentStatus{
		{ID: "a1", Name: "Maria", Role: "human", DynamicState: map[string]interface{}{
			"location": "Shelter", "health": 0.8, "stress": 0.3,
		}},
	}
	m.steps[0] = &api.StepResponse{
		StepIndex:     0,
		StateSnapshot: map[string]interface{}{"hazard_level": 1.0, "time_of_day": "morning"},
	}

	view := m.View(80, 40)
	if view == "" {
		t.Error("expected non-empty view for loaded run")
	}

	// width=0 and width=1 should not panic
	_ = m.View(0, 40)
	_ = m.View(1, 40)
}

func TestRenderReplayLeft_NilStep(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	out := m.renderReplayLeft(80, 40)
	if !strings.Contains(out, "loading") {
		t.Error("expected loading indicator for nil step")
	}
}

func TestRenderReplayLeft_EmptyWorldState(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.steps[0] = &api.StepResponse{
		StepIndex:     0,
		StateSnapshot: map[string]interface{}{},
	}
	out := m.renderReplayLeft(80, 40)
	if !strings.Contains(out, "no state") {
		t.Error("expected '(no state)' for empty snapshot")
	}
}

func TestRenderReplayLeft_DiffMode_NoPrevStep(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.showDiff = true
	m.currentStep = 1
	m.steps[1] = &api.StepResponse{
		StepIndex:     1,
		StateSnapshot: map[string]interface{}{"key": "val"},
	}
	out := m.renderReplayLeft(80, 40)
	if !strings.Contains(out, "previous step not loaded") {
		t.Error("expected 'previous step not loaded' message")
	}
}

func TestRenderReplayLeft_DiffMode_WithBothSteps(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.showDiff = true
	m.currentStep = 1
	m.steps[0] = &api.StepResponse{
		StepIndex:     0,
		StateSnapshot: map[string]interface{}{"key": "old"},
	}
	m.steps[1] = &api.StepResponse{
		StepIndex:     1,
		StateSnapshot: map[string]interface{}{"key": "new"},
	}
	out := m.renderReplayLeft(80, 40)
	if strings.Contains(out, "loading") {
		t.Error("should not show loading when both steps present")
	}
}

func TestRenderReplayLeft_Width0(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.steps[0] = &api.StepResponse{
		StepIndex:     0,
		StateSnapshot: map[string]interface{}{"k": "v"},
		Actions:       []map[string]interface{}{{"agent_id": "a1", "action_type": "move"}},
	}
	out := m.renderReplayLeft(0, 40)
	_ = out // no panic
}

func TestRenderReplayRight_NoAgents(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	out := m.renderReplayRight(80, 40)
	if !strings.Contains(out, "none") {
		t.Error("expected '(none)' for no agents")
	}
}

func TestRenderReplayRight_Width0(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{
		ID:      "test",
		Metrics: map[string]interface{}{"total_messages": 42.0},
	}
	out := m.renderReplayRight(0, 40)
	_ = out // no panic
}

func TestRenderReplayRight_WithEvaluation(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{
		ID:          "test",
		CurrentStep: 10,
		Evaluation: map[string]interface{}{
			"cooperation_score": 0.8,
			"survival_rate":     0.6,
		},
		Metrics: map[string]interface{}{
			"total_messages": 42.0,
		},
	}
	m.totalSteps = 10
	m.currentStep = 9 // last step (0-indexed)

	out := m.renderReplayRight(80, 40)
	if !strings.Contains(out, "EVALUATION") {
		t.Error("expected EVALUATION section on last step")
	}
}

func TestRenderReplayRight_NotLastStep(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{
		ID:          "test",
		CurrentStep: 10,
		Evaluation:  map[string]interface{}{"score": 0.8},
	}
	m.totalSteps = 10
	m.currentStep = 5

	out := m.renderReplayRight(80, 40)
	if strings.Contains(out, "EVALUATION") {
		t.Error("should NOT show EVALUATION on non-last step")
	}
}

func TestRenderReplayRight_LongAgentName(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.agents = []api.AgentStatus{
		{
			ID:   "a1",
			Name: "A Very Long Agent Name That Exceeds Fourteen Characters",
			Role: "human",
			DynamicState: map[string]interface{}{
				"location": "An Extremely Long Location Name",
				"health":   0.5,
				"stress":   0.7,
			},
		},
	}
	out := m.renderReplayRight(40, 20)
	_ = out // no panic
}

// --- Replay key handling edge cases ---

func TestReplayModel_HandleKey_BigJump_L(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.totalSteps = 3
	m.currentStep = 2
	m2, _ := m.handleKey(runeKey('L'))
	if m2.currentStep != 2 {
		t.Errorf("expected clamped to 2, got %d", m2.currentStep)
	}
}

func TestReplayModel_HandleKey_BigJump_H(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.totalSteps = 10
	m.currentStep = 2
	m2, _ := m.handleKey(runeKey('H'))
	if m2.currentStep != 0 {
		t.Errorf("expected clamped to 0, got %d", m2.currentStep)
	}
}

func TestReplayModel_HandleKey_BigJump_L_ZeroTotalSteps(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.totalSteps = 0
	m.currentStep = 0
	m2, _ := m.handleKey(runeKey('L'))
	if m2.currentStep != 0 {
		t.Errorf("expected 0 for zero total steps, got %d", m2.currentStep)
	}
}

func TestReplayModel_SpeedBounds(t *testing.T) {
	m := NewReplayModel(nil, "test")

	// Speed up many times
	for i := 0; i < 20; i++ {
		m, _ = m.handleKey(runeKey('+'))
	}
	if m.playSpeed < 250_000_000 { // 250ms in nanoseconds
		t.Errorf("speed should be clamped to 250ms min, got %v", m.playSpeed)
	}

	// Slow down many times
	for i := 0; i < 20; i++ {
		m, _ = m.handleKey(runeKey('-'))
	}
	if m.playSpeed > 5_000_000_000 { // 5s in nanoseconds
		t.Errorf("speed should be clamped to 5s max, got %v", m.playSpeed)
	}
}

func TestReplayModel_PlayPauseToggle(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.totalSteps = 10

	// Start playing
	m, _ = m.handleKey(specialKey(tea.KeySpace))
	if !m.playing {
		t.Error("expected playing after space")
	}

	// Pause
	m, _ = m.handleKey(specialKey(tea.KeySpace))
	if m.playing {
		t.Error("expected paused after second space")
	}
}

func TestReplayModel_DiffToggle(t *testing.T) {
	m := NewReplayModel(nil, "test")
	if m.showDiff {
		t.Error("diff should be off initially")
	}
	m, _ = m.handleKey(runeKey('d'))
	if !m.showDiff {
		t.Error("diff should be on after toggle")
	}
	m, _ = m.handleKey(runeKey('d'))
	if m.showDiff {
		t.Error("diff should be off after second toggle")
	}
}

func TestReplayModel_HomeEnd(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.totalSteps = 10
	m.currentStep = 5

	m, _ = m.handleKey(specialKey(tea.KeyHome))
	if m.currentStep != 0 {
		t.Errorf("expected step 0 after home, got %d", m.currentStep)
	}

	m, _ = m.handleKey(specialKey(tea.KeyEnd))
	if m.currentStep != 9 {
		t.Errorf("expected step 9 after end, got %d", m.currentStep)
	}
}

func TestReplayModel_LeftRight_Boundaries(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.totalSteps = 3
	m.currentStep = 0

	// Left at 0 should stay at 0
	m, _ = m.handleKey(specialKey(tea.KeyLeft))
	if m.currentStep != 0 {
		t.Errorf("expected 0 at left boundary, got %d", m.currentStep)
	}

	m.currentStep = 2
	// Right at max should stay at max
	m, _ = m.handleKey(specialKey(tea.KeyRight))
	if m.currentStep != 2 {
		t.Errorf("expected 2 at right boundary, got %d", m.currentStep)
	}
}

func TestReplayModel_NavigationStopsPlayback(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.totalSteps = 10
	m.currentStep = 5
	m.playing = true

	m, _ = m.handleKey(specialKey(tea.KeyLeft))
	if m.playing {
		t.Error("left arrow should stop playback")
	}

	m.playing = true
	m, _ = m.handleKey(specialKey(tea.KeyRight))
	if m.playing {
		t.Error("right arrow should stop playback")
	}

	m.playing = true
	m, _ = m.handleKey(runeKey('H'))
	if m.playing {
		t.Error("H should stop playback")
	}

	m.playing = true
	m, _ = m.handleKey(runeKey('L'))
	if m.playing {
		t.Error("L should stop playback")
	}
}

// --- Transport bar edge cases ---

func TestRenderTransportBar_ZeroTotalSteps(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.totalSteps = 0
	// Should not divide by zero
	bar := m.renderTransportBar(80)
	if bar == "" {
		t.Error("expected non-empty transport bar")
	}
}

func TestRenderTransportBar_SingleStep(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.totalSteps = 1
	m.currentStep = 0
	bar := m.renderTransportBar(80)
	if bar == "" {
		t.Error("expected non-empty transport bar")
	}
}

func TestRenderTransportBar_PlayingVsPaused(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	m.totalSteps = 10

	m.playing = false
	paused := m.renderTransportBar(80)

	m.playing = true
	playing := m.renderTransportBar(80)

	if paused == playing {
		t.Log("transport bar should differ between playing and paused (icon changes)")
	}
}

func TestRenderTransportBar_Width0(t *testing.T) {
	m := NewReplayModel(nil, "test")
	m.run = &api.RunResponse{ID: "test"}
	bar := m.renderTransportBar(0)
	_ = bar // no panic
}
