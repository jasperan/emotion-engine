package ssh

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/ssh"
	"github.com/charmbracelet/wish"
	bm "github.com/charmbracelet/wish/bubbletea"
	"github.com/jasperan/emotion-engine/tui/internal/app"
)

// ListenAndServe starts a Wish SSH server on the given port.
// Each connection gets its own read-only Bubble Tea program.
func ListenAndServe(port int, serverURL string, version string) error {
	s, err := wish.NewServer(
		wish.WithAddress(fmt.Sprintf(":%d", port)),
		wish.WithMiddleware(
			bm.Middleware(func(sess ssh.Session) (tea.Model, []tea.ProgramOption) {
				a := app.NewApp(serverURL, true, version)
				return a, []tea.ProgramOption{tea.WithAltScreen()}
			}),
		),
	)
	if err != nil {
		return fmt.Errorf("failed to create SSH server: %w", err)
	}

	return s.ListenAndServe()
}
