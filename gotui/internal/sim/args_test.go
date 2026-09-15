package sim

import (
	"reflect"
	"testing"
)

func ptrInt(v int) *int           { return &v }
func ptrFloat(v float64) *float64 { return &v }
func ptrString(v string) *string  { return &v }

func TestRunArgsMinimal(t *testing.T) {
	got, err := RunArgs(RunOptions{Scenario: "Rising Flood"})
	if err != nil {
		t.Fatalf("RunArgs: %v", err)
	}
	want := []string{"run", "--scenario", "Rising Flood"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("RunArgs = %v, want %v", got, want)
	}
}

func TestRunArgsFull(t *testing.T) {
	got, err := RunArgs(RunOptions{
		Scenario:  "Rising Flood",
		MaxSteps:  50,
		Seed:      ptrInt(42),
		TickDelay: ptrFloat(0.25),
		Verbose:   true,
		Simple:    true,
		ForceVLLM: ptrString("http://localhost:8020"),
	})
	if err != nil {
		t.Fatalf("RunArgs: %v", err)
	}
	want := []string{
		"run", "--scenario", "Rising Flood",
		"--max-steps", "50", "--seed", "42", "--tick-delay", "0.25",
		"--verbose", "--simple", "--force-vllm", "http://localhost:8020",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("RunArgs = %v\nwant %v", got, want)
	}
}

// A bare --force-vllm means "engine default port", which is what the click
// option's optional value encodes. Passing a value there would be wrong.
func TestRunArgsBareForceVLLM(t *testing.T) {
	got, err := RunArgs(RunOptions{Scenario: "s", ForceVLLM: ptrString("")})
	if err != nil {
		t.Fatalf("RunArgs: %v", err)
	}
	want := []string{"run", "--scenario", "s", "--force-vllm"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("RunArgs = %v, want %v", got, want)
	}
}

func TestRunArgsValidation(t *testing.T) {
	cases := map[string]RunOptions{
		"empty scenario":     {Scenario: "  "},
		"negative max steps": {Scenario: "s", MaxSteps: -1},
		"negative tick":      {Scenario: "s", TickDelay: ptrFloat(-0.5)},
		"relative vllm url":  {Scenario: "s", ForceVLLM: ptrString("/vllm")},
		"scheme-less vllm":   {Scenario: "s", ForceVLLM: ptrString("localhost:8010")},
	}
	for name, o := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := RunArgs(o); err == nil {
				t.Errorf("RunArgs(%+v) returned no error, want a rejection", o)
			}
		})
	}
}

func TestEvalArgs(t *testing.T) {
	got, err := EvalArgs(EvalOptions{Scenarios: "flood", Seeds: 3, MaxSteps: 10, Repeat: 2, JSON: true})
	if err != nil {
		t.Fatalf("EvalArgs: %v", err)
	}
	want := []string{"eval", "--scenarios", "flood", "--seeds", "3", "--max-steps", "10", "--repeat", "2", "--json"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("EvalArgs = %v, want %v", got, want)
	}
}

func TestEvalArgsValidation(t *testing.T) {
	if _, err := EvalArgs(EvalOptions{Scenarios: ""}); err == nil {
		t.Error("empty scenarios returned no error")
	}
	if _, err := EvalArgs(EvalOptions{Scenarios: "s", Seeds: 0, MaxSteps: 1, Repeat: 1}); err == nil {
		t.Error("zero seeds returned no error")
	}
	if _, err := EvalArgs(EvalOptions{Scenarios: "s", Seeds: 1, MaxSteps: 0, Repeat: 1}); err == nil {
		t.Error("zero max steps returned no error")
	}
	if _, err := EvalArgs(EvalOptions{Scenarios: "s", Seeds: 1, MaxSteps: 1, Repeat: 0}); err == nil {
		t.Error("zero repeat returned no error")
	}
}

func TestMonitorArgs(t *testing.T) {
	got, err := MonitorArgs(MonitorOptions{URL: "http://localhost:8000/api", RunID: "abc123"})
	if err != nil {
		t.Fatalf("MonitorArgs: %v", err)
	}
	want := []string{"monitor", "--url", "ws://localhost:8000/api/ws", "--run-id", "abc123"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("MonitorArgs = %v, want %v", got, want)
	}
}

func TestMonitorArgsValidation(t *testing.T) {
	if _, err := MonitorArgs(MonitorOptions{URL: "nope", RunID: "x"}); err == nil {
		t.Error("bad url returned no error")
	}
	if _, err := MonitorArgs(MonitorOptions{URL: DefaultWSBase, RunID: ""}); err == nil {
		t.Error("empty run id returned no error")
	}
}
