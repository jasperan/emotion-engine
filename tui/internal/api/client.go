package api

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// Client wraps the EmotionSim REST API.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// NewClient creates an API client for the given base URL.
func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// BaseURL returns the configured backend URL for diagnostics and UI hints.
func (c *Client) BaseURL() string {
	if c == nil {
		return ""
	}
	return c.baseURL
}

// --- Scenarios ---

// ListScenarios returns all available scenarios.
func (c *Client) ListScenarios() ([]ScenarioResponse, error) {
	var result []ScenarioResponse
	if err := c.get("/api/scenarios", &result); err != nil {
		return nil, err
	}
	return result, nil
}

// GetScenario returns a single scenario by ID.
func (c *Client) GetScenario(id string) (*ScenarioResponse, error) {
	var result ScenarioResponse
	if err := c.get("/api/scenarios/"+id, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// ListScenarioFiles returns scenario files from the filesystem.
func (c *Client) ListScenarioFiles() ([]ScenarioFileResponse, error) {
	var result []ScenarioFileResponse
	if err := c.get("/api/scenarios/files", &result); err != nil {
		return nil, err
	}
	return result, nil
}

// --- Runs ---

// CreateRun starts a new simulation run.
func (c *Client) CreateRun(req RunCreate) (*RunResponse, error) {
	var result RunResponse
	if err := c.post("/api/runs", req, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// ListRuns returns runs, optionally filtered by scenario ID.
func (c *Client) ListRuns(scenarioID string, limit int) ([]RunResponse, error) {
	path := fmt.Sprintf("/api/runs?limit=%d", limit)
	if scenarioID != "" {
		path += "&scenario_id=" + scenarioID
	}
	var result []RunResponse
	if err := c.get(path, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// GetRun returns a single run by ID.
func (c *Client) GetRun(id string) (*RunResponse, error) {
	var result RunResponse
	if err := c.get("/api/runs/"+id, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// ControlRun sends a control action (pause, resume, stop) to a run.
func (c *Client) ControlRun(id string, action string) error {
	body := RunControl{Action: action}
	return c.post("/api/runs/"+id+"/control", body, nil)
}

// GetRunAgents returns all agents for a given run.
func (c *Client) GetRunAgents(id string) ([]AgentStatus, error) {
	var result []AgentStatus
	if err := c.get("/api/runs/"+id+"/agents", &result); err != nil {
		return nil, err
	}
	return result, nil
}

// GetRunMessages returns messages for a given run.
func (c *Client) GetRunMessages(id string, limit int) ([]MessageResponse, error) {
	path := fmt.Sprintf("/api/runs/%s/messages?limit=%d", id, limit)
	var result []MessageResponse
	if err := c.get(path, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// GetRunSteps returns steps for a given run with pagination.
func (c *Client) GetRunSteps(runID string, skip, limit int) ([]StepResponse, error) {
	var steps []StepResponse
	err := c.get(fmt.Sprintf("/api/runs/%s/steps?skip=%d&limit=%d", runID, skip, limit), &steps)
	return steps, err
}

// DeleteRun deletes a run by ID.
func (c *Client) DeleteRun(id string) error {
	req, err := http.NewRequest(http.MethodDelete, c.baseURL+"/api/runs/"+id, nil)
	if err != nil {
		return fmt.Errorf("creating request: %w", err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("delete request: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

// --- Datalake ---

// DatalakeStats returns aggregated statistics from the datalake.
func (c *Client) DatalakeStats() (map[string]interface{}, error) {
	var stats map[string]interface{}
	err := c.get("/api/datalake/stats", &stats)
	return stats, err
}

// DatalakeRuns returns runs from the datalake, optionally filtered by scenario name.
func (c *Client) DatalakeRuns(scenarioName string, limit int) ([]map[string]interface{}, error) {
	path := fmt.Sprintf("/api/datalake/runs?limit=%d", limit)
	if scenarioName != "" {
		path += "&scenario_name=" + url.QueryEscape(scenarioName)
	}
	var runs []map[string]interface{}
	err := c.get(path, &runs)
	return runs, err
}

// Ping checks if the backend is reachable with a short timeout.
func (c *Client) Ping() error {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/health", nil)
	if err != nil {
		return fmt.Errorf("creating health request: %w", err)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("GET /health: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("health check HTTP %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

// --- Internal helpers ---

func (c *Client) get(path string, result interface{}) error {
	resp, err := c.httpClient.Get(c.baseURL + path)
	if err != nil {
		return fmt.Errorf("GET %s: %w", path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(body))
	}

	if result != nil {
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return fmt.Errorf("decoding response from %s: %w", path, err)
		}
	}
	return nil
}

func (c *Client) post(path string, body interface{}, result interface{}) error {
	var reqBody io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("marshaling request body: %w", err)
		}
		reqBody = bytes.NewReader(data)
	}

	resp, err := c.httpClient.Post(c.baseURL+path, "application/json", reqBody)
	if err != nil {
		return fmt.Errorf("POST %s: %w", path, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(respBody))
	}

	if result != nil {
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return fmt.Errorf("decoding response from %s: %w", path, err)
		}
	}
	return nil
}
