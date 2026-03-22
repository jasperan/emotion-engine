package app

import (
	"testing"

	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/components"
)

// --- handleWSEvent edge cases ---

func newTestDashboard() *DashboardModel {
	tp := components.NewThroughputTracker()
	m := NewDashboardModel(nil, tp, false, "test-run")
	m.run = &api.RunResponse{
		ID:         "test-run",
		Status:     "running",
		WorldState: map[string]interface{}{},
	}
	m.agents = []api.AgentStatus{
		{ID: "agent-1", Name: "Maria"},
		{ID: "agent-2", Name: "Kenji"},
	}
	m.streams["agent-1"] = &agentStream{name: "Maria"}
	m.streams["agent-2"] = &agentStream{name: "Kenji"}
	return &m
}

func TestHandleWSEvent_EmptyEventType(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "", Data: map[string]interface{}{}}
	// Should not panic on empty event
	m.handleWSEvent(evt)
}

func TestHandleWSEvent_UnknownEventType(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "totally_made_up_event", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	// No panic expected
}

func TestHandleWSEvent_TokenStream_MissingFields(t *testing.T) {
	m := newTestDashboard()
	// No agent_id, no tokens
	evt := api.WSMessage{Event: "token_stream", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)

	// Streams should be unchanged
	if m.streams["agent-1"].active {
		t.Error("stream should not be active without matching agent_id")
	}
}

func TestHandleWSEvent_TokenStream_NilData(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "token_stream", Data: nil}
	// Should not panic on nil data
	m.handleWSEvent(evt)
}

func TestHandleWSEvent_TokenStream_WrongTypes(t *testing.T) {
	m := newTestDashboard()
	// agent_id as int instead of string
	evt := api.WSMessage{Event: "token_stream", Data: map[string]interface{}{
		"agent_id": 12345,
		"tokens":   99999, // int instead of string
	}}
	m.handleWSEvent(evt)
	// Type assertion to string fails silently; no panic
}

func TestHandleWSEvent_TokenStream_FallbackToSingularToken(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "token_stream", Data: map[string]interface{}{
		"agent_id": "agent-1",
		"token":    "hello", // singular field (no "tokens")
	}}
	m.handleWSEvent(evt)
	if !m.streams["agent-1"].active {
		t.Error("stream should be active after token")
	}
	if m.streams["agent-1"].tokens.String() != "hello" {
		t.Errorf("expected 'hello', got %q", m.streams["agent-1"].tokens.String())
	}
}

func TestHandleWSEvent_TokenStream_PluralTokensPreferred(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "token_stream", Data: map[string]interface{}{
		"agent_id": "agent-1",
		"tokens":   "batch",
		"token":    "single",
	}}
	m.handleWSEvent(evt)
	// "tokens" (plural) should be preferred
	if m.streams["agent-1"].tokens.String() != "batch" {
		t.Errorf("expected 'batch', got %q", m.streams["agent-1"].tokens.String())
	}
}

func TestHandleWSEvent_TokenDone_MissingFields(t *testing.T) {
	m := newTestDashboard()
	m.streams["agent-1"].active = true
	evt := api.WSMessage{Event: "token_done", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	// agent-1 should still be active (agent_id didn't match)
	if !m.streams["agent-1"].active {
		t.Error("stream should still be active when agent_id missing")
	}
}

func TestHandleWSEvent_TokenDone_LatencyAsString(t *testing.T) {
	m := newTestDashboard()
	m.streams["agent-1"].active = true
	// latency_ms sent as string instead of float64
	evt := api.WSMessage{Event: "token_done", Data: map[string]interface{}{
		"agent_id":   "agent-1",
		"latency_ms": "500",
	}}
	m.handleWSEvent(evt)
	if m.streams["agent-1"].active {
		t.Error("stream should be inactive after token_done")
	}
	// latency_ms type assertion will fail, default to 0
	if m.streams["agent-1"].latencyMs != 0 {
		t.Errorf("expected latency 0 (string type assertion fails), got %d", m.streams["agent-1"].latencyMs)
	}
}

func TestHandleWSEvent_StepCompleted_MissingStep(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "step_completed", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	// Step should be 0 (default from failed type assertion)
	if m.run.CurrentStep != 0 {
		t.Errorf("expected step 0, got %d", m.run.CurrentStep)
	}
}

func TestHandleWSEvent_StepCompleted_StepAsString(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "step_completed", Data: map[string]interface{}{
		"step": "not_a_number",
	}}
	m.handleWSEvent(evt)
	// Type assertion to float64 fails, falls through to step_index which also fails
	if m.run.CurrentStep != 0 {
		t.Errorf("expected step 0, got %d", m.run.CurrentStep)
	}
}

func TestHandleWSEvent_StepCompleted_FallbackStepIndex(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "step_completed", Data: map[string]interface{}{
		"step_index": float64(7),
	}}
	m.handleWSEvent(evt)
	if m.run.CurrentStep != 7 {
		t.Errorf("expected step 7 from step_index fallback, got %d", m.run.CurrentStep)
	}
}

func TestHandleWSEvent_StepCompleted_WithWorldState(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "step_completed", Data: map[string]interface{}{
		"step": float64(3),
		"world_state": map[string]interface{}{
			"hazard_level": float64(5.0),
			"locations":    map[string]interface{}{"Shelter": map[string]interface{}{}},
		},
	}}
	m.handleWSEvent(evt)
	if m.run.CurrentStep != 3 {
		t.Errorf("expected step 3, got %d", m.run.CurrentStep)
	}
	if m.hazardLevel != 5.0 {
		t.Errorf("expected hazard 5.0, got %f", m.hazardLevel)
	}
}

func TestHandleWSEvent_StepCompleted_WorldStateNotMap(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "step_completed", Data: map[string]interface{}{
		"step":        float64(1),
		"world_state": "this_is_not_a_map",
	}}
	m.handleWSEvent(evt)
	// Should not crash, just skip world state update
	if m.run.CurrentStep != 1 {
		t.Errorf("expected step 1, got %d", m.run.CurrentStep)
	}
}

func TestHandleWSEvent_Message_MissingFields(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "message", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	if len(m.feedEntries) != 1 {
		t.Fatalf("expected 1 feed entry, got %d", len(m.feedEntries))
	}
	// Missing agent_name defaults to "System"
	if m.feedEntries[0].AgentName != "System" {
		t.Errorf("expected System default, got %q", m.feedEntries[0].AgentName)
	}
	// Missing message_type defaults to "message"
	if m.feedEntries[0].MessageType != "message" {
		t.Errorf("expected 'message' default, got %q", m.feedEntries[0].MessageType)
	}
}

func TestHandleWSEvent_Message_AllFields(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "message", Data: map[string]interface{}{
		"agent_name":   "Maria",
		"content":      "Help needed!",
		"message_type": "broadcast",
		"location":     "Town Square",
		"step_index":   float64(5),
	}}
	m.handleWSEvent(evt)
	if len(m.feedEntries) != 1 {
		t.Fatalf("expected 1 feed entry, got %d", len(m.feedEntries))
	}
	e := m.feedEntries[0]
	if e.AgentName != "Maria" {
		t.Errorf("wrong agent: %q", e.AgentName)
	}
	if e.Content != "Help needed!" {
		t.Errorf("wrong content: %q", e.Content)
	}
	if e.Location != "Town Square" {
		t.Errorf("wrong location: %q", e.Location)
	}
	if e.Step != 5 {
		t.Errorf("wrong step: %d", e.Step)
	}
}

func TestHandleWSEvent_SceneTurn_SameAsMessage(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "scene_turn", Data: map[string]interface{}{
		"agent_name": "Kenji",
		"content":    "I see water rising",
	}}
	m.handleWSEvent(evt)
	if len(m.feedEntries) != 1 {
		t.Fatalf("expected 1 feed entry, got %d", len(m.feedEntries))
	}
	if m.feedEntries[0].AgentName != "Kenji" {
		t.Errorf("wrong agent: %q", m.feedEntries[0].AgentName)
	}
}

func TestHandleWSEvent_FeedCap(t *testing.T) {
	m := newTestDashboard()
	for i := 0; i < 600; i++ {
		evt := api.WSMessage{Event: "message", Data: map[string]interface{}{
			"agent_name": "Spammer",
			"content":    "msg",
			"step_index": float64(i),
		}}
		m.handleWSEvent(evt)
	}
	if len(m.feedEntries) > 500 {
		t.Errorf("feed should be capped at 500, got %d", len(m.feedEntries))
	}
}

func TestHandleWSEvent_RunCompleted(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "run_completed", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	if m.run.Status != "completed" {
		t.Errorf("expected status 'completed', got %q", m.run.Status)
	}
}

func TestHandleWSEvent_RunStopped(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "run_stopped", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	if m.run.Status != "stopped" {
		t.Errorf("expected status 'stopped', got %q", m.run.Status)
	}
}

func TestHandleWSEvent_RunPaused(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "run_paused", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	if m.run.Status != "paused" {
		t.Errorf("expected status 'paused', got %q", m.run.Status)
	}
}

func TestHandleWSEvent_RunStarted(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "run_started", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	if m.run.Status != "started" {
		t.Errorf("expected status 'started', got %q", m.run.Status)
	}
}

func TestHandleWSEvent_RunStatus_NilRun(t *testing.T) {
	tp := components.NewThroughputTracker()
	m := NewDashboardModel(nil, tp, false, "test")
	// m.run is nil
	evt := api.WSMessage{Event: "run_completed", Data: map[string]interface{}{}}
	// Should not panic
	m.handleWSEvent(evt)
}

func TestHandleWSEvent_AgentMoved_MissingFields(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "agent_moved", Data: map[string]interface{}{}}
	m.handleWSEvent(evt)
	// Should not panic, creates a feed entry with empty values
	if len(m.feedEntries) != 1 {
		t.Errorf("expected 1 feed entry, got %d", len(m.feedEntries))
	}
}

func TestHandleWSEvent_ProposalCreated_NilProposal(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "proposal_created", Data: map[string]interface{}{
		"proposal": nil,
	}}
	// proposal.(map[string]interface{}) will fail, producing zero-value strings
	m.handleWSEvent(evt)
	// Should not panic
}

func TestHandleWSEvent_ProposalCreated_DescriptionFallback(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "proposal_created", Data: map[string]interface{}{
		"proposal": map[string]interface{}{
			"id":          "p1",
			"proposer":    "Maria",
			"target":      "Kenji",
			"description": "Share supplies",
			// no "terms" field
		},
		"step": float64(3),
	}}
	m.handleWSEvent(evt)
	if len(m.negotiations) != 1 {
		t.Fatalf("expected 1 negotiation, got %d", len(m.negotiations))
	}
	if m.negotiations[0].Terms != "Share supplies" {
		t.Errorf("expected description fallback, got %q", m.negotiations[0].Terms)
	}
}

func TestHandleWSEvent_VouchFor(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "vouch_for", Data: map[string]interface{}{
		"voucher": "Maria",
		"subject": "Kenji",
	}}
	m.handleWSEvent(evt)
	if len(m.relEdges) != 1 {
		t.Fatalf("expected 1 relationship edge, got %d", len(m.relEdges))
	}
	if m.relEdges[0].Label != "vouched" {
		t.Errorf("expected label 'vouched', got %q", m.relEdges[0].Label)
	}
}

func TestHandleWSEvent_LocationDiscovered(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "location_discovered", Data: map[string]interface{}{
		"location":     "Hidden Cave",
		"connected_to": "Riverside",
	}}
	m.handleWSEvent(evt)
	found := false
	for _, loc := range m.mapLocations {
		if loc.Name == "Hidden Cave" {
			found = true
			if len(loc.ConnectedTo) != 1 || loc.ConnectedTo[0] != "Riverside" {
				t.Errorf("wrong connections: %v", loc.ConnectedTo)
			}
		}
	}
	if !found {
		t.Error("expected Hidden Cave in map locations")
	}
}

func TestHandleWSEvent_EmotionContagion(t *testing.T) {
	m := newTestDashboard()
	evt := api.WSMessage{Event: "emotion_contagion", Data: map[string]interface{}{}}
	// Placeholder event; should not panic
	m.handleWSEvent(evt)
}

// --- safeFloat edge cases ---

func TestSafeFloat_Valid(t *testing.T) {
	data := map[string]interface{}{"step": float64(42)}
	if safeFloat(data, "step") != 42 {
		t.Error("expected 42")
	}
}

func TestSafeFloat_Missing(t *testing.T) {
	data := map[string]interface{}{}
	if safeFloat(data, "step") != 0 {
		t.Error("expected 0 for missing key")
	}
}

func TestSafeFloat_WrongType(t *testing.T) {
	data := map[string]interface{}{"step": "not_a_float"}
	if safeFloat(data, "step") != 0 {
		t.Error("expected 0 for wrong type")
	}
}

func TestSafeFloat_NilMap(t *testing.T) {
	// This would panic since the function doesn't check for nil map
	// Let's see if it does
	defer func() {
		if r := recover(); r != nil {
			t.Log("safeFloat panics on nil map (this is a known edge case)")
		}
	}()
	safeFloat(nil, "key")
}

// --- Dashboard helper method edge cases ---

func TestRemoveStr_Found(t *testing.T) {
	ss := []string{"a", "b", "c"}
	result := removeStr(ss, "b")
	if len(result) != 2 || result[0] != "a" || result[1] != "c" {
		t.Errorf("unexpected result: %v", result)
	}
}

func TestRemoveStr_NotFound(t *testing.T) {
	ss := []string{"a", "b", "c"}
	result := removeStr(ss, "z")
	if len(result) != 3 {
		t.Errorf("expected unchanged slice, got: %v", result)
	}
}

func TestRemoveStr_Empty(t *testing.T) {
	result := removeStr(nil, "z")
	if len(result) != 0 {
		t.Errorf("expected empty result, got: %v", result)
	}
}

func TestRemoveStr_Duplicate(t *testing.T) {
	ss := []string{"a", "b", "a", "c"}
	result := removeStr(ss, "a")
	// Should remove only the first occurrence
	if len(result) != 3 {
		t.Errorf("expected 3 elements, got: %v", result)
	}
}

func TestDashboard_AgentNameByID_Found(t *testing.T) {
	m := newTestDashboard()
	name := m.agentNameByID("agent-1")
	if name != "Maria" {
		t.Errorf("expected Maria, got %q", name)
	}
}

func TestDashboard_AgentNameByID_LongUnknown(t *testing.T) {
	m := newTestDashboard()
	name := m.agentNameByID("abcdefghijklmnop")
	if name != "abcdefgh" {
		t.Errorf("expected truncated, got %q", name)
	}
}

func TestDashboard_AgentNameByID_ShortUnknown(t *testing.T) {
	m := newTestDashboard()
	name := m.agentNameByID("xy")
	if name != "xy" {
		t.Errorf("expected 'xy', got %q", name)
	}
}

func TestDashboard_AddOrUpdateRelEdge_New(t *testing.T) {
	m := newTestDashboard()
	m.addOrUpdateRelEdge("Maria", "Kenji", components.RelTrust, 0.7, "vouched")
	if len(m.relEdges) != 1 {
		t.Fatalf("expected 1 edge, got %d", len(m.relEdges))
	}
	if m.relEdges[0].Strength != 0.7 {
		t.Errorf("expected strength 0.7, got %f", m.relEdges[0].Strength)
	}
}

func TestDashboard_AddOrUpdateRelEdge_Update(t *testing.T) {
	m := newTestDashboard()
	m.addOrUpdateRelEdge("Maria", "Kenji", components.RelTrust, 0.5, "initial")
	m.addOrUpdateRelEdge("Maria", "Kenji", components.RelAlliance, 0.9, "allied")
	if len(m.relEdges) != 1 {
		t.Fatalf("expected 1 edge after update, got %d", len(m.relEdges))
	}
	if m.relEdges[0].Strength != 0.9 {
		t.Errorf("expected updated strength 0.9, got %f", m.relEdges[0].Strength)
	}
	if m.relEdges[0].Label != "allied" {
		t.Errorf("expected updated label 'allied', got %q", m.relEdges[0].Label)
	}
}

func TestDashboard_AddOrUpdateRelEdge_ReverseOrder(t *testing.T) {
	m := newTestDashboard()
	m.addOrUpdateRelEdge("Maria", "Kenji", components.RelTrust, 0.5, "forward")
	m.addOrUpdateRelEdge("Kenji", "Maria", components.RelAlliance, 0.8, "reverse")
	// Should update existing edge (bidirectional match)
	if len(m.relEdges) != 1 {
		t.Errorf("expected 1 edge (bidirectional update), got %d", len(m.relEdges))
	}
}

func TestDashboard_UpdateTravel_NewAndUpdate(t *testing.T) {
	m := newTestDashboard()
	m.updateTravel("Maria", "Shelter", "Bridge", 0.3)
	if len(m.mapTravels) != 1 {
		t.Fatalf("expected 1 travel, got %d", len(m.mapTravels))
	}
	if m.mapTravels[0].Progress != 0.3 {
		t.Errorf("expected progress 0.3, got %f", m.mapTravels[0].Progress)
	}

	m.updateTravel("Maria", "Shelter", "Bridge", 0.7)
	if len(m.mapTravels) != 1 {
		t.Fatalf("expected 1 travel after update, got %d", len(m.mapTravels))
	}
	if m.mapTravels[0].Progress != 0.7 {
		t.Errorf("expected updated progress 0.7, got %f", m.mapTravels[0].Progress)
	}
}

func TestDashboard_RemoveTravel(t *testing.T) {
	m := newTestDashboard()
	m.updateTravel("Maria", "A", "B", 0.5)
	m.updateTravel("Kenji", "C", "D", 0.2)
	m.removeTravel("Maria")
	if len(m.mapTravels) != 1 {
		t.Fatalf("expected 1 travel after removal, got %d", len(m.mapTravels))
	}
	if m.mapTravels[0].AgentName != "Kenji" {
		t.Errorf("expected Kenji remaining, got %q", m.mapTravels[0].AgentName)
	}
}

func TestDashboard_RemoveTravel_NotFound(t *testing.T) {
	m := newTestDashboard()
	m.removeTravel("Nobody")
	// Should not panic
}

func TestDashboard_AddMapLocation_New(t *testing.T) {
	m := newTestDashboard()
	m.addMapLocation("Cave", "River")
	found := false
	for _, loc := range m.mapLocations {
		if loc.Name == "Cave" {
			found = true
			if len(loc.ConnectedTo) != 1 || loc.ConnectedTo[0] != "River" {
				t.Errorf("wrong connections: %v", loc.ConnectedTo)
			}
		}
	}
	if !found {
		t.Error("expected Cave in map locations")
	}
}

func TestDashboard_AddMapLocation_Existing(t *testing.T) {
	m := newTestDashboard()
	m.addMapLocation("Cave", "River")
	m.addMapLocation("Cave", "Mountain")
	count := 0
	for _, loc := range m.mapLocations {
		if loc.Name == "Cave" {
			count++
			if len(loc.ConnectedTo) != 2 {
				t.Errorf("expected 2 connections, got %d", len(loc.ConnectedTo))
			}
		}
	}
	if count != 1 {
		t.Errorf("expected 1 Cave entry, got %d", count)
	}
}

func TestDashboard_AddMapLocation_EmptyConnection(t *testing.T) {
	m := newTestDashboard()
	m.addMapLocation("Cave", "")
	for _, loc := range m.mapLocations {
		if loc.Name == "Cave" {
			if len(loc.ConnectedTo) != 0 {
				t.Errorf("expected no connections for empty connectedTo, got %v", loc.ConnectedTo)
			}
		}
	}
}

// --- buildScenarioList edge cases ---

func TestBuildScenarioList_Nil(t *testing.T) {
	result := buildScenarioList(nil)
	if len(result) != 1 || result[0] != "All" {
		t.Errorf("expected [All] for nil input, got %v", result)
	}
}

func TestBuildScenarioList_EmptySlice(t *testing.T) {
	result := buildScenarioList([]map[string]interface{}{})
	if len(result) != 1 || result[0] != "All" {
		t.Errorf("expected [All] for empty input, got %v", result)
	}
}

func TestBuildScenarioList_DuplicateNames(t *testing.T) {
	runs := []map[string]interface{}{
		{"scenario_name": "Flood"},
		{"scenario_name": "Flood"},
		{"scenario_name": "Flood"},
		{"scenario_name": "Tsunami"},
	}
	result := buildScenarioList(runs)
	if len(result) != 3 { // All + Flood + Tsunami
		t.Errorf("expected 3 entries, got %d: %v", len(result), result)
	}
	if result[0] != "All" {
		t.Errorf("first entry should be All, got %q", result[0])
	}
}

func TestBuildScenarioList_EmptyScenarioName(t *testing.T) {
	runs := []map[string]interface{}{
		{"scenario_name": ""},
		{"scenario_name": "Flood"},
	}
	result := buildScenarioList(runs)
	// Empty names should be skipped
	if len(result) != 2 { // All + Flood
		t.Errorf("expected 2 entries, got %d: %v", len(result), result)
	}
}

func TestBuildScenarioList_MissingScenarioName(t *testing.T) {
	runs := []map[string]interface{}{
		{"other_field": "value"},
		{"scenario_name": "Flood"},
	}
	result := buildScenarioList(runs)
	if len(result) != 2 { // All + Flood
		t.Errorf("expected 2 entries, got %d: %v", len(result), result)
	}
}

func TestBuildScenarioList_SortedOutput(t *testing.T) {
	runs := []map[string]interface{}{
		{"scenario_name": "Zombie"},
		{"scenario_name": "Avalanche"},
		{"scenario_name": "Flood"},
	}
	result := buildScenarioList(runs)
	if result[0] != "All" || result[1] != "Avalanche" || result[2] != "Flood" || result[3] != "Zombie" {
		t.Errorf("expected sorted output, got %v", result)
	}
}

// --- Analytics scenario cycling edge case ---

func TestAnalytics_SingleScenario_Cycling(t *testing.T) {
	m := AnalyticsModel{
		scenarios:   []string{"All"},
		selScenario: 0,
		available:   true,
	}
	// Cycling with only "All" should stay on All
	m.selScenario = (m.selScenario + 1) % len(m.scenarios)
	if m.scenarios[m.selScenario] != "All" {
		t.Errorf("expected All, got %q", m.scenarios[m.selScenario])
	}
}

func TestAnalytics_View_ZeroDimensions(t *testing.T) {
	m := AnalyticsModel{available: true, stats: map[string]interface{}{"count": 5.0}}
	view := m.View(0, 0)
	_ = view // no panic
}

func TestAnalytics_View_NoRuns(t *testing.T) {
	m := AnalyticsModel{
		available: true,
		stats:     map[string]interface{}{},
		runs:      nil,
		scenarios: []string{"All"},
	}
	view := m.View(80, 40)
	if view == "" {
		t.Error("expected non-empty view")
	}
}
