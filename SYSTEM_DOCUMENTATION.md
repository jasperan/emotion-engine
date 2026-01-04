# EmotionSim - System Documentation

**Version:** 0.1.0  
**Last Updated:** 2026-01-04

This document provides comprehensive technical documentation for the EmotionSim multi-agent simulation system. It covers API endpoints, CLI integration, data schemas, WebSocket protocols, and integration examples.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [API Reference](#api-reference)
3. [CLI Integration Guide](#cli-integration-guide)
4. [Data Schemas](#data-schemas)
5. [WebSocket Protocol](#websocket-protocol)
6. [Integration Examples](#integration-examples)
7. [Testing and Development](#testing-and-development)

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    SvelteKit Frontend                        │
│                    (Port 5173)                               │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────────┐    │
│  │ Scenarios │  │ Run View  │  │  Agent Chat Logs     │    │
│  └───────────┘  └───────────┘  └──────────────────────┘    │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket / REST
┌────────────────────────┴────────────────────────────────────┐
│                    FastAPI Backend                           │
│                    (Port 8000)                               │
│  ┌──────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │   API    │  │ SimulationEngine │  │   LLM Router   │    │
│  └──────────┘  └─────────────────┘  └─────────────────┘    │
│        │               │                     │              │
│  ┌─────┴─────┐  ┌─────┴─────┐        ┌─────┴─────┐        │
│  │  SQLite   │  │  Agents   │        │  Ollama   │        │
│  │ Database  │  │  (Human,  │        │ (gemma2)  │        │
│  │           │  │   Env,    │        │           │        │
│  │           │  │ Designer) │        │           │        │
│  └───────────┘  └───────────┘        └───────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Scenario Creation**: Frontend/CLI → POST `/api/scenarios/` → Database
2. **Run Initialization**: Frontend/CLI → POST `/api/runs/` → SimulationEngine
3. **Simulation Execution**: SimulationEngine → Agents → LLM → Actions/Messages
4. **Real-time Updates**: SimulationEngine → WebSocket → Frontend/CLI
5. **State Persistence**: SimulationEngine → Database (Steps, Messages, Metrics)

### Database Schema

- **Scenarios**: Scenario definitions with agent templates and world config
- **Runs**: Simulation instances with status, metrics, and world state
- **Agents**: Agent instances with personas and dynamic state
- **Steps**: Snapshots of world state at each simulation tick
- **Messages**: Agent communications (direct, room, broadcast)

---

## API Reference

### Base URL

```
http://localhost:8000/api
```

### Authentication

Currently, no authentication is required. All endpoints are open.

---

### Scenarios API

#### List All Scenarios

```http
GET /api/scenarios/
```

**Query Parameters:**
- `skip` (int, optional): Number of records to skip (default: 0)
- `limit` (int, optional): Maximum records to return (default: 50)

**Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Rising Flood",
    "description": "A flood disaster scenario with 8 diverse human agents",
    "config": {
      "name": "Flooded City District",
      "description": "Urban area experiencing rapid flooding",
      "max_steps": 10,
      "tick_delay": 1.0,
      "initial_state": {
        "water_level": 0,
        "temperature": 20
      }
    },
    "agent_templates": [...],
    "created_at": "2026-01-04T12:00:00Z",
    "updated_at": "2026-01-04T12:00:00Z"
  }
]
```

#### Get Scenario by ID

```http
GET /api/scenarios/{scenario_id}
```

**Response:** Single scenario object (same structure as list item)

#### Create Scenario

```http
POST /api/scenarios/
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "My Custom Scenario",
  "description": "A custom disaster scenario",
  "config": {
    "name": "World Name",
    "description": "World description",
    "max_steps": 50,
    "tick_delay": 1.0,
    "initial_state": {
      "hazard_level": 0
    },
    "dynamics": {},
    "objects": {}
  },
  "agent_templates": [
    {
      "name": "Agent 1",
      "role": "human",
      "model_id": "gemma2",
      "provider": "ollama",
      "persona": {
        "age": 30,
        "sex": "female",
        "occupation": "Engineer",
        "big_five": {
          "openness": 0.7,
          "conscientiousness": 0.8,
          "extraversion": 0.5,
          "agreeableness": 0.6,
          "neuroticism": 0.3
        },
        "behavioral_modifiers": {
          "risk_tolerance": 0.5,
          "empathy": 0.7,
          "leadership": 0.6
        }
      },
      "goals": ["Survive", "Help others"],
      "initial_state": {
        "location": "Building A",
        "health": 10,
        "stress": 0
      },
      "inventory": []
    }
  ]
}
```

**Response:** Created scenario object with generated ID

#### Update Scenario

```http
PUT /api/scenarios/{scenario_id}
Content-Type: application/json
```

**Request Body:** Partial scenario object (only fields to update)

#### Delete Scenario

```http
DELETE /api/scenarios/{scenario_id}
```

**Response:**
```json
{
  "status": "deleted",
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Generate Scenario (AI-Powered)

```http
POST /api/scenarios/generate
Content-Type: application/json
```

**Request Body:**
```json
{
  "prompt": "zombie outbreak in a shopping mall",
  "persona_count": 50,
  "archetypes": ["survivor", "security", "civilian"],
  "save_to_file": true
}
```

**Response:**
```json
{
  "scenario": {
    "name": "Mall Outbreak",
    "description": "Zombie outbreak scenario...",
    "config": {...},
    "agent_templates": [...]
  },
  "filepath": "/path/to/scenarios_generated/mall_outbreak_20260104_120000.json",
  "message": "Successfully generated scenario: Mall Outbreak"
}
```

#### List Scenario Files

```http
GET /api/scenarios/files
```

Lists all generated scenario JSON files from `scenarios_generated/` directory.

**Response:**
```json
[
  {
    "filename": "trade_winds_20260104_160945.json",
    "filepath": "/full/path/to/file.json",
    "name": "Trade Winds",
    "description": "Maritime trade scenario",
    "generated_at": "2026-01-04T16:09:45Z",
    "persona_count": 50
  }
]
```

#### Get Scenario File

```http
GET /api/scenarios/files/{filename}
```

#### Delete Scenario File

```http
DELETE /api/scenarios/files/{filename}
```

#### Import Scenario File to Database

```http
POST /api/scenarios/files/{filename}/import
```

Imports a generated scenario file into the database.

---

### Runs API

#### Create Run

```http
POST /api/runs/
Content-Type: application/json
```

**Request Body:**
```json
{
  "scenario_id": "550e8400-e29b-41d4-a716-446655440000",
  "seed": 42,
  "max_steps": 100
}
```

**Response:**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "scenario_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "current_step": 0,
  "max_steps": 100,
  "seed": 42,
  "world_state": {},
  "metrics": {},
  "evaluation": {},
  "created_at": "2026-01-04T12:00:00Z",
  "started_at": null,
  "completed_at": null
}
```

#### List Runs

```http
GET /api/runs/
```

**Query Parameters:**
- `scenario_id` (string, optional): Filter by scenario
- `skip` (int, optional): Pagination offset
- `limit` (int, optional): Max results (default: 50)

#### Get Run by ID

```http
GET /api/runs/{run_id}
```

#### Control Run

```http
POST /api/runs/{run_id}/control
Content-Type: application/json
```

**Request Body:**
```json
{
  "action": "start"
}
```

**Actions:**
- `start`: Begin simulation
- `pause`: Pause execution
- `resume`: Resume from pause
- `stop`: Stop simulation
- `step`: Execute single step (for debugging)

**Response:**
```json
{
  "status": "ok",
  "action": "start",
  "run_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

#### Get Run Status

```http
GET /api/runs/{run_id}/status
```

**Response:**
```json
{
  "run_id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "running",
  "current_step": 15,
  "max_steps": 100,
  "is_paused": false
}
```

#### Get Run Agents

```http
GET /api/runs/{run_id}/agents
```

**Response:**
```json
[
  {
    "id": "agent_001",
    "name": "Dr. Sarah Chen",
    "role": "human",
    "model_id": "gemma2",
    "provider": "ollama",
    "persona": {...},
    "dynamic_state": {
      "location": "Building A",
      "health": 8,
      "stress": 3
    },
    "is_active": true
  }
]
```

#### Get Run Steps

```http
GET /api/runs/{run_id}/steps
```

**Query Parameters:**
- `skip`, `limit`: Pagination

**Response:**
```json
[
  {
    "id": "step_001",
    "run_id": "660e8400-e29b-41d4-a716-446655440001",
    "step_index": 1,
    "state_snapshot": {
      "water_level": 2,
      "temperature": 19
    },
    "actions": [...],
    "step_metrics": {
      "avg_health": 9.5,
      "avg_stress": 2.1
    },
    "timestamp": "2026-01-04T12:01:00Z"
  }
]
```

#### Get Run Messages

```http
GET /api/runs/{run_id}/messages
```

**Query Parameters:**
- `agent_id` (string, optional): Filter by agent
- `skip`, `limit`: Pagination

**Response:**
```json
[
  {
    "id": "msg_001",
    "run_id": "660e8400-e29b-41d4-a716-446655440001",
    "from_agent_id": "agent_001",
    "to_target": "agent_002",
    "message_type": "direct",
    "content": "We need to move to higher ground!",
    "metadata": {
      "context_size": 1024
    },
    "step_index": 5,
    "timestamp": "2026-01-04T12:05:00Z"
  }
]
```

#### Delete Run

```http
DELETE /api/runs/{run_id}
```

---

### Seed API

#### Seed Rising Flood Scenario

```http
POST /api/seed/rising-flood
```

Creates the built-in "Rising Flood" scenario in the database if it doesn't exist.

---

### Health Endpoints

#### API Health

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "app": "EmotionSim API"
}
```

#### LLM Health

```http
GET /api/health/llm
```

**Response:**
```json
{
  "provider": "ollama",
  "status": "healthy"
}
```

---

## CLI Integration Guide

### Installation

```bash
cd backend
pip install -e .
```

This installs the `emotionsim` command globally.

### Primary Testing Modes

EmotionSim provides two primary CLI modes for testing and running simulations:

#### 1. `emotionsim run` - Interactive Single Simulation

Run a single simulation with full control and real-time monitoring.

**Basic Usage:**
```bash
emotionsim run --scenario "Rising Flood" --max-steps 10 --seed 42
```

**Options:**
- `--scenario`, `-s`: Scenario name (required)
- `--max-steps`, `-m`: Maximum simulation steps (default: from scenario config)
- `--seed`: Random seed for reproducibility (optional)
- `--tick-delay`, `-t`: Delay between ticks in seconds (default: 1.0)
- `--simple`: Use simple log output instead of rich UI

**Rich UI Mode (Default):**
Displays a live-updating terminal interface with:
- World state panel (hazard levels, temperature, time)
- Agent status panel (health, stress, location, inventory)
- Live stream panel (real-time LLM output)
- Event log (formatted messages and actions)

**Simple Mode:**
```bash
emotionsim run --scenario "Rising Flood" --simple
```

Clean streaming logs suitable for piping or grepping.

#### 2. `emotionsim auto` - Automated Sequential Testing

Automatically run multiple simulations sequentially for testing and data collection.

**Basic Usage:**
```bash
emotionsim auto
```

**Options:**
- `--count`, `-n`: Number of simulations to run (default: infinite)

**Features:**
- Interactive preset selection at startup
- Checks for pending runs first, then creates new ones
- Cleans up any stuck pending/running simulations before starting
- Uses Rich UI mode for detailed monitoring
- Automatically cycles through scenarios or uses selected preset

**Preset Selection:**
```
Select Auto-Run Source:
  0. Random (Cycle through all)
  1. Rising Flood
  2. Other Scenario...
```

**Example - Run 5 simulations:**
```bash
emotionsim auto --count 5
```

### Additional CLI Commands

#### Check Server Status

```bash
emotionsim status
```

Shows backend health and recent runs.

#### List Scenarios

```bash
emotionsim scenarios
```

**Create built-in scenarios:**
```bash
emotionsim scenarios --create-builtin
```

#### Interactive Wizard

```bash
emotionsim interactive
```

Launches a step-by-step wizard to configure and run a simulation.

#### Monitor Running Simulation (Client Mode)

```bash
emotionsim monitor --run-id <uuid>
```

Connect to a running simulation via WebSocket and monitor in real-time.

**Options:**
- `--url`, `-u`: Backend URL (default: `ws://localhost:8000/api`)
- `--simple`: Simple log output

#### Show Best Runs

```bash
emotionsim best --limit 10
```

Displays top simulations ranked by agent health and stress metrics.

### CLI Modes Comparison

| Feature | `run` | `auto` | `monitor` |
|---------|-------|--------|-----------|
| Server Required | No (Standalone) | No (Standalone) | Yes (Client) |
| Creates Run | Yes | Yes | No |
| Real-time UI | Yes | Yes | Yes |
| Multiple Runs | No | Yes | No |
| Preset Selection | No | Yes | No |

---

## Data Schemas

### Scenario Schemas

#### WorldConfig

```python
{
  "name": str,                    # World/environment name
  "description": str,             # World description
  "initial_state": dict,          # Initial world state (e.g., {"water_level": 0})
  "dynamics": dict,               # How world changes over time
  "max_steps": int | None,        # Max simulation steps (None = infinite)
  "tick_delay": float,            # Delay between ticks (0-60 seconds)
  "objects": dict                 # Item and interactable definitions
}
```

#### AgentConfig

```python
{
  "name": str,
  "role": "human" | "environment" | "designer" | "evaluator",
  "model_id": str,                # LLM model (e.g., "gemma2")
  "provider": "ollama" | "anthropic",
  "persona": Persona | None,      # Required for human agents
  "goals": list[str],
  "tools": list[str],
  "initial_state": dict,          # Initial dynamic state
  "inventory": list[Item]
}
```

#### Persona

```python
{
  "age": int,
  "sex": str,
  "occupation": str,
  "backstory": str,
  "big_five": {
    "openness": float,            # 0.0 - 1.0
    "conscientiousness": float,
    "extraversion": float,
    "agreeableness": float,
    "neuroticism": float
  },
  "behavioral_modifiers": {
    "risk_tolerance": float,      # 0.0 - 1.0
    "empathy": float,
    "leadership": float,
    "adaptability": float,
    "stress_resilience": float
  }
}
```

#### Item

```python
{
  "name": str,
  "description": str,
  "properties": dict              # Custom properties
}
```

### Run Schemas

#### RunCreate

```python
{
  "scenario_id": str,             # UUID of scenario
  "seed": int | None,             # Random seed
  "max_steps": int | None         # Override scenario max_steps
}
```

#### RunControl

```python
{
  "action": "start" | "pause" | "resume" | "stop" | "step"
}
```

#### RunResponse

```python
{
  "id": str,
  "scenario_id": str,
  "status": "pending" | "running" | "paused" | "completed" | "stopped" | "cancelled" | "error",
  "current_step": int,
  "max_steps": int,
  "seed": int | None,
  "world_state": dict,
  "metrics": dict,
  "evaluation": dict,
  "created_at": datetime,
  "started_at": datetime | None,
  "completed_at": datetime | None
}
```

### Agent Schemas

#### AgentAction

```python
{
  "action_type": "move" | "speak" | "wait" | "reflect" | "help" | 
                 "search" | "take" | "drop" | "use" | "interact" |
                 "join_conversation" | "leave_conversation" |
                 "propose_task" | "accept_task" | "report_progress" | 
                 "call_for_vote" | "environment_update" | "affect_agent",
  "target": str | None,           # Target agent, location, or item
  "parameters": dict              # Action-specific parameters
}
```

#### AgentMessage

```python
{
  "content": str,
  "to_target": str,               # Agent ID, room name, or "broadcast"
  "message_type": "direct" | "room" | "broadcast",
  "metadata": dict                # Optional (e.g., context_size)
}
```

#### AgentResponse

```python
{
  "actions": list[AgentAction],
  "message": AgentMessage | None,
  "state_changes": dict,          # Changes to dynamic state
  "reasoning": str                # Internal reasoning (for logging)
}
```

---

## WebSocket Protocol

### Connection

```
ws://localhost:8000/api/ws/{run_id}
```

### Event Types

All WebSocket messages follow this structure:

```json
{
  "event": "event_type",
  "data": {...},
  "timestamp": "2026-01-04T12:00:00Z"
}
```

#### Event: `connected`

Sent immediately upon connection.

```json
{
  "event": "connected",
  "data": {
    "run_id": "660e8400-e29b-41d4-a716-446655440001",
    "status": "running",
    "current_step": 5,
    "max_steps": 100,
    "is_paused": false
  },
  "timestamp": "2026-01-04T12:00:00Z"
}
```

#### Event: `step_started`

Sent when a new simulation step begins.

```json
{
  "event": "step_started",
  "data": {
    "step": 6,
    "world_state": {
      "water_level": 3,
      "temperature": 18
    }
  },
  "timestamp": "2026-01-04T12:06:00Z"
}
```

#### Event: `step_completed`

Sent when a step finishes.

```json
{
  "event": "step_completed",
  "data": {
    "step": 6,
    "messages": [
      {
        "from_agent_id": "agent_001",
        "to_target": "broadcast",
        "content": "Everyone move to Building B!",
        "message_type": "broadcast"
      }
    ],
    "actions": [
      {
        "agent_id": "agent_001",
        "action_type": "move",
        "target": "Building B"
      }
    ],
    "metrics": {
      "avg_health": 8.5,
      "avg_stress": 4.2
    }
  },
  "timestamp": "2026-01-04T12:06:30Z"
}
```

#### Event: `message`

Real-time agent message.

```json
{
  "event": "message",
  "data": {
    "from_agent_id": "agent_001",
    "from_agent_name": "Dr. Sarah Chen",
    "to_target": "agent_002",
    "content": "Are you okay?",
    "message_type": "direct",
    "step": 6
  },
  "timestamp": "2026-01-04T12:06:15Z"
}
```

#### Event: `agent_action`

Agent action notification.

```json
{
  "event": "agent_action",
  "data": {
    "agent_id": "agent_001",
    "agent_name": "Dr. Sarah Chen",
    "action_type": "help",
    "target": "agent_003",
    "step": 6
  },
  "timestamp": "2026-01-04T12:06:20Z"
}
```

#### Event: `state_change`

World or agent state change.

```json
{
  "event": "state_change",
  "data": {
    "type": "world" | "agent",
    "changes": {
      "water_level": 4
    },
    "agent_id": "agent_001"  // Only for agent state changes
  },
  "timestamp": "2026-01-04T12:06:25Z"
}
```

#### Event: `run_status`

Run status update.

```json
{
  "event": "run_status",
  "data": {
    "status": "completed",
    "current_step": 100,
    "metrics": {
      "avg_health": 7.2,
      "avg_stress": 5.8,
      "survival_rate": 0.875
    }
  },
  "timestamp": "2026-01-04T13:00:00Z"
}
```

#### Event: `run_completed`

Simulation finished.

```json
{
  "event": "run_completed",
  "data": {
    "final_step": 100,
    "metrics": {...},
    "evaluation": {
      "cooperation_score": 8.5,
      "ethics_score": 7.2,
      "strategy_score": 6.8,
      "narrative": "The group demonstrated strong cooperation..."
    }
  },
  "timestamp": "2026-01-04T13:00:00Z"
}
```

#### Event: `run_stopped`

Simulation manually stopped.

#### Event: `error`

Error occurred during simulation.

```json
{
  "event": "error",
  "data": {
    "error": "Agent timeout",
    "details": "Agent agent_005 failed to respond within 30s"
  },
  "timestamp": "2026-01-04T12:30:00Z"
}
```

#### Event: `ping` / `pong`

Keep-alive messages (sent every 30 seconds).

### Client Commands

Clients can send commands to the server:

#### Ping

```json
{
  "type": "ping"
}
```

#### Get Status

```json
{
  "type": "get_status"
}
```

---

## Integration Examples

### Python Client Example

```python
import asyncio
import httpx
import websockets
import json

BASE_URL = "http://localhost:8000/api"
WS_URL = "ws://localhost:8000/api"

async def create_and_run_simulation():
    async with httpx.AsyncClient() as client:
        # 1. List scenarios
        response = await client.get(f"{BASE_URL}/scenarios/")
        scenarios = response.json()
        scenario_id = scenarios[0]["id"]
        
        # 2. Create a run
        response = await client.post(
            f"{BASE_URL}/runs/",
            json={
                "scenario_id": scenario_id,
                "seed": 42,
                "max_steps": 50
            }
        )
        run = response.json()
        run_id = run["id"]
        print(f"Created run: {run_id}")
        
        # 3. Start the run
        await client.post(
            f"{BASE_URL}/runs/{run_id}/control",
            json={"action": "start"}
        )
        
        # 4. Monitor via WebSocket
        async with websockets.connect(f"{WS_URL}/ws/{run_id}") as ws:
            async for message in ws:
                data = json.loads(message)
                event_type = data["event"]
                
                if event_type == "message":
                    msg = data["data"]
                    print(f"[{msg['from_agent_name']}]: {msg['content']}")
                
                elif event_type == "run_completed":
                    print("Simulation completed!")
                    print(f"Metrics: {data['data']['metrics']}")
                    break

# Run the example
asyncio.run(create_and_run_simulation())
```

### JavaScript/TypeScript Client Example

```typescript
// Using fetch and WebSocket APIs

const BASE_URL = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/api';

async function createAndRunSimulation() {
  // 1. List scenarios
  const scenariosRes = await fetch(`${BASE_URL}/scenarios/`);
  const scenarios = await scenariosRes.json();
  const scenarioId = scenarios[0].id;
  
  // 2. Create a run
  const runRes = await fetch(`${BASE_URL}/runs/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario_id: scenarioId,
      seed: 42,
      max_steps: 50
    })
  });
  const run = await runRes.json();
  const runId = run.id;
  console.log(`Created run: ${runId}`);
  
  // 3. Start the run
  await fetch(`${BASE_URL}/runs/${runId}/control`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'start' })
  });
  
  // 4. Monitor via WebSocket
  const ws = new WebSocket(`${WS_URL}/ws/${runId}`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.event === 'message') {
      const msg = data.data;
      console.log(`[${msg.from_agent_name}]: ${msg.content}`);
    }
    
    if (data.event === 'run_completed') {
      console.log('Simulation completed!');
      console.log('Metrics:', data.data.metrics);
      ws.close();
    }
  };
}

createAndRunSimulation();
```

### CLI Automation Script

```bash
#!/bin/bash
# run_batch_simulations.sh

SCENARIO="Rising Flood"
NUM_RUNS=10

for i in $(seq 1 $NUM_RUNS); do
  echo "Running simulation $i/$NUM_RUNS..."
  emotionsim run --scenario "$SCENARIO" --max-steps 50 --seed $i --simple >> results_$i.log 2>&1
  echo "Completed simulation $i"
  sleep 2
done

echo "All simulations complete!"
```

### Custom Scenario Creation

```python
from app.schemas.scenario import ScenarioCreate, WorldConfig
from app.schemas.agent import AgentConfig
from app.schemas.persona import Persona
import httpx
import asyncio

async def create_custom_scenario():
    scenario = ScenarioCreate(
        name="Office Fire Drill",
        description="Fire drill in a corporate office building",
        config=WorldConfig(
            name="Corporate Office - Floor 15",
            description="Modern office space with 50 employees",
            max_steps=30,
            tick_delay=1.0,
            initial_state={
                "fire_alarm": False,
                "smoke_level": 0,
                "exits_blocked": []
            },
            dynamics={
                "smoke_increase_rate": 0.1
            }
        ),
        agent_templates=[
            AgentConfig(
                name="Office Manager",
                role="human",
                model_id="gemma2",
                provider="ollama",
                persona=Persona(
                    age=45,
                    sex="female",
                    occupation="Office Manager",
                    backstory="Experienced manager, trained in emergency procedures",
                    big_five={
                        "openness": 0.6,
                        "conscientiousness": 0.9,
                        "extraversion": 0.7,
                        "agreeableness": 0.8,
                        "neuroticism": 0.2
                    },
                    behavioral_modifiers={
                        "risk_tolerance": 0.3,
                        "empathy": 0.8,
                        "leadership": 0.9,
                        "adaptability": 0.7,
                        "stress_resilience": 0.8
                    }
                ),
                goals=["Ensure everyone evacuates safely", "Account for all employees"],
                initial_state={
                    "location": "Office",
                    "health": 10,
                    "stress": 1
                },
                inventory=[]
            )
            # Add more agents...
        ]
    )
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/scenarios/",
            json=scenario.model_dump()
        )
        created = response.json()
        print(f"Created scenario: {created['id']}")
        return created

asyncio.run(create_custom_scenario())
```

---

## Testing and Development

### Using `emotionsim auto` for Automated Testing

The `emotionsim auto` command is ideal for:

1. **Regression Testing**: Run multiple simulations to ensure system stability
2. **Data Collection**: Generate large datasets of simulation runs
3. **Scenario Validation**: Test new scenarios across multiple seeds
4. **Performance Testing**: Monitor system performance under load

**Example Workflow:**

```bash
# Terminal 1: Start auto-runner with specific preset
emotionsim auto --count 20

# Terminal 2: Monitor database growth
watch -n 5 'sqlite3 emotionsim.db "SELECT COUNT(*) FROM runs WHERE status=\"completed\""'

# Terminal 3: Analyze results
emotionsim best --limit 10
```

### Using `emotionsim run` for Development

The `emotionsim run` command is ideal for:

1. **Debugging**: Step through simulations with detailed logging
2. **Scenario Development**: Test new scenarios interactively
3. **Agent Behavior Analysis**: Observe agent decision-making in real-time
4. **UI Development**: Test frontend integration with live data

**Example Workflow:**

```bash
# Run with simple mode for log analysis
emotionsim run --scenario "Rising Flood" --max-steps 10 --simple > debug.log

# Run with Rich UI for interactive debugging
emotionsim run --scenario "Rising Flood" --max-steps 10 --seed 42

# Run with custom tick delay for observation
emotionsim run --scenario "Rising Flood" --tick-delay 2.0
```

### Scenario Generation Workflow

1. **Generate with AI:**
   ```bash
   curl -X POST http://localhost:8000/api/scenarios/generate \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "earthquake in Tokyo with rescue workers",
       "persona_count": 30,
       "save_to_file": true
     }'
   ```

2. **Review Generated File:**
   ```bash
   ls backend/scenarios_generated/
   cat backend/scenarios_generated/earthquake_tokyo_*.json
   ```

3. **Import to Database:**
   ```bash
   curl -X POST http://localhost:8000/api/scenarios/files/earthquake_tokyo_*.json/import
   ```

4. **Test with CLI:**
   ```bash
   emotionsim run --scenario "Earthquake Tokyo"
   ```

### Integration Testing Pattern

```python
import pytest
import httpx
import asyncio

@pytest.mark.asyncio
async def test_full_simulation_lifecycle():
    async with httpx.AsyncClient(base_url="http://localhost:8000/api") as client:
        # Create scenario
        scenario_res = await client.post("/scenarios/", json={...})
        scenario_id = scenario_res.json()["id"]
        
        # Create run
        run_res = await client.post("/runs/", json={
            "scenario_id": scenario_id,
            "max_steps": 5
        })
        run_id = run_res.json()["id"]
        
        # Start run
        await client.post(f"/runs/{run_id}/control", json={"action": "start"})
        
        # Poll until completed
        for _ in range(30):
            status_res = await client.get(f"/runs/{run_id}")
            status = status_res.json()["status"]
            if status == "completed":
                break
            await asyncio.sleep(1)
        
        assert status == "completed"
        
        # Verify messages were created
        messages_res = await client.get(f"/runs/{run_id}/messages")
        messages = messages_res.json()
        assert len(messages) > 0
```

---

## Physical System Architecture

### Simulation Engine Lifecycle

The `SimulationEngine` is the core orchestrator that manages the entire simulation lifecycle:

```
┌─────────────────────────────────────────────────────────────┐
│                    Simulation Lifecycle                      │
├─────────────────────────────────────────────────────────────┤
│  1. INITIALIZATION                                           │
│     ├─ Load scenario configuration                          │
│     ├─ Create agent instances (Human, Environment, etc.)    │
│     ├─ Initialize world state (locations, hazards, etc.)    │
│     ├─ Set up message bus and conversation manager          │
│     └─ Persist initial state to database                    │
│                                                              │
│  2. EXECUTION LOOP (per step)                                │
│     ├─ Reset step counters and failed movement cache        │
│     ├─ Process Environment Agents (create events)           │
│     ├─ Process Human Agents (sequential, randomized)        │
│     │   ├─ Check if agent should respond (personality)      │
│     │   ├─ Build context (world state + messages)           │
│     │   ├─ Call LLM (with streaming)                        │
│     │   ├─ Parse response (actions + messages)              │
│     │   ├─ Execute actions (move, take, use, etc.)          │
│     │   ├─ Send messages (direct, room, broadcast)          │
│     │   └─ Update world state                               │
│     ├─ Cleanup ended conversations                          │
│     ├─ Persist step to database                             │
│     └─ Emit step_completed event                            │
│                                                              │
│  3. COMPLETION                                               │
│     ├─ Calculate final metrics                              │
│     ├─ Update run status to "completed"                     │
│     └─ Emit run_completed event                             │
└─────────────────────────────────────────────────────────────┘
```

### Agent Types and Roles

#### HumanAgent
- **Purpose**: Simulates human behavior in crisis scenarios
- **Personality**: Driven by Big Five traits and behavioral modifiers
- **Decision Making**: Uses LLM to generate contextual responses
- **Response Probability**: Based on personality traits (extraversion, neuroticism)
- **Memory**: Maintains episodic memory and relationship tracking
- **Actions**: move, take, drop, use, interact, search, propose_task, etc.

#### EnvironmentAgent
- **Purpose**: Simulates environmental dynamics (floods, fires, etc.)
- **Behavior**: Updates hazard levels, weather, temperature
- **Actions**: `environment_update`, `affect_agent`
- **Processing**: Always runs first in each step
- **Example**: Increases water level, creates hazard events

#### DesignerAgent
- **Purpose**: Dynamically adjusts scenario difficulty
- **Behavior**: Monitors agent stress and adjusts hazards
- **Goal**: Maintain engagement without overwhelming agents

#### EvaluationAgent
- **Purpose**: Assesses simulation outcomes
- **Metrics**: Survival rate, cooperation level, decision quality
- **Output**: Evaluation report with recommendations

---

## Movement System

### Location Graph

Locations are represented as a graph where each location has:
- **nearby**: List of directly connected locations
- **distance**: Number of steps required to reach (1 = adjacent, 2+ = multi-step travel)
- **items**: Objects available at this location
- **hazard_affected**: Boolean indicating hazard presence

**Example Location:**
```json
{
  "crash_site": {
    "description": "The airplane crash site with debris",
    "nearby": ["forest_edge", "hilltop"],
    "distance": 1,
    "items": ["first_aid_kit", "radio"],
    "hazard_affected": false
  },
  "hilltop": {
    "description": "A hilltop with good visibility",
    "nearby": ["crash_site"],
    "distance": 2,
    "items": [],
    "hazard_affected": false
  }
}
```

### Pathfinding Algorithm

The movement system uses **Breadth-First Search (BFS)** to find the shortest path between locations:

```python
def _find_path(start_loc: str, target_loc: str, locations: dict) -> list[str] | None:
    """
    Find shortest path using BFS.
    Returns: List of locations from start to target, or None if unreachable.
    """
    if start_loc == target_loc:
        return [start_loc]
        
    queue = [(start_loc, [start_loc])]
    visited = {start_loc}
    
    while queue:
        current, path = queue.pop(0)
        nearby = locations.get(current, {}).get("nearby", [])
        
        for neighbor in nearby:
            if neighbor == target_loc:
                return path + [neighbor]
            
            if neighbor not in visited and neighbor in locations:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
                
    return None  # No path found
```

### Multi-Step Movement

When an agent attempts to move to a non-adjacent location:

1. **Pathfinding**: BFS searches for a path (up to 5 steps)
2. **Routing**: If path found, agent moves to the next intermediate location
3. **Event**: `agent_rerouted` event emitted with full path
4. **Failure**: If no path exists, `movement_failed` event emitted

**Example:**
```
Agent at "crash_site" wants to reach "hilltop"
Path found: ["crash_site", "forest_edge", "hilltop"]
→ Agent moves to "forest_edge" this step
→ Next step, agent can move to "hilltop"
```

### Movement Retry Prevention

To prevent agents from repeatedly attempting unreachable locations:

- **Failed Movement Cache**: `_agent_failed_movements: dict[str, set[str]]`
- **Reset**: Cleared at the start of each step
- **Check**: Before attempting movement, check if already failed this step
- **Skip**: If in cache, silently skip to prevent duplicate error events

**Flow:**
```
1. Agent attempts to move to "unreachable_location"
2. Pathfinding fails (no path found)
3. Location added to failed movement cache
4. movement_failed event emitted ONCE
5. Future attempts in same step are silently skipped
6. Cache cleared at next step (agent can try again)
```

### Dynamic Location Creation

If an agent attempts to move to a non-existent location:
- System creates the location dynamically
- Connects it to current location (bidirectional)
- Assigns random distance (1-3 steps)
- Emits `location_created` event

---

## Action System

### Available Actions

#### Movement Actions

**`move`**
- **Target**: Location name (string)
- **Parameters**: Optional metadata
- **Behavior**: 
  - Checks if target is adjacent or finds multi-step path
  - Handles multi-step travel with progress tracking
  - Prevents retry loops with failed movement cache
- **Events**: `agent_moved`, `movement_failed`, `agent_rerouted`, `travel_started`, `agent_travelling`

#### Inventory Actions

**`take`**
- **Target**: Item name
- **Behavior**: Removes item from location, adds to agent inventory
- **Validation**: Item must exist at current location

**`drop`**
- **Target**: Item name
- **Behavior**: Removes item from inventory, adds to current location
- **Validation**: Item must be in agent inventory

**`use`**
- **Target**: Item name
- **Parameters**: Usage context
- **Behavior**: Triggers item-specific effects (e.g., first_aid_kit heals)
- **Validation**: Item must be in inventory

#### Interaction Actions

**`interact`**
- **Target**: Object or agent name
- **Parameters**: Interaction type and details
- **Behavior**: Custom interactions with objects/agents at location

**`search`**
- **Target**: None
- **Behavior**: Reveals hidden items at current location
- **Effect**: Adds discovered items to location

#### Cooperation Actions

**`propose_task`**
- **Parameters**: `{description, priority, required_skills}`
- **Behavior**: Creates shared task in cooperation coordinator
- **Effect**: Other agents can accept and work on task

**`accept_task`**
- **Target**: Task ID
- **Behavior**: Agent commits to working on task
- **Effect**: Task assigned to agent

**`report_progress`**
- **Parameters**: `{task_id, progress, status}`
- **Behavior**: Updates task completion status
- **Effect**: Coordinator tracks progress

**`call_for_vote`**
- **Parameters**: `{proposal, options}`
- **Behavior**: Initiates group decision-making
- **Effect**: Agents can vote on proposal

### Action Processing Flow

```
1. Agent LLM generates response with actions
2. For each action in response.actions:
   a. Validate action type
   b. Execute action handler
   c. If action fails (e.g., movement), skip and continue
   d. Log action to step_actions
   e. Track action for loop detection
3. Process agent message (if any)
4. Update world state
```

**Key Feature**: Failed actions don't block other actions. If movement fails, the agent's other actions still execute.

---

## Memory and Context System

### AgentMemory

Each agent maintains an enhanced memory system:

**Components:**
- **Episodic Memory**: Recent events and interactions (sliding window)
- **Relationship Tracking**: Trust levels and sentiment toward other agents
- **Arrival Context**: How and why agent arrived at current location
- **Conversation History**: Recent conversation content

**Relationship Schema:**
```python
{
  "agent_id": str,
  "agent_name": str,
  "trust_level": int,  # 0-10
  "sentiment": str,    # "positive", "neutral", "negative"
  "interaction_count": int,
  "notes": list[str],
  "last_interaction": datetime
}
```

### Context Building

When an agent's tick is called, the context includes:

1. **World State**: Current hazard level, weather, locations, etc.
2. **Recent Messages**: Direct messages, room messages, broadcasts
3. **Step Actions**: What other agents did this step
4. **Step Events**: Environmental events (hazard increases, etc.)
5. **Cooperation Context**: Shared goals, active tasks
6. **Suggestions**: If agent is stuck in loop
7. **Conversation Context**: If in active conversation

**Context Size**: Tracked in message metadata for monitoring

---

## Conversation System

### Conversation Types

**Location-Based Conversations:**
- Automatically created when multiple agents are at same location
- Turn-based speaking order
- Agents can join/leave as they move

**Direct Conversations:**
- Between specific agents
- Can span locations

### Turn Management

```python
class Conversation:
    participants: list[str]
    current_speaker_index: int
    max_turns_per_agent: int
    
    def get_next_speaker(self) -> str:
        """Round-robin turn assignment"""
        return participants[current_speaker_index % len(participants)]
    
    def advance_turn(self, spoke: bool):
        """Move to next speaker"""
        if spoke:
            current_speaker_index += 1
```

### Conversation Lifecycle

```
1. CREATED: Agents at same location trigger conversation
2. ACTIVE: Agents take turns speaking
3. PAUSED: No activity for N turns
4. ENDED: All agents left location or max turns reached
5. CLEANUP: Removed from active conversations
```

---

## Cooperation System

### Shared Goals

Goals that multiple agents work toward:
- Extracted from agent personas
- Tracked by `CooperationCoordinator`
- Visible to all agents in context

### Task Coordination

**Task Schema:**
```python
{
  "id": str,
  "description": str,
  "priority": int,  # 1-10
  "status": "proposed" | "in_progress" | "completed",
  "assigned_agents": list[str],
  "required_skills": list[str],
  "progress": int  # 0-100
}
```

**Workflow:**
1. Agent proposes task
2. Other agents accept task
3. Agents report progress
4. Task marked completed

### Loop Detection

Prevents agents from getting stuck:
- Tracks repeated actions (same action + target)
- Tracks repeated conversation topics
- Provides suggestions when loop detected

---

## WebSocket Streaming Protocol

### Token Streaming

During agent LLM generation, tokens are streamed in real-time:

**Event:** `stream_token`
```json
{
  "event": "stream_token",
  "data": {
    "agent_id": "agent_001",
    "token": "I think we should"
  }
}
```

**Client Implementation:**
```python
async with websockets.connect(f"ws://localhost:8000/api/ws/{run_id}") as ws:
    async for message in ws:
        event = json.loads(message)
        
        if event["event"] == "stream_token":
            agent_id = event["data"]["agent_id"]
            token = event["data"]["token"]
            # Update UI with streaming text
```

### Event Ordering

Events are emitted in this order per step:

1. `step_started`
2. `stream_token` (multiple, during LLM generation)
3. `message` (agent messages)
4. `agent_moved` / `movement_failed` (movement events)
5. `agent_error` (if errors occur)
6. `step_completed`

---

## Integration Examples

### Creating a Custom Scenario

```python
from app.models.scenario import Scenario
from app.schemas.persona import Persona

# Define custom scenario
scenario = Scenario(
    name="Zombie Outbreak",
    description="Survival scenario in shopping mall",
    config={
        "name": "Shopping Mall",
        "description": "Large mall with multiple floors",
        "max_steps": 50,
        "tick_delay": 1.0,
        "initial_state": {
            "hazard_level": 3,
            "zombie_count": 10,
            "time_of_day": "night"
        },
        "locations": {
            "food_court": {
                "description": "Central food court",
                "nearby": ["electronics", "clothing"],
                "distance": 1,
                "items": ["canned_food", "water"],
                "hazard_affected": False
            },
            "electronics": {
                "description": "Electronics store",
                "nearby": ["food_court", "exit"],
                "distance": 1,
                "items": ["radio", "flashlight"],
                "hazard_affected": True
            }
        }
    },
    agent_templates=[
        {
            "name": "Security Guard",
            "role": "human",
            "model_id": "gemma2",
            "provider": "ollama",
            "persona": {
                "age": 45,
                "sex": "male",
                "occupation": "Security",
                "backstory": "Former military, trained in crisis response",
                "big_five": {
                    "openness": 0.5,
                    "conscientiousness": 0.9,
                    "extraversion": 0.6,
                    "agreeableness": 0.7,
                    "neuroticism": 0.3
                },
                "behavioral_modifiers": {
                    "risk_tolerance": 0.7,
                    "empathy": 0.6,
                    "leadership": 0.9,
                    "adaptability": 0.7,
                    "stress_resilience": 0.8
                }
            },
            "goals": ["Protect civilians", "Secure exits"],
            "initial_state": {
                "location": "food_court",
                "health": 10,
                "stress": 2
            },
            "inventory": [
                {"name": "radio", "description": "Two-way radio"},
                {"name": "flashlight", "description": "Heavy-duty flashlight"}
            ]
        }
    ]
)

# Save to database
async with AsyncSession(engine) as session:
    session.add(scenario)
    await session.commit()
```

### Running Simulation Programmatically

```python
from app.simulation.engine import SimulationEngine
from app.core.database import get_session

async def run_custom_simulation():
    # Create run
    async with get_session() as session:
        run = Run(
            scenario_id=scenario.id,
            max_steps=50,
            seed=42
        )
        session.add(run)
        await session.commit()
        
        # Initialize engine
        engine = SimulationEngine(
            run_id=run.id,
            db_session=session,
            on_event=lambda event_type, data: print(f"{event_type}: {data}")
        )
        
        # Load scenario
        await engine.initialize(scenario.to_dict())
        
        # Start simulation
        await engine.start()
```

### Custom Agent Implementation

```python
from app.agents.base import Agent
from app.schemas.agent import AgentResponse, AgentAction, AgentMessage

class CustomAgent(Agent):
    def get_system_prompt(self) -> str:
        return """You are a custom agent with special abilities.
        Your goal is to assist humans in crisis situations."""
    
    def build_context(
        self,
        world_state: dict,
        messages: list[dict],
        step_actions: list[dict] | None = None,
        step_messages: list[dict] | None = None,
        step_events: list[str] | None = None,
    ) -> str:
        # Build custom context
        context = f"Current hazard level: {world_state.get('hazard_level', 0)}\n"
        context += f"Your location: {self.dynamic_state.get('location', 'unknown')}\n"
        
        if messages:
            context += "\nRecent messages:\n"
            for msg in messages[-5:]:
                context += f"- {msg.get('from_agent_name')}: {msg.get('content')}\n"
        
        return context
```

---

## Appendix

### Environment Variables

```bash
# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_DEFAULT_MODEL=gemma2

# Database
DATABASE_URL=sqlite+aiosqlite:///./emotionsim.db

# Server
HOST=0.0.0.0
PORT=8000
```

### Default Models

- **Human Agents**: `gemma2` (Ollama)
- **Environment Agent**: `gemma2` (Ollama)
- **Designer Agent**: `gemma2` (Ollama)
- **Evaluator Agent**: `gemma2` (Ollama)

### Troubleshooting

**Issue: WebSocket connection refused**
- Ensure backend is running: `python -m app.main`
- Check firewall settings
- Verify URL: `ws://localhost:8000/api/ws/{run_id}`

**Issue: LLM timeout**
- Increase timeout in `app/llm/client.py`
- Check Ollama is running: `ollama serve`
- Verify model is pulled: `ollama pull gemma2`

**Issue: Database locked**
- Close all connections to `emotionsim.db`
- Restart backend server
- Check for zombie processes: `ps aux | grep emotionsim`

---

**For more information, see:**
- [README.md](README.md) - Quick start and overview
- [additional_context.md](additional_context.md) - Design philosophy and architecture details
- GitHub Issues - Bug reports and feature requests
