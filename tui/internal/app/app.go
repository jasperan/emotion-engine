package app

import (
	"fmt"
	"strings"

	tea "charm.land/bubbletea/v2"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/components"
)

// ProgramRef holds a shared reference to the tea.Program.
// Because App uses value receivers (Elm architecture), we need
// a pointer-indirection so all copies share the same program ref.
type ProgramRef struct {
	P *tea.Program
}

// Screen identifies the active screen.
type Screen int

const (
	ScreenSplash Screen = iota
	ScreenScenarios
	ScreenLauncher
	ScreenDashboard
	ScreenTheater
	ScreenHistory
	ScreenReplay
	ScreenAnalytics
)

// SwitchScreenMsg requests a transition to a different screen.
type SwitchScreenMsg struct {
	Screen Screen
	Data   interface{}
}

// switchTo requests a screen transition with no payload.
func switchTo(screen Screen) tea.Cmd {
	return func() tea.Msg { return SwitchScreenMsg{Screen: screen} }
}

// switchToData requests a screen transition carrying a screen payload, which
// the router reads back as the scenario or run id.
func switchToData(screen Screen, data interface{}) tea.Cmd {
	return func() tea.Msg { return SwitchScreenMsg{Screen: screen, Data: data} }
}

// formContentWidth is the usable width for a huh form: the terminal less the
// margins the screens place around the body, clamped so a form stays readable
// on a narrow terminal and does not sprawl on a wide one.
func formContentWidth(width int) int {
	if width <= 0 {
		return 64
	}
	contentWidth := width - 10
	if contentWidth < 36 {
		contentWidth = 36
	}
	if contentWidth > 84 {
		contentWidth = 84
	}
	return contentWidth
}

// selectHeight returns the height to set on a Select, or 0 when every option
// fits.
//
// huh sizes a Select's viewport to the option count when no height is set, and
// pads it out to the height when one is. Sizing it for a short list would
// therefore leave a hole inside the field's border, so the height is only set
// when the options would otherwise overflow.
func selectHeight(screenHeight, options int) int {
	// Rows left for options after the screen chrome and the Select's own title
	// and description lines.
	rows := screenHeight - 14
	if rows < 1 {
		rows = 1
	}
	if options <= rows {
		return 0
	}
	// The height also covers the title and description the viewport is offset by.
	return rows + 2
}

// formHeight bounds a form's height to the rows left over after the screen's
// own chrome (title block, hovered-item line, footer hints and margins).
//
// A form needs this because huh sizes each group's viewport from the height of
// its fields BEFORE the theme is applied: the rounded field cards are taller
// than the built-in styles assume, so without it the last field is scrolled out
// of view on a roomy terminal. Groups pad themselves out to this height, which
// trimFormPad removes again; when the room really is too small huh scrolls to
// the focused field, which is the right fallback.
func formHeight(height int) int {
	h := height - 12
	if h < 9 {
		h = 9
	}
	if h > 30 {
		h = 30
	}
	return h
}

// trimFormPad drops the blank rows a huh group pads itself out to the height
// set by formHeight. Without this the pad sits between the last field and the
// screen's own hint bar, which reads as a hole in the layout. The forms hide
// huh's help footer (the screens already draw one), so the pad is always the
// trailing run of blank lines.
func trimFormPad(view string) string {
	lines := strings.Split(view, "\n")
	for len(lines) > 0 && strings.TrimSpace(lines[len(lines)-1]) == "" {
		lines = lines[:len(lines)-1]
	}
	return strings.Join(lines, "\n")
}

// WSEventMsg wraps a WebSocket event for the Bubble Tea update loop.
type WSEventMsg struct {
	Event api.WSMessage
}

// WSErrorMsg signals a WebSocket connection failure.
type WSErrorMsg struct {
	Err error
}

// App is the root Bubble Tea model.
type App struct {
	client     *api.Client
	wsClient   *api.WSClient
	readOnly   bool
	width      int
	height     int
	screen     Screen
	throughput *components.ThroughputTracker

	splash    SplashModel
	scenarios ScenarioModel
	launcher  LauncherModel
	dashboard DashboardModel
	theater   TheaterModel
	history   HistoryModel
	replay    ReplayModel
	analytics AnalyticsModel

	Version string

	showHelp bool
	help     HelpModel

	// programRef holds a shared reference to tea.Program for WS bridge.
	programRef *ProgramRef
}

// NewApp creates the root application model.
func NewApp(serverURL string, readOnly bool, version string) App {
	client := api.NewClient(serverURL)
	wsClient := api.NewWSClient(serverURL)
	tp := components.NewThroughputTracker()

	return App{
		client:     client,
		wsClient:   wsClient,
		readOnly:   readOnly,
		screen:     ScreenSplash,
		throughput: tp,
		Version:    version,
		splash:     NewSplashModel(client, version),
		programRef: &ProgramRef{},
	}
}

// SetProgram stores the tea.Program reference for the WS bridge.
func (a *App) SetProgram(p *tea.Program) {
	a.programRef.P = p
}

// Init delegates to the splash screen.
func (a App) Init() tea.Cmd {
	return a.splash.Init()
}

// Update handles global keys, screen switching, and delegates to sub-models.
func (a App) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		a.width = msg.Width
		a.height = msg.Height
		// Deliberately no return: the size is also delegated to the current
		// screen below. An embedded huh form rebuilds its content on Update,
		// not on View, so a screen that only learned its size while rendering
		// would draw one mis-sized frame and then reflow on the next keystroke.

	case tea.KeyPressMsg:
		switch msg.String() {
		case "ctrl+c":
			a.wsClient.Close()
			return a, tea.Quit
		case "f1":
			a.showHelp = !a.showHelp
			return a, nil
		}

	case SwitchScreenMsg:
		return a.switchScreen(msg)

	case WSEventMsg:
		if a.screen == ScreenDashboard {
			var cmd tea.Cmd
			a.dashboard, cmd = a.dashboard.Update(msg)
			return a, cmd
		}
		if a.screen == ScreenTheater {
			var cmd tea.Cmd
			a.theater, cmd = a.theater.Update(msg)
			return a, cmd
		}
		return a, nil

	case WSErrorMsg:
		if a.screen == ScreenDashboard {
			a.dashboard.errMsg = "WebSocket: " + msg.Err.Error()
		}
		return a, nil
	}

	// Delegate to current screen
	switch a.screen {
	case ScreenSplash:
		var cmd tea.Cmd
		a.splash, cmd = a.splash.Update(msg)
		return a, cmd
	case ScreenScenarios:
		var cmd tea.Cmd
		a.scenarios, cmd = a.scenarios.Update(msg)
		return a, cmd
	case ScreenLauncher:
		var cmd tea.Cmd
		a.launcher, cmd = a.launcher.Update(msg)
		return a, cmd
	case ScreenDashboard:
		var cmd tea.Cmd
		a.dashboard, cmd = a.dashboard.Update(msg)
		return a, cmd
	case ScreenTheater:
		var cmd tea.Cmd
		a.theater, cmd = a.theater.Update(msg)
		return a, cmd
	case ScreenHistory:
		var cmd tea.Cmd
		a.history, cmd = a.history.Update(msg)
		return a, cmd
	case ScreenReplay:
		var cmd tea.Cmd
		a.replay, cmd = a.replay.Update(msg)
		return a, cmd
	case ScreenAnalytics:
		var cmd tea.Cmd
		a.analytics, cmd = a.analytics.Update(msg)
		return a, cmd
	}

	return a, nil
}

// View renders the current screen, with an optional help overlay.
//
// AltScreen is declared HERE rather than as a program option. v2 removed the
// alt-screen program option, so terminal features moved onto the returned tea.View.
// That is also what makes the SSH entry point work: internal/ssh hands a model
// to a Wish middleware and cannot pass the terminal a program option, so the
// model has to declare the alternate screen itself. Both entry points
// (cmd/root.go for local, internal/ssh for remote) therefore get it from here.
func (a App) View() tea.View {
	var content string

	switch a.screen {
	case ScreenSplash:
		content = a.splash.View(a.width, a.height)
	case ScreenScenarios:
		content = a.scenarios.View(a.width, a.height)
	case ScreenLauncher:
		content = a.launcher.View(a.width, a.height)
	case ScreenDashboard:
		content = a.dashboard.View(a.width, a.height)
	case ScreenTheater:
		content = a.theater.View(a.width, a.height)
	case ScreenHistory:
		content = a.history.View(a.width, a.height)
	case ScreenReplay:
		content = a.replay.View(a.width, a.height)
	case ScreenAnalytics:
		content = a.analytics.View(a.width, a.height)
	default:
		content = "Unknown screen"
	}

	if a.showHelp {
		content = a.renderHelpOverlay(content)
	}

	v := tea.NewView(content)
	v.AltScreen = true
	return v
}

// switchScreen creates a fresh sub-model for the target screen and initialises it.
func (a App) switchScreen(msg SwitchScreenMsg) (tea.Model, tea.Cmd) {
	// Close WS connection when leaving live screens, unless going to another live screen.
	isLiveSource := a.screen == ScreenDashboard || a.screen == ScreenTheater
	isLiveDest := msg.Screen == ScreenDashboard || msg.Screen == ScreenTheater
	if isLiveSource && !isLiveDest {
		a.wsClient.Close()
	}

	a.screen = msg.Screen

	switch msg.Screen {
	case ScreenSplash:
		a.splash = NewSplashModel(a.client, a.Version)
		return a, a.splash.Init()

	case ScreenScenarios:
		a.scenarios = NewScenarioModel(a.client)
		return a, a.scenarios.Init()

	case ScreenLauncher:
		scenarioID, _ := msg.Data.(string)
		a.launcher = NewLauncherModel(a.client, scenarioID)
		return a, a.launcher.Init()

	case ScreenDashboard:
		runID, _ := msg.Data.(string)
		a.dashboard = NewDashboardModel(a.client, a.throughput, a.readOnly, runID)
		cmd := a.dashboard.Init()

		// Start WS connection in a goroutine, bridging events into Bubble Tea.
		if a.programRef != nil && a.programRef.P != nil {
			prog := a.programRef.P
			wsClient := a.wsClient
			wsClient.SetDisconnectHandler(func() {
				prog.Send(WSErrorMsg{Err: fmt.Errorf("connection lost")})
			})
			go func() {
				err := wsClient.Connect(runID, func(wsMsg api.WSMessage) {
					prog.Send(WSEventMsg{Event: wsMsg})
				})
				if err != nil {
					prog.Send(WSErrorMsg{Err: err})
				}
			}()
		}

		return a, cmd

	case ScreenTheater:
		// Theater reuses existing WS connection from Dashboard.
		runID, _ := msg.Data.(string)
		a.theater = NewTheaterModel(a.client, runID, a.dashboard.run)
		return a, a.theater.Init()

	case ScreenHistory:
		a.history = NewHistoryModel(a.client)
		return a, a.history.Init()

	case ScreenReplay:
		runID, _ := msg.Data.(string)
		a.replay = NewReplayModel(a.client, runID)
		return a, a.replay.Init()

	case ScreenAnalytics:
		a.analytics = NewAnalyticsModel(a.client)
		return a, a.analytics.Init()
	}

	return a, nil
}

// renderHelpOverlay draws a centered help panel on top of the current view.
func (a App) renderHelpOverlay(background string) string {
	return a.help.Overlay(background, a.width, a.height, a.screen)
}
