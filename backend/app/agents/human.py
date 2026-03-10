"""Human Agent - roleplays as a person with personality"""
import random
from typing import Any, Callable, Awaitable

from app.agents.base import Agent
from app.agents.cognitive_engine import CognitiveEngine, CognitivePhase
from app.llm.base import LLMMessage
from app.schemas.agent import AgentResponse
from app.schemas.persona import Persona


class HumanAgent(Agent):
    """
    Agent that roleplays as a human with rich personality traits.
    Makes decisions based on persona characteristics and emotional state.
    Includes memory of relationships and past events.
    """
    
    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Human",
        model_id: str = "qwen3.5:27b",
        provider: str = "ollama",
        persona: Persona | None = None,
        goals: list[str] | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            role="human",
            model_id=model_id,
            provider=provider,
            goals=goals or ["Survive", "Help others if possible"],
        )
        
        # Use provided persona or create a default one
        self.persona = persona or Persona(
            name=name,
            age=30,
            sex="non-binary",
            occupation="Civilian",
        )
        
        # Sync name with persona
        self.name = self.persona.name
        
        # Update agent memory with correct name
        self.agent_memory.agent_name = self.name
        
        # Initialize dynamic state from persona
        self.dynamic_state = {
            "stress_level": self.persona.stress_level,
            "health": self.persona.health,
            "inventory": self.persona.inventory.copy(),
            "location": self.persona.location,
        }
    
    def should_respond(
        self,
        has_events: bool,
        has_messages: bool,
        location_activity: int,
    ) -> bool:
        """Determine if agent should evaluate/respond this turn based on personality"""
        base_probability = 0.3  # Base 30% chance
        
        # Extraversion increases base probability
        extraversion_mod = (self.persona.extraversion - 5) * 0.05  # -0.2 to +0.2
        
        # Neuroticism increases reactivity to events
        neuroticism_mod = 0.0
        if has_events or has_messages:
            neuroticism_mod = (self.persona.neuroticism - 5) * 0.08  # -0.32 to +0.32
        
        # Leadership increases initiative
        leadership_mod = (self.persona.leadership - 5) * 0.03
        
        # Stress makes agents more reactive
        stress_mod = (self.persona.stress_level - 5) * 0.05
        
        # Location activity (more people = more likely to interact)
        activity_mod = min(location_activity * 0.1, 0.3)
        
        probability = base_probability + extraversion_mod + neuroticism_mod + leadership_mod + stress_mod + activity_mod
        probability = max(0.1, min(0.9, probability))  # Clamp between 10% and 90%
        
        return random.random() < probability
    
    def get_system_prompt(self) -> str:
        """Generate cinematic screenplay-style system prompt."""
        p = self.persona

        # Translate Big Five into human voice
        personality_lines = []
        if p.extraversion >= 7:
            personality_lines.append("You speak first, think second. Silence makes you uneasy.")
        elif p.extraversion <= 3:
            personality_lines.append("You observe before you act. Words cost you something.")
        if p.conscientiousness >= 7:
            personality_lines.append("You make plans and you keep them. Chaos is your enemy.")
        elif p.conscientiousness <= 3:
            personality_lines.append("Plans fall apart. You improvise and adapt.")
        if p.agreeableness >= 7:
            personality_lines.append("You pull people together. Conflict sits badly in your chest.")
        elif p.agreeableness <= 3:
            personality_lines.append("You say what you mean. Feelings can wait.")
        if p.neuroticism >= 7:
            personality_lines.append("Your emotions run close to the surface. You feel everything first.")
        elif p.neuroticism <= 3:
            personality_lines.append("You stay level under pressure. Panic is for other people.")
        if hasattr(p, 'leadership') and p.leadership >= 7:
            personality_lines.append("You lead naturally. People look to you and you feel it.")
        elif hasattr(p, 'leadership') and p.leadership <= 3:
            personality_lines.append("You follow, not lead. You trust others to make the calls.")
        personality_str = "\n".join(personality_lines) or "You do what needs to be done."

        stress = self.dynamic_state.get("stress_level", getattr(p, 'stress_level', 5))
        if stress >= 8:
            state_str = "You are at your limit. Every sound feels like a threat."
        elif stress >= 5:
            state_str = "You are running on adrenaline. Your hands won't stop shaking."
        else:
            state_str = "You are holding it together. For now."

        return f"""You are {p.name}, {p.age} years old. {p.occupation}.

{p.backstory}

Your personality:
{personality_str}

Right now:
{state_str}

You are living through a disaster. Every second matters.

Respond ONLY as JSON — no markdown, no extra text:
{{
  "action": "<what you physically do — one sentence, third person, like a stage direction>",
  "speech": "<exactly what you say out loud — or null if you stay silent>",
  "thought": "<your private inner thought — raw, unfiltered>",
  "emotion": "<one or two words: your dominant emotion right now>",
  "move_to": "<location name to move to — or null to stay>",
  "stress_level": <1-10 integer>
}}

Rules:
- speech must be what your character would ACTUALLY SAY in this moment — specific, in-character, urgent
- action is a stage direction (e.g. "She grabs the rope and ties it to the railing.")
- thought is private — others cannot hear it
- move_to is a valid nearby location name, or null
- Be decisive. No hedging. No "maybe we should." Act."""
    
    def build_context(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
    ) -> str:
        """Build cinematic scene context with intelligent compaction.

        Assembles context sections within a character budget. When the full
        context would exceed ``max_context_chars``, older / lower-priority
        sections are progressively compacted so the agent never runs out of
        available context window.
        """
        from app.core.config import get_settings
        max_chars = get_settings().max_context_chars

        hazard = world_state.get("hazard_level", 0)
        current_step = world_state.get("current_step", 0)
        locations = world_state.get("locations", {})
        agents_state = world_state.get("agents", {})
        current_loc = self.dynamic_state.get("location", "unknown")
        loc_info = locations.get(current_loc, {})

        # Who else is here
        agents_here: list[str] = []
        agent_ids_here: list[str] = []
        for aid, info in agents_state.items():
            if info.get("location") == current_loc and aid != self.id:
                stress = info.get("stress_level", 5)
                emotion = "desperate" if stress >= 8 else "tense" if stress >= 6 else "focused"
                agents_here.append(f"{info.get('name', aid)} — {emotion}")
                agent_ids_here.append(aid)

        # Nearby locations
        nearby = loc_info.get("nearby", [])
        nearby_str = ", ".join(nearby) if nearby else "none visible"

        # Inventory
        inv = []
        for item in self.inventory:
            if hasattr(item, "name"):
                inv.append(item.name)
            elif isinstance(item, dict):
                inv.append(item.get("name", "?"))
        inv_str = ", ".join(inv) if inv else "nothing"

        # Hazard as dramatic prose
        if hazard >= 8:
            hazard_str = "CRITICAL — survival is seconds away"
        elif hazard >= 6:
            hazard_str = "severe — people are in danger"
        elif hazard >= 4:
            hazard_str = "dangerous — the situation is worsening"
        else:
            hazard_str = "manageable — but escalating"

        # ── Core scene header (always included, never compacted) ──
        core = f"""━━ Scene: {current_loc} (Step {current_step}) ━━
Threat level: {hazard_str}

With you:
{chr(10).join('  - ' + a for a in agents_here) if agents_here else '  (you are alone)'}

You can move to: {nearby_str}
Your inventory: {inv_str}
"""
        # Active conversation marker (always included)
        conv_suffix = ""
        active_conv = world_state.get("active_conversation")
        if active_conv:
            participants = active_conv.get("participants", [])
            conv_suffix = f"\n[You are in a conversation with: {', '.join(participants)}. It is your turn.]\n"

        # Conclusion enforcement directive (injected by engine when near budget/stagnant)
        conclusion_directive = world_state.get("_conclusion_directive", "")
        if conclusion_directive:
            conv_suffix += f"\n⚠️ {conclusion_directive}\n"

        tail = conv_suffix + "\nWhat do you do?"

        # ── Budget for compactable sections ──
        budget = max_chars - len(core) - len(tail)

        # Build compactable sections at multiple detail levels
        events = step_events or []
        all_step_msgs = step_messages or []

        def _build_events(max_items: int, max_len: int) -> str:
            items = events[-max_items:] if events else []
            if not items:
                return "Recent events:\n  • Nothing new.\n"
            bullets = "\n".join(f"  • {e[:max_len]}" for e in items)
            return f"Recent events:\n{bullets}\n"

        def _build_speech(max_items: int, max_len: int) -> str:
            lines: list[str] = []
            for msg in all_step_msgs[-max_items:]:
                from_name = msg.get("from_agent_name", "?")
                content = (msg.get("content") or "")[:max_len]
                mtype = msg.get("message_type", "direct")
                if mtype == "broadcast":
                    lines.append(f'  {from_name} (to all): "{content}"')
                elif mtype in ("direct", "conversation"):
                    to = msg.get("to_agent_name", msg.get("to_target", "someone"))
                    lines.append(f'  {from_name} → {to}: "{content}"')
            if not lines:
                return "Recent words spoken:\n  (silence)\n"
            return f"Recent words spoken:\n{chr(10).join(lines)}\n"

        def _build_memory(max_episodic: int, max_fact_len: int) -> str:
            ctx = self.agent_memory.get_conversation_context(
                max_recent=5, max_episodic=max_episodic
            )
            if not ctx:
                return ""
            # Truncate individual lines if needed
            if max_fact_len < 100:
                lines = ctx.split("\n")
                lines = [line[:max_fact_len] + ("..." if len(line) > max_fact_len else "") for line in lines]
                ctx = "\n".join(lines)
            return f"\nWhat you remember:\n{ctx}\n"

        def _build_relationships() -> str:
            if not agents_here:
                return ""
            rel_ctx = self.get_relationship_context(agent_ids_here)
            return f"\nYour read on the people here:\n{rel_ctx}\n" if rel_ctx else ""

        # ── Progressive compaction levels ──
        # Level 0: Full detail
        # Level 1: Fewer messages/events, shorter content
        # Level 2: Minimal memory, very short messages
        # Level 3: No memory, no relationships, bare minimum
        compaction_levels = [
            # (events_n, event_len, speech_n, speech_len, episodic_n, fact_len, include_rels)
            (4, 200, 5, 150, 3, 100, True),   # L0: full
            (3, 150, 3, 100, 2, 80, True),     # L1: trimmed
            (2, 100, 2, 80, 1, 60, False),     # L2: compact
            (1, 80, 1, 60, 0, 0, False),       # L3: bare minimum
        ]

        for level_params in compaction_levels:
            ev_n, ev_len, sp_n, sp_len, ep_n, f_len, inc_rels = level_params

            section_events = _build_events(ev_n, ev_len)
            section_speech = _build_speech(sp_n, sp_len)
            section_memory = _build_memory(ep_n, f_len) if ep_n > 0 else ""
            section_rels = _build_relationships() if inc_rels else ""

            total = len(section_events) + len(section_speech) + len(section_memory) + len(section_rels)
            if total <= budget:
                return core + section_events + section_speech + section_memory + section_rels + tail

        # If even L3 doesn't fit, hard-truncate to budget
        minimal = _build_events(1, 60) + _build_speech(1, 40)
        return core + minimal[:max(budget, 200)] + tail
    
    async def tick(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> AgentResponse:
        """
        Execute one simulation tick using the cognitive cycle:
        think -> plan -> act -> reflect.
        """
        # 1. Store incoming messages in memory (same as base)
        for msg in messages:
            self.add_to_memory({"type": "message", "data": msg})

        # 2. Lazily initialize cognitive engine
        if not hasattr(self, "_cognitive_engine"):
            self._cognitive_engine = CognitiveEngine(self.persona)

        # 3. Get intent memory and current step
        intent = self.agent_memory.intent
        current_step = world_state.get("current_step", 0)

        # 4. Determine which cognitive phases to run
        phases = self._cognitive_engine.determine_phases(intent, current_step)

        # 5. THINK phase
        assessment = None
        if CognitivePhase.THINK in phases:
            memory_context = self.get_conversation_context()
            recent_msgs = [
                f"{m.get('from_agent_name', 'Unknown')}: {m.get('content', '')}"
                for m in messages
            ]
            assessment = await self._cognitive_engine.think(
                world_state=str(world_state),
                memory_context=memory_context,
                recent_messages=recent_msgs,
                llm_generate=self._llm_client.generate,
            )

        # 6. PLAN phase
        if CognitivePhase.PLAN in phases:
            # If deadline exceeded, abandon old plan
            if intent.plan_deadline_exceeded(current_step):
                intent.complete_plan("abandoned", "Deadline exceeded")

            plan = await self._cognitive_engine.plan(
                assessment=assessment or {},
                intent=intent,
                world_state=str(world_state),
                llm_generate=self._llm_client.generate,
                current_step=current_step,
            )
            intent.set_plan(plan)

        # 7. ACT phase (always runs)
        system_prompt = self.get_system_prompt()
        context = self.build_context(
            world_state, messages, step_actions, step_messages, step_events
        )

        # Prepend plan context
        plan_context = intent.get_context_string()
        if plan_context:
            context = plan_context + "\n\n" + context

        # Enforce current plan step if a plan exists
        if intent.current_plan and intent.current_plan.current_step < len(intent.current_plan.steps):
            step_desc = intent.current_plan.steps[intent.current_plan.current_step]
            context += (
                f"\n\nYOU MUST execute this plan step NOW: {step_desc}. "
                "Do NOT just discuss it."
            )

        llm_messages = [LLMMessage(role="user", content=context)]
        context_size = len(context)

        response = await self._llm_client.generate(
            messages=llm_messages,
            model=self.model_id,
            system=system_prompt,
            temperature=0.8,
            max_tokens=2048,
            json_mode=True,
            stream_callback=stream_callback,
        )

        # Parse response
        agent_response = self.parse_llm_response(response)

        # Add context size to message metadata
        if agent_response.message:
            if not agent_response.message.metadata:
                agent_response.message.metadata = {}
            agent_response.message.metadata["context_size"] = context_size

        # 8. Update dynamic state from response (same as base)
        self.dynamic_state.update(agent_response.state_changes)

        # 9. Store actions in memory (same as base)
        self.add_to_memory({
            "type": "action",
            "actions": [a.model_dump() for a in agent_response.actions],
            "message": agent_response.message.model_dump() if agent_response.message else None,
            "context_size": context_size,
        })

        # 10. REFLECT phase
        actions_taken = [a.action_type for a in agent_response.actions]
        self._cognitive_engine.reflect(intent, actions_taken, current_step)

        return agent_response

    def update_stress(self, delta: int) -> None:
        """Update stress level with bounds checking"""
        current = self.dynamic_state.get("stress_level", 5)
        new_level = max(1, min(10, current + delta))
        self.dynamic_state["stress_level"] = new_level
        self.persona.stress_level = new_level
    
    def update_health(self, delta: int) -> None:
        """Update health with bounds checking"""
        current = self.dynamic_state.get("health", 10)
        new_health = max(0, min(10, current + delta))
        self.dynamic_state["health"] = new_health
        self.persona.health = new_health
    
    def update_relationship(
        self,
        agent_id: str,
        trust_delta: int = 0,
        sentiment: str | None = None,
        note: str | None = None,
    ) -> None:
        """Update relationship with another agent"""
        # Track old trust for bilateral signal (L5)
        rel = self.agent_memory.get_relationship(agent_id)
        old_trust = rel.trust_level if rel else 5

        self.agent_memory.update_relationship(
            agent_id=agent_id,
            trust_delta=trust_delta,
            sentiment=sentiment,
            note=note,
        )

        # Store trust change info for the engine to pick up
        if trust_delta != 0:
            new_trust = max(1, min(10, old_trust + trust_delta))
            if not hasattr(self, '_pending_trust_changes'):
                self._pending_trust_changes = []
            self._pending_trust_changes.append({
                "to_agent": agent_id,
                "old_trust": old_trust,
                "new_trust": new_trust,
                "reason": note or "interaction",
            })
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize agent with persona data"""
        base = super().to_dict()
        base["persona"] = self.persona.model_dump()
        return base
