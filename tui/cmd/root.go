package cmd

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/jasperan/emotion-engine/tui/internal/app"
	"github.com/jasperan/emotion-engine/tui/internal/backend"
	sshsrv "github.com/jasperan/emotion-engine/tui/internal/ssh"
	"github.com/spf13/cobra"
)

var (
	serverURL  string
	sshPort    int
	noBackend  bool
	noVLLM     bool
	vllmURL    string
	vllmModel  string
	vllmPort   int
	backendDir string
	pythonPath string
	Version    string
)

var rootCmd = &cobra.Command{
	Use:   "emotionsim-tui",
	Short: "Emotion Engine Terminal Dashboard",
	Long:  "A Bubble Tea TUI for monitoring Emotion Engine multi-agent simulations in real time.",
	RunE: func(cmd *cobra.Command, args []string) error {
		var proc *backend.Process
		var vllmProc *backend.Process

		// Auto-start vLLM unless disabled
		if !noVLLM && !backend.IsVLLMRunning(vllmURL) {
			vllmBin := backend.FindVLLM()
			if vllmBin != "" {
				var err error
				vllmProc, err = backend.StartVLLM(vllmBin, vllmModel, vllmPort)
				if err != nil {
					log.Printf("Warning: could not start vLLM: %v", err)
				} else {
					log.Printf("Started vLLM (model=%s, port=%d, log=%s)", vllmModel, vllmPort, vllmProc.LogPath())
				}
			} else {
				log.Printf("Warning: vLLM binary not found, skipping auto-start (Ollama fallback will be used)")
			}
		}

		// Auto-start backend unless disabled
		if !noBackend && !isBackendRunning(serverURL) {
			dir := backendDir
			if dir == "" {
				dir = backend.FindBackendDir()
			}
			if dir != "" {
				var err error
				proc, err = backend.Start(dir, pythonPath)
				if err != nil {
					log.Printf("Warning: could not start backend: %v", err)
				}
			}
		}

		// Stop processes when TUI exits (backend first, then vLLM)
		defer func() {
			if proc != nil {
				proc.Stop()
			}
			if vllmProc != nil {
				vllmProc.Stop()
			}
		}()

		// Start SSH server if requested.
		if sshPort > 0 {
			go func() {
				if err := sshsrv.ListenAndServe(sshPort, serverURL, Version); err != nil {
					log.Printf("SSH server error: %v", err)
				}
			}()
		}

		a := app.NewApp(serverURL, false, Version)

		p := tea.NewProgram(a, tea.WithAltScreen())
		a.SetProgram(p)

		// Re-wrap since SetProgram mutates the pointer receiver
		if _, err := p.Run(); err != nil {
			return fmt.Errorf("TUI error: %w", err)
		}
		return nil
	},
}

// isBackendRunning does a quick check to see if the backend is already up.
func isBackendRunning(url string) bool {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(url + "/health")
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode < 400
}

func init() {
	rootCmd.Flags().StringVar(&serverURL, "server", "http://localhost:8000", "Emotion Engine backend URL")
	rootCmd.Flags().IntVar(&sshPort, "ssh-port", 0, "SSH server port (0 = disabled)")
	rootCmd.Flags().BoolVar(&noBackend, "no-backend", false, "Do not auto-start the backend server")
	rootCmd.Flags().BoolVar(&noVLLM, "no-vllm", false, "Do not auto-start the vLLM server")
	rootCmd.Flags().StringVar(&vllmURL, "vllm-url", "http://localhost:8010", "vLLM server URL for health check")
	rootCmd.Flags().StringVar(&vllmModel, "vllm-model", "Qwen/Qwen3.5-4B", "Model for vLLM to serve")
	rootCmd.Flags().IntVar(&vllmPort, "vllm-port", 8010, "Port for vLLM server")
	rootCmd.Flags().StringVar(&backendDir, "backend-dir", "", "Backend directory (auto-detected if empty)")
	rootCmd.Flags().StringVar(&pythonPath, "python", "", "Python interpreter path (auto-detected if empty)")
}

// Execute runs the root command.
func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
