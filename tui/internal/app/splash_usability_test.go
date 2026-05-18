package app

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
	"github.com/jasperan/emotion-engine/tui/internal/api"
)

func TestSplashConnectionFailureShowsActionableGuidance(t *testing.T) {
	m := NewSplashModel(api.NewClient("http://localhost:9999"), "test")
	m.errMsg = "GET /health: connection refused"
	m.retryCount = m.maxRetries

	out := m.View(80, 24)
	for _, expected := range []string{
		"Backend health",
		"docker compose",
		"ollama pull",
		"vLLM",
	} {
		if !strings.Contains(out, expected) {
			t.Fatalf("expected %q in splash guidance, got %q", expected, out)
		}
	}
}

func TestSplashCompactViewFits80Columns(t *testing.T) {
	m := NewSplashModel(api.NewClient("http://localhost:9999"), "test")
	m.errMsg = "GET /health: connection refused"
	m.retryCount = m.maxRetries

	out := m.View(80, 24)
	for _, line := range strings.Split(out, "\n") {
		if got := lipgloss.Width(line); got > 80 {
			t.Fatalf("line width %d exceeds 80 columns: %q", got, line)
		}
	}
}

func TestHelpLauncherDocumentsActualBackKeys(t *testing.T) {
	h := HelpModel{}
	found := false
	for _, binding := range h.bindingsForScreen(ScreenLauncher) {
		if binding.key == "q/Esc" && binding.desc == "Back" {
			found = true
		}
	}
	if !found {
		t.Fatal("launcher help should document q/Esc back behavior")
	}
}
