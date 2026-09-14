package ssh

import (
	"fmt"

	tea "charm.land/bubbletea/v2"
	"charm.land/ssh"
	"charm.land/wish/v2"
	bm "charm.land/wish/v2/bubbletea"
	"github.com/jasperan/emotion-engine/tui/internal/app"
)

// ListenAndServe starts a Wish SSH server on the given port.
// Each connection gets its own read-only Bubble Tea program.
//
// No program options are returned here. v2 removed the alt-screen program
// option, so the alternate screen is declared by the model instead (App.View sets
// View.AltScreen). That is not a workaround: the terminal feature has to live on
// the model, because this entry point hands the model to a middleware and has no
// way to reach the program's options. The local entry point (cmd/root.go) gets
// the same behaviour from the same place, so local and SSH sessions render alike.
func ListenAndServe(port int, serverURL string, version string) error {
	s, err := wish.NewServer(
		wish.WithAddress(fmt.Sprintf(":%d", port)),
		wish.WithMiddleware(
			bm.Middleware(func(sess ssh.Session) (tea.Model, []tea.ProgramOption) {
				a := app.NewApp(serverURL, true, version)
				return a, nil
			}),
		),
	)
	if err != nil {
		return fmt.Errorf("failed to create SSH server: %w", err)
	}

	return s.ListenAndServe()
}
