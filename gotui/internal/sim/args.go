package sim

import (
	"fmt"
	"net/url"
	"strconv"
	"strings"
)

// DefaultBinary is the console script declared in pyproject.toml.
const DefaultBinary = "emotionsim"

// RunOptions mirrors the click options of `emotionsim run` (emotionsim/cli.py:166-174).
type RunOptions struct {
	// Scenario maps to --scenario/-s. The CLI prompts when it is omitted; the
	// front-end requires it because a wizard that submits nothing is a no-op.
	Scenario string
	// MaxSteps maps to --max-steps/-m. Zero means "leave it to the scenario".
	MaxSteps int
	// Seed maps to --seed. Nil means the engine picks a seed.
	Seed *int
	// TickDelay maps to --tick-delay/-d. Nil means the engine default.
	TickDelay *float64
	// Simple maps to --simple.
	Simple bool
	// Verbose maps to --verbose/-v.
	Verbose bool
	// ForceVLLM maps to --force-vllm, which takes an optional URL:
	// nil is absent, a pointer to "" is the bare flag (engine default port),
	// and a pointer to a URL forces that host.
	ForceVLLM *string
}

// EvalOptions mirrors the click options of `emotionsim eval` (emotionsim/cli.py:655-666).
type EvalOptions struct {
	Scenarios      string
	Seeds          int
	MaxSteps       int
	Repeat         int
	PromptVariants string
	Output         string
	JSON           bool
}

// MonitorOptions mirrors the click options of `emotionsim monitor` (emotionsim/cli.py:713-716).
type MonitorOptions struct {
	// URL is the socket base, validated with ParseEndpoint.
	URL string
	// RunID is appended to URL as the final path segment.
	RunID string
	// Simple maps to --simple.
	Simple bool
}

// RunArgs builds the argv for `emotionsim run`, argv[0] excluded.
func RunArgs(o RunOptions) ([]string, error) {
	scenario := strings.TrimSpace(o.Scenario)
	if scenario == "" {
		return nil, fmt.Errorf("scenario is required")
	}
	if o.MaxSteps < 0 {
		return nil, fmt.Errorf("max steps must not be negative, got %d", o.MaxSteps)
	}
	if o.TickDelay != nil && *o.TickDelay < 0 {
		return nil, fmt.Errorf("tick delay must not be negative, got %v", *o.TickDelay)
	}
	if o.ForceVLLM != nil && *o.ForceVLLM != "" {
		if err := validateHTTPURL(*o.ForceVLLM); err != nil {
			return nil, fmt.Errorf("force-vllm URL: %w", err)
		}
	}

	argv := []string{"run", "--scenario", scenario}
	if o.MaxSteps > 0 {
		argv = append(argv, "--max-steps", strconv.Itoa(o.MaxSteps))
	}
	if o.Seed != nil {
		argv = append(argv, "--seed", strconv.Itoa(*o.Seed))
	}
	if o.TickDelay != nil {
		argv = append(argv, "--tick-delay", strconv.FormatFloat(*o.TickDelay, 'f', -1, 64))
	}
	if o.Verbose {
		argv = append(argv, "--verbose")
	}
	if o.Simple {
		argv = append(argv, "--simple")
	}
	if o.ForceVLLM != nil {
		if *o.ForceVLLM == "" {
			argv = append(argv, "--force-vllm")
		} else {
			argv = append(argv, "--force-vllm", *o.ForceVLLM)
		}
	}
	return argv, nil
}

// EvalArgs builds the argv for `emotionsim eval`, argv[0] excluded.
func EvalArgs(o EvalOptions) ([]string, error) {
	scenarios := strings.TrimSpace(o.Scenarios)
	if scenarios == "" {
		return nil, fmt.Errorf("at least one scenario is required")
	}
	if o.Seeds < 1 {
		return nil, fmt.Errorf("seeds must be at least 1, got %d", o.Seeds)
	}
	if o.MaxSteps < 1 {
		return nil, fmt.Errorf("max steps must be at least 1, got %d", o.MaxSteps)
	}
	if o.Repeat < 1 {
		return nil, fmt.Errorf("repeat must be at least 1, got %d", o.Repeat)
	}

	argv := []string{
		"eval",
		"--scenarios", scenarios,
		"--seeds", strconv.Itoa(o.Seeds),
		"--max-steps", strconv.Itoa(o.MaxSteps),
		"--repeat", strconv.Itoa(o.Repeat),
	}
	if v := strings.TrimSpace(o.PromptVariants); v != "" {
		argv = append(argv, "--prompt-variants", v)
	}
	if out := strings.TrimSpace(o.Output); out != "" {
		argv = append(argv, "--output", out)
	}
	if o.JSON {
		argv = append(argv, "--json")
	}
	return argv, nil
}

// MonitorArgs builds the argv for `emotionsim monitor`, argv[0] excluded.
//
// URL is normalised through ParseEndpoint so a user may pass the bare
// http://host:8000/api form and still reach the socket route.
func MonitorArgs(o MonitorOptions) ([]string, error) {
	ep, err := ParseEndpoint(o.URL)
	if err != nil {
		return nil, err
	}
	if _, err := ep.RunURL(o.RunID); err != nil {
		return nil, err
	}

	argv := []string{"monitor", "--url", ep.WSBase, "--run-id", strings.TrimSpace(o.RunID)}
	if o.Simple {
		argv = append(argv, "--simple")
	}
	return argv, nil
}

// validateHTTPURL rejects anything that is not an absolute http/https URL.
func validateHTTPURL(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("%q is not a valid URL: %w", raw, err)
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return fmt.Errorf("%q must be an absolute http or https URL", raw)
	}
	if u.Host == "" {
		return fmt.Errorf("%q has no host", raw)
	}
	return nil
}
