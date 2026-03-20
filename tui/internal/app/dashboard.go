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

	relAgents []components.RelAgent
	relEdges  []components.RelEdge

	negotiations []components.NegotiationEntry
	negScroll    int
	feedFilter   components.FeedFilter

	refreshNeeded bool

	expandedAgent int // -1 = not expanded; 0+ = agent index shown in mind view

	err    error
	errMsg string
}

// NewDashboardModel creates a dashboard for the given run.
func NewDashboardModel(client *api.Client, tp *components.ThroughputTracker, readOnly bool, runID string) DashboardModel {
	return DashboardModel{
		client:        client,
		throughput:    tp,
		readOnly:      readOnly,
		runID:         runID,
		mode:          ModeFocus,
		streams:       make(map[string]*agentStream),
		expandedAgent: -1,
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
		// Initialize relationship web nodes from agent list
		for _, agent := range m.agents {
			m.relAgents = append(m.relAgents, components.RelAgent{
				ID:   agent.ID,
				Name: agent.Name,
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
		m.feedEntries = append(m.feedEntries, components.FeedEntry{
			AgentName:   agentName,
			Content:     fmt.Sprintf("Moved from %s to %s", from, to),
			MessageType: "movement",
			Step:        int(safeFloat(evt.Data, "step")),
		})

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
		m.feedEntries = append(m.feedEntries, components.FeedEntry{
			AgentName:   agentName,
			Content:     fmt.Sprintf("Started travelling from %s to %s", from, to),
			MessageType: "movement",
			Step:        int(safeFloat(evt.Data, "step")),
		})

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

	case "vouch_for":
		voucher, _ := evt.Data["voucher"].(string)
		subject, _ := evt.Data["subject"].(string)
		m.addOrUpdateRelEdge(voucher, subject, components.RelTrust, 0.7, "vouched")

	case "proposal_accepted":
		// Try to extract parties from agreement and create alliance edge
		if agreement, ok := evt.Data["agreement"].(map[string]interface{}); ok {
			if parties, ok := agreement["parties"].([]interface{}); ok && len(parties) >= 2 {
				a, _ := parties[0].(string)
				b, _ := parties[1].(string)
				if a != "" && b != "" {
					m.addOrUpdateRelEdge(a, b, components.RelAlliance, 0.8, "agreement")
				}
			}
		}
		// Update negotiation entry
		proposalID, _ := evt.Data["proposal_id"].(string)
		for i, n := range m.negotiations {
			if n.ProposalID == proposalID {
				m.negotiations[i].Status = components.NegAccepted
				break
			}
		}

	case "proposal_rejected":
		agentID, _ := evt.Data["agent_id"].(string)
		_ = m.agentNameByID(agentID) // limited info available
		// Update negotiation entry
		proposalID2, _ := evt.Data["proposal_id"].(string)
		agentID2, _ := evt.Data["agent_id"].(string)
		agentName2 := m.agentNameByID(agentID2)
		step2 := int(safeFloat(evt.Data, "step"))
		for i, n := range m.negotiations {
			if n.ProposalID == proposalID2 {
				m.negotiations[i].Responses = append(m.negotiations[i].Responses, components.NegotiationResponse{
					AgentName: agentName2, Action: "rejected", Step: step2,
				})
				break
			}
		}

	case "proposal_created":
		proposal, _ := evt.Data["proposal"].(map[string]interface{})
		proposalID, _ := proposal["id"].(string)
		proposer, _ := proposal["proposer"].(string)
		target, _ := proposal["target"].(string)
		terms, _ := proposal["terms"].(string)
		if terms == "" {
			if desc, ok := proposal["description"].(string); ok {
				terms = desc
			}
		}
		step := int(safeFloat(evt.Data, "step"))
		m.negotiations = append(m.negotiations, components.NegotiationEntry{
			ProposalID: proposalID,
			Proposer:   proposer,
			Target:     target,
			Terms:      terms,
			Status:     components.NegPending,
			Step:       step,
		})
		m.feedEntries = append(m.feedEntries, components.FeedEntry{
			AgentName:   proposer,
			Content:     fmt.Sprintf("Proposed: %s", terms),
			MessageType: "negotiation",
			Step:        step,
		})

	case "counter_proposal":
		proposalID, _ := evt.Data["proposal_id"].(string)
		agentID, _ := evt.Data["agent_id"].(string)
		agentName := m.agentNameByID(agentID)
		counterTerms, _ := evt.Data["counter_terms"].(string)
		step := int(safeFloat(evt.Data, "step"))
		for i, n := range m.negotiations {
			if n.ProposalID == proposalID {
				m.negotiations[i].Status = components.NegCountered
				m.negotiations[i].Responses = append(m.negotiations[i].Responses, components.NegotiationResponse{
					AgentName: agentName, Action: "countered", Detail: counterTerms, Step: step,
				})
				break
			}
		}

	case "proposal_expired":
		proposalID, _ := evt.Data["proposal_id"].(string)
		for i, n := range m.negotiations {
			if n.ProposalID == proposalID {
				m.negotiations[i].Status = components.NegExpired
				break
			}
		}

	case "emotion_contagion":
		// Placeholder: could update relationship edges based on emotional spread
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

// addOrUpdateRelEdge upserts a relationship edge between two agents by name.
func (m *DashboardModel) addOrUpdateRelEdge(a, b string, edgeType components.RelEdgeType, strength float64, label string) {
	for i, e := range m.relEdges {
		if (e.AgentA == a && e.AgentB == b) || (e.AgentA == b && e.AgentB == a) {
			m.relEdges[i].Type = edgeType
			m.relEdges[i].Strength = strength
			if label != "" {
				m.relEdges[i].Label = label
			}
			return
		}
	}
	m.relEdges = append(m.relEdges, components.RelEdge{
		AgentA: a, AgentB: b, Type: edgeType, Strength: strength, Label: label,
	})
}

// safeFloat safely extracts a float64 from a map by key.
func safeFloat(data map[string]interface{}, key string) float64 {
	if v, ok := data[key].(float64); ok {
		return v
	}
	return 0
}

// agentNameByID resolves an agent ID to its display name.
func (m *DashboardModel) agentNameByID(id string) string {
	for _, a := range m.agents {
		if a.ID == id {
			return a.Name
		}
	}
	if len(id) > 8 {
		return id[:8]
	}
	return id
}

// handleKey processes keyboard input for the dashboard.
func (m DashboardModel) handleKey(msg tea.KeyMsg) (DashboardModel, tea.Cmd) {
	switch msg.String() {
	case "tab":
		m.panelMode = (m.panelMode + 1) % 4

	case "f":
		if m.panelMode == PanelFeed {
			m.feedFilter = (m.feedFilter + 1) % 4
		}

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
		if m.panelMode == PanelNegotiations {
			if m.negScroll > 0 {
				m.negScroll--
			}
		} else {
			if m.feedScroll > 0 {
				m.feedScroll--
			}
		}
	case "down", "j":
		if m.panelMode == PanelNegotiations {
			m.negScroll++
		} else {
			if m.feedScroll < len(m.feedEntries) {
				m.feedScroll++
			}
		}

	case "enter":
		if m.expandedAgent < 0 && len(m.agents) > 0 && m.selectedIdx < len(m.agents) {
			m.expandedAgent = m.selectedIdx
		}

	case "left", "h":
		if m.expandedAgent >= 0 {
			m.expandedAgent--
			if m.expandedAgent < 0 {
				m.expandedAgent = len(m.agents) - 1
			}
			m.selectedIdx = m.expandedAgent
		} else {
			if m.selectedIdx > 0 {
				m.selectedIdx--
			}
		}
	case "right", "l":
		if m.expandedAgent >= 0 {
			m.expandedAgent = (m.expandedAgent + 1) % len(m.agents)
			m.selectedIdx = m.expandedAgent
		} else {
			if m.selectedIdx < len(m.agents)-1 {
				m.selectedIdx++
			}
		}

	case "q", "esc":
		if m.expandedAgent >= 0 {
			m.expandedAgent = -1
			return m, nil
		}
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
		Connected:  true,
		RunStatus:  m.run.Status,
		Step:       m.run.CurrentStep,
		MaxSteps:   m.run.MaxSteps,
		TokPerSec:  m.throughput.CurrentRate(),
		Hints:      hints,
		PanelName:  m.panelMode.String(),
		FilterName: m.feedFilter.String(),
	}, width)

	sparkline := components.RenderThroughput(m.throughput, width)

	return lipgloss.JoinVertical(lipgloss.Left, main, sparkline, bar)
}

// renderFocusMode renders the two-column focus layout.
func (m DashboardModel) renderFocusMode(width, height int) string {
	leftWidth := width * 60 / 100
	rightWidth := width - leftWidth

	// Mind view replaces the left panel when an agent is expanded.
	if m.expandedAgent >= 0 && m.expandedAgent < len(m.agents) {
		leftContent := m.renderMindView(m.expandedAgent, leftWidth, height)
		left := lipgloss.NewStyle().Width(leftWidth).Height(height).Render(leftContent)

		// Right panel renders as normal (fall through to right-panel block below).
		rightHeight := height
		var right string
		switch m.panelMode {
		case PanelFeed:
			feedHeight := rightHeight * 2 / 3
			worldHeight := rightHeight - feedHeight
			feed := components.RenderMessageFeed(components.MessageFeedData{
				Entries:   m.feedEntries,
				Filter:    m.feedFilter,
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
			right = lipgloss.NewStyle().Width(rightWidth - 2).Height(rightHeight - 2).Render(
				components.RenderSpatialMap(components.SpatialMapData{
					Locations: m.mapLocations,
					Travels:   m.mapTravels,
					Width:     rightWidth,
					Height:    rightHeight,
				}))
		case PanelRelationships:
			right = lipgloss.NewStyle().Width(rightWidth - 2).Height(rightHeight - 2).Render(
				components.RenderRelationshipWeb(components.RelationshipWebData{
					Agents: m.relAgents,
					Edges:  m.relEdges,
					Width:  rightWidth,
					Height: rightHeight,
				}))
		case PanelNegotiations:
			right = lipgloss.NewStyle().Width(rightWidth - 2).Height(rightHeight - 2).Render(
				components.RenderNegotiationTheater(components.NegotiationTheaterData{
					Entries:   m.negotiations,
					ScrollPos: m.negScroll,
					Width:     rightWidth,
					Height:    rightHeight,
				}))
		}
		right = lipgloss.NewStyle().Width(rightWidth).Height(height).Render(right)
		return lipgloss.JoinHorizontal(lipgloss.Top, left, right)
	}

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
			Filter:    m.feedFilter,
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
		rightContent := components.RenderRelationshipWeb(components.RelationshipWebData{
			Agents: m.relAgents,
			Edges:  m.relEdges,
			Width:  rightWidth,
			Height: rightHeight,
		})
		right = lipgloss.NewStyle().Width(rightWidth - 2).Height(rightHeight - 2).Render(rightContent)
	case PanelNegotiations:
		rightContent := components.RenderNegotiationTheater(components.NegotiationTheaterData{
			Entries:   m.negotiations,
			ScrollPos: m.negScroll,
			Width:     rightWidth,
			Height:    rightHeight,
		})
		right = lipgloss.NewStyle().Width(rightWidth - 2).Height(rightHeight - 2).Render(rightContent)
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

// renderMindView builds a MindViewData from agent state and renders the full mind view.
func (m DashboardModel) renderMindView(idx, width, height int) string {
	agent := m.agents[idx]
	d := components.MindViewData{
		Name:   agent.Name,
		Width:  width,
		Height: height,
	}

	// Extract from Persona map
	if p := agent.Persona; p != nil {
		if v, ok := p["occupation"].(string); ok {
			d.Occupation = v
		}
		if v, ok := p["age"].(float64); ok {
			d.Age = int(v)
		}
		if v, ok := p["openness"].(float64); ok {
			d.Openness = int(v)
		}
		if v, ok := p["conscientiousness"].(float64); ok {
			d.Conscientiousness = int(v)
		}
		if v, ok := p["extraversion"].(float64); ok {
			d.Extraversion = int(v)
		}
		if v, ok := p["agreeableness"].(float64); ok {
			d.Agreeableness = int(v)
		}
		if v, ok := p["neuroticism"].(float64); ok {
			d.Neuroticism = int(v)
		}
		if v, ok := p["risk_tolerance"].(float64); ok {
			d.RiskTolerance = int(v)
		}
		if v, ok := p["empathy_level"].(float64); ok {
			d.Empathy = int(v)
		}
		if v, ok := p["leadership"].(float64); ok {
			d.Leadership = int(v)
		}
	}

	// Extract from DynamicState map
	if ds := agent.DynamicState; ds != nil {
		if v, ok := ds["health"].(float64); ok {
			d.Health = int(v)
		}
		if v, ok := ds["stress_level"].(float64); ok {
			d.Stress = int(v)
		}
		if v, ok := ds["location"].(string); ok {
			d.Location = v
		}
		if v, ok := ds["current_emotion"].(string); ok {
			d.Emotion = v
		}
		if v, ok := ds["last_reasoning"].(string); ok {
			d.LastReasoning = v
		}
		if inv, ok := ds["inventory"].([]interface{}); ok {
			for _, item := range inv {
				if s, ok := item.(string); ok {
					d.Inventory = append(d.Inventory, s)
				}
			}
		}
	}

	// Extract plan
	if plan := agent.CurrentPlan; plan != nil {
		d.PlanGoal = plan.Goal
		d.PlanStep = plan.CurrentStep
		d.PlanProgress = plan.StepProgress
		if plan.DeadlineStep != nil {
			d.PlanDeadline = *plan.DeadlineStep
		}
	}

	return components.RenderMindView(d)
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
