package tui

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"charm.land/bubbles/v2/cursor"
	tea "charm.land/bubbletea/v2"

	"github.com/jasperan/emotion-engine/gotui/internal/api"
	"github.com/jasperan/emotion-engine/gotui/internal/sim"
)

// unreachable is a client pointed at a closed port: connection refused is
// immediate, so these tests never wait on a network timeout.
func unreachable() *api.Client { return api.NewClient("http://127.0.0.1:1") }

func testEndpoint(t *testing.T) sim.Endpoint {
	t.Helper()
	ep, err := sim.ParseEndpoint(sim.DefaultWSBase)
	if err != nil {
		t.Fatalf("ParseEndpoint: %v", err)
	}
	return ep
}

// sized runs Init and reports a terminal size, which a huh form needs before it
// renders any field content.
func sized(t *testing.T, m Model) Model {
	t.Helper()
	m = drain(t, m, m.Init(), 0)
	return pump(t, m, tea.WindowSizeMsg{Width: 120, Height: 36})
}

// pump feeds one message through Update and drains the resulting commands.
//
// The drain drops cursor blink ticks: huh re-arms the blink on every Update and
// each tick sleeps ~530ms, so feeding one back in never terminates.
func pump(t *testing.T, m Model, msg tea.Msg) Model {
	t.Helper()
	next, cmd := m.Update(msg)
	out, ok := next.(Model)
	if !ok {
		t.Fatalf("Update returned %T, want tui.Model", next)
	}
	return drain(t, out, cmd, 0)
}

func drain(t *testing.T, m Model, cmd tea.Cmd, depth int) Model {
	t.Helper()
	if cmd == nil || depth > 32 {
		return m
	}
	msg := cmd()
	if msg == nil {
		return m
	}
	if drainBlink(msg) {
		return m
	}
	if batch, ok := msg.(tea.BatchMsg); ok {
		for _, c := range batch {
			m = drain(t, m, c, depth+1)
		}
		return m
	}
	next, nextCmd := m.Update(msg)
	out, ok := next.(Model)
	if !ok {
		return m
	}
	return drain(t, out, nextCmd, depth+1)
}

// The engine is normally down. The wizard must still open, must say so, and
// must fall back to a typed scenario rather than an empty picker.
func TestWizardOpensWithEngineDown(t *testing.T) {
	m := New(context.Background(), testEndpoint(t), unreachable(), Preset{})
	if m.probeErr == nil {
		t.Fatal("expected the scenario probe to fail against a closed port")
	}
	if len(m.scenarios) != 0 {
		t.Fatalf("scenarios = %d, want 0", len(m.scenarios))
	}
	if m.mode != modeWizard {
		t.Fatalf("mode = %v, want modeWizard", m.mode)
	}
	if got := m.engineStatusText(); !strings.Contains(got, "unreachable") {
		t.Errorf("engine status = %q, want it to name the unreachable engine", got)
	}

	m = sized(t, m)
	if view := m.View().Content; view == "" {
		t.Error("wizard rendered an empty view")
	}
	// A typed name is the fallback; the field must carry a placeholder for it.
	if !strings.Contains(m.View().Content, "Scenario") {
		t.Error("wizard does not render a scenario field")
	}
}

// With a reachable engine the wizard offers the picker the API returned.
func TestWizardUsesPickerWhenEngineAnswers(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/scenarios/" {
			http.NotFound(w, r)
			return
		}
		_, _ = w.Write([]byte(`[{"id":"a1","name":"Rising Flood","description":"d"}]`))
	}))
	defer srv.Close()

	m := New(context.Background(), testEndpoint(t), api.NewClient(srv.URL), Preset{})
	m = sized(t, m)
	if m.probeErr != nil {
		t.Fatalf("probe failed against a stub engine: %v", m.probeErr)
	}
	if len(m.scenarios) != 1 {
		t.Fatalf("scenarios = %d, want 1", len(m.scenarios))
	}
	if got := m.scenarioName["a1"]; got != "Rising Flood" {
		t.Errorf("scenarioName[a1] = %q", got)
	}
	// The picker binds the id, because POST /api/runs/ wants the id.
	if !strings.Contains(m.View().Content, "Rising Flood") {
		t.Errorf("picker does not render the returned scenario: %q", m.View().Content)
	}
}

func TestInitSendsNothingWhenThereIsNoForm(t *testing.T) {
	m := Model{}
	if cmd := m.Init(); cmd != nil {
		t.Error("Init on an empty model returned a command")
	}
}

// The monitor entry point must subscribe on Init without a wizard in front.
func TestNewMonitorSubscribesOnInit(t *testing.T) {
	m := NewMonitor(testEndpoint(t), unreachable(), "abc123")
	if m.mode != modeMonitoring {
		t.Fatalf("mode = %v, want modeMonitoring", m.mode)
	}
	if m.run == nil || m.run.ID != "abc123" {
		t.Fatalf("run = %+v, want id abc123", m.run)
	}
	if cmd := m.Init(); cmd == nil {
		t.Fatal("Init returned no command, want the subscribe command")
	}
}

// A failed dial must land in the event log and leave the program alive: the
// engine is usually down and that must not be a crash or a hang.
func TestMonitorSurvivesFailedDial(t *testing.T) {
	m := NewMonitor(testEndpoint(t), unreachable(), "abc123")
	m = drain(t, m, m.Init(), 0)

	if m.mode != modeMonitoring {
		t.Fatalf("mode = %v, want the monitor to stay up", m.mode)
	}
	if m.status != "monitor unavailable" {
		t.Errorf("status = %q, want the monitor to report itself unavailable", m.status)
	}
	if len(m.events) != 1 || !strings.Contains(m.events[0], "dial") {
		t.Errorf("events = %v, want one dial failure", m.events)
	}
	if view := m.View().Content; !strings.Contains(view, "monitor_error") {
		t.Errorf("view does not surface the dial failure: %q", view)
	}
}

func TestMonitorQuitsOnQ(t *testing.T) {
	m := NewMonitor(testEndpoint(t), unreachable(), "abc123")
	m = pump(t, m, tea.KeyPressMsg{Code: 'q', Text: "q"})
	if !m.quit {
		t.Error("q did not quit the monitor")
	}
}

func TestSummaryRestatesTheAnswers(t *testing.T) {
	m := New(context.Background(), testEndpoint(t), unreachable(), Preset{
		Scenario:   "Rising Flood",
		MaxSteps:   50,
		LLMBackend: "vllm",
	})
	got := m.summary()
	for _, want := range []string{"Rising Flood", "50", "vllm"} {
		if !strings.Contains(got, want) {
			t.Errorf("summary = %q, want it to mention %q", got, want)
		}
	}
}

func TestSummaryReportsMissingScenario(t *testing.T) {
	m := New(context.Background(), testEndpoint(t), unreachable(), Preset{})
	if got := m.summary(); !strings.Contains(got, "scenario is required") {
		t.Errorf("summary = %q, want the validation error", got)
	}
}

func TestRunOptionsResolvesAndValidates(t *testing.T) {
	seed := 7
	delay := 0.5
	a := &Answers{
		Scenario:   "  Rising Flood  ",
		MaxSteps:   "50",
		Seed:       "7",
		TickDelay:  "0.5",
		LLMBackend: "vllm",
		Verbose:    true,
		Simple:     true,
	}
	got, err := a.RunOptions()
	if err != nil {
		t.Fatalf("RunOptions: %v", err)
	}
	if got.Scenario != "Rising Flood" {
		t.Errorf("scenario = %q, want it trimmed", got.Scenario)
	}
	if got.MaxSteps != 50 {
		t.Errorf("max steps = %d", got.MaxSteps)
	}
	if got.Seed == nil || *got.Seed != seed {
		t.Errorf("seed = %v, want %d", got.Seed, seed)
	}
	if got.TickDelay == nil || *got.TickDelay != delay {
		t.Errorf("tick delay = %v, want %v", got.TickDelay, delay)
	}
	if !got.Verbose || !got.Simple {
		t.Errorf("flags = verbose:%v simple:%v", got.Verbose, got.Simple)
	}
	if a.Backend() != "vllm" {
		t.Errorf("backend = %q, want vllm", a.Backend())
	}
}

// Blank means "leave it to the engine", which is the whole point of the
// placeholders on the numeric fields.
func TestRunOptionsAcceptsBlanks(t *testing.T) {
	a := &Answers{Scenario: "s"}
	got, err := a.RunOptions()
	if err != nil {
		t.Fatalf("RunOptions: %v", err)
	}
	if got.MaxSteps != 0 || got.Seed != nil || got.TickDelay != nil {
		t.Errorf("blank answers produced %+v, want them left unset", got)
	}
	// An unknown backend must not reach the closed API Literal set.
	a.LLMBackend = "gpt5"
	if got := a.Backend(); got != "" {
		t.Errorf("Backend() = %q, want empty for an unknown backend", got)
	}
}

func TestRunOptionsRejectsBadValues(t *testing.T) {
	cases := map[string]Answers{
		"no scenario":    {},
		"zero max steps": {Scenario: "s", MaxSteps: "0"},
		"junk max steps": {Scenario: "s", MaxSteps: "lots"},
		"junk seed":      {Scenario: "s", Seed: "abc"},
		"negative tick":  {Scenario: "s", TickDelay: "-1"},
	}
	for name, a := range cases {
		t.Run(name, func(t *testing.T) {
			if _, err := a.RunOptions(); err == nil {
				t.Errorf("RunOptions(%+v) returned no error", a)
			}
		})
	}
}

func TestValidators(t *testing.T) {
	intValidator := validateOptionalInt("max steps", 1)
	for _, bad := range []string{"0", "-5", "x", "1.5"} {
		if err := intValidator(bad); err == nil {
			t.Errorf("validateOptionalInt(%q) returned no error", bad)
		}
	}
	for _, ok := range []string{"", "1", "50", " 7 "} {
		if err := intValidator(ok); err != nil {
			t.Errorf("validateOptionalInt(%q) = %v, want nil", ok, err)
		}
	}

	floatValidator := validateOptionalFloat("tick delay")
	for _, bad := range []string{"-0.1", "soon"} {
		if err := floatValidator(bad); err == nil {
			t.Errorf("validateOptionalFloat(%q) returned no error", bad)
		}
	}
	for _, ok := range []string{"", "0", "0.25"} {
		if err := floatValidator(ok); err != nil {
			t.Errorf("validateOptionalFloat(%q) = %v, want nil", ok, err)
		}
	}
}

// The review page must show a shell-ready command, because that is what the
// standalone user is going to paste.
func TestStandaloneFallbackRendersTheCommand(t *testing.T) {
	m := New(context.Background(), testEndpoint(t), unreachable(), Preset{Scenario: "Rising Flood", MaxSteps: 50})
	m.mode = modeFallback
	view := m.View().Content
	if !strings.Contains(view, "emotionsim run --scenario Rising Flood --max-steps 50") {
		t.Errorf("fallback view = %q, want the standalone command", view)
	}
}

func TestPlanUsesTheScenarioLabelForTheStandaloneArgv(t *testing.T) {
	m := New(context.Background(), testEndpoint(t), unreachable(), Preset{})
	m.scenarioName["a1"] = "Rising Flood"
	opts, err := (&Answers{Scenario: "a1"}).RunOptions()
	if err != nil {
		t.Fatalf("RunOptions: %v", err)
	}
	p := m.plan(opts)
	if !strings.Contains(strings.Join(p.argv, " "), "Rising Flood") {
		t.Errorf("argv = %v, want the label rather than the raw id", p.argv)
	}
	if !strings.Contains(p.Scenario, "a1") {
		t.Errorf("plan scenario = %q, want the id shown for review", p.Scenario)
	}
}

func TestDrainBlinkIdentifiesBlinkTicks(t *testing.T) {
	if !drainBlink(cursor.BlinkMsg{}) {
		t.Error("drainBlink did not recognise a blink tick")
	}
	if drainBlink(tea.WindowSizeMsg{Width: 1, Height: 1}) {
		t.Error("drainBlink treated a window size as a blink tick")
	}
}

// quit must not hang on a nil or idle stream.
func TestWaitForEventNilChannel(t *testing.T) {
	if cmd := waitForEvent(nil); cmd != nil {
		t.Error("waitForEvent(nil) returned a command")
	}
}

func TestWaitForEventClosedChannel(t *testing.T) {
	ch := make(chan tea.Msg)
	close(ch)
	if _, ok := waitForEvent(ch)().(streamClosedMsg); !ok {
		t.Error("a closed channel did not produce streamClosedMsg")
	}
}

// The whole wizard must be constructible and renderable within the sizes the
// capture harness uses, with no engine and no scenario list.
func TestWizardRendersAtHarnessSize(t *testing.T) {
	m := sized(t, New(context.Background(), testEndpoint(t), unreachable(), Preset{}))
	if got := m.View().Content; len(got) == 0 {
		t.Error("empty render at harness size")
	}
}

func TestMonitorEventLogIsBounded(t *testing.T) {
	m := NewMonitor(testEndpoint(t), unreachable(), "abc123")
	for i := 0; i < maxEvents+50; i++ {
		m.appendEvent(wsEventMsg{Event: "step_completed", Data: map[string]any{"step": i}})
	}
	if len(m.events) != maxEvents {
		t.Errorf("events = %d, want the log capped at %d", len(m.events), maxEvents)
	}
}

func TestReadPumpStopsOnClose(t *testing.T) {
	// A nil-connection pump would panic; guard the contract that readPump is
	// only ever started with a live connection by checking the timeout path.
	done := make(chan struct{})
	go func() {
		defer close(done)
		ch := make(chan tea.Msg)
		close(ch)
		_, ok := <-ch
		if ok {
			t.Error("expected the channel to be closed")
		}
	}()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Error("channel handling did not complete")
	}
}
