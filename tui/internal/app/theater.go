package app

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// TheaterEntry represents one moment on stage (public + private).
type TheaterEntry struct {
	AgentName  string
	Location   string
	Step       int
	Action     string // public stage direction
	Speech     string // public dialogue
	Thought    string // private inner monologue
	Emotion    string
	IsMovement bool
}

// DirectorNote is a system-level observation shown in the footer.
type DirectorNote struct {
	Step    int
	Content string
	Type    string // "governance", "contagion", "scene", "system"
}

// TheaterModel is the cinematic theater view screen.
type TheaterModel struct {
	client *api.Client
	runID  string
	run    *api.RunResponse

	entries       []TheaterEntry
	directorNotes []DirectorNote
	focusAgent    int // -1 = all agents, 0+ = index into agent names
	agentNames    []string
	paused        bool
	scrollPos     int
	maxEntries    int
}

// NewTheaterModel creates a theater view for the given run.
func NewTheaterModel(client *api.Client, runID string, run *api.RunResponse) TheaterModel {
	return TheaterModel{
		client:     client,
		runID:      runID,
		run:        run,
		focusAgent: -1,
		maxEntries: 500,
	}
}

// Init is a no-op; theater receives events via WS passthrough.
func (m TheaterModel) Init() tea.Cmd {
	return nil
}

// Update handles key input and WS events.
func (m TheaterModel) Update(msg tea.Msg) (TheaterModel, tea.Cmd) {
	switch msg := msg.(type) {
	case WSEventMsg:
		m.handleWSEvent(msg.Event)
		return m, nil

	case tea.KeyMsg:
		return m.handleKey(msg)
	}
	return m, nil
}

// handleWSEvent processes WS events for theater display.
func (m *TheaterModel) handleWSEvent(evt api.WSMessage) {
	switch evt.Event {
	case "scene_turn":
		agentName, _ := evt.Data["agent_name"].(string)
		action, _ := evt.Data["action"].(string)
		speech, _ := evt.Data["speech"].(string)
		thought, _ := evt.Data["thought"].(string)
		emotion, _ := evt.Data["emotion"].(string)
		location, _ := evt.Data["location"].(string)
		step := int(safeFloat(evt.Data, "step_index"))

		entry := TheaterEntry{
			AgentName: agentName,
			Location:  location,
			Step:      step,
			Action:    action,
			Speech:    speech,
			Thought:   thought,
			Emotion:   emotion,
		}
		m.addEntry(entry)
		m.trackAgent(agentName)

	case "message":
		agentName, _ := evt.Data["agent_name"].(string)
		content, _ := evt.Data["content"].(string)
		location, _ := evt.Data["location"].(string)
		step := int(safeFloat(evt.Data, "step_index"))

		entry := TheaterEntry{
			AgentName: agentName,
			Location:  location,
			Step:      step,
			Speech:    content,
		}
		m.addEntry(entry)
		m.trackAgent(agentName)

	case "agent_moved":
		agentName, _ := evt.Data["agent_name"].(string)
		from, _ := evt.Data["from"].(string)
		to, _ := evt.Data["to"].(string)
		step := int(safeFloat(evt.Data, "step"))

		entry := TheaterEntry{
			AgentName:  agentName,
			Step:       step,
			Action:     fmt.Sprintf("Exits %s, enters %s", from, to),
			Location:   to,
			IsMovement: true,
		}
		m.addEntry(entry)

	case "emotion_contagion":
		source, _ := evt.Data["source_name"].(string)
		target, _ := evt.Data["target_name"].(string)
		mechanism, _ := evt.Data["mechanism"].(string)
		delta, _ := evt.Data["delta"].(float64)
		step := int(safeFloat(evt.Data, "step"))

		note := DirectorNote{
			Step:    step,
			Type:    "contagion",
			Content: fmt.Sprintf("%s %s %s (%+.1f stress)", source, mechanism, target, delta),
		}
		m.directorNotes = append(m.directorNotes, note)
		if len(m.directorNotes) > 50 {
			m.directorNotes = m.directorNotes[len(m.directorNotes)-50:]
		}

	case "step_completed":
		step := int(safeFloat(evt.Data, "step"))
		if m.run != nil {
			m.run.CurrentStep = int(step)
		}

	case "run_completed", "run_stopped":
		status := strings.TrimPrefix(evt.Event, "run_")
		if m.run != nil {
			m.run.Status = status
		}
	}
}

func (m *TheaterModel) addEntry(entry TheaterEntry) {
	if m.paused {
		return
	}
	m.entries = append(m.entries, entry)
	if len(m.entries) > m.maxEntries {
		m.entries = m.entries[len(m.entries)-m.maxEntries:]
	}
}

func (m *TheaterModel) trackAgent(name string) {
	for _, n := range m.agentNames {
		if n == name {
			return
		}
	}
	m.agentNames = append(m.agentNames, name)
}

func (m TheaterModel) handleKey(msg tea.KeyMsg) (TheaterModel, tea.Cmd) {
	switch msg.String() {
	case " ":
		m.paused = !m.paused

	case "1", "2", "3", "4", "5", "6", "7", "8", "9":
		idx := int(msg.String()[0]-'0') - 1
		if idx < len(m.agentNames) {
			if m.focusAgent == idx {
				m.focusAgent = -1 // toggle off
			} else {
				m.focusAgent = idx
			}
		}

	case "0":
		m.focusAgent = -1 // show all

	case "up", "k":
		if m.scrollPos > 0 {
			m.scrollPos--
		}
	case "down", "j":
		m.scrollPos++

	case "q", "esc":
		return m, func() tea.Msg {
			return SwitchScreenMsg{Screen: ScreenDashboard, Data: m.runID}
		}
	}
	return m, nil
}

// View renders the theater in two-column dramatic layout.
func (m TheaterModel) View(width, height int) string {
	if m.run == nil {
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
			theme.MutedText.Render("Loading theater..."))
	}

	// Layout: header (1) + main (height-4) + director notes (2) + status (1)
	headerH := 1
	directorH := 3
	statusH := 1
	mainH := height - headerH - directorH - statusH
	if mainH < 5 {
		mainH = 5
	}

	// Header
	focusLabel := "All Agents"
	if m.focusAgent >= 0 && m.focusAgent < len(m.agentNames) {
		focusLabel = m.agentNames[m.focusAgent]
	}
	pauseLabel := ""
	if m.paused {
		pauseLabel = lipgloss.NewStyle().Foreground(theme.Warning).Bold(true).Render(" [PAUSED]")
	}
	header := theme.Title.Render(" THEATER") + "  " +
		theme.MutedText.Render("focus: ") +
		lipgloss.NewStyle().Foreground(theme.Primary).Render(focusLabel) +
		pauseLabel

	header = lipgloss.NewStyle().Width(width).Background(theme.Surface).Render(header)

	// Filter entries by focus agent
	entries := m.entries
	if m.focusAgent >= 0 && m.focusAgent < len(m.agentNames) {
		focusName := m.agentNames[m.focusAgent]
		var filtered []TheaterEntry
		for _, e := range entries {
			if e.AgentName == focusName {
				filtered = append(filtered, e)
			}
		}
		entries = filtered
	}

	// Main area: two columns
	stageWidth := width * 55 / 100
	backstageWidth := width - stageWidth

	stageContent := m.renderStage(entries, stageWidth-4, mainH)
	backstageContent := m.renderBackstage(entries, backstageWidth-4, mainH)

	stagePanel := lipgloss.NewStyle().
		Width(stageWidth-2).Height(mainH).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Accent).
		Padding(0, 1).
		Render(stageContent)

	backstagePanel := lipgloss.NewStyle().
		Width(backstageWidth-2).Height(mainH).
		Border(lipgloss.RoundedBorder()).
		BorderForeground(theme.Primary).
		Padding(0, 1).
		Render(backstageContent)

	main := lipgloss.JoinHorizontal(lipgloss.Top, stagePanel, backstagePanel)

	// Director's Notes footer
	director := m.renderDirectorNotes(width, directorH)

	// Status bar
	step := 0
	maxSteps := 0
	if m.run != nil {
		step = m.run.CurrentStep
		maxSteps = m.run.MaxSteps
	}
	status := lipgloss.NewStyle().Background(theme.Surface).Width(width).Render(
		fmt.Sprintf(" Step %d/%d  %s  %s  %s  %s",
			step, maxSteps,
			theme.KeyName.Render("Space")+theme.KeyHint.Render(" pause"),
			theme.KeyName.Render("1-9")+theme.KeyHint.Render(" focus"),
			theme.KeyName.Render("0")+theme.KeyHint.Render(" all"),
			theme.KeyName.Render("q/Esc")+theme.KeyHint.Render(" back"),
		))

	return lipgloss.JoinVertical(lipgloss.Left, header, main, director, status)
}

// renderStage renders the public left column.
func (m TheaterModel) renderStage(entries []TheaterEntry, width, height int) string {
	var lines []string
	lines = append(lines, lipgloss.NewStyle().Foreground(theme.Accent).Bold(true).Render("STAGE"))
	lines = append(lines, "")

	if len(entries) == 0 {
		lines = append(lines, theme.MutedText.Render("The curtain rises..."))
		return strings.Join(lines, "\n")
	}

	currentLoc := ""
	for _, e := range entries {
		// Scene header on location change
		if e.Location != currentLoc && e.Location != "" {
			currentLoc = e.Location
			lines = append(lines, "")
			lines = append(lines,
				lipgloss.NewStyle().Foreground(theme.Primary).Bold(true).
					Render(fmt.Sprintf("\u2501\u2501 %s \u2501\u2501", currentLoc)))
		}

		nameStyle := lipgloss.NewStyle().Foreground(theme.Accent).Bold(true)

		if e.IsMovement {
			lines = append(lines,
				theme.MutedText.Render(fmt.Sprintf("  [%s %s]", e.AgentName, e.Action)))
			continue
		}

		// Stage direction (action)
		if e.Action != "" {
			lines = append(lines,
				theme.MutedText.Render(fmt.Sprintf("  (%s %s)", e.AgentName, e.Action)))
		}

		// Dialogue (speech)
		if e.Speech != "" {
			speech := e.Speech
			if len(speech) > width*3 {
				speech = speech[:width*3] + "..."
			}
			lines = append(lines,
				fmt.Sprintf("  %s: %s",
					nameStyle.Render(e.AgentName),
					lipgloss.NewStyle().Foreground(theme.Text).Render(speech)))
		}

		// Emotion tag
		if e.Emotion != "" {
			lines = append(lines,
				theme.MutedText.Render(fmt.Sprintf("    [feeling: %s]", e.Emotion)))
		}
	}

	// Apply scroll and height limit
	allLines := strings.Split(strings.Join(lines, "\n"), "\n")
	return applyScroll(allLines, m.scrollPos, height)
}

// renderBackstage renders the private right column.
func (m TheaterModel) renderBackstage(entries []TheaterEntry, width, height int) string {
	var lines []string
	lines = append(lines, lipgloss.NewStyle().Foreground(theme.Primary).Bold(true).Render("BACKSTAGE"))
	lines = append(lines, "")

	hasThoughts := false
	for _, e := range entries {
		if e.Thought == "" {
			continue
		}
		hasThoughts = true

		nameStyle := lipgloss.NewStyle().Foreground(theme.Primary).Bold(true)
		thought := e.Thought
		if len(thought) > width*4 {
			thought = thought[:width*4] + "..."
		}

		lines = append(lines,
			fmt.Sprintf("  %s %s",
				nameStyle.Render(e.AgentName+":"),
				theme.MutedText.Render("(thinking)")))
		lines = append(lines,
			"    "+lipgloss.NewStyle().Foreground(lipgloss.Color("#AEAEB2")).Italic(true).
				Render(thought))
		lines = append(lines, "")
	}

	if !hasThoughts {
		lines = append(lines, theme.MutedText.Render("No inner monologue yet..."))
		lines = append(lines, "")
		lines = append(lines, theme.MutedText.Render("Thoughts appear when agents"))
		lines = append(lines, theme.MutedText.Render("use the cinematic reasoning path."))
	}

	allLines := strings.Split(strings.Join(lines, "\n"), "\n")
	return applyScroll(allLines, m.scrollPos, height)
}

// renderDirectorNotes renders the bottom strip with system observations.
func (m TheaterModel) renderDirectorNotes(width, height int) string {
	style := lipgloss.NewStyle().
		Width(width).
		Height(height).
		Background(lipgloss.Color("#1A1A2E")).
		Foreground(theme.Muted).
		Padding(0, 1)

	if len(m.directorNotes) == 0 {
		return style.Render(theme.MutedText.Render("Director's Notes: watching..."))
	}

	// Show last few notes that fit
	var notes []string
	start := len(m.directorNotes) - height
	if start < 0 {
		start = 0
	}
	for _, n := range m.directorNotes[start:] {
		icon := "\u00b7" // ·
		switch n.Type {
		case "governance":
			icon = "\u2696" // ⚖
		case "contagion":
			icon = "\u26a1" // ⚡
		case "scene":
			icon = "\u2606" // ☆
		}
		notes = append(notes, fmt.Sprintf("%s [%d] %s", icon, n.Step, n.Content))
	}

	return style.Render(strings.Join(notes, "\n"))
}

// applyScroll trims lines to fit height with scroll offset.
func applyScroll(lines []string, scrollPos, height int) string {
	if len(lines) <= height {
		return strings.Join(lines, "\n")
	}

	// Auto-scroll to bottom unless manually scrolled
	start := len(lines) - height
	if scrollPos > 0 && scrollPos < start {
		start = scrollPos
	}
	if start < 0 {
		start = 0
	}
	end := start + height
	if end > len(lines) {
		end = len(lines)
	}

	return strings.Join(lines[start:end], "\n")
}
