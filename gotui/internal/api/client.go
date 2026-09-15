// Package api is the HTTP half of the front-end: it talks to the FastAPI app
// mounted at /api (emotionsim/main.py:123) and never to the database directly.
package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// DefaultTimeout bounds every call. The engine is frequently not running, and a
// front-end that hangs instead of reporting that is worse than useless.
const DefaultTimeout = 5 * time.Second

// maxErrorBody caps how much of an error response is quoted back to the user.
const maxErrorBody = 300

// Scenario is the subset of ScenarioResponse the wizard needs
// (emotionsim/schemas/scenario.py:47).
type Scenario struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// Label is what the picker shows: the name, falling back to the id.
func (s Scenario) Label() string {
	if strings.TrimSpace(s.Name) != "" {
		return s.Name
	}
	return s.ID
}

// RunCreate is the request body of POST /api/runs/ (emotionsim/schemas/run.py:7).
// llm_backend is a closed set on the server, so the zero value means unset.
type RunCreate struct {
	ScenarioID string `json:"scenario_id"`
	Seed       *int   `json:"seed,omitempty"`
	MaxSteps   int    `json:"max_steps,omitempty"`
	LLMBackend string `json:"llm_backend,omitempty"`
}

// Run is the subset of RunResponse the front-end tracks (emotionsim/schemas/run.py:15).
type Run struct {
	ID          string `json:"id"`
	ScenarioID  string `json:"scenario_id"`
	Status      string `json:"status"`
	CurrentStep int    `json:"current_step"`
	MaxSteps    int    `json:"max_steps"`
}

// Client is a thin, timeout-bounded HTTP client for one engine instance.
type Client struct {
	base string
	hc   *http.Client
}

// NewClient returns a client rooted at restBase, e.g. http://localhost:8000/api.
func NewClient(restBase string) *Client {
	return &Client{
		base: strings.TrimRight(restBase, "/"),
		hc:   &http.Client{Timeout: DefaultTimeout},
	}
}

// ListScenarios returns every scenario the engine knows about.
func (c *Client) ListScenarios(ctx context.Context) ([]Scenario, error) {
	var out []Scenario
	if err := c.do(ctx, http.MethodGet, "/scenarios/", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// CreateRun creates a run for a scenario. The run does not start on its own.
func (c *Client) CreateRun(ctx context.Context, rc RunCreate) (*Run, error) {
	if strings.TrimSpace(rc.ScenarioID) == "" {
		return nil, fmt.Errorf("scenario id is required")
	}
	var out Run
	if err := c.do(ctx, http.MethodPost, "/runs/", rc, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// ControlRun sends one of start/pause/resume/stop/step
// (emotionsim/schemas/run.py RunControl).
func (c *Client) ControlRun(ctx context.Context, runID, action string) error {
	switch action {
	case "start", "pause", "resume", "stop", "step":
	default:
		return fmt.Errorf("unsupported control action %q", action)
	}
	body := map[string]string{"action": action}
	return c.do(ctx, http.MethodPost, "/runs/"+runID+"/control", body, nil)
}

// GetRunStatus returns the engine's live view of a run
// (GET /api/runs/{id}/status, which is not the persisted RunResponse).
func (c *Client) GetRunStatus(ctx context.Context, runID string) (map[string]any, error) {
	var out map[string]any
	if err := c.do(ctx, http.MethodGet, "/runs/"+runID+"/status", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// HealthLLM reports whether the configured LLM backend is reachable. The wizard
// uses it to warn before a run is created, not to block one.
func (c *Client) HealthLLM(ctx context.Context) (map[string]any, error) {
	var out map[string]any
	if err := c.do(ctx, http.MethodGet, "/health/llm", nil, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Client) do(ctx context.Context, method, path string, in any, out any) error {
	var body io.Reader
	if in != nil {
		encoded, err := json.Marshal(in)
		if err != nil {
			return fmt.Errorf("encode %s %s: %w", method, path, err)
		}
		body = bytes.NewReader(encoded)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.base+path, body)
	if err != nil {
		return fmt.Errorf("build %s %s: %w", method, path, err)
	}
	req.Header.Set("Accept", "application/json")
	if in != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.hc.Do(req)
	if err != nil {
		return fmt.Errorf("%s %s: %w", method, path, err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		detail, _ := io.ReadAll(io.LimitReader(resp.Body, maxErrorBody))
		msg := strings.TrimSpace(string(detail))
		if msg == "" {
			return fmt.Errorf("%s %s: HTTP %d", method, path, resp.StatusCode)
		}
		return fmt.Errorf("%s %s: HTTP %d: %s", method, path, resp.StatusCode, msg)
	}

	if out == nil {
		_, _ = io.Copy(io.Discard, resp.Body)
		return nil
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("decode %s %s: %w", method, path, err)
	}
	return nil
}
