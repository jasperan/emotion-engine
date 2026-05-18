#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# emotion-engine -- One-Command Installer
# EmotionSim - Multi-Agent Simulation System
#
# Pulls Oracle DB 26ai Free, creates tables, seeds 9 built-in
# scenarios, and starts the full stack. Zero manual steps.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/jasperan/emotion-engine/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/jasperan/emotion-engine/main/install.sh | bash -s -- --check
#
# Override install location:
#   curl -fsSL ... | env PROJECT_DIR=/opt/myapp bash
# ============================================================

REPO_URL="https://github.com/jasperan/emotion-engine.git"
PROJECT="emotion-engine"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${PROJECT_DIR:-$(pwd)/$PROJECT}"
CHECK_ONLY=false

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()    { echo -e "${BLUE}>>>${NC} $1"; }
success() { echo -e "${GREEN} +${NC} $1"; }
warn()    { echo -e "${YELLOW} !${NC} $1"; }
fail()    { echo -e "${RED} x $1${NC}"; exit 1; }
command_exists() { command -v "$1" &>/dev/null; }

print_usage() {
    cat <<EOF
Emotion Engine installer

Usage:
  install.sh [options]

Options:
  --check       Run preflight checks only; do not clone, pull, or start services.
  -h, --help   Show this help.

Environment:
  PROJECT_DIR  Install directory. Default: ./emotion-engine
  BRANCH       Git branch to clone or pull. Default: main

Examples:
  curl -fsSL https://raw.githubusercontent.com/jasperan/emotion-engine/main/install.sh | bash
  curl -fsSL https://raw.githubusercontent.com/jasperan/emotion-engine/main/install.sh | bash -s -- --check
  curl -fsSL https://raw.githubusercontent.com/jasperan/emotion-engine/main/install.sh | env PROJECT_DIR=/opt/emotion-engine bash
EOF
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --check)
                CHECK_ONLY=true
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                fail "Unknown option: $1. Run with --help for usage."
                ;;
        esac
        shift
    done
}

compose_cmd() {
    if docker compose version &>/dev/null; then
        docker compose "$@"
    elif command_exists docker-compose; then
        docker-compose "$@"
    else
        fail "Docker Compose not found"
    fi
}

port_in_use() {
    local port="$1"
    if command_exists lsof; then
        lsof -nP -iTCP:"$port" -sTCP:LISTEN &>/dev/null
    elif command_exists ss; then
        ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
    elif command_exists netstat; then
        netstat -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${port}$"
    else
        return 2
    fi
}

compose_service_owns_port() {
    local service="$1"
    local container_port="$2"
    local host_port="$3"
    local mapped

    [ -f "$INSTALL_DIR/docker-compose.yml" ] || return 1

    mapped=$(cd "$INSTALL_DIR" && compose_cmd port "$service" "$container_port" 2>/dev/null || true)
    [ -n "$mapped" ] && grep -Eq "[:.]${host_port}$" <<<"$mapped"
}

compose_env_value() {
    local key="$1"
    local env_file="$INSTALL_DIR/.env"
    local value

    [ -f "$env_file" ] || return 1
    value=$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$env_file" | tail -n 1 | cut -d= -f2- || true)
    [ -n "$value" ] || return 1
    value="${value%%#*}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    echo "$value"
}

compose_bind_addr() {
    local env_bind_addr
    if [ -n "${COMPOSE_BIND_ADDR:-}" ]; then
        echo "$COMPOSE_BIND_ADDR"
        return
    fi
    env_bind_addr="$(compose_env_value COMPOSE_BIND_ADDR || true)"
    echo "${env_bind_addr:-127.0.0.1}"
}

compose_probe_host() {
    local bind_addr
    bind_addr="$(compose_bind_addr)"
    case "$bind_addr" in
        ""|127.0.0.1|0.0.0.0)
            echo "localhost"
            ;;
        *)
            echo "$bind_addr"
            ;;
    esac
}

compose_url() {
    local port="$1"
    local path="${2:-}"
    echo "http://$(compose_probe_host):${port}${path}"
}

compose_db_user() {
    local env_db_user
    if [ -n "${ORACLE_DB_USER:-}" ]; then
        echo "$ORACLE_DB_USER"
        return
    fi
    env_db_user="$(compose_env_value ORACLE_DB_USER || true)"
    echo "${env_db_user:-emotionsim}"
}

validate_compose_bind_addr() {
    local bind_addr
    bind_addr="$(compose_bind_addr)"
    case "$bind_addr" in
        127.0.0.1|0.0.0.0)
            ;;
        *)
            fail "COMPOSE_BIND_ADDR must be 127.0.0.1 for local-only installs or 0.0.0.0 to expose services on all interfaces."
            ;;
    esac
}

print_banner() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  EmotionSim${NC} -- Multi-Agent Simulation Engine"
    echo -e "  ${DIM}Disaster scenarios with LLM-driven agent swarms${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# ── Step 1: Prerequisites ───────────────────────────────────
check_prereqs() {
    info "Checking prerequisites..."

    command_exists git || fail "Git is required. Install it from https://git-scm.com/ and rerun this installer."
    success "Git $(git --version | cut -d' ' -f3)"

    command_exists curl || fail "curl is required for backend health checks. Install curl and rerun this installer."
    success "curl available"

    command_exists docker || fail "Docker is required. Install Docker Desktop or Docker Engine: https://docs.docker.com/get-docker/"
    success "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

    if docker compose version &>/dev/null; then
        success "Docker Compose (plugin)"
    elif command_exists docker-compose; then
        success "Docker Compose (standalone)"
    else
        fail "Docker Compose is required. Install the Docker Compose plugin or docker-compose standalone."
    fi

    # Check Docker daemon is running
    docker info &>/dev/null || fail "Docker daemon is not running. Start Docker, then rerun this installer."
    success "Docker daemon running"
    echo ""
}

check_ports() {
    info "Checking required ports..."

    local conflicts=0
    local ports=("1522:1521:oracle-db:Oracle DB" "8000:8000:backend:FastAPI backend" "3000:3000:frontend:Web dashboard")
    local item port container_port service label

    for item in "${ports[@]}"; do
        IFS=: read -r port container_port service label <<<"$item"
        if port_in_use "$port"; then
            if compose_service_owns_port "$service" "$container_port" "$port"; then
                success "Port $port already used by this Emotion Engine stack ($label)"
            else
                warn "Port $port is already in use ($label)."
                warn "Stop the conflicting service or edit docker-compose.yml before installing."
                conflicts=1
            fi
        else
            local status=$?
            if [ "$status" -eq 2 ]; then
                warn "Could not check port $port; install lsof, ss, or netstat for port diagnostics."
            else
                success "Port $port available ($label)"
            fi
        fi
    done

    if [ "$conflicts" -eq 1 ]; then
        fail "Required ports are occupied. Free ports 1522, 8000, and 3000, then rerun."
    fi
    echo ""
}

check_llm_setup() {
    info "Checking local LLM services..."

    local ollama_model="${DOCKER_OLLAMA_DEFAULT_MODEL:-qwen3.5:4b}"
    local ollama_url="${DOCKER_OLLAMA_BASE_URL:-http://host.docker.internal:11434/v1}"
    local vllm_url="${DOCKER_VLLM_BASE_URL:-http://host.docker.internal:8010}"
    ollama_url="${ollama_url%/}"
    ollama_url="${ollama_url%/v1}"
    vllm_url="${vllm_url%/}"

    # host.docker.internal is valid inside Docker; probe localhost from the host installer.
    local ollama_probe_url="${ollama_url/host.docker.internal/localhost}"
    local ollama_tags

    if ollama_tags="$(curl -sf "$ollama_probe_url/api/tags" 2>/dev/null)"; then
        success "Ollama is reachable at $ollama_probe_url"
        if [[ "$ollama_tags" == *"\"name\":\"$ollama_model\""* || "$ollama_tags" == *"\"model\":\"$ollama_model\""* ]]; then
            success "Ollama model '$ollama_model' is available"
        else
            warn "Ollama is running, but model '$ollama_model' was not found."
            warn "Pull it with: ollama pull $ollama_model"
            warn "Or rerun with DOCKER_OLLAMA_DEFAULT_MODEL set to an installed model."
        fi
    else
        warn "Ollama is not reachable at $ollama_probe_url."
        warn "Simulations need a model. Recommended host setup:"
        warn "  ollama serve"
        warn "  ollama pull $ollama_model"
        warn "If Ollama uses a non-default port, set DOCKER_OLLAMA_BASE_URL before installing."
    fi

    local vllm_probe_url="${vllm_url/host.docker.internal/localhost}"
    if curl -sf "$vllm_probe_url/health" &>/dev/null; then
        success "vLLM is reachable at $vllm_probe_url"
    else
        warn "vLLM is not reachable at $vllm_probe_url; Docker will use Ollama by default."
        warn "If vLLM uses a non-default host port, set DOCKER_VLLM_BASE_URL before installing."
    fi
    echo ""
}

run_preflight() {
    validate_compose_bind_addr
    check_prereqs
    check_ports
    check_llm_setup
}

# ── Step 2: Clone / Update Repo ─────────────────────────────
clone_repo() {
    if [ -d "$INSTALL_DIR" ]; then
        warn "Directory $INSTALL_DIR already exists"
        info "Pulling latest changes..."
        (cd "$INSTALL_DIR" && git pull origin "$BRANCH") \
            || fail "Could not update $INSTALL_DIR. Check that it is a git checkout and that branch '$BRANCH' exists."
    else
        info "Cloning repository..."
        git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR" \
            || fail "Clone failed. Check your internet connection."
    fi
    success "Repository ready at $INSTALL_DIR"
    echo ""
}

# ── Step 3: Pull Oracle DB 26ai Free ────────────────────────
pull_oracle_image() {
    info "Pulling Oracle DB 26ai Free image (this may take a few minutes on first run)..."
    docker pull gvenzl/oracle-free:latest-faststart 2>&1 | tail -1
    success "Oracle DB 26ai Free image ready"
    echo ""
}

# ── Step 4: Start Services ──────────────────────────────────
start_services() {
    cd "$INSTALL_DIR"
    info "Starting Oracle DB 26ai Free..."

    # Start just Oracle first so it can initialize
    compose_cmd up -d oracle-db

    # Wait for Oracle to become healthy
    info "Waiting for Oracle DB to initialize (first run takes ~60-90s)..."
    local max_wait=300
    local elapsed=0
    local interval=5

    while [ $elapsed -lt $max_wait ]; do
        # Check container health status
        local health
        health=$(docker inspect --format='{{.State.Health.Status}}' \
            "$(compose_cmd ps -q oracle-db 2>/dev/null)" 2>/dev/null || echo "starting")

        if [ "$health" = "healthy" ]; then
            success "Oracle DB 26ai Free is healthy"
            echo ""
            break
        fi

        # Show progress
        printf "\r  ${DIM}[%3ds] Oracle DB status: %s${NC}   " "$elapsed" "$health"
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    if [ $elapsed -ge $max_wait ]; then
        echo ""
        fail "Oracle DB did not become healthy within ${max_wait}s. Check: docker compose logs oracle-db"
    fi

    # Now start backend + frontend (backend creates tables and seeds scenarios on startup)
    info "Starting backend and frontend..."
    compose_cmd up -d --build backend frontend
    echo ""

    # Wait for backend health
    info "Waiting for backend to start..."
    local backend_health_url
    backend_health_url="$(compose_url 8000 /health)"
    local be_wait=0
    local be_max=120
    while [ $be_wait -lt $be_max ]; do
        if curl -sf "$backend_health_url" &>/dev/null; then
            success "Backend is healthy"
            echo ""
            break
        fi
        printf "\r  ${DIM}[%3ds] Backend starting...${NC}   " "$be_wait"
        sleep 3
        be_wait=$((be_wait + 3))
    done

    if [ $be_wait -ge $be_max ]; then
        echo ""
        warn "Backend not responding yet. It may still be starting."
        warn "Check logs: cd $INSTALL_DIR && docker compose logs -f backend"
        warn "Common causes: Oracle is still warming up, port 8000 is occupied, or the backend image failed to build."
        echo ""
    fi
}

# ── Step 5: Verify ──────────────────────────────────────────
verify_install() {
    info "Verifying installation..."

    local backend_health_url
    local scenarios_url
    backend_health_url="$(compose_url 8000 /health)"
    scenarios_url="$(compose_url 8000 /api/scenarios)"

    if ! curl -sf "$backend_health_url" &>/dev/null; then
        warn "Backend health check failed: $backend_health_url"
        warn "Run: cd $INSTALL_DIR && docker compose logs -f backend"
        echo ""
        fail "Backend did not pass health verification."
    fi

    # Check scenarios were seeded
    local scenario_count
    if command_exists python3; then
        scenario_count=$(curl -sf "$scenarios_url" 2>/dev/null \
            | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null \
            || echo "0")
    else
        warn "python3 not found; skipping scenario count verification."
        warn "Manual check: curl $scenarios_url"
        echo ""
        return
    fi

    if [ "$scenario_count" -gt 0 ] 2>/dev/null; then
        success "$scenario_count scenarios loaded and ready"
    else
        warn "Could not verify scenarios. The backend may still be initializing."
        warn "Run: curl $scenarios_url | python3 -m json.tool"
    fi
    echo ""
}

# ── Done ─────────────────────────────────────────────────────
print_done() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${BOLD}Installation complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${BOLD}Location:${NC}   $INSTALL_DIR"
    echo -e "  ${BOLD}Dashboard:${NC}  ${CYAN}$(compose_url 3000)${NC}"
    echo -e "  ${BOLD}API:${NC}        ${CYAN}$(compose_url 8000)${NC}"
    echo -e "  ${BOLD}Oracle DB:${NC}  $(compose_probe_host):1522 ($(compose_db_user)/configured password)"
    echo ""
    echo -e "  ${BOLD}Services:${NC}   docker compose ps"
    echo -e "  ${BOLD}Logs:${NC}       docker compose logs -f"
    echo -e "  ${BOLD}Stop:${NC}       docker compose down"
    echo ""
    echo -e "  ${BOLD}TUI:${NC}        cd $INSTALL_DIR/tui && make build"
    echo -e "              ./emotionsim-tui --no-backend --no-vllm"
    echo ""
    echo -e "  ${DIM}LLM note: Install Ollama (https://ollama.com) on the host${NC}"
    echo -e "  ${DIM}and pull a model: ollama pull \${DOCKER_OLLAMA_DEFAULT_MODEL:-qwen3.5:4b}${NC}"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────
main() {
    parse_args "$@"
    print_banner
    run_preflight
    if [ "$CHECK_ONLY" = true ]; then
        success "Preflight checks complete. No services were started."
        return
    fi
    clone_repo
    pull_oracle_image
    start_services
    verify_install
    print_done
}

main "$@"
