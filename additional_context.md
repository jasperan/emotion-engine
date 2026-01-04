The kind of system you describe is absolutely feasible: a multi-agent “simulation engine” where autonomous AI agents interact in parallel, pursuing goals inside configurable scenarios, with a dashboard to observe and steer them.

​

Below is a concise but complete technical requirements draft plus a Claude-oriented “implementation helper spec” you can feed to a coding agent.
1. Conceptual model inspired by The Great Flood

In The Great Flood, the key AI idea is an Emotion Engine trained via thousands of disaster simulations where agents face moral and survival dilemmas, with the twist that the entire apparent “reality” is a simulation.

​

For your system:

    Core concept: A Simulation Engine that runs many “worlds,” each world containing multiple autonomous agents (LLM-backed) that:

        Receive scenario context and local observations.

        Interact with each other via messages (chats) and environment events.

        Take actions and log their reasoning toward a scenario-specific goal (e.g., rescue planning, resource allocation, ethical choices).

    Design role (the “lady” in the film): A Designer Agent or Orchestrator that:

        Defines or modifies scenario parameters.

        Spawns agents with roles, capabilities, and personalities.

        Monitors and evaluates outcomes across many runs.

    Objective: Provide a dashboard to:

        Start/stop simulations and runs.

        Inspect conversations per agent/group.

        Compare runs, scores, and emergent behaviors.

2. System architecture (Python + Ollama + Claude)

High-level components:

    Frontend Dashboard

        Web UI (e.g., Next.js/React, SvelteKit, or FastAPI + HTMX) for:

            Scenario configuration (world parameters, #agents, roles).

            Simulation control (start, pause, step, reset).

            Live views:

                Per-agent chat logs.

                Room/group chats.

                Timeline of events and key decisions.

        WebSocket or SSE for streaming updates from backend.

    ​

Backend API & Orchestrator

    Python web framework: FastAPI for REST + WebSocket endpoints.

    Responsibilities:

        Scenario and run management (CRUD, versioning).

        Agent lifecycle: spawn, assign roles, route messages.

        Simulation clock:

            Discrete steps (ticks) or event-driven (messages trigger actions).

        Logging & persistence in PostgreSQL or SQLite:

            Worlds, agents, runs, steps, messages, states, metrics.

    Queue/execution:

        Use async + asyncio or a lightweight queue (e.g., Redis + RQ/Celery) to parallelize agent reasoning.

Agent Runtime Layer

    Agent abstraction:

        Agent base class with:

            id, role, persona, goals, memory, tools.

            observe(state) -> perception.

            decide(perception, messages) -> action(s), message(s).

            tick() that encapsulates one turn.

    Agent types:

        Environment Agent: manipulates world state (flood level, hazards, resources).

        Human-like Agents: with persona and emotional profile, interacting via chat.

        Designer/Orchestrator Agent: sets goals, parameters, evaluation rules.

    Multi-agent routing:

        Message bus: in-memory or Redis-channel based.

        Supports:

            Direct messages (agent-to-agent).

            Group chats (room/topic).

            Broadcasts (system announcements).

    AI integration:

        Ollama-backed models for most agents (local Llama 3.x, phi, etc.).

​

        ​

        Optional Claude via API for:

            Higher-level orchestration (e.g., scenario design).

            Evaluation and scoring of runs.

        Use an “LLM Router” abstraction so each agent can specify which model to call.

LLM Invocation Layer (Ollama + Claude)

    Ollama:

        Local server at http://localhost:11434.

​

Python client using OpenAI-compatible interface or ollama Python package.
​

            ​

        Claude:

            Standard HTTPS API client with retries and rate limiting.

        Common interface:

            LLMClient.generate(model_id, messages, tools=None, system=None, temperature=...).

        Prompt templates:

            Agent system prompts defining:

                Role and persona.

                Scenario context and constraints.

                Action space and output schema (JSON for actions + natural language for chat).

    State & Storage

        Database schema (simplified):

            scenarios (id, name, config JSON, created_by, created_at).

            runs (id, scenario_id, seed, status, start_at, end_at, metrics JSON).

            agents (id, run_id, role, model, persona, config JSON).

            steps (id, run_id, step_index, timestamp, state_snapshot JSON).

            messages (id, run_id, from_agent, to_agent or room, content, metadata JSON).

        Optional:

            Vector store (e.g., Qdrant) for long-term episodic memory per agent.

3. Interaction model and simulation loop

Simulation loop (discrete-time example):

    Initialization:

        Load scenario config and seed RNG.

        Instantiate agents with roles and initial knowledge.

        Create initial world state (e.g., flood level, known locations, resources).

    For each tick:

        For each active agent:

            Collect:

                Local view of state.

                Recent messages addressed to this agent or its room.

            Call its underlying LLM (Ollama/Claude) with:

                System prompt: role, rules, allowed actions.

                Context: scenario summary, current state summary, past key events.

                Messages: conversation turns.

            Parse structured output:

                actions (e.g., move, rescue, broadcast).

                message (optional chat content).

        Apply actions to world state (environment logic).

        Emit messages into message bus and persist logs.

        Compute metrics (e.g., casualties, resources used, cooperation score).

        Notify frontend via WebSockets.

    Termination:

        Stop when:

            Max ticks reached.

            Goal reached or failure condition triggered.

        Evaluate run:

            Use an Evaluation Agent (Claude) to score:

                Cooperation, ethics, strategy, emotional coherence.

        Store metrics and evaluation summary.

Parallel runs:

    Support multiple concurrent runs per scenario with different seeds or parameters to mimic “thousands of simulations” as in the film.

    ​

    Backend needs:

        Configurable concurrency limit.

        Run queue and worker pool.

4. Technology choices and key libraries

Backend:

    Python 3.11+

    FastAPI (API + WebSockets) + Uvicorn or Hypercorn.

    SQLAlchemy + Alembic migrations.

    PostgreSQL (prod) or SQLite (dev).

    Redis (optional) for:

        Pub/sub message bus.

        Task queue.

Multi-agent & LLM:

    Ollama with OpenAI-compatible client.

​

​

Custom lightweight agent framework, or:

    Evaluate OpenAI’s Swarm framework and adapt for Ollama as in community integrations.

​

        ​

    For Claude-based orchestration:

        Use Anthropic SDK or plain HTTP client.

Frontend:

    SvelteKit or Next.js with Tailwind for fast development.

    WebSockets/SSE client for live logs and state.

Protocols (optional, forward-looking):

    MCP & A2A if you want to make your agents and tools reusable across ecosystems.

​

    ​

        MCP to expose tools (sim controller, state inspection).

        A2A for standardized inter-agent messaging.

5. “Technical requirements file” (draft spec)

You can treat this as a spec to hand to a coding agent (e.g., Claude) as the high-level contract.
5.1 Non-functional requirements

    Local-first, privacy-friendly:

        All primary simulation runs must be possible with Ollama-only models.

    Extensible:

        Pluggable models and agent roles.

        New scenarios defined via JSON/YAML.

    Observability:

        Structured logs of all messages and actions.

        Per-run metrics with filters and charts.

    Concurrency:

        Support at least:

            10 concurrent scenarios.

            50 agents per scenario.

            200 total agents active.

    UX:

        Web dashboard with:

            Scenario designer view.

            Run explorer.

            Per-agent chat view.

5.2 Functional requirements

    Scenario Management

        Create, update, clone, delete scenarios.

        Scenario config includes:

            Name, description.

            Simulation mode (discrete-time vs event-driven).

            Global parameters (e.g., disaster intensity, resource availability).

            Agent templates:

                Role, persona, model, tools, initial knowledge.

            Termination conditions (time limit, goal threshold).

    Agent Management

        Define agent templates:

            Model ID (e.g., "llama3.3", "phi3"), provider (ollama, claude).

            Role description and persona.

            Input/output schemas for actions.

        Runtime:

            Show active agents per run.

            Enable pausing, muting (no messages), or terminating an agent.

            Manual override: send message or command to specific agents from UI.

    Simulation Engine

        Implement discrete-time tick loop with:

            Per-agent step execution.

            Deterministic ordering with seed.

        Support parallel runs:

            Async workers per run.

        State progression:

            Configurable environment dynamics (e.g., flood level increase).

        Logging:

            Persist state snapshots and messages per step.

    Messaging System

        Message routing:

            Direct, room, broadcast.

        Message formats:

            Structured JSON with metadata (sender, recipients, run, step).

        History:

            Query API by agent, room, run, timeframe.

        UI:

            Chat-style view per agent and per room.

    Evaluation & Scoring

        Rule-based metrics (code-defined).

        LLM-based evaluation:

            An Evaluation Agent (Claude or a strong local model) that:

                Reads run summary & logs.

                Outputs scores and narrative assessment.

        UI:

            Show scores, charts, and evaluation text.

    Dashboard & UX

        Pages:

            Home: list scenarios and recent runs.

            Scenario Designer: forms for parameters and agent templates.

            Run Console:

                LIVE view (current step, key metrics).

                Agent chats and actions.

                Timeline of events.

        Controls:

            Start, pause, resume, step, stop runs.

            Duplicate run with tweaks.
