package api

import (
	"encoding/json"
	"testing"
	"time"
)

// --- FlexTime Edge Cases ---

func TestFlexTime_EmptyString(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`""`))
	if err != nil {
		t.Errorf("empty string should not error, got: %v", err)
	}
	if !ft.Time.IsZero() {
		t.Errorf("empty string should produce zero time, got: %v", ft.Time)
	}
}

func TestFlexTime_NullLiteral(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"null"`))
	if err != nil {
		t.Errorf("null literal should not error, got: %v", err)
	}
	if !ft.Time.IsZero() {
		t.Errorf("null should produce zero time, got: %v", ft.Time)
	}
}

func TestFlexTime_InvalidFormat(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"not-a-date"`))
	if err == nil {
		t.Error("expected error for invalid date format")
	}
}

func TestFlexTime_GarbageInput(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"2024/13/45 99:99:99"`))
	if err == nil {
		t.Error("expected error for garbage date with out-of-range values")
	}
}

func TestFlexTime_RFC3339(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"2024-06-15T10:30:00Z"`))
	if err != nil {
		t.Fatalf("valid RFC3339 should parse, got: %v", err)
	}
	if ft.Time.Year() != 2024 || ft.Time.Month() != 6 || ft.Time.Day() != 15 {
		t.Errorf("wrong date parsed: %v", ft.Time)
	}
}

func TestFlexTime_WithoutTimezone(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"2024-06-15T10:30:00"`))
	if err != nil {
		t.Fatalf("datetime without timezone should parse, got: %v", err)
	}
	if ft.Time.Hour() != 10 || ft.Time.Minute() != 30 {
		t.Errorf("wrong time parsed: %v", ft.Time)
	}
}

func TestFlexTime_SpaceSeparated(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"2024-06-15 10:30:00"`))
	if err != nil {
		t.Fatalf("space-separated datetime should parse, got: %v", err)
	}
	if ft.Time.Year() != 2024 {
		t.Errorf("wrong year: %v", ft.Time)
	}
}

func TestFlexTime_UnixEpoch(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"1970-01-01T00:00:00Z"`))
	if err != nil {
		t.Fatalf("Unix epoch should parse, got: %v", err)
	}
	if !ft.Time.Equal(time.Date(1970, 1, 1, 0, 0, 0, 0, time.UTC)) {
		t.Errorf("expected Unix epoch, got: %v", ft.Time)
	}
}

func TestFlexTime_FarFuture(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"9999-12-31T23:59:59Z"`))
	if err != nil {
		t.Fatalf("far future date should parse, got: %v", err)
	}
	if ft.Time.Year() != 9999 {
		t.Errorf("expected year 9999, got: %v", ft.Time.Year())
	}
}

func TestFlexTime_FarPast(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"0001-01-01T00:00:00Z"`))
	if err != nil {
		t.Fatalf("far past date should parse, got: %v", err)
	}
	if ft.Time.Year() != 1 {
		t.Errorf("expected year 1, got: %v", ft.Time.Year())
	}
}

func TestFlexTime_WithOffset(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"2024-06-15T10:30:00+05:30"`))
	if err != nil {
		t.Fatalf("RFC3339 with offset should parse, got: %v", err)
	}
	if ft.Time.Year() != 2024 {
		t.Errorf("wrong year: %v", ft.Time)
	}
}

func TestFlexTime_JSONUnmarshalIntegration(t *testing.T) {
	// Test full JSON round-trip with various fields
	type testStruct struct {
		Created FlexTime `json:"created"`
		Updated FlexTime `json:"updated"`
	}

	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{"both null", `{"created":"null","updated":"null"}`, false},
		{"both empty", `{"created":"","updated":""}`, false},
		{"valid dates", `{"created":"2024-01-01T00:00:00Z","updated":"2024-12-31T23:59:59Z"}`, false},
		{"mixed formats", `{"created":"2024-01-01T00:00:00","updated":"2024-12-31 23:59:59"}`, false},
		{"one invalid", `{"created":"2024-01-01T00:00:00Z","updated":"garbage"}`, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var s testStruct
			err := json.Unmarshal([]byte(tt.input), &s)
			if tt.wantErr && err == nil {
				t.Error("expected error")
			}
			if !tt.wantErr && err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		})
	}
}

func TestFlexTime_OnlyDate(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"2024-06-15"`))
	if err == nil {
		t.Log("date-only string parsed (may be unexpected)")
	}
	// This should error since none of the layouts match date-only.
	// Just verify no panic.
}

func TestFlexTime_NumericString(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"1234567890"`))
	if err == nil {
		t.Log("numeric string unexpectedly parsed")
	}
	// Verify no panic regardless of result.
}

func TestFlexTime_WhitespaceOnly(t *testing.T) {
	var ft FlexTime
	err := ft.UnmarshalJSON([]byte(`"   "`))
	// Whitespace-only should fail since it's not empty and not a valid format
	if err == nil {
		// Not necessarily wrong, but worth verifying behavior
		t.Log("whitespace-only string did not error")
	}
}

// --- WSMessage type parsing ---

func TestWSMessage_Unmarshal(t *testing.T) {
	raw := `{"event":"step_completed","data":{"step":5,"world_state":{}},"timestamp":"2024-01-01T00:00:00Z"}`
	var msg WSMessage
	err := json.Unmarshal([]byte(raw), &msg)
	if err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if msg.Event != "step_completed" {
		t.Errorf("wrong event: %s", msg.Event)
	}
	step, ok := msg.Data["step"].(float64)
	if !ok || step != 5 {
		t.Errorf("wrong step: %v", msg.Data["step"])
	}
}

func TestWSMessage_EmptyEvent(t *testing.T) {
	raw := `{"event":"","data":{},"timestamp":""}`
	var msg WSMessage
	err := json.Unmarshal([]byte(raw), &msg)
	if err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if msg.Event != "" {
		t.Errorf("expected empty event, got: %s", msg.Event)
	}
}

func TestWSMessage_NilData(t *testing.T) {
	raw := `{"event":"test","timestamp":"now"}`
	var msg WSMessage
	err := json.Unmarshal([]byte(raw), &msg)
	if err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if msg.Data != nil {
		t.Log("data was non-nil (empty map from JSON null)")
	}
}

func TestWSMessage_WrongTypes(t *testing.T) {
	// step is string where float64 expected
	raw := `{"event":"step_completed","data":{"step":"not_a_number","world_state":"also_wrong"}}`
	var msg WSMessage
	err := json.Unmarshal([]byte(raw), &msg)
	if err != nil {
		t.Fatalf("unmarshal should succeed (loose typing): %v", err)
	}
	// Type assertions should fail gracefully
	_, ok := msg.Data["step"].(float64)
	if ok {
		t.Error("step should NOT be float64 when sent as string")
	}
}

func TestScenarioResponse_Unmarshal(t *testing.T) {
	raw := `{
		"id": "abc",
		"name": "Test",
		"description": "desc",
		"config": {},
		"agent_templates": [],
		"created_at": "2024-01-01T00:00:00Z",
		"updated_at": "2024-06-15 12:00:00"
	}`
	var s ScenarioResponse
	err := json.Unmarshal([]byte(raw), &s)
	if err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if s.Name != "Test" {
		t.Errorf("wrong name: %s", s.Name)
	}
	if s.CreatedAt.Year() != 2024 {
		t.Errorf("wrong year: %d", s.CreatedAt.Year())
	}
}
