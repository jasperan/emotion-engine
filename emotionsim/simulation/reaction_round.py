"""ReactionRound: intra-step reactive ticks (Step 7 refactor).

Moved verbatim from the engine monolith. After all agents tick, agents who
received direct messages or proposals this step get a quick reactive tick
with restricted actions — enabling same-step proposal->response instead of
2+ step latency. Respects hybrid-population budget + background mode.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from emotionsim.agents.human import HumanAgent
from emotionsim.simulation.negotiation import ProposalState


class ReactionRound:
    """Runs the intra-step reaction round for the engine."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    async def execute(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        rt = self.runtime
        reactive_agents = set()

        # Agents with pending proposals that were created this step
        for prop in rt.negotiation._proposals.values():
            if (
                prop.created_at_step == rt.current_step
                and prop.state == ProposalState.PENDING
                and prop.target_id
            ):
                reactive_agents.add(prop.target_id)

        # Agents who received direct messages this step
        for msg in step_messages:
            if msg.get("message_type") == "direct":
                target = msg.get("to_target")
                if target and target in rt.agents:
                    reactive_agents.add(target)

        if not reactive_agents:
            return

        # Hybrid populations: the reaction round must respect the per-step LLM
        # budget and background mode (it previously bypassed _tick_single_agent
        # and could leak unbudgeted LLM calls).
        budget = rt._settings.max_llm_agents_per_step
        budget_ok = budget <= 0 or rt._step_llm_budget_left > 0

        for agent_id in reactive_agents:
            agent = rt.agents.get(agent_id)
            if not agent or agent.role != "human":
                continue
            if not rt.supervisor.is_agent_available(agent_id):
                continue

            messages = rt.message_bus.get_messages(agent_id)
            if not messages:
                continue

            # Background agents (and foreground agents beyond the LLM budget)
            # react via rule-based decisions — no LLM call.
            if isinstance(agent, HumanAgent) and (agent.background or not budget_ok):
                await rt._tick_background(
                    agent_id, agent, rt.world_state, messages,
                    step_actions, step_messages, step_events,
                    False, None,
                )
                continue

            # Build minimal reactive context
            agent_world_state = rt.world_state.copy()
            agent_world_state["negotiations"] = rt.negotiation.get_negotiation_context(agent_id)
            agent_world_state["_reactive_round"] = True

            if isinstance(agent, HumanAgent):
                rt._step_llm_budget_left -= 1

            response = await rt.supervisor.supervised_tick(
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
                    await rt._process_agent_action(
                        agent_id, agent, action, step_actions, step_messages,
                        False, None,
                    )

            if response.message and response.message.content.strip():
                stored_msg = rt._route_message(agent_id, agent, response.message, False, None)
                step_messages.append(stored_msg)
                rt.diff_tracker.record_message()
                await rt._persist_message(agent_id, response.message)

                rt.on_event("message", {
                    "type": "message",
                    "data": stored_msg,
                    "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S")
                })

            rt._update_agents_in_world_state()
