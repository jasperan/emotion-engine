package app

import (
	"strconv"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/components"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// DashboardMode toggles between focus and grid layouts.
type DashboardMode int

const (
	ModeFocus DashboardMode = iota
	ModeGrid
)

// agentStream tracks per-agent token streaming state.
type agentStream struct {
	name      string
	tokens    strings.Builder
	active    bool
	latencyMs int
	step      int
}

// --- Messages ---

type dashboardLoadedMsg struct {
	run    *api.RunResponse
	agents []api.AgentStatus
	err    error
}

type controlErrorMsg struct{ err error }

// --- DashboardModel ---

// DashboardModel is the live simulation dashboard.
type DashboardModel struct {
	client     *api.Client
	throughput *components.ThroughputTracker
	readOnly   bool
	runID      string

	mode        DashboardMode
	run         *api.RunResponse
	agents      []api.AgentStatus
	streams     map[string]*agentStream
	feedEntries []components.FeedEntry
	feedScroll  int
	selectedIdx int
	hazardLevel float64
	locations   []components.LocationInfo

	err    error
	errMsg string
}

// NewDashboardModel creates a dashboard for the given run.
func NewDashboardModel(client *api.Client, tp *components.ThroughputTracker, readOnly bool, runID string) DashboardModel {
	return DashboardModel{
		client:     client,
		throughput: tp,
		readOnly:   readOnly,
		runID:      runID,
		mode:       ModeFocus,
		streams:    make(map[string]*agentStream),
	}
}

// Init fetches initial run and agent data.
func (m DashboardModel) Init() tea.Cmd {
	client := m.client
	runID := m.runID
	return func() tea.Msg {
		run, err := client.GetRun(runID)
		if err != nil {
			return dashboardLoadedMsg{err: err}
		}
		agents, err := client.GetRunAgents(runID)
		if err != nil {
			return dashboardLoadedMsg{err: err}
		}
		return dashboardLoadedMsg{run: run, agents: agents}
	}
}

// Update handles WS events, key input, and data loading.
func (m DashboardModel) Update(msg tea.Msg) (DashboardModel, tea.Cmd) {
	switch msg := msg.(type) {
	case dashboardLoadedMsg:
		if msg.err != nil {
			m.err = msg.err
			return m, nil
		}
		m.run = msg.run
		m.agents = msg.agents
		// Initialize streams for each agent
		for _, a := range m.agents {
			m.streams[a.ID] = &agentStream{
				name: a.Name,
			}
		}
		return m, nil

	case controlErrorMsg:
		m.errMsg = msg.err.Error()
		return m, nil

	case WSEventMsg:
		m.handleWSEvent(msg.Event)
		return m, nil

	case tea.KeyMsg:
		m.errMsg = "" // clear error on next keypress
		return m.handleKey(msg)
	}

	return m, nil
}

// handleWSEvent processes a WebSocket event and updates dashboard state.
func (m *DashboardModel) handleWSEvent(evt api.WSMessage) {
	switch evt.Event {
	case "token_stream":
		agentID, _ := evt.Data["agent_id"].(string)
		token, _ := evt.Data["token"].(string)
		if s, ok := m.streams[agentID]; ok {
			s.active = true
			s.tokens.WriteString(token)
		}
		m.throughput.Add(1)

	case "token_done":
		agentID, _ := evt.Data["agent_id"].(string)
		latency, _ := evt.Data["latency_ms"].(float64)
		if s, ok := m.streams[agentID]; ok {
			s.active = false
			s.latencyMs = int(latency)
		}

	case "step_completed":
		step, _ := evt.Data["step_index"].(float64)
		if m.run != nil {
			m.run.CurrentStep = int(step)
			// Update world state if present
			if ws, ok := evt.Data["world_state"].(map[string]interface{}); ok {
				m.run.WorldState = ws
				m.updateWorldState(ws)
			}
		}
		// Update stream step counters and clear completed token buffers
		for _, s := range m.streams {
			s.step = int(step)
		}
		m.clearCompletedStreams()

	case "message", "scene_turn":
		agentName, _ := evt.Data["agent_name"].(string)
		content, _ := evt.Data["content"].(string)
		msgType, _ := evt.Data["message_type"].(string)
		location, _ := evt.Data["location"].(string)
		step, _ := evt.Data["step_index"].(float64)

		if agentName == "" {
			agentName = "System"
		}
		if msgType == "" {
			msgType = "message"
		}

		m.feedEntries = append(m.feedEntries, components.FeedEntry{
			AgentName:   agentName,
			Content:     content,
			MessageType: msgType,
			Location:    location,
			Step:        int(step),
		})

	case "run_completed", "run_stopped", "run_paused", "run_started":
		status := strings.TrimPrefix(evt.Event, "run_")
		if m.run != nil {
			m.run.Status = status
		}
	}
}

// updateWorldState extracts hazard level and location info from world state.
func (m *DashboardModel) updateWorldState(ws map[string]interface{}) {
	if hl, ok := ws["hazard_level"].(float64); ok {
		m.hazardLevel = hl
	}

	if locs, ok := ws["locations"].(map[string]interface{}); ok {
		m.locations = nil
		for name, v := range locs {
			loc := components.LocationInfo{Name: name}
			if locData, ok := v.(map[string]interface{}); ok {
				if agents, ok := locData["agents"].([]interface{}); ok {
					for _, a := range agents {
						if aName, ok := a.(string); ok {
							loc.AgentNames = append(loc.AgentNames, aName)
						}
					}
				}
			}
			m.locations = append(m.locations, loc)
		}
	}
}

// handleKey processes keyboard input for the dashboard.
func (m DashboardModel) handleKey(msg tea.KeyMsg) (DashboardModel, tea.Cmd) {
	switch msg.String() {
	case "tab":
		if m.mode == ModeFocus {
			m.mode = ModeGrid
		} else {
			m.mode = ModeFocus
		}

	case " ":
		if !m.readOnly && m.run != nil {
			action := "pause"
			if m.run.Status == "paused" {
				action = "resume"
			}
			client := m.client
			runID := m.runID
			return m, func() tea.Msg {
				if err := client.ControlRun(runID, action); err != nil {
					return controlErrorMsg{err: err}
				}
				return nil
			}
		}

	case "s":
		if !m.readOnly && m.run != nil {
			client := m.client
			runID := m.runID
			return m, func() tea.Msg {
				if err := client.ControlRun(runID, "stop"); err != nil {
					return controlErrorMsg{err: err}
				}
				return nil
			}
		}

	case "1", "2", "3", "4", "5", "6", "7", "8", "9":
		idx, _ := strconv.Atoi(msg.String())
		idx-- // 0-based
		if idx < len(m.agents) {
			m.selectedIdx = idx
		}

	case "up", "k":
		if m.feedScroll > 0 {
			m.feedScroll--
		}
	case "down", "j":
		if m.feedScroll < len(m.feedEntries) {
			m.feedScroll++
		}

	case "left", "h":
		if m.selectedIdx > 0 {
			m.selectedIdx--
		}
	case "right", "l":
		if m.selectedIdx < len(m.agents)-1 {
			m.selectedIdx++
		}

	case "q", "esc":
		return m, func() tea.Msg {
			return SwitchScreenMsg{Screen: ScreenScenarios}
		}
	}

	return m, nil
}

// View renders the dashboard in either Focus or Grid mode.
func (m DashboardModel) View(width, height int) string {
	if m.err != nil {
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
			theme.ErrorText.Render("Dashboard error: "+m.err.Error()))
	}

	if m.run == nil {
		if m.readOnly {
			return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
				theme.MutedText.Render("Live streaming unavailable in SSH mode — browse scenarios and history instead"))
		}
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
			theme.MutedText.Render("Loading dashboard..."))
	}

	statusBarHeight := 1
	sparklineHeight := 1
	mainHeight := height - statusBarHeight - sparklineHeight

	var main string
	if m.mode == ModeFocus {
		main = m.renderFocusMode(width, mainHeight)
	} else {
		main = m.renderGridMode(width, mainHeight)
	}

	// Status bar
	hints := []components.KeyHint{
		{Key: "Tab", Desc: "mode"},
		{Key: "F1", Desc: "help"},
	}
	if !m.readOnly {
		hints = append(hints, components.KeyHint{Key: "Space", Desc: "pause"})
	}
	hints = append(hints, components.KeyHint{Key: "q", Desc: "back"})

	if m.errMsg != "" {
		hints = append([]components.KeyHint{{Key: "!", Desc: m.errMsg}}, hints...)
	}

	bar := components.RenderStatusBar(components.StatusBarData{
		Connected: true,
		RunStatus: m.run.Status,
		Step:      m.run.CurrentStep,
		MaxSteps:  m.run.MaxSteps,
		TokPerSec: m.throughput.CurrentRate(),
		Hints:     hints,
	}, width)

	sparkline := components.RenderThroughput(m.throughput, width)

	return lipgloss.JoinVertical(lipgloss.Left, main, sparkline, bar)
}

// renderFocusMode renders the two-column focus layout.
func (m DashboardModel) renderFocusMode(width, height int) string {
	leftWidth := width * 60 / 100
	rightWidth := width - leftWidth

	// Left: up to 4 agent panes stacked
	agentPanes := m.buildAgentPanes(leftWidth, height, 4)
	left := lipgloss.JoinVertical(lipgloss.Left, agentPanes...)
	left = lipgloss.NewStyle().Width(leftWidth).Height(height).Render(left)

	// Right: message feed (top 2/3) + world state (bottom 1/3)
	feedHeight := height * 2 / 3
	worldHeight := height - feedHeight

	feed := components.RenderMessageFeed(components.MessageFeedData{
		Entries:   m.feedEntries,
		ScrollPos: m.feedScroll,
		Height:    feedHeight - 2,
		Width:     rightWidth - 2,
	})
	feedPanel := theme.Panel.Width(rightWidth - 2).Height(feedHeight - 2).Render(feed)

	world := components.RenderWorldState(components.WorldStateData{
		HazardLevel: m.hazardLevel,
		Locations:   m.locations,
		Width:       rightWidth - 2,
	})
	worldPanel := theme.Panel.Width(rightWidth - 2).Height(worldHeight - 2).Render(world)

	right := lipgloss.JoinVertical(lipgloss.Left, feedPanel, worldPanel)
	right = lipgloss.NewStyle().Width(rightWidth).Height(height).Render(right)

	return lipgloss.JoinHorizontal(lipgloss.Top, left, right)
}

// renderGridMode renders a 2x5 grid of compact agent panes.
func (m DashboardModel) renderGridMode(width, height int) string {
	cols := 5
	rows := 2
	paneWidth := width / cols
	paneHeight := height / rows

	var rowViews []string
	agentIdx := 0
	for r := 0; r < rows; r++ {
		var colViews []string
		for c := 0; c < cols; c++ {
			if agentIdx < len(m.agents) {
				pane := m.buildSingleAgentPane(agentIdx, paneWidth, paneHeight)
				colViews = append(colViews, pane)
			} else {
				empty := theme.Panel.Width(paneWidth - 2).Height(paneHeight - 2).
					Render(theme.MutedText.Render("empty"))
				colViews = append(colViews, empty)
			}
			agentIdx++
		}
		rowViews = append(rowViews, lipgloss.JoinHorizontal(lipgloss.Top, colViews...))
	}

	return lipgloss.JoinVertical(lipgloss.Left, rowViews...)
}

// buildAgentPanes builds up to maxPanes agent pane views.
func (m DashboardModel) buildAgentPanes(width, totalHeight, maxPanes int) []string {
	count := len(m.agents)
	if count > maxPanes {
		count = maxPanes
	}
	if count == 0 {
		return []string{theme.MutedText.Render("No agents")}
	}

	paneHeight := totalHeight / count
	var panes []string
	for i := 0; i < count; i++ {
		panes = append(panes, m.buildSingleAgentPane(i, width, paneHeight))
	}
	return panes
}

// buildSingleAgentPane renders one agent's pane.
func (m DashboardModel) buildSingleAgentPane(idx int, width, height int) string {
	if idx >= len(m.agents) {
		return ""
	}

	agent := m.agents[idx]
	stream := m.streams[agent.ID]

	data := components.AgentPaneData{
		ID:       agent.ID,
		Name:     agent.Name,
		Selected: idx == m.selectedIdx,
	}

	if stream != nil {
		data.Active = stream.active
		data.Tokens = stream.tokens.String()
		data.LatencyMs = stream.latencyMs
		data.Step = stream.step
	}

	return components.RenderAgentPane(data, width, height)
}

// --- Utility: step_completed handler clears completed streams ---

func (m *DashboardModel) clearCompletedStreams() {
	for _, s := range m.streams {
		if !s.active {
			s.tokens.Reset()
		}
	}
}
