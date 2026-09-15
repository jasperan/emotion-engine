// Command emotionsim-tui is a Go front-end for the emotionsim engine: a
// huh-driven run wizard, a confirmation page, and a WebSocket monitor.
//
// Every action is reachable with flags alone. When stdin is not a terminal, or
// when --plan is passed, the program resolves what it would do and prints it as
// JSON instead of prompting, so it is usable from scripts and CI.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"strings"

	tea "charm.land/bubbletea/v2"

	"github.com/jasperan/emotion-engine/gotui/internal/api"
	"github.com/jasperan/emotion-engine/gotui/internal/huhstyle"
	"github.com/jasperan/emotion-engine/gotui/internal/sim"
	"github.com/jasperan/emotion-engine/gotui/internal/tui"
)

// plan is the resolved, printable description of what the front-end would do.
type plan struct {
	Command    string       `json:"command"`
	Endpoint   endpointView `json:"endpoint"`
	Arguments  []string     `json:"arguments"`
	Executable string       `json:"executable"`
	Scenario   string       `json:"scenario,omitempty"`
	RunID      string       `json:"run_id,omitempty"`
	Mode       string       `json:"mode"`
	Note       string       `json:"note,omitempty"`
}

type endpointView struct {
	WSBase   string `json:"ws_base"`
	RESTBase string `json:"rest_base"`
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "error: "+err.Error())
		os.Exit(1)
	}
}

func run() error {
	fs := flag.NewFlagSet("emotionsim-tui", flag.ContinueOnError)
	fs.Usage = func() {
		fmt.Fprintf(fs.Output(), "usage: emotionsim-tui [flags]\n\n")
		fmt.Fprintf(fs.Output(), "A huh-driven front-end for the emotionsim engine.\n\n")
		fs.PrintDefaults()
	}

	endpoint := fs.String("endpoint", sim.DefaultWSBase, "engine socket base URL (ws://host:port/api/ws)")
	command := fs.String("command", "run", "engine command to drive: run, eval or monitor")
	binary := fs.String("binary", sim.DefaultBinary, "CLI to invoke for the standalone path")
	scenario := fs.String("scenario", "", "scenario name or id")
	maxSteps := fs.Int("max-steps", 0, "override max steps (0 keeps the scenario default)")
	seed := fs.Int("seed", 0, "seed for reproducibility")
	tickDelay := fs.Float64("tick-delay", -1, "delay between steps in seconds")
	llmBackend := fs.String("llm-backend", "", "override provider over the API: ollama, vllm or openai")
	forceVLLM := fs.String("force-vllm", "",
		"standalone runs only: 'default' forces vLLM on its default port, or give an http URL")
	verbose := fs.Bool("verbose", false, "timestamp every LLM call with token counts")
	simple := fs.Bool("simple", false, "plain log output instead of the rich renderer")
	runID := fs.String("run-id", "", "run id to monitor (--command monitor)")
	seeds := fs.Int("seeds", 3, "--command eval: seeds per scenario")
	repeat := fs.Int("repeat", 2, "--command eval: repetitions")
	output := fs.String("output", "", "--command eval: output path")
	asJSON := fs.Bool("json", false, "--command eval: emit JSON results")

	printPlan := fs.Bool("plan", false, "resolve and print what would run, then exit (never prompts)")
	noWizard := fs.Bool("no-wizard", false, "skip the wizard and use the flags as given")
	doExec := fs.Bool("exec", false, "execute the resolved CLI command instead of printing it")

	if err := fs.Parse(os.Args[1:]); err != nil {
		return err
	}

	ep, err := sim.ParseEndpoint(*endpoint)
	if err != nil {
		return err
	}

	preset := tui.Preset{
		Scenario:   *scenario,
		MaxSteps:   *maxSteps,
		Verbose:    *verbose,
		Simple:     *simple,
		LLMBackend: *llmBackend,
	}

	forceVLLMValue, err := parseForceVLLM(*forceVLLM)
	if err != nil {
		return err
	}
	if wasSet(fs, "seed") {
		v := *seed
		preset.Seed = &v
	}
	if wasSet(fs, "tick-delay") {
		v := *tickDelay
		preset.TickDelay = &v
	}

	client := api.NewClient(ep.RESTBase)

	switch *command {
	case "run":
		opts := sim.RunOptions{
			Scenario:  strings.TrimSpace(*scenario),
			MaxSteps:  *maxSteps,
			Seed:      preset.Seed,
			TickDelay: preset.TickDelay,
			Verbose:   *verbose,
			Simple:    *simple,
			ForceVLLM: forceVLLMValue,
		}
		return driveRun(ep, client, preset, opts, *binary, *llmBackend, *printPlan, *noWizard, *doExec)

	case "eval":
		opts := sim.EvalOptions{
			Scenarios: strings.TrimSpace(*scenario),
			Seeds:     *seeds,
			MaxSteps:  *maxSteps,
			Repeat:    *repeat,
			Output:    strings.TrimSpace(*output),
			JSON:      *asJSON,
		}
		argv, err := sim.EvalArgs(opts)
		if err != nil {
			return err
		}
		return emitPlan(plan{
			Command: "eval", Endpoint: endpointView{ep.WSBase, ep.RESTBase},
			Executable: *binary, Arguments: argv, Mode: "cli",
		}, *doExec, *binary)

	case "monitor":
		if strings.TrimSpace(*runID) == "" {
			return fmt.Errorf("--command monitor requires --run-id")
		}
		if *printPlan || *noWizard || !huhstyle.Interactive() {
			argv, err := sim.MonitorArgs(sim.MonitorOptions{URL: *endpoint, RunID: *runID, Simple: *simple})
			if err != nil {
				return err
			}
			return emitPlan(plan{
				Command: "monitor", Endpoint: endpointView{ep.WSBase, ep.RESTBase},
				Executable: *binary, Arguments: argv, RunID: *runID, Mode: "cli",
			}, *doExec, *binary)
		}
		return runMonitor(ep, client, *runID)

	default:
		return fmt.Errorf("unknown --command %q; use run, eval or monitor", *command)
	}
}

// driveRun either starts the wizard or, when prompting is not possible or not
// wanted, resolves the plan from the flags.
func driveRun(ep sim.Endpoint, client *api.Client, preset tui.Preset, opts sim.RunOptions, binary, llmBackend string, printPlan, noWizard, doExec bool) error {
	headless := printPlan || noWizard || !huhstyle.Interactive()

	if !headless {
		model := tui.New(context.Background(), ep, client, preset)
		_, err := tea.NewProgram(model).Run()
		return err
	}

	argv, err := sim.RunArgs(opts)
	if err != nil {
		return fmt.Errorf("%w (headless runs need --scenario)", err)
	}
	note := "standalone: the CLI runs the simulation itself and needs no server"
	if _, apiErr := api.NewClient(ep.RESTBase).ListScenarios(context.Background()); apiErr == nil {
		note = "engine reachable; the wizard would create this run over the API and monitor it"
	}
	// --llm-backend is an API-only field (RunCreate.llm_backend); the CLI has no
	// equivalent, so say so rather than dropping the flag silently.
	if strings.TrimSpace(llmBackend) != "" {
		note += "; --llm-backend applies only to the API path, use --force-vllm standalone"
	}
	return emitPlan(plan{
		Command: "run", Endpoint: endpointView{ep.WSBase, ep.RESTBase},
		Executable: binary, Arguments: argv, Scenario: opts.Scenario, Mode: "cli", Note: note,
	}, doExec, binary)
}

// emitPlan prints the plan as JSON and, when asked, executes it.
func emitPlan(p plan, doExec bool, binary string) error {
	if !doExec {
		encoded, err := json.MarshalIndent(p, "", "  ")
		if err != nil {
			return err
		}
		fmt.Println(string(encoded))
		return nil
	}

	cmd := exec.Command(binary, p.Arguments...) //nolint:gosec // argv is validated by the sim builders
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

func runMonitor(ep sim.Endpoint, client *api.Client, runID string) error {
	model := tui.NewMonitor(ep, client, runID)
	_, err := tea.NewProgram(model).Run()
	return err
}

// parseForceVLLM maps the --force-vllm flag onto sim.RunOptions.ForceVLLM, whose
// nil/empty/URL triple mirrors click's optional-value option.
func parseForceVLLM(raw string) (*string, error) {
	switch strings.TrimSpace(raw) {
	case "":
		return nil, nil
	case "default":
		bare := ""
		return &bare, nil
	default:
		value := strings.TrimSpace(raw)
		return &value, nil
	}
}

// wasSet reports whether a flag was supplied, which is how an "unset" seed stays
// distinct from an explicit seed of 0.
func wasSet(fs *flag.FlagSet, name string) bool {
	found := false
	fs.Visit(func(f *flag.Flag) {
		if f.Name == name {
			found = true
		}
	})
	return found
}
