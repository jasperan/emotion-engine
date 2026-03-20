package app

import (
	"fmt"
	"sort"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// --- Message types ---

type replayLoadedMsg struct {
	run      *api.RunResponse
	agents   []api.AgentStatus
	messages []api.MessageResponse
	err      error
}

type replayStepMsg struct {
	step *api.StepResponse
	err  error
}

type replayTickMsg struct{}

// --- ReplayModel ---

// ReplayModel is the replay screen for stepping through completed runs.
type ReplayModel struct {
	client      *api.Client
	runID       string
	run         *api.RunResponse
	agents      []api.AgentStatus
	steps       map[int]*api.StepResponse
	messages    []api.MessageResponse
	currentStep int
	totalSteps  int
	playing     bool
	playSpeed   time.Duration
	showDiff    bool
	err         error
}

// NewReplayModel creates a new replay model for the given run ID.
func NewReplayModel(client *api.Client, runID string) ReplayModel {
	return ReplayModel{
		client:    client,
		runID:     runID,
		steps:     make(map[int]*api.StepResponse),
		playSpeed: time.Second,
	}
}

// Init fetches run metadata, agents, and messages.
func (m ReplayModel) Init() tea.Cmd {
	client := m.client
	runID := m.runID
	return func() tea.Msg {
		run, err := client.GetRun(runID)
		if err != nil {
			return replayLoadedMsg{err: err}
		}
		agents, err := client.GetRunAgents(runID)
		if err != nil {
			return replayLoadedMsg{err: err}
		}
		messages, err := client.GetRunMessages(runID, 5000)
		if err != nil {
			return replayLoadedMsg{err: err}
		}
		return replayLoadedMsg{run: run, agents: agents, messages: messages}
	}
}

// fetchStep returns a Cmd that fetches a single step by index.
func (m ReplayModel) fetchStep(stepIndex int) tea.Cmd {
	client := m.client
	runID := m.runID
	return func() tea.Msg {
		steps, err := client.GetRunSteps(runID, stepIndex, 1)
		if err != nil {
			return replayStepMsg{err: err}
		}
		if len(steps) == 0 {
			return replayStepMsg{err: fmt.Errorf("step %d not found", stepIndex)}
		}
		return replayStepMsg{step: &steps[0]}
	}
}

// prefetchSteps returns cmds to fetch missing steps in the lookahead window.
func (m ReplayModel) prefetchSteps(from, count int) []tea.Cmd {
	var cmds []tea.Cmd
	for i := 0; i < count; i++ {
		idx := from + i
		if idx >= m.totalSteps {
			break
		}
		if _, ok := m.steps[idx]; !ok {
			cmds = append(cmds, m.fetchStep(idx))
		}
	}
	return cmds
}

// scheduleTick returns a Cmd that fires replayTickMsg after playSpeed.
func (m ReplayModel) scheduleTick() tea.Cmd {
	d := m.playSpeed
	return tea.Tick(d, func(_ time.Time) tea.Msg {
		return replayTickMsg{}
	})
}

// Update processes messages for the replay screen.
func (m ReplayModel) Update(msg tea.Msg) (ReplayModel, tea.Cmd) {
	switch msg := msg.(type) {
	case replayLoadedMsg:
		if msg.err != nil {
			m.err = msg.err
			return m, nil
		}
		m.run = msg.run
		m.agents = msg.agents
		m.messages = msg.messages
		m.totalSteps = msg.run.CurrentStep
		m.currentStep = 0
		return m, m.fetchStep(0)

	case replayStepMsg:
		if msg.err != nil {
			// Non-fatal: step may just not exist yet.
			return m, nil
		}
		m.steps[msg.step.StepIndex] = msg.step
		// Prefetch next 5.
		cmds := m.prefetchSteps(msg.step.StepIndex+1, 5)
		return m, tea.Batch(cmds...)

	case replayTickMsg:
		if !m.playing {
			return m, nil
		}
		if m.currentStep >= m.totalSteps-1 {
			m.playing = false
			return m, nil
		}
		m.currentStep++
		var cmds []tea.Cmd
		if _, ok := m.steps[m.currentStep]; !ok {
			cmds = append(cmds, m.fetchStep(m.currentStep))
		}
		cmds = append(cmds, m.prefetchSteps(m.currentStep+1, 5)...)
		cmds = append(cmds, m.scheduleTick())
		return m, tea.Batch(cmds...)

	case tea.KeyMsg:
		return m.handleKey(msg)
	}

	return m, nil
}

// handleKey processes key input for the replay screen.
func (m ReplayModel) handleKey(msg tea.KeyMsg) (ReplayModel, tea.Cmd) {
	switch msg.String() {
	case "left", "h":
		m.playing = false
		if m.currentStep > 0 {
			m.currentStep--
			if _, ok := m.steps[m.currentStep]; !ok {
				return m, m.fetchStep(m.currentStep)
			}
		}
		return m, nil

	case "right", "l":
		m.playing = false
		if m.currentStep < m.totalSteps-1 {
			m.currentStep++
			if _, ok := m.steps[m.currentStep]; !ok {
				return m, m.fetchStep(m.currentStep)
			}
		}
		return m, nil

	case "H":
		m.playing = false
		m.currentStep -= 5
		if m.currentStep < 0 {
			m.currentStep = 0
		}
		if _, ok := m.steps[m.currentStep]; !ok {
			return m, m.fetchStep(m.currentStep)
		}
		return m, nil

	case "L":
		m.playing = false
		m.currentStep += 5
		if m.currentStep >= m.totalSteps {
			m.currentStep = m.totalSteps - 1
		}
		if m.currentStep < 0 {
			m.currentStep = 0
		}
		if _, ok := m.steps[m.currentStep]; !ok {
			return m, m.fetchStep(m.currentStep)
		}
		return m, nil

	case "home":
		m.playing = false
		m.currentStep = 0
		if _, ok := m.steps[0]; !ok {
			return m, m.fetchStep(0)
		}
		return m, nil

	case "end":
		m.playing = false
		if m.totalSteps > 0 {
			m.currentStep = m.totalSteps - 1
		}
		if _, ok := m.steps[m.currentStep]; !ok {
			return m, m.fetchStep(m.currentStep)
		}
		return m, nil

	case " ":
		if m.playing {
			m.playing = false
			return m, nil
		}
		// Start playing.
		m.playing = true
		return m, m.scheduleTick()

	case "+", "=":
		m.playSpeed /= 2
		if m.playSpeed < 250*time.Millisecond {
			m.playSpeed = 250 * time.Millisecond
		}
		return m, nil

	case "-":
		m.playSpeed *= 2
		if m.playSpeed > 5*time.Second {
			m.playSpeed = 5 * time.Second
		}
		return m, nil

	case "d":
		m.showDiff = !m.showDiff
		return m, nil

	case "e":
		m.playing = false
		if m.totalSteps > 0 {
			m.currentStep = m.totalSteps - 1
		}
		if _, ok := m.steps[m.currentStep]; !ok {
			return m, m.fetchStep(m.currentStep)
		}
		return m, nil

	case "q", "esc":
		return m, func() tea.Msg {
			return SwitchScreenMsg{Screen: ScreenHistory}
		}
	}

	return m, nil
}

// View renders the replay screen.
func (m ReplayModel) View(width, height int) string {
	if m.err != nil {
		errMsg := theme.ErrorText.Render("Error loading replay: "+m.err.Error()) +
			"\n\n" + theme.KeyName.Render("q") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, errMsg)
	}

	if m.run == nil {
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
			theme.MutedText.Render("Loading replay..."))
	}

	// Transport bar (top row).
	transportBar := m.renderTransportBar(width)

	// Hint bar (bottom row).
	hintBar := m.renderHintBar(width)

	// Available height for main content.
	mainHeight := height - 2 // transport + hint

	// Split main area 55/45.
	leftWidth := (width * 55) / 100
	rightWidth := width - leftWidth - 1 // -1 for separator

	leftContent := m.renderReplayLeft(leftWidth, mainHeight)
	rightContent := m.renderReplayRight(rightWidth, mainHeight)

	mainArea := lipgloss.JoinHorizontal(lipgloss.Top,
		lipgloss.NewStyle().Width(leftWidth).Height(mainHeight).Render(leftContent),
		lipgloss.NewStyle().Width(1).Height(mainHeight).Foreground(theme.Muted).Render(strings.Repeat("│\n", mainHeight)),
		lipgloss.NewStyle().Width(rightWidth).Height(mainHeight).Render(rightContent),
	)

	return lipgloss.JoinVertical(lipgloss.Left, transportBar, mainArea, hintBar)
}

// renderTransportBar renders the top transport control bar.
func (m ReplayModel) renderTransportBar(width int) string {
	playIcon := "▶"
	if m.playing {
		playIcon = "⏸"
	}

	total := m.totalSteps
	if total == 0 {
		total = 1
	}
	var pct float64
	if total <= 1 {
		pct = 0
	} else {
		pct = float64(m.currentStep) / float64(total-1)
	}

	const barWidth = 30
	filled := int(pct * barWidth)
	if filled > barWidth {
		filled = barWidth
	}
	progressBar := strings.Repeat("█", filled) + strings.Repeat("░", barWidth-filled)

	speedStr := fmt.Sprintf("%.2fs/step", m.playSpeed.Seconds())

	diffIndicator := ""
	if m.showDiff {
		diffIndicator = "  " + theme.KeyName.Render("[DIFF]")
	}

	content := fmt.Sprintf(" %s  Step %d/%d  [%s] %d%%%s  Speed: %s",
		playIcon,
		m.currentStep+1,
		total,
		progressBar,
		int(pct*100),
		diffIndicator,
		speedStr,
	)

	return theme.StatusBar.Width(width).Render(content)
}

// renderHintBar renders the bottom key hint bar.
func (m ReplayModel) renderHintBar(width int) string {
	hints := []string{
		theme.KeyName.Render("←/h") + theme.KeyHint.Render(" prev"),
		theme.KeyName.Render("→/l") + theme.KeyHint.Render(" next"),
		theme.KeyName.Render("H/L") + theme.KeyHint.Render(" ±5"),
		theme.KeyName.Render("Home/End") + theme.KeyHint.Render(" first/last"),
		theme.KeyName.Render("Space") + theme.KeyHint.Render(" play"),
		theme.KeyName.Render("+/-") + theme.KeyHint.Render(" speed"),
		theme.KeyName.Render("d") + theme.KeyHint.Render(" diff"),
		theme.KeyName.Render("e") + theme.KeyHint.Render(" eval"),
		theme.KeyName.Render("q") + theme.KeyHint.Render(" back"),
	}
	bar := strings.Join(hints, "  ")
	return theme.StatusBar.Width(width).Render(" " + bar)
}

// renderReplayLeft renders the left panel: world state, actions, and messages.
func (m ReplayModel) renderReplayLeft(width, height int) string {
	var b strings.Builder

	step := m.steps[m.currentStep]

	// World state section.
	b.WriteString(theme.Subtitle.Render("WORLD STATE") + "\n")
	if step == nil {
		b.WriteString(theme.MutedText.Render("  (loading...)") + "\n")
	} else if m.showDiff && m.currentStep > 0 {
		prevStep := m.steps[m.currentStep-1]
		if prevStep != nil {
			lines := computeDiff(prevStep.StateSnapshot, step.StateSnapshot, width-4)
			for _, l := range lines {
				b.WriteString("  " + l + "\n")
			}
		} else {
			b.WriteString(theme.MutedText.Render("  (previous step not loaded)") + "\n")
		}
	} else {
		keys := make([]string, 0, len(step.StateSnapshot))
		for k := range step.StateSnapshot {
			if !strings.HasPrefix(k, "_") {
				keys = append(keys, k)
			}
		}
		sort.Strings(keys)
		for _, k := range keys {
			v := fmt.Sprintf("%v", step.StateSnapshot[k])
			if len(v) > width-len(k)-6 {
				v = v[:width-len(k)-6] + "…"
			}
			b.WriteString(fmt.Sprintf("  %s: %s\n",
				theme.KeyName.Render(k),
				theme.MutedText.Render(v),
			))
		}
		if len(keys) == 0 {
			b.WriteString(theme.MutedText.Render("  (no state)") + "\n")
		}
	}

	b.WriteString("\n")

	// Actions section.
	b.WriteString(theme.Subtitle.Render("ACTIONS THIS STEP") + "\n")
	if step == nil {
		b.WriteString(theme.MutedText.Render("  (loading...)") + "\n")
	} else if len(step.Actions) == 0 {
		b.WriteString(theme.MutedText.Render("  (none)") + "\n")
	} else {
		for _, action := range step.Actions {
			agentID := fmt.Sprintf("%v", action["agent_id"])
			agentName := m.agentNameByID(agentID)
			actionType := fmt.Sprintf("%v", action["action_type"])
			b.WriteString(fmt.Sprintf("  • %s %s\n",
				theme.KeyName.Render(agentName),
				theme.MutedText.Render(actionType),
			))
		}
	}

	b.WriteString("\n")

	// Messages section.
	b.WriteString(theme.Subtitle.Render("MESSAGES") + "\n")
	stepMsgs := m.messagesAtStep(m.currentStep)
	if len(stepMsgs) == 0 {
		b.WriteString(theme.MutedText.Render("  (none at this step)") + "\n")
	} else {
		for _, msg := range stepMsgs {
			sender := "(env)"
			if msg.FromAgentID != nil {
				sender = m.agentNameByID(*msg.FromAgentID)
			}
			content := msg.Content
			maxContentWidth := width - len(sender) - 6
			if maxContentWidth < 10 {
				maxContentWidth = 10
			}
			if len(content) > maxContentWidth {
				content = content[:maxContentWidth] + "…"
			}
			b.WriteString(fmt.Sprintf("  %s: %s\n",
				theme.AgentName.Render(sender),
				theme.TokenText.Render(content),
			))
		}
	}

	return b.String()
}

// renderReplayRight renders the right panel: agents, evaluation, metrics.
func (m ReplayModel) renderReplayRight(width, height int) string {
	var b strings.Builder

	// Agents section.
	b.WriteString(theme.Subtitle.Render("AGENTS") + "\n")
	if len(m.agents) == 0 {
		b.WriteString(theme.MutedText.Render("  (none)") + "\n")
	} else {
		for _, agent := range m.agents {
			if agent.Role != "human" {
				continue
			}
			loc := "-"
			hp := "-"
			stress := "-"
			if ds := agent.DynamicState; ds != nil {
				if v, ok := ds["location"]; ok {
					loc = fmt.Sprintf("%v", v)
				}
				if v, ok := ds["health"]; ok {
					hp = fmt.Sprintf("%.0f%%", toFloat(v)*100)
				}
				if v, ok := ds["stress"]; ok {
					stress = fmt.Sprintf("%.0f%%", toFloat(v)*100)
				}
			}
			nameStr := agent.Name
			if len(nameStr) > 14 {
				nameStr = nameStr[:14]
			}
			locStr := loc
			if len(locStr) > 12 {
				locStr = locStr[:12]
			}
			b.WriteString(fmt.Sprintf("  %-14s  %-12s  HP:%s Stress:%s\n",
				theme.AgentName.Render(nameStr),
				theme.MutedText.Render(locStr),
				theme.TokenText.Render(hp),
				theme.TokenText.Render(stress),
			))
		}
	}

	b.WriteString("\n")

	// Evaluation section (last step only).
	isLastStep := m.totalSteps > 0 && m.currentStep == m.totalSteps-1
	if isLastStep && m.run != nil && len(m.run.Evaluation) > 0 {
		b.WriteString(theme.Subtitle.Render("EVALUATION") + "\n")
		keys := sortedKeys(m.run.Evaluation)
		for _, k := range keys {
			v := fmt.Sprintf("%v", m.run.Evaluation[k])
			if len(v) > width-len(k)-6 {
				v = v[:width-len(k)-6] + "…"
			}
			b.WriteString(fmt.Sprintf("  %s: %s\n",
				theme.KeyName.Render(k),
				theme.MutedText.Render(v),
			))
		}
		b.WriteString("\n")
	}

	// Metrics section.
	if m.run != nil && len(m.run.Metrics) > 0 {
		b.WriteString(theme.Subtitle.Render("METRICS") + "\n")
		keys := sortedKeys(m.run.Metrics)
		for _, k := range keys {
			v := fmt.Sprintf("%v", m.run.Metrics[k])
			if len(v) > width-len(k)-6 {
				v = v[:width-len(k)-6] + "…"
			}
			b.WriteString(fmt.Sprintf("  %s: %s\n",
				theme.KeyName.Render(k),
				theme.MutedText.Render(v),
			))
		}
	}

	return b.String()
}

// computeDiff computes a styled diff between two world state snapshots.
// Returns a slice of styled lines (added, changed, removed).
func computeDiff(prev, curr map[string]interface{}, lineWidth int) []string {
	added := lipgloss.NewStyle().Foreground(lipgloss.Color("#30D158"))
	changed := lipgloss.NewStyle().Foreground(lipgloss.Color("#FFD60A"))
	removed := lipgloss.NewStyle().Foreground(lipgloss.Color("#FF453A"))

	var lines []string

	// Added and changed keys.
	keys := sortedKeys(curr)
	for _, k := range keys {
		if strings.HasPrefix(k, "_") {
			continue
		}
		currVal := fmt.Sprintf("%v", curr[k])
		if prevVal, ok := prev[k]; !ok {
			lines = append(lines, added.Render(fmt.Sprintf("+ %s: %s", k, currVal)))
		} else {
			prevStr := fmt.Sprintf("%v", prevVal)
			if prevStr != currVal {
				lines = append(lines, changed.Render(fmt.Sprintf("~ %s: %s -> %s", k, prevStr, currVal)))
			}
		}
	}

	// Removed keys.
	prevKeys := sortedKeys(prev)
	for _, k := range prevKeys {
		if strings.HasPrefix(k, "_") {
			continue
		}
		if _, ok := curr[k]; !ok {
			lines = append(lines, removed.Render(fmt.Sprintf("- %s", k)))
		}
	}

	if len(lines) == 0 {
		lines = append(lines, lipgloss.NewStyle().Foreground(lipgloss.Color("#636366")).Render("(no changes)"))
	}

	return lines
}

// messagesAtStep filters messages that belong to the given step index.
func (m ReplayModel) messagesAtStep(step int) []api.MessageResponse {
	var result []api.MessageResponse
	for _, msg := range m.messages {
		if msg.StepIndex == step {
			result = append(result, msg)
		}
	}
	return result
}

// agentNameByID looks up an agent's name by ID.
func (m ReplayModel) agentNameByID(id string) string {
	for _, a := range m.agents {
		if a.ID == id {
			return a.Name
		}
	}
	// Return truncated ID as fallback.
	if len(id) > 8 {
		return id[:8]
	}
	return id
}

// sortedKeys returns the keys of a map in sorted order.
func sortedKeys(m map[string]interface{}) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

// toFloat converts an interface{} to float64 best-effort.
func toFloat(v interface{}) float64 {
	switch val := v.(type) {
	case float64:
		return val
	case float32:
		return float64(val)
	case int:
		return float64(val)
	case int64:
		return float64(val)
	}
	return 0
}
