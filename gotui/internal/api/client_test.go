package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// newTestClient wires a Client to a stub engine, so every door in this package
// is exercised without a live FastAPI server or vLLM.
func newTestClient(t *testing.T, h http.HandlerFunc) *Client {
	t.Helper()
	srv := httptest.NewServer(h)
	t.Cleanup(srv.Close)
	return NewClient(srv.URL)
}

func TestListScenarios(t *testing.T) {
	c := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/scenarios/" {
			t.Errorf("path = %q, want /scenarios/", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode([]Scenario{{ID: "a1", Name: "Rising Flood"}})
	})
	got, err := c.ListScenarios(context.Background())
	if err != nil {
		t.Fatalf("ListScenarios: %v", err)
	}
	if len(got) != 1 || got[0].ID != "a1" || got[0].Label() != "Rising Flood" {
		t.Errorf("ListScenarios = %+v", got)
	}
}

func TestScenarioLabelFallsBackToID(t *testing.T) {
	if got := (Scenario{ID: "a1"}).Label(); got != "a1" {
		t.Errorf("Label = %q, want a1", got)
	}
}

func TestCreateRun(t *testing.T) {
	var got RunCreate
	c := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/runs/" {
			t.Errorf("got %s %s, want POST /runs/", r.Method, r.URL.Path)
		}
		if ct := r.Header.Get("Content-Type"); ct != "application/json" {
			t.Errorf("Content-Type = %q", ct)
		}
		if err := json.NewDecoder(r.Body).Decode(&got); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		_ = json.NewEncoder(w).Encode(Run{ID: "r1", ScenarioID: "a1", Status: "created"})
	})

	seed := 42
	run, err := c.CreateRun(context.Background(), RunCreate{ScenarioID: "a1", Seed: &seed, MaxSteps: 50, LLMBackend: "vllm"})
	if err != nil {
		t.Fatalf("CreateRun: %v", err)
	}
	if run.ID != "r1" || run.Status != "created" {
		t.Errorf("CreateRun = %+v", run)
	}
	// Only the fields the server accepts may reach the wire.
	if got.ScenarioID != "a1" || got.Seed == nil || *got.Seed != 42 || got.MaxSteps != 50 || got.LLMBackend != "vllm" {
		t.Errorf("request body = %+v", got)
	}
}

func TestCreateRunOmitsUnsetFields(t *testing.T) {
	var raw map[string]any
	c := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewDecoder(r.Body).Decode(&raw)
		_ = json.NewEncoder(w).Encode(Run{ID: "r1"})
	})
	if _, err := c.CreateRun(context.Background(), RunCreate{ScenarioID: "a1"}); err != nil {
		t.Fatalf("CreateRun: %v", err)
	}
	for _, k := range []string{"seed", "max_steps", "llm_backend"} {
		if _, present := raw[k]; present {
			t.Errorf("%s should be omitted when unset, body = %v", k, raw)
		}
	}
	if _, present := raw["scenario_id"]; !present {
		t.Errorf("scenario_id missing from body %v", raw)
	}
}

func TestCreateRunRequiresScenario(t *testing.T) {
	c := NewClient("http://127.0.0.1:1")
	if _, err := c.CreateRun(context.Background(), RunCreate{}); err == nil {
		t.Error("empty scenario id returned no error")
	}
}

func TestControlRun(t *testing.T) {
	var action string
	c := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/runs/r1/control" {
			t.Errorf("path = %q", r.URL.Path)
		}
		var body map[string]string
		_ = json.NewDecoder(r.Body).Decode(&body)
		action = body["action"]
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	})
	if err := c.ControlRun(context.Background(), "r1", "start"); err != nil {
		t.Fatalf("ControlRun: %v", err)
	}
	if action != "start" {
		t.Errorf("action = %q, want start", action)
	}
}

// The server's RunControl is a closed Literal set; rejecting locally keeps a
// typo from becoming a 422 that reads like a server fault.
func TestControlRunRejectsUnknownAction(t *testing.T) {
	c := NewClient("http://127.0.0.1:1")
	if err := c.ControlRun(context.Background(), "r1", "explode"); err == nil {
		t.Error("unknown action returned no error")
	}
}

func TestGetRunStatus(t *testing.T) {
	c := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/runs/r1/status" {
			t.Errorf("path = %q", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"status": "running", "current_step": 3})
	})
	got, err := c.GetRunStatus(context.Background(), "r1")
	if err != nil {
		t.Fatalf("GetRunStatus: %v", err)
	}
	if got["status"] != "running" {
		t.Errorf("status = %v", got["status"])
	}
}

// The engine is usually down. The error must name the endpoint and the cause,
// because that error is the entire offline experience.
func TestErrorsNameEndpointAndStatus(t *testing.T) {
	c := NewClient("http://127.0.0.1:1")
	_, err := c.ListScenarios(context.Background())
	if err == nil {
		t.Fatal("expected a connection error")
	}
	if !strings.Contains(err.Error(), "/scenarios/") {
		t.Errorf("error %q does not name the endpoint", err)
	}

	c2 := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "llm backend unreachable", http.StatusServiceUnavailable)
	})
	_, err = c2.ListScenarios(context.Background())
	if err == nil {
		t.Fatal("expected an error for HTTP 503")
	}
	for _, want := range []string{"503", "llm backend unreachable"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("error %q does not mention %q", err, want)
		}
	}
}

func TestErrorBodyIsTruncated(t *testing.T) {
	c := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = fmt.Fprint(w, strings.Repeat("x", 5000))
	})
	_, err := c.ListScenarios(context.Background())
	if err == nil {
		t.Fatal("expected an error")
	}
	if len(err.Error()) > maxErrorBody+200 {
		t.Errorf("error message is %d bytes, want it truncated", len(err.Error()))
	}
}
