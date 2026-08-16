# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EmotionSim: Multi-agent simulation engine analyzing emergent cooperative behaviors in AI agent swarms. Simulates disaster scenarios (e.g., "The Great Flood") with diverse personas where LLM-driven agents interact, make decisions, and cooperate based on personality traits and emotional states.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy, Oracle DB 26ai Free, vLLM/Ollama), Go 1.24+ (Bubble Tea TUI), SvelteKit 2.0 + Vite (frontend)

**Branch: `mirofish-integration`** adds knowledge graph infrastructure (Oracle SQL/PGQ), document ingestion via NER/RE, graph-backed agent memory with hybrid search, post-sim analysis tools, opinion dynamics, and lightweight agents for 100+ scaling. The core MiroFish features are now wired into the live engine (see Gotchas for the runtime switches: `GRAPH_MEMORY_ENABLED`, hybrid populations, governance gates, goal trees).

## Development Commands

```bash
# Installation (repo root)
pip install -e .

# CLI Mode (Recommended for Testing)
emotionsim run --scenario "Rising Flood" --max-steps 50 --seed 42
emotionsim run --scenario "Rising Flood" --simple         # Simple logs
emotionsim auto --count 5                                 # Batch testing
emotionsim scenarios --create-builtin                     # Create scenarios
emotionsim interactive                                    # Wizard mode
emotionsim status                                         # Backend health
emotionsim eval --scenarios "Rising Flood,Space Station" --seeds 3   # Offline eval matrix (stub LLM)

# Go TUI Dashboard
cd tui
make build                                    # Build binary
./emotionsim-tui                              # Auto-starts backend + vLLM
./emotionsim-tui --no-backend --no-vllm       # Connect to existing services
./emotionsim-tui --ssh-port 2222              # Share read-only via SSH
go test ./...                                 # Run TUI tests

# Full Web Stack
cd frontend
npm run dev                   # Both backend + frontend (concurrently)
npm run dev:frontend         # Frontend only
npm run build                # Production build
npm run check                # TypeScript/Svelte validation

# Backend Only (from repo root)
python3 -m emotionsim.main   # Direct server start (:8000)

# Docker (full stack)
docker-compose up -d          # Oracle DB (:1522) + Backend (:8000) + Frontend (:3000)

# Testing (from repo root)
pytest tests/               # Python tests (~980 tests)
pytest tests/test_agents.py  # Single test file
pytest --cov                 # With coverage
cd tui && go test ./...                    # Go TUI tests

# Pre-commit
pre-commit install            # Set up hooks (trailing whitespace, secrets detection)
pre-commit run --all-files    # Run all checks
```

## Architecture

### System Flow

```
SvelteKit Dashboard (scenarios, run monitoring, chat logs)
    ↓ WebSocket / REST API
FastAPI Backend (:8000)
    ├─ API Routes: /api/scenarios, /api/runs, /api/websocket, /api/seed, /api/documents, /api/runs/{id}/agents/{id}/chat, /api/runs/{id}/report
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
    ├─ EvaluationAgent (post-run analysis)
    └─ LightweightAgent (rule-based, no LLM, for 100+ agent scaling)
    ↓
Knowledge Graph Layer (mirofish-integration branch)
    ├─ GraphStorage ABC (Oracle SQL/PGQ implementation)
    ├─ EmbeddingService (Ollama nomic-embed-text, 768d)
    ├─ NERExtractor (LLM-based entity/relationship extraction)
    ├─ DocumentIngestor (text → NER/RE → graph → scenario)
    ├─ PersonaGenerator (graph entity → Big Five + MBTI persona)
    ├─ ScenarioAssembler (graph entities → simulation-ready scenario)
    ├─ GraphMemory (hybrid search recall: 0.7 vector + 0.3 BM25)
    ├─ ReportAgent (InsightForge deep search + PanoramaSearch breadth)
    └─ GraphToolsService (post-sim analysis with agent interviews)
    ↓
Social Dynamics Layer (mirofish-integration branch)
    ├─ OpinionDynamics (opinion shifts via influence/trust/bias)
    ├─ SentimentTracker (per-step topic tracking, tipping point detection)
    ├─ InfluenceNetwork (who influenced whom, super-spreaders, anchors)
    └─ SocialDynamicsEngine (orchestrator for all social systems)
    ↓
Supporting Systems
    ├─ MessageBus (async routing)
    ├─ ConversationManager (multi-turn dialogues)
    ├─ CooperationCoordinator (task/goal tracking)
    ├─ AgentMemory (episodic + relationships; GraphMemory on mirofish branch)
    ├─ AgentSupervisor (fault isolation, timeout, backoff)
    ├─ SceneDirector (cinematic scene grouping)
    ├─ TrustNetwork (vouch/betray tracking)
    ├─ NegotiationManager (proposals, counter-proposals)
    ├─ WorldStateDiffTracker (step-over-step change detection)
    └─ CognitiveEngine (think → plan → act → reflect)
    ↓
LLM Router (vLLM primary, Ollama fallback)
    ├─ vLLM: Parallel inference via continuous batching (:8010)
    ├─ Ollama: Single-slot fallback with semaphore gating
    └─ Per-agent-type model routing
    ↓
Database (Oracle DB 26ai Free / SQLAlchemy: Runs, Agents, Steps, Messages, Scenarios, Graphs, Entities, Edges, Memories)
    ↓
Datalake (cross-run analytics, comparison queries)

Go TUI (Bubble Tea)
    ├─ 7 screens: Splash, Scenarios, Launcher, Dashboard, History, Replay, Analytics
    ├─ Components: AgentPane, SpatialMap, RelationshipWeb, NegotiationTheater, MindView
    ├─ Auto-starts backend + vLLM processes
    └─ SSH server for read-only sharing (charmbracelet/wish)
```

### Key Components

**SimulationEngine** (`emotionsim/simulation/engine.py`)
- Orchestrates agent lifecycle and tick loop
- Three processing phases:
  - Phase 1: Environment agents (generate events)
  - Phase 2: Human agents (scene-based parallel, or sequential)
  - Phase 3: Reaction round (intra-step responses)
- Parallel scene processing: independent locations run concurrently via asyncio.gather (vLLM)
- Agent conclusion enforcement: token budget + stagnation detection
- Detects consensus, auto-stops simulation
- Evaluates runs on completion
- Max safety cap: 1000 steps

**Agent Hierarchy** (`emotionsim/agents/`)
- **BaseAgent**: Abstract base with LLM, memory, tick logic
- **HumanAgent**: Role-plays with Big Five traits, stress/health, inventory
- **EnvironmentAgent**: Manages hazards, locations, items, world events
- **DesignerAgent**: Guides scenario narrative
- **EvaluationAgent**: Analyzes behavior post-run

**MessageBus** (`emotionsim/simulation/message_bus.py`)
- Routes messages: direct, room-scoped, broadcast, conversation
- Tracks history for persistence/replay
- Manages room subscriptions by location

**ConversationManager** (`emotionsim/simulation/conversation.py`)
- Multi-turn dialogues between agents
- Turn-taking, conversation state
- Tracks participants, prevents loops

**ACP (Agent Coordination Protocol)** (`emotionsim/acp/`)
- `registry.py` — tracks live agent identities, statuses, capabilities, roles
- `wave_controller.py` — wave-based task batching: groups tasks into dependency waves, runs each wave via `asyncio.gather`
- `coordination.py` — cross-agent coordination primitives
- `message.py` — ACP message/identity dataclasses

**CooperationCoordinator** (`emotionsim/agents/coordinator.py`)
- Tracks shared goals and task assignments
- Detects and breaks behavioral loops
- Provides suggestions when agents stuck

**LLM Router** (`emotionsim/llm/router.py`)
- Abstraction for providers (vLLM primary, Ollama fallback)
- Singleton pattern for client reuse
- Per-agent-type model routing (human/environment/reactive can use different models)
- Automatic fallback chain: vLLM → Ollama → fallback model

**Database Models** (`emotionsim/models/`)
- **Run**: Simulation state, status, metrics
- **Scenario**: Templates with agent configs
- **Agent**: Instances with persona + dynamic state
- **Step**: Per-step world state snapshots
- **Message**: Timestamped log with routing metadata
- **Conversation**: Multi-turn dialogue records
- **GraphModel**: Knowledge graph partition (mirofish branch)
- **EntityModel**: Graph entity nodes with embeddings (mirofish branch)
- **EdgeModel**: Graph relationship edges with embeddings (mirofish branch)
- **MemoryNodeModel**: Run-scoped agent memories with embeddings (mirofish branch)
- **MemoryEdgeModel**: Links between memories and entities (mirofish branch)

## Important Patterns

### Discrete Event Simulation (DES)
- Scene mode (default): agents grouped by location, scenes run in parallel (vLLM) or sequential (Ollama)
- Within scenes, turns are sequential so agents react to prior speech
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
- Opinion vectors per topic (-1.0 to 1.0), opinion_bias (resistance), reaction_speed, influence_level (mirofish branch)
- MBTI type generated alongside Big Five for richer personality modeling (mirofish branch)

### Graph-Backed Memory (mirofish branch)
- `GraphMemory` replaces flat sliding-window `AgentMemory` with semantic retrieval
- Hybrid search: 0.7 * cosine vector similarity + 0.3 * BM25 keyword matching
- Agents recall by *relevance*, not recency (e.g., bridge memory from 30 steps ago surfaces when at a bridge)
- Knowledge graph entities linked to agent memories via `MemoryEdgeModel`
- `build_context()` merges recalled memories + graph facts into LLM prompt

### Opinion Dynamics (mirofish branch)
- Agents have opinion vectors on topics (e.g., {"evacuation": 0.8, "cooperation": -0.2})
- When agents interact, opinions shift based on: influence level, trust, opinion bias (resistance), reaction speed
- Shift formula: `direction * base_rate * influence * trust * (1-bias) * speed * distance_factor`
- Clamped to max +-0.3 per interaction, stances clamped to [-1.0, 1.0]
- `SentimentTracker` detects tipping points (convergence/divergence) via sliding window over std_dev
- `InfluenceNetwork` tracks who influenced whom, identifies super-spreaders and opinion anchors

### Lightweight Agents (mirofish branch)
- `LightweightAgent`: personality-driven rule-based decisions, zero LLM calls
- Action weights computed from Big Five traits (extraversion->speak, agreeableness->help, openness->move, etc.)
- Dynamic promotion: background agents become foreground when addressed directly, in active scenes, or if high-leadership + low-stress
- Enables 100+ agent simulations without proportional LLM cost

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
- Events: `run_started`, `step_completed`, `message`, `agent_error`, `movement_failed`, `token_stream`, `token_done`, `scene_turn`, `scene_completed`, `proposal_created`, `proposal_accepted`, `proposal_rejected`, `vouch_for`, `plan_shared`, `conversation_outcome`

**Configuration:**
- Environment variables via `pydantic_settings`
- `.env` file support
- Defaults: vLLM (:8010, Qwen/Qwen3.5-4B), Oracle DB 26ai Free (localhost:1522/FREEPDB1)
- Key settings: `llm_backend`, `vllm_base_url`, `scene_mode`, `max_concurrent_llm_calls`, `agent_max_tokens_per_run`, `agent_max_stagnant_steps`

## API Endpoints

- `POST /api/scenarios` - Create scenario
- `GET /api/scenarios` - List scenarios
- `POST /api/runs` - Start simulation
- `GET /api/runs/{id}` - Get run status
- `POST /api/runs/{id}/stop` - Stop simulation
- `WS /api/websocket` - Real-time updates
- `POST /api/seed` - Seed database
- `POST /api/documents` - Upload document, extract entities via NER, generate scenario (mirofish branch)
- `POST /api/runs/{id}/agents/{id}/chat` - Chat with agent post-simulation (mirofish branch)
- `POST /api/runs/{id}/report` - Generate analysis report with InsightForge (mirofish branch)
- `GET /api/runs/{id}/steps` - Per-step snapshots (replay timeline)
- `GET /api/runs/{id}/metrics` - Run observability: tokens, latency, cost (Step 9)
- `GET /datalake/compare?run_ids=a,b` - Cross-run metric comparison (Step 9)

## Testing

- Pytest with async support (`pytest-asyncio`)
- Coverage tracking
- MyPy type checking enabled

## Key Files

- `emotionsim/simulation/engine.py` - Main orchestrator
- `emotionsim/agents/base.py` - Agent base class
- `emotionsim/agents/human.py` - Persona-driven agents (CognitiveEngine + IntentMemory)
- `emotionsim/simulation/message_bus.py` - Message routing
- `emotionsim/simulation/conversation.py` - Multi-turn dialogues
- `emotionsim/agents/coordinator.py` - Cooperation tracking
- `emotionsim/llm/router.py` - LLM abstraction
- `emotionsim/llm/vllm.py` - vLLM client (parallel inference)
- `emotionsim/llm/token_logger.py` - Per-agent JSONL token logging
- `emotionsim/simulation/agent_supervisor.py` - Fault isolation & backoff
- `emotionsim/simulation/scene_director.py` - Location-based scene grouping
- `emotionsim/models/` - Database models
- `emotionsim/cli.py` - CLI commands
- `emotionsim/acp/` - Agent Coordination Protocol (registry, wave controller, coordination primitives)
- `frontend/src/routes/` - SvelteKit pages
- `frontend/src/lib/components/TokenStream.svelte` - Real-time token visualizer
- `emotionsim/storage/` - Knowledge graph layer (mirofish branch)
  - `graph_storage.py` - GraphStorage ABC + Entity/Edge/SearchResult dataclasses
  - `oracle_graph_storage.py` - Oracle 26ai implementation with hybrid search
  - `embedding_service.py` - Ollama nomic-embed-text (768d) wrapper
  - `ner_extractor.py` - LLM-based NER/RE extraction
- `emotionsim/services/` - High-level services (mirofish branch)
  - `document_ingestor.py` - Text → NER → graph pipeline
  - `persona_generator.py` - Graph entity → Big Five + MBTI persona
  - `scenario_assembler.py` - Graph entities → ScenarioCreate
  - `report_agent.py` - Post-sim analysis with graph tools
  - `graph_tools.py` - InsightForge, PanoramaSearch
- `emotionsim/agents/graph_memory.py` - Relevance-based recall via hybrid search (runtime-wired via `GRAPH_MEMORY_ENABLED`)
- `emotionsim/agents/lightweight_agent.py` - Rule-based agent for 100+ scaling; hybrid populations wired into the engine (background agents + promotion/demotion)
- `emotionsim/simulation/opinion_dynamics.py` - Opinion shift engine (topic-aware: topics extracted from real message content)
- `emotionsim/simulation/sentiment_tracker.py` - Topic sentiment tracking + tipping points
- `emotionsim/simulation/influence_network.py` - Directed influence graph
- `emotionsim/simulation/social_dynamics.py` - Orchestrator for all social systems
- `emotionsim/simulation/governance.py` - Ethics gates on agent actions (wired into the V1 tick loop)
- `emotionsim/simulation/goal_tree.py` - Mission → group → individual goals (surfaced in agent prompts)
- `emotionsim/simulation/persistence.py` - RunPersistence service (Step/Run/Message writes extracted from the engine)
- `emotionsim/simulation/scene_processor.py` / `reaction_round.py` / `token_streamer.py` - Scene, reaction-round, and token-streaming services (extracted from the engine monolith)
- `emotionsim/llm/schemas.py` - Pydantic schemas + validation for act/think/plan/reflection/governance outputs
- `emotionsim/llm/stub.py` - Deterministic offline LLM client (eval harness)
- `emotionsim/eval/` - Offline eval harness: `emotionsim eval` CLI, metrics, determinism fingerprints

## Go TUI Architecture

The TUI (`tui/`) is a standalone Go binary that connects to the backend via WebSocket + REST.

**Screen flow:** Splash → Scenarios → Launcher → Dashboard (live sim) → History → Replay → Analytics

**Key patterns:**
- Each screen implements `tea.Model` with `Init()`, `Update()`, `View()`
- `internal/api/client.go` wraps all REST calls; `websocket.go` handles live events
- `internal/backend/process.go` manages backend + vLLM process lifecycle (auto-start/stop)
- Components are reusable Bubble Tea models composed into screens
- `internal/theme/theme.go` centralizes all Lipgloss styles
- Tests co-locate with source files (`*_test.go`)

**Build:** `cd tui && make build` produces `emotionsim-tui` binary

## Gotchas

- **vLLM model override**: `VLLMClient` ignores model param and always uses the server's loaded model (`vllm_default_model`)
- **Qwen thinking tokens**: vLLM payload sets `chat_template_kwargs.enable_thinking: false` for qwen3 models to avoid empty responses
- **World state `_` keys**: Engine injects `_scene_location`, `_scene_participants`, `_conclusion_directive`, `_graph_entity_ids` into world_state — these are transient and cleaned up after use
- **Token budget**: `agent_max_tokens_per_run=50000` counts streamed characters (not LLM tokens). Set to 0 to disable. Completion telemetry: `run.metrics` gets `tokens`, `tokens_per_agent`, `latency_ms`, `cost_estimate_usd` (rate = `LLM_COST_PER_1K_TOKENS`)
- **Parallel scenes**: Only with `llm_backend=vllm`. Ollama falls back to sequential due to GPU serialization
- **TUI auto-start**: The Go TUI spawns `python3 -m emotionsim.main` and `vllm serve` as child processes. Use `--no-backend`/`--no-vllm` flags to suppress
- **Single engine path**: `SimulationEngine` (V1) is the only engine. The experimental V2 engine (heartbeat scheduling) was removed; goal trees + governance gates are native to V1, and heartbeat scheduling was never adopted
- **env.example**: Lives at the repo root (`env.example`). Missing `VLLM_BASE_URL` and `VLLM_DEFAULT_MODEL` (those default in code to `:8010` and `Qwen/Qwen3.5-4B`)
- **Datalake**: Enabled via `DATALAKE_ENABLED=true`. Schema in `datalake/schema.sql`. Powers the TUI Analytics screen + `/datalake/compare` endpoint
- **Hybrid search weights** (mirofish branch): `VECTOR_WEIGHT=0.7`, `KEYWORD_WEIGHT=0.3` in `OracleGraphStorage`. Keyword scoring is simple term-matching (not true BM25) for SQLite test compat
- **Embeddings stored as JSON** (mirofish branch): `embedding_json` columns use `OracleJSON` (CLOB) for SQLite test compatibility. In production Oracle, migrate to `VECTOR(768)` columns for native vector search. Embedding failures degrade gracefully to keyword-only scoring
- **Opinion shift clamping** (mirofish branch): Max shift per interaction is +-0.3, stances clamped to [-1.0, 1.0]. Shifts below 0.001 are ignored as noise
- **Lightweight agent promotion** (mirofish branch): `should_promote()` returns True when addressed directly, when extraversion >= 7 in active scene, or when leadership >= 8 with stress <= 4. Promoted agents consume the per-step LLM budget (`MAX_LLM_AGENTS_PER_STEP`); demotion returns them to background after `BACKGROUND_DEMOTE_AFTER_STEPS` of inactivity
- **Graph memory vs AgentMemory** (mirofish branch): runtime-switchable via `GRAPH_MEMORY_ENABLED`. On: HumanAgents recall via hybrid graph search (relevance, not recency) and store observations/decisions as memory nodes linked to location entities. Off: flat `AgentMemory` sliding window (default — preserves byte-identical determinism)
- **Structured output**: act/think/plan responses validate against Pydantic schemas in `emotionsim/llm/schemas.py`; on validation failure the LLM is retried once with the error injected, then defensive parsing
- **Reflection**: every `REFLECTION_INTERVAL_STEPS` ticks, foreground agents run a batched LLM reflection that stores lessons in episodic memory; `get_salient_memories` does importance-weighted recall with recency decay
- **Eval harness**: `emotionsim eval` runs scenario × seed × prompt-variant matrices against the offline stub LLM (`LLM_BACKEND=stub`), aggregating cooperation/emergence metrics and determinism fingerprints; wired into CI as a regression gate
