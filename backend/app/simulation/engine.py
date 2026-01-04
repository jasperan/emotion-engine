"""Simulation Engine - main orchestrator for runs"""
import asyncio
import random
from datetime import datetime
from typing import Any, Callable
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import Agent, EnvironmentAgent, HumanAgent, DesignerAgent, EvaluationAgent
from app.simulation.message_bus import MessageBus
from app.simulation.conversation import ConversationManager, Conversation, ConversationState
from app.models.run import Run, RunStatus
from app.models.agent import AgentModel
from app.models.step import Step
from app.models.message import Message, MessageType
from app.schemas.persona import Persona


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
    Manages agent lifecycle, tick loop, conversations, and state persistence.
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
        
        # Conversation management
        self.conversation_manager = ConversationManager()
        
        # Real-time agent locations (updated during steps)
        self._agent_locations: dict[str, str] = {}
        
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
            self.message_bus.register_agent(agent.id, agent.name)
            
            # Initialize agent location in conversation manager
            agent_location = agent.dynamic_state.get("location", "unknown")
            self._agent_locations[agent.id] = agent_location
            self.conversation_manager.update_agent_location(agent.id, agent_location)
            
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
        """Execute a single simulation step with multi-turn conversations"""
        self.current_step += 1
        self.world_state["current_step"] = self.current_step
        
        step_actions = []
        step_messages = []
        
        # Reset conversation counters for this step
        self.conversation_manager.reset_step_counters()
        
        # Build current agent states for world state
        self._update_agents_in_world_state()
        
        # Phase 1: Environment agent updates (if any)
        await self._process_environment_agents(step_actions, step_messages)
        
        # Phase 2: Multi-turn conversation loop
        await self._process_conversations(step_actions, step_messages)
        
        # Phase 3: Cleanup ended conversations
        self.conversation_manager.cleanup_ended_conversations()
        
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
            "conversations": [c.to_dict() for c in self.conversation_manager.get_all_active_conversations()],
        })
    
    def _update_agents_in_world_state(self) -> None:
        """Update world state with current agent information"""
        agents_state = {}
        for agent_id, agent in self.agents.items():
            location = self._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
            agents_state[agent_id] = {
                "name": agent.name,
                "role": agent.role,
                "location": location,
                **agent.dynamic_state,
            }
        self.world_state["agents"] = agents_state
    
    async def _process_environment_agents(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
    ) -> None:
        """Process environment agent updates"""
        for agent_id, agent in self.agents.items():
            if agent.role != "environment":
                continue
            
            messages = self.message_bus.get_messages(agent_id)
            
            try:
                response = await agent.tick(self.world_state.copy(), messages)
                
                for action in response.actions:
                    step_actions.append({
                        "agent_id": agent_id,
                        "agent_name": agent.name,
                        **action.model_dump(),
                    })
                    
                    if action.action_type == "environment_update":
                        self._apply_environment_update(action.parameters)
                
                if response.message:
                    msg = response.message
                    stored_msg = self.message_bus.broadcast(
                        agent_id, msg.content, self.current_step
                    )
                    step_messages.append(stored_msg)
                    await self._persist_message(agent_id, msg)
                    
            except Exception as e:
                self.on_event("agent_error", {
                    "agent_id": agent_id,
                    "error": str(e),
                    "step": self.current_step,
                })
    
    async def _process_conversations(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
    ) -> None:
        """Process multi-turn conversations until they conclude"""
        max_conversation_rounds = 10  # Safety limit
        round_count = 0
        
        while round_count < max_conversation_rounds:
            round_count += 1
            
            # Get all conversations that need processing
            active_conversations = self.conversation_manager.get_conversations_needing_turns()
            
            if not active_conversations:
                break
            
            # Process each conversation
            any_activity = False
            
            for conv in active_conversations:
                activity = await self._process_single_conversation(
                    conv, step_actions, step_messages
                )
                any_activity = any_activity or activity
            
            # If no conversation had activity, we're done
            if not any_activity:
                break
    
    async def _process_single_conversation(
        self,
        conversation: Conversation,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
    ) -> bool:
        """Process a single conversation turn. Returns True if there was activity."""
        if not conversation.should_continue():
            return False
        
        # Get the next speaker
        speaker_id = conversation.get_next_speaker()
        if not speaker_id or speaker_id not in self.agents:
            conversation.advance_turn(spoke=False)
            return False
        
        agent = self.agents[speaker_id]
        
        # Skip non-human agents in conversations (they're handled separately)
        if agent.role != "human":
            conversation.advance_turn(spoke=False)
            return False
        
        # Build context for this agent including conversation history
        conversation_context = conversation.get_context_for_agent(speaker_id)
        pending_messages = self.message_bus.get_messages(speaker_id)
        
        # Combine conversation history with any pending messages
        all_messages = conversation_context + pending_messages
        
        # Add conversation metadata to world state
        conv_world_state = self.world_state.copy()
        conv_world_state["active_conversation"] = {
            "id": conversation.id,
            "location": conversation.location,
            "participants": [
                self.agents[pid].name if pid in self.agents else pid
                for pid in conversation.participants
            ],
            "is_my_turn": True,
        }
        
        try:
            response = await agent.tick(conv_world_state, all_messages)
            
            # Process actions (including movement)
            for action in response.actions:
                step_actions.append({
                    "agent_id": speaker_id,
                    "agent_name": agent.name,
                    **action.model_dump(),
                })
                
                # Handle movement within the step
                if action.action_type == "move":
                    await self._handle_movement(speaker_id, action.target, action.parameters)
            
            # Process message
            if response.message and response.message.content.strip():
                msg = response.message
                
                # Send to conversation participants
                stored_msg = self.message_bus.send_to_conversation(
                    from_agent_id=speaker_id,
                    conversation_id=conversation.id,
                    participant_ids=conversation.participants,
                    content=msg.content,
                    step_index=self.current_step,
                    location=conversation.location,
                )
                
                # Add to conversation history
                conversation.add_message(stored_msg)
                step_messages.append(stored_msg)
                
                # Persist to database
                await self._persist_message(speaker_id, msg, conversation.id)
                
                conversation.advance_turn(spoke=True)
                return True
            else:
                # Agent chose not to speak
                conversation.advance_turn(spoke=False)
                return False
                
        except Exception as e:
            self.on_event("agent_error", {
                "agent_id": speaker_id,
                "error": str(e),
                "step": self.current_step,
                "conversation_id": conversation.id,
            })
            conversation.advance_turn(spoke=False)
            return False
    
    async def _handle_movement(
        self,
        agent_id: str,
        target_location: str | None,
        parameters: dict[str, Any],
    ) -> None:
        """Handle agent movement between locations"""
        if not target_location:
            return
        
        current_location = self._agent_locations.get(agent_id, "unknown")
        
        # Validate movement (target must be nearby)
        locations = self.world_state.get("locations", {})
        current_loc_data = locations.get(current_location, {})
        nearby = current_loc_data.get("nearby", [])
        
        if target_location not in nearby and target_location != current_location:
            # Invalid movement - location not reachable
            self.on_event("movement_failed", {
                "agent_id": agent_id,
                "from": current_location,
                "to": target_location,
                "reason": "Location not reachable",
            })
            return
        
        # Update location
        self._agent_locations[agent_id] = target_location
        
        # Update agent's dynamic state
        agent = self.agents.get(agent_id)
        if agent:
            agent.dynamic_state["location"] = target_location
        
        # Update conversation manager (handles join/leave of location conversations)
        self.conversation_manager.update_agent_location(agent_id, target_location)
        
        # Update world state
        self._update_agents_in_world_state()
        
        self.on_event("agent_moved", {
            "agent_id": agent_id,
            "from": current_location,
            "to": target_location,
            "step": self.current_step,
        })
    
    async def _persist_message(
        self,
        agent_id: str,
        msg: Any,
        conversation_id: str | None = None,
    ) -> None:
        """Persist a message to the database"""
        # Determine message type
        msg_type = msg.message_type if hasattr(msg, 'message_type') else "broadcast"
        if conversation_id:
            msg_type = "conversation"
        
        # Map to MessageType enum
        try:
            db_msg_type = MessageType(msg_type)
        except ValueError:
            db_msg_type = MessageType.BROADCAST
        
        db_message = Message(
            run_id=self.run_id,
            from_agent_id=agent_id,
            to_target=conversation_id or msg.to_target,
            message_type=db_msg_type,
            content=msg.content,
            step_index=self.current_step,
            metadata={"conversation_id": conversation_id} if conversation_id else {},
        )
        self.db.add(db_message)
    
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
            "active_conversations": len(self.conversation_manager.get_all_active_conversations()),
        }
    
    def start_explicit_conversation(
        self,
        initiator_id: str,
        target_agent_ids: list[str],
    ) -> str:
        """Start an explicit conversation between specific agents"""
        initiator_location = self._agent_locations.get(initiator_id)
        return self.conversation_manager.start_explicit_conversation(
            initiator_id, target_agent_ids, initiator_location
        )
    
    def get_agents_at_location(self, location: str) -> list[str]:
        """Get all agent IDs at a specific location"""
        return [
            agent_id
            for agent_id, loc in self._agent_locations.items()
            if loc == location
        ]
    
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
