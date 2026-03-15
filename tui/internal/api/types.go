package api

import (
	"strings"
	"time"
)

// FlexTime handles timestamps with or without timezone info.
type FlexTime struct {
	time.Time
}

func (ft *FlexTime) UnmarshalJSON(b []byte) error {
	s := strings.Trim(string(b), "\"")
	if s == "null" || s == "" {
		return nil
	}
	for _, layout := range []string{
		time.RFC3339,
		"2006-01-02T15:04:05",
		"2006-01-02 15:04:05",
	} {
		if t, err := time.Parse(layout, s); err == nil {
			ft.Time = t
			return nil
		}
	}
	t, err := time.Parse(time.RFC3339, s)
	ft.Time = t
	return err
}

// --- Scenarios ---

type ScenarioResponse struct {
	ID             string                   `json:"id"`
	Name           string                   `json:"name"`
	Description    string                   `json:"description"`
	Config         map[string]interface{}   `json:"config"`
	AgentTemplates []map[string]interface{} `json:"agent_templates"`
	CreatedAt      FlexTime                 `json:"created_at"`
	UpdatedAt      FlexTime                 `json:"updated_at"`
}

type ScenarioFileResponse struct {
	Filename     string `json:"filename"`
	Filepath     string `json:"filepath"`
	Name         string `json:"name"`
	Description  string `json:"description"`
	GeneratedAt  string `json:"generated_at"`
	PersonaCount int    `json:"persona_count"`
}

// --- Runs ---

type RunCreate struct {
	ScenarioID string  `json:"scenario_id"`
	Seed       *int    `json:"seed,omitempty"`
	MaxSteps   *int    `json:"max_steps,omitempty"`
	LLMBackend *string `json:"llm_backend,omitempty"`
}

type RunResponse struct {
	ID          string                 `json:"id"`
	ScenarioID  string                 `json:"scenario_id"`
	Status      string                 `json:"status"`
	CurrentStep int                    `json:"current_step"`
	MaxSteps    int                    `json:"max_steps"`
	Seed        *int                   `json:"seed,omitempty"`
	WorldState  map[string]interface{} `json:"world_state"`
	Metrics     map[string]interface{} `json:"metrics"`
	Evaluation  map[string]interface{} `json:"evaluation"`
	CreatedAt   FlexTime               `json:"created_at"`
	StartedAt   *FlexTime              `json:"started_at,omitempty"`
	CompletedAt *FlexTime              `json:"completed_at,omitempty"`
}

type RunControl struct {
	Action string `json:"action"`
}

// --- Agents ---

type AgentStatus struct {
	ID           string                 `json:"id"`
	Name         string                 `json:"name"`
	Role         string                 `json:"role"`
	ModelID      string                 `json:"model_id"`
	Provider     string                 `json:"provider"`
	Persona      map[string]interface{} `json:"persona,omitempty"`
	DynamicState map[string]interface{} `json:"dynamic_state"`
	IsActive     bool                   `json:"is_active"`
	CurrentPlan  *AgentPlanStatus       `json:"current_plan,omitempty"`
}

type AgentPlanStatus struct {
	Goal         string `json:"goal"`
	CurrentStep  string `json:"current_step"`
	StepProgress string `json:"step_progress"`
	DeadlineStep *int   `json:"deadline_step,omitempty"`
}

// --- Messages ---

type MessageResponse struct {
	ID          string                 `json:"id"`
	RunID       string                 `json:"run_id"`
	FromAgentID *string                `json:"from_agent_id,omitempty"`
	ToTarget    string                 `json:"to_target"`
	MessageType string                 `json:"message_type"`
	Content     string                 `json:"content"`
	Metadata    map[string]interface{} `json:"metadata"`
	StepIndex   int                    `json:"step_index"`
	Timestamp   FlexTime               `json:"timestamp"`
}

// --- Steps ---

type StepResponse struct {
	ID            string                   `json:"id"`
	RunID         string                   `json:"run_id"`
	StepIndex     int                      `json:"step_index"`
	StateSnapshot map[string]interface{}   `json:"state_snapshot"`
	Actions       []map[string]interface{} `json:"actions"`
	StepMetrics   map[string]interface{}   `json:"step_metrics"`
	Timestamp     FlexTime                 `json:"timestamp"`
}

// --- WebSocket ---

type WSMessage struct {
	Event     string                 `json:"event"`
	Data      map[string]interface{} `json:"data"`
	Timestamp string                 `json:"timestamp"`
}

type WSCommand struct {
	Type string `json:"type"`
}
