# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EmotionSim: Multi-agent simulation engine analyzing emergent cooperative behaviors in AI agent swarms. Simulates disaster scenarios (e.g., "The Great Flood") with diverse personas where LLM-driven agents interact, make decisions, and cooperate based on personality traits and emotional states.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy, Ollama), SvelteKit 2.0 + Vite (frontend)

## Development Commands

```bash
# Installation
cd backend
pip install -e .

# CLI Mode (Recommended for Testing)
emotionsim run --scenario "Rising Flood" --max-steps 50 --seed 42
emotionsim run --scenario "Rising Flood" --simple         # Simple logs
emotionsim auto --count 5                                 # Batch testing
emotionsim scenarios --create-builtin                     # Create scenarios
emotionsim interactive                                    # Wizard mode
emotionsim status                                         # Backend health

# Full Web Stack
cd frontend
npm run dev                   # Both backend + frontend (concurrently)
npm run dev:frontend         # Frontend only
npm run build                # Production build
npm run check                # TypeScript/Svelte validation

# Backend Only
cd backend
python3 -m app.main          # Direct server start (:8000)

# Testing
pytest tests/
pytest --cov                 # With coverage
```

## Architecture

### System Flow

```
SvelteKit Dashboard (scenarios, run monitoring, chat logs)
    ↓ WebSocket / REST API
FastAPI Backend (:8000)
    ├─ API Routes: /api/scenarios, /api/runs, /api/websocket, /api/seed
    ↓
SimulationEngine (Orchestrator)
    ├─ Agent lifecycle & tick loop
    ├─ Conversation management
    ├─ Cooperation tracking
    └─ State persistence
    ↓
Agent Types
    ├─ HumanAgent (LLM-based with personas, Big Five traits)
    ├─ EnvironmentAgent (world events/state)
    ├─ DesignerAgent (scenario guidance)
    └─ EvaluationAgent (post-run analysis)
    ↓
Supporting Systems
    ├─ MessageBus (async routing)
    ├─ ConversationManager (multi-turn dialogues)
    ├─ CooperationCoordinator (task/goal tracking)
    └─ AgentMemory (episodic + relationships)
    ↓
LLM Router (Ollama local or Claude/GPT-4)
    ↓
Database (SQLite/SQLAlchemy: Runs, Agents, Steps, Messages, Scenarios)
```

### Key Components

**SimulationEngine** (`backend/app/simulation/engine.py`)
- Orchestrates agent lifecycle and tick loop
- Two processing phases:
  - Phase 1: Environment agents (generate events)
  - Phase 2: Human agents (shuffled order for fairness)
- Detects consensus, auto-stops simulation
- Evaluates runs on completion
- Max safety cap: 1000 steps

**Agent Hierarchy** (`backend/app/agents/`)
- **BaseAgent**: Abstract base with LLM, memory, tick logic
- **HumanAgent**: Role-plays with Big Five traits, stress/health, inventory
- **EnvironmentAgent**: Manages hazards, locations, items, world events
- **DesignerAgent**: Guides scenario narrative
- **EvaluationAgent**: Analyzes behavior post-run

**MessageBus** (`backend/app/simulation/message_bus.py`)
- Routes messages: direct, room-scoped, broadcast, conversation
- Tracks history for persistence/replay
- Manages room subscriptions by location

**ConversationManager** (`backend/app/simulation/conversation.py`)
- Multi-turn dialogues between agents
- Turn-taking, conversation state
- Tracks participants, prevents loops

**CooperationCoordinator** (`backend/app/agents/coordinator.py`)
- Tracks shared goals and task assignments
- Detects and breaks behavioral loops
- Provides suggestions when agents stuck

**LLM Router** (`backend/app/llm/router.py`)
- Abstraction for providers (Ollama primary, Claude planned)
- Singleton pattern for client reuse
- Configurable model selection

**Database Models** (`backend/app/models/`)
- **Run**: Simulation state, status, metrics
- **Scenario**: Templates with agent configs
- **Agent**: Instances with persona + dynamic state
- **Step**: Per-step world state snapshots
- **Message**: Timestamped log with routing metadata
- **Conversation**: Multi-turn dialogue records

## Important Patterns

### Discrete Event Simulation (DES)
- Each tick executes all agents sequentially
- World state updates atomically per step
- Deterministic, reproducible (seedable)
- Max 1000 steps to prevent infinite loops

### Agent Ticking Pipeline
```
Agent.tick() →
  Build system prompt (role, persona, goals) →
  Build context (world state + recent messages) →
  Call LLM with JSON-mode request →
  Parse response (actions + optional message) →
  Apply state changes →
  Store in memory & database
```

### Persona-Driven Decision Making
- Big Five personality traits (openness, conscientiousness, etc.)
- `should_respond()` uses personality probabilities
- Stress levels and health affect behavior
- Relationships tracked in episodic memory

### Resilient Movement System
- Multi-step travel with progress tracking
- Path-finding for non-adjacent locations
- Fails gracefully (no retry loops)
- Dynamic location creation

### Conversation Flow Control
- Explicit initiation between agents
- Turn-taking with safety limits (10 rounds max)
- Participants tracked; messages to relevant agents only
- Automatic cleanup of ended conversations

### State Persistence & Resumption
- Engine can be paused/resumed
- World state + dynamic state saved per step
- `load_from_db()` restores full context
- Auto-resumption on backend restart

### Async-First Architecture
- All DB operations use async/await
- LLM calls are non-blocking
- FastAPI handlers use async context managers
- Enables concurrent API + background simulation

## Code Organization

**Models/Schemas Separation:**
- `app/models/`: SQLAlchemy ORM (database schema)
- `app/schemas/`: Pydantic validation (API contracts)

**JSON Response Parsing:**
- LLM outputs expected in JSON
- Fallback to natural language if parsing fails
- Defensive parsing for malformed responses

**Dynamic vs. Static State:**
- `persona`: Immutable traits (age, occupation, skills)
- `dynamic_state`: Mutable (health, stress, location, inventory)

**Event-Driven Architecture:**
- `on_event()` callbacks emit to WebSocket clients
- Events: `run_started`, `step_completed`, `message`, `agent_error`, `movement_failed`

**Configuration:**
- Environment variables via `pydantic_settings`
- `.env` file support
- CLI-based model selection
- Defaults: Ollama localhost, SQLite in-memory

## API Endpoints

- `POST /api/scenarios` - Create scenario
- `GET /api/scenarios` - List scenarios
- `POST /api/runs` - Start simulation
- `GET /api/runs/{id}` - Get run status
- `POST /api/runs/{id}/stop` - Stop simulation
- `WS /api/websocket` - Real-time updates
- `POST /api/seed` - Seed database

## Testing

- Pytest with async support (`pytest-asyncio`)
- Coverage tracking
- MyPy type checking enabled

## Key Files

- `backend/app/simulation/engine.py` - Main orchestrator
- `backend/app/agents/base.py` - Agent base class
- `backend/app/agents/human_agent.py` - Persona-driven agents
- `backend/app/simulation/message_bus.py` - Message routing
- `backend/app/simulation/conversation.py` - Multi-turn dialogues
- `backend/app/agents/coordinator.py` - Cooperation tracking
- `backend/app/llm/router.py` - LLM abstraction
- `backend/app/models/` - Database models
- `backend/app/cli/main.py` - CLI commands
- `frontend/src/routes/` - SvelteKit pages
