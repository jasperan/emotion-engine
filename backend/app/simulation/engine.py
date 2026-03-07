"""Simulation Engine - main orchestrator for runs"""
import asyncio
import logging
import random
from datetime import datetime
from typing import Any, Callable, Awaitable
from enum import Enum

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import Agent, EnvironmentAgent, HumanAgent, DesignerAgent, EvaluationAgent
from app.llm.router import LLMRouter, configure_model_routing
from app.simulation.message_bus import MessageBus
from app.simulation.conversation import ConversationManager, Conversation, ConversationState
from app.simulation.agent_supervisor import AgentSupervisor
from app.simulation.negotiation import NegotiationManager, ProposalState
from app.simulation.trust_network import TrustNetwork
from app.simulation.world_state_diff import WorldStateDiffTracker
from app.simulation.conversation_outcomes import ConversationOutcomeExtractor
from app.models.run import Run, RunStatus
from app.models.agent import AgentModel
from app.models.step import Step
from app.models.message import Message, MessageType
from app.schemas.persona import Persona
from app.acp.registry import AgentRegistry
from app.acp.coordination import CoordinationController
from app.agents.voting_mixin import GroupDecisionMixin

logger = logging.getLogger(__name__)


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
        
        # Cooperation coordinator
        from app.agents.coordinator import CooperationCoordinator
        self.coordinator = CooperationCoordinator()
        
        # Real-time agent locations (updated during steps)
        self._agent_locations: dict[str, str] = {}

        # Failed movement tracking (reset each step to prevent retry loops)
        self._agent_failed_movements: dict[str, set[str]] = {}

        # Hop distance cache (cleared each step)
        self._hop_cache: dict[tuple[str, str], int] = {}

        # Control
        self._stop_requested = False
        self._pause_requested = False
        self._step_event = asyncio.Event()

        # ACP components
        self.acp_registry = AgentRegistry()
        self.acp_coordination = CoordinationController(level="moderate")
        self.group_voting = GroupDecisionMixin()

        # === NEW: Symphony/Pi-inspired systems ===
        from app.core.config import get_settings
        settings = get_settings()

        # L1: Agent Supervisor (Symphony-inspired fault isolation)
        self.supervisor = AgentSupervisor(
            tick_timeout=settings.agent_tick_timeout,
            max_backoff=settings.agent_max_backoff,
            max_consecutive_failures=settings.agent_max_consecutive_failures,
        )

        # L2: Negotiation Manager (Symphony state-machine for proposals)
        self.negotiation = NegotiationManager(
            default_expiry_steps=settings.negotiation_default_expiry_steps,
        )

        # L5: Trust Network (bilateral trust signals)
        self.trust_network = TrustNetwork()

        # L6: Conversation Outcome Extractor
        self.outcome_extractor = ConversationOutcomeExtractor()

        # L8: World State Diff Tracker (Pi hash-anchor inspired)
        self.diff_tracker = WorldStateDiffTracker()

        # L9: Configure per-agent-type model routing
        configure_model_routing({
            "environment": settings.model_route_environment or settings.ollama_fallback_model,
            "reactive": settings.model_route_reactive or settings.ollama_fallback_model,
        })

        # SceneDirector: groups co-located human agents into dramatic scenes
        from app.simulation.scene_director import SceneDirector
        self.scene_director = SceneDirector(max_turns=settings.scene_max_turns)
        self.scene_mode = settings.scene_mode

    async def load_from_db(self) -> None:
        """Load simulation state from database for resumption"""
        self.state = SimulationState.INITIALIZING
        
        # Get run record
        run = await self.db.get(Run, self.run_id)
        if not run:
            raise ValueError(f"Run {self.run_id} not found in database")
            
        # Restore basic state
        self.current_step = run.current_step
        self.max_steps = run.max_steps
        self.world_state = run.world_state or {
            "hazard_level": 0,
            "locations": {},
            "resources": [],
            "events": [],
        }
        
        # Restore agents
        result = await self.db.execute(
            select(AgentModel).where(AgentModel.run_id == self.run_id)
        )
        agent_models = result.scalars().all()
        
        for model in agent_models:
            # Recreate agent instance based on role
            config = {
                "name": model.name,
                "role": model.role,
                "model_id": model.model_id or "qwen3.5:27b",
                "provider": model.provider or "ollama",
                "persona": model.persona,
                "goals": model.persona.get("goals", []) if model.persona else [],
            }
            
            agent = self._create_agent(config)
            agent.id = model.id
            agent.dynamic_state = model.dynamic_state or {}
            
            # Restore memory if available
            if hasattr(model, 'memory_snapshot') and model.memory_snapshot:
                agent.restore_memory(model.memory_snapshot)
                
            self.agents[agent.id] = agent
            self.message_bus.register_agent(agent.id, agent.name)
            self.acp_registry.register(agent.get_acp_identity())
            self.supervisor.register_agent(agent.id, agent.name)

            # Restore location tracking
            location = agent.dynamic_state.get("location", "unknown")
            self._agent_locations[agent.id] = location
            self.conversation_manager.update_agent_location(agent.id, location)
            self.message_bus.join_room(agent.id, location)
            
        # Restore message history to message bus for context
        result = await self.db.execute(
            select(Message)
            .where(Message.run_id == self.run_id)
            .order_by(Message.timestamp)
        )
        db_messages = result.scalars().all()
        
        for msg in db_messages:
            # Reconstruct the message object as expected by message bus
            bus_msg = {
                "id": msg.id,
                "from_agent": msg.from_agent_id,
                "from_agent_name": self.message_bus.get_agent_name(msg.from_agent_id) if msg.from_agent_id else "System",
                "to_target": msg.to_target,
                "message_type": msg.message_type.value if hasattr(msg.message_type, 'value') else msg.message_type,
                "content": msg.content,
                "step_index": msg.step_index,
                "metadata": msg.metadata or {},
                "timestamp": msg.timestamp.isoformat(),
            }
            self.message_bus._message_history.append(bus_msg)
            
            # If it was a conversation message, add to conversation history
            if "conversation_id" in bus_msg["metadata"]:
                conv_id = bus_msg["metadata"]["conversation_id"]
                self.message_bus._conversation_messages[conv_id].append(bus_msg)
                
        # Initialize coordinator with shared goals
        all_goals = set()
        for agent in self.agents.values():
            if agent.role == "human" and hasattr(agent, 'goals'):
                all_goals.update(agent.goals)
        
        for goal in all_goals:
            self.coordinator.add_shared_goal(goal)
            
        # Restore coordinator context
        self.world_state["shared_goals"] = self.coordinator.shared_goals
        self.world_state["cooperation"] = self.coordinator.get_cooperation_context()
        
        self.state = SimulationState.IDLE
        self.on_event("resumed", {"step": self.current_step, "agent_count": len(self.agents)})

    async def initialize(self, scenario_config: dict[str, Any]) -> None:
        """Initialize the simulation from scenario config"""
        self.state = SimulationState.INITIALIZING
        
        # Set world parameters
        world_config = scenario_config.get("config", {})
        # Default to None (infinite) unless explicitly set
        self.max_steps = world_config.get("max_steps", None)
        self.tick_delay = world_config.get("tick_delay", 0.5)
        
        
        self.world_state.update(world_config.get("initial_state", {}))
        self.world_state["objects"] = world_config.get("objects", {})
        
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
            self.acp_registry.register(agent.get_acp_identity())
            self.supervisor.register_agent(agent.id, agent.name)

            # Initialize agent location in conversation manager
            agent_location = agent.dynamic_state.get("location", "unknown")
            self._agent_locations[agent.id] = agent_location
            self.conversation_manager.update_agent_location(agent.id, agent_location)
            # Subscribe agent to location room for room messages
            self.message_bus.join_room(agent.id, agent_location)
            
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
        
        # Initialize shared goals from agent goals
        all_goals = set()
        for agent in self.agents.values():
            if agent.role == "human" and hasattr(agent, 'goals'):
                all_goals.update(agent.goals)
        
        for goal in all_goals:
            self.coordinator.add_shared_goal(goal)
        
        # Add cooperation context to world state
        self.world_state["shared_goals"] = self.coordinator.shared_goals
        self.world_state["cooperation"] = self.coordinator.get_cooperation_context()
        
        # Update agents in world state for initial display
        self._update_agents_in_world_state()
        
        self.state = SimulationState.IDLE
        self.on_event("initialized", {
            "agent_count": len(self.agents),
            "world_state": self.world_state,
            "conversations": [],
        })
    
    def _create_agent(self, config: dict[str, Any]) -> Agent:
        """Create an agent from configuration"""
        role = config.get("role", "human")
        
        if role == "environment":
            return EnvironmentAgent(
                name=config.get("name", "Environment"),
                model_id=config.get("model_id", "qwen3.5:27b"),
                provider=config.get("provider", "ollama"),
                environment_type=config.get("environment_type", "flood"),
                dynamics_config=config.get("dynamics_config"),
            )
        elif role == "designer":
            return DesignerAgent(
                name=config.get("name", "Director"),
                model_id=config.get("model_id", "qwen3.5:27b"),
                provider=config.get("provider", "ollama"),
                scenario_goals=config.get("goals"),
            )
        elif role == "evaluator":
            return EvaluationAgent(
                name=config.get("name", "Evaluator"),
                model_id=config.get("model_id", "qwen3.5:27b"),
                provider=config.get("provider", "ollama"),
            )
        else:  # human
            persona_data = config.get("persona", {})
            if persona_data and "inventory" not in persona_data and config.get("inventory"):
                # Update persona with initial inventory if provided in agent config
                persona_data["inventory"] = [
                    item.get("name") if isinstance(item, dict) else item.name 
                    for item in config.get("inventory", [])
                ]
                
            persona = Persona(**persona_data) if persona_data else None
            
            return HumanAgent(
                name=config.get("name", "Human"),
                model_id=config.get("model_id", "qwen3.5:27b"),
                provider=config.get("provider", "ollama"),
                persona=persona,
                goals=config.get("goals"),
            )
    
    async def start(
        self,
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
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
        await self._run_loop(stream_callback)
    
    async def _run_loop(
        self,
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Main simulation loop"""
        # Safety limit to prevent infinite runs
        MAX_SAFETY_STEPS = 1000
        
        while (
            (self.max_steps is None or self.current_step < self.max_steps)
            and self.current_step < MAX_SAFETY_STEPS
            and not self._stop_requested
            and self.state == SimulationState.RUNNING
            and not self._check_consensus()
        ):
            if self._pause_requested:
                self.state = SimulationState.PAUSED
                self._pause_requested = False
                self.on_event("run_paused", {"step": self.current_step})
                return
            
            await self._execute_step(stream_callback)
            
            # Wait between ticks - minimal delay for yielding to event loop
            await asyncio.sleep(0.01)
        
        # Run completed
        if not self._stop_requested:
            await self._complete_run()
    
    async def _execute_step(
        self,
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Execute a single simulation step with sequential agent processing"""
        self.current_step += 1
        self.world_state["current_step"] = self.current_step

        step_actions = []
        step_messages = []
        step_events = []

        # Reset failed movement cache for this step
        self._agent_failed_movements.clear()

        # Reset hop distance cache for this step
        self._hop_cache = {}

        # Reset conversation counters for this step
        self.conversation_manager.reset_step_counters()

        # L8: Start diff tracking for this step
        self.diff_tracker.start_step(self.current_step, self.world_state)

        # L2: Expire old proposals
        expired = self.negotiation.expire_proposals(self.current_step)
        for prop_id in expired:
            self.on_event("proposal_expired", {"proposal_id": prop_id, "step": self.current_step})

        # Build current agent states for world state
        self._update_agents_in_world_state()

        # Process all agents sequentially
        await self._process_agents_sequentially(
            step_actions,
            step_messages,
            step_events,
            stream_callback
        )

        # L4: Intra-step reaction round
        await self._execute_reaction_round(step_actions, step_messages, step_events, stream_callback)

        # L6: Extract outcomes from ended conversations before cleanup
        ended_conversations = [
            conv for conv in self.conversation_manager._conversations.values()
            if conv.state == ConversationState.ENDED
        ]
        for conv in ended_conversations:
            agent_names = {aid: self.agents[aid].name for aid in conv.participants if aid in self.agents}
            outcome = self.outcome_extractor.extract_outcome(
                conversation_id=conv.id,
                messages=conv.message_history,
                participants=list(conv.participants),
                location=conv.location,
                agent_names=agent_names,
            )
            # Feed commitments into IntentMemory for each participant
            for agent_name, commitment_text in outcome.commitments.items():
                for aid, agent in self.agents.items():
                    if agent.name == agent_name and hasattr(agent, 'agent_memory'):
                        agent.agent_memory.intent.add_commitment(
                            to="group", what=commitment_text, step=self.current_step
                        )
            self.on_event("conversation_outcome", {
                "conversation_id": conv.id,
                "outcome": outcome.to_dict(),
                "step": self.current_step,
            })

        # Cleanup ended conversations
        self.conversation_manager.cleanup_ended_conversations()

        # L8: End diff tracking
        self.diff_tracker.end_step(self.world_state)
        
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
        
        # Emit step event with telemetry (L3)
        self.on_event("step_completed", {
            "step": self.current_step,
            "actions": step_actions,
            "messages": step_messages,
            "world_state": self.world_state,
            "conversations": [c.to_dict() for c in self.conversation_manager.get_all_active_conversations()],
            "agent_telemetry": self.supervisor.get_all_telemetry(),
            "world_state_diff": self.diff_tracker.get_current_diff().to_dict(),
            "negotiations": self.negotiation.to_dict(),
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

    def _calculate_hop_distance(self, agent_id_1: str, agent_id_2: str) -> int:
        """Calculate hop distance between two agents using BFS. Cached per step."""
        cache_key = tuple(sorted((agent_id_1, agent_id_2)))
        if cache_key in self._hop_cache:
            return self._hop_cache[cache_key]

        loc1 = self._agent_locations.get(agent_id_1)
        loc2 = self._agent_locations.get(agent_id_2)

        if loc1 is None or loc2 is None:
            self._hop_cache[cache_key] = 99
            return 99

        if loc1 == loc2:
            self._hop_cache[cache_key] = 0
            return 0

        # BFS from loc1 to loc2
        from collections import deque
        locations = self.world_state.get("locations", {})
        visited: set[str] = {loc1}
        queue: deque[tuple[str, int]] = deque([(loc1, 0)])

        while queue:
            current, dist = queue.popleft()
            for neighbor in locations.get(current, {}).get("nearby", []):
                if neighbor == loc2:
                    result = dist + 1
                    self._hop_cache[cache_key] = result
                    return result
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))

        self._hop_cache[cache_key] = 99
        return 99

    def _get_comm_zone(self, sender_id: str, receiver_id: str) -> str:
        """Get communication zone: 'same', 'adjacent', or 'distant'."""
        hops = self._calculate_hop_distance(sender_id, receiver_id)
        if hops == 0:
            return "same"
        elif hops == 1:
            return "adjacent"
        else:
            return "distant"

    async def _process_agents_sequentially(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Process all agents sequentially so they can see each other's actions"""
        # Phase 1: Process environment agents first (they create events)
        # L1: Use supervisor for fault isolation
        for agent_id, agent in self.agents.items():
            if agent.role != "environment":
                continue

            if not self.supervisor.is_agent_available(agent_id):
                continue

            messages = self.message_bus.get_messages(agent_id)

            response = await self.supervisor.supervised_tick(
                agent, self.world_state.copy(), messages,
                step_actions, step_messages, step_events,
            )
            agent.last_reasoning = response.reasoning or None

            for action in response.actions:
                action_dict = {
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    **action.model_dump(),
                }
                step_actions.append(action_dict)

                if action.action_type == "environment_update":
                    self._apply_environment_update(action.parameters)
                    if "events" in action.parameters:
                        for evt in action.parameters["events"]:
                            step_events.append(evt)
                            self.diff_tracker.record_event(evt)

            if response.message:
                msg = response.message
                stored_msg = self.message_bus.broadcast(
                    agent_id, msg.content, self.current_step
                )
                step_messages.append(stored_msg)
                self.diff_tracker.record_message()
                await self._persist_message(agent_id, msg)

                self.on_event("message", {
                    "type": "message",
                    "data": stored_msg,
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S")
                })
                await asyncio.sleep(0)

            self._update_agents_in_world_state()
        
        # Build agent_plans and agent_trust for plan visibility
        agent_plans = {}
        agent_trust = {}
        for aid, agent in self.agents.items():
            if hasattr(agent, 'agent_memory') and hasattr(agent.agent_memory, 'intent'):
                intent = agent.agent_memory.intent
                if intent.current_plan:
                    plan = intent.current_plan
                    current_step_desc = (
                        plan.steps[plan.current_step]
                        if plan.current_step < len(plan.steps)
                        else "completing"
                    )
                    agent_plans[aid] = {
                        "goal": plan.goal,
                        "current_step": current_step_desc,
                        "step_progress": f"{plan.current_step + 1}/{len(plan.steps)}",
                    }
            if hasattr(agent, 'agent_memory'):
                trust_data = {}
                for rel in agent.agent_memory._relationships.values():
                    trust_data[rel.agent_id] = rel.trust_level
                agent_trust[aid] = trust_data
        self.world_state["agent_plans"] = agent_plans
        self.world_state["agent_trust"] = agent_trust

        # Phase 2: Process human agents — scene-based or sequential depending on config
        if self.scene_mode:
            await self._process_agents_as_scenes(step_actions, step_messages, step_events, stream_callback)
        else:
            await self._process_human_agents_sequential(step_actions, step_messages, step_events, stream_callback)

    async def _tick_single_agent(
        self,
        agent_id: str,
        agent: Agent,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Execute a single human agent tick with full context enrichment.

        This is the shared implementation used by both sequential and scene modes.
        """
        # L1: Check supervisor availability
        if not self.supervisor.is_agent_available(agent_id):
            return

        # Check if agent is in a conversation and it's their turn
        in_conversation = False
        conversation = None

        agent_conversations = self.conversation_manager.get_agent_conversations(agent_id)
        for conv in agent_conversations:
            if conv.should_continue() and conv.get_next_speaker() == agent_id:
                in_conversation = True
                conversation = conv
                break

        # For human agents not in conversations, check if they should respond
        if isinstance(agent, HumanAgent) and not in_conversation:
            agent_location = self._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
            location_activity = len([
                aid for aid, loc in self._agent_locations.items()
                if loc == agent_location and aid != agent_id
            ])
            has_events = len(step_events) > 0
            has_messages = len(step_messages) > 0

            # Also force response if agent has pending proposals (L2)
            has_pending_proposals = len(self.negotiation.get_pending_proposals_for_agent(agent_id)) > 0

            if not has_pending_proposals and not agent.should_respond(has_events, has_messages, location_activity):
                return

        # Get messages for this agent
        messages = self.message_bus.get_messages(agent_id)

        # Build world state with all context
        agent_world_state = self.world_state.copy()

        # Add cooperation context
        agent_world_state["cooperation"] = self.coordinator.get_cooperation_context()

        # Add suggestions if agent is stuck
        if self.coordinator.is_stuck_in_loop(agent_id):
            agent_world_state["suggestions"] = self.coordinator.get_suggestions_for_agent(agent_id)

        # Add agent's assigned tasks
        agent_tasks_list = self.coordinator.agent_tasks.get(agent_id, [])
        agent_world_state["my_tasks"] = [
            {
                "id": self.coordinator.tasks[tid].id,
                "description": self.coordinator.tasks[tid].description,
                "priority": self.coordinator.tasks[tid].priority,
                "status": self.coordinator.tasks[tid].status,
            }
            for tid in agent_tasks_list
            if tid in self.coordinator.tasks
        ]

        # L2: Add negotiation context
        agent_world_state["negotiations"] = self.negotiation.get_negotiation_context(agent_id)

        # L5: Add trust signals
        trust_context = self.trust_network.get_trust_context(agent_id)
        if trust_context:
            agent_world_state["trust_signals"] = trust_context
        # Consume signals after building context
        self.trust_network.get_pending_signals(agent_id, clear=True)

        # L6: Add recent conversation outcomes
        recent_outcomes = self.outcome_extractor.get_agent_recent_outcomes(agent_id, limit=2)
        if recent_outcomes:
            agent_world_state["recent_conversation_outcomes"] = [
                o.to_context_string() for o in recent_outcomes
            ]

        # L8: Add world state diff
        agent_names = {aid: a.name for aid, a in self.agents.items()}
        diff_context = self.diff_tracker.get_current_diff().to_context_string(agent_id, agent_names)
        if diff_context:
            agent_world_state["world_state_diff"] = diff_context

        if in_conversation and conversation:
            conversation_context = conversation.get_context_for_agent(agent_id)
            messages = conversation_context + messages
            agent_world_state["active_conversation"] = {
                "id": conversation.id,
                "location": conversation.location,
                "participants": [
                    self.agents[pid].name if pid in self.agents else pid
                    for pid in conversation.participants
                ],
                "is_my_turn": True,
            }

        # L1: Use supervisor for fault-isolated tick
        agent_callback = None
        if stream_callback:
            async def _cb(token: str, _aid=agent_id):
                await stream_callback(_aid, token)
            agent_callback = _cb

        response = await self.supervisor.supervised_tick(
            agent, agent_world_state, messages,
            step_actions, step_messages, step_events,
            stream_callback=agent_callback,
        )
        agent.last_reasoning = response.reasoning or None

        # Process actions
        for action in response.actions:
            await self._process_agent_action(
                agent_id, agent, action, step_actions, step_messages,
                in_conversation, conversation,
            )

        # Process message
        if response.message and response.message.content.strip():
            msg = response.message
            stored_msg = self._route_message(
                agent_id, agent, msg, in_conversation, conversation,
            )
            step_messages.append(stored_msg)
            self.diff_tracker.record_message()
            await self._persist_message(agent_id, msg, conversation.id if in_conversation else None)

            self.on_event("message", {
                "type": "message",
                "data": stored_msg,
                "timestamp": datetime.utcnow().strftime("%H:%M:%S")
            })
            await asyncio.sleep(0)
        elif in_conversation and conversation:
            conversation.advance_turn(spoke=False)

        # Track for loop detection
        if response.message and response.message.content.strip():
            topic = self._extract_topic(response.message.content)
            self.coordinator.track_conversation(agent_id, topic)

        # L5: Poll pending trust changes from HumanAgent and feed into TrustNetwork
        if isinstance(agent, HumanAgent) and hasattr(agent, '_pending_trust_changes'):
            for tc in agent._pending_trust_changes:
                self.trust_network.record_trust_change(
                    from_agent=agent_id,
                    to_agent=tc["to_agent"],
                    old_trust=tc["old_trust"],
                    new_trust=tc["new_trust"],
                    reason=tc["reason"],
                    step=self.current_step,
                )
            agent._pending_trust_changes.clear()

        self._update_agents_in_world_state()

    async def _process_human_agents_sequential(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Process all human agents sequentially in shuffled order (original behaviour)."""
        human_agents = [
            (agent_id, agent)
            for agent_id, agent in self.agents.items()
            if agent.role == "human"
        ]
        random.shuffle(human_agents)

        for agent_id, agent in human_agents:
            await self._tick_single_agent(agent_id, agent, step_actions, step_messages, step_events, stream_callback)

    async def _process_agents_as_scenes(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Process human agents as dramatic scenes grouped by location."""
        # Build agent_locations dict from current tracking
        agent_locations = {
            agent_id: self._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
            for agent_id, agent in self.agents.items()
            if hasattr(agent, 'dynamic_state')
        }

        groups = self.scene_director.group_agents_by_location(self.agents, agent_locations)

        for location, agent_ids in groups.items():
            # Filter to available agents
            available = [
                aid for aid in agent_ids
                if self.supervisor.is_agent_available(aid)
            ]

            if not available:
                continue

            if len(available) == 1:
                # Solo agent — run a standard single tick
                aid = available[0]
                agent = self.agents[aid]
                await self._tick_single_agent(aid, agent, step_actions, step_messages, step_events, stream_callback)
                continue

            # Multi-agent scene: pick initiator by extraversion, order turns
            try:
                initiator_id = self.scene_director.pick_initiator(available, self.agents)
            except ValueError:
                continue
            ordered = [initiator_id] + [a for a in available if a != initiator_id]
            turn_ids = ordered[:self.scene_director.max_turns]

            # Inject scene context into world state so agents know who is present
            try:
                self.world_state["_scene_location"] = location
                self.world_state["_scene_participants"] = [
                    self.agents[aid].name for aid in available if aid in self.agents
                ]

                last_speech: dict[str, str | None] = {}
                for agent_id in turn_ids:
                    agent = self.agents[agent_id]
                    msg_count_before = len(step_messages)

                    await self._tick_single_agent(
                        agent_id, agent, step_actions, step_messages, step_events, stream_callback
                    )

                    # Capture speech from any message sent during this turn
                    speech: str | None = None
                    if len(step_messages) > msg_count_before:
                        newest = step_messages[-1]
                        speech = newest.get("content")
                    last_speech[agent_id] = speech

                    # Emit per-turn scene event
                    self.on_event("scene_turn", {
                        "location": location,
                        "agent_id": agent_id,
                        "agent_name": agent.name,
                        "action": getattr(agent, '_last_cinematic', {}).get("action", ""),
                        "speech": speech,
                        "thought": getattr(agent, '_last_cinematic', {}).get("thought", ""),
                        "emotion": getattr(agent, '_last_cinematic', {}).get("emotion", ""),
                        "step": self.current_step,
                    })

                    # Update world state after each turn so next agent sees latest position
                    self._update_agents_in_world_state()

                # Emit scene_completed event
                self.on_event("scene_completed", {
                    "location": location,
                    "participants": [self.agents[aid].name for aid in available if aid in self.agents],
                    "turn_count": len(turn_ids),
                    "step": self.current_step,
                })
            finally:
                self.world_state.pop("_scene_location", None)
                self.world_state.pop("_scene_participants", None)


    async def _process_agent_action(
        self,
        agent_id: str,
        agent: Agent,
        action: Any,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        in_conversation: bool,
        conversation: Any,
    ) -> None:
        """Process a single agent action, dispatching to appropriate handler"""
        if action.action_type == "move":
            success = await self._handle_movement(agent_id, action.target, action.parameters)
            if success and action.target:
                old_loc = self._agent_locations.get(agent_id, "unknown")
                self.diff_tracker.record_movement(agent_id, old_loc, action.target)
            if not success:
                return  # Skip failed movement
        elif action.action_type == "propose_task":
            self._handle_propose_task(agent_id, action.parameters)
        elif action.action_type == "accept_task":
            self._handle_accept_task(agent_id, action.target, action.parameters)
        elif action.action_type == "report_progress":
            self._handle_report_progress(agent_id, action.parameters)
        elif action.action_type == "call_for_vote":
            self._handle_call_for_vote(agent_id, action.parameters)
        elif action.action_type == "take":
            await self._handle_take(agent_id, action.target)
        elif action.action_type == "drop":
            await self._handle_drop(agent_id, action.target)
        elif action.action_type == "use":
            await self._handle_use(agent_id, action.target)
        elif action.action_type == "interact":
            await self._handle_interact(agent_id, action.target, action.parameters)
        elif action.action_type == "search":
            await self._handle_search(agent_id)
        # L2: Negotiation actions
        elif action.action_type == "propose":
            self._handle_propose(agent_id, action.target, action.parameters)
        elif action.action_type == "accept_proposal":
            self._handle_accept_proposal(agent_id, action.target, action.parameters)
        elif action.action_type == "reject_proposal":
            self._handle_reject_proposal(agent_id, action.target, action.parameters)
        elif action.action_type == "counter_propose":
            self._handle_counter_propose(agent_id, action.target, action.parameters)
        elif action.action_type == "withdraw_proposal":
            self._handle_withdraw_proposal(agent_id, action.target)
        # L5: Trust actions
        elif action.action_type == "vouch_for":
            self._handle_vouch_for(agent_id, action.target, action.parameters)
        elif action.action_type == "share_plan":
            self._handle_share_plan(agent_id, action.target)
        # L7: Emergent leadership
        elif action.action_type == "coordinate":
            self._handle_coordinate(agent_id, action.parameters)
        elif action.action_type == "delegate_task":
            self._handle_delegate_task(agent_id, action.target, action.parameters)
        elif action.action_type == "explore":
            self._handle_explore(agent_id, action.parameters)

        # Log action
        action_dict = {
            "agent_id": agent_id,
            "agent_name": agent.name,
            **action.model_dump(),
        }
        step_actions.append(action_dict)
        self.coordinator.track_action(agent_id, action.action_type, action.target)

    def _route_message(
        self,
        agent_id: str,
        agent: Agent,
        msg: Any,
        in_conversation: bool,
        conversation: Any,
    ) -> dict[str, Any]:
        """Route a message to the appropriate destination"""
        if in_conversation and conversation:
            stored_msg = self.message_bus.send_to_conversation(
                from_agent_id=agent_id,
                conversation_id=conversation.id,
                participant_ids=conversation.participants,
                content=msg.content,
                step_index=self.current_step,
                location=conversation.location,
                metadata=msg.metadata,
            )
            conversation.add_message(stored_msg)
            conversation.advance_turn(spoke=True)
        elif msg.message_type == "broadcast":
            stored_msg = self.message_bus.broadcast(
                agent_id, msg.content, self.current_step,
                metadata=msg.metadata,
            )
        elif msg.message_type == "room":
            agent_location = self._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
            for aid, loc in self._agent_locations.items():
                if loc == agent_location:
                    self.message_bus.join_room(aid, agent_location)
            stored_msg = self.message_bus.send_to_room(
                from_agent_id=agent_id,
                room_name=agent_location,
                content=msg.content,
                step_index=self.current_step,
                metadata=msg.metadata,
            )
        else:  # direct
            to_agent_id = msg.to_target
            if to_agent_id != "broadcast":
                # Try alias registry first (handles partial names, nicknames, titles)
                resolved = self.message_bus.alias_registry.resolve(to_agent_id)
                if resolved:
                    to_agent_id = resolved
                else:
                    # Fallback to exact name match
                    for aid, a in self.agents.items():
                        if a.name == to_agent_id:
                            to_agent_id = aid
                            break
            stored_msg = self.message_bus.send_direct(
                from_agent_id=agent_id,
                to_agent_id=to_agent_id,
                content=msg.content,
                step_index=self.current_step,
                metadata=msg.metadata,
            )
        return stored_msg

    # === L4: Intra-step Reaction Round ===

    async def _execute_reaction_round(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """
        After all agents tick, agents who received direct messages or proposals
        this step get a quick reactive tick with restricted actions.
        This enables same-step proposal->response instead of 2+ step latency.
        """
        reactive_agents = set()

        # Agents with pending proposals that were created this step
        for prop in self.negotiation._proposals.values():
            if (
                prop.created_at_step == self.current_step
                and prop.state == ProposalState.PENDING
                and prop.target_id
            ):
                reactive_agents.add(prop.target_id)

        # Agents who received direct messages this step
        for msg in step_messages:
            if msg.get("message_type") == "direct":
                target = msg.get("to_target")
                if target and target in self.agents:
                    reactive_agents.add(target)

        if not reactive_agents:
            return

        for agent_id in reactive_agents:
            agent = self.agents.get(agent_id)
            if not agent or agent.role != "human":
                continue
            if not self.supervisor.is_agent_available(agent_id):
                continue

            messages = self.message_bus.get_messages(agent_id)
            if not messages:
                continue

            # Build minimal reactive context
            agent_world_state = self.world_state.copy()
            agent_world_state["negotiations"] = self.negotiation.get_negotiation_context(agent_id)
            agent_world_state["_reactive_round"] = True

            response = await self.supervisor.supervised_tick(
                agent, agent_world_state, messages,
                step_actions, step_messages, step_events,
            )
            agent.last_reasoning = response.reasoning or None

            for action in response.actions:
                # Only allow reactive actions
                if action.action_type in (
                    "speak", "accept_proposal", "reject_proposal",
                    "counter_propose", "help", "wait",
                ):
                    await self._process_agent_action(
                        agent_id, agent, action, step_actions, step_messages,
                        False, None,
                    )

            if response.message and response.message.content.strip():
                stored_msg = self._route_message(agent_id, agent, response.message, False, None)
                step_messages.append(stored_msg)
                self.diff_tracker.record_message()
                await self._persist_message(agent_id, response.message)

                self.on_event("message", {
                    "type": "message",
                    "data": stored_msg,
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S")
                })

            self._update_agents_in_world_state()

    # === L2: Negotiation Action Handlers ===

    def _handle_propose(self, agent_id: str, target: str | None, params: dict[str, Any]) -> None:
        """Handle a formal proposal (Symphony-style state machine)"""
        # Resolve target name to ID
        target_id = target
        if target_id:
            for aid, a in self.agents.items():
                if a.name == target_id:
                    target_id = aid
                    break

        proposal = self.negotiation.create_proposal(
            proposer_id=agent_id,
            target_id=target_id,
            proposal_type=params.get("type", "cooperation"),
            description=params.get("description", ""),
            parameters=params,
            current_step=self.current_step,
        )
        self.diff_tracker.record_proposal()
        self.on_event("proposal_created", {
            "proposal": proposal.to_dict(),
            "agent_id": agent_id,
            "step": self.current_step,
        })

    def _handle_accept_proposal(self, agent_id: str, proposal_id: str | None, params: dict[str, Any]) -> None:
        """Handle accepting a proposal"""
        if not proposal_id:
            # Try to find the most recent pending proposal targeting this agent
            pending = self.negotiation.get_pending_proposals_for_agent(agent_id)
            if pending:
                proposal_id = pending[0].id
            else:
                return

        agreement = self.negotiation.accept_proposal(
            proposal_id, agent_id, self.current_step,
            reasoning=params.get("reasoning", ""),
        )
        if agreement:
            # Feed commitments into IntentMemory
            for party_id, commitment in agreement.commitments.items():
                agent = self.agents.get(party_id)
                if agent and hasattr(agent, 'agent_memory'):
                    other_parties = [p for p in agreement.parties if p != party_id]
                    to_name = self.agents[other_parties[0]].name if other_parties and other_parties[0] in self.agents else "others"
                    agent.agent_memory.intent.add_commitment(
                        to=to_name, what=commitment, step=self.current_step
                    )

            self.on_event("proposal_accepted", {
                "proposal_id": proposal_id,
                "agreement": agreement.to_dict(),
                "step": self.current_step,
            })

    def _handle_reject_proposal(self, agent_id: str, proposal_id: str | None, params: dict[str, Any]) -> None:
        """Handle rejecting a proposal"""
        if not proposal_id:
            pending = self.negotiation.get_pending_proposals_for_agent(agent_id)
            if pending:
                proposal_id = pending[0].id
            else:
                return

        self.negotiation.reject_proposal(
            proposal_id, agent_id, self.current_step,
            reasoning=params.get("reasoning", ""),
        )
        self.on_event("proposal_rejected", {
            "proposal_id": proposal_id,
            "agent_id": agent_id,
            "step": self.current_step,
        })

    def _handle_counter_propose(self, agent_id: str, proposal_id: str | None, params: dict[str, Any]) -> None:
        """Handle counter-proposal"""
        if not proposal_id:
            pending = self.negotiation.get_pending_proposals_for_agent(agent_id)
            if pending:
                proposal_id = pending[0].id
            else:
                return

        self.negotiation.counter_propose(
            proposal_id, agent_id, params, self.current_step,
        )
        self.on_event("counter_proposal", {
            "proposal_id": proposal_id,
            "agent_id": agent_id,
            "counter_terms": params,
            "step": self.current_step,
        })

    def _handle_withdraw_proposal(self, agent_id: str, proposal_id: str | None) -> None:
        """Handle proposal withdrawal"""
        if proposal_id:
            self.negotiation.withdraw_proposal(proposal_id, agent_id, self.current_step)

    # === L5: Trust Action Handlers ===

    def _handle_vouch_for(self, agent_id: str, subject: str | None, params: dict[str, Any]) -> None:
        """Handle agent vouching for another agent"""
        if not subject:
            return

        # Resolve subject name to ID
        subject_id = subject
        for aid, a in self.agents.items():
            if a.name == subject:
                subject_id = aid
                break

        # Vouch to all agents at the same location
        agent_location = self._agent_locations.get(agent_id)
        recipients = [
            aid for aid, loc in self._agent_locations.items()
            if loc == agent_location and aid != agent_id and aid != subject_id
        ]

        signals = self.trust_network.vouch_for(
            voucher_id=agent_id,
            subject_id=subject_id,
            recipient_ids=recipients,
            step=self.current_step,
            reason=params.get("reason", ""),
        )
        for _ in signals:
            self.diff_tracker.record_trust_signal()

        self.on_event("vouch_for", {
            "voucher": agent_id,
            "subject": subject_id,
            "recipients": recipients,
            "step": self.current_step,
        })

    def _handle_share_plan(self, agent_id: str, target: str | None) -> None:
        """Handle explicit plan sharing (trust-building gesture)"""
        agent = self.agents.get(agent_id)
        if not agent or not hasattr(agent, 'agent_memory'):
            return

        intent = agent.agent_memory.intent
        if not intent.current_plan:
            return

        # Share plan increases trust with target
        if target:
            target_id = target
            for aid, a in self.agents.items():
                if a.name == target:
                    target_id = aid
                    break

            # Get current trust level
            rel = agent.agent_memory.get_relationship(target_id)
            old_trust = rel.trust_level if rel else 5

            if isinstance(agent, HumanAgent):
                agent.update_relationship(target_id, trust_delta=1, note="Shared their plan with me")

            new_trust = old_trust + 1
            self.trust_network.record_trust_change(
                from_agent=agent_id, to_agent=target_id,
                old_trust=old_trust, new_trust=new_trust,
                reason="Shared their plan openly",
                step=self.current_step,
            )

        self.on_event("plan_shared", {
            "agent_id": agent_id,
            "target": target,
            "plan_goal": intent.current_plan.goal,
            "step": self.current_step,
        })

    # === L7: Emergent Leadership Handlers ===

    def _handle_coordinate(self, agent_id: str, params: dict[str, Any]) -> None:
        """Handle coordination action (emergent leadership)"""
        description = params.get("description", "")
        if description:
            self.on_event("coordination_proposed", {
                "agent_id": agent_id,
                "agent_name": self.agents[agent_id].name if agent_id in self.agents else agent_id,
                "description": description,
                "step": self.current_step,
            })

    def _handle_delegate_task(self, agent_id: str, target: str | None, params: dict[str, Any]) -> None:
        """Handle task delegation (emergent leadership)"""
        if not target or not params.get("description"):
            return

        # Resolve target name to ID
        target_id = target
        for aid, a in self.agents.items():
            if a.name == target:
                target_id = aid
                break

        # Create as a proposal so target can accept/reject
        self.negotiation.create_proposal(
            proposer_id=agent_id,
            target_id=target_id,
            proposal_type="task_delegation",
            description=params.get("description", ""),
            parameters={
                "proposer_commitment": "coordinate and support",
                "target_commitment": params.get("description", ""),
                **params,
            },
            current_step=self.current_step,
        )
        self.diff_tracker.record_proposal()

        self.on_event("task_delegated", {
            "from_agent": agent_id,
            "to_agent": target_id,
            "description": params.get("description"),
            "step": self.current_step,
        })

    def _handle_explore(self, agent_id: str, parameters: dict) -> None:
        """Handle explore action — check potential_locations for discoverable areas."""
        agent = self.agents[agent_id]
        current_loc = self._agent_locations.get(agent_id, "unknown")
        description = parameters.get("description", "").lower()
        potential = self.world_state.get("potential_locations", {})

        discovered = None
        for loc_name, loc_data in list(potential.items()):
            # Only discover locations connected to current location
            if current_loc not in loc_data.get("nearby", []):
                continue
            # Check if any discovery hint matches the explore description
            hints = loc_data.get("discovery_hints", [])
            if any(hint in description for hint in hints):
                discovered = loc_name
                break

        if discovered:
            loc_data = potential.pop(discovered)
            # Add to active locations
            self.world_state["locations"][discovered] = loc_data
            # Ensure bidirectional connections
            for connected_loc in loc_data.get("nearby", []):
                if connected_loc in self.world_state["locations"]:
                    if discovered not in self.world_state["locations"][connected_loc].get("nearby", []):
                        self.world_state["locations"][connected_loc]["nearby"].append(discovered)
            agent._action_feedback.append(
                f"Discovery: You found '{discovered}' — {loc_data['description']}"
            )
            self.on_event("location_discovered", {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "location": discovered,
                "connected_to": current_loc,
                "step": self.current_step,
            })
        else:
            agent._action_feedback.append(
                "Exploration: You search the area but find nothing new."
            )

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
                agent.last_reasoning = response.reasoning or None

                for action in response.actions:
                    step_actions.append({
                        "agent_id": agent_id,
                        "agent_name": agent.name,
                        **action.model_dump(),
                    })
                    
                    if action.action_type == "environment_update":
                        self._apply_environment_update(action.parameters)
                    elif action.action_type == "affect_agent":
                        self._apply_agent_effect(action.target, action.parameters)
                
                if response.message:
                    msg = response.message
                    stored_msg = self.message_bus.broadcast(
                        agent_id, msg.content, self.current_step
                    )
                    step_messages.append(stored_msg)
                    await self._persist_message(agent_id, msg)
                    
            except Exception as e:
                agent = self.agents.get(agent_id)
                agent_name = agent.name if agent else agent_id
                self.on_event("agent_error", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": str(e),
                    "step": self.current_step,
                    "context": "environment_agent_tick",
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
            agent.last_reasoning = response.reasoning or None

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
            agent = self.agents.get(speaker_id)
            agent_name = agent.name if agent else speaker_id
            self.on_event("agent_error", {
                "agent_id": speaker_id,
                "agent_name": agent_name,
                "error": str(e),
                "step": self.current_step,
                "conversation_id": conversation.id,
                "context": "conversation_speak",
            })
            conversation.advance_turn(spoke=False)
            return False
    
    def _find_path(self, start_loc: str, target_loc: str, locations: dict[str, Any]) -> list[str] | None:
        """Find the shortest path between locations using BFS"""
        if start_loc == target_loc:
            return [start_loc]
            
        queue = [(start_loc, [start_loc])]
        visited = {start_loc}
        
        while queue:
            current, path = queue.pop(0)
            
            # check neighbors
            nearby = locations.get(current, {}).get("nearby", [])
            for neighbor in nearby:
                if neighbor == target_loc:
                    return path + [neighbor]
                
                if neighbor not in visited and neighbor in locations:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
                    
        return None

    def _fuzzy_match_location(self, target: str, nearby: list[str]) -> str | None:
        """Fuzzy-match a target location name against nearby locations.
        Handles: case differences, 'the X' prefix, underscore/space equivalence."""
        target_clean = target.strip().lower()
        for prefix in ("the ", "a ", "an "):
            if target_clean.startswith(prefix):
                target_clean = target_clean[len(prefix):]

        for loc in nearby:
            loc_clean = loc.strip().lower()
            if target_clean == loc_clean:
                return loc
            if target_clean.replace(" ", "_") == loc_clean or target_clean.replace("_", " ") == loc_clean:
                return loc
            if target_clean in loc_clean or loc_clean in target_clean:
                return loc
        return None

    async def _handle_movement(
        self,
        agent_id: str,
        target_location: str | None,
        parameters: dict[str, Any],
    ) -> bool:
        """Handle agent movement between locations. Returns True if successfully initiated or completed."""
        if not target_location:
            return False
            
        # Ensure target_location is a string
        if isinstance(target_location, list):
            # This handles the "unhashable type: list" bug where LLM returns a list
            if len(target_location) > 0:
                target_location = str(target_location[0])
            else:
                return False
        elif not isinstance(target_location, str):
            target_location = str(target_location)
        
        # Check if this agent already failed to move to this location in this step
        if agent_id not in self._agent_failed_movements:
            self._agent_failed_movements[agent_id] = set()
        
        if target_location in self._agent_failed_movements[agent_id]:
            # Already tried and failed this step - silently skip to prevent duplicate errors
            return False
            
        # Get agent
        agent = self.agents.get(agent_id)
        if not agent:
            return False
        
        current_location = self._agent_locations.get(agent_id, "unknown")
        
        # Prevent redundant moves
        if current_location == target_location:
            return True # Successfully "stayed" at location, no event emitted

        
        # Check if already travelling
        travel_state = agent.dynamic_state.get("travel", None)
        if travel_state and travel_state.get("target") == target_location:
            # Continue travel
            travel_state["progress"] += 1
            distance = travel_state["distance"]
            
            if travel_state["progress"] >= distance:
                # Arrived!
                del agent.dynamic_state["travel"]
                # Proceed to update location below
            else:
                # Still travelling
                self.on_event("agent_travelling", {
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "target": target_location,
                    "progress": travel_state["progress"],
                    "distance": distance,
                    "step": self.current_step,
                })
                return True # Action successful (progress made)
        elif travel_state:
             # Changing target mid-travel? Reset or disallow?
             # For now, allow changing target, reset progress
             pass
        
        # Validate movement (target must be nearby)
        locations = self.world_state.get("locations", {})
        current_loc_data = locations.get(current_location, {})
        nearby = current_loc_data.get("nearby", [])
        
        # Check if target location exists
        if target_location not in locations:
            # Try fuzzy match against ALL known locations
            fuzzy = self._fuzzy_match_location(target_location, list(locations.keys()))
            if fuzzy:
                target_location = fuzzy
            else:
                # Location doesn't exist at all — fail with feedback
                agent._action_feedback.append(
                    f"Movement failed: '{target_location}' doesn't exist. "
                    f"Nearby locations: {', '.join(nearby)}."
                )
                self._agent_failed_movements[agent_id].add(target_location)
                self.on_event("movement_failed", {
                    "agent_id": agent_id,
                    "agent_name": agent.name if agent else agent_id,
                    "from": current_location,
                    "to": target_location,
                    "reason": "Location does not exist",
                    "nearby_locations": nearby,
                })
                return False
        
        if target_location not in nearby and target_location != current_location:
            # Try fuzzy match against nearby
            fuzzy = self._fuzzy_match_location(target_location, nearby)
            if fuzzy:
                target_location = fuzzy

        if target_location not in nearby and target_location != current_location:
            # Try to find a path for multi-step movement
            path = self._find_path(current_location, target_location, locations)
            
            if path and len(path) > 1:
                # Path found! Route via the next stop
                next_stop = path[1]
                
                agent = self.agents.get(agent_id)
                agent_name = agent.name if agent else agent_id
                
                self.on_event("agent_rerouted", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "original_target": target_location,
                    "next_stop": next_stop,
                    "full_path": path,
                    "step": self.current_step,
                })
                
                # Update target to the next stop for this specific move action
                target_location = next_stop
                # Current location's nearby list already contains next_stop by definition of path
            else:
                # Invalid movement - location not reachable
                agent = self.agents.get(agent_id)
                agent_name = agent.name if agent else agent_id
                reason = "Location not reachable from current location"

                # Track this failed movement to prevent retries in this step
                self._agent_failed_movements[agent_id].add(target_location)

                agent._action_feedback.append(
                    f"Movement failed: Can't reach '{target_location}' from '{current_location}'. "
                    f"Nearby locations: {', '.join(nearby)}."
                )
                self.on_event("movement_failed", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "from": current_location,
                    "to": target_location,
                    "reason": reason,
                    "available_locations": list(locations.keys()),
                    "nearby_locations": nearby,
                })
                return False
            
        # Check distance for new travel
        target_info = locations.get(target_location, {})
        distance = target_info.get("distance", 1)
        
        if distance > 1 and not (travel_state and travel_state.get("target") == target_location):
             # Start multi-step travel
             agent.dynamic_state["travel"] = {
                 "target": target_location,
                 "origin": current_location,
                 "distance": distance,
                 "progress": 1 # First step taken
             }
             
             if distance > 1:
                 self.on_event("travel_started", {
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "from": current_location,
                    "to": target_location,
                    "distance": distance,
                    "step": self.current_step,
                 })
                 return True # Started travel
        
        # Update location (Arrived)
        self._agent_locations[agent_id] = target_location
        
        # Update agent's dynamic state
        agent = self.agents.get(agent_id)
        if agent:
            agent.dynamic_state["location"] = target_location
            # Clear travel state if it existed
            if "travel" in agent.dynamic_state:
                del agent.dynamic_state["travel"]
        
        # Subscribe agent to location room for room messages
        self.message_bus.join_room(agent_id, target_location)
        
        # Update conversation manager (handles join/leave of location conversations)
        self.conversation_manager.update_agent_location(agent_id, target_location)
        
        # Update world state
        self._update_agents_in_world_state()
        
        agent = self.agents.get(agent_id)
        agent_name = agent.name if agent else agent_id
        self.on_event("agent_moved", {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "from": current_location,
            "to": target_location,
            "step": self.current_step,
        })
        return True
    
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
        
        # Apply location-based health effects
        self._apply_location_health_effects()
    
    def _apply_agent_effect(self, target_agent_id: str | None, params: dict[str, Any]) -> None:
        """Apply direct health/stress effects to a specific agent"""
        if not target_agent_id:
            return
        
        # Try to find agent by ID first, then by name
        agent = self.agents.get(target_agent_id)
        if not agent:
            # Search by name
            for agent_id, a in self.agents.items():
                if a.name == target_agent_id:
                    agent = a
                    break
        
        if not agent:
            return
            
        current_health = agent.dynamic_state.get("health", 100.0) # Default to 100 if missing
        current_stress = agent.dynamic_state.get("stress", 0.0)   # Default to 0 if missing
        
        # Ensure they are floats
        if current_health is None: current_health = 100.0
        if current_stress is None: current_stress = 0.0
        
        if "health_delta" in params:
            delta = params["health_delta"]
            if delta is not None:
                agent.dynamic_state["health"] = max(0.0, min(100.0, current_health + float(delta)))
        
        if "stress_delta" in params:
            new_stress = max(1, min(10, current_stress + params["stress_delta"]))
            agent.dynamic_state["stress_level"] = new_stress
        
        if "stress_level" in params:
            agent.dynamic_state["stress_level"] = max(1, min(10, params["stress_level"]))
    
    def _apply_location_health_effects(self) -> None:
        """Apply health effects based on agent locations and location properties"""
        locations = self.world_state.get("locations", {})
        hazard_level = self.world_state.get("hazard_level", 0)
        
        for agent_id, agent in self.agents.items():
            if agent.role != "human":
                continue
            
            location = agent.dynamic_state.get("location", "unknown")
            if location not in locations:
                continue
            
            loc_data = locations[location]
            
            # Apply location effects
            location_effects = loc_data.get("location_effects", {})
            if "health_per_tick" in location_effects:
                current_health = agent.dynamic_state.get("health", 10)
                # Convert to float in case it's stored as string
                try:
                    current_health = float(current_health)
                except (ValueError, TypeError):
                    current_health = 10
                new_health = max(0, min(10, current_health + location_effects["health_per_tick"]))
                agent.dynamic_state["health"] = new_health
            
            if "stress_per_tick" in location_effects:
                current_stress = agent.dynamic_state.get("stress_level", 1)
                # Convert to float in case it's stored as string
                try:
                    current_stress = float(current_stress)
                except (ValueError, TypeError):
                    current_stress = 1
                new_stress = max(1, min(10, current_stress + location_effects["stress_per_tick"]))
                agent.dynamic_state["stress_level"] = new_stress
            
            # Apply item-based effects
            items = loc_data.get("items", [])
            for item in items:
                # First aid kits increase health
                if "first_aid" in item.lower() or "medical" in item.lower():
                    current_health = agent.dynamic_state.get("health", 10)
                    if current_health < 10:
                        agent.dynamic_state["health"] = min(10, current_health + 0.5)
                
                # Contaminated items reduce health
                if "contaminated" in item.lower() or "toxic" in item.lower():
                    current_health = agent.dynamic_state.get("health", 10)
                    agent.dynamic_state["health"] = max(0, current_health - 0.5)
            
            # Apply hazard-based effects if location is hazard-affected
            if loc_data.get("hazard_affected", False) and hazard_level > 0:
                # Higher hazard levels cause more health loss
                health_loss = (hazard_level / 10.0) * 0.3
                current_health = agent.dynamic_state.get("health", 10)
                agent.dynamic_state["health"] = max(0, current_health - health_loss)
                
                # Hazard also increases stress
                stress_gain = (hazard_level / 10.0) * 0.2
                current_stress = agent.dynamic_state.get("stress_level", 1)
                agent.dynamic_state["stress_level"] = min(10, current_stress + stress_gain)
    
    def _extract_topic(self, message: str) -> str:
        """Extract a topic/keyword from a message for loop detection"""
        # Simple keyword extraction
        keywords = [
            "rescue", "help", "move", "safety", "flood", "bridge", "shelter",
            "medical", "supplies", "coordinate", "plan", "danger", "evacuate"
        ]
        message_lower = message.lower()
        for keyword in keywords:
            if keyword in message_lower:
                return keyword
        return "general"
    
    def _handle_propose_task(self, agent_id: str, params: dict[str, Any]) -> None:
        """Handle task proposal from an agent"""
        description = params.get("description", "")
        priority = params.get("priority", 5)
        assigned_to = params.get("assigned_to")
        
        if description:
            task_id = self.coordinator.create_task(description, priority, assigned_to)
            self.on_event("task_proposed", {
                "agent_id": agent_id,
                "task_id": task_id,
                "description": description,
                "priority": priority,
            })
    
    def _handle_accept_task(self, agent_id: str, task_id: str | None, params: dict[str, Any]) -> None:
        """Handle task acceptance by an agent"""
        if not task_id:
            # Try to find task by description
            description = params.get("description", "")
            for tid, task in self.coordinator.tasks.items():
                if task.description == description and task.status == "pending":
                    task_id = tid
                    break
        
        if task_id and self.coordinator.assign_task(task_id, agent_id):
            agent = self.agents.get(agent_id)
            agent_name = agent.name if agent else agent_id
            self.on_event("task_accepted", {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task_id": task_id,
            })
    
    def _handle_report_progress(self, agent_id: str, params: dict[str, Any]) -> None:
        """Handle progress report from an agent"""
        task_id = params.get("task_id")
        progress = params.get("progress", 0.0)
        goal = params.get("goal")
        
        if task_id and task_id in self.coordinator.tasks:
            task = self.coordinator.tasks[task_id]
            task.progress = max(0.0, min(1.0, progress))
            if progress >= 1.0:
                self.coordinator.complete_task(task_id)
        
        if goal:
            goal_progress = params.get("goal_progress", 0.0)
            self.coordinator.update_goal_progress(goal, goal_progress)
    
    def _handle_call_for_vote(self, agent_id: str, params: dict[str, Any]) -> None:
        """Handle vote call from an agent (for consensus detection)"""
        topic = params.get("topic", "general")
        vote = params.get("vote", "continue")  # continue, end, pause
        
        # Store vote in world state for consensus detection
        if "votes" not in self.world_state:
            self.world_state["votes"] = {}
        
        self.world_state["votes"][agent_id] = {
            "topic": topic,
            "vote": vote,
            "step": self.current_step,
        }

    async def _handle_take(self, agent_id: str, item_name: str) -> bool:
        """Handle agent taking an item"""
        if not item_name:
            return False
            
        agent = self.agents.get(agent_id)
        if not agent:
            return False
            
        location = agent.dynamic_state.get("location")
        if not location:
            return False
            
        loc_data = self.world_state["locations"].get(location, {})
        if "items" not in loc_data:
            loc_data["items"] = []
            
        # Find item in location
        found_idx = -1
        item_obj = None
        
        for idx, item in enumerate(loc_data["items"]):
            # Normalize item (string or dict)
            iname = item.get("name") if isinstance(item, dict) else item
            if iname.lower() == item_name.lower():
                found_idx = idx
                item_obj = item
                break
        
        if found_idx == -1:
            return False
            
        # Remove from location and add to agent inventory
        loc_data["items"].pop(found_idx)
        
        if "inventory" not in agent.dynamic_state:
            agent.dynamic_state["inventory"] = []
            
        # Add to dynamic state inventory
        agent.dynamic_state["inventory"].append(item_obj)
        
        # Sync Python object inventory list if applicable
        if hasattr(agent, "inventory"):
             agent.inventory.append(item_obj if isinstance(item_obj, dict) else {"name": item_obj})
        
        self.message_bus.broadcast(agent_id, f"Taken {item_name}", self.current_step)
        return True

    async def _handle_drop(self, agent_id: str, item_name: str) -> bool:
        """Handle agent dropping an item"""
        if not item_name:
            return False
            
        agent = self.agents.get(agent_id)
        if not agent:
            return False
            
        location = agent.dynamic_state.get("location")
        if not location:
            return False
            
        if "inventory" not in agent.dynamic_state:
            return False
            
        # Find item in inventory
        found_idx = -1
        item_obj = None
        
        for idx, item in enumerate(agent.dynamic_state["inventory"]):
            iname = item.get("name") if isinstance(item, dict) else item
            if iname.lower() == item_name.lower():
                found_idx = idx
                item_obj = item
                break
        
        if found_idx == -1:
            return False
            
        # Remove from inventory and add to location
        agent.dynamic_state["inventory"].pop(found_idx)
        
        # Sync Python object inventory
        if hasattr(agent, "inventory"):
            # Simple rebuild to avoid mismatch
            if isinstance(agent.inventory, list):
                 # Find and remove
                 for i, inv_item in enumerate(agent.inventory):
                      inv_name = inv_item.name if hasattr(inv_item, "name") else inv_item.get("name", "")
                      if inv_name.lower() == item_name.lower():
                           agent.inventory.pop(i)
                           break

        loc_data = self.world_state["locations"].get(location, {})
        if "items" not in loc_data:
            loc_data["items"] = []
            
        loc_data["items"].append(item_obj)
        
        self.message_bus.broadcast(agent_id, f"Dropped {item_name}", self.current_step)
        return True

    async def _handle_use(self, agent_id: str, item_name: str) -> bool:
        """Handle agent using an item"""
        if not item_name:
            return False
            
        agent = self.agents.get(agent_id)
        if not agent:
            return False
            
        # Check inventory first
        inventory = agent.dynamic_state.get("inventory", [])
        has_item = False
        used_item = None
        
        for idx, item in enumerate(inventory):
             iname = item.get("name") if isinstance(item, dict) else item
             if iname.lower() == item_name.lower():
                 has_item = True
                 used_item = item
                 # Remove if consumable (assume yes for now)
                 inventory.pop(idx)
                 # Sync python object
                 if hasattr(agent, "inventory") and isinstance(agent.inventory, list):
                       if len(agent.inventory) > idx:
                            agent.inventory.pop(idx)
                 break
        
        if not has_item:
            return False
            
        # Apply effects
        objects = self.world_state.get("objects", {})
        obj_def = objects.get(item_name, {})
        # If item was dict in inventory, maybe it has effects?
        if not obj_def and isinstance(used_item, dict):
             obj_def = used_item
             
        effects = obj_def.get("effects", [])
        
        # Default fallback logic
        if not effects:
            if "med" in item_name.lower() or "first aid" in item_name.lower():
                effects = [{"target_attribute": "health", "value": 3}]
            elif "water" in item_name.lower() or "food" in item_name.lower():
                effects = [{"target_attribute": "stress_level", "value": -1}]
        
        applied_msg = []
        for effect in effects:
             attr = effect.get("target_attribute")
             val = effect.get("value", 0)
             if attr == "health":
                 if hasattr(agent, "update_health"):
                      agent.update_health(val)
                      applied_msg.append(f"Health {'+' if val>0 else ''}{val}")
             elif attr == "stress" or attr == "stress_level":
                 if hasattr(agent, "update_stress"):
                      agent.update_stress(val)
                      applied_msg.append(f"Stress {'+' if val>0 else ''}{val}")

        msg = f"Used {item_name}"
        if applied_msg:
             msg += f" ({', '.join(applied_msg)})"
             
        self.message_bus.broadcast(agent_id, msg, self.current_step)
                 
        return True

    async def _handle_search(self, agent_id: str) -> list[str]:
        """Handle search action"""
        agent = self.agents.get(agent_id)
        if not agent:
            return []
            
        location = agent.dynamic_state.get("location")
        if not location:
            return []
            
        loc_data = self.world_state["locations"].get(location, {})
        
        # For now, just return visible items as "found" to confirm
        found = []
        items = loc_data.get("items", [])
        for item in items:
             name = item.get("name") if isinstance(item, dict) else item
             found.append(name)
             
        if found:
             self.message_bus.broadcast(agent_id, f"Searched and found: {', '.join(found)}", self.current_step)
        else:
             self.message_bus.broadcast(agent_id, "Searched but found nothing.", self.current_step)
             
        return found

    async def _handle_interact(self, agent_id: str, target: str, params: dict) -> tuple[bool, str]:
        """Handle interaction with objects"""
        self.message_bus.broadcast(agent_id, f"Interacted with {target}", self.current_step)
        return True, f"Interacted with {target}"

    
    def _check_consensus(self) -> bool:
        """Check if agents have reached consensus to end the simulation"""
        votes = self.world_state.get("votes", {})
        if not votes:
            return False
        
        # Get human agents
        human_agents = [aid for aid, agent in self.agents.items() if agent.role == "human"]
        if len(human_agents) < 2:
            return False
        
        # Count votes to end
        end_votes = sum(1 for v in votes.values() if v.get("vote") == "end")
        total_votes = len(votes)
        
        # Need majority (50%+) of agents who voted to agree to end
        # Or if we have votes from majority of all agents, check if majority want to end
        if total_votes >= len(human_agents) * 0.5:  # At least 50% of agents voted
            if end_votes >= total_votes * 0.6:  # 60% of voters want to end
                self.on_event("consensus_reached", {
                    "decision": "end",
                    "end_votes": end_votes,
                    "total_votes": total_votes,
                    "total_agents": len(human_agents),
                })
                return True
        
        # Unanimous agreement (all voters want to end)
        if total_votes >= len(human_agents) * 0.8 and end_votes == total_votes:
            self.on_event("consensus_reached", {
                "decision": "end",
                "end_votes": end_votes,
                "total_votes": total_votes,
                "total_agents": len(human_agents),
            })
            return True
        
        return False
    
    def _compute_step_metrics(self) -> dict[str, Any]:
        """Compute metrics for the current step"""
        total_health = 0
        total_stress = 0
        human_count = 0
        
        for agent in self.agents.values():
            if agent.role == "human":
                human_count += 1
                # Convert to float/int in case they're stored as strings
                health = agent.dynamic_state.get("health", 10)
                stress = agent.dynamic_state.get("stress_level", 5)
                try:
                    total_health += float(health) if health else 10
                    total_stress += float(stress) if stress else 5
                except (ValueError, TypeError):
                    total_health += 10
                    total_stress += 5
        
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
