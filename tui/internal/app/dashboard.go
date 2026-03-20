package app

import (
	"fmt"
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

// PanelMode selects which panel is shown in the right column of Focus mode.
type PanelMode int

const (
	PanelFeed PanelMode = iota
	PanelMap
	PanelRelationships
	PanelNegotiations
)

var panelModeNames = [...]string{"Feed", "Map", "Relationships", "Negotiations"}

func (p PanelMode) String() string { return panelModeNames[p] }

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
type agentsRefreshedMsg struct{ agents []api.AgentStatus }

// --- DashboardModel ---

// DashboardModel is the live simulation dashboard.
type DashboardModel struct {
	client     *api.Client
	throughput *components.ThroughputTracker
	readOnly   bool
	runID      string

	mode        DashboardMode
	panelMode   PanelMode
	run         *api.RunResponse
	agents      []api.AgentStatus
	streams     map[string]*agentStream
	feedEntries []components.FeedEntry
	feedScroll  int
	selectedIdx int
	hazardLevel float64
	locations   []components.LocationInfo

	mapLocations []components.MapLocation
	mapTravels   []components.MapTravel

	refreshNeeded bool

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
		// Populate initial map locations from agent data
		for _, loc := range m.locations {
			m.mapLocations = append(m.mapLocations, components.MapLocation{
				Name:   loc.Name,
				Agents: loc.AgentNames,
			})
		}
		return m, nil

	case controlErrorMsg:
		m.errMsg = msg.err.Error()
		return m, nil

	case WSEventMsg:
		m.handleWSEvent(msg.Event)
		if m.refreshNeeded {
			m.refreshNeeded = false
			client := m.client
			runID := m.runID
			return m, func() tea.Msg {
				agents, err := client.GetRunAgents(runID)
				if err != nil {
					return nil
				}
				return agentsRefreshedMsg{agents: agents}
			}
		}
		return m, nil

	case agentsRefreshedMsg:
		m.agents = msg.agents
		// Ensure streams exist for all agents (handles late-joining agents)
		for _, a := range m.agents {
			if _, ok := m.streams[a.ID]; !ok {
				m.streams[a.ID] = &agentStream{name: a.Name}
			}
		}
		// Re-derive locations from refreshed agent data
		if m.run != nil && m.run.WorldState != nil {
			m.updateWorldState(m.run.WorldState)
		}
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
		// Backend sends "tokens" (plural, buffered chunks)
		token, _ := evt.Data["tokens"].(string)
		if token == "" {
			// Fallback to singular "token" for compatibility
			token, _ = evt.Data["token"].(string)
		}
		if s, ok := m.streams[agentID]; ok {
			if !s.active {
				// New generation starting — clear previous step's output
				s.tokens.Reset()
			}
			s.active = true
			s.tokens.WriteString(token)
		}
		m.throughput.Add(len(token))

	case "token_done":
		agentID, _ := evt.Data["agent_id"].(string)
		latency, _ := evt.Data["latency_ms"].(float64)
		if s, ok := m.streams[agentID]; ok {
			s.active = false
			s.latencyMs = int(latency)
		}

	case "step_completed":
		// Backend sends "step" for step_completed events; fall back to "step_index"
		step, ok := evt.Data["step"].(float64)
		if !ok {
			step, _ = evt.Data["step_index"].(float64)
		}
		if m.run != nil {
			m.run.CurrentStep = int(step)
			// Update world state if present
			if ws, ok := evt.Data["world_state"].(map[string]interface{}); ok {
				m.run.WorldState = ws
				m.updateWorldState(ws)
			}
		}
		// Update stream step counters (tokens preserved until next generation starts)
		for _, s := range m.streams {
			s.step = int(step)
		}
		// Refresh agent data to get updated dynamic_state (locations, health, etc.)
		m.refreshNeeded = true

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
		// Cap feed size to prevent sluggish rendering on long runs
		if len(m.feedEntries) > 500 {
			m.feedEntries = m.feedEntries[len(m.feedEntries)-500:]
		}

	case "run_completed", "run_stopped", "run_paused", "run_started":
		status := strings.TrimPrefix(evt.Event, "run_")
		if m.run != nil {
			m.run.Status = status
		}

	case "agent_moved":
		agentName, _ := evt.Data["agent_name"].(string)
		from, _ := evt.Data["from"].(string)
		to, _ := evt.Data["to"].(string)
		m.updateMapAgentLocation(agentName, from, to)
		m.removeTravel(agentName)

	case "agent_travelling":
		agentName, _ := evt.Data["agent_name"].(string)
		target, _ := evt.Data["target"].(string)
		progress, _ := evt.Data["progress"].(float64)
		from, _ := evt.Data["from"].(string)
		m.updateTravel(agentName, from, target, progress)

	case "travel_started":
		agentName, _ := evt.Data["agent_name"].(string)
		from, _ := evt.Data["from"].(string)
		to, _ := evt.Data["to"].(string)
		m.updateTravel(agentName, from, to, 0.0)

	case "location_discovered":
		locName, _ := evt.Data["location"].(string)
		connectedTo, _ := evt.Data["connected_to"].(string)
		m.addMapLocation(locName, connectedTo)

	case "movement_failed":
		agentName, _ := evt.Data["agent_name"].(string)
		reason, _ := evt.Data["reason"].(string)
		step, _ := evt.Data["step"].(float64)
		m.feedEntries = append(m.feedEntries, components.FeedEntry{
			AgentName:   agentName,
			Content:     fmt.Sprintf("Movement failed: %s", reason),
			MessageType: "error",
			Step:        int(step),
		})
	}
}

// updateWorldState extracts hazard level and location info from world state.
func (m *DashboardModel) updateWorldState(ws map[string]interface{}) {
	if hl, ok := ws["hazard_level"].(float64); ok {
		m.hazardLevel = hl
	}

	// Build location list from world_state.locations keys
	locAgents := make(map[string][]string) // location_name -> agent names

	if locs, ok := ws["locations"].(map[string]interface{}); ok {
		for name := range locs {
			if _, exists := locAgents[name]; !exists {
				locAgents[name] = nil
			}
		}
	}

	// Populate agent positions from their dynamic_state.location
	for _, a := range m.agents {
		if ds := a.DynamicState; ds != nil {
			if loc, ok := ds["location"].(string); ok && loc != "" {
				locAgents[loc] = append(locAgents[loc], a.Name)
			}
		}
	}

	m.locations = nil
	for name, agents := range locAgents {
		m.locations = append(m.locations, components.LocationInfo{
			Name:       name,
			AgentNames: agents,
		})
	}
}

// updateMapAgentLocation moves an agent from one location to another on the map.
func (m *DashboardModel) updateMapAgentLocation(agent, from, to string) {
	for i, loc := range m.mapLocations {
		if loc.Name == from {
			m.mapLocations[i].Agents = removeStr(loc.Agents, agent)
		}
		if loc.Name == to {
			m.mapLocations[i].Agents = append(m.mapLocations[i].Agents, agent)
			return
		}
	}
	m.mapLocations = append(m.mapLocations, components.MapLocation{
		Name:   to,
		Agents: []string{agent},
	})
}

// removeTravel removes a completed travel entry for an agent.
func (m *DashboardModel) removeTravel(agent string) {
	for i, t := range m.mapTravels {
		if t.AgentName == agent {
			m.mapTravels = append(m.mapTravels[:i], m.mapTravels[i+1:]...)
			return
		}
	}
}

// updateTravel adds or updates a travel entry for an agent.
func (m *DashboardModel) updateTravel(agent, from, to string, progress float64) {
	for i, t := range m.mapTravels {
		if t.AgentName == agent {
			m.mapTravels[i].Progress = progress
			return
		}
	}
	m.mapTravels = append(m.mapTravels, components.MapTravel{
		AgentName: agent,
		From:      from,
		To:        to,
		Progress:  progress,
	})
}

// addMapLocation adds a new location or appends a connection to an existing one.
func (m *DashboardModel) addMapLocation(name, connectedTo string) {
	for i, loc := range m.mapLocations {
		if loc.Name == name {
			if connectedTo != "" {
				m.mapLocations[i].ConnectedTo = append(loc.ConnectedTo, connectedTo)
			}
			return
		}
	}
	loc := components.MapLocation{Name: name}
	if connectedTo != "" {
		loc.ConnectedTo = []string{connectedTo}
	}
	m.mapLocations = append(m.mapLocations, loc)
}

// removeStr removes the first occurrence of s from ss.
func removeStr(ss []string, s string) []string {
	for i, v := range ss {
		if v == s {
			return append(ss[:i], ss[i+1:]...)
		}
	}
	return ss
}

// handleKey processes keyboard input for the dashboard.
func (m DashboardModel) handleKey(msg tea.KeyMsg) (DashboardModel, tea.Cmd) {
	switch msg.String() {
	case "tab":
		m.panelMode = (m.panelMode + 1) % 4

	case "g":
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
		{Key: "Tab", Desc: "panel"},
		{Key: "g", Desc: "grid"},
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
		PanelName: m.panelMode.String(),
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

	// Right: panel mode dispatch
	rightHeight := height
	var right string
	switch m.panelMode {
	case PanelFeed:
		feedHeight := rightHeight * 2 / 3
		worldHeight := rightHeight - feedHeight

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

		right = lipgloss.JoinVertical(lipgloss.Left, feedPanel, worldPanel)
	case PanelMap:
		rightContent := components.RenderSpatialMap(components.SpatialMapData{
			Locations: m.mapLocations,
			Travels:   m.mapTravels,
			Width:     rightWidth,
			Height:    rightHeight,
		})
		right = lipgloss.NewStyle().Width(rightWidth - 2).Height(rightHeight - 2).Render(rightContent)
	case PanelRelationships:
		right = theme.Panel.Width(rightWidth - 2).Height(rightHeight - 2).Render(
			theme.MutedText.Render("Relationship Web (coming soon...)"))
	case PanelNegotiations:
		right = theme.Panel.Width(rightWidth - 2).Height(rightHeight - 2).Render(
			theme.MutedText.Render("Negotiation Theater (coming soon...)"))
	}
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

	// Extract persona fields
	if persona := agent.Persona; persona != nil {
		if occ, ok := persona["occupation"].(string); ok {
			data.Occupation = occ
		}
		if age, ok := persona["age"].(float64); ok {
			data.Age = int(age)
		}
	}

	// Extract dynamic state
	if ds := agent.DynamicState; ds != nil {
		if h, ok := ds["health"].(float64); ok {
			data.Health = int(h)
		}
		if s, ok := ds["stress_level"].(float64); ok {
			data.Stress = int(s)
		}
		if loc, ok := ds["location"].(string); ok {
			data.Location = loc
		}
	}

	// Extract plan
	if plan := agent.CurrentPlan; plan != nil {
		data.PlanGoal = plan.Goal
		data.PlanProgress = plan.StepProgress
	}

	return components.RenderAgentPane(data, width, height)
}
