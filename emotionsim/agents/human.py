"""Human Agent - roleplays as a person with personality"""
import random
from typing import Any, Callable, Awaitable

from emotionsim.agents.base import Agent
from emotionsim.agents.cognitive_engine import CognitiveEngine, CognitivePhase
from emotionsim.agents.graph_memory import GraphMemory
from emotionsim.agents.lightweight_agent import LightweightAgent
from emotionsim.llm.base import LLMMessage
from emotionsim.llm.router import LLMRouter
from emotionsim.llm.schemas import ActResponse, validate_content
from emotionsim.schemas.agent import AgentResponse, AgentAction, AgentMessage
from emotionsim.schemas.persona import Persona


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
        background: bool = False,
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

        # Graph-backed memory (MiroFish). Attached by the engine when
        # settings.graph_memory_enabled is on and a knowledge graph exists
        # for this run. When None, the agent uses flat sliding-window memory.
        self.graph_memory: GraphMemory | None = None
        # Deduplication set for observations already stored in the graph.
        self._graph_seen_events: set[str] = set()

        # Hybrid population mode (LightweightAgent scaling).
        # Background agents act via rule-based decisions with zero LLM calls;
        # the engine promotes them to full LLM agents on demand and demotes
        # them back after a period of inactivity.
        self.background = background
        self.started_background = background
        self._steps_since_promotion = 0
        self._promote_reason: str | None = None
        self._lightweight_agent: LightweightAgent | None = None
        self.dynamic_state["_background"] = background

        # Theory of Mind: beliefs about other agents (opt-in, see theory_of_mind.py)
        self.theory_of_mind = None

        # Continuous emotion dimensions (valence/arousal) — off by default
        # (EMOTION_DIMENSIONS_ENABLED=false keeps the default path byte-identical).
        # Lazily initialized on first tick/build_context via get_settings().
        self.emotion_dimensions_enabled = False
        self.valence = 0.0
        self.arousal = 0.0
        self._emotion_base_valence = 0.0
        self._emotion_base_arousal = 0.0

    def _maybe_init_theory_of_mind(self) -> None:
        """Create the ToM belief store when the config flag is on."""
        if self.theory_of_mind is not None:
            return
        from emotionsim.core.config import get_settings

        if get_settings().theory_of_mind_enabled is True:
            from emotionsim.agents.theory_of_mind import TheoryOfMind

            self.theory_of_mind = TheoryOfMind(self.id, self.name)

    def _maybe_init_emotion_dimensions(self) -> None:
        """Enable + baseline emotion dimensions when the config flag is on."""
        from emotionsim.core.config import get_settings

        if get_settings().emotion_dimensions_enabled is True:
            self.emotion_dimensions_enabled = True
            if not self.dynamic_state.get("valence", None):
                from emotionsim.agents.emotion_dimensions import personality_baselines

                base_v, base_a = personality_baselines(self.persona)
                self._emotion_base_valence = base_v
                self._emotion_base_arousal = base_a
                self.valence = self.dynamic_state.get("valence", base_v)
                self.arousal = self.dynamic_state.get("arousal", base_a)
                self.dynamic_state["valence"] = round(self.valence, 3)
                self.dynamic_state["arousal"] = round(self.arousal, 3)

    def update_emotion_dimensions(
        self,
        world_state: dict[str, Any],
        helped: bool = False,
        danger_observed: bool = False,
    ) -> None:
        """One tick of valence/arousal dynamics (events + relaxation to baseline)."""
        if not self.emotion_dimensions_enabled:
            return
        from emotionsim.agents.emotion_dimensions import compute_emotion_update
        from emotionsim.core.config import get_settings

        stress = self.dynamic_state.get("stress_level", self.persona.stress_level)
        self.valence, self.arousal = compute_emotion_update(
            self.valence,
            self.arousal,
            self._emotion_base_valence,
            self._emotion_base_arousal,
            stress,
            world_state.get("hazard_level", 0),
            helped,
            danger_observed,
            decay=get_settings().emotion_decay,
        )
        self.dynamic_state["valence"] = round(self.valence, 3)
        self.dynamic_state["arousal"] = round(self.arousal, 3)

    def _apply_emotion_pull(self) -> None:
        """Pull valence/arousal toward the dominant emotion of the last decision.

        Uses the parsed act response's emotion word (from the LLM or the
        rule-based background decision), mapped through EMOTION_LEXICON.
        """
        if not self.emotion_dimensions_enabled:
            return
        from emotionsim.agents.emotion_dimensions import (
            clamp,
            emotion_to_vector,
        )
        from emotionsim.core.config import get_settings

        cinematic = getattr(self, "_last_cinematic", {}) or {}
        vec = emotion_to_vector(cinematic.get("emotion", ""))
        if vec is None:
            return
        pull = get_settings().emotion_lm_pull
        self.valence = clamp(self.valence + pull * (vec[0] - self.valence))
        self.arousal = clamp(self.arousal + pull * (vec[1] - self.arousal))
        self.dynamic_state["valence"] = round(self.valence, 3)
        self.dynamic_state["arousal"] = round(self.arousal, 3)

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

        # Arousal (emotion dimensions, when enabled) makes agents more reactive
        arousal_mod = 0.0
        if getattr(self, "emotion_dimensions_enabled", False):
            from emotionsim.agents.emotion_dimensions import clamp

            arousal_mod = clamp(self.arousal) * 0.15

        # Location activity (more people = more likely to interact)
        activity_mod = min(location_activity * 0.1, 0.3)

        probability = base_probability + extraversion_mod + neuroticism_mod + leadership_mod + stress_mod + activity_mod + arousal_mod
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
        from emotionsim.core.config import get_settings
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
"""

        # Goal tree context (mission -> group -> individual, Step 6)
        goal_ctx = world_state.get("goal_tree")
        if goal_ctx:
            core += f"\n{goal_ctx}\n"

        # Governance warning for a previously flagged action (Step 6)
        gov_ctx = world_state.get("governance")
        if gov_ctx:
            categories = ", ".join(gov_ctx.get("categories", []))
            core += (
                f"\n⚠️ GOVERNANCE WARNING: Your last action was flagged as "
                f"ethically significant ({categories}). "
                f"Consider the consequences of your choices.\n"
            )

        # Continuous emotion dimensions (valence/arousal, opt-in)
        self._maybe_init_emotion_dimensions()
        if self.emotion_dimensions_enabled:
            from emotionsim.agents.emotion_dimensions import emotion_line

            core += f"\n{emotion_line(self.valence, self.arousal)}\n"

        # Theory of Mind: what I believe about the others (opt-in)
        self._maybe_init_theory_of_mind()
        if self.theory_of_mind is not None:
            tom_section = self.theory_of_mind.beliefs_for_prompt()
            if tom_section:
                core += f"\n{tom_section}\n"

        # Eval prompt variant (Step 8): experiment instruction injected into
        # the prompt so the harness can compare prompt variants offline.
        variant = world_state.get("_prompt_variant")
        if variant:
            core += f"\n[Experiment instruction: {variant}]\n"

        core += f"""
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
            rumors = world_state.get("_rumors") or {}
            for msg in all_step_msgs[-max_items:]:
                from_name = msg.get("from_agent_name", "?")
                content = (msg.get("content") or "")[:max_len]
                # Rumor distortion: retold stories surface degraded (opt-in).
                if rumors:
                    from emotionsim.simulation.rumor import (
                        distort_text,
                        find_chain,
                    )

                    cid = find_chain(
                        rumors, content, 0.5, exclude_reader=self.id
                    )
                    if cid is not None:
                        info = rumors.get(cid, {})
                        content = distort_text(
                            content,
                            info.get("hops", 1),
                            cid,
                            fidelity_drop=get_settings().rumor_fidelity_drop,
                        )[:max_len]
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
                max_recent=5, max_episodic=max_episodic,
                current_step=current_step,
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
        # Background (lightweight) agents act via rule-based decisions,
        # never calling the LLM.
        if self.background:
            return await self._background_tick(world_state, messages, current_step=world_state.get("current_step", 0))

        self._maybe_init_emotion_dimensions()
        if self.emotion_dimensions_enabled:
            # Did someone help me this step? Did I observe danger?
            helped = any(
                a.get("action") == "help" and a.get("target") == self.id
                for a in (step_actions or [])
            )
            danger_observed = any(
                any(w in (e or "").lower() for w in ("collaps", "fire", "flood", "danger", "injur", "falling"))
                for e in (step_events or [])
            ) or world_state.get("hazard_level", 0) >= 7
            self.update_emotion_dimensions(world_state, helped=helped, danger_observed=danger_observed)

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
                llm_generate=LLMRouter.generate_with_fallback,
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
                llm_generate=LLMRouter.generate_with_fallback,
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

        # Prepend graph-backed memory context (relevance recall, MiroFish)
        graph_context = await self._recall_graph_context(world_state, messages)
        if graph_context:
            context = graph_context + "\n\n" + context

        # Enforce current plan step if a plan exists
        if intent.current_plan and intent.current_plan.current_step < len(intent.current_plan.steps):
            step_desc = intent.current_plan.steps[intent.current_plan.current_step]
            context += (
                f"\n\nYOU MUST execute this plan step NOW: {step_desc}. "
                "Do NOT just discuss it."
            )

        llm_messages = [LLMMessage(role="user", content=context)]
        context_size = len(context)

        response = await LLMRouter.generate_with_fallback(
            messages=llm_messages,
            system=system_prompt,
            temperature=0.8,
            max_tokens=2048,
            json_mode=True,
            stream_callback=stream_callback,
            model_override=self.model_id,
            agent_role=self.role,
        )

        # Structured-output enforcement (Step 3): validate the act output
        # against the cinematic schema; retry once with the validation error
        # injected into the prompt. Final fallback remains defensive parsing.
        ok, _, err = validate_content(response.content, ActResponse)
        if not ok:
            response = await LLMRouter.generate_with_fallback(
                messages=llm_messages
                + [
                    LLMMessage(
                        role="user",
                        content=(
                            f"Your previous response failed validation: {err}\n"
                            "Return ONLY valid JSON with fields: action (string), "
                            "speech (string or null), thought (string or null), "
                            "emotion (string or null), move_to (string or null), "
                            "stress_level (integer 1-10)."
                        ),
                    )
                ],
                system=system_prompt,
                temperature=0.8,
                max_tokens=2048,
                json_mode=True,
                stream_callback=stream_callback,
                model_override=self.model_id,
                agent_role=self.role,
            )

        # Parse response
        agent_response = self.parse_llm_response(response)

        # Emotion dimensions: pull toward the LLM-stated dominant emotion.
        self._apply_emotion_pull()

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

        # 9b. Store graph-backed memories (observations + decision)
        await self._store_graph_memories(agent_response, current_step, step_events)

        # 9c. Batched reflection (every N steps): distill lessons into memory
        await self._maybe_reflect(current_step)

        # 10. REFLECT phase
        actions_taken = [a.action_type for a in agent_response.actions]
        self._cognitive_engine.reflect(intent, actions_taken, current_step)

        return agent_response

    # ── Graph-backed memory (MiroFish) ────────────────────────────────────

    def _graph_situation(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> str:
        """Build the current-situation query used for relevance recall.

        Combines the agent's location, hazard level, nearby places and the
        most recent speech into a natural-language query — graph memories
        are recalled by *relevance* to this, not by recency.
        """
        current_loc = self.dynamic_state.get("location", "unknown")
        hazard = world_state.get("hazard_level", 0)
        loc_info = world_state.get("locations", {}).get(current_loc, {})
        nearby = ", ".join(loc_info.get("nearby", []))
        parts = [
            f"I am at {current_loc}.",
            f"Hazard level: {hazard}.",
        ]
        if nearby:
            parts.append(f"Nearby: {nearby}.")
        recent = [m.get("content", "") for m in (messages or []) if m.get("content")]
        if recent:
            parts.append("Recent talk: " + " ".join(recent[-5:]))
        return " ".join(parts)

    async def _recall_graph_context(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> str:
        """Recall relevant graph memories + facts for the current situation.

        Returns an empty string on any failure so the simulation continues
        with flat-memory context (graceful fallback).
        """
        gm = self.graph_memory
        if gm is None:
            return ""
        try:
            situation = self._graph_situation(world_state, messages)
            return await gm.build_context(situation, max_memories=5, max_graph_facts=3)
        except Exception:
            return ""

    def _graph_link_entities(self) -> list[str] | None:
        """Entity ids to link a new memory node to (current location)."""
        gm = self.graph_memory
        if gm is None:
            return None
        loc = self.dynamic_state.get("location")
        eid = gm.entity_id_for(loc) if loc else None
        return [eid] if eid else None

    async def _store_graph_memories(
        self,
        response: AgentResponse,
        current_step: int,
        step_events: list[str] | None = None,
    ) -> None:
        """Persist this tick's observations + decision as graph memory nodes.

        Observations come from world events (deduplicated, capped per step);
        the decision records the agent's action, emotion and speech. Both are
        linked to the current location entity when one was seeded for it.
        Any failure is swallowed — graph memory is best-effort.
        """
        gm = self.graph_memory
        if gm is None:
            return
        try:
            # Observations from step events (deduped, capped per step)
            seen = self._graph_seen_events
            new_events = [e for e in (step_events or []) if e and e not in seen]
            for evt in new_events[:3]:
                seen.add(evt)
                await gm.store(
                    content=evt,
                    memory_type="observation",
                    importance=5,
                    step_number=current_step,
                    linked_entity_ids=self._graph_link_entities(),
                )

            # Decision: what the agent did this tick
            cinematic = getattr(self, "_last_cinematic", {}) or {}
            action = cinematic.get("action") or "I kept going."
            emotion = cinematic.get("emotion", "")
            speech = response.message.content if response.message else None
            stress = self.dynamic_state.get("stress_level", 5)

            content = f"Step {current_step}: I {action}"
            if emotion:
                content += f" Feeling {emotion}."
            if speech:
                content += f" I said: \"{speech}\""

            importance = 8 if stress >= 8 else 6 if stress >= 6 else 4
            valence = 0.0
            el = emotion.lower()
            if any(w in el for w in ("fear", "panic", "despair", "anger", "angry")):
                valence = -0.4
            elif any(w in el for w in ("hope", "calm", "relief", "grateful")):
                valence = 0.3

            await gm.store(
                content=content,
                memory_type="decision",
                importance=importance,
                emotional_valence=valence,
                step_number=current_step,
                linked_entity_ids=self._graph_link_entities(),
            )
        except Exception:
            return

    # ── Hybrid population mode (LightweightAgent scaling) ────────────────

    def _lightweight(self) -> LightweightAgent:
        """Lazily construct the rule-based decision engine for this agent."""
        if self._lightweight_agent is None:
            self._lightweight_agent = LightweightAgent(
                agent_id=self.id,
                name=self.name,
                persona=self.persona,
                location=self.dynamic_state.get("location", "unknown"),
            )
        return self._lightweight_agent

    def should_promote(
        self,
        addressed_directly: bool = False,
        in_active_scene: bool = False,
    ) -> bool:
        """Whether this background agent should be promoted to a full LLM agent."""
        return self._lightweight().should_promote(
            addressed_directly=addressed_directly,
            in_active_scene=in_active_scene,
        )

    def promote(self, reason: str = "") -> None:
        """Promote to a full LLM agent (foreground)."""
        self.background = False
        self._steps_since_promotion = 0
        self._promote_reason = reason
        self.dynamic_state["_background"] = False

    def demote(self) -> None:
        """Demote back to rule-based background behavior."""
        self.background = True
        self._steps_since_promotion = 0
        self.dynamic_state["_background"] = True

    def _cinematic_action_text(self, decision: Any) -> str:
        """Human-readable stage direction for a lightweight decision."""
        texts = {
            "speak": "They speak to those nearby.",
            "move": f"They move toward {decision.target_location or 'another location'}.",
            "help": f"They go to help {decision.target_agent or 'someone'}.",
            "gather": "They search for useful supplies.",
            "observe": "They watch the situation carefully.",
            "wait": "They wait and keep alert.",
        }
        return texts.get(decision.action_type, f"They {decision.action_type}.")

    def _cinematic_emotion(self, action_type: str) -> str:
        """A simple emotion label for a lightweight action."""
        return {"observe": "anxious", "wait": "tense"}.get(action_type, "determined")

    async def _background_tick(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        current_step: int,
    ) -> AgentResponse:
        """Rule-based decision tick with zero LLM calls (background mode)."""
        agents_state = world_state.get("agents", {})
        my_loc = self.dynamic_state.get("location", "unknown")
        nearby = [
            info.get("name", aid)
            for aid, info in agents_state.items()
            if aid != self.id and info.get("location") == my_loc
        ]

        decision = self._lightweight().tick(
            world_state=world_state,
            nearby_agents=nearby,
            recent_messages=messages,
            step=current_step,
        )

        actions: list[AgentAction] = []
        message: AgentMessage | None = None
        if decision.action_type == "move" and decision.target_location:
            actions.append(
                AgentAction(action_type="move", target=decision.target_location, parameters={})
            )
        elif decision.action_type == "gather":
            actions.append(AgentAction(action_type="search", target=None, parameters={}))
        elif decision.action_type == "speak" and decision.message:
            message = AgentMessage(
                content=decision.message,
                to_target="broadcast",
                message_type="broadcast",
            )
        elif decision.action_type == "help" and decision.target_agent:
            message = AgentMessage(
                content=f"I'm coming to help, {decision.target_agent}!",
                to_target=decision.target_agent,
                message_type="direct",
            )

        self._last_cinematic = {
            "action": self._cinematic_action_text(decision),
            "thought": decision.reasoning,
            "emotion": self._cinematic_emotion(decision.action_type),
            "speech": message.content if message else None,
        }

        # Emotion dimensions from the rule-based decision's inferred emotion.
        if self.emotion_dimensions_enabled:
            self.update_emotion_dimensions(world_state)
            self._apply_emotion_pull()

        response = AgentResponse(
            actions=actions,
            message=message,
            state_changes={},
            reasoning=decision.reasoning,
        )
        self.add_to_memory({
            "type": "action",
            "actions": [a.model_dump() for a in actions],
            "message": message.model_dump() if message else None,
            "background": True,
        })
        return response

    def _reflection_interval(self) -> int:
        from emotionsim.core.config import get_settings
        return get_settings().reflection_interval_steps

    async def _maybe_reflect(self, current_step: int) -> None:
        """Batched LLM reflection every N steps (best-effort).

        Distills the recent activity window into a summary + lessons stored
        as episodic memories with importance, so agents visibly learn over a
        run. Any failure is swallowed — reflection never breaks the tick.
        """
        interval = self._reflection_interval()
        if interval <= 0 or current_step <= 0 or current_step % interval != 0:
            return
        if self.background:
            return
        try:
            from emotionsim.llm.schemas import ReflectionResponse, validate_content

            recent = self.agent_memory.get_recent_events(limit=20)
            if not recent:
                return
            lines: list[str] = []
            for evt in recent[-12:]:
                if evt.get("type") == "message":
                    data = evt.get("data", {})
                    lines.append(
                        f"{data.get('from_agent_name', '?')}: {data.get('content', '')}"
                    )
                elif evt.get("type") == "action":
                    acts = evt.get("actions", [])
                    lines.append(
                        "I did: " + (", ".join(a.get("action_type", "") for a in acts) or "nothing")
                    )
                elif evt.get("type") == "observation":
                    lines.append(f"I observed: {evt.get('content', '')}")
            activity = "\n".join(lines) or "No notable activity."

            system = (
                f"You are {self.name}, reflecting on what just happened. "
                "Respond with JSON: summary (one sentence), "
                "lessons (list of 1-3 concise lessons learned), "
                "importance (integer 1-10)."
            )
            user = (
                f"Recent activity:\n{activity}\n\n"
                "Reflect on this. What did you learn that you should remember?"
            )
            response = await LLMRouter.generate_with_fallback(
                messages=[LLMMessage(role="user", content=user)],
                system=system,
                temperature=0.5,
                max_tokens=512,
                json_mode=True,
                model_override=self.model_id,
                agent_role=self.role,
            )
            ok, parsed, _ = validate_content(response.content, ReflectionResponse)
            if not ok:
                return
            self.agent_memory.add_lesson(parsed.summary, current_step, parsed.importance)
            for lesson in parsed.lessons[:3]:
                self.agent_memory.add_lesson(lesson, current_step, max(1, parsed.importance - 1))
        except Exception:
            return

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
