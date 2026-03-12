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
#
# Override install location:
#   PROJECT_DIR=/opt/myapp curl -fsSL ... | bash
# ============================================================

REPO_URL="https://github.com/jasperan/emotion-engine.git"
PROJECT="emotion-engine"
BRANCH="main"
INSTALL_DIR="${PROJECT_DIR:-$(pwd)/$PROJECT}"

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

compose_cmd() {
    if docker compose version &>/dev/null; then
        docker compose "$@"
    elif command_exists docker-compose; then
        docker-compose "$@"
    else
        fail "Docker Compose not found"
    fi
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

    command_exists git || fail "Git is required: https://git-scm.com/"
    success "Git $(git --version | cut -d' ' -f3)"

    command_exists docker || fail "Docker is required: https://docs.docker.com/get-docker/"
    success "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

    if docker compose version &>/dev/null; then
        success "Docker Compose (plugin)"
    elif command_exists docker-compose; then
        success "Docker Compose (standalone)"
    else
        fail "Docker Compose is required"
    fi

    # Check Docker daemon is running
    docker info &>/dev/null || fail "Docker daemon is not running. Start Docker first."
    success "Docker daemon running"
    echo ""
}

# ── Step 2: Clone / Update Repo ─────────────────────────────
clone_repo() {
    if [ -d "$INSTALL_DIR" ]; then
        warn "Directory $INSTALL_DIR already exists"
        info "Pulling latest changes..."
        (cd "$INSTALL_DIR" && git pull origin "$BRANCH" 2>/dev/null) || true
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
    local be_wait=0
    local be_max=120
    while [ $be_wait -lt $be_max ]; do
        if curl -sf http://localhost:8000/health &>/dev/null; then
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
        echo ""
    fi
}

# ── Step 5: Verify ──────────────────────────────────────────
verify_install() {
    info "Verifying installation..."

    # Check scenarios were seeded
    local scenario_count
    scenario_count=$(curl -sf http://localhost:8000/api/scenarios 2>/dev/null \
        | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null \
        || echo "0")

    if [ "$scenario_count" -gt 0 ] 2>/dev/null; then
        success "$scenario_count scenarios loaded and ready"
    else
        warn "Could not verify scenarios. The backend may still be initializing."
        warn "Run: curl http://localhost:8000/api/scenarios | python3 -m json.tool"
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
    echo -e "  ${BOLD}Dashboard:${NC}  ${CYAN}http://localhost:3000${NC}"
    echo -e "  ${BOLD}API:${NC}        ${CYAN}http://localhost:8000${NC}"
    echo -e "  ${BOLD}Oracle DB:${NC}  localhost:1522 (emotionsim/emotionsim)"
    echo ""
    echo -e "  ${BOLD}Services:${NC}   docker compose ps"
    echo -e "  ${BOLD}Logs:${NC}       docker compose logs -f"
    echo -e "  ${BOLD}Stop:${NC}       docker compose down"
    echo ""
    echo -e "  ${DIM}LLM note: Install Ollama (https://ollama.com) on the host${NC}"
    echo -e "  ${DIM}and pull a model: ollama pull qwen3.5:4b${NC}"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────
main() {
    print_banner
    check_prereqs
    clone_repo
    pull_oracle_image
    start_services
    verify_install
    print_done
}

main "$@"
