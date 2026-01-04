"""Simulation Engine - main orchestrator for runs"""
import asyncio
import random
from datetime import datetime
from typing import Any, Callable
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents import Agent, EnvironmentAgent, HumanAgent, DesignerAgent, EvaluationAgent
from app.simulation.message_bus import MessageBus
from app.models.run import Run, RunStatus
from app.models.agent import AgentModel
from app.models.step import Step
from app.models.message import Message, MessageType
from app.schemas.persona import Persona
from app.schemas.agent import AgentConfig


class SimulationState(str, Enum):
    """Current state of the simulation engine"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETING = "completing"
    ERROR = "error"


class SimulationEngine:
    """
    Main simulation engine that orchestrates runs.
    Manages agent lifecycle, tick loop, and state persistence.
    """
    
    def __init__(
        self,
        run_id: str,
        db_session: AsyncSession,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        self.run_id = run_id
        self.db = db_session
        self.on_event = on_event or (lambda t, d: None)
        
        self.state = SimulationState.IDLE
        self.current_step = 0
        self.max_steps = 100
        self.tick_delay = 0.5
        
        # World state
        self.world_state: dict[str, Any] = {
            "hazard_level": 0,
            "locations": {},
            "resources": [],
            "events": [],
        }
        
        # Agents
        self.agents: dict[str, Agent] = {}
        self.message_bus = MessageBus()
        
        # Control
        self._stop_requested = False
        self._pause_requested = False
        self._step_event = asyncio.Event()
    
    async def initialize(self, scenario_config: dict[str, Any]) -> None:
        """Initialize the simulation from scenario config"""
        self.state = SimulationState.INITIALIZING
        
        # Set world parameters
        world_config = scenario_config.get("config", {})
        self.max_steps = world_config.get("max_steps", 100)
        self.tick_delay = world_config.get("tick_delay", 0.5)
        
        self.world_state.update(world_config.get("initial_state", {}))
        
        # Initialize seed if provided
        seed = scenario_config.get("seed")
        if seed is not None:
            random.seed(seed)
        
        # Create agents from templates
        agent_templates = scenario_config.get("agent_templates", [])
        for template in agent_templates:
            agent = self._create_agent(template)
            self.agents[agent.id] = agent
            self.message_bus.register_agent(agent.id)
            
            # Persist agent to database
            agent_model = AgentModel(
                id=agent.id,
                run_id=self.run_id,
                role=agent.role,
                name=agent.name,
                model_id=agent.model_id,
                provider=agent.provider,
                persona=agent.to_dict().get("persona", {}),
                dynamic_state=agent.dynamic_state,
            )
            self.db.add(agent_model)
        
        await self.db.commit()
        
        self.state = SimulationState.IDLE
        self.on_event("initialized", {"agent_count": len(self.agents)})
    
    def _create_agent(self, config: dict[str, Any]) -> Agent:
        """Create an agent from configuration"""
        role = config.get("role", "human")
        
        if role == "environment":
            return EnvironmentAgent(
                name=config.get("name", "Environment"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
                environment_type=config.get("environment_type", "flood"),
                dynamics_config=config.get("dynamics_config"),
            )
        elif role == "designer":
            return DesignerAgent(
                name=config.get("name", "Director"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
                scenario_goals=config.get("goals"),
            )
        elif role == "evaluator":
            return EvaluationAgent(
                name=config.get("name", "Evaluator"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
            )
        else:  # human
            persona_data = config.get("persona", {})
            persona = Persona(**persona_data) if persona_data else None
            
            return HumanAgent(
                name=config.get("name", "Human"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
                persona=persona,
                goals=config.get("goals"),
            )
    
    async def start(self) -> None:
        """Start the simulation run"""
        if self.state not in (SimulationState.IDLE, SimulationState.PAUSED):
            return
        
        self.state = SimulationState.RUNNING
        self._stop_requested = False
        self._pause_requested = False
        
        # Update run status in DB
        run = await self.db.get(Run, self.run_id)
        if run:
            run.status = RunStatus.RUNNING
            run.started_at = run.started_at or datetime.utcnow()
            await self.db.commit()
        
        self.on_event("run_started", {"step": self.current_step})
        
        # Main simulation loop
        await self._run_loop()
    
    async def _run_loop(self) -> None:
        """Main simulation loop"""
        while (
            self.current_step < self.max_steps
            and not self._stop_requested
            and self.state == SimulationState.RUNNING
        ):
            if self._pause_requested:
                self.state = SimulationState.PAUSED
                self._pause_requested = False
                self.on_event("run_paused", {"step": self.current_step})
                return
            
            await self._execute_step()
            
            # Wait between ticks
            await asyncio.sleep(self.tick_delay)
        
        # Run completed
        if not self._stop_requested:
            await self._complete_run()
    
    async def _execute_step(self) -> None:
        """Execute a single simulation step"""
        self.current_step += 1
        self.world_state["current_step"] = self.current_step
        
        step_actions = []
        step_messages = []
        
        # Build current agent states for world state
        agents_state = {}
        for agent_id, agent in self.agents.items():
            agents_state[agent_id] = {
                "name": agent.name,
                "role": agent.role,
                **agent.dynamic_state,
            }
        self.world_state["agents"] = agents_state
        
        # Execute each agent's tick
        for agent_id, agent in self.agents.items():
            # Get messages for this agent
            messages = self.message_bus.get_messages(agent_id)
            
            try:
                # Execute agent tick
                response = await agent.tick(self.world_state.copy(), messages)
                
                # Process actions
                for action in response.actions:
                    step_actions.append({
                        "agent_id": agent_id,
                        "agent_name": agent.name,
                        **action.model_dump(),
                    })
                    
                    # Handle environment updates
                    if action.action_type == "environment_update":
                        self._apply_environment_update(action.parameters)
                
                # Process message
                if response.message:
                    msg = response.message
                    if msg.message_type == "broadcast":
                        stored_msg = self.message_bus.broadcast(
                            agent_id, msg.content, self.current_step
                        )
                    elif msg.message_type == "room":
                        stored_msg = self.message_bus.send_to_room(
                            agent_id, msg.to_target, msg.content, self.current_step
                        )
                    else:
                        stored_msg = self.message_bus.send_direct(
                            agent_id, msg.to_target, msg.content, self.current_step
                        )
                    
                    step_messages.append(stored_msg)
                    
                    # Persist message to database
                    db_message = Message(
                        run_id=self.run_id,
                        from_agent_id=agent_id,
                        to_target=msg.to_target,
                        message_type=MessageType(msg.message_type),
                        content=msg.content,
                        step_index=self.current_step,
                    )
                    self.db.add(db_message)
                
                # Update agent state in DB
                agent_model = await self.db.get(AgentModel, agent_id)
                if agent_model:
                    agent_model.dynamic_state = agent.dynamic_state
            
            except Exception as e:
                self.on_event("agent_error", {
                    "agent_id": agent_id,
                    "error": str(e),
                    "step": self.current_step,
                })
        
        # Persist step
        step = Step(
            run_id=self.run_id,
            step_index=self.current_step,
            state_snapshot=self.world_state.copy(),
            actions=step_actions,
            step_metrics=self._compute_step_metrics(),
        )
        self.db.add(step)
        
        # Update run
        run = await self.db.get(Run, self.run_id)
        if run:
            run.current_step = self.current_step
            run.world_state = self.world_state.copy()
        
        await self.db.commit()
        
        # Emit step event
        self.on_event("step_completed", {
            "step": self.current_step,
            "actions": step_actions,
            "messages": step_messages,
            "world_state": self.world_state,
        })
    
    def _apply_environment_update(self, params: dict[str, Any]) -> None:
        """Apply environment agent updates to world state"""
        if "hazard_level" in params:
            self.world_state["hazard_level"] = params["hazard_level"]
        
        if "events" in params:
            self.world_state.setdefault("events", []).extend(params["events"])
        
        if "new_resources" in params:
            self.world_state.setdefault("resources", []).extend(params["new_resources"])
        
        if "affected_locations" in params:
            for loc in params["affected_locations"]:
                self.world_state.setdefault("locations", {})[loc] = {
                    "hazard_affected": True,
                }
    
    def _compute_step_metrics(self) -> dict[str, Any]:
        """Compute metrics for the current step"""
        total_health = 0
        total_stress = 0
        human_count = 0
        
        for agent in self.agents.values():
            if agent.role == "human":
                human_count += 1
                total_health += agent.dynamic_state.get("health", 10)
                total_stress += agent.dynamic_state.get("stress_level", 5)
        
        return {
            "avg_health": total_health / max(human_count, 1),
            "avg_stress": total_stress / max(human_count, 1),
            "hazard_level": self.world_state.get("hazard_level", 0),
            "message_count": len(self.message_bus._message_history),
        }
    
    async def pause(self) -> None:
        """Pause the simulation"""
        if self.state == SimulationState.RUNNING:
            self._pause_requested = True
    
    async def resume(self) -> None:
        """Resume a paused simulation"""
        if self.state == SimulationState.PAUSED:
            await self.start()
    
    async def stop(self) -> None:
        """Stop the simulation"""
        self._stop_requested = True
        
        run = await self.db.get(Run, self.run_id)
        if run:
            run.status = RunStatus.CANCELLED
            run.completed_at = datetime.utcnow()
            await self.db.commit()
        
        self.state = SimulationState.IDLE
        self.on_event("run_stopped", {"step": self.current_step})
    
    async def step_once(self) -> None:
        """Execute a single step (manual stepping)"""
        if self.state in (SimulationState.IDLE, SimulationState.PAUSED):
            await self._execute_step()
    
    async def _complete_run(self) -> None:
        """Complete the run and trigger evaluation"""
        self.state = SimulationState.COMPLETING
        
        # Run evaluation
        evaluator = EvaluationAgent()
        
        run_summary = {
            "total_steps": self.current_step,
            "hazard_level": self.world_state.get("hazard_level", 0),
            "outcome": "completed",
            "agents_summary": {},
        }
        
        for agent_id, agent in self.agents.items():
            run_summary["agents_summary"][agent.name] = {
                **agent.dynamic_state,
                "action_count": len([
                    m for m in agent.memory if m.get("type") == "action"
                ]),
                "message_count": len([
                    m for m in agent.memory if m.get("type") == "message"
                ]),
            }
        
        all_messages = self.message_bus.get_history()
        
        try:
            evaluation = await evaluator.evaluate_run(run_summary, all_messages)
        except Exception as e:
            evaluation = {"error": str(e)}
        
        # Update run in DB
        run = await self.db.get(Run, self.run_id)
        if run:
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            run.metrics = self._compute_step_metrics()
            run.evaluation = evaluation
            await self.db.commit()
        
        self.state = SimulationState.IDLE
        self.on_event("run_completed", {
            "step": self.current_step,
            "evaluation": evaluation,
        })

