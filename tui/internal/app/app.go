package app

import (
	tea "github.com/charmbracelet/bubbletea"
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
	ScreenHistory
)

// SwitchScreenMsg requests a transition to a different screen.
type SwitchScreenMsg struct {
	Screen Screen
	Data   interface{}
}

// WSEventMsg wraps a WebSocket event for the Bubble Tea update loop.
type WSEventMsg struct {
	Event api.WSMessage
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
	history   HistoryModel

	showHelp bool
	help     HelpModel

	// programRef holds a shared reference to tea.Program for WS bridge.
	programRef *ProgramRef
}

// NewApp creates the root application model.
func NewApp(serverURL string, readOnly bool) App {
	client := api.NewClient(serverURL)
	wsClient := api.NewWSClient(serverURL)
	tp := components.NewThroughputTracker()

	return App{
		client:     client,
		wsClient:   wsClient,
		readOnly:   readOnly,
		screen:     ScreenSplash,
		throughput: tp,
		splash:     NewSplashModel(client),
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
		return a, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "ctrl+c":
			a.wsClient.Close()
			return a, tea.Quit
		case "?":
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
	case ScreenHistory:
		var cmd tea.Cmd
		a.history, cmd = a.history.Update(msg)
		return a, cmd
	}

	return a, nil
}

// View renders the current screen, with an optional help overlay.
func (a App) View() string {
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
	case ScreenHistory:
		content = a.history.View(a.width, a.height)
	default:
		content = "Unknown screen"
	}

	if a.showHelp {
		content = a.renderHelpOverlay(content)
	}

	return content
}

// switchScreen creates a fresh sub-model for the target screen and initialises it.
func (a App) switchScreen(msg SwitchScreenMsg) (tea.Model, tea.Cmd) {
	a.screen = msg.Screen

	switch msg.Screen {
	case ScreenSplash:
		a.splash = NewSplashModel(a.client)
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
			go func() {
				_ = wsClient.Connect(runID, func(wsMsg api.WSMessage) {
					prog.Send(WSEventMsg{Event: wsMsg})
				})
			}()
		}

		return a, cmd

	case ScreenHistory:
		a.history = NewHistoryModel(a.client)
		return a, a.history.Init()
	}

	return a, nil
}

// renderHelpOverlay draws a centered help panel on top of the current view.
func (a App) renderHelpOverlay(background string) string {
	return a.help.Overlay(background, a.width, a.height, a.screen)
}
