package backend

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

// Process manages a background process (backend or vLLM).
type Process struct {
	cmd     *exec.Cmd
	logFile *os.File
}

// FindBackendDir looks for the backend directory relative to the executable.
func FindBackendDir() string {
	exe, err := os.Executable()
	if err != nil {
		return ""
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		return ""
	}
	// Binary is at tui/emotionsim-tui; the emotionsim package lives at ../emotionsim/
	dir := filepath.Join(filepath.Dir(exe), "..")
	dir, _ = filepath.Abs(dir)
	if _, err := os.Stat(filepath.Join(dir, "emotionsim", "main.py")); err == nil {
		return dir
	}
	return ""
}

// FindPython finds the best Python interpreter for the backend.
func FindPython() string {
	home, _ := os.UserHomeDir()
	// Try conda env "emotion" first (has emotionsim package installed)
	condaPython := filepath.Join(home, "miniconda3", "envs", "emotion", "bin", "python3")
	if _, err := os.Stat(condaPython); err == nil {
		return condaPython
	}
	// Fall back to system python
	if p, err := exec.LookPath("python3"); err == nil {
		return p
	}
	return "python3"
}

// Start launches the backend process in the background.
func Start(backendDir, pythonPath string) (*Process, error) {
	if backendDir == "" {
		return nil, fmt.Errorf("backend directory not found")
	}
	if pythonPath == "" {
		pythonPath = FindPython()
	}

	logFile, err := os.CreateTemp("", "emotion-engine-backend-*.log")
	if err != nil {
		return nil, fmt.Errorf("creating log file: %w", err)
	}

	cmd := exec.Command(pythonPath, "-m", "emotionsim.main")
	cmd.Dir = backendDir
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.Env = append(os.Environ(), "PYTHONUNBUFFERED=1")

	if err := cmd.Start(); err != nil {
		logFile.Close()
		return nil, fmt.Errorf("starting backend: %w", err)
	}

	return &Process{
		cmd:     cmd,
		logFile: logFile,
	}, nil
}

// Stop gracefully shuts down the backend process.
func (p *Process) Stop() {
	if p == nil || p.cmd == nil || p.cmd.Process == nil {
		return
	}
	// Try graceful shutdown first
	p.cmd.Process.Signal(os.Interrupt)
	done := make(chan error, 1)
	go func() { done <- p.cmd.Wait() }()
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		p.cmd.Process.Kill()
	}
	if p.logFile != nil {
		name := p.logFile.Name()
		p.logFile.Close()
		os.Remove(name)
	}
}

// LogPath returns the path to the backend log file.
func (p *Process) LogPath() string {
	if p == nil || p.logFile == nil {
		return ""
	}
	return p.logFile.Name()
}

// --- vLLM management ---

// FindVLLM locates the vllm binary, checking conda base and PATH.
func FindVLLM() string {
	home, _ := os.UserHomeDir()
	// Check conda base (where vllm is typically installed)
	condaVLLM := filepath.Join(home, "miniconda3", "bin", "vllm")
	if _, err := os.Stat(condaVLLM); err == nil {
		return condaVLLM
	}
	// Check conda emotion env
	condaEnvVLLM := filepath.Join(home, "miniconda3", "envs", "emotion", "bin", "vllm")
	if _, err := os.Stat(condaEnvVLLM); err == nil {
		return condaEnvVLLM
	}
	// Fall back to PATH
	if p, err := exec.LookPath("vllm"); err == nil {
		return p
	}
	return ""
}

// IsVLLMRunning checks if a vLLM server is responding on the given URL.
func IsVLLMRunning(baseURL string) bool {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(baseURL + "/health")
	if err != nil {
		return false
	}
	resp.Body.Close()
	return resp.StatusCode < 400
}

// StartVLLM launches vLLM serve in the background with the given model and port.
func StartVLLM(vllmBin, model string, port int) (*Process, error) {
	if vllmBin == "" {
		return nil, fmt.Errorf("vllm binary not found")
	}

	logFile, err := os.CreateTemp("", "emotion-engine-vllm-*.log")
	if err != nil {
		return nil, fmt.Errorf("creating vllm log file: %w", err)
	}

	cmd := exec.Command(vllmBin, "serve", model,
		"--port", fmt.Sprintf("%d", port),
		"--max-model-len", "4096",
		"--gpu-memory-utilization", "0.85",
	)
	cmd.Stdout = logFile
	cmd.Stderr = logFile
	cmd.Env = append(os.Environ(), "PYTHONUNBUFFERED=1")

	if err := cmd.Start(); err != nil {
		logFile.Close()
		return nil, fmt.Errorf("starting vllm: %w", err)
	}

	return &Process{
		cmd:     cmd,
		logFile: logFile,
	}, nil
}
