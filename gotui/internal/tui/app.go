// Package tui is the huh-driven front-end: a run-configuration wizard, a
// confirmation page that restates exactly what will run, and a monitor that
// streams events for the run it just started.
//
// It drives the engine over interfaces the engine already exposes. When the
// FastAPI server answers, runs are created and controlled over /api and watched
// over the /api/ws/{run_id} socket. When it does not answer - which is the
// normal case for a laptop that has not started a server, and the only case
// testable here - the front-end falls back to the standalone `emotionsim run`
// subprocess path that the CLI documents as needing no server at all.
package tui

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"charm.land/bubbles/v2/cursor"
	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"charm.land/lipgloss/v2"
	"github.com/gorilla/websocket"

	"github.com/jasperan/emotion-engine/gotui/internal/api"
	"github.com/jasperan/emotion-engine/gotui/internal/huhstyle"
	"github.com/jasperan/emotion-engine/gotui/internal/sim"
)

// probeTimeout bounds the startup scenario probe. It is deliberately shorter
// than the client's own timeout: a wizard that freezes for five seconds before
// appearing is worse than one that appears immediately and says the engine is
// not running.
const probeTimeout = 2 * time.Second

// maxEvents caps the monitor log so a long run cannot grow without bound.
const maxEvents = 500

// Backend names accepted by RunCreate.llm_backend
// (emotionsim/schemas/run.py:12). The empty value means "scenario default".
var backends = []string{"ollama", "vllm", "openai"}

type mode int

const (
	modeWizard mode = iota
	modeStarting
	modeMonitoring
	modeFallback
	modeFailed
)

// Preset carries the flag-supplied answers so a caller can pre-fill the wizard,
// or skip it entirely.
type Preset struct {
	Scenario   string
	MaxSteps   int
	Seed       *int
	TickDelay  *float64
	Verbose    bool
	Simple     bool
	LLMBackend string
}

// Answers holds every form-bound value. It is always heap-allocated and bound
// by pointer: binding a field of a value-typed Bubble Tea model silently
// persists defaults, because the receiver copy the form writes to is discarded.
type Answers struct {
	Scenario   string
	MaxSteps   string
	Seed       string
	TickDelay  string
	LLMBackend string
	Verbose    bool
	Simple     bool
	Start      bool
}

// RunOptions resolves and validates the answers into engine options.
func (a *Answers) RunOptions() (sim.RunOptions, error) {
	out := sim.RunOptions{
		Scenario:  strings.TrimSpace(a.Scenario),
		Verbose:   a.Verbose,
		Simple:    a.Simple,
		ForceVLLM: nil,
	}
	if out.Scenario == "" {
		return out, fmt.Errorf("a scenario is required")
	}

	if raw := strings.TrimSpace(a.MaxSteps); raw != "" {
		n, err := strconv.Atoi(raw)
		if err != nil {
			return out, fmt.Errorf("max steps %q is not a whole number", raw)
		}
		if n < 1 {
			return out, fmt.Errorf("max steps must be at least 1, got %d", n)
		}
		out.MaxSteps = n
	}

	if raw := strings.TrimSpace(a.Seed); raw != "" {
		n, err := strconv.Atoi(raw)
		if err != nil {
			return out, fmt.Errorf("seed %q is not a whole number", raw)
		}
		out.Seed = &n
	}

	if raw := strings.TrimSpace(a.TickDelay); raw != "" {
		f, err := strconv.ParseFloat(raw, 64)
		if err != nil {
			return out, fmt.Errorf("tick delay %q is not a number", raw)
		}
		if f < 0 {
			return out, fmt.Errorf("tick delay must not be negative, got %v", f)
		}
		out.TickDelay = &f
	}

	// The backend override is deliberately resolved by Backend(), not here:
	// RunOptions carries the CLI's force-vllm pointer, which the API path never
	// uses. Keeping one resolver avoids the two drifting apart.
	return out, nil
}

// Backend returns the llm_backend to send to the API, or "" for the default.
func (a *Answers) Backend() string {
	raw := strings.TrimSpace(a.LLMBackend)
	for _, b := range backends {
		if b == raw {
			return raw
		}
	}
	return ""
}

// Model is the Bubble Tea model for the whole front-end.
type Model struct {
	ep     sim.Endpoint
	client *api.Client

	answers *Answers
	form    *huh.Form

	scenarios    []api.Scenario
	scenarioName map[string]string // id -> label, for the standalone argv
	probeErr     error

	mode   mode
	run    *api.Run
	events []string
	status string
	err    error

	eventsCh chan tea.Msg
	conn     *websocket.Conn

	// pendingSubscribe is set only by NewMonitor: it is the run to attach to
	// before the program starts, with no wizard in front of it.
	pendingSubscribe string

	width  int
	height int
	quit   bool
}

// New builds the front-end. The scenario probe happens here, synchronously, so
// the wizard knows whether to offer a picker or a typed name before it renders.
func New(ctx context.Context, ep sim.Endpoint, client *api.Client, preset Preset) Model {
	m := Model{
		ep:           ep,
		client:       client,
		answers:      &Answers{},
		scenarioName: map[string]string{},
		width:        100,
		height:       30,
	}

	probeCtx, cancel := context.WithTimeout(ctx, probeTimeout)
	defer cancel()
	if client != nil {
		if scenarios, err := client.ListScenarios(probeCtx); err != nil {
			m.probeErr = err
		} else {
			m.scenarios = scenarios
			for _, s := range scenarios {
				m.scenarioName[s.ID] = s.Label()
			}
		}
	}

	m.applyPreset(preset)
	m.form = m.buildForm()
	return m
}

func (m *Model) applyPreset(p Preset) {
	m.answers.Scenario = p.Scenario
	if p.MaxSteps > 0 {
		m.answers.MaxSteps = strconv.Itoa(p.MaxSteps)
	}
	if p.Seed != nil {
		m.answers.Seed = strconv.Itoa(*p.Seed)
	}
	if p.TickDelay != nil {
		m.answers.TickDelay = strconv.FormatFloat(*p.TickDelay, 'f', -1, 64)
	}
	m.answers.Verbose = p.Verbose
	m.answers.Simple = p.Simple
	if p.LLMBackend != "" {
		m.answers.LLMBackend = p.LLMBackend
	}
}

// buildForm builds the two-page wizard. Page one gathers the run options and
// page two restates them for confirmation, so nothing is submitted unseen.
func (m *Model) buildForm() *huh.Form {
	first := huh.NewGroup(m.configFields()...).Title("Simulation").Description(m.engineStatusText())

	second := huh.NewGroup(
		huh.NewNote().
			Title("Ready to run").
			DescriptionFunc(m.summary, m.answers),
		huh.NewConfirm().
			Title("Start this run?").
			Affirmative("Start").
			Negative("Cancel").
			Value(&m.answers.Start),
	).Title("Review")

	return huh.NewForm(first, second).
		WithTheme(huh.ThemeFunc(huhstyle.Theme)).
		WithAccessible(huhstyle.Accessible()).
		WithShowHelp(true).
		WithWidth(m.width)
}

// configFields returns page one's fields, choosing a picker or a typed name
// depending on whether the engine answered the probe.
func (m *Model) configFields() []huh.Field {
	var scenario huh.Field
	if len(m.scenarios) > 0 {
		// Static Options only: OptionsFunc resolves asynchronously and is empty
		// under accessible mode, and Options() silently ignores an empty slice.
		opts := make([]huh.Option[string], 0, len(m.scenarios))
		for _, s := range m.scenarios {
			opts = append(opts, huh.NewOption(s.Label(), s.ID))
		}
		scenario = huh.NewSelect[string]().
			Title("Scenario").
			Description("Fetched from the running engine.").
			Options(opts...).
			// Select.Height excludes the frame and defaults to 0, which renders
			// an option-less box; keep it to a readable page.
			Height(min(len(opts), 8)).
			Value(&m.answers.Scenario)
	} else {
		scenario = huh.NewInput().
			Title("Scenario").
			Description("Engine unreachable, so type a scenario name. It will run standalone.").
			Placeholder("Rising Flood").
			Value(&m.answers.Scenario).
			Validate(huh.ValidateNotEmpty())
	}

	fields := []huh.Field{scenario}

	var backendOptions []huh.Option[string]
	backendOptions = append(backendOptions, huh.NewOption("scenario default", ""))
	for _, b := range backends {
		backendOptions = append(backendOptions, huh.NewOption(b, b))
	}

	fields = append(fields,
		huh.NewInput().
			Title("Max steps").
			Description("Blank keeps the scenario's own limit.").
			Placeholder("scenario default").
			Value(&m.answers.MaxSteps).
			Validate(validateOptionalInt("max steps", 1)),
		huh.NewInput().
			Title("Seed").
			Description("Blank lets the engine choose.").
			Placeholder("random").
			Value(&m.answers.Seed).
			Validate(validateOptionalInt("seed", 0)),
		huh.NewInput().
			Title("Tick delay (seconds)").
			Description("Blank uses the engine default.").
			Placeholder("engine default").
			Value(&m.answers.TickDelay).
			Validate(validateOptionalFloat("tick delay")),
		huh.NewSelect[string]().
			Title("LLM backend").
			Description("Overrides the scenario's provider for this run.").
			Options(backendOptions...).
			Height(len(backendOptions)).
			Value(&m.answers.LLMBackend),
		huh.NewConfirm().
			Title("Verbose logging?").
			Description("Timestamps every LLM call with token and context counts.").
			Affirmative("Verbose").
			Negative("Normal").
			Value(&m.answers.Verbose),
		huh.NewConfirm().
			Title("Simple output?").
			Description("Plain log lines instead of the rich renderer.").
			Affirmative("Simple").
			Negative("Rich").
			Value(&m.answers.Simple),
	)
	return fields
}

// engineStatusText tells the user which of the two run modes the wizard is in.
func (m *Model) engineStatusText() string {
	if len(m.scenarios) > 0 {
		return fmt.Sprintf("%d scenarios loaded from %s", len(m.scenarios), m.ep.RESTBase)
	}
	if m.probeErr != nil {
		return fmt.Sprintf("Engine unreachable at %s; runs will use the standalone CLI.", m.ep.RESTBase)
	}
	return "No scenarios available from the engine; runs will use the standalone CLI."
}

// summary is the review page body. It is recomputed on every render, so the
// confirmation always restates the answers as they stand.
func (m *Model) summary() string {
	opts, err := m.answers.RunOptions()
	if err != nil {
		return errStyle.Render(err.Error())
	}
	plan := m.plan(opts)

	lines := []string{
		label("Scenario", plan.Scenario),
		label("Max steps", plan.MaxSteps),
		label("Seed", plan.Seed),
		label("Tick delay", plan.TickDelay),
		label("Backend", plan.Backend),
	}
	return strings.Join(lines, "\n")
}

type planView struct {
	Scenario  string
	MaxSteps  string
	Seed      string
	TickDelay string
	Backend   string
	argv      []string
}

func (m *Model) plan(opts sim.RunOptions) planView {
	p := planView{Scenario: opts.Scenario, MaxSteps: "scenario default", Seed: "random", TickDelay: "engine default", Backend: "scenario default"}

	// Prefer the engine's id when the scenario came from the picker, because
	// that is what POST /api/runs/ wants; the argv path wants the label.
	scenarioForArgv := opts.Scenario
	if label, ok := m.scenarioName[opts.Scenario]; ok {
		p.Scenario = fmt.Sprintf("%s (%s)", label, opts.Scenario)
		scenarioForArgv = label
	}
	if opts.MaxSteps > 0 {
		p.MaxSteps = strconv.Itoa(opts.MaxSteps)
	}
	if opts.Seed != nil {
		p.Seed = strconv.Itoa(*opts.Seed)
	}
	if opts.TickDelay != nil {
		p.TickDelay = strconv.FormatFloat(*opts.TickDelay, 'f', -1, 64)
	}
	if backend := m.answers.Backend(); backend != "" {
		p.Backend = backend
	}

	argvOpts := opts
	argvOpts.Scenario = scenarioForArgv
	if argv, err := sim.RunArgs(argvOpts); err == nil {
		p.argv = argv
	}
	return p
}

func label(k, v string) string {
	return fmt.Sprintf("%s  %s", mutedStyle.Render(lipgloss.NewStyle().Width(12).Render(k)), bodyStyle.Render(v))
}

// --- messages ---

type scenariosMsg struct{ err error }
type runCreatedMsg struct {
	run *api.Run
	err error
}
type runStartedMsg struct{ err error }
type subscribedMsg struct{ conn *websocket.Conn }
type dialFailedMsg struct{ err error }
type wsEventMsg struct {
	Event     string         `json:"event"`
	Data      map[string]any `json:"data"`
	Timestamp string         `json:"timestamp"`
}
type streamClosedMsg struct{}

// --- lifecycle ---

// NewMonitor builds a front-end that goes straight to monitoring an existing
// run, mirroring `emotionsim monitor --run-id`. It deliberately skips the
// scenario probe: a monitor does not need the scenario list, and waiting on a
// probe would be the first thing the user sees.
func NewMonitor(ep sim.Endpoint, client *api.Client, runID string) Model {
	m := Model{
		ep:               ep,
		client:           client,
		answers:          &Answers{},
		scenarioName:     map[string]string{},
		width:            100,
		height:           30,
		mode:             modeMonitoring,
		status:           "connecting",
		run:              &api.Run{ID: strings.TrimSpace(runID)},
		pendingSubscribe: strings.TrimSpace(runID),
		eventsCh:         make(chan tea.Msg, 64),
	}
	return m
}

// Init starts the form, or subscribes immediately when there is no form.
func (m Model) Init() tea.Cmd {
	if m.form == nil {
		if m.pendingSubscribe == "" {
			return nil
		}
		return subscribeCmd(m.ep, m.pendingSubscribe, m.eventsCh)
	}
	return m.form.Init()
}

// Update routes messages: the wizard owns input until it completes, then the
// run is created and the monitor takes over.
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		if m.form != nil {
			m.form = m.form.WithWidth(msg.Width)
		}
		return m, nil

	case wsEventMsg:
		m.appendEvent(msg)
		return m, waitForEvent(m.eventsCh)

	case subscribedMsg:
		m.conn = msg.conn
		m.status = "streaming"
		return m, waitForEvent(m.eventsCh)

	case dialFailedMsg:
		m.appendEvent(wsEventMsg{Event: "monitor_error", Data: map[string]any{"error": msg.err.Error()}})
		m.status = "monitor unavailable"
		return m, nil

	case streamClosedMsg:
		m.status = "stream closed"
		return m, nil

	case runCreatedMsg:
		if msg.err != nil {
			m.mode = modeFailed
			m.err = msg.err
			return m, nil
		}
		m.run = msg.run
		m.status = "created " + msg.run.ID
		return m, func() tea.Msg {
			err := m.client.ControlRun(context.Background(), msg.run.ID, "start")
			return runStartedMsg{err: err}
		}

	case runStartedMsg:
		if msg.err != nil {
			m.mode = modeFailed
			m.err = msg.err
			return m, nil
		}
		m.mode = modeMonitoring
		m.status = "running"
		m.eventsCh = make(chan tea.Msg, 64)
		return m, func() tea.Msg { return subscribeCmd(m.ep, m.run.ID, m.eventsCh)() }
	}

	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c":
			if m.mode != modeWizard {
				m.quit = true
				if m.conn != nil {
					_ = m.conn.Close()
				}
				return m, tea.Quit
			}
		}
	}

	if m.mode == modeWizard && m.form != nil {
		form, cmd := m.form.Update(msg)
		if f, ok := form.(*huh.Form); ok {
			m.form = f
		}
		switch m.form.State {
		case huh.StateCompleted:
			return m.submit()
		case huh.StateAborted:
			m.quit = true
			return m, tea.Quit
		}
		return m, cmd
	}

	return m, nil
}

// submit decides between the API path and the standalone fallback, and never
// guesses: the fallback is chosen exactly when the engine could not be reached.
func (m Model) submit() (tea.Model, tea.Cmd) {
	if !m.answers.Start {
		m.quit = true
		return m, tea.Quit
	}
	opts, err := m.answers.RunOptions()
	if err != nil {
		m.mode = modeFailed
		m.err = err
		return m, nil
	}

	if len(m.scenarios) == 0 || m.client == nil {
		// No engine: the CLI's standalone `run` needs no server at all.
		m.mode = modeFallback
		m.status = "standalone"
		return m, nil
	}

	m.mode = modeStarting
	m.status = "creating run"
	client := m.client
	req := api.RunCreate{
		ScenarioID: opts.Scenario,
		Seed:       opts.Seed,
		MaxSteps:   opts.MaxSteps,
		LLMBackend: m.answers.Backend(),
	}
	return m, func() tea.Msg {
		run, err := client.CreateRun(context.Background(), req)
		return runCreatedMsg{run: run, err: err}
	}
}

func (m *Model) appendEvent(ev wsEventMsg) {
	line := ev.Event
	switch ev.Event {
	case "step_completed":
		if step, ok := ev.Data["step"]; ok {
			line = fmt.Sprintf("%s step %v", ev.Event, step)
		}
	}
	if summary := summarise(ev.Data); summary != "" {
		line = line + "  " + summary
	}
	m.events = append(m.events, line)
	if len(m.events) > maxEvents {
		m.events = m.events[len(m.events)-maxEvents:]
	}
}

func summarise(data map[string]any) string {
	if len(data) == 0 {
		return ""
	}
	raw, err := json.Marshal(data)
	if err != nil {
		return ""
	}
	const limit = 120
	s := string(raw)
	if len(s) > limit {
		return s[:limit] + "..."
	}
	return s
}

// --- commands ---

// subscribeCmd dials the run's socket and starts its read pump. The pump owns
// the channel and closes it on exit, so the model only has to stop waiting.
func subscribeCmd(ep sim.Endpoint, runID string, ch chan tea.Msg) tea.Cmd {
	return func() tea.Msg {
		url, err := ep.RunURL(runID)
		if err != nil {
			return dialFailedMsg{err: err}
		}
		dialer := websocket.Dialer{HandshakeTimeout: 5 * time.Second}
		conn, resp, err := dialer.Dial(url, nil)
		if err != nil {
			if resp != nil {
				return dialFailedMsg{err: fmt.Errorf("dial %s: HTTP %d", url, resp.StatusCode)}
			}
			return dialFailedMsg{err: fmt.Errorf("dial %s: %w", url, err)}
		}
		go readPump(conn, ch)
		return subscribedMsg{conn: conn}
	}
}

func readPump(conn *websocket.Conn, ch chan tea.Msg) {
	defer close(ch)
	defer func() { _ = conn.Close() }()
	for {
		_, raw, err := conn.ReadMessage()
		if err != nil {
			return
		}
		var ev wsEventMsg
		if err := json.Unmarshal(raw, &ev); err != nil {
			continue
		}
		if ev.Event == "" {
			continue
		}
		ch <- ev
	}
}

func waitForEvent(ch <-chan tea.Msg) tea.Cmd {
	if ch == nil {
		return nil
	}
	return func() tea.Msg {
		msg, ok := <-ch
		if !ok {
			return streamClosedMsg{}
		}
		return msg
	}
}

// --- rendering ---

// View renders the wizard, the monitor, or the terminal state. tea.View (not a
// bare string) is what bubbletea v2 requires.
func (m Model) View() tea.View {
	if m.quit {
		return tea.NewView("")
	}

	var body string
	switch m.mode {
	case modeWizard:
		body = m.form.View()
	case modeStarting:
		body = titleStyle.Render("Starting run") + "\n\n" + m.status
	case modeMonitoring:
		body = m.monitorView()
	case modeFallback:
		body = m.fallbackView()
	case modeFailed:
		body = m.failedView()
	}

	return tea.NewView(body + "\n" + m.footer())
}

func (m Model) monitorView() string {
	var b strings.Builder
	heading := "Monitor"
	if m.run != nil {
		heading = fmt.Sprintf("Monitor  %s  (%s)", m.run.ID, m.run.ScenarioID)
	}
	b.WriteString(titleStyle.Render(heading) + "\n")
	if m.status != "" {
		b.WriteString(mutedStyle.Render(m.status) + "\n")
	}
	b.WriteString("\n")

	if len(m.events) == 0 {
		b.WriteString(mutedStyle.Render("Waiting for events...") + "\n")
	} else {
		for _, ev := range m.events {
			b.WriteString("  " + bodyStyle.Render(ev) + "\n")
		}
	}
	return b.String()
}

// fallbackView is the standalone path: it shows the exact command that will run
// instead of pretending a server exists.
func (m Model) fallbackView() string {
	opts, err := m.answers.RunOptions()
	if err != nil {
		return m.failedView()
	}
	p := m.plan(opts)

	var b strings.Builder
	b.WriteString(titleStyle.Render("Standalone run") + "\n")
	b.WriteString(mutedStyle.Render("No engine answered, so this runs the CLI directly:") + "\n\n")
	b.WriteString("  " + bodyStyle.Render(strings.Join(append([]string{sim.DefaultBinary}, p.argv...), " ")) + "\n\n")
	b.WriteString(metaStyle.Render("Run it from a shell to watch the simulation.") + "\n")
	return b.String()
}

func (m Model) failedView() string {
	var b strings.Builder
	b.WriteString(titleStyle.Render("Failed") + "\n\n")
	if m.err != nil {
		b.WriteString(errStyle.Render(m.err.Error()) + "\n\n")
	}
	b.WriteString(metaStyle.Render("The engine may simply not be running.") + "\n")
	b.WriteString(metaStyle.Render("Start it with: emotionsim dev") + "\n")
	return b.String()
}

func (m Model) footer() string {
	hint := "q quit"
	switch m.mode {
	case modeWizard:
		hint = "enter next  shift+tab back  ctrl+c quit"
	case modeFallback:
		hint = "q quit"
	}
	return barStyle.Width(m.width).Render(mutedStyle.Render(hint))
}

// min returns the smaller of two ints. Go 1.21's builtin min is not used here
// so the intent stays explicit at the call site.
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// --- validators ---

// validateOptionalInt accepts a blank value (meaning "leave it to the engine")
// and otherwise requires a whole number at or above min.
func validateOptionalInt(field string, min int) func(string) error {
	return func(s string) error {
		raw := strings.TrimSpace(s)
		if raw == "" {
			return nil
		}
		n, err := strconv.Atoi(raw)
		if err != nil {
			return fmt.Errorf("%s must be a whole number", field)
		}
		if n < min {
			return fmt.Errorf("%s must be at least %d", field, min)
		}
		return nil
	}
}

func validateOptionalFloat(field string) func(string) error {
	return func(s string) error {
		raw := strings.TrimSpace(s)
		if raw == "" {
			return nil
		}
		f, err := strconv.ParseFloat(raw, 64)
		if err != nil {
			return fmt.Errorf("%s must be a number", field)
		}
		if f < 0 {
			return fmt.Errorf("%s must not be negative", field)
		}
		return nil
	}
}

// drainBlink is re-exported for tests: a blink tick carries no state, and
// feeding one back into Update re-arms the ~530ms timer forever.
func drainBlink(msg tea.Msg) bool {
	_, isBlink := msg.(cursor.BlinkMsg)
	return isBlink
}
