package cmd

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/jasperan/emotion-engine/tui/internal/app"
	"github.com/spf13/cobra"
)

var (
	serverURL string
	sshPort   int
)

var rootCmd = &cobra.Command{
	Use:   "emotionsim-tui",
	Short: "EmotionSim Terminal Dashboard",
	Long:  "A Bubble Tea TUI for monitoring EmotionSim multi-agent simulations in real time.",
	RunE: func(cmd *cobra.Command, args []string) error {
		a := app.NewApp(serverURL, false)

		p := tea.NewProgram(a, tea.WithAltScreen())
		a.SetProgram(p)

		// Re-wrap since SetProgram mutates the pointer receiver
		if _, err := p.Run(); err != nil {
			return fmt.Errorf("TUI error: %w", err)
		}
		return nil
	},
}

func init() {
	rootCmd.Flags().StringVar(&serverURL, "server", "http://localhost:8000", "EmotionSim backend URL")
	rootCmd.Flags().IntVar(&sshPort, "ssh-port", 0, "SSH server port (0 = disabled)")
}

// Execute runs the root command.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
