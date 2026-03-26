package app

import (
	"fmt"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/harmonica"
	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
	"github.com/jasperan/emotion-engine/tui/internal/theme"
)

const banner = ` ███████╗███╗   ███╗ ██████╗ ████████╗██╗ ██████╗ ███╗   ██╗
 ██╔════╝████╗ ████║██╔═══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
 █████╗  ██╔████╔██║██║   ██║   ██║   ██║██║   ██║██╔██╗ ██║
 ██╔══╝  ██║╚██╔╝██║██║   ██║   ██║   ██║██║   ██║██║╚██╗██║
 ███████╗██║ ╚═╝ ██║╚██████╔╝   ██║   ██║╚██████╔╝██║ ╚████║
 ╚══════╝╚═╝     ╚═╝ ╚═════╝    ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
      ███████╗███╗   ██╗ ██████╗ ██╗███╗   ██╗███████╗
      ██╔════╝████╗  ██║██╔════╝ ██║████╗  ██║██╔════╝
      █████╗  ██╔██╗ ██║██║  ███╗██║██╔██╗ ██║█████╗
      ██╔══╝  ██║╚██╗██║██║   ██║██║██║╚██╗██║██╔══╝
      ███████╗██║ ╚████║╚██████╔╝██║██║ ╚████║███████╗
      ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝`

// --- Messages ---

type connectionCheckMsg struct {
	err            error
	scenarioCount  int
}

type fadeTickMsg time.Time
type retryTickMsg struct{}

// --- Model ---

// SplashModel implements the splash/connection screen.
type SplashModel struct {
	client         *api.Client
	connected      bool
	checking       bool
	errMsg         string
	scenarioCount  int
	opacity        float64
	velocity       float64
	spring         harmonica.Spring
	done           bool
	version        string
	retryCount     int
	maxRetries     int
}

// NewSplashModel creates a fresh splash screen model.
func NewSplashModel(client *api.Client, version string) SplashModel {
	return SplashModel{
		client:     client,
		opacity:    0,
		spring:     harmonica.NewSpring(harmonica.FPS(60), 5.0, 0.4),
		version:    version,
		maxRetries: 10,
	}
}

// Init starts the connection check and fade animation.
func (m SplashModel) Init() tea.Cmd {
	return tea.Batch(
		m.checkConnection(),
		m.fadeTick(),
	)
}

// Update handles connection results, fade ticks, and key input.
func (m SplashModel) Update(msg tea.Msg) (SplashModel, tea.Cmd) {
	switch msg := msg.(type) {
	case connectionCheckMsg:
		m.checking = false
		if msg.err != nil {
			m.connected = false
			m.errMsg = msg.err.Error()
			// Auto-retry after 3 seconds if under the limit
			if m.retryCount < m.maxRetries {
				return m, tea.Tick(3*time.Second, func(t time.Time) tea.Msg {
					return retryTickMsg{}
				})
			}
		} else {
			m.connected = true
			m.errMsg = ""
			m.scenarioCount = msg.scenarioCount
		}
		return m, nil

	case retryTickMsg:
		if !m.connected && m.retryCount < m.maxRetries {
			m.retryCount++
			m.checking = true
			return m, m.checkConnection()
		}
		return m, nil

	case fadeTickMsg:
		if m.opacity < 1.0 {
			m.opacity, m.velocity = m.spring.Update(m.opacity, m.velocity, 1.0)
			if m.opacity > 1.0 {
				m.opacity = 1.0
			}
			return m, m.fadeTick()
		}
		return m, nil

	case tea.KeyMsg:
		switch msg.String() {
		case "enter":
			if m.connected {
				return m, func() tea.Msg {
					return SwitchScreenMsg{Screen: ScreenScenarios}
				}
			}
		case "r":
			m.checking = true
			m.errMsg = ""
			m.retryCount = 0
			return m, m.checkConnection()
		case "q":
			return m, tea.Quit
		}
	}

	return m, nil
}

// View renders the splash screen.
func (m SplashModel) View(width, height int) string {
	// Banner with fade effect via color interpolation
	alpha := m.opacity
	if alpha < 0 {
		alpha = 0
	}
	bannerColor := lerpColor("#1C1C1E", "#5E5CE6", alpha)
	bannerStyle := lipgloss.NewStyle().Foreground(lipgloss.Color(bannerColor))
	renderedBanner := bannerStyle.Render(banner)

	// Status line
	var status string
	if m.checking {
		if m.retryCount > 0 {
			status = theme.MutedText.Render(fmt.Sprintf("⟳ Retrying connection (%d/%d)...", m.retryCount, m.maxRetries))
		} else {
			status = theme.MutedText.Render("⟳ Connecting to backend...")
		}
	} else if m.connected {
		status = theme.StatusActive.Render(theme.StatusDot) + " " +
			theme.Title.Render(fmt.Sprintf("Connected — %d scenarios available", m.scenarioCount))
	} else if m.errMsg != "" {
		if m.retryCount < m.maxRetries {
			status = theme.StatusError.Render(theme.StatusDot) + " " +
				theme.ErrorText.Render("Connection failed, retrying...")
		} else {
			status = theme.StatusError.Render(theme.StatusDot) + " " +
				theme.ErrorText.Render("Connection failed: "+m.errMsg)
		}
	} else {
		status = theme.MutedText.Render("Waiting...")
	}

	// Navigation hints
	var hints string
	if m.connected {
		hints = theme.KeyName.Render("Enter") + theme.KeyHint.Render(" browse scenarios") +
			"  " + theme.KeyName.Render("q") + theme.KeyHint.Render(" quit")
	} else {
		hints = theme.KeyName.Render("r") + theme.KeyHint.Render(" retry") +
			"  " + theme.KeyName.Render("q") + theme.KeyHint.Render(" quit")
	}

	versionLine := theme.MutedText.Render("v" + m.version)

	content := lipgloss.JoinVertical(lipgloss.Center,
		renderedBanner,
		"",
		status,
		"",
		hints,
		"",
		versionLine,
	)

	return lipgloss.Place(width, height, lipgloss.Center, lipgloss.Center, content)
}

// --- Commands ---

func (m SplashModel) checkConnection() tea.Cmd {
	client := m.client
	return func() tea.Msg {
		err := client.Ping()
		if err != nil {
			return connectionCheckMsg{err: err}
		}
		scenarios, err := client.ListScenarios()
		if err != nil {
			return connectionCheckMsg{err: err}
		}
		return connectionCheckMsg{scenarioCount: len(scenarios)}
	}
}

func (m SplashModel) fadeTick() tea.Cmd {
	return tea.Tick(time.Second/60, func(t time.Time) tea.Msg {
		return fadeTickMsg(t)
	})
}

// lerpColor linearly interpolates between two hex colors.
func lerpColor(from, to string, t float64) string {
	fr, fg, fb := hexToRGB(from)
	tr, tg, tb := hexToRGB(to)

	r := fr + int(float64(tr-fr)*t)
	g := fg + int(float64(tg-fg)*t)
	b := fb + int(float64(tb-fb)*t)

	return fmt.Sprintf("#%02x%02x%02x", r, g, b)
}

func hexToRGB(hex string) (int, int, int) {
	if len(hex) == 7 && hex[0] == '#' {
		var r, g, b int
		fmt.Sscanf(hex[1:], "%02x%02x%02x", &r, &g, &b)
		return r, g, b
	}
	return 0, 0, 0
}
