# EmotionSim - Multi-Agent Simulation System

![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Code Style](https://img.shields.io/badge/Code%20Style-Black-000000.svg?style=for-the-badge)
![Ollama](https://img.shields.io/badge/backend-Ollama-black?style=for-the-badge)

> **"The Great Flood" in your terminal.**
> A local-first multi-agent simulation system for running complex disaster scenarios with diverse human personas.

![CLI Monitor](img/cli.png)

## Overview

EmotionSim is a research-grade simulation engine designed to analyze emergent cooperative behaviors in AI agent swarms. It combines a robust discrete-event simulation kernel with rich LLM-driven agent personas to create high-fidelity social simulations.

## Key Features

- **🧠 Deep Agent Roleplay**: Agents have rich personas with demographics, Big Five personality traits, and dynamic emotional states.
- **⚡ Real-time CLI Monitor**: A beautiful, terminal-based dashboard for watching your simulation unfold in real-time.
- **🔄 Discrete Event Simulation**: Deterministic step-by-step execution for reproducible research.
- **📡 Modern Architecture**: FastAPI backend + SvelteKit frontend, connected via WebSockets.
- **🔌 LLM Agnostic**: Built for Ollama (local) but extensible to Claude/GPT-4.
- **📊 Auto-Evaluation**: Built-in evaluator agents that analyze run performance and narrative arcs.

## Quick Start

The fastest way to get started is using the CLI tool.

### 1. Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) running locally (e.g., `ollama serve`)
- An LLM model pulled (e.g., `ollama pull gemma2`)

### 2. Installation

```bash
cd backend
pip install -e .
```

### 3. Run a Simulation

The `emotionsim` CLI is the main interface. Start a simulation immediately:

```bash
# Run the built-in "Rising Flood" scenario
emotionsim run --scenario "Rising Flood"
```

This launches the **Interactive CLI Monitor**, where you can watch:
- 🌍 **World State**: Water levels, temperature, time.
- 👥 **Agents**: Real-time health, stress, and current actions.
- 💬 **Live Stream**: The raw thought process of the LLM agents.

### Other Running Modes

**Automated Batch Testing**
Run multiple simulations in sequence without supervision:
```bash
emotionsim auto --count 5
```

**Full Client-Server Mode**
If you prefer the web dashboard:
```bash
# Start the full stack
cd frontend
npm run dev
```

This will:
1. Start the Python backend (API + Simulation Engine)
2. Start the SvelteKit frontend dashboard
3. Launch the browser automatically

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SvelteKit Dashboard                       │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────────┐    │
│  │ Scenarios │  │ Run View  │  │  Agent Chat Logs     │    │
│  └───────────┘  └───────────┘  └──────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket / REST
┌────────────────────────┴────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌──────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │   API    │  │ SimulationEngine │  │   LLM Router   │    │
│  └──────────┘  └─────────────────┘  └─────────────────┘    │
│        │               │                     │              │
│  ┌─────┴─────┐  ┌─────┴─────┐        ┌─────┴─────┐        │
│  │  SQLite   │  │  Agents   │        │  Ollama   │        │
│  └───────────┘  └───────────┘        └───────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
emotion-engine/
├── backend/
│   ├── app/
│   │   ├── agents/         # Agent classes (Human, Environment, Designer, Evaluator)
│   │   ├── api/            # FastAPI routes and WebSocket
│   │   ├── llm/            # LLM client abstraction
│   │   ├── models/         # SQLAlchemy database models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── scenarios/      # Pre-built scenarios (Rising Flood)
│   │   └── simulation/     # Simulation engine and message bus
│   └── tests/              # Pytest tests
├── frontend/
│   ├── src/
│   │   ├── lib/            # Components, stores, API client
│   │   └── routes/         # SvelteKit pages
│   └── static/
└── docker-compose.yml
```

## Example Scenario: Rising Flood

The included "Rising Flood" scenario features 8 diverse human agents:

| Character | Age | Occupation | Key Traits |
|-----------|-----|------------|------------|
| Dr. Sarah Chen | 42 | ER Doctor | High empathy, calm under pressure |
| Marcus Thompson | 28 | Construction Worker | Risk-taker, physically strong |
| Elena Rodriguez | 67 | Retired Teacher | Wise, limited mobility |
| Jake Miller | 16 | Student | Impulsive, athletic swimmer |
| Aisha Patel | 35 | Software Engineer | Analytical, introverted |
| Bobby Williams | 55 | Retired Firefighter | Natural leader, some injuries |
| Mei-Lin Wu | 8 | Child | Scared, needs protection |
| Victor Kozlov | 45 | Unemployed | Bitter, unpredictable |

## CLI Monitor Tool

### Installation

```bash
cd backend
pip install -e .  # Install CLI entry point
```

### Interactive Menu
Run `python backend/cli.py` (or just `emotionsim` if installed) to see the new dashboard:

```
```text
╭───────────────────────────────────────────╮
│ Emotion Engine CLI                        │
│ Autonomous Agent Simulation System         │
╰───────────────────────────────────────────╯

? Select a Task:
  Generate New Scenario
  Browse Scenarios
  Run Scenario (Standalone)
  Monitor Simulation
  Interactive Wizard
  Exit
```
```

### Commands

**Run Simulation (Standalone Mode)**
```bash
emotionsim run --scenario "Rising Flood" --max-steps 50 --seed 42
emotionsim run --scenario "Rising Flood" --simple  # Log output
```

**Monitor Running Simulation (Client Mode)**
```bash
emotionsim monitor --run-id <uuid>
emotionsim monitor --run-id <uuid> --simple
```

**Scenario Management**
```bash
emotionsim scenarios                    # List scenarios
emotionsim scenarios --create-builtin   # Create built-in scenarios
```

**Interactive Mode**
```bash
emotionsim interactive  # Wizard to configure and run
```

**Server Status**
```bash
emotionsim status  # Check if backend is running
```

### CLI Features

- **Rich UI Mode**: Live-updating panels with world state, agent status, conversations, and event log
- **Simple Mode**: Clean streaming logs for piping/grepping
- **Dual Modes**: Standalone (no server) or Client (WebSocket to backend)
- **Real-time Monitoring**: See all agent conversations, movements, and events as they happen

---

# ANNEX: Agent Harness Implementation

This section documents the advanced reasoning strategies and communication mechanisms implemented in the EmotionEngine agent harness.

## Agent Communication Protocol (ACP)

The EmotionEngine implements a sophisticated Agent Communication Protocol (ACP) that enables structured, context-aware agent interactions.

### Core Components

#### 1. Agent Identity System

Each agent maintains a rich identity profile:

```python
@dataclass
class AgentIdentity:
    name: str
    role: str
    status: str = "active"  # active, idle, stuck, away
    personality: PersonalityProfile | None = None
    capabilities: list[str] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)
```

**Status Tracking**: Agents automatically transition between states based on activity, enabling the system to detect stuck or disengaged agents.

#### 2. Personality-Driven Behavior

The `PersonalityProfile` implements the Big Five personality model with extensions:

```python
@dataclass
class PersonalityProfile:
    # Big Five traits (1-10 scale)
    openness: int = 5
    conscientiousness: int = 5
    extraversion: int = 5
    agreeableness: int = 5
    neuroticism: int = 5
    
    # Extended traits
    risk_tolerance: int = 5
    empathy_level: int = 5
    leadership: int = 5
    
    # Dynamic state
    stress: int = 0
    confidence: float = 0.5
    engagement: int = 5
    communication_style: str = "balanced"
```

**Personality Modulation**: Personality traits directly influence agent behavior:
- **Extraversion** affects communication frequency and initiative
- **Neuroticism** modulates stress responses and emotional reactions
- **Leadership** impacts decision-making weight in group scenarios
- **Empathy** shapes cooperative behaviors and relationship building

#### 3. Structured Messaging

ACP messages carry rich metadata:

```python
@dataclass
class ACPMessage:
    sender: AgentIdentity
    channel: str  # direct, broadcast, room:location
    msg_type: str
    payload: dict[str, Any]
    recipient: str | None = None
    coordination_level: str = "moderate"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
```

**Channel Types**:
- **Direct**: One-to-one agent communication
- **Broadcast**: System-wide announcements
- **Room**: Location-based group communication (e.g., `room:hospital`)

### Communication Mechanisms

#### 1. Coordination Controller

Manages agent communication frequency and depth:

```python
class CoordinationController:
    LEVELS = {
        "none": {"probability": 0.0, "max_messages": 0},
        "minimal": {"probability": 0.3, "max_messages": 2},
        "moderate": {"probability": 0.6, "max_messages": 5},
        "chatty": {"probability": 0.9, "max_messages": 10},
    }
```

**Personality-Weighted Communication**:
- Base probability set by coordination level
- Modified by agent's extraversion score
- Tracks message counts per round to prevent spam
- Dynamically adjusts based on context and stress levels

**Usage**:
```python
if coordinator.should_communicate(agent, context):
    if coordinator.can_send_more(agent.name, round_id):
        # Agent can send message
        coordinator.record_message(agent.name, round_id)
```

#### 2. Agent Registry

Centralized tracking of all agents in the simulation:

```python
class AgentRegistry:
    def register(self, identity: AgentIdentity) -> None:
        """Register a new agent"""
        
    def get(self, name: str) -> AgentIdentity | None:
        """Get agent by name"""
        
    def detect_stuck_agents(self, threshold: float = 300.0) -> list[str]:
        """Find agents inactive for > threshold seconds"""
```

**Stuck Agent Detection**: Automatically identifies agents that haven't responded within a configurable time window, enabling intervention or reassignment.

#### 3. Wave-Based Task Execution

Implements dependency-aware task scheduling:

```python
class WaveController:
    async def execute_waves(self, tasks: list[Task]) -> AsyncIterator[WaveResult]:
        """
        Execute tasks in waves based on dependencies.
        Tasks with no dependencies run in wave 1.
        Tasks depending on wave 1 tasks run in wave 2, etc.
        """
```

**Features**:
- Automatic dependency resolution
- Concurrent execution within waves
- Maximum wave limit to prevent infinite loops
- Real-time progress reporting via async iterator

**Example**:
```python
# Task A and B have no dependencies (wave 1)
# Task C depends on A (wave 2)
# Task D depends on B and C (wave 3)

wave_controller.add_dependency("C", "A")
wave_controller.add_dependency("D", "B")
wave_controller.add_dependency("D", "C")

async for wave_result in wave_controller.execute_waves(tasks):
    print(f"Wave {wave_result.wave} completed")
```

## Reasoning Strategies

### 1. Multi-Level Memory System

Agents maintain sophisticated memory with multiple layers:

```python
class AgentMemory:
    def __init__(self, agent_id: str, sliding_window_size: int = 50):
        self.sliding_window_size = sliding_window_size
        self.events: deque[dict] = deque(maxlen=sliding_window_size)
        self.episodic_memories: list[EpisodicMemory] = []
        self.relationships: dict[str, RelationshipMemory] = {}
        self.arrival_context: dict | None = None
```

**Memory Components**:

#### A. Sliding Window (Short-Term)
- Fixed-size queue of recent events
- Automatically evicts oldest entries
- Provides immediate context for decision-making

#### B. Episodic Memory (Long-Term)
- Significant events and interactions
- Auto-summarization when threshold reached
- Enables learning from past experiences

```python
@dataclass
class EpisodicMemory:
    event_type: str
    description: str
    participants: list[str]
    emotional_valence: float  # -1 to 1
    importance: float  # 0 to 1
    timestamp: float
    summary: str | None = None  # Generated during consolidation
```

#### C. Relationship Tracking
- Tracks interactions with other agents
- Maintains trust levels and sentiment
- Stores notes about each relationship

```python
@dataclass
class RelationshipMemory:
    agent_id: str
    agent_name: str
    interaction_count: int = 0
    trust_level: float = 5.0  # 0-10 scale
    sentiment: str = "neutral"  # positive, neutral, negative
    notes: list[str] = field(default_factory=list)
    last_interaction: float = field(default_factory=time.time)
```

### 2. Contextual Decision Making

Agents build rich context before each decision:

```python
def build_context(
    self,
    world_state: dict[str, Any],
    messages: list[dict[str, Any]],
    step_actions: list[dict[str, Any]] | None = None,
    step_messages: list[dict[str, Any]] | None = None,
    step_events: list[str] | None = None,
) -> str:
    """Build comprehensive context from multiple sources"""
    context_parts = []
    
    # World state
    context_parts.append(self._format_world_state(world_state))
    
    # Recent messages
    context_parts.append(self._format_recent_messages(messages))
    
    # Relationship context
    if relevant_agents:
        context_parts.append(self.get_relationship_context(relevant_agents))
    
    # Episodic context
    context_parts.append(self.get_conversation_context())
    
    # Arrival context (why am I here?)
    if self.agent_memory.arrival_context:
        context_parts.append(self._format_arrival_context())
    
    return "\n\n".join(context_parts)
```

**Context Layers**:
1. **World State**: Current environment, hazards, resources
2. **Message History**: Recent communications
3. **Relationship Context**: Trust and sentiment with nearby agents
4. **Episodic Context**: Relevant past experiences
5. **Arrival Context**: Reason for being at current location

### 3. Group Decision Making (Voting)

Implements weighted democratic decision-making:

```python
class GroupDecisionMixin:
    def tally_votes(
        self,
        votes: dict[str, dict],  # {agent_name: {choice, weight}}
        personalities: dict[str, PersonalityProfile] | None = None,
        trust_levels: dict[tuple[str, str], float] | None = None,
    ) -> VoteResult:
        """
        Tally votes with personality and trust weighting.
        
        Weight modifiers:
        - Leadership: Higher leadership = more influence
        - Stress: High stress reduces voting weight
        - Trust: Agents trusted by others have more weight
        """
```

**Weight Calculation**:
```python
base_weight = vote_data["weight"]

# Leadership modifier
leadership_mod = personality.leadership / 5.0

# Stress penalty
stress_penalty = 1.0 - (personality.stress / 20.0)

# Trust modifier
avg_trust = calculate_average_trust_from_others(agent_name)
trust_mod = 0.5 + avg_trust

effective_weight = base_weight * leadership_mod * stress_penalty * trust_mod
```

**Result Structure**:
```python
@dataclass
class VoteResult:
    winner: str
    confidence: float  # 0-1, how strong the consensus
    breakdown: dict  # Vote distribution with weights
    total_votes: int
```

### 4. Behavioral Loop Detection & Breaking

The CooperationCoordinator prevents agents from getting stuck:

```python
class CooperationCoordinator:
    def detect_behavioral_loop(self, agent_id: str, action: str) -> bool:
        """Detect if agent is repeating the same action"""
        recent_actions = self._action_history[agent_id][-5:]
        return recent_actions.count(action) >= 3
    
    def suggest_alternative(self, agent_id: str, current_action: str) -> str | None:
        """Suggest alternative action to break loop"""
        if self.detect_behavioral_loop(agent_id, current_action):
            return random.choice([
                "seek_help",
                "change_location",
                "rest",
                "communicate",
            ])
        return None
```

**Loop Prevention Strategies**:
1. **Pattern Detection**: Identifies repeated actions
2. **Intervention**: Suggests alternative behaviors
3. **Goal Reassignment**: Redirects to different objectives
4. **Resource Reallocation**: Adjusts available resources

### 5. Adaptive LLM Prompting

Agents construct context-aware prompts:

```python
def get_system_prompt(self) -> str:
    """Generate role-specific system prompt"""
    return f"""You are {self.name}, a {self.persona.age}-year-old {self.persona.occupation}.

Personality:
- Openness: {self.persona.openness}/10
- Conscientiousness: {self.persona.conscientiousness}/10
- Extraversion: {self.persona.extraversion}/10
- Agreeableness: {self.persona.agreeableness}/10
- Neuroticism: {self.persona.neuroticism}/10

Current State:
- Health: {self.dynamic_state.get('health', 100)}%
- Stress: {self.dynamic_state.get('stress', 0)}%
- Location: {self.dynamic_state.get('location', 'unknown')}

Goals: {', '.join(self.goals)}

Remember:
- Stay in character based on your personality
- React emotionally based on your neuroticism and current stress
- Cooperate with others based on your agreeableness
- Take initiative based on your extraversion
- Adapt your communication style to your personality

Respond in JSON format with your action and optional message.
"""
```

**Prompt Engineering Principles**:
1. **Role Consistency**: Explicit personality reminders
2. **State Awareness**: Current health, stress, location
3. **Goal Orientation**: Clear objectives
4. **Behavioral Guidelines**: How to embody the personality
5. **Structured Output**: JSON response format for reliability

## Integration Architecture

### Simulation Engine Orchestration

The `SimulationEngine` coordinates all components:

```python
class SimulationEngine:
    def __init__(self, run_id: str, db_session: AsyncSession):
        # Core systems
        self.agents: dict[str, Agent] = {}
        self.message_bus = MessageBus()
        self.conversation_manager = ConversationManager()
        self.coordinator = CooperationCoordinator()
        
        # ACP components
        self.acp_registry = AgentRegistry()
        self.acp_coordination = CoordinationController(level="moderate")
        self.group_voting = GroupDecisionMixin()
        
        # State
        self.world_state: dict[str, Any] = {}
        self._agent_locations: dict[str, str] = {}
```

### Tick Loop Implementation

```python
async def run_simulation(self):
    """Main simulation loop"""
    while not self._stop_requested and self.current_step < self.max_steps:
        # Phase 1: Environment agents generate events
        for agent in environment_agents:
            await agent.tick(self.world_state, [])
        
        # Phase 2: Human agents act (shuffled for fairness)
        random.shuffle(human_agents)
        for agent in human_agents:
            # Get relevant messages
            messages = self.message_bus.get_messages(agent.id)
            
            # Build context
            context = agent.build_context(
                world_state=self.world_state,
                messages=messages,
                step_actions=step_actions,
                step_messages=step_messages,
            )
            
            # Agent decides and acts
            response = await agent.tick(self.world_state, messages)
            
            # Process actions
            for action in response.actions:
                await self._process_action(agent, action)
            
            # Send messages if any
            if response.message:
                self.message_bus.send(
                    from_agent=agent.id,
                    to_target=response.message.to_agent,
                    content=response.message.content,
                )
        
        # Persist state
        await self._save_step()
        
        # Check for consensus/completion
        if self._check_consensus():
            break
        
        self.current_step += 1
        await asyncio.sleep(self.tick_delay)
```

## Key Design Principles

### 1. Separation of Concerns
- **Agent**: Decision-making and role-playing
- **MessageBus**: Communication routing
- **ConversationManager**: Dialogue coordination
- **CooperationCoordinator**: Goal tracking and loop prevention
- **SimulationEngine**: Orchestration and persistence

### 2. Extensibility
- New agent types inherit from `Agent` base class
- Custom coordination strategies implement `CoordinationController` interface
- Additional memory layers can extend `AgentMemory`

### 3. Determinism
- Seedable random number generation
- Ordered agent processing (environment first, then shuffled humans)
- Explicit state snapshots for reproducibility

### 4. Resilience
- Automatic stuck agent detection
- Behavioral loop breaking
- Graceful degradation under LLM failures
- State persistence for resumption

### 5. Observability
- Rich logging at every layer
- Real-time WebSocket events
- Database persistence for post-hoc analysis
- CLI monitor for live inspection

## Performance Characteristics

- **Memory**: O(N × M) where N = agents, M = memory window size
- **Communication**: O(M) per agent per step (bounded by coordination limits)
- **Decision Latency**: Dominated by LLM inference time (typically 1-5 seconds)
- **Scalability**: Tested up to 20 concurrent agents on single Ollama instance

## Future Enhancements

1. **Distributed Simulation**: Multi-node deployment for larger agent counts
2. **Hierarchical Agents**: Agents that can spawn sub-agents for complex tasks
3. **Learning from Feedback**: Episodic memory influences future decisions
4. **Emotion Contagion**: Agents' emotional states affect nearby agents
5. **Coalition Formation**: Dynamic group formation based on goals and trust

---

## License

MIT License - see LICENSE file for details.

## Acknowledgments

Inspired by the Emotion Engine concept from Netflix's "The Great Flood" - where AI agents run through thousands of disaster simulations to develop emotional intelligence and moral reasoning.

---

<div align="center">

[![GitHub](https://img.shields.io/badge/GitHub-jasperan-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/jasperan)&nbsp;
[![LinkedIn](https://img.shields.io/badge/LinkedIn-jasperan-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/jasperan/)

</div>
