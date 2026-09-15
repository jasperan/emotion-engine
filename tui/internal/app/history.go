package app

import (
	"fmt"

	tea "charm.land/bubbletea/v2"
	"charm.land/huh/v2"
	"charm.land/lipgloss/v2"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/huhstyle"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

// --- Messages ---

type runsLoadedMsg struct {
	runs []api.RunResponse
	err  error
}

const keyRun = "run"

// runSelection is the storage the run Select is bound to. Pointer for the same
// reason as scenarioSelection: models are copied by value on every Update.
type runSelection struct {
	id string
}

// runOptionLabel is the option text for a run. The old list delegate drew the
// id, status and step counter on one line and the scenario on the next; the
// scenario moves beneath the form, alongside the status colour.
func runOptionLabel(r api.RunResponse) string {
	id := r.ID
	if len(id) > 8 {
		id = id[:8]
	}
	return fmt.Sprintf("#%s  %s  step %d/%d", id, r.Status, r.CurrentStep, r.MaxSteps)
}

// buildHistoryForm builds the run history browser as a huh form.
func buildHistoryForm(runs []api.RunResponse, sel *runSelection) (*huh.Form, *huh.Select[string]) {
	opts := make([]huh.Option[string], 0, len(runs))
	for _, r := range runs {
		opts = append(opts, huh.NewOption(runOptionLabel(r), r.ID))
	}

	selectField := huh.NewSelect[string]().
		Key(keyRun).
		Title("Run History").
		Description("Pick a run to open. Completed runs open in Replay.").
		Options(opts...).
		Value(&sel.id)

	form := huh.NewForm(huh.NewGroup(selectField)).
		WithTheme(huh.ThemeFunc(huhstyle.Theme)).
		WithAccessible(huhstyle.Accessible()).
		// The screen draws its own hint bar from footerBindingsForScreen, and
		// the F1 overlay documents the same keys. huh's footer would be a
		// second, differently-worded copy of the same hints.
		WithShowHelp(false)

	return form, selectField
}

// runTargetScreen is where a run opens: finished runs have a full trace to
// replay, live ones have a dashboard to attach to.
func runTargetScreen(status string) Screen {
	switch status {
	case "completed", "failed", "cancelled":
		return ScreenReplay
	default:
		return ScreenDashboard
	}
}

// --- HistoryModel ---

// HistoryModel is the run history browser screen.
type HistoryModel struct {
	client    *api.Client
	runs      []api.RunResponse
	selection *runSelection
	form      *huh.Form
	selectF   *huh.Select[string]
	loading   bool
	errMsg    string

	// width and height are the last size reported by tea.WindowSizeMsg. The
	// form is sized from these in Update, because huh rebuilds a form's content
	// on Update and a width applied during View would land a frame too late.
	width  int
	height int
}

// NewHistoryModel creates a new history browser.
func NewHistoryModel(client *api.Client) HistoryModel {
	return HistoryModel{
		client:    client,
		selection: &runSelection{},
		loading:   true,
	}
}

// Init fetches runs from the backend.
func (m HistoryModel) Init() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		runs, err := client.ListRuns("", 50)
		return runsLoadedMsg{runs: runs, err: err}
	}
}

// Update handles list navigation and key input.
func (m HistoryModel) Update(msg tea.Msg) (HistoryModel, tea.Cmd) {
	switch msg := msg.(type) {
	case runsLoadedMsg:
		m.loading = false
		if msg.err != nil {
			m.errMsg = msg.err.Error()
			return m, nil
		}
		m.runs = msg.runs
		m.form, m.selectF = buildHistoryForm(msg.runs, m.selection)
		m.resizeForm()
		return m, m.form.Init()

	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.resizeForm()
		// Still delegated to the form below, which is what rebuilds its content.

	case tea.KeyPressMsg:
		// The Select owns every key while its "/" filter is capturing input.
		if m.selectF != nil && !m.selectF.GetFiltering() {
			switch msg.String() {
			case "r", "enter":
				// Enter is handled by the form's submit; r is the documented
				// shortcut for opening the highlighted run.
				if msg.String() == "r" {
					if run, ok := m.hoveredRun(); ok {
						return m, switchToData(runTargetScreen(run.Status), run.ID)
					}
				}
			case "a":
				return m, switchTo(ScreenAnalytics)
			case "q", "esc":
				return m, switchTo(ScreenScenarios)
			}
		}
	}

	if m.form == nil {
		return m, nil
	}

	model, cmd := m.form.Update(msg)
	if form, ok := model.(*huh.Form); ok {
		m.form = form
	}
	if m.form.State == huh.StateCompleted {
		if run, ok := m.hoveredRun(); ok {
			return m, switchToData(runTargetScreen(run.Status), run.ID)
		}
	}
	return m, cmd
}

// resizeForm applies the last reported terminal size to the form. It is a
// no-op until the form exists, so a size that arrives before the runs load is
// applied when the form is built.
func (m *HistoryModel) resizeForm() {
	if m.form == nil {
		return
	}
	m.form.WithWidth(formContentWidth(m.width))
	m.form.WithHeight(formHeight(m.height))
	m.selectF.Height(selectHeight(m.height, len(m.runs)))
}

// hoveredRun returns the run under the cursor.
func (m HistoryModel) hoveredRun() (api.RunResponse, bool) {
	if m.selectF == nil {
		return api.RunResponse{}, false
	}
	id, ok := m.selectF.Hovered()
	if !ok {
		return api.RunResponse{}, false
	}
	for _, r := range m.runs {
		if r.ID == id {
			return r, true
		}
	}
	return api.RunResponse{}, false
}

// View renders the run history browser.
func (m HistoryModel) View(width, height int) string {
	if m.errMsg != "" {
		errView := theme.ErrorText.Render("Failed to load runs: "+m.errMsg) +
			"\n\n" + theme.KeyName.Render("q/Esc") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, errView)
	}

	if m.loading {
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center,
			theme.MutedText.Render("Loading run history..."))
	}

	if len(m.runs) == 0 {
		empty := theme.MutedText.Render("No runs yet.") +
			"\n\n" + theme.KeyName.Render("q/Esc") + theme.KeyHint.Render(" back")
		return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, empty)
	}

	body := trimFormPad(m.form.View())
	if run, ok := m.hoveredRun(); ok {
		status := lipgloss.NewStyle().Foreground(theme.StatusColor(run.Status)).Render(run.Status)
		body += "\n\n" + status + theme.MutedText.Render("  scenario: "+run.ScenarioID)
	}

	hints := hintBar(width, footerBindingsForScreen(ScreenHistory))

	return lipgloss.Place(width, height-2, lipgloss.Center, lipgloss.Center, body) + "\n" + hints
}
