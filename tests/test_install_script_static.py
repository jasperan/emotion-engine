from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"
COMPOSE = ROOT / "docker-compose.yml"


def run_bash(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_install_script_has_valid_bash_syntax() -> None:
    run_bash("-n", str(INSTALL))


def test_install_help_documents_preflight_and_install_location() -> None:
    result = run_bash(str(INSTALL), "--help")

    assert "--check" in result.stdout
    assert "PROJECT_DIR" in result.stdout
    assert "bash -s -- --check" in result.stdout


def test_install_script_contains_actionable_preflight_checks() -> None:
    text = INSTALL.read_text()

    for expected in [
        "Docker daemon is not running",
        "Required ports are occupied",
        "OLLAMA_BASE_URL",
        "OLLAMA_DEFAULT_MODEL",
        "ollama pull $ollama_model",
        "Backend health check failed",
        "cd $INSTALL_DIR/tui && make build",
    ]:
        assert expected in text


def test_compose_backend_healthcheck_uses_image_available_python() -> None:
    text = COMPOSE.read_text()

    assert 'version: "3.8"' not in text
    assert "urllib.request.urlopen('http://localhost:8000/health'" in text
    assert '"curl", "-f", "http://localhost:8000/health"' not in text


def test_compose_allows_llm_runtime_overrides() -> None:
    text = COMPOSE.read_text()

    assert "OLLAMA_BASE_URL=${DOCKER_OLLAMA_BASE_URL:-http://host.docker.internal:11434/v1}" in text
    assert "OLLAMA_DEFAULT_MODEL=${DOCKER_OLLAMA_DEFAULT_MODEL:-qwen3.5:4b}" in text
    assert "OLLAMA_FALLBACK_MODEL=${DOCKER_OLLAMA_FALLBACK_MODEL:-qwen3.5:4b}" in text
    assert "VLLM_BASE_URL=${DOCKER_VLLM_BASE_URL:-http://host.docker.internal:8010}" in text
    assert "VLLM_DEFAULT_MODEL=${DOCKER_VLLM_DEFAULT_MODEL:-Qwen/Qwen3.5-4B}" in text
    assert "LLM_BACKEND=${DOCKER_LLM_BACKEND:-ollama}" in text


def test_install_script_allows_ports_owned_by_existing_stack() -> None:
    text = INSTALL.read_text()

    assert "compose_service_owns_port" in text
    assert "Port $port already used by this Emotion Engine stack" in text
    assert "1522:1521:oracle-db:Oracle DB" in text


def test_install_preflight_uses_docker_llm_override_names() -> None:
    text = INSTALL.read_text()

    assert 'local ollama_model="${DOCKER_OLLAMA_DEFAULT_MODEL:-qwen3.5:4b}"' in text
    assert 'local ollama_url="${DOCKER_OLLAMA_BASE_URL:-http://host.docker.internal:11434/v1}"' in text
    assert 'local vllm_url="${DOCKER_VLLM_BASE_URL:-http://host.docker.internal:8010}"' in text
    assert "set DOCKER_OLLAMA_BASE_URL" in text
    assert "set DOCKER_VLLM_BASE_URL" in text
